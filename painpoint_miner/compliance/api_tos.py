"""API 服务 ToS 验证器。

区分两种访问模式：
- API 服务（TikHub、Twitter API）：检查 API 提供商的 ToS
- 直接 HTTP 访问（Playwright）：检查目标平台的 robots.txt
"""

from typing import Optional

from ..models.enums import Platform


class ApiTosChecker:
    """API 服务条款和 robots.txt 检查器。"""

    # 各平台 robots.txt URL（仅 Playwright 直接访问时使用）
    ROBOTS_URLS: dict[Platform, str] = {
        Platform.TWITTER: "https://x.com/robots.txt",
        Platform.XIAOHONGSHU: "https://www.xiaohongshu.com/robots.txt",
        Platform.WEIBO: "https://weibo.com/robots.txt",
        Platform.DOUYIN: "https://www.douyin.com/robots.txt",
        Platform.ZHIHU: "https://www.zhihu.com/robots.txt",
    }

    # 各 API 提供商的 ToS 摘要
    API_PROVIDERS = {
        "tikhub": {
            "name": "TikHub",
            "note": "第三方数据中介，授权状态需用户自行验证",
            "required_env": "PPM_TIKHUB_API_KEY",
        },
        "twitter_api": {
            "name": "Twitter API v2",
            "note": "官方付费 API，需开发者账号",
            "required_env": "PPM_TWITTER_BEARER_TOKEN",
        },
        "twscrape": {
            "name": "twscrape",
            "note": "⚠️ HIGH RISK: 违反 X/Twitter ToS，需 --accept-tos-risk",
            "required_env": "PPM_TWITTER_ACCOUNTS",
        },
    }

    def __init__(self, tikhub_available: bool = False, twitter_mode: str = "api_v2"):
        self._tikhub_available = tikhub_available
        self._twitter_mode = twitter_mode

    async def check_api_tos(self, platform: Platform) -> dict:
        """检查 API 访问的合规状态。

        Returns:
            dict with keys: allowed (bool), provider (str), note (str)
        """
        tikhub_platforms = {
            Platform.XIAOHONGSHU,
            Platform.WEIBO,
            Platform.DOUYIN,
            Platform.ZHIHU,
        }

        if platform in tikhub_platforms:
            if self._tikhub_available:
                provider_info = self.API_PROVIDERS["tikhub"]
                return {
                    "allowed": True,
                    "provider": provider_info["name"],
                    "note": provider_info["note"],
                }
            return {
                "allowed": False,
                "provider": "TikHub",
                "note": "TikHub API key 未配置",
            }

        if platform == Platform.TWITTER:
            mode = self._twitter_mode
            if mode == "twscrape":
                provider_info = self.API_PROVIDERS["twscrape"]
                return {
                    "allowed": True,
                    "provider": provider_info["name"],
                    "note": provider_info["note"],
                    "risk": "high",
                }
            provider_info = self.API_PROVIDERS["twitter_api"]
            return {
                "allowed": True,
                "provider": provider_info["name"],
                "note": provider_info["note"],
            }

        return {
            "allowed": False,
            "provider": "unknown",
            "note": f"不支持的平台: {platform}",
        }

    async def check_robots_txt(
        self, platform: Platform, path: str = "/"
    ) -> dict:
        """检查 robots.txt（仅用于 Playwright 直接访问模式）。

        Returns:
            dict with keys: allowed (bool), source (str), details (str)
        """
        url = self.ROBOTS_URLS.get(platform)
        if not url:
            return {
                "allowed": False,
                "source": "robots.txt",
                "details": f"未找到 {platform} 的 robots.txt URL",
            }
        # 实际实现需要 HTTP 获取并解析 robots.txt
        # 此处返回基础结构，具体解析在集成时实现
        return {
            "allowed": True,
            "source": url,
            "details": "robots.txt 检查需要 HTTP 客户端，运行时实现",
        }
