"""LLM 批量痛点提取器（支持 merged/split 双模式）。"""

import logging
from typing import Optional

from ..models.base import PainPoint, RawPost
from ..models.enums import PainType, Sentiment, Severity
from ..utils.cost import CostTracker
from ..llm.base import BaseLLMProvider

logger = logging.getLogger("painpoint_miner")


class PainPointExtractor:
    """痛点提取器。

    merged 模式：一次 LLM 调用同时返回痛点+情感（默认，省成本）
    split 模式：分两次调用，先用基础模型提取痛点，再用强模型分析情感
    """

    def __init__(
        self,
        llm: BaseLLMProvider,
        batch_size: int = 15,
        cost_tracker: Optional[CostTracker] = None,
    ):
        self._llm = llm
        self._batch_size = batch_size
        self._cost_tracker = cost_tracker
        self._id_counter = 0

    def _next_id(self) -> str:
        self._id_counter += 1
        return f"pp_{self._id_counter:04d}"

    async def extract(
        self,
        posts: list[RawPost],
        mode: str = "merged",
    ) -> list[PainPoint]:
        """批量提取痛点。

        Args:
            posts: 已匿名化的帖子列表
            mode: "merged" 或 "split"

        Returns:
            提取到的痛点列表
        """
        if not posts:
            return []

        all_pain_points: list[PainPoint] = []

        # 分批处理
        for i in range(0, len(posts), self._batch_size):
            batch = posts[i : i + self._batch_size]

            # 预算检查
            if self._cost_tracker:
                self._cost_tracker.check_and_raise()

            # 转为 dict 格式供 LLM
            posts_dicts = [
                {
                    "platform": p.platform.value,
                    "content": p.content,
                    "title": p.title,
                    "likes": p.likes,
                    "comments_count": p.comments_count,
                }
                for p in batch
            ]

            try:
                results = await self._llm.extract_pain_points(
                    posts_dicts, mode=mode
                )
            except Exception as e:
                logger.error("Pain point extraction failed: %s", e)
                continue

            # 解析结果
            for result in results:
                if not result.get("has_pain_point", False):
                    continue

                for pp_data in result.get("pain_points", []):
                    try:
                        pain_point = PainPoint(
                            id=self._next_id(),
                            source_post_ids=[
                                batch[result["post_index"]].post_id
                                if result.get("post_index", 0) < len(batch)
                                else ""
                            ],
                            platforms=[
                                batch[result["post_index"]].platform
                                if result.get("post_index", 0) < len(batch)
                                else posts[0].platform
                            ],
                            description=pp_data.get("description", ""),
                            pain_type=PainType(pp_data.get("pain_type", "other")),
                            severity=Severity(pp_data.get("severity", 3)),
                            sentiment_score=max(
                                -1.0, min(1.0, pp_data.get("sentiment_score", 0.0))
                            ),
                            sentiment_label=Sentiment(
                                pp_data.get("sentiment_label", "neutral")
                            ),
                            evidence_quotes=[
                                pp_data.get("evidence_quote", "")
                            ],
                            frequency=1,
                        )
                        all_pain_points.append(pain_point)
                    except Exception as e:
                        logger.warning("Failed to parse pain point: %s", e)
                        continue

        logger.info("Extracted %d pain points from %d posts", len(all_pain_points), len(posts))
        return all_pain_points
