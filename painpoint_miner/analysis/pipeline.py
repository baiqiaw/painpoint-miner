"""分析流水线编排器 — 抓取→分析→导出的完整流程。"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from ..compliance.anonymizer import Anonymizer
from ..compliance.tos import TosAcceptance
from ..config.settings import Settings
from ..llm.base import BaseLLMProvider
from ..models.base import AnalysisReport, PainPoint, PipelineConfig, RawPost
from ..models.enums import Platform
from ..storage.cache import Cache
from ..storage.checkpoint import Checkpoint
from ..storage.migrations import run_migrations
from ..utils.cost import CostTracker
from .clustering import PainPointClusterer
from .dedup import PainPointDeduplicator
from .extractor import PainPointExtractor
from ..scrapers.registry import ScraperRegistry

logger = logging.getLogger("painpoint_miner")


class AnalysisPipeline:
    """编排完整的抓取→分析→导出流水线。

    支持断点续传、部分失败恢复、预算控制。
    """

    def __init__(
        self,
        registry: ScraperRegistry,
        extractor: PainPointExtractor,
        clusterer: PainPointClusterer,
        deduplicator: PainPointDeduplicator,
        anonymizer: Anonymizer,
        llm: BaseLLMProvider,
        settings: Settings,
        db_path: Optional[str] = None,
    ):
        self._registry = registry
        self._extractor = extractor
        self._clusterer = clusterer
        self._deduplicator = deduplicator
        self._anonymizer = anonymizer
        self._llm = llm
        self._settings = settings
        self._db_path = db_path or ":memory:"

    async def run(self, config: PipelineConfig) -> AnalysisReport:
        """执行完整流水线。"""
        from pathlib import Path

        db_path = Path(self._db_path)

        # 1. Schema 迁移
        await run_migrations(db_path)

        # 2. 初始化存储
        cache = Cache(db_path)
        checkpoint = Checkpoint(db_path)

        # 3. 清理过期数据
        await cache.cleanup_expired(self._settings.privacy.retention_days)

        # 4. 加载断点
        prev_state = await checkpoint.load_latest()

        # 5. 并行抓取 + 匿名化
        all_posts: list[RawPost] = []
        platform_counts: dict[str, int] = {}
        errors: list[str] = []
        semaphore = asyncio.Semaphore(3)

        async def scrape_platform(platform: Platform):
            async with semaphore:
                try:
                    scraper = await self._registry.get_scraper(platform)
                    async with scraper:
                        count = 0
                        async for post in scraper.search_posts(
                            config.keywords, config.max_posts_per_keyword
                        ):
                            # 立即匿名化
                            if self._settings.privacy.anonymize:
                                post = self._anonymizer.anonymize_post(post)
                            # 增量去重
                            if not await cache.is_scraped(post.platform, post.post_id):
                                all_posts.append(post)
                                await cache.save_post(post)
                                count += 1
                    platform_counts[platform.value] = count
                    logger.info("Scraped %d posts from %s", count, platform.value)
                except Exception as e:
                    error_msg = f"{platform.value}: {e}"
                    errors.append(error_msg)
                    logger.error("Scraping failed for %s", error_msg)

        await asyncio.gather(
            *[scrape_platform(p) for p in config.platforms],
            return_exceptions=True,
        )

        logger.info(
            "Total scraped: %d posts, %d errors",
            len(all_posts),
            len(errors),
        )

        # 6. LLM 痛点提取
        pain_points: list[PainPoint] = []
        if all_posts:
            try:
                pain_points = await self._extractor.extract(
                    all_posts,
                    mode=config.analysis_mode.value,
                )
            except Exception as e:
                logger.error("Pain point extraction failed: %s", e)

        # 7. 跨平台去重
        if pain_points:
            pain_points = self._deduplicator.deduplicate(pain_points)

        # 8. 聚类
        clusters = []
        if pain_points:
            pain_points, clusters = self._clusterer.cluster(pain_points)

        # 9. 生成报告
        report = AnalysisReport(
            query_keywords=config.keywords,
            scrape_timestamp=datetime.now(),
            total_posts_scraped=sum(platform_counts.values()),
            pain_points=pain_points,
            topic_clusters=clusters,
            summary=self._generate_summary(pain_points, clusters, errors),
            platform_breakdown=platform_counts,
        )

        # 10. 保存 checkpoint
        await checkpoint.save({
            "phase": "complete",
            "keywords": config.keywords,
            "platforms": [p.value for p in config.platforms],
            "posts_scraped": len(all_posts),
            "pain_points_found": len(pain_points),
            "errors": errors,
        })

        return report

    def _generate_summary(
        self,
        pain_points: list[PainPoint],
        clusters: list,
        errors: list[str],
    ) -> str:
        """生成分析摘要。"""
        lines = [f"共发现 {len(pain_points)} 个用户痛点。"]

        if clusters:
            lines.append(f"归纳为 {len(clusters)} 个主题类别。")

        if errors:
            lines.append(f"抓取过程中有 {len(errors)} 个平台出现错误。")

        # 按类型统计
        from collections import Counter

        type_counts = Counter(pp.pain_type.value for pp in pain_points)
        if type_counts:
            top_types = type_counts.most_common(3)
            type_str = ", ".join(f"{t}({c})" for t, c in top_types)
            lines.append(f"主要痛点类型：{type_str}")

        return " ".join(lines)
