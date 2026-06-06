"""抽象 LLM Provider 接口。"""

from abc import ABC, abstractmethod


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
    async def extract_sentiment(self, descriptions: list[str]) -> list[dict]:
        """独立情感分析（split 模式使用）。

        Args:
            descriptions: 痛点描述列表

        Returns:
            情感分析结果列表（含 sentiment_score, sentiment_label）
        """

    @abstractmethod
    async def generate_cluster_label(
        self, cluster_descriptions: list[str]
    ) -> str:
        """为聚类生成主题标签。"""

    @classmethod
    def is_available(cls) -> bool:
        """检查此 Provider 是否可用（默认 True）。"""
        return True
