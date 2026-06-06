"""Claude API LLM Provider。"""

import json
import logging
import re
from typing import Optional

import anthropic

from ..utils.cost import CostTracker
from .base import BaseLLMProvider
from .prompt_templates import (
    CLUSTER_LABEL_PROMPT,
    MERGED_EXTRACTION_PROMPT,
    SPLIT_EXTRACTION_PROMPT,
    SPLIT_SENTIMENT_PROMPT,
    format_items_block,
    format_posts_block,
)

logger = logging.getLogger("painpoint_miner")


class ClaudeProvider(BaseLLMProvider):
    """Claude API 提供者。

    支持 merged 和 split 两种分析模式。
    集成 CostTracker 进行预算控制。
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-haiku-4-5-20251001",
        cost_tracker: Optional[CostTracker] = None,
    ):
        self._api_key = api_key
        self._model = model
        self._cost_tracker = cost_tracker
        self._client: Optional[anthropic.AsyncAnthropic] = None

    async def _get_client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def _call_claude(self, system: str, user: str) -> str:
        """调用 Claude API 并追踪成本。"""
        client = await self._get_client()

        response = await client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )

        # 追踪成本
        if self._cost_tracker:
            self._cost_tracker.track(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                model=self._model,
            )

        # 提取文本内容
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text

        return text

    @staticmethod
    def _parse_json_response(text: str) -> list[dict]:
        """从 Claude 响应中解析 JSON。"""
        # 尝试直接解析
        text = text.strip()
        # 移除 markdown 代码块标记
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
            text = text.strip()

        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
            return [result]
        except json.JSONDecodeError:
            # 尝试提取 JSON 数组
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            logger.warning("Failed to parse LLM JSON response")
            return []

    async def extract_pain_points(
        self,
        posts: list[dict],
        mode: str = "merged",
    ) -> list[dict]:
        """提取痛点和情感。"""
        posts_block = format_posts_block(posts)

        if mode == "merged":
            system = "你是专业的用户反馈分析师。只返回 JSON 格式的分析结果。"
            user = MERGED_EXTRACTION_PROMPT.format(posts_block=posts_block)
        else:
            system = "你是专业的用户反馈分析师。只返回 JSON 格式的分析结果。"
            user = SPLIT_EXTRACTION_PROMPT.format(posts_block=posts_block)

        response_text = await self._call_claude(system, user)
        return self._parse_json_response(response_text)

    async def extract_sentiment(self, descriptions: list[str]) -> list[dict]:
        """独立情感分析（split 模式使用）。"""
        items_block = format_items_block(descriptions)
        system = "你是情感分析专家。只返回 JSON 格式结果。"
        user = SPLIT_SENTIMENT_PROMPT.format(items_block=items_block)

        response_text = await self._call_claude(system, user)
        return self._parse_json_response(response_text)

    async def generate_cluster_label(
        self, cluster_descriptions: list[str]
    ) -> str:
        """为聚类生成主题标签。"""
        descriptions = "\n".join(f"- {d}" for d in cluster_descriptions[:20])
        system = "你是一个简洁的主题标签生成器。只返回标签文本。"
        user = CLUSTER_LABEL_PROMPT.format(descriptions=descriptions)

        return await self._call_claude(system, user)


class MockLLMProvider(BaseLLMProvider):
    """用于测试的 Mock LLM Provider。"""

    def __init__(self, pain_points: Optional[list[dict]] = None):
        self._pain_points = pain_points or [
            {
                "post_index": 0,
                "has_pain_point": True,
                "pain_points": [
                    {
                        "description": "按钮位置不明显，难以找到功能入口",
                        "pain_type": "ux_problem",
                        "severity": 3,
                        "sentiment_score": -0.6,
                        "sentiment_label": "negative",
                        "evidence_quote": "太难用了",
                    }
                ],
            }
        ]

    async def extract_pain_points(
        self, posts: list[dict], mode: str = "merged"
    ) -> list[dict]:
        return self._pain_points[: len(posts)]

    async def generate_cluster_label(
        self, cluster_descriptions: list[str]
    ) -> str:
        return "UI/UX 问题"
