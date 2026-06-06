import sqlite3
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from .database import Database
from .models import Account, Category, Transaction, Tag, Subscription
from .llm import LLMClient
from .embedding import EmbeddingEngine
from .importers import ImportManager


class AccountingService:
    def __init__(self, db: Database):
        self.db = db
        self.llm = LLMClient()
        self.embedding_engine = EmbeddingEngine(db)

    def get_account_by_name(self, name: str) -> Optional[Account]:
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE name = ?", (name,))
        row = cursor.fetchone()
        return Account.from_row(row) if row else None

    def get_account_by_id(self, id: int) -> Optional[Account]:
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE id = ?", (id,))
        row = cursor.fetchone()
        return Account.from_row(row) if row else None

    def get_all_accounts(self) -> List[Account]:
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM accounts ORDER BY id")
        return [Account.from_row(row) for row in cursor.fetchall()]

    def get_category_by_name(self, name: str) -> Optional[Category]:
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM categories WHERE name = ?", (name,))
        row = cursor.fetchone()
        return Category.from_row(row) if row else None

    def infer_category(self, description: str, amount: float = 0.0) -> Optional[Category]:
        # 先尝试用 LLM
        trans_type = "income" if amount > 0 else "expense"
        llm_category = self.llm.infer_category(description, abs(amount), trans_type)
        if llm_category:
            category = self.get_category_by_name(llm_category)
            if category:
                return category

        # 后备关键词匹配
        keywords = {
            "早餐": "早餐", "午餐": "午餐", "晚餐": "晚餐",
            "地铁": "地铁", "公交": "公交", "打车": "打车",
            "高铁": "高铁", "飞机": "飞机",
            "工资": "工资", "奖金": "奖金",
            "会员": "会员订阅"
        }
        for keyword, category_name in keywords.items():
            if keyword in description:
                return self.get_category_by_name(category_name)
        return None

    def get_tags_by_transaction_id(self, transaction_id: int) -> List[str]:
        cursor = self.db.conn.cursor()
        cursor.execute('''
            SELECT t.name FROM tags t
            JOIN transaction_tags tt ON t.id = tt.tag_id
            WHERE tt.transaction_id = ?
        ''', (transaction_id,))
        return [row[0] for row in cursor.fetchall()]

    def _normalize_date(self, date: Optional[str]) -> str:
        """标准化日期格式为 YYYY-MM-DD"""
        if not date:
            return datetime.now().strftime("%Y-%m-%d")

        date_str = date.strip()

        # 尝试多种日期格式
        formats = [
            "%Y-%m-%d",              # 2024-01-15
            "%Y/%m/%d",              # 2024/01/15
            "%Y-%m-%d %H:%M:%S",     # 2024-01-15 10:30:00
            "%Y/%m/%d %H:%M:%S",     # 2024/01/15 10:30:00
            "%Y-%m-%d %H:%M",        # 2024-01-15 10:30
            "%Y/%m/%d %H:%M",        # 2024/01/15 10:30
            "%m/%d/%Y",              # 01/15/2024
            "%d/%m/%Y",              # 15/01/2024
            "%Y年%m月%d日",           # 2024年01月15日
            "%Y年%m月%d日 %H:%M:%S",  # 2024年01月15日 10:30:00
            "%m-%d",                 # 01-15 (使用当前年份)
            "%m/%d",                 # 01/15 (使用当前年份)
            "%m月%d日",               # 01月15日 (使用当前年份)
            "%Y.%m.%d",              # 2024.01.15
            "%Y.%m.%d %H:%M:%S",     # 2024.01.15 10:30:00
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        # 如果所有格式都失败，返回当前日期
        return datetime.now().strftime("%Y-%m-%d")

    def add_transaction(self, description: str, amount: float, date: Optional[str] = None,
                        category_name: Optional[str] = None, account_name: str = "总账户",
                        tags: Optional[List[str]] = None,
                        metadata: Optional[Dict[str, Any]] = None) -> Transaction:
        """添加新交易（默认添加到最新）"""
        date = self._normalize_date(date)

        account = self.get_account_by_name(account_name)
        if not account:
            raise ValueError(f"账户不存在: {account_name}")

        category = None
        if category_name:
            category = self.get_category_by_name(category_name)
        if not category:
            category = self.infer_category(description, amount)

        trans_type = "income" if amount > 0 else "expense"

        # 计算新余额：账户当前余额 + amount（amount已带符号）
        new_balance = account.balance + amount

        cursor = self.db.conn.cursor()
        now = datetime.now().isoformat()

        metadata_json = None
        if metadata:
            metadata_json = json.dumps(metadata, ensure_ascii=False)

        cursor.execute('''
            INSERT INTO transactions (date, type, amount, running_balance, category_id,
                                     account_id, description, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (date, trans_type, abs(amount), new_balance, category.id if category else None,
              account.id, description, metadata_json, now, now))

        transaction_id = cursor.lastrowid

        saved_tags = []
        if tags:
            for tag_name in tags:
                tag_name = tag_name.lstrip("#")
                cursor.execute(
                    "SELECT id FROM tags WHERE name = ?", (tag_name,))
                tag_row = cursor.fetchone()
                if tag_row:
                    tag_id = tag_row[0]
                else:
                    cursor.execute(
                        "INSERT INTO tags (name) VALUES (?)", (tag_name,))
                    tag_id = cursor.lastrowid
                cursor.execute("INSERT INTO transaction_tags (transaction_id, tag_id) VALUES (?, ?)",
                               (transaction_id, tag_id))
                saved_tags.append(tag_name)

        # 更新账户余额
        cursor.execute('''
            UPDATE accounts SET balance = ?, updated_at = ? WHERE id = ?
        ''', (new_balance, now, account.id))

        self.db.conn.commit()

        cursor.execute("SELECT * FROM transactions WHERE id = ?",
                       (transaction_id,))
        tx_row = cursor.fetchone()
        tx = Transaction.from_row(tx_row)
        tx.account_name = account.name
        tx.category_name = category.name if category else None
        tx.tags = saved_tags

        # 自动计算并保存 embedding
        if self.embedding_engine.is_available():
            self.embedding_engine.compute_and_store_embedding(tx)

        return tx

    def insert_transaction(self, date: str, description: str, amount: float,
                           category_name: Optional[str] = None,
                           account_name: str = "总账户",
                           tags: Optional[List[str]] = None) -> Transaction:
        """插入历史记录（自动重算后续余额）"""
        date = self._normalize_date(date)

        account = self.get_account_by_name(account_name)
        if not account:
            raise ValueError(f"账户不存在: {account_name}")

        category = None
        if category_name:
            category = self.get_category_by_name(category_name)
        if not category:
            category = self.infer_category(description, amount)

        trans_type = "income" if amount > 0 else "expense"

        cursor = self.db.conn.cursor()
        now = datetime.now().isoformat()

        # 先找到插入点之前的最后一笔交易，获取其余额
        cursor.execute('''
            SELECT running_balance FROM transactions
            WHERE account_id = ? AND date <= ?
            ORDER BY date DESC, id DESC LIMIT 1
        ''', (account.id, date))
        prev_row = cursor.fetchone()

        if prev_row:
            # 找到之前的交易，从它的余额开始计算
            start_balance = prev_row[0]
        else:
            # 没有更早的交易，从0开始
            start_balance = 0.0

        # 计算这笔交易的余额
        if trans_type == "income":
            new_balance = start_balance + abs(amount)
        else:
            new_balance = start_balance - abs(amount)

        # 插入这笔交易
        metadata_json = None
        cursor.execute('''
            INSERT INTO transactions (date, type, amount, running_balance, category_id,
                                     account_id, description, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (date, trans_type, abs(amount), new_balance, category.id if category else None,
              account.id, description, metadata_json, now, now))

        transaction_id = cursor.lastrowid

        saved_tags = []
        if tags:
            for tag_name in tags:
                tag_name = tag_name.lstrip("#")
                cursor.execute(
                    "SELECT id FROM tags WHERE name = ?", (tag_name,))
                tag_row = cursor.fetchone()
                if tag_row:
                    tag_id = tag_row[0]
                else:
                    cursor.execute(
                        "INSERT INTO tags (name) VALUES (?)", (tag_name,))
                    tag_id = cursor.lastrowid
                cursor.execute("INSERT INTO transaction_tags (transaction_id, tag_id) VALUES (?, ?)",
                               (transaction_id, tag_id))
                saved_tags.append(tag_name)

        # 现在重新计算插入日期之后的所有交易余额
        cursor.execute('''
            SELECT id, date, type, amount FROM transactions
            WHERE account_id = ? AND date >= ? AND id != ?
            ORDER BY date ASC, id ASC
        ''', (account.id, date, transaction_id))

        current_balance = new_balance
        for tx_id, tx_date, tx_type, tx_amount in cursor.fetchall():
            if tx_type == "income":
                current_balance += tx_amount
            else:
                current_balance -= tx_amount

            cursor.execute('''
                UPDATE transactions SET running_balance = ? WHERE id = ?
            ''', (current_balance, tx_id))

        # 更新账户余额为最新余额
        cursor.execute('''
            UPDATE accounts SET balance = ?, updated_at = ? WHERE id = ?
        ''', (current_balance, now, account.id))

        self.db.conn.commit()

        cursor.execute("SELECT * FROM transactions WHERE id = ?",
                       (transaction_id,))
        tx_row = cursor.fetchone()
        tx = Transaction.from_row(tx_row)
        tx.account_name = account.name
        tx.category_name = category.name if category else None
        tx.tags = saved_tags
        return tx


    def list_transactions(self, from_date: Optional[str] = None, to_date: Optional[str] = None,
                          category_name: Optional[str] = None, account_name: Optional[str] = None,
                          tag_name: Optional[str] = None, limit: Optional[int] = None) -> List[Transaction]:
        cursor = self.db.conn.cursor()

        query = '''
            SELECT t.*, c.name as category_name, a.name as account_name
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            LEFT JOIN accounts a ON t.account_id = a.id
        '''
        conditions = []
        params = []

        if account_name:
            account = self.get_account_by_name(account_name)
            if account:
                conditions.append("t.account_id = ?")
                params.append(account.id)

        if from_date:
            conditions.append("t.date >= ?")
            params.append(from_date)

        if to_date:
            conditions.append("t.date <= ?")
            params.append(to_date)

        if category_name:
            category = self.get_category_by_name(category_name)
            if category:
                conditions.append("t.category_id = ?")
                params.append(category.id)

        if tag_name:
            tag_name = tag_name.lstrip("#")
            query += " JOIN transaction_tags tt ON t.id = tt.transaction_id"
            query += " JOIN tags tg ON tt.tag_id = tg.id"
            conditions.append("tg.name = ?")
            params.append(tag_name)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY t.date DESC, t.id DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor.execute(query, params)

        transactions = []
        for row in cursor.fetchall():
            tx = Transaction.from_row(row)
            tx.category_name = row["category_name"]
            tx.account_name = row["account_name"]
            tx.tags = self.get_tags_by_transaction_id(tx.id)
            transactions.append(tx)

        return transactions

    def get_balance(self, account_name: Optional[str] = None) -> List[Account]:
        if account_name:
            account = self.get_account_by_name(account_name)
            return [account] if account else []
        return self.get_all_accounts()

    def get_stats(self, from_date: Optional[str] = None, to_date: Optional[str] = None,
                  by_category: bool = False) -> Dict[str, Any]:
        cursor = self.db.conn.cursor()

        if not from_date:
            from_date = (datetime.now() - timedelta(days=30)
                         ).strftime("%Y-%m-%d")
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")

        stats = {
            "from_date": from_date,
            "to_date": to_date,
            "total_income": 0,
            "total_expense": 0,
            "net": 0,
            "by_category": {}
        }

        cursor.execute('''
            SELECT type, SUM(amount) as total
            FROM transactions
            WHERE date >= ? AND date <= ?
            GROUP BY type
        ''', (from_date, to_date))

        for row in cursor.fetchall():
            if row["type"] == "income":
                stats["total_income"] = row["total"]
            else:
                stats["total_expense"] = row["total"]

        stats["net"] = stats["total_income"] - stats["total_expense"]

        if by_category:
            cursor.execute('''
                SELECT c.name, t.type, SUM(t.amount) as total
                FROM transactions t
                LEFT JOIN categories c ON t.category_id = c.id
                WHERE t.date >= ? AND t.date <= ?
                GROUP BY c.name, t.type
                ORDER BY total DESC
            ''', (from_date, to_date))

            for row in cursor.fetchall():
                cat_name = row["name"] or "未分类"
                if cat_name not in stats["by_category"]:
                    stats["by_category"][cat_name] = {
                        "income": 0, "expense": 0}
                if row["type"] == "income":
                    stats["by_category"][cat_name]["income"] = row["total"]
                else:
                    stats["by_category"][cat_name]["expense"] = row["total"]

        return stats

    def add_tag(self, name: str) -> Tag:
        cursor = self.db.conn.cursor()
        name = name.lstrip("#")
        cursor.execute("INSERT INTO tags (name) VALUES (?)", (name,))
        self.db.conn.commit()
        cursor.execute("SELECT * FROM tags WHERE id = ?", (cursor.lastrowid,))
        return Tag.from_row(cursor.fetchone())

    def list_tags(self) -> List[Tag]:
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM tags")
        return [Tag.from_row(row) for row in cursor.fetchall()]

    def delete_tag(self, tag_id: int):
        cursor = self.db.conn.cursor()
        cursor.execute(
            "DELETE FROM transaction_tags WHERE tag_id = ?", (tag_id,))
        cursor.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        self.db.conn.commit()

    def list_subscriptions(self) -> List[Subscription]:
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM subscriptions")
        return [Subscription.from_row(row) for row in cursor.fetchall()]

    def add_subscription(self, name: str, amount: float, cycle: str, start_date: str,
                         platform: Optional[str] = None, end_date: Optional[str] = None,
                         auto_renew: bool = False, category_name: Optional[str] = None,
                         account_name: str = "总账户") -> Subscription:
        account = self.get_account_by_name(account_name)
        if not account:
            raise ValueError(f"账户不存在: {account_name}")

        category = None
        if category_name:
            category = self.get_category_by_name(category_name)

        cursor = self.db.conn.cursor()
        now = datetime.now().isoformat()

        cursor.execute('''
            INSERT INTO subscriptions (name, platform, amount, currency, cycle, start_date,
                                      end_date, auto_renew, category_id, account_id, status,
                                      created_at, updated_at)
            VALUES (?, ?, ?, 'CNY', ?, ?, ?, ?, ?, ?, 'active', ?, ?)
        ''', (name, platform, amount, cycle, start_date, end_date, int(auto_renew),
              category.id if category else None, account.id, now, now))

        self.db.conn.commit()

        cursor.execute("SELECT * FROM subscriptions WHERE id = ?",
                       (cursor.lastrowid,))
        return Subscription.from_row(cursor.fetchone())

    def cancel_subscription(self, subscription_id: int):
        cursor = self.db.conn.cursor()
        cursor.execute('''
            UPDATE subscriptions SET status = 'cancelled', updated_at = ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), subscription_id))
        self.db.conn.commit()

    def check_duplicate_transaction(self, date: str, description: str, amount: float, account_id: int) -> Optional[Transaction]:
        cursor = self.db.conn.cursor()
        cursor.execute('''
            SELECT t.*, c.name as category_name, a.name as account_name
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            LEFT JOIN accounts a ON t.account_id = a.id
            WHERE t.date = ? AND t.description = ? AND t.account_id = ?
        ''', (date, description, account_id))

        row = cursor.fetchone()
        if not row:
            amount_to_check = abs(amount)
            cursor.execute('''
                SELECT t.*, c.name as category_name, a.name as account_name
                FROM transactions t
                LEFT JOIN categories c ON t.category_id = c.id
                LEFT JOIN accounts a ON t.account_id = a.id
                WHERE t.date = ? AND t.amount = ? AND t.account_id = ?
            ''', (date, amount_to_check, account_id))
            row = cursor.fetchone()

        if row:
            tx = Transaction.from_row(row)
            tx.category_name = row["category_name"]
            tx.account_name = row["account_name"]
            tx.tags = self.get_tags_by_transaction_id(tx.id)
            return tx
        return None

    def set_account_balance(self, account_name: str, balance: float, date: Optional[str] = None) -> Transaction:
        account = self.get_account_by_name(account_name)
        if not account:
            raise ValueError(f"账户不存在: {account_name}")

        cursor = self.db.conn.cursor()

        # 获取该账户的所有交易，按时间顺序
        cursor.execute('''
            SELECT t.id, t.date, t.type, t.amount
            FROM transactions t
            WHERE t.account_id = ?
            ORDER BY t.date ASC, t.id ASC
        ''', (account.id,))
        transactions = cursor.fetchall()

        if transactions:
            # 如果有交易记录，从目标余额从后往前倒推
            current_balance = balance

            # 倒序遍历交易
            for tx in reversed(transactions):
                tx_id, tx_date, tx_type, tx_amount = tx

                # 先更新这条交易的余额
                cursor.execute('''
                    UPDATE transactions SET running_balance = ? WHERE id = ?
                ''', (current_balance, tx_id))

                # 倒推前一条交易的余额
                if tx_type == 'income':
                    current_balance -= tx_amount
                else:
                    current_balance += tx_amount

            # 使用最后一条交易作为结果
            cursor.execute('''
                SELECT t.*, c.name as category_name, a.name as account_name
                FROM transactions t
                LEFT JOIN categories c ON t.category_id = c.id
                LEFT JOIN accounts a ON t.account_id = a.id
                WHERE t.id = ?
            ''', (transactions[-1][0],))
            row = cursor.fetchone()
            tx = Transaction.from_row(row)
            tx.category_name = row["category_name"]
            tx.account_name = row["account_name"]
            tx.tags = self.get_tags_by_transaction_id(tx.id)
        else:
            # 如果没有交易记录，添加初始余额
            if not date:
                date = datetime.now().strftime("%Y-%m-%d")
            tx = self._add_transaction_no_recalculate(
                "初始余额", balance, date, None, account_name, None
            )
            tx.running_balance = balance

            # 更新这条交易的 running_balance
            cursor.execute('''
                UPDATE transactions SET running_balance = ? WHERE id = ?
            ''', (balance, tx.id))

        # 更新账户表中的余额
        cursor.execute('''
            UPDATE accounts SET balance = ? WHERE id = ?
        ''', (balance, account.id))

        self.db.conn.commit()

        return tx

    def set_multiple_balances(self, balances: Dict[str, float], date: Optional[str] = None,
                              create_initial_tx: bool = False) -> Dict[str, Any]:
        """
        设置多个账户余额
        
        Args:
            balances: {账户名: 余额}
            date: 日期（仅用于创建初始交易时）
            create_initial_tx: 是否创建初始交易记录（默认 False）
        """
        results = {
            "accounts_updated": 0,
            "transactions_created": 0,
            "balances_recalculated": False
        }
        
        cursor = self.db.conn.cursor()
        
        for account_name, balance in balances.items():
            account = self.get_account_by_name(account_name)
            if not account:
                continue
            
            results["accounts_updated"] += 1
            
            if create_initial_tx:
                # 创建初始交易
                tx = self.set_account_balance(account_name, balance, date)
                results["transactions_created"] += 1
            else:
                # 只更新账户表中的余额，不创建交易
                cursor.execute('''
                    UPDATE accounts SET balance = ?, updated_at = ? WHERE id = ?
                ''', (balance, datetime.now().isoformat(), account.id))
        
        # 更新总账户余额
        cursor.execute('''
            SELECT SUM(balance) FROM accounts WHERE type != 'summary'
        ''')
        total = cursor.fetchone()[0] or 0.0
        cursor.execute('''
            UPDATE accounts SET balance = ?, updated_at = ? WHERE type = 'summary'
        ''', (total, datetime.now().isoformat()))
        
        self.db.conn.commit()
        
        # 自动重新倒推计算所有交易余额
        recalc_result = self.recalculate_all_balances_backwards()
        results["balances_recalculated"] = True
        results["recalculate_info"] = recalc_result
        
        return results

    def recalculate_all_balances_backwards(self) -> Dict[str, Any]:
        """
        从当前余额倒推计算所有交易的 running_balance
        
        对每个账户：
        1. 获取当前余额
        2. 按时间倒序遍历所有交易
        3. 从当前余额开始，倒推每笔交易后的余额
        """
        results = {
            "accounts_processed": 0,
            "transactions_updated": 0,
            "errors": []
        }
        
        try:
            cursor = self.db.conn.cursor()
            
            # 获取所有账户（除了总账户，因为它是汇总的）
            cursor.execute('''
                SELECT id, name, balance FROM accounts WHERE type != 'summary'
            ''')
            accounts = cursor.fetchall()
            
            for account_row in accounts:
                account_id = account_row["id"]
                account_name = account_row["name"]
                current_balance = account_row["balance"]
                
                results["accounts_processed"] += 1
                
                # 获取该账户的所有交易，按时间倒序排列（最新的在前）
                cursor.execute('''
                    SELECT id, date, type, amount
                    FROM transactions
                    WHERE account_id = ?
                    ORDER BY date DESC, id DESC
                ''', (account_id,))
                transactions = cursor.fetchall()
                
                if not transactions:
                    continue
                
                # 从当前余额倒推
                balance_updates = []
                for tx in transactions:
                    # 保存当前余额到这笔交易
                    balance_updates.append((current_balance, tx["id"]))
                    results["transactions_updated"] += 1
                    
                    # 倒推上一笔交易的余额
                    if tx["type"] == "income":
                        # 收入：前一笔余额 = 当前余额 - 这笔收入
                        current_balance -= tx["amount"]
                    else:
                        # 支出：前一笔余额 = 当前余额 + 这笔支出
                        current_balance += tx["amount"]
                
                # 批量更新余额
                for balance, tx_id in balance_updates:
                    cursor.execute('''
                        UPDATE transactions SET running_balance = ? WHERE id = ?
                    ''', (balance, tx_id))
            
            # 更新总账户余额（汇总其他账户）
            cursor.execute('''
                SELECT SUM(balance) FROM accounts WHERE type != 'summary'
            ''')
            total_balance = cursor.fetchone()[0] or 0.0
            cursor.execute('''
                UPDATE accounts SET balance = ?, updated_at = ? WHERE type = 'summary'
            ''', (total_balance, datetime.now().isoformat()))
            
            self.db.conn.commit()
            self.db.create_backup()
            
        except Exception as e:
            results["errors"].append(str(e))
        
        return results

    def import_csv(self, csv_path: str, source: Optional[str] = None,
                  account_name: Optional[str] = None,
                  account_balance: Optional[float] = None,
                  mode: str = "skip") -> Dict[str, Any]:
        """统一的CSV导入方法，使用ImportManager自动检测或指定来源"""
        manager = ImportManager(self.db)
        return manager.import_csv(csv_path, source=source,
                                  account_name=account_name,
                                  account_balance=account_balance,
                                  mode=mode)

    def detect_csv_source(self, csv_path: str) -> Optional[str]:
        """检测CSV文件来源"""
        manager = ImportManager(self.db)
        return manager.detect_source(csv_path)

