"""法律免责声明和可接受使用政策（AUP）展示。"""

from rich.console import Console
from rich.panel import Panel

DISCLAIMER_TEXT = """
[bold red]⚠️ 法律风险提示 / Legal Risk Disclaimer[/bold red]

本工具用于合法的市场调研和产品改进用途。

[bold]禁止用途：[/bold]
• 竞争对手恶意攻击或抹黑
• 用户个人追踪或画像
• 制造虚假舆论（Astroturfing）
• 任何违反当地法律法规的使用

[bold]数据来源风险：[/bold]
• TikHub 为第三方数据中介，其授权状态需您自行验证
• 使用 twscrape 违反 X/Twitter 服务条款
• 使用本工具即表示您自行承担所有法律风险

[bold]隐私保护：[/bold]
• 默认启用匿名化（用户ID → 加盐哈希）
• 数据保留期默认 30 天
• 导出文件不包含真实用户身份（默认模式）

使用 [code]--accept-tos-risk[/code] 标志确认您已了解上述风险。
"""

AUP_SUMMARY = """
[bold]可接受使用政策 (AUP) 摘要：[/bold]
1. 仅用于合法市场调研和产品改进
2. 不得用于追踪、骚扰或攻击特定用户
3. 不得将数据用于虚假舆论制造
4. 必须遵守各平台服务条款
5. 必须遵守当地法律法规（包括 PIPL、GDPR）
"""


def show_disclaimer() -> None:
    """在 CLI 启动时展示法律免责声明。"""
    console = Console()
    console.print()
    console.print(Panel(DISCLAIMER_TEXT, border_style="red", padding=(1, 2)))
    console.print()
