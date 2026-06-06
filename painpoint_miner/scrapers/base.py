"""抓取器抽象基类。"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Self

from ..models.base import RawComment, RawPost
from ..models.enums import Platform


class BaseScraper(ABC):
    """所有平台抓取器的抽象基类。

    使用 async context manager 管理资源生命周期。
    每个平台可有多个实现（API / Playwright），由 Registry 按健康检查优先级选择。
    """

    async def __aenter__(self) -> Self:
        await self._initialize()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._cleanup()

    @abstractmethod
    async def search_posts(
        self, keywords: list[str], limit: int
    ) -> AsyncGenerator[RawPost, None]:
        """搜索匹配关键词的帖子。"""

    @abstractmethod
    async def get_comments(
        self, post: RawPost, limit: int
    ) -> AsyncGenerator[RawComment, None]:
        """获取指定帖子的评论。"""

    @abstractmethod
    async def health_check(self) -> bool:
        """验证抓取器是否可用（API 连通性、凭证有效性等）。"""

    @property
    @abstractmethod
    def platform(self) -> Platform:
        """返回目标平台。"""

    @property
    def name(self) -> str:
        """抓取器名称（用于日志和 Registry 识别）。"""
        return f"{self.__class__.__name__}"

    async def _initialize(self) -> None:
        """初始化连接。子类可覆盖。"""

    async def _cleanup(self) -> None:
        """释放资源。子类可覆盖。"""
