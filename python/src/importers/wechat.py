"""
微信 CSV 导入器

处理微信导出的交易记录 CSV 文件。

微信 CSV 格式特点：
- 表头：交易时间, 交易类型, 交易对方, 商品, 收/支, 金额(元), 支付方式, 当前状态, 交易单号, 商户单号, 备注
- 只导入"支付方式"为"零钱"的交易
- 跳过失败/关闭/撤销/已拒绝/已取消的交易
"""
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from .base import BaseImporter, ImportResult


class WechatImporter(BaseImporter):
    """微信 CSV 导入器"""
    name = "wechat"
    display_name = "微信"

    # 微信标准表头
    WECHAT_HEADERS = [
        "交易时间", "交易类型", "交易对方", "商品", "收/支",
        "金额(元)", "支付方式", "当前状态", "交易单号", "商户单号", "备注",
    ]

    # 需要跳过的交易状态
    FAIL_KEYWORDS = ["失败", "关闭", "撤销", "已拒绝", "已取消"]

    def can_handle(self, filepath: str) -> bool:
        """检测是否为微信 CSV 文件"""
        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                first_line = f.readline().strip()
                # 微信 CSV 表头特征
                if "交易时间" in first_line and "交易类型" in first_line and "交易对方" in first_line:
                    return True
            return False
        except Exception:
            return False

    def import_file(self, filepath: str, mode: str = "skip") -> ImportResult:
        """导入微信 CSV 文件"""
        result = ImportResult()

        try:
            csv_file = Path(filepath)
            if not csv_file.exists():
                raise FileNotFoundError(f"文件不存在: {filepath}")

            transactions_to_import = []

            with open(csv_file, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)

                for line_num, row in enumerate(reader, start=2):
                    result.total += 1

                    try:
                        # 检查交易状态
                        status = row.get("当前状态", "").strip()
                        if status and any(kw in status for kw in self.FAIL_KEYWORDS):
                            result.ignored_count += 1
                            continue

                        # 检查支付方式，只导入零钱交易
                        pay_method = row.get("支付方式", "").strip()
                        if pay_method and pay_method != "零钱":
                            result.ignored_count += 1
                            continue

                        # 获取金额
                        amount_str = row.get("金额(元)", "").strip()
                        if not amount_str:
                            result.ignored_count += 1
                            continue

                        amount = self._parse_amount(amount_str)

                        # 判断收支
                        type_str = row.get("收/支", "").strip()
                        if "支出" in type_str:
                            amount = -abs(amount)

                        # 获取时间和描述
                        date_str = row.get("交易时间", "").strip()
                        transaction_type = row.get("交易类型", "").strip()
                        counterparty = row.get("交易对方", "").strip()
                        product = row.get("商品", "").strip()
                        note = row.get("备注", "").strip()

                        # 构建描述
                        description_parts = []
                        if transaction_type:
                            description_parts.append(transaction_type)
                        if counterparty:
                            description_parts.append(counterparty)
                        if product and product != "/":
                            description_parts.append(product)
                        if note and note != "/":
                            description_parts.append(note)

                        description = " - ".join(description_parts) if description_parts else "微信交易"

                        transaction_id = row.get("交易单号", "").strip()
                        metadata_json = self._build_metadata(
                            "wechat", transaction_id, dict(row)
                        )

                        transactions_to_import.append({
                            "description": description,
                            "amount": amount,
                            "date": date_str,
                            "account_name": "微信",
                            "metadata_json": metadata_json,
                        })

                    except Exception as e:
                        result.failed += 1
                        result.errors.append(f"行 {line_num}: {str(e)}")

            # 倒序导入（从最新到最早）
            if transactions_to_import:
                self._do_backwards_import(transactions_to_import, result, mode)

        except Exception as e:
            result.errors.append(f"读取CSV文件失败: {str(e)}")

        return result

    def _do_backwards_import(
        self, transactions: List[Dict], result: ImportResult, mode: str = "skip"
    ) -> None:
        """
        倒序导入交易（从最新到最早），从当前余额倒推

        Args:
            transactions: 交易数据列表
            result: 导入结果对象
            mode: 重复处理模式 (skip/replace/keep_both)
                - skip: 跳过已存在的交易
                - replace: 替换所有现有交易
                - keep_both: 保留所有交易
        """
        cursor = self.db.conn.cursor()

        account_name = transactions[0]["account_name"]
        account = self._get_or_create_account(account_name)

        current_balance = account.balance

        if mode == "replace":
            # 替换模式：清空该账户的现有交易
            cursor.execute(
                """
                DELETE FROM transaction_tags WHERE transaction_id IN (
                    SELECT id FROM transactions WHERE account_id = ?
                )
                """,
                (account.id,),
            )
            cursor.execute(
                "DELETE FROM transactions WHERE account_id = ?", (account.id,)
            )
            self.db.conn.commit()
        elif mode == "skip":
            # 跳过模式：获取现有交易，后续检查重复
            pass

        # 按时间倒序排序（最新的在前）
        transactions.sort(key=lambda x: x["date"], reverse=True)

        imported_ids = []
        balance_updates = []

        for tx_data in transactions:
            try:
                # 跳过模式：检查是否已存在相同交易
                if mode == "skip":
                    cursor.execute(
                        """
                        SELECT id FROM transactions
                        WHERE description = ? AND amount = ? AND account_id = ?
                        """,
                        (tx_data["description"], abs(tx_data["amount"]), account.id),
                    )
                    if cursor.fetchone():
                        result.skipped += 1
                        continue

                tx = self._insert_transaction_no_recalc(
                    tx_data["description"],
                    tx_data["amount"],
                    tx_data["date"],
                    None,
                    tx_data["account_name"],
                    tx_data["metadata_json"],
                )
                imported_ids.append(tx.id)

                balance_updates.append((current_balance, tx.id))

                if tx.type == "income":
                    current_balance -= tx.amount
                else:
                    current_balance += tx.amount

                result.success += 1
            except Exception as e:
                result.failed += 1
                result.errors.append(f"导入失败: {str(e)}")

        # 批量更新余额
        for balance, tx_id in balance_updates:
            cursor.execute(
                "UPDATE transactions SET running_balance = ? WHERE id = ?",
                (balance, tx_id),
            )

        self.db.conn.commit()

        # 重新加载交易
        self._reload_transactions(imported_ids, result)

    def _reload_transactions(self, tx_ids: List[int], result: ImportResult) -> None:
        """从数据库重新加载交易"""
        from ..models import Transaction

        cursor = self.db.conn.cursor()
        for tx_id in tx_ids:
            cursor.execute(
                """
                SELECT t.*, c.name as category_name, a.name as account_name
                FROM transactions t
                LEFT JOIN categories c ON t.category_id = c.id
                LEFT JOIN accounts a ON t.account_id = a.id
                WHERE t.id = ?
                """,
                (tx_id,),
            )
            row = cursor.fetchone()
            if row:
                tx = Transaction.from_row(row)
                tx.category_name = row["category_name"]
                tx.account_name = row["account_name"]
                result.imported_transactions.append(tx)