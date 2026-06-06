#!/usr/bin/env python3
"""
数据迁移脚本：把旧位置的数据迁移到用户目录 ~/.accounting/
"""
import sys
import shutil
from pathlib import Path

def migrate_data(auto_yes=False):
    print("=== 数据迁移工具 ===")
    print()
    
    # 旧位置
    project_root = Path(__file__).parent.parent
    old_data_dir = project_root / "data"
    old_backup_dir = project_root / "backups"
    
    # 新位置
    home_dir = Path.home()
    new_data_dir = home_dir / ".accounting" / "data"
    new_backup_dir = home_dir / ".accounting" / "backups"
    
    # 检查旧数据是否存在
    old_db = old_data_dir / "accounting.db"
    if not old_db.exists():
        print("✓ 没有找到旧数据，无需迁移")
        return False
    
    print(f"发现旧数据库: {old_db}")
    print()
    
    # 确认
    if not auto_yes:
        try:
            response = input("是否要迁移数据到新位置？(y/n): ").strip().lower()
            if response != 'y':
                print("取消迁移")
                return False
        except EOFError:
            print("非交互模式，使用 --yes 自动确认")
            return False
    
    # 创建新目录
    new_data_dir.mkdir(parents=True, exist_ok=True)
    (new_backup_dir / "primary").mkdir(parents=True, exist_ok=True)
    (new_backup_dir / "secondary").mkdir(parents=True, exist_ok=True)
    
    # 复制数据库
    new_db = new_data_dir / "accounting.db"
    if new_db.exists() and not auto_yes:
        try:
            response = input(f"新位置已有数据库，是否覆盖？(y/n): ").strip().lower()
            if response != 'y':
                print("取消迁移")
                return False
        except EOFError:
            print("新位置已有数据库，在非交互模式下不覆盖")
            return False
    
    shutil.copy2(old_db, new_db)
    print(f"✓ 数据库已复制到: {new_db}")
    
    # 复制旧备份
    if old_backup_dir.exists():
        backups = list(old_backup_dir.glob("accounting_*.db"))
        if backups:
            print(f"\n发现 {len(backups)} 个旧备份...")
            for backup in backups:
                shutil.copy2(backup, new_backup_dir / "primary" / backup.name)
            print(f"✓ 备份已复制到: {new_backup_dir / 'primary'}")
    
    # 复制 data/backups 里的备份
    old_data_backups = old_data_dir / "backups"
    if old_data_backups.exists():
        for subdir in ["primary", "secondary"]:
            subdir_path = old_data_backups / subdir
            if subdir_path.exists():
                backups = list(subdir_path.glob("accounting_*.db"))
                if backups:
                    for backup in backups:
                        shutil.copy2(backup, new_backup_dir / subdir / backup.name)
    
    print()
    print("=== 迁移完成 ===")
    print()
    print(f"新数据位置: {new_data_dir}")
    print(f"新备份位置: {new_backup_dir}")
    print()
    print("你现在可以正常使用记账软件了！")
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="迁移旧数据到用户目录")
    parser.add_argument("--yes", "-y", action="store_true", help="自动确认所有提示")
    args = parser.parse_args()
    
    migrate_data(auto_yes=args.yes)
