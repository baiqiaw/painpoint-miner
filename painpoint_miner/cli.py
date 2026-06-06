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
def run(
    config: Optional[str],
    keywords: tuple,
    platforms: tuple,
    mode: str,
    accept_tos_risk: bool,
    dry_run: bool,
    output: Optional[str],
):
    """执行痛点抓取与分析流水线。"""
    # Windows asyncio 兼容
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    show_disclaimer()

    if not accept_tos_risk:
        console.print("[red]请使用 --accept-tos-risk 标志确认您已了解法律风险[/red]")
        sys.exit(1)

    config_path = Path(config) if config else None
    settings = _get_or_create_settings(config_path)

    # 构建 PipelineConfig
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
    console.print(f"  输出: {pipeline_config.output_dir}\n")

    if dry_run:
        console.print("[green]Dry run 完成，配置有效。[/green]")
        return

    # 执行流水线
    asyncio.run(_run_pipeline(pipeline_config, settings))


async def _run_pipeline(config: PipelineConfig, settings: Settings):
    """异步执行完整流水线。"""
    from .analysis.clustering import PainPointClusterer
    from .analysis.dedup import PainPointDeduplicator
    from .analysis.extractor import PainPointExtractor
    from .analysis.pipeline import AnalysisPipeline
    from .compliance.anonymizer import Anonymizer
    from .exporters import ExcelExporter, JsonExporter, MarkdownExporter
    from .llm import MockLLMProvider
    from .scrapers.registry import ScraperRegistry
    from .storage.migrations import run_migrations
    from .utils.cost import CostTracker

    console.print("[bold blue]正在初始化...[/bold blue]")

    # 初始化组件
    registry = ScraperRegistry()
    # 注意：实际使用时需要注册真实抓取器（带 API key）
    # 这里用 Mock 提供基础框架

    db_path = Path("painpoint_miner.db")
    await run_migrations(db_path)

    anonymizer = Anonymizer(salt=settings.encryption_passphrase or "default-salt")
    cost_tracker = CostTracker(
        budget=config.max_llm_budget_usd,
        model=config.llm_model,
    )
    llm = MockLLMProvider()  # 实际使用替换为 ClaudeProvider
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

    # 成本报告
    if cost_tracker:
        summary = cost_tracker.summary()
        console.print(f"\n[bold]LLM 成本:[/bold] ${summary.estimated_cost_usd:.4f}")

    console.print(f"\n[bold green]分析完成！发现 {len(report.pain_points)} 个痛点[/bold green]")


def main():
    """入口函数。"""
    cli()


if __name__ == "__main__":
    main()
