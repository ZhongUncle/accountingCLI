import sqlite3
import os
import shutil
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from .models import Transaction


class Database:
    def __init__(self, db_path=None):
        if db_path is None:
            self.db_path = self._get_default_db_path()
        else:
            self.db_path = db_path
        
        self._ensure_data_dir()
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()
        self._init_default_data()
        self.create_dedup_index()

    def _get_default_db_path(self):
        # 使用用户主目录下的 .accounting 文件夹
        home_dir = Path.home()
        data_dir = home_dir / ".accounting" / "data"
        return str(data_dir / "accounting.db")

    def _ensure_data_dir(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _init_tables(self):
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL,
                balance REAL NOT NULL DEFAULT 0,
                currency TEXT NOT NULL DEFAULT 'CNY',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                parent_id INTEGER,
                sort_order INTEGER DEFAULT 0,
                FOREIGN KEY (parent_id) REFERENCES categories(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                type TEXT NOT NULL,
                amount REAL NOT NULL,
                running_balance REAL NOT NULL,
                category_id INTEGER,
                account_id INTEGER NOT NULL,
                description TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (category_id) REFERENCES categories(id),
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                color TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transaction_tags (
                transaction_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (transaction_id, tag_id),
                FOREIGN KEY (transaction_id) REFERENCES transactions(id),
                FOREIGN KEY (tag_id) REFERENCES tags(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                platform TEXT,
                amount REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'CNY',
                cycle TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT,
                auto_renew INTEGER NOT NULL DEFAULT 0,
                category_id INTEGER,
                account_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (category_id) REFERENCES categories(id),
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transaction_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id INTEGER NOT NULL,
                embedding TEXT NOT NULL,
                model TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (transaction_id) REFERENCES transactions(id),
                UNIQUE(transaction_id, model)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            )
        ''')
        
        self.conn.commit()
        self._migrate_schema()

    def _migrate_schema(self):
        import json
        cursor = self.conn.cursor()
        
        # 获取当前版本
        cursor.execute("SELECT version FROM schema_version")
        row = cursor.fetchone()
        current_version = row[0] if row else 0
        
        if current_version < 1:
            # 版本 1: 添加 metadata 字段到 transactions
            try:
                cursor.execute("ALTER TABLE transactions ADD COLUMN metadata TEXT")
            except sqlite3.OperationalError:
                # 字段已存在
                pass
            
            # 更新版本
            if current_version == 0:
                cursor.execute("INSERT INTO schema_version (version) VALUES (1)")
            else:
                cursor.execute("UPDATE schema_version SET version = 1")
        
        if current_version < 2:
            # 版本 2: 添加 transaction_embeddings 表
            try:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS transaction_embeddings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        transaction_id INTEGER NOT NULL,
                        embedding TEXT NOT NULL,
                        model TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (transaction_id) REFERENCES transactions(id),
                        UNIQUE(transaction_id, model)
                    )
                ''')
            except sqlite3.OperationalError:
                # 表已存在
                pass
            
            # 更新版本
            cursor.execute("UPDATE schema_version SET version = 2")
        
        self.conn.commit()

    def _init_default_data(self):
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM accounts")
        if cursor.fetchone()[0] == 0:
            now = datetime.now().isoformat()
            accounts = [
                ("总账户", "summary"),
                ("银行卡", "bank"),
                ("支付宝", "alipay"),
                ("微信", "wechat")
            ]
            for name, type_ in accounts:
                cursor.execute(
                    "INSERT INTO accounts (name, type, balance, created_at, updated_at) VALUES (?, ?, 0, ?, ?)",
                    (name, type_, now, now)
                )
        
        cursor.execute("SELECT COUNT(*) FROM categories")
        if cursor.fetchone()[0] == 0:
            self._init_default_categories()
        
        self.conn.commit()

    def _init_default_categories(self):
        cursor = self.conn.cursor()
        
        # 新分类系统 - 所有都是顶级分类
        expense_categories = [
            ("餐饮", "expense", 1),
            ("地铁", "expense", 2),
            ("打车", "expense", 3),
            ("公交", "expense", 4),
            ("加油", "expense", 5),
            ("高铁", "expense", 6),
            ("飞机", "expense", 7),
            ("停车费", "expense", 8),
            ("共享单车", "expense", 9),
            ("日用品", "expense", 10),
            ("服装", "expense", 11),
            ("电子产品", "expense", 12),
            ("杂项", "expense", 13),
            ("家居", "expense", 14),
            ("电影", "expense", 15),
            ("游戏", "expense", 16),
            ("聚会", "expense", 17),
            ("会员订阅", "expense", 18),
            ("旅游", "expense", 19),
            ("房租", "expense", 20),
            ("水电", "expense", 21),
            ("物业", "expense", 22),
            ("燃气", "expense", 23),
            ("网费", "expense", 24),
            ("话费", "expense", 25),
            ("流量套餐", "expense", 26),
            ("药品", "expense", 27),
            ("体检", "expense", 28),
            ("挂号", "expense", 29),
            ("书籍", "expense", 30),
            ("课程", "expense", 31),
            ("AI会员", "expense", 32),
            ("学习资料", "expense", 33),
            ("红包", "expense", 34),
            ("转账", "expense", 35),
            ("捐赠", "expense", 36)
        ]
        
        income_categories = [
            ("工资", "income", 1),
            ("奖金", "income", 2),
            ("投资收益", "income", 3),
            ("兼职", "income", 4),
            ("红包", "income", 5),
            ("退款", "income", 6),
            ("其他", "income", 7)
        ]
        
        for name, type_, order in expense_categories:
            cursor.execute(
                "INSERT INTO categories (name, type, sort_order) VALUES (?, ?, ?)",
                (name, type_, order)
            )
        
        for name, type_, order in income_categories:
            cursor.execute(
                "INSERT INTO categories (name, type, sort_order) VALUES (?, ?, ?)",
                (name, type_, order)
            )

    def create_backup(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"accounting_{timestamp}.db"

        home_dir = Path.home()
        backup_paths = [
            home_dir / ".accounting" / "backups" / "primary",
            home_dir / ".accounting" / "backups" / "secondary"
        ]

        for backup_dir in backup_paths:
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.db_path, backup_dir / filename)

        self._cleanup_old_backups(backup_paths)
        return str(backup_paths[0] / filename)

    def _cleanup_old_backups(self, backup_paths):
        for backup_dir in backup_paths:
            if not backup_dir.exists():
                continue
            backups = sorted(backup_dir.glob("accounting_*.db"), reverse=True)
            for old_backup in backups[7:]:
                old_backup.unlink()

    def export_to_json(self, output_path):
        import json
        cursor = self.conn.cursor()
        
        cursor.execute('''
            SELECT t.*, c.name as category_name, a.name as account_name
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            LEFT JOIN accounts a ON t.account_id = a.id
            ORDER BY t.date DESC, t.id DESC
        ''')
        
        transactions = []
        for row in cursor.fetchall():
            tx = dict(row)
            # 获取标签
            cursor.execute('''
                SELECT tg.name
                FROM tags tg
                JOIN transaction_tags tt ON tg.id = tt.tag_id
                WHERE tt.transaction_id = ?
            ''', (tx['id'],))
            tx['tags'] = [r[0] for r in cursor.fetchall()]
            transactions.append(tx)
        
        data = {
            'exported_at': datetime.now().isoformat(),
            'transaction_count': len(transactions),
            'transactions': transactions
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return len(transactions)
    
    def export_to_csv(self, output_path):
        import csv
        cursor = self.conn.cursor()
        
        cursor.execute('''
            SELECT t.id, t.date, t.type, t.amount, t.running_balance,
                   t.description, c.name as category_name, a.name as account_name
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            LEFT JOIN accounts a ON t.account_id = a.id
            ORDER BY t.date DESC, t.id DESC
        ''')
        
        rows = cursor.fetchall()
        
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'date', 'type', 'amount', 'running_balance', 
                           'description', 'category', 'account'])
            for row in rows:
                amount = row['amount']
                if row['type'] == 'expense':
                    amount = -amount
                writer.writerow([
                    row['id'], row['date'], row['type'], amount,
                    row['running_balance'], row['description'],
                    row['category_name'] or '', row['account_name'] or ''
                ])
        
        return len(rows)
    
    def list_backups(self):
        home_dir = Path.home()
        backup_paths = [
            home_dir / ".accounting" / "backups" / "primary",
            home_dir / ".accounting" / "backups" / "secondary"
        ]
        
        backups = []
        for backup_dir in backup_paths:
            if backup_dir.exists():
                for backup_file in backup_dir.glob("accounting_*.db"):
                    stat = backup_file.stat()
                    backups.append({
                        'path': str(backup_file),
                        'filename': backup_file.name,
                        'date': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        'size': f"{stat.st_size / 1024:.1f}KB"
                    })
        
        return sorted(backups, key=lambda x: x['date'], reverse=True)
    
    def restore_from_backup(self, backup_path):
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"备份文件不存在: {backup_path}")
        
        # 先创建一个当前数据库的备份
        self.create_backup()
        
        # 关闭当前连接
        self.conn.close()
        
        # 复制备份文件
        shutil.copy2(backup_path, self.db_path)
        
        # 重新连接
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
    
    def find_transaction_by_metadata(self, source: str, transaction_id: str) -> Optional[Transaction]:
        """通过 metadata 中的 source 和 transaction_id 查找交易"""
        cursor = self.conn.cursor()
        # 修复 LIKE 模式：使用 % 通配符匹配 JSON 中的 source 字段
        cursor.execute('''
            SELECT t.*, c.name as category_name, a.name as account_name
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            LEFT JOIN accounts a ON t.account_id = a.id
            WHERE t.metadata LIKE ?
        ''', (f'%"source": "{source}"%',))
        
        rows = cursor.fetchall()
        for row in rows:
            try:
                if row['metadata']:
                    metadata = json.loads(row['metadata'])
                    if metadata.get('transaction_id') == transaction_id:
                        from .models import Transaction
                        tx = Transaction.from_row(row)
                        tx.category_name = row["category_name"]
                        tx.account_name = row["account_name"]
                        return tx
            except (json.JSONDecodeError, KeyError):
                pass
        
        return None

    def safe_bulk_insert(self, transactions: list) -> int:
        """
        安全批量插入交易（使用事务）

        Args:
            transactions: 交易数据列表，每个元素为 (date, type, amount, running_balance,
                         category_id, account_id, description, metadata, created_at, updated_at)

        Returns:
            成功插入的数量
        """
        cursor = self.conn.cursor()
        count = 0
        try:
            cursor.execute("BEGIN TRANSACTION")
            cursor.executemany('''
                INSERT INTO transactions (date, type, amount, running_balance, category_id,
                                         account_id, description, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', transactions)
            count = cursor.rowcount
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return count

    def upsert_transaction(self, date: str, trans_type: str, amount: float,
                           running_balance: float, category_id: int, account_id: int,
                           description: str, metadata: str = None) -> int:
        """
        插入或更新交易（基于 date + description + amount 去重）

        如果存在相同 date/description/amount 的交易则更新，否则插入

        Returns:
            交易 ID
        """
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()

        # 查找是否存在
        cursor.execute('''
            SELECT id FROM transactions
            WHERE date = ? AND description = ? AND amount = ?
        ''', (date, description, amount))
        existing = cursor.fetchone()

        if existing:
            cursor.execute('''
                UPDATE transactions
                SET type = ?, running_balance = ?, category_id = ?, account_id = ?,
                    metadata = ?, updated_at = ?
                WHERE id = ?
            ''', (trans_type, running_balance, category_id, account_id, metadata, now, existing[0]))
            self.conn.commit()
            return existing[0]
        else:
            cursor.execute('''
                INSERT INTO transactions (date, type, amount, running_balance, category_id,
                                         account_id, description, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (date, trans_type, amount, running_balance, category_id, account_id,
                  description, metadata, now, now))
            self.conn.commit()
            return cursor.lastrowid

    def create_dedup_index(self):
        """创建去重索引（如果不存在）"""
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_transactions_dedup
                ON transactions(date, description, amount)
            ''')
            self.conn.commit()
        except sqlite3.OperationalError:
            pass

    def get_db_path(self) -> str:
        """获取数据库文件路径"""
        return self.db_path

    def delete_transaction(self, transaction_id: int):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM transaction_tags WHERE transaction_id = ?', (transaction_id,))
        cursor.execute('DELETE FROM transactions WHERE id = ?', (transaction_id,))
        self.conn.commit()
        self.create_backup()

    def close(self):
        self.conn.close()
