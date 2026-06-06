"""TikHub 各平台抓取器的共享基类。"""

import logging
from datetime import datetime
from typing import AsyncGenerator, Optional

from ...models.base import RawComment, RawPost
from ...models.enums import Platform
from ..base import BaseScraper
from .client import TikHubClient

logger = logging.getLogger("painpoint_miner")


class TikHubBaseScraper(BaseScraper):
    """TikHub 抓取器基类。

    子类只需实现 _get_search_path()、_map_to_post() 和 _map_to_comment()。
    """

    def __init__(self, client: TikHubClient, platform_val: Platform):
        self._client = client
        self._platform = platform_val

    @property
    def platform(self) -> Platform:
        return self._platform

    async def _initialize(self) -> None:
        pass

    async def _cleanup(self) -> None:
        pass

    async def health_check(self) -> bool:
        return await self._client.health_check()

    def _get_search_path(self) -> str:
        """返回搜索 API 路径。子类必须实现。"""
        raise NotImplementedError

    def _get_comments_path(self, post_id: str) -> str:
        """返回评论 API 路径。子类必须实现。"""
        raise NotImplementedError

    def _map_to_post(self, item: dict) -> RawPost:
        """将 TikHub 响应项映射为 RawPost。子类必须实现。"""
        raise NotImplementedError

    def _map_to_comment(self, item: dict, post_id: str) -> RawComment:
        """将 TikHub 评论项映射为 RawComment。子类必须实现。"""
        raise NotImplementedError

    async def search_posts(
        self, keywords: list[str], limit: int
    ) -> AsyncGenerator[RawPost, None]:
        """搜索帖子。"""
        query = " ".join(keywords)
        offset = 0
        count = 0

        while count < limit:
            params = {
                "keyword": query,
                "offset": offset,
                "count": min(20, limit - count),
            }
            try:
                data = await self._client.get(
                    self._get_search_path(), params=params
                )
            except Exception as e:
                logger.error("Search failed for %s: %s", self._platform.value, e)
                return

            items = data.get("data", [])
            if not items:
                break

            for item in items:
                try:
                    post = self._map_to_post(item)
                    yield post
                    count += 1
                except Exception as e:
                    logger.warning("Failed to map post: %s", e)
                    continue

            if not data.get("has_more", False):
                break
            offset = data.get("cursor", offset + len(items))

    async def get_comments(
        self, post: RawPost, limit: int
    ) -> AsyncGenerator[RawComment, None]:
        """获取评论。"""
        offset = 0
        count = 0

        while count < limit:
            params = {
                "offset": offset,
                "count": min(20, limit - count),
            }
            try:
                data = await self._client.get(
                    self._get_comments_path(post.post_id), params=params
                )
            except Exception as e:
                logger.error(
                    "Comments failed for %s/%s: %s",
                    self._platform.value,
                    post.post_id,
                    e,
                )
                return

            items = data.get("comments", data.get("data", []))
            if not items:
                break

            for item in items:
                try:
                    comment = self._map_to_comment(item, post.post_id)
                    yield comment
                    count += 1
                except Exception as e:
                    logger.warning("Failed to map comment: %s", e)
                    continue

            if not data.get("has_more", False):
                break
            offset = data.get("cursor", offset + len(items))
