"""API ToS 检查器单元测试。"""

import pytest

from painpoint_miner.compliance.api_tos import ApiTosChecker
from painpoint_miner.models.enums import Platform


class TestApiTosChecker:
    """ApiTosChecker 测试。"""

    @pytest.mark.asyncio
    async def test_tikhub_platform_with_key(self):
        """TikHub 平台 + API key 已配置 → allowed。"""
        checker = ApiTosChecker(tikhub_available=True)
        result = await checker.check_api_tos(Platform.XIAOHONGSHU)

        assert result["allowed"] is True
        assert result["provider"] == "TikHub"
        assert "第三方" in result["note"]

    @pytest.mark.asyncio
    async def test_tikhub_platform_without_key(self):
        """TikHub 平台 + 无 API key → not allowed。"""
        checker = ApiTosChecker(tikhub_available=False)
        result = await checker.check_api_tos(Platform.XIAOHONGSHU)

        assert result["allowed"] is False
        assert "未配置" in result["note"]

    @pytest.mark.asyncio
    async def test_all_tikhub_platforms(self):
        """所有 TikHub 平台都走 TikHub 通道。"""
        checker = ApiTosChecker(tikhub_available=True)
        for platform in [Platform.WEIBO, Platform.DOUYIN, Platform.ZHIHU]:
            result = await checker.check_api_tos(platform)
            assert result["allowed"] is True
            assert result["provider"] == "TikHub"

    @pytest.mark.asyncio
    async def test_twitter_api_v2(self):
        """Twitter API v2 模式。"""
        checker = ApiTosChecker(twitter_mode="api_v2")
        result = await checker.check_api_tos(Platform.TWITTER)

        assert result["allowed"] is True
        assert result["provider"] == "Twitter API v2"
        assert "官方" in result["note"]

    @pytest.mark.asyncio
    async def test_twitter_twscrape_mode(self):
        """Twitter twscrape 模式 → 高风险标记。"""
        checker = ApiTosChecker(twitter_mode="twscrape")
        result = await checker.check_api_tos(Platform.TWITTER)

        assert result["allowed"] is True
        assert result["provider"] == "twscrape"
        assert result["risk"] == "high"
        assert "HIGH RISK" in result["note"]

    @pytest.mark.asyncio
    async def test_robots_txt_known_platform(self):
        """已知平台的 robots.txt URL 存在。"""
        checker = ApiTosChecker()
        result = await checker.check_robots_txt(Platform.XIAOHONGSHU)

        assert result["allowed"] is True
        assert "xiaohongshu.com" in result["source"]

    @pytest.mark.asyncio
    async def test_robots_txt_all_platforms(self):
        """所有平台都有 robots.txt URL。"""
        checker = ApiTosChecker()
        for platform in Platform:
            result = await checker.check_robots_txt(platform)
            assert "source" in result
            assert "details" in result

    def test_robots_urls_cover_all_platforms(self):
        """ROBOTS_URLS 覆盖所有平台。"""
        assert set(ApiTosChecker.ROBOTS_URLS.keys()) == set(Platform)

    def test_api_providers_structure(self):
        """API_PROVIDERS 结构正确。"""
        for key, info in ApiTosChecker.API_PROVIDERS.items():
            assert "name" in info
            assert "note" in info
            assert "required_env" in info
