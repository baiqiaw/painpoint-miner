"""抽象 LLM Provider 接口。"""

from abc import ABC, abstractmethod
from typing import Any


class BaseLLMProvider(ABC):
    """LLM 提供者抽象基类。"""

    @abstractmethod
    async def extract_pain_points(
        self,
        posts: list[dict],
        mode: str = "merged",
    ) -> list[dict]:
        """从帖子中提取痛点和情感。

        Args:
            posts: 帖子列表（dict 格式，含 content, platform 等字段）
            mode: "merged"（痛点+情感一次调用）或 "split"（分两次调用）

        Returns:
            痛点列表（dict 格式，含 description, pain_type, severity, sentiment 等）
        """

    @abstractmethod
    async def generate_cluster_label(
        self, cluster_descriptions: list[str]
    ) -> str:
        """为聚类生成主题标签。"""
