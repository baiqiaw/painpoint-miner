"""CLI 入口点 — Click + Rich。"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .compliance.disclaimer import show_disclaimer
from .config.settings import Settings, load_settings
from .models.base import PipelineConfig
from .models.enums import AnalysisMode, Platform

console = Console()


def _get_or_create_settings(config_path: Optional[Path]) -> Settings:
    """加载或创建配置。"""
    return load_settings(config_path)


def _create_llm_provider(settings: Settings, cost_tracker):
    """根据 llm_mode 自动选择 LLM Provider。"""
    mode = settings.analysis.llm_mode

    if mode == "cli":
        from .llm import ClaudeCliProvider

        console.print(f"[dim]  LLM 模式: 本地 CLI ({settings.analysis.cli_command})[/dim]")
        return ClaudeCliProvider(
            cli_command=settings.analysis.cli_command,
            model=settings.analysis.llm_model,
            cost_tracker=cost_tracker,
        )
    else:  # mode == "api"
        from .llm import ClaudeProvider

        if not settings.anthropic_api_key:
            console.print("[red]API 模式需要设置 PPM_ANTHROPIC_API_KEY 环境变量[/red]")
            sys.exit(1)
        console.print(f"[dim]  LLM 模式: Anthropic API ({settings.analysis.llm_model})[/dim]")
        return ClaudeProvider(
            api_key=settings.anthropic_api_key,
            model=settings.analysis.llm_model,
            cost_tracker=cost_tracker,
        )


def _register_scrapers(registry, settings: Settings) -> list[Platform]:
    """根据已配置的 API Key 动态注册抓取器。

    Returns:
        成功注册的平台列表。
    """
    registered = []

    if settings.tikhub_api_key:
        try:
            from .scrapers.tikhub.client import TikHubClient
            from .scrapers.tikhub.xiaohongshu import XiaohongshuScraper
            from .scrapers.tikhub.weibo import WeiboScraper
            from .scrapers.tikhub.douyin import DouyinScraper
            from .scrapers.tikhub.zhihu import ZhihuScraper
            from .utils.rate_limiter import RateLimiter

            rate_limiter = RateLimiter(
                requests_per_minute=settings.scraping.rate_limit.tikhub_requests_per_minute
            )
            client = TikHubClient(
                api_key=settings.tikhub_api_key,
                rate_limiter=rate_limiter,
            )

            registry.register(Platform.XIAOHONGSHU, XiaohongshuScraper(client))
            registry.register(Platform.WEIBO, WeiboScraper(client))
            registry.register(Platform.DOUYIN, DouyinScraper(client))
            registry.register(Platform.ZHIHU, ZhihuScraper(client))
            registered.extend([Platform.XIAOHONGSHU, Platform.WEIBO, Platform.DOUYIN, Platform.ZHIHU])
        except Exception as e:
            console.print(f"[yellow]  ⚠ TikHub 抓取器注册失败: {e}[/yellow]")

    if settings.twitter_bearer_token:
        try:
            from .scrapers.twitter.api_v2_scraper import TwitterApiV2Scraper

            registry.register(Platform.TWITTER, TwitterApiV2Scraper(
                bearer_token=settings.twitter_bearer_token,
            ))
            registered.append(Platform.TWITTER)
        except Exception as e:
            console.print(f"[yellow]  ⚠ Twitter 抓取器注册失败: {e}[/yellow]")

    return registered


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """PainPoint Miner — 多平台用户痛点抓取与分析工具。"""
    pass


@cli.command()
@click.option("--config", "-c", type=click.Path(), default=None, help="配置文件路径")
@click.option("--keywords", "-k", multiple=True, help="搜索关键词（可多次指定）")
@click.option("--platforms", "-p", multiple=True, help="目标平台（可多次指定）")
@click.option("--mode", "-m", type=click.Choice(["merged", "split"]), default="merged", help="分析模式")
@click.option("--accept-tos-risk", is_flag=True, help="确认已了解服务条款风险")
@click.option("--dry-run", is_flag=True, help="仅验证配置，不执行抓取")
@click.option("--output", "-o", type=click.Path(), default=None, help="输出目录")
@click.option("--llm-mode", type=click.Choice(["cli", "api"]), default=None, help="LLM 调用方式（默认: cli）")
def run(
    config: Optional[str],
    keywords: tuple,
    platforms: tuple,
    mode: str,
    accept_tos_risk: bool,
    dry_run: bool,
    output: Optional[str],
    llm_mode: Optional[str],
):
    """执行痛点抓取与分析流水线。"""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    show_disclaimer()

    if not accept_tos_risk:
        console.print("[red]请使用 --accept-tos-risk 标志确认您已了解法律风险[/red]")
        sys.exit(1)

    config_path = Path(config) if config else None
    settings = _get_or_create_settings(config_path)

    if llm_mode:
        settings.analysis.llm_mode = llm_mode

    kw_list = list(keywords) if keywords else ["产品难用", "太贵了", "客服不回复"]
    plat_list = [Platform(p) for p in platforms] if platforms else settings.scraping.platforms

    pipeline_config = PipelineConfig(
        keywords=kw_list,
        platforms=plat_list,
        analysis_mode=AnalysisMode(mode),
        max_posts_per_keyword=settings.scraping.max_posts_per_keyword,
        max_comments_per_post=settings.scraping.max_comments_per_post,
        llm_model=settings.analysis.llm_model,
        dedup_threshold=settings.analysis.dedup.similarity_threshold,
        max_llm_budget_usd=settings.analysis.max_llm_budget_usd,
        output_dir=output or settings.export.output_dir,
        output_formats=settings.export.formats,
    )

    console.print(f"\n[bold]配置摘要:[/bold]")
    console.print(f"  关键词: {', '.join(kw_list)}")
    console.print(f"  平台: {', '.join(p.value for p in plat_list)}")
    console.print(f"  模式: {mode}")
    console.print(f"  LLM: {settings.analysis.llm_mode} ({settings.analysis.llm_model})")
    console.print(f"  输出: {pipeline_config.output_dir}\n")

    # 注册抓取器
    from .scrapers.registry import ScraperRegistry

    registry = ScraperRegistry()
    registered = _register_scrapers(registry, settings)

    if not registered:
        console.print("[red]未注册任何抓取器。请至少配置一个平台的 API Key（TikHub 或 Twitter）。[/red]")
        console.print("[dim]  TikHub: 设置 PPM_TIKHUB_API_KEY（小红书/微博/抖音/知乎）[/dim]")
        console.print("[dim]  Twitter: 设置 PPM_TWITTER_BEARER_TOKEN[/dim]")
        if not dry_run:
            sys.exit(1)

    # 检查请求的平台是否都有对应抓取器
    unregistered = [p for p in plat_list if p not in registered]
    if unregistered:
        for p in unregistered:
            console.print(f"[yellow]  ⚠ 平台 {p.value} 无可用抓取器（缺少 API Key），已跳过[/yellow]")
        plat_list = [p for p in plat_list if p in registered]
        if not plat_list:
            console.print("[red]所有请求的平台都无可用抓取器。[/red]")
            if not dry_run:
                sys.exit(1)

    if dry_run:
        # 检查 LLM
        if settings.analysis.llm_mode == "cli":
            from .llm import ClaudeCliProvider

            if not ClaudeCliProvider.is_available(settings.analysis.cli_command):
                console.print(
                    f"[red]  ✗ CLI '{settings.analysis.cli_command}' 不可用。\n"
                    f"    请确认已安装并认证。安装指南: https://docs.anthropic.com/en/docs/claude-code\n"
                    f"    如命令名不同，请在 config.yaml 中设置 cli_command[/red]"
                )
                sys.exit(1)
            console.print(f"[green]  ✓ CLI '{settings.analysis.cli_command}' 可用[/green]")
        elif settings.analysis.llm_mode == "api" and not settings.anthropic_api_key:
            console.print("[red]  ✗ API 模式需要 PPM_ANTHROPIC_API_KEY[/red]")
            sys.exit(1)
        else:
            console.print("[green]  ✓ LLM 配置有效[/green]")

        console.print(f"[green]  ✓ 已注册 {len(registered)} 个平台抓取器[/green]")
        console.print("[green]Dry run 完成，配置有效。[/green]")
        return

    # 更新 pipeline_config 中的平台列表（去掉无抓取器的）
    pipeline_config.platforms = plat_list

    asyncio.run(_run_pipeline(pipeline_config, settings, registry))


async def _run_pipeline(config: PipelineConfig, settings: Settings, registry):
    """异步执行完整流水线。"""
    from .analysis.clustering import PainPointClusterer
    from .analysis.dedup import PainPointDeduplicator
    from .analysis.extractor import PainPointExtractor
    from .analysis.pipeline import AnalysisPipeline
    from .compliance.anonymizer import Anonymizer
    from .exporters import ExcelExporter, JsonExporter, MarkdownExporter
    from .storage.migrations import run_migrations
    from .utils.cost import CostTracker

    console.print("[bold blue]正在初始化...[/bold blue]")

    db_path = Path("painpoint_miner.db")
    await run_migrations(db_path)

    anonymizer = Anonymizer(salt=settings.encryption_passphrase or "default-salt")
    cost_tracker = CostTracker(
        budget=config.max_llm_budget_usd,
        model=config.llm_model,
    )

    llm = _create_llm_provider(settings, cost_tracker)

    extractor = PainPointExtractor(llm=llm, batch_size=settings.analysis.batch_size, cost_tracker=cost_tracker)
    clusterer = PainPointClusterer(
        model_name=settings.analysis.embedding.model,
        min_cluster_size=settings.analysis.clustering.min_cluster_size,
    )
    deduplicator = PainPointDeduplicator(
        similarity_threshold=config.dedup_threshold,
    )

    pipeline = AnalysisPipeline(
        registry=registry,
        extractor=extractor,
        clusterer=clusterer,
        deduplicator=deduplicator,
        anonymizer=anonymizer,
        llm=llm,
        settings=settings,
        db_path=str(db_path),
    )

    console.print("[bold blue]正在执行流水线...[/bold blue]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("抓取和分析中...", total=None)
        report = await pipeline.run(config)

    # 导出
    output_dir = Path(config.output_dir)
    exporters = {
        "markdown": MarkdownExporter(),
        "json": JsonExporter(),
        "excel": ExcelExporter(),
    }

    for fmt_name in config.output_formats:
        exporter = exporters.get(fmt_name)
        if exporter:
            ext = {"markdown": ".md", "json": ".json", "excel": ".xlsx"}[fmt_name]
            output_path = output_dir / f"painpoint_report{ext}"
            await exporter.export(report, output_path)
            console.print(f"  [green]✓[/green] {fmt_name}: {output_path}")

    if cost_tracker:
        summary = cost_tracker.summary()
        console.print(f"\n[bold]LLM 成本:[/bold] ${summary.estimated_cost_usd:.4f}")

    console.print(f"\n[bold green]分析完成！发现 {len(report.pain_points)} 个痛点[/bold green]")


def main():
    """入口函数。"""
    cli()


if __name__ == "__main__":
    main()
