"""抓取框架单元测试。"""

import pytest
from typing import AsyncGenerator
from unittest.mock import AsyncMock

from painpoint_miner.models.base import RawComment, RawPost
from painpoint_miner.models.enums import Platform
from painpoint_miner.scrapers.base import BaseScraper
from painpoint_miner.scrapers.registry import NoHealthyScraperError, ScraperRegistry


class MockScraper(BaseScraper):
    """用于测试的 mock 抓取器。"""

    def __init__(
        self,
        platform_val: Platform,
        healthy: bool = True,
        name: str = "MockScraper",
    ):
        self._platform = platform_val
        self._healthy = healthy
        self._name = name
        self._initialized = False
        self._cleaned_up = False

    @property
    def platform(self) -> Platform:
        return self._platform

    @property
    def name(self) -> str:
        return self._name

    async def search_posts(
        self, keywords: list[str], limit: int
    ) -> AsyncGenerator[RawPost, None]:
        yield RawPost(
            platform=self._platform,
            post_id="mock_001",
            author_id="mock_user",
            content=f"mock content for {keywords}",
        )

    async def get_comments(
        self, post: RawPost, limit: int
    ) -> AsyncGenerator[RawComment, None]:
        yield RawComment(
            platform=self._platform,
            comment_id="mock_cmt_001",
            post_id=post.post_id,
            author_id="mock_user",
            content="mock comment",
        )

    async def health_check(self) -> bool:
        return self._healthy

    async def _initialize(self) -> None:
        self._initialized = True

    async def _cleanup(self) -> None:
        self._cleaned_up = True


class TestBaseScraper:
    """BaseScraper 抽象基类测试。"""

    @pytest.mark.asyncio
    async def test_context_manager_lifecycle(self):
        scraper = MockScraper(Platform.XIAOHONGSHU)
        assert not scraper._initialized
        assert not scraper._cleaned_up

        async with scraper:
            assert scraper._initialized
            assert not scraper._cleaned_up

        assert scraper._cleaned_up

    @pytest.mark.asyncio
    async def test_search_posts_yields(self):
        scraper = MockScraper(Platform.WEIBO)
        posts = []
        async for post in scraper.search_posts(["测试"], limit=10):
            posts.append(post)
        assert len(posts) == 1
        assert posts[0].platform == Platform.WEIBO

    @pytest.mark.asyncio
    async def test_get_comments_yields(self):
        scraper = MockScraper(Platform.WEIBO)
        post = RawPost(
            platform=Platform.WEIBO,
            post_id="wb_001",
            author_id="h1",
            content="test",
        )
        comments = []
        async for comment in scraper.get_comments(post, limit=10):
            comments.append(comment)
        assert len(comments) == 1
        assert comments[0].post_id == "wb_001"


class TestScraperRegistry:
    """ScraperRegistry 测试。"""

    def test_register_platform(self):
        registry = ScraperRegistry()
        scraper = MockScraper(Platform.XIAOHONGSHU)
        registry.register(Platform.XIAOHONGSHU, scraper, priority=1)
        assert Platform.XIAOHONGSHU in registry.get_registered_platforms()

    @pytest.mark.asyncio
    async def test_get_healthy_scraper(self):
        registry = ScraperRegistry()
        scraper = MockScraper(Platform.XIAOHONGSHU, healthy=True)
        registry.register(Platform.XIAOHONGSHU, scraper)
        result = await registry.get_scraper(Platform.XIAOHONGSHU)
        assert result is scraper

    @pytest.mark.asyncio
    async def test_fallback_to_healthy(self):
        """优先使用高优先级，失败时回退。"""
        registry = ScraperRegistry()
        unhealthy = MockScraper(
            Platform.XIAOHONGSHU, healthy=False, name="UnhealthyScraper"
        )
        healthy = MockScraper(
            Platform.XIAOHONGSHU, healthy=True, name="HealthyScraper"
        )
        registry.register(Platform.XIAOHONGSHU, unhealthy, priority=1)
        registry.register(Platform.XIAOHONGSHU, healthy, priority=2)
        result = await registry.get_scraper(Platform.XIAOHONGSHU)
        assert result.name == "HealthyScraper"

    @pytest.mark.asyncio
    async def test_no_scraper_raises(self):
        registry = ScraperRegistry()
        with pytest.raises(NoHealthyScraperError) as exc_info:
            await registry.get_scraper(Platform.ZHIHU)
        assert exc_info.value.platform == Platform.ZHIHU

    @pytest.mark.asyncio
    async def test_all_unhealthy_raises(self):
        registry = ScraperRegistry()
        registry.register(
            Platform.DOUYIN,
            MockScraper(Platform.DOUYIN, healthy=False),
        )
        with pytest.raises(NoHealthyScraperError):
            await registry.get_scraper(Platform.DOUYIN)

    def test_get_scrapers_for_platform(self):
        registry = ScraperRegistry()
        s1 = MockScraper(Platform.WEIBO, name="S1")
        s2 = MockScraper(Platform.WEIBO, name="S2")
        registry.register(Platform.WEIBO, s1, priority=1)
        registry.register(Platform.WEIBO, s2, priority=2)
        scrapers = registry.get_scrapers_for_platform(Platform.WEIBO)
        assert len(scrapers) == 2
        assert scrapers[0].name == "S1"
        assert scrapers[1].name == "S2"

    def test_empty_platform_returns_empty_list(self):
        registry = ScraperRegistry()
        assert registry.get_scrapers_for_platform(Platform.TWITTER) == []
