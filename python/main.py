#!/usr/bin/env python3
from datetime import datetime, timedelta
from src.embedding import EmbeddingEngine
from src.visualization import Visualizer
from src.export import Exporter
from src.commands import AccountingService
from src.database import Database
from src.llm import LLMClient
from src.agent import FinanceAgent
import argparse
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import box
from rich.markdown import Markdown

sys.path.insert(0, str(Path(__file__).parent))


console = Console()
visualizer = Visualizer()


def parse_ctx_size(ctx_size_str):
    """解析上下文大小字符串，如 '8k', '32k', '128k' -> 8192, 32768, 131072"""
    ctx_size_str = ctx_size_str.strip().lower()
    multipliers = {
        'k': 1024,
        'm': 1024 * 1024,
    }
    
    for suffix, mult in multipliers.items():
        if ctx_size_str.endswith(suffix):
            try:
                num = float(ctx_size_str[:-len(suffix)])
                return int(num * mult)
            except ValueError:
                pass
    
    # 尝试直接解析数字
    try:
        return int(ctx_size_str)
    except ValueError:
        # 默认返回 256k
        return 262144


def get_db_path():
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    return str(data_dir / "accounting.db")


def print_transaction_table(transactions):
    table = Table(title="交易记录", box=box.ROUNDED)
    table.add_column("ID", style="cyan")
    table.add_column("日期", style="magenta")
    table.add_column("类型", style="yellow")
    table.add_column("金额", style="green" if len(transactions)
                     == 0 or transactions[0].amount > 0 else "red")
    table.add_column("余额", style="blue")
    table.add_column("描述", style="white")
    table.add_column("分类", style="cyan")
    table.add_column("账户", style="yellow")
    table.add_column("标签", style="magenta")

    for tx in transactions:
        amount_str = f"+{tx.amount:.2f}" if tx.type == "income" else f"-{tx.amount:.2f}"
        tags_str = " ".join([f"#{tag}" for tag in tx.tags]) if tx.tags else ""
        table.add_row(
            str(tx.id),
            tx.date,
            tx.type,
            amount_str,
            f"{tx.running_balance:.2f}",
            tx.description,
            tx.category_name or "",
            tx.account_name or "",
            tags_str
        )

    console.print(table)


def print_account_table(accounts):
    table = Table(title="账户余额", box=box.ROUNDED)
    table.add_column("账户", style="cyan")
    table.add_column("类型", style="magenta")
    table.add_column("余额", style="green")
    table.add_column("货币", style="yellow")

    for acc in accounts:
        table.add_row(acc.name, acc.type, f"{acc.balance:.2f}", acc.currency)

    console.print(table)


def print_stats(stats):
    console.print(
        f"\n统计报告 ({stats['from_date']} 至 {stats['to_date']})\n", style="bold")

    summary_table = Table(title="汇总", box=box.ROUNDED)
    summary_table.add_column("项目", style="cyan")
    summary_table.add_column("金额", style="green")
    summary_table.add_row("总收入", f"+{stats['total_income']:.2f}")
    summary_table.add_row("总支出", f"-{stats['total_expense']:.2f}")
    summary_table.add_row("净收支", f"{stats['net']:.2f}")
    console.print(summary_table)

    if stats.get("by_category"):
        cat_table = Table(title="分类统计", box=box.ROUNDED)
        cat_table.add_column("分类", style="cyan")
        cat_table.add_column("收入", style="green")
        cat_table.add_column("支出", style="red")
        cat_table.add_column("净额", style="yellow")

        for cat, data in stats["by_category"].items():
            net = data["income"] - data["expense"]
            cat_table.add_row(
                cat,
                f"{data['income']:.2f}",
                f"{data['expense']:.2f}",
                f"{net:.2f}"
            )

        console.print(cat_table)

        console.print("\n支出ASCII图表")
        max_width = 40
        expenses = {k: v["expense"]
                    for k, v in stats["by_category"].items() if v["expense"] > 0}
        if expenses:
            max_expense = max(expenses.values())
            for cat, amount in sorted(expenses.items(), key=lambda x: -x[1]):
                bar_length = int((amount / max_expense) *
                                 max_width) if max_expense > 0 else 0
                console.print(f"{cat:<12} | {'█' * bar_length} {amount:.2f}")


def main():
    parser = argparse.ArgumentParser(
        description="跨平台记账软件 - 记录日常开销和存款余额",
        epilog="示例:\n  acc add 早餐 -25                    # 添加一笔支出\n  acc add 工资 +8000                  # 添加一笔收入\n  acc list --month                    # 查看本月记录\n  acc balance                         # 查看余额\n  acc stats --category                # 查看分类统计\n  acc export json ./export.json       # 导出数据",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(title="命令", dest="command")

    add_parser = subparsers.add_parser("add", help="添加交易")
    add_parser.add_argument("description", help="交易描述")
    add_parser.add_argument("amount", type=float, help="金额（正为收入，负为支出）")
    add_parser.add_argument("--date", help="日期 (YYYY-MM-DD)")
    add_parser.add_argument("--category", help="分类名称")
    add_parser.add_argument("--account", default="总账户", help="账户名称")
    add_parser.add_argument("--tags", nargs="*", help="标签列表")

    insert_parser = subparsers.add_parser("insert", help="插入历史记录（自动重算余额）")
    insert_parser.add_argument("date", help="日期 (YYYY-MM-DD)")
    insert_parser.add_argument("description", help="交易描述")
    insert_parser.add_argument("amount", type=float, help="金额（正为收入，负为支出）")
    insert_parser.add_argument("--category", help="分类名称")
    insert_parser.add_argument("--account", default="总账户", help="账户名称")
    insert_parser.add_argument("--tags", nargs="*", help="标签列表")

    list_parser = subparsers.add_parser("list", help="列出交易记录")
    list_parser.add_argument("--from", dest="from_date", help="起始日期")
    list_parser.add_argument("--to", dest="to_date", help="结束日期")
    list_parser.add_argument("--category", help="按分类过滤")
    list_parser.add_argument("--account", help="按账户过滤")
    list_parser.add_argument("--tag", help="按标签过滤")
    list_parser.add_argument("--limit", type=int, help="限制条数")
    list_parser.add_argument("--month", action="store_true", help="查看本月记录")
    list_parser.add_argument("--week", action="store_true", help="查看本周记录")

    balance_parser = subparsers.add_parser("balance", help="查看账户余额")
    balance_parser.add_argument("--account", help="指定账户")

    stats_parser = subparsers.add_parser("stats", help="查看统计报告")
    stats_parser.add_argument("--from", dest="from_date", help="起始日期")
    stats_parser.add_argument("--to", dest="to_date", help="结束日期")
    stats_parser.add_argument("--month", action="store_true", help="查看本月统计")
    stats_parser.add_argument("--category", action="store_true", help="按分类统计")

    export_parser = subparsers.add_parser("export", help="导出数据")
    export_parser.add_argument("format", choices=["json", "csv"], help="导出格式")
    export_parser.add_argument("output", help="输出文件路径")

    tag_parser = subparsers.add_parser("tag", help="标签管理")
    tag_subparsers = tag_parser.add_subparsers(dest="tag_command")
    tag_list_parser = tag_subparsers.add_parser("list", help="列出所有标签")

    sub_parser = subparsers.add_parser("subscription", help="订阅管理")
    sub_subparsers = sub_parser.add_subparsers(dest="sub_command")
    sub_list_parser = sub_subparsers.add_parser("list", help="列出订阅")

    backup_parser = subparsers.add_parser("backup", help="备份管理")
    backup_subparsers = backup_parser.add_subparsers(dest="backup_command")
    backup_list_parser = backup_subparsers.add_parser("list", help="列出备份")
    backup_create_parser = backup_subparsers.add_parser(
        "create", help="创建数据库备份")
    backup_restore_parser = backup_subparsers.add_parser(
        "restore", help="从备份恢复")
    backup_restore_parser.add_argument("backup_file", help="备份文件路径")

    set_balance_parser = subparsers.add_parser("set-balance", help="设置账户余额")
    set_balance_parser.add_argument("account", help="账户名称")
    set_balance_parser.add_argument("balance", type=float, help="目标余额")
    set_balance_parser.add_argument("--date", help="初始余额日期（可选）")

    set_all_balances_parser = subparsers.add_parser(
        "set-all-balances", help="设置多个账户余额")
    set_all_balances_parser.add_argument("balances", nargs="+",
                                         help="账户余额对，格式：账户=余额（如：微信=100.17）")
    set_all_balances_parser.add_argument("--date", help="初始余额日期（仅用于创建初始交易时）")
    set_all_balances_parser.add_argument("--create-initial-tx", action="store_true",
                                         help="创建初始余额交易（不推荐，通常只更新账户余额即可）")

    recalc_balances_parser = subparsers.add_parser(
        "recalculate-balances", help="从当前余额倒推重算所有交易余额")

    import_parser = subparsers.add_parser("import", help="导入数据")
    import_subparsers = import_parser.add_subparsers(dest="import_command")

    import_template_parser = import_subparsers.add_parser(
        "template", help="生成CSV导入模板")
    import_template_parser.add_argument("filepath", help="模板文件路径")

    import_csv_parser = import_subparsers.add_parser("csv", help="从CSV导入数据（自动检测来源）")
    import_csv_parser.add_argument("filepath", help="CSV文件路径")
    import_csv_parser.add_argument("--source", choices=["alipay", "wechat", "generic", "auto"],
                                   default="auto", help="数据来源（默认自动检测）")
    import_csv_parser.add_argument("--mode", choices=["skip", "replace", "keep_both"],
                                   default="skip", help="重复处理模式（默认跳过）")
    import_csv_parser.add_argument("--account", type=str, default=None,
                                   help="关联账户名称")
    import_csv_parser.add_argument("--balance", type=float, default=None,
                                   help="账户当前余额（用于倒序计算历史余额）")

    import_detect_parser = import_subparsers.add_parser("detect", help="自动检测来源并导入CSV数据（import csv --source auto 的别名）")
    import_detect_parser.add_argument("filepath", help="CSV文件路径")
    import_detect_parser.add_argument("--mode", choices=["skip", "replace", "keep_both"],
                                      default="skip", help="重复处理模式（默认跳过）")
    import_detect_parser.add_argument("--account", type=str, default=None,
                                      help="关联账户名称")
    import_detect_parser.add_argument("--balance", type=float, default=None,
                                      help="账户当前余额（用于倒序计算历史余额）")

    search_parser = subparsers.add_parser("search", help="语义搜索交易记录")
    search_parser.add_argument("query", help="搜索关键词")
    search_parser.add_argument("--top", type=int, default=5, help="返回结果数量")

    embed_parser = subparsers.add_parser("embed", help="Embedding管理")
    embed_subparsers = embed_parser.add_subparsers(dest="embed_command")
    embed_compute_parser = embed_subparsers.add_parser(
        "compute", help="计算所有交易的embedding")
    embed_status_parser = embed_subparsers.add_parser(
        "status", help="查看embedding覆盖率")

    chat_parser = subparsers.add_parser("chat", help="与AI对话分析交易数据（智能体自动查询）")
    chat_parser.add_argument("query", nargs="+", help="问题描述")
    chat_parser.add_argument("--nothink", action="store_true", help="禁用AI思考链路（更快响应）")
    chat_parser.add_argument("--no-think", action="store_true", help="禁用AI思考链路（更快响应）")
    chat_parser.add_argument("--ctx-size", type=str, help="分析阶段上下文大小（如：8k, 32k, 64k, 128k, 256k），不传则使用模型默认值")
    chat_parser.add_argument("--model", type=str, default="gemma4:e4b", help="使用的Ollama模型（默认：gemma4:e4b）")

    analyze_parser = subparsers.add_parser("analyze", help="AI财务深度分析")
    analyze_subparsers = analyze_parser.add_subparsers(dest="analyze_command")
    
    analyze_report_parser = analyze_subparsers.add_parser("report", help="生成财务分析报告")
    analyze_report_parser.add_argument("--month", action="store_true", help="分析本月")
    analyze_report_parser.add_argument("--ctx-size", type=str, help="上下文大小（如：8k, 32k, 64k, 128k, 256k），不传则使用模型默认值")
    analyze_report_parser.add_argument("--model", type=str, default="gemma4:e4b", help="使用的Ollama模型（默认：gemma4:e4b）")
    
    analyze_budget_parser = analyze_subparsers.add_parser("budget", help="生成预算建议")
    analyze_budget_parser.add_argument("--month", action="store_true", help="基于本月数据")
    analyze_budget_parser.add_argument("--ctx-size", type=str, help="上下文大小（如：8k, 32k, 64k, 128k, 256k），不传则使用模型默认值")
    analyze_budget_parser.add_argument("--model", type=str, default="gemma4:e4b", help="使用的Ollama模型（默认：gemma4:e4b）")
    
    args = parser.parse_args()

    db = Database(get_db_path())
    service = AccountingService(db)

    if args.command == "add":
        try:
            tx = service.add_transaction(
                args.description, args.amount, args.date,
                args.category, args.account, args.tags
            )
            console.print("✓ 交易添加成功", style="bold green")
            print_transaction_table([tx])
        except Exception as e:
            console.print(f"✗ 错误: {e}", style="bold red")

    elif args.command == "insert":
        try:
            tx = service.insert_transaction(
                args.date, args.description, args.amount,
                args.category, args.account, args.tags
            )
            console.print("✓ 历史记录插入成功，余额已重算", style="bold green")
            print_transaction_table([tx])
        except Exception as e:
            console.print(f"✗ 错误: {e}", style="bold red")

    elif args.command == "list":
        from_date = args.from_date
        to_date = args.to_date

        if args.month:
            today = datetime.now()
            from_date = today.replace(day=1).strftime("%Y-%m-%d")
        elif args.week:
            today = datetime.now()
            from_date = (today - timedelta(days=today.weekday())
                         ).strftime("%Y-%m-%d")

        txs = service.list_transactions(
            from_date, to_date, args.category, args.account,
            args.tag, args.limit
        )
        if txs:
            print_transaction_table(txs)
        else:
            console.print("没有找到交易记录", style="yellow")

    elif args.command == "balance":
        accounts = service.get_balance(args.account)
        print_account_table(accounts)

    elif args.command == "stats":
        from_date = args.from_date
        to_date = args.to_date

        if args.month:
            today = datetime.now()
            from_date = today.replace(day=1).strftime("%Y-%m-%d")

        stats = service.get_stats(from_date, to_date, args.category)
        print_stats(stats)

    elif args.command == "export":
        try:
            if args.format == "json":
                count = db.export_to_json(args.output)
            else:
                count = db.export_to_csv(args.output)
            console.print(
                f"✓ 已导出 {count} 条记录到 {args.output}", style="bold green")
        except Exception as e:
            console.print(f"✗ 错误: {e}", style="bold red")

    elif args.command == "tag":
        if args.tag_command == "list":
            tags = service.list_tags()
            if tags:
                table = Table(title="标签列表", box=box.ROUNDED)
                table.add_column("ID", style="cyan")
                table.add_column("名称", style="magenta")
                for tag in tags:
                    table.add_row(str(tag.id), tag.name)
                console.print(table)
            else:
                console.print("没有标签", style="yellow")

    elif args.command == "subscription":
        if args.sub_command == "list":
            subs = service.list_subscriptions()
            if subs:
                table = Table(title="订阅列表", box=box.ROUNDED)
                table.add_column("ID", style="cyan")
                table.add_column("名称", style="magenta")
                table.add_column("金额", style="green")
                table.add_column("周期", style="yellow")
                table.add_column("开始日期", style="blue")
                table.add_column("状态", style="red")
                for sub in subs:
                    table.add_row(str(sub.id), sub.name, f"{sub.amount:.2f}",
                                  sub.cycle, sub.start_date, sub.status)
                console.print(table)
            else:
                console.print("没有订阅", style="yellow")

    elif args.command == "backup":
        if args.backup_command == "list":
            backups = db.list_backups()
            if backups:
                table = Table(title="备份列表", box=box.ROUNDED)
                table.add_column("文件名", style="cyan")
                table.add_column("日期", style="magenta")
                table.add_column("大小", style="green")
                for b in backups:
                    table.add_row(b["filename"], b["date"], b["size"])
                console.print(table)
            else:
                console.print("没有备份", style="yellow")
        elif args.backup_command == "create":
            try:
                backup_path = db.create_backup()
                console.print(f"✓ 备份已创建: {backup_path}", style="bold green")
            except Exception as e:
                console.print(f"✗ 错误: {e}", style="bold red")
        elif args.backup_command == "restore":
            try:
                db.restore_from_backup(args.backup_file)
                console.print("✓ 备份恢复成功", style="bold green")
            except Exception as e:
                console.print(f"✗ 错误: {e}", style="bold red")

    elif args.command == "set-balance":
        try:
            tx = service.set_account_balance(
                args.account, args.balance, args.date)
            console.print(
                f"✓ {args.account} 余额已设置为 {args.balance:.2f}", style="bold green")
            print_transaction_table([tx])
        except Exception as e:
            console.print(f"✗ 错误: {e}", style="bold red")

    elif args.command == "set-all-balances":
        try:
            balances = {}
            for item in args.balances:
                if "=" in item:
                    account, balance_str = item.split("=", 1)
                    try:
                        balances[account.strip()] = float(balance_str.strip())
                    except ValueError:
                        console.print(f"⚠️ 跳过无效格式: {item}", style="yellow")

            if not balances:
                console.print("✗ 错误: 没有有效的账户余额对（格式：账户=余额）", style="bold red")
            else:
                results = service.set_multiple_balances(
                    balances, args.date, args.create_initial_tx)
                console.print("✓ 已设置以下账户余额:", style="bold green")
                for name, balance in balances.items():
                    console.print(f"  • {name}: {balance:.2f}", style="green")
                console.print(
                    f"  • 总账户: {results.get('recalculate_info', {}).get('accounts_processed', 0)} 个账户已处理", style="green")
                console.print(
                    f"  • 重算余额: {results.get('transactions_updated', 0)} 条交易已更新", style="green")
                accounts = service.get_balance()
                print_account_table(accounts)
        except Exception as e:
            console.print(f"✗ 错误: {e}", style="bold red")

    elif args.command == "recalculate-balances":
        try:
            results = service.recalculate_all_balances_backwards()
            console.print("✓ 余额已重算完成:", style="bold green")
            console.print(
                f"  • 处理账户: {results['accounts_processed']} 个", style="green")
            console.print(
                f"  • 更新交易: {results['transactions_updated']} 条", style="green")
            if results['errors']:
                console.print(
                    f"  • 错误: {len(results['errors'])} 个", style="red")
                for err in results['errors']:
                    console.print(f"    - {err}", style="red")
            accounts = service.get_balance()
            print_account_table(accounts)
        except Exception as e:
            console.print(f"✗ 错误: {e}", style="bold red")

    elif args.command == "import":
        if args.import_command == "template":
            try:
                Exporter.generate_csv_template(args.filepath)
                visualizer.print_success(f"CSV模板已生成: {args.filepath}")
                console.print("\n💡 提示: 编辑模板文件，填入你的数据后，使用 'import csv' 命令导入")
            except Exception as e:
                visualizer.print_error(f"{e}")
        elif args.import_command in ("csv", "detect"):
            try:
                import traceback
                source = args.source if args.source != "auto" else None
                results = service.import_csv(
                    args.filepath,
                    source=source,
                    account_name=args.account,
                    account_balance=args.balance,
                    mode=args.mode
                )

                # 打印汇总报告
                source_name = results.get("source", "未知")
                console.print("\n" + "=" * 60)
                console.print(f"📋 导入结果汇总 (来源: {source_name})", style="bold")
                console.print("=" * 60)
                console.print(f"  总处理: {results['total']} 条")
                if "ignored_count" in results:
                    console.print(f"  忽略: {results['ignored_count']} 条（交易未成功）")
                console.print()
                console.print(f"  ✅ 成功: {results['success']} 条", style="green")
                console.print(
                    f"  ⚠️  跳过: {results['skipped']} 条", style="yellow")
                console.print(f"  ❌ 失败: {results['failed']} 条", style="red")
                console.print("=" * 60)

                # 打印错误详情
                if results["errors"]:
                    console.print("\n❌ 失败详情:", style="bold red")
                    for error in results["errors"]:
                        console.print(f"  {error}")

                # 打印警告详情
                if results["warnings"]:
                    console.print("\n⚠️  警告详情:", style="bold yellow")
                    for warning in results["warnings"]:
                        console.print(f"  {warning}")

                # 打印导入的交易
                if results["imported_transactions"]:
                    console.print("\n✅ 成功导入的交易:", style="bold green")
                    visualizer.print_transactions(
                        results["imported_transactions"])

                console.print()
                visualizer.print_success("导入完成！")
            except Exception as e:
                import traceback
                visualizer.print_error(f"{e}\n{traceback.format_exc()}")

    elif args.command == "search":
        try:
            embed_engine = EmbeddingEngine(db)

            if not embed_engine.is_available():
                console.print("⚠️ Embedding功能不可用", style="bold yellow")
                console.print("请先安装：pip install sentence-transformers numpy")
            else:
                txs = service.list_transactions()
                if not txs:
                    console.print("没有交易记录", style="yellow")
                else:
                    console.print(f"🔍 搜索：{args.query}", style="bold")
                    results = embed_engine.semantic_search(
                        args.query, txs, args.top)

                    if results:
                        table = Table(title="搜索结果", box=box.ROUNDED)
                        table.add_column("相似度", style="cyan")
                        table.add_column("日期", style="magenta")
                        table.add_column("类型", style="yellow")
                        table.add_column("金额", style="green")
                        table.add_column("描述", style="white")
                        table.add_column("分类", style="cyan")
                        table.add_column("账户", style="yellow")

                        for result in results:
                            tx = result["transaction"]
                            similarity = result["similarity"]
                            amount_str = f"+{tx.amount:.2f}" if tx.type == "income" else f"-{tx.amount:.2f}"
                            table.add_row(
                                f"{similarity:.2%}",
                                tx.date,
                                tx.type,
                                amount_str,
                                tx.description,
                                tx.category_name or "",
                                tx.account_name or ""
                            )

                        console.print(table)
                    else:
                        console.print("没有找到相关交易", style="yellow")
        except Exception as e:
            import traceback
            visualizer.print_error(f"{e}\n{traceback.format_exc()}")

    elif args.command == "embed":
        if args.embed_command == "compute":
            try:
                embed_engine = EmbeddingEngine(db)

                if not embed_engine.is_available():
                    console.print("⚠️ Embedding功能不可用", style="bold yellow")
                    console.print(
                        "请先安装：pip install numpy requests，并启动 Ollama")
                else:
                    txs = service.list_transactions()
                    if not txs:
                        console.print("没有交易记录", style="yellow")
                    else:
                        console.print(
                            f"🧠 正在计算 {len(txs)} 条交易的embedding...", style="bold")

                        def progress_callback(current, total):
                            console.print(
                                f"进度：{current}/{total} ({current/total:.1%})", end="\r")

                        success_count = embed_engine.compute_all_embeddings(
                            txs, progress_callback)

                        console.print(
                            f"\n✅ 完成！成功计算 {success_count}/{len(txs)} 条交易的embedding", style="bold green")
            except Exception as e:
                import traceback
                visualizer.print_error(f"{e}\n{traceback.format_exc()}")
        elif args.embed_command == "status":
            try:
                embed_engine = EmbeddingEngine(db)

                if not embed_engine.is_available():
                    console.print("⚠️ Embedding功能不可用", style="bold yellow")
                    console.print(
                        "请先安装：pip install numpy requests，并启动 Ollama")
                else:
                    coverage = embed_engine.get_embedding_coverage()

                    table = Table(title="Embedding覆盖率", box=box.ROUNDED)
                    table.add_column("项目", style="cyan")
                    table.add_column("数量", style="yellow")

                    table.add_row("总交易数", str(coverage["total"]))
                    table.add_row("已计算", str(coverage["covered"]))
                    table.add_row("未计算", str(coverage["missing"]))

                    console.print(table)

                    if coverage["total"] > 0:
                        percent = coverage["covered"] / coverage["total"]
                        console.print(f"\n覆盖率：{percent:.1%}", style="bold")
                        if percent < 1:
                            console.print("\n💡 提示：使用 'embed compute' 命令计算缺失的embedding", style="yellow")
            except Exception as e:
                import traceback
                visualizer.print_error(f"{e}\n{traceback.format_exc()}")

    elif args.command == "chat":
        try:
            query = " ".join(args.query)
            nothink = args.nothink or args.no_think
            ctx_size = parse_ctx_size(args.ctx_size) if args.ctx_size else None
            console.print(f"\n💬 用户问题：{query}\n", style="bold blue")
            if args.ctx_size:
                console.print(f"📐 上下文大小：{args.ctx_size} ({ctx_size} tokens)\n", style="cyan")
            else:
                console.print(f"📐 上下文大小：使用模型默认值\n", style="cyan")
            console.print(f"🧠 使用模型：{args.model}\n", style="cyan")

            # 使用新的智能体
            agent = FinanceAgent(get_db_path(), model=args.model)
            if not agent.available:
                console.print("⚠️ Ollama服务不可用", style="bold yellow")
                console.print("请确保 Ollama 已启动并且模型可用")
                console.print("\n启动命令：ollama run gemma4:e4b")
            else:
                console.print("🤖 智能体正在分析中...\n", style="cyan")
                response = agent.process_query(query, nothink=nothink, ctx_size=ctx_size)

                if response:
                    console.print("\n" + "="*60)
                    console.print("📊 AI智能分析结果", style="bold green")
                    console.print("="*60 + "\n")
                    console.print(response)
                else:
                    console.print("未获得有效响应", style="red")
        except Exception as e:
            import traceback
            visualizer.print_error(f"{e}\n{traceback.format_exc()}")

    elif args.command == "analyze":
        try:
            from_date = None
            period = "全部"
            
            if args.month:
                today = datetime.now()
                from_date = today.replace(day=1).strftime("%Y-%m-%d")
                period = "本月"

            ctx_size = parse_ctx_size(args.ctx_size) if args.ctx_size else None

            console.print(f"\n📊 AI财务深度分析", style="bold blue")
            if args.month:
                console.print(f"📅 时间范围：本月 ({from_date} 至今)\n", style="cyan")
            if args.ctx_size:
                console.print(f"📐 上下文大小：{args.ctx_size} ({ctx_size} tokens)\n", style="cyan")
            else:
                console.print(f"📐 上下文大小：使用模型默认值\n", style="cyan")
            console.print(f"🧠 使用模型：{args.model}\n", style="cyan")

            llm_client = LLMClient(model=args.model)
            if not llm_client.available:
                console.print("⚠️ LLM服务不可用", style="bold yellow")
                console.print("请确保 Ollama 已启动并且模型可用")
                console.print("\n启动：ollama run gemma4:e4b")
            else:
                with console.status("正在分析数据，请稍候...", spinner="dots"):
                    all_txs = service.list_transactions(from_date, None)
                    if not all_txs:
                        console.print("没有找到交易记录", style="yellow")
                    else:
                        txs_data = []
                        for tx in all_txs:
                            txs_data.append({
                                "date": tx.date,
                                "type": tx.type,
                                "amount": tx.amount,
                                "description": tx.description,
                                "category": tx.category_name or "未分类"
                            })

                        stats = service.get_stats(from_date, None, True)

                        if args.analyze_command == "report":
                            console.print("\n📋 生成财务分析报告...", style="cyan")
                            response = llm_client.generate_analysis_report(txs_data, stats, period, num_ctx=ctx_size)
                            if response:
                                console.print("\n" + "="*60)
                                console.print("📊 财务分析报告", style="bold green")
                                console.print("="*60 + "\n")
                                console.print(response)
                        
                        elif args.analyze_command == "budget":
                            console.print("\n💰 生成预算建议...", style="cyan")
                            response = llm_client.generate_budget_advice(txs_data, stats, num_ctx=ctx_size)
                            if response:
                                console.print("\n" + "="*60)
                                console.print("💰 预算建议", style="bold green")
                                console.print("="*60 + "\n")
                                console.print(response)
        
        except Exception as e:
            import traceback
            visualizer.print_error(f"{e}\n{traceback.format_exc()}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
