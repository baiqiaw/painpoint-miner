"""聚类 — fastembed 嵌入 + sklearn HDBSCAN。"""

import logging
from typing import Optional

import numpy as np
from fastembed import TextEmbedding
from sklearn.cluster import HDBSCAN

from ..models.base import PainPoint, TopicCluster

logger = logging.getLogger("painpoint_miner")


class PainPointClusterer:
    """痛点聚类器。

    使用 fastembed 多语言嵌入 + sklearn HDBSCAN 自动发现主题簇。
    """

    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-large",
        min_cluster_size: int = 3,
    ):
        self._model_name = model_name
        self._min_cluster_size = min_cluster_size
        self._embedding_model: Optional[TextEmbedding] = None

    def _get_model(self) -> TextEmbedding:
        """懒加载嵌入模型。"""
        if self._embedding_model is None:
            logger.info("Loading embedding model: %s", self._model_name)
            self._embedding_model = TextEmbedding(self._model_name)
        return self._embedding_model

    def _generate_embeddings(self, texts: list[str]) -> np.ndarray:
        """生成文本嵌入向量。"""
        model = self._get_model()
        embeddings = list(model.embed(texts))
        return np.array(embeddings)

    def cluster(
        self, pain_points: list[PainPoint]
    ) -> tuple[list[PainPoint], list[TopicCluster]]:
        """对痛点进行聚类。

        Returns:
            (更新后的痛点列表（含 cluster_id），主题簇列表)
        """
        if len(pain_points) < self._min_cluster_size:
            logger.info(
                "Too few pain points (%d) for clustering (min: %d)",
                len(pain_points),
                self._min_cluster_size,
            )
            return pain_points, []

        # 生成嵌入
        descriptions = [pp.description for pp in pain_points]
        embeddings = self._generate_embeddings(descriptions)

        # HDBSCAN 聚类
        clusterer = HDBSCAN(
            min_cluster_size=self._min_cluster_size,
            metric="euclidean",
        )
        labels = clusterer.fit_predict(embeddings)

        # 构建主题簇
        unique_labels = set(labels) - {-1}  # -1 = noise
        clusters: list[TopicCluster] = []

        for cluster_id in unique_labels:
            member_indices = [i for i, l in enumerate(labels) if l == cluster_id]
            member_pps = [pain_points[i] for i in member_indices]

            # 提取关键词（简单方案：用最常见的词）
            all_words = []
            for pp in member_pps:
                all_words.extend(pp.description.split())
            from collections import Counter

            word_counts = Counter(w for w in all_words if len(w) > 1)
            keywords = [w for w, _ in word_counts.most_common(5)]

            cluster = TopicCluster(
                id=int(cluster_id),
                label=", ".join(keywords[:3]),
                pain_point_ids=[pp.id for pp in member_pps],
                keywords=keywords,
                size=len(member_indices),
            )
            clusters.append(cluster)

        # 更新痛点的 cluster_id
        updated_pps = []
        for i, pp in enumerate(pain_points):
            cluster_id = int(labels[i]) if labels[i] != -1 else None
            updated_pps.append(pp.model_copy(update={"topic_cluster_id": cluster_id}))

        noise_count = sum(1 for l in labels if l == -1)
        logger.info(
            "Clustered %d pain points into %d clusters (%d noise)",
            len(pain_points),
            len(clusters),
            noise_count,
        )

        return updated_pps, clusters
