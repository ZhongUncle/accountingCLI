from typing import Dict, Any, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from .models import Transaction, Account, Subscription


class Visualizer:
    def __init__(self):
        self.console = Console()

    def print_transactions(self, transactions: List[Transaction]):
        if not transactions:
            self.console.print("[yellow]没有找到交易记录[/yellow]")
            return
        
        table = Table(title="交易记录")
        table.add_column("ID", style="cyan")
        table.add_column("日期", style="magenta")
        table.add_column("类型", style="yellow")
        table.add_column("金额", style="green")
        table.add_column("余额", style="blue")
        table.add_column("描述", style="white")
        table.add_column("分类", style="cyan")
        table.add_column("账户", style="magenta")
        table.add_column("标签", style="yellow")
        
        for tx in transactions:
            type_style = "green" if tx.type == "income" else "red"
            amount_text = f"+{tx.amount:.2f}" if tx.type == "income" else f"-{tx.amount:.2f}"
            tags_text = ",".join(f"#{t}" for t in tx.tags)
            
            table.add_row(
                str(tx.id),
                tx.date,
                Text(tx.type, style=type_style),
                Text(amount_text, style=type_style),
                f"{tx.running_balance:.2f}",
                tx.description or "",
                tx.category_name or "",
                tx.account_name or "",
                tags_text
            )
        
        self.console.print(table)

    def print_balance(self, accounts: List[Account]):
        table = Table(title="账户余额")
        table.add_column("账户", style="cyan")
        table.add_column("类型", style="magenta")
        table.add_column("余额", style="green")
        table.add_column("货币", style="yellow")
        
        for acc in accounts:
            balance_style = "green" if acc.balance >= 0 else "red"
            table.add_row(
                acc.name,
                acc.type,
                Text(f"{acc.balance:.2f}", style=balance_style),
                acc.currency
            )
        
        self.console.print(table)

    def print_stats(self, stats: Dict[str, Any]):
        self.console.print(f"\n[bold cyan]统计报告 ({stats['from_date']} 至 {stats['to_date']})[/bold cyan]")
        
        net_style = "green" if stats["net"] >= 0 else "red"
        
        table = Table(title="汇总")
        table.add_column("项目", style="cyan")
        table.add_column("金额", style="yellow")
        table.add_row("总收入", f"+{stats['total_income']:.2f}", style="green")
        table.add_row("总支出", f"-{stats['total_expense']:.2f}", style="red")
        table.add_row("净收支", Text(f"{stats['net']:.2f}", style=net_style))
        
        self.console.print(table)
        
        if stats["by_category"]:
            cat_table = Table(title="分类统计")
            cat_table.add_column("分类", style="cyan")
            cat_table.add_column("收入", style="green")
            cat_table.add_column("支出", style="red")
            cat_table.add_column("净额", style="yellow")
            
            for cat_name, data in stats["by_category"].items():
                net = data["income"] - data["expense"]
                net_style = "green" if net >= 0 else "red"
                cat_table.add_row(
                    cat_name,
                    f"{data['income']:.2f}",
                    f"{data['expense']:.2f}",
                    Text(f"{net:.2f}", style=net_style)
                )
            
            self.console.print(cat_table)
            self._print_ascii_chart(stats["by_category"])

    def _print_ascii_chart(self, category_data: Dict[str, Dict[str, float]]):
        self.console.print("\n[bold cyan]支出ASCII图表[/bold cyan]")
        
        expenses = {k: v["expense"] for k, v in category_data.items() if v["expense"] > 0}
        if not expenses:
            self.console.print("[yellow]没有支出数据[/yellow]")
            return
        
        max_expense = max(expenses.values())
        max_bar_length = 40
        
        sorted_cats = sorted(expenses.items(), key=lambda x: x[1], reverse=True)
        
        for cat_name, amount in sorted_cats:
            bar_length = int((amount / max_expense) * max_bar_length) if max_expense > 0 else 0
            bar = "█" * bar_length
            self.console.print(f"[cyan]{cat_name:<10}[/cyan] | [red]{bar}[/red] {amount:.2f}")

    def print_tags(self, tags: List[Subscription]):
        if not tags:
            self.console.print("[yellow]没有标签[/yellow]")
            return
        
        table = Table(title="标签列表")
        table.add_column("ID", style="cyan")
        table.add_column("名称", style="magenta")
        table.add_column("颜色", style="yellow")
        
        for tag in tags:
            table.add_row(str(tag.id), tag.name, tag.color or "")
        
        self.console.print(table)

    def print_subscriptions(self, subscriptions: List[Subscription]):
        if not subscriptions:
            self.console.print("[yellow]没有订阅[/yellow]")
            return
        
        table = Table(title="订阅列表")
        table.add_column("ID", style="cyan")
        table.add_column("名称", style="magenta")
        table.add_column("平台", style="yellow")
        table.add_column("金额", style="green")
        table.add_column("周期", style="blue")
        table.add_column("开始日期", style="cyan")
        table.add_column("自动续费", style="yellow")
        table.add_column("状态", style="magenta")
        
        for sub in subscriptions:
            status_style = "green" if sub.status == "active" else "red"
            table.add_row(
                str(sub.id),
                sub.name,
                sub.platform or "",
                f"{sub.amount:.2f}",
                sub.cycle,
                sub.start_date,
                "是" if sub.auto_renew else "否",
                Text(sub.status, style=status_style)
            )
        
        self.console.print(table)

    def print_success(self, message: str):
        self.console.print(f"[green]✓ {message}[/green]")

    def print_error(self, message: str):
        self.console.print(f"[red]✗ {message}[/red]")

    def print_info(self, message: str):
        self.console.print(f"[blue]ℹ {message}[/blue]")