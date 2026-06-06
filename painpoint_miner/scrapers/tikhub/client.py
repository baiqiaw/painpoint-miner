"""TikHub API HTTP 客户端封装。"""

import logging
from typing import Any, Optional

import httpx

from ...config.settings import Settings
from ...utils.rate_limiter import RateLimiter

logger = logging.getLogger("painpoint_miner")

TIKHUB_BASE_URL = "https://api.tikhub.io"


class TikHubClientError(Exception):
    """TikHub API 调用错误。"""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"TikHub API error {status_code}: {message}")


class TikHubClient:
    """TikHub API 客户端。

    封装 HTTP 请求、认证、速率限制和错误处理。
    全局速率限制独立于 per-platform 限制。
    """

    def __init__(
        self,
        api_key: str,
        rate_limiter: Optional[RateLimiter] = None,
        base_url: str = TIKHUB_BASE_URL,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._rate_limiter = rate_limiter or RateLimiter(
            requests_per_minute=60, burst=10
        )
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "PainPointMiner/1.0",
            },
            timeout=30.0,
        )

    async def __aenter__(self) -> "TikHubClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict:
        """发送 API 请求（经过速率限制）。

        Args:
            method: HTTP 方法
            path: API 路径（相对于 base_url）
            params: 查询参数

        Returns:
            API 响应 JSON

        Raises:
            TikHubClientError: API 返回错误状态码
        """
        await self._rate_limiter.acquire()

        response = await self._client.request(
            method, path, params=params
        )

        if response.status_code == 429:
            logger.warning("TikHub rate limit hit, backing off")
            raise TikHubClientError(429, "Rate limit exceeded")

        if response.status_code >= 400:
            raise TikHubClientError(
                response.status_code, response.text[:500]
            )

        return response.json()

    async def get(self, path: str, params: Optional[dict] = None) -> dict:
        """GET 请求快捷方式。"""
        return await self.request("GET", path, params=params)

    async def health_check(self) -> bool:
        """检查 API 连通性和密钥有效性。"""
        if not self._api_key:
            return False
        try:
            # 用一个轻量级请求验证密钥
            response = await self._client.get(
                "/api/v1/user/info",
            )
            return response.status_code == 200
        except Exception:
            return False
