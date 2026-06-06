"""
通用 CSV 导入器

处理用户自定义格式的 CSV 文件。

支持格式：
- 标准格式：date, description, amount, category, account, tags
- 自动检测编码
- 支持多种日期格式
- 支持重复处理模式 (skip/replace/keep_both)
"""
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from .base import BaseImporter, ImportResult


class GenericCSVImporter(BaseImporter):
    """通用 CSV 导入器"""
    name = "generic"
    display_name = "通用CSV"

    # 标准表头
    STANDARD_HEADERS = ["date", "description", "amount", "category", "account", "tags"]

    def can_handle(self, filepath: str) -> bool:
        """通用导入器总是返回 True（作为兜底）"""
        return True

    def import_file(self, filepath: str, mode: str = "skip") -> ImportResult:
        """导入通用 CSV 文件"""
        result = ImportResult()

        try:
            csv_file = Path(filepath)
            if not csv_file.exists():
                raise FileNotFoundError(f"文件不存在: {filepath}")

            # 使用编码检测读取
            rows, fieldnames = self._read_csv_with_encoding_detection(filepath)

            if not rows:
                result.warnings.append("CSV 文件为空")
                return result

            # 标准化字段名（转小写，去空格）
            normalized_fieldnames = [f.strip().lower() for f in fieldnames]

            # 检查是否有标准表头
            has_standard_headers = all(
                h in normalized_fieldnames for h in ["date", "description", "amount"]
            )

            transactions_to_import = []

            for line_num, row in enumerate(rows, start=2):
                result.total += 1

                try:
                    if has_standard_headers:
                        # 标准格式
                        date_str = row.get("date", "").strip()
                        description = row.get("description", "").strip()
                        amount_str = row.get("amount", "").strip()
                        category = row.get("category", "").strip() or None
                        account_name = row.get("account", "").strip() or "总账户"
                        tags_str = row.get("tags", "").strip() or ""
                    else:
                        # 非标准格式：尝试按位置解析
                        # 假设前三个字段是 date, description, amount
                        values = list(row.values())
                        if len(values) < 3:
                            result.ignored_count += 1
                            continue
                        date_str = str(values[0]).strip()
                        description = str(values[1]).strip()
                        amount_str = str(values[2]).strip()
                        category = str(values[3]).strip() if len(values) > 3 else None
                        account_name = str(values[4]).strip() if len(values) > 4 else "总账户"
                        tags_str = str(values[5]).strip() if len(values) > 5 else ""

                    if not date_str or not description or not amount_str:
                        result.ignored_count += 1
                        continue

                    amount = self._parse_amount(amount_str)

                    # 推断分类
                    if not category:
                        category = self._infer_category(description, amount)

                    metadata_json = self._build_metadata(
                        "generic", "", dict(row)
                    )

                    transactions_to_import.append({
                        "description": description,
                        "amount": amount,
                        "date": date_str,
                        "category": category,
                        "account_name": account_name,
                        "tags": tags_str,
                        "metadata_json": metadata_json,
                    })

                except Exception as e:
                    result.failed += 1
                    result.errors.append(f"行 {line_num}: {str(e)}")

            # 导入交易
            if transactions_to_import:
                self._do_forward_import(transactions_to_import, result, mode)

        except Exception as e:
            result.errors.append(f"读取CSV文件失败: {str(e)}")

        return result

    def _do_forward_import(
        self, transactions: List[Dict], result: ImportResult, mode: str
    ) -> None:
        """
        正向导入交易（按时间顺序），适用于通用 CSV

        与支付宝/微信不同，通用 CSV 不覆盖现有数据，而是追加
        """
        cursor = self.db.conn.cursor()

        # 按时间正序排序
        transactions.sort(key=lambda x: x["date"])

        imported_ids = []

        for tx_data in transactions:
            try:
                # 检查重复
                if mode == "skip":
                    if self._check_duplicate(tx_data):
                        result.skipped += 1
                        continue
                elif mode == "replace":
                    self._remove_duplicate(tx_data)

                tx = self._insert_transaction_no_recalc(
                    tx_data["description"],
                    tx_data["amount"],
                    tx_data["date"],
                    tx_data.get("category"),
                    tx_data["account_name"],
                    tx_data["metadata_json"],
                )
                imported_ids.append(tx.id)

                # 处理标签
                tags_str = tx_data.get("tags", "")
                if tags_str:
                    self._add_tags_to_transaction(tx.id, tags_str)

                result.success += 1
            except Exception as e:
                result.failed += 1
                result.errors.append(f"导入失败: {str(e)}")

        # 重新计算余额
        if imported_ids:
            account_name = transactions[0]["account_name"]
            account = self._get_or_create_account(account_name)
            self._recalculate_balances_backwards(account.id, imported_ids)

        # 重新加载交易
        self._reload_transactions(imported_ids, result)

    def _check_duplicate(self, tx_data: Dict) -> bool:
        """检查是否存在重复交易"""
        cursor = self.db.conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM transactions
            WHERE date = ? AND description = ? AND amount = ?
            """,
            (
                self._normalize_date(tx_data["date"]),
                tx_data["description"],
                abs(tx_data["amount"]),
            ),
        )
        return cursor.fetchone()[0] > 0

    def _remove_duplicate(self, tx_data: Dict) -> None:
        """删除重复交易"""
        cursor = self.db.conn.cursor()
        cursor.execute(
            """
            DELETE FROM transactions
            WHERE date = ? AND description = ? AND amount = ?
            """,
            (
                self._normalize_date(tx_data["date"]),
                tx_data["description"],
                abs(tx_data["amount"]),
            ),
        )
        self.db.conn.commit()

    def _add_tags_to_transaction(self, tx_id: int, tags_str: str) -> None:
        """为交易添加标签"""
        cursor = self.db.conn.cursor()
        tags = [t.strip().lstrip("#") for t in tags_str.split() if t.strip()]

        for tag_name in tags:
            # 获取或创建标签
            cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
            row = cursor.fetchone()
            if row:
                tag_id = row[0]
            else:
                cursor.execute("INSERT INTO tags (name) VALUES (?)", (tag_name,))
                tag_id = cursor.lastrowid

            # 关联标签
            cursor.execute(
                "INSERT OR IGNORE INTO transaction_tags (transaction_id, tag_id) VALUES (?, ?)",
                (tx_id, tag_id),
            )

        self.db.conn.commit()

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