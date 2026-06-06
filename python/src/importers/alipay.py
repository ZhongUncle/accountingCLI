"""
支付宝 CSV 导入器

处理支付宝导出的交易记录 CSV 文件。

支付宝 CSV 格式特点：
- 前 4 行是元数据（账号信息等）
- 第 5 行是表头
- 标准表头：交易号, 商家订单号, 交易创建时间, 付款时间, 最近修改时间,
  交易来源地, 类型, 交易对方, 商品名称, 金额（元）, 收/支, 交易状态,
  服务费（元）, 成功退款（元）, 备注, 资金状态
"""
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from .base import BaseImporter, ImportResult


class AlipayImporter(BaseImporter):
    """支付宝 CSV 导入器"""
    name = "alipay"
    display_name = "支付宝"

    # 支付宝标准表头
    ALIPAY_HEADERS = [
        "交易号", "商家订单号", "交易创建时间", "付款时间", "最近修改时间",
        "交易来源地", "类型", "交易对方", "商品名称", "金额（元）",
        "收/支", "交易状态", "服务费（元）", "成功退款（元）", "备注", "资金状态",
    ]

    def can_handle(self, filepath: str) -> bool:
        """检测是否为支付宝 CSV 文件"""
        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                first_line = f.readline().strip()
                # 支付宝 CSV 第一行通常是 "支付宝交易记录明细查询"
                if "支付宝" in first_line:
                    return True

                # 或者检查表头是否匹配
                f.seek(0)
                # 跳过可能的元数据行
                for _ in range(5):
                    line = f.readline().strip()
                    if "交易号" in line and "商家订单号" in line:
                        return True

            return False
        except Exception:
            return False

    def import_file(self, filepath: str, mode: str = "skip") -> ImportResult:
        """导入支付宝 CSV 文件"""
        result = ImportResult()

        try:
            csv_file = Path(filepath)
            if not csv_file.exists():
                raise FileNotFoundError(f"文件不存在: {filepath}")

            # 收集所有需要导入的交易
            transactions_to_import = []

            with open(csv_file, "r", encoding="utf-8-sig") as f:
                first_line = f.readline().strip()
                f.seek(0)

                if first_line.startswith("支付宝交易记录明细查询") or first_line.startswith("账号:"):
                    # 有元数据头，跳过前 4 行
                    for _ in range(4):
                        f.readline()
                    reader = csv.DictReader(f)
                else:
                    # 没有元数据头，直接读取
                    reader = csv.DictReader(f, fieldnames=self.ALIPAY_HEADERS)

                for line_num, row in enumerate(reader, start=2):
                    result.total += 1

                    try:
                        # 检查交易状态
                        status = row.get("交易状态", "")
                        if status and "成功" not in status:
                            result.ignored_count += 1
                            continue

                        # 获取金额
                        amount_str = row.get("金额（元）", "").strip()
                        if not amount_str:
                            result.ignored_count += 1
                            continue

                        amount = self._parse_amount(amount_str)

                        # 判断收支：优先看"资金状态"字段
                        fund_status = row.get("资金状态", "").strip()
                        if "已支出" in fund_status:
                            amount = -abs(amount)
                        elif "已收入" in fund_status:
                            amount = abs(amount)
                        else:
                            # 不是明确的收入或支出，跳过
                            result.ignored_count += 1
                            continue

                        # 获取时间和描述
                        date_str = row.get("交易创建时间", "").strip() or row.get("付款时间", "").strip()
                        description = (
                            row.get("商品名称", "").strip()
                            or row.get("备注", "").strip()
                            or "支付宝交易"
                        )

                        transaction_id = row.get("交易号", "").strip()
                        metadata_json = self._build_metadata(
                            "alipay", transaction_id, dict(row)
                        )

                        transactions_to_import.append({
                            "description": description,
                            "amount": amount,
                            "date": date_str,
                            "account_name": "支付宝",
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
                    None,  # category 由 AccountingService 层处理
                    tx_data["account_name"],
                    tx_data["metadata_json"],
                )
                imported_ids.append(tx.id)

                # 保存余额更新
                balance_updates.append((current_balance, tx.id))

                # 倒推：根据交易类型调整余额
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

        # 重新加载交易以获取正确的余额
        self._reload_transactions(imported_ids, result)

    def _reload_transactions(self, tx_ids: List[int], result: ImportResult) -> None:
        """从数据库重新加载交易，填充到 result 中"""
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