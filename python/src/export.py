import json
import csv
from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path
from .models import Transaction, Account, Subscription


class Exporter:
    @staticmethod
    def export_transactions_to_json(transactions: List[Transaction], filepath: str):
        data = []
        for tx in transactions:
            data.append({
                "id": tx.id,
                "date": tx.date,
                "type": tx.type,
                "amount": tx.amount,
                "running_balance": tx.running_balance,
                "description": tx.description,
                "category_name": tx.category_name,
                "account_name": tx.account_name,
                "tags": tx.tags,
                "created_at": tx.created_at,
                "updated_at": tx.updated_at
            })
        
        output = {
            "exported_at": datetime.now().isoformat(),
            "transaction_count": len(data),
            "transactions": data
        }
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    @staticmethod
    def export_transactions_to_csv(transactions: List[Transaction], filepath: str):
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "ID", "日期", "类型", "金额", "余额", "描述", "分类", "账户", "标签", "创建时间"
            ])
            for tx in transactions:
                writer.writerow([
                    tx.id,
                    tx.date,
                    tx.type,
                    tx.amount,
                    tx.running_balance,
                    tx.description or "",
                    tx.category_name or "",
                    tx.account_name or "",
                    ",".join(tx.tags),
                    tx.created_at
                ])

    @staticmethod
    def export_accounts_to_json(accounts: List[Account], filepath: str):
        data = []
        for acc in accounts:
            data.append({
                "id": acc.id,
                "name": acc.name,
                "type": acc.type,
                "balance": acc.balance,
                "currency": acc.currency,
                "created_at": acc.created_at,
                "updated_at": acc.updated_at
            })
        
        output = {
            "exported_at": datetime.now().isoformat(),
            "account_count": len(data),
            "accounts": data
        }
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    @staticmethod
    def export_subscriptions_to_json(subscriptions: List[Subscription], filepath: str):
        data = []
        for sub in subscriptions:
            data.append({
                "id": sub.id,
                "name": sub.name,
                "platform": sub.platform,
                "amount": sub.amount,
                "currency": sub.currency,
                "cycle": sub.cycle,
                "start_date": sub.start_date,
                "end_date": sub.end_date,
                "auto_renew": sub.auto_renew,
                "status": sub.status,
                "created_at": sub.created_at,
                "updated_at": sub.updated_at
            })
        
        output = {
            "exported_at": datetime.now().isoformat(),
            "subscription_count": len(data),
            "subscriptions": data
        }
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def generate_csv_template(filepath: str):
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            
            # 先写表头
            writer.writerow(["date", "description", "amount", "category", "account", "tags"])
            
            # 写入示例数据
            writer.writerow(["2024-04-01 08:30:00", "早餐", "-25", "早餐", "总账户", "#餐饮 #早餐"])
            writer.writerow(["2024-04-01 10:00:00", "工资", "8000", "工资", "银行卡", "#收入"])
            writer.writerow(["2024-04-02 09:00:00", "地铁", "-4", "地铁", "支付宝", "#交通"])
            writer.writerow(["2024-04-02 12:00:00", "午餐", "-30", "午餐", "微信", "#餐饮 #午餐"])
        
        # 另外生成说明文档
        readme_file = Path(filepath).parent / "README_IMPORT.md"
        with open(readme_file, "w", encoding="utf-8") as f:
            f.write("# 记账数据导入说明\n\n")
            f.write("## CSV格式说明\n\n")
            f.write("| 字段 | 必填 | 说明 |\n")
            f.write("|------|------|------|\n")
            f.write("| date | ✅ | 日期时间，格式 YYYY-MM-DD HH:MM:SS（也支持 YYYY-MM-DD） |\n")
            f.write("| description | ✅ | 描述 |\n")
            f.write("| amount | ✅ | 金额，正数为收入，负数为支出 |\n")
            f.write("| category | ❌ | 分类 |\n")
            f.write("| account | ❌ | 账户，默认总账户 |\n")
            f.write("| tags | ❌ | 标签，用空格分隔 |\n\n")
            f.write("## 可用账户\n\n")
            f.write("- 总账户\n")
            f.write("- 银行卡\n")
            f.write("- 支付宝\n")
            f.write("- 微信\n\n")
            f.write("## 常用分类\n\n")
            f.write("早餐, 午餐, 晚餐, 公交, 地铁, 打车, 工资, 奖金等\n\n")
            f.write("## 导入命令\n\n")
            f.write("```bash\n")
            f.write("acc import csv my_data.csv\n")
            f.write("```\n\n")
            f.write("### 重复处理模式\n\n")
            f.write("- `--mode skip` - 跳过重复（默认）\n")
            f.write("- `--mode replace` - 替换重复记录\n")
            f.write("- `--mode keep_both` - 保留两者\n")
