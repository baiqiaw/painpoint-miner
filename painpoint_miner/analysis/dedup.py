"""跨平台去重（相似度 > 阈值的合并）。"""

import logging

import numpy as np
from fastembed import TextEmbedding
from sklearn.metrics.pairwise import cosine_similarity

from ..models.base import PainPoint

logger = logging.getLogger("painpoint_miner")


class PainPointDeduplicator:
    """跨平台痛点去重器。

    使用嵌入向量的余弦相似度合并描述相似的痛点。
    """

    def __init__(
        self,
        similarity_threshold: float = 0.9,
        model_name: str = "intfloat/multilingual-e5-large",
    ):
        self._threshold = similarity_threshold
        self._model_name = model_name
        self._embedding_model = None

    def _get_model(self):
        if self._embedding_model is None:
            self._embedding_model = TextEmbedding(self._model_name)
        return self._embedding_model

    def deduplicate(self, pain_points: list[PainPoint]) -> list[PainPoint]:
        """去重痛点。

        相似度超过阈值的痛点合并为一个（保留第一个，累加 frequency）。

        Returns:
            去重后的痛点列表
        """
        if len(pain_points) <= 1:
            return pain_points

        descriptions = [pp.description for pp in pain_points]
        model = self._get_model()
        embeddings = np.array(list(model.embed(descriptions)))

        # 计算相似度矩阵
        sim_matrix = cosine_similarity(embeddings)

        # 贪心合并
        merged: set[int] = set()
        result: list[PainPoint] = []

        for i in range(len(pain_points)):
            if i in merged:
                continue

            current = pain_points[i]
            merge_targets = [i]

            for j in range(i + 1, len(pain_points)):
                if j in merged:
                    continue
                if sim_matrix[i][j] >= self._threshold:
                    merge_targets.append(j)
                    merged.add(j)

            if len(merge_targets) > 1:
                # 合并：累加频率，合并平台和来源
                all_platforms = set()
                all_source_ids = []
                total_freq = 0
                for idx in merge_targets:
                    all_platforms.update(pain_points[idx].platforms)
                    all_source_ids.extend(pain_points[idx].source_post_ids)
                    total_freq += pain_points[idx].frequency

                current = current.model_copy(
                    update={
                        "platforms": list(all_platforms),
                        "source_post_ids": list(set(all_source_ids)),
                        "frequency": total_freq,
                    }
                )

            result.append(current)

        removed = len(pain_points) - len(result)
        if removed > 0:
            logger.info("Deduplicated: %d → %d pain points", len(pain_points), len(result))

        return result
