"""
导入器基类 - 定义所有导入器的通用接口和共享逻辑
"""
import csv
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


@dataclass
class ImportResult:
    """导入结果"""
    total: int = 0
    ignored_count: int = 0
    success: int = 0
    skipped: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    imported_transactions: List[Any] = field(default_factory=list)


class BaseImporter(ABC):
    """导入器抽象基类"""

    def __init__(self, db):
        self.db = db

    @abstractmethod
    def can_handle(self, filepath: str) -> bool:
        """判断是否能处理该文件"""
        ...

    @abstractmethod
    def import_file(self, filepath: str, mode: str = "skip") -> ImportResult:
        """导入文件"""
        ...

    def _normalize_date(self, date_str: str) -> str:
        """
        标准化日期格式为 YYYY-MM-DD HH:MM:SS

        支持的输入格式：
        - 2024-01-01 12:30:00
        - 2024-01-01 12:30
        - 2024/01/01 12:30:00
        - 2024/1/1 12:30:00
        - 2024-01-01
        - 2024/01/01
        - 2024/1/1
        - 01/01/2024 (美式)
        """
        if not date_str:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        date_str = date_str.strip()

        # 如果已经包含时间部分
        if len(date_str) > 10:
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y/%m/%d %H:%M",
            ]
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue

        # 只有日期部分
        formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d 00:00:00")
            except ValueError:
                continue

        raise ValueError(f"无法解析日期格式: {date_str}")

    def _parse_amount(self, amount_str: str) -> float:
        """解析金额字符串"""
        if not amount_str:
            return 0.0
        amount_str = amount_str.replace("¥", "").replace(",", "").strip()
        return float(amount_str)

    def _infer_category(self, description: str, amount: float = 0.0) -> Optional[str]:
        """
        根据描述推断分类

        使用关键词匹配作为后备方案（LLM 推断在 AccountingService 层处理）
        """
        keywords = {
            "早餐": "早餐", "午餐": "午餐", "晚餐": "晚餐",
            "地铁": "地铁", "公交": "公交", "打车": "打车",
            "高铁": "高铁", "飞机": "飞机",
            "工资": "工资", "奖金": "奖金",
            "会员": "会员订阅",
        }
        for keyword, category_name in keywords.items():
            if keyword in description:
                return category_name
        return None

    def _read_csv_with_encoding_detection(self, filepath: str) -> Tuple[List[Dict], List[str]]:
        """
        读取 CSV 文件，自动检测编码

        尝试顺序：utf-8-sig -> utf-8 -> gbk -> gb2312 -> gb18030

        Returns:
            (rows, fieldnames)
        """
        encodings = ["utf-8-sig", "utf-8", "gbk", "gb2312", "gb18030"]

        for encoding in encodings:
            try:
                with open(filepath, "r", encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    if rows:
                        return rows, reader.fieldnames or []
            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception:
                continue

        raise ValueError(f"无法读取文件 {filepath}，尝试了所有编码方式均失败")

    def _build_metadata(self, source: str, transaction_id: str, raw_data: Dict) -> str:
        """构建 metadata JSON 字符串"""
        metadata = {
            "source": source,
            "transaction_id": transaction_id,
            "raw_data": {k: v for k, v in raw_data.items() if v},
        }
        return json.dumps(metadata, ensure_ascii=False)

    def _get_or_create_account(self, account_name: str) -> Any:
        """获取或创建账户"""
        from ..models import Account

        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE name = ?", (account_name,))
        row = cursor.fetchone()
        if row:
            return Account.from_row(row)

        # 创建新账户
        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO accounts (name, type, balance, created_at, updated_at) VALUES (?, ?, 0, ?, ?)",
            (account_name, "other", now, now),
        )
        self.db.conn.commit()
        cursor.execute("SELECT * FROM accounts WHERE id = ?", (cursor.lastrowid,))
        return Account.from_row(cursor.fetchone())

    def _insert_transaction_no_recalc(
        self,
        description: str,
        amount: float,
        date: str,
        category_name: Optional[str],
        account_name: str,
        metadata_json: Optional[str],
    ) -> Any:
        """
        插入交易但不重新计算余额（用于批量导入）

        返回插入的 Transaction 对象
        """
        from ..models import Transaction

        date = self._normalize_date(date)

        account = self._get_or_create_account(account_name)

        category_id = None
        if category_name:
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
            row = cursor.fetchone()
            if row:
                category_id = row[0]

        trans_type = "income" if amount > 0 else "expense"

        cursor = self.db.conn.cursor()
        now = datetime.now().isoformat()

        cursor.execute(
            """
            INSERT INTO transactions (date, type, amount, running_balance, category_id,
                                     account_id, description, metadata, created_at, updated_at)
            VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?, ?)
            """,
            (
                date,
                trans_type,
                abs(amount),
                category_id,
                account.id,
                description,
                metadata_json,
                now,
                now,
            ),
        )

        transaction_id = cursor.lastrowid
        self.db.conn.commit()

        cursor.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,))
        tx = Transaction.from_row(cursor.fetchone())
        tx.account_name = account.name
        tx.category_name = category_name
        return tx

    def _recalculate_balances_backwards(
        self, account_id: int, transaction_ids: List[int]
    ) -> None:
        """
        从当前余额倒推计算所有交易的 running_balance

        对指定账户，按时间倒序遍历所有交易，从当前余额倒推每笔交易后的余额
        """
        cursor = self.db.conn.cursor()

        # 获取账户当前余额
        cursor.execute("SELECT balance FROM accounts WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        if not row:
            return
        current_balance = row[0]

        # 获取该账户所有交易，按时间倒序
        cursor.execute(
            """
            SELECT id, type, amount FROM transactions
            WHERE account_id = ?
            ORDER BY date DESC, id DESC
            """,
            (account_id,),
        )
        transactions = cursor.fetchall()

        if not transactions:
            return

        balance_updates = []
        for tx in transactions:
            balance_updates.append((current_balance, tx["id"]))

            if tx["type"] == "income":
                current_balance -= tx["amount"]
            else:
                current_balance += tx["amount"]

        for balance, tx_id in balance_updates:
            cursor.execute(
                "UPDATE transactions SET running_balance = ? WHERE id = ?",
                (balance, tx_id),
            )

        self.db.conn.commit()