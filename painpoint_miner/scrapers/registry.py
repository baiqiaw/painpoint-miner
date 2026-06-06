"""抓取器注册表 — 工厂模式 + 健康检查优先级。"""

import logging
from typing import Optional

from ..models.enums import Platform
from .base import BaseScraper

logger = logging.getLogger("painpoint_miner")


class NoHealthyScraperError(Exception):
    """没有可用的抓取器。"""

    def __init__(self, platform: Platform):
        self.platform = platform
        super().__init__(f"No healthy scraper available for {platform.value}")


class ScraperRegistry:
    """抓取器注册表。

    每个平台维护一个有序的抓取器列表（按优先级排列）。
    get_scraper() 返回第一个通过健康检查的抓取器。

    用法:
        registry = ScraperRegistry()
        registry.register(Platform.XIAOHONGSHU, tikhub_scraper, priority=1)
        registry.register(Platform.XIAOHONGSHU, apify_scraper, priority=2)

        scraper = await registry.get_scraper(Platform.XIAOHONGSHU)
        # 返回 tikhub_scraper（如果健康），否则 apify_scraper
    """

    def __init__(self) -> None:
        self._scrapers: dict[Platform, list[BaseScraper]] = {}

    def register(
        self, platform: Platform, scraper: BaseScraper, priority: int = 0
    ) -> None:
        """注册抓取器。

        Args:
            platform: 目标平台
            scraper: 抓取器实例
            priority: 优先级（数字越小优先级越高）
        """
        if platform not in self._scrapers:
            self._scrapers[platform] = []
        # 插入排序保持优先级顺序
        scrapers = self._scrapers[platform]
        scraper._registry_priority = priority  # type: ignore[attr-defined]
        scrapers.append(scraper)
        scrapers.sort(key=lambda s: getattr(s, "_registry_priority", 999))
        logger.info(
            "Registered %s for %s (priority %d)",
            scraper.name,
            platform.value,
            priority,
        )

    async def get_scraper(self, platform: Platform) -> BaseScraper:
        """获取第一个健康的抓取器。

        Raises:
            NoHealthyScraperError: 没有可用的抓取器
        """
        scrapers = self._scrapers.get(platform, [])
        if not scrapers:
            raise NoHealthyScraperError(platform)

        for scraper in scrapers:
            try:
                if await scraper.health_check():
                    logger.info(
                        "Using %s for %s", scraper.name, platform.value
                    )
                    return scraper
            except Exception as e:
                logger.warning(
                    "Health check failed for %s: %s", scraper.name, e
                )

        raise NoHealthyScraperError(platform)

    def get_registered_platforms(self) -> list[Platform]:
        """返回所有已注册的平台。"""
        return list(self._scrapers.keys())

    def get_scrapers_for_platform(self, platform: Platform) -> list[BaseScraper]:
        """返回指定平台的所有抓取器。"""
        return list(self._scrapers.get(platform, []))
