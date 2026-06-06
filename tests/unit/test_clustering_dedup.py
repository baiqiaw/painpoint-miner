"""Tests for painpoint_miner.analysis.clustering and painpoint_miner.analysis.dedup.

Heavy dependencies (fastembed, sklearn) are mocked at the module level so the
test suite can run without them installed.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from painpoint_miner.models.base import PainPoint, TopicCluster
from painpoint_miner.models.enums import (
    PainType,
    Platform,
    Sentiment,
    Severity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pain_point(
    id_suffix: str = "1",
    description: str = "App crashes on launch",
    platforms: list[Platform] | None = None,
    frequency: int = 1,
    source_post_ids: list[str] | None = None,
) -> PainPoint:
    """Factory for PainPoint test instances."""
    return PainPoint(
        id=f"pp-{id_suffix}",
        source_post_ids=source_post_ids or [f"post-{id_suffix}"],
        platforms=platforms or [Platform.TWITTER],
        description=description,
        pain_type=PainType.BUG,
        severity=Severity.MAJOR,
        sentiment_score=-0.7,
        sentiment_label=Sentiment.NEGATIVE,
        frequency=frequency,
        extracted_at=datetime(2026, 1, 1),
    )


# ===================================================================
#  clustering.py tests
# ===================================================================

class TestPainPointClusterer:
    """Tests for PainPointClusterer.cluster()."""

    # -- too few pain points (< min_cluster_size) -----------------------

    @patch("painpoint_miner.analysis.clustering.HDBSCAN")
    @patch("painpoint_miner.analysis.clustering.TextEmbedding")
    def test_cluster_too_few_returns_original_and_empty_clusters(
        self, mock_text_embedding_cls, mock_hdbscan_cls
    ):
        """When pain points < min_cluster_size, return (pps, [])."""
        from painpoint_miner.analysis.clustering import PainPointClusterer

        clusterer = PainPointClusterer(min_cluster_size=3)
        pps = [_make_pain_point(str(i), f"desc {i}") for i in range(2)]

        result_pps, result_clusters = clusterer.cluster(pps)

        assert result_pps == pps
        assert result_clusters == []
        # Neither the embedding model nor HDBSCAN should be touched.
        mock_text_embedding_cls.assert_not_called()
        mock_hdbscan_cls.assert_not_called()

    # -- enough pain points, successful clustering ----------------------

    @patch("painpoint_miner.analysis.clustering.HDBSCAN")
    @patch("painpoint_miner.analysis.clustering.TextEmbedding")
    def test_cluster_sets_cluster_ids_on_pain_points(
        self, mock_text_embedding_cls, mock_hdbscan_cls
    ):
        """Cluster IDs must be set on the returned pain points."""
        from painpoint_miner.analysis.clustering import PainPointClusterer

        clusterer = PainPointClusterer(min_cluster_size=3)
        pps = [_make_pain_point(str(i), f"desc {i}") for i in range(5)]

        # Mock the embedding model to return deterministic vectors.
        fake_embeddings = np.eye(5, dtype=float)
        mock_model = MagicMock()
        mock_model.embed.return_value = iter(fake_embeddings)
        mock_text_embedding_cls.return_value = mock_model

        # Mock HDBSCAN: assign first 3 to cluster 0, last 2 to cluster 1.
        mock_clusterer = MagicMock()
        mock_clusterer.fit_predict.return_value = np.array([0, 0, 0, 1, 1])
        mock_hdbscan_cls.return_value = mock_clusterer

        result_pps, result_clusters = clusterer.cluster(pps)

        assert len(result_pps) == 5
        # First three should belong to cluster 0.
        assert result_pps[0].topic_cluster_id == 0
        assert result_pps[1].topic_cluster_id == 0
        assert result_pps[2].topic_cluster_id == 0
        # Last two should belong to cluster 1.
        assert result_pps[3].topic_cluster_id == 1
        assert result_pps[4].topic_cluster_id == 1
        # Two distinct clusters produced.
        assert len(result_clusters) == 2

    # -- noise points (label=-1) get cluster_id=None --------------------

    @patch("painpoint_miner.analysis.clustering.HDBSCAN")
    @patch("painpoint_miner.analysis.clustering.TextEmbedding")
    def test_cluster_noise_points_get_none_cluster_id(
        self, mock_text_embedding_cls, mock_hdbscan_cls
    ):
        """Points labelled -1 by HDBSCAN (noise) must have cluster_id=None."""
        from painpoint_miner.analysis.clustering import PainPointClusterer

        clusterer = PainPointClusterer(min_cluster_size=2)
        pps = [_make_pain_point(str(i), f"desc {i}") for i in range(4)]

        fake_embeddings = np.eye(4, dtype=float)
        mock_model = MagicMock()
        mock_model.embed.return_value = iter(fake_embeddings)
        mock_text_embedding_cls.return_value = mock_model

        # Labels: 0, -1, 0, -1  => points 1 and 3 are noise.
        mock_clusterer = MagicMock()
        mock_clusterer.fit_predict.return_value = np.array([0, -1, 0, -1])
        mock_hdbscan_cls.return_value = mock_clusterer

        result_pps, result_clusters = clusterer.cluster(pps)

        assert result_pps[0].topic_cluster_id == 0
        assert result_pps[1].topic_cluster_id is None  # noise
        assert result_pps[2].topic_cluster_id == 0
        assert result_pps[3].topic_cluster_id is None  # noise
        # Only one real cluster (label 0).
        assert len(result_clusters) == 1

    # -- _generate_embeddings called with correct descriptions -----------

    @patch("painpoint_miner.analysis.clustering.HDBSCAN")
    @patch("painpoint_miner.analysis.clustering.TextEmbedding")
    def test_generate_embeddings_receives_descriptions(
        self, mock_text_embedding_cls, mock_hdbscan_cls
    ):
        """_generate_embeddings must be called with pain point descriptions."""
        from painpoint_miner.analysis.clustering import PainPointClusterer

        clusterer = PainPointClusterer(min_cluster_size=2)
        descriptions = ["crash bug", "slow performance", "crash bug again"]
        pps = [
            _make_pain_point(str(i), descriptions[i]) for i in range(3)
        ]

        fake_embeddings = np.random.rand(3, 4).astype(float)
        mock_model = MagicMock()
        mock_model.embed.return_value = iter(fake_embeddings)
        mock_text_embedding_cls.return_value = mock_model

        mock_clusterer = MagicMock()
        mock_clusterer.fit_predict.return_value = np.array([0, -1, 0])
        mock_hdbscan_cls.return_value = mock_clusterer

        with patch.object(
            clusterer, "_generate_embeddings", wraps=clusterer._generate_embeddings
        ) as spy_embed:
            clusterer.cluster(pps)
            spy_embed.assert_called_once_with(descriptions)

        # Also verify the underlying model.embed received the descriptions.
        mock_model.embed.assert_called_once_with(descriptions)

    # -- HDBSCAN receives correct min_cluster_size -----------------------

    @patch("painpoint_miner.analysis.clustering.HDBSCAN")
    @patch("painpoint_miner.analysis.clustering.TextEmbedding")
    def test_hdbscan_called_with_min_cluster_size(
        self, mock_text_embedding_cls, mock_hdbscan_cls
    ):
        """HDBSCAN must be instantiated with the configured min_cluster_size."""
        from painpoint_miner.analysis.clustering import PainPointClusterer

        clusterer = PainPointClusterer(min_cluster_size=5)
        pps = [_make_pain_point(str(i), f"desc {i}") for i in range(6)]

        fake_embeddings = np.eye(6, dtype=float)
        mock_model = MagicMock()
        mock_model.embed.return_value = iter(fake_embeddings)
        mock_text_embedding_cls.return_value = mock_model

        mock_clusterer = MagicMock()
        mock_clusterer.fit_predict.return_value = np.zeros(6, dtype=int)
        mock_hdbscan_cls.return_value = mock_clusterer

        clusterer.cluster(pps)

        mock_hdbscan_cls.assert_called_once_with(
            min_cluster_size=5, metric="euclidean"
        )

    # -- cluster keywords are extracted from descriptions ----------------

    @patch("painpoint_miner.analysis.clustering.HDBSCAN")
    @patch("painpoint_miner.analysis.clustering.TextEmbedding")
    def test_cluster_keywords_extracted_from_descriptions(
        self, mock_text_embedding_cls, mock_hdbscan_cls
    ):
        """TopicCluster keywords should come from member descriptions."""
        from painpoint_miner.analysis.clustering import PainPointClusterer

        clusterer = PainPointClusterer(min_cluster_size=2)
        pps = [
            _make_pain_point("0", "app crash frequently"),
            _make_pain_point("1", "app crash again"),
        ]

        fake_embeddings = np.eye(2, dtype=float)
        mock_model = MagicMock()
        mock_model.embed.return_value = iter(fake_embeddings)
        mock_text_embedding_cls.return_value = mock_model

        mock_clusterer = MagicMock()
        mock_clusterer.fit_predict.return_value = np.array([0, 0])
        mock_hdbscan_cls.return_value = mock_clusterer

        _, clusters = clusterer.cluster(pps)

        assert len(clusters) == 1
        cluster = clusters[0]
        # "crash" appears in both, "app" appears in both.
        assert "crash" in cluster.keywords
        assert "app" in cluster.keywords
        assert cluster.size == 2
        assert cluster.id == 0


# ===================================================================
#  dedup.py tests
# ===================================================================

class TestPainPointDeduplicator:
    """Tests for PainPointDeduplicator.deduplicate()."""

    # -- empty list ------------------------------------------------------

    @patch("painpoint_miner.analysis.dedup.cosine_similarity")
    @patch("painpoint_miner.analysis.dedup.TextEmbedding")
    def test_deduplicate_empty_list_returns_empty(
        self, mock_text_embedding_cls, mock_cosine_similarity
    ):
        """Empty input returns empty output."""
        from painpoint_miner.analysis.dedup import PainPointDeduplicator

        dedup = PainPointDeduplicator()
        result = dedup.deduplicate([])

        assert result == []

    # -- single item -----------------------------------------------------

    @patch("painpoint_miner.analysis.dedup.cosine_similarity")
    @patch("painpoint_miner.analysis.dedup.TextEmbedding")
    def test_deduplicate_single_item_returns_same(
        self, mock_text_embedding_cls, mock_cosine_similarity
    ):
        """Single-item input is returned unchanged (early return path)."""
        from painpoint_miner.analysis.dedup import PainPointDeduplicator

        dedup = PainPointDeduplicator()
        pp = _make_pain_point("1", "some description")
        result = dedup.deduplicate([pp])

        assert len(result) == 1
        assert result[0].id == pp.id
        # The embedding model and cosine_similarity should NOT be called
        # because len(pain_points) <= 1 triggers an early return.
        mock_text_embedding_cls.assert_not_called()
        mock_cosine_similarity.assert_not_called()

    # -- similar items above threshold are merged ------------------------

    @patch("painpoint_miner.analysis.dedup.cosine_similarity")
    @patch("painpoint_miner.analysis.dedup.TextEmbedding")
    def test_deduplicate_similar_items_merged(
        self, mock_text_embedding_cls, mock_cosine_similarity
    ):
        """Items with cosine similarity >= threshold are merged into one."""
        from painpoint_miner.analysis.dedup import PainPointDeduplicator

        dedup = PainPointDeduplicator(similarity_threshold=0.9)

        pp_a = _make_pain_point(
            "1",
            "The app crashes when I open it",
            platforms=[Platform.TWITTER],
            frequency=3,
            source_post_ids=["post-1"],
        )
        pp_b = _make_pain_point(
            "2",
            "App crashes on startup every time",
            platforms=[Platform.WEIBO],
            frequency=2,
            source_post_ids=["post-2"],
        )

        # Mock embeddings.
        fake_embeddings = np.array([[1.0, 0.0], [0.99, 0.1]])
        mock_model = MagicMock()
        mock_model.embed.return_value = iter(fake_embeddings)
        mock_text_embedding_cls.return_value = mock_model

        # Similarity matrix — items are very similar.
        mock_cosine_similarity.return_value = np.array(
            [[1.0, 0.95], [0.95, 1.0]]
        )

        result = dedup.deduplicate([pp_a, pp_b])

        # Only one pain point should survive (merged).
        assert len(result) == 1
        merged = result[0]

        # The merged result keeps the first item's id.
        assert merged.id == "pp-1"

        # Platforms from both items should be combined.
        assert Platform.TWITTER in merged.platforms
        assert Platform.WEIBO in merged.platforms

        # Source post IDs from both items should be present.
        assert "post-1" in merged.source_post_ids
        assert "post-2" in merged.source_post_ids

    # -- different items below threshold are NOT merged ------------------

    @patch("painpoint_miner.analysis.dedup.cosine_similarity")
    @patch("painpoint_miner.analysis.dedup.TextEmbedding")
    def test_deduplicate_different_items_not_merged(
        self, mock_text_embedding_cls, mock_cosine_similarity
    ):
        """Items with cosine similarity < threshold are kept separate."""
        from painpoint_miner.analysis.dedup import PainPointDeduplicator

        dedup = PainPointDeduplicator(similarity_threshold=0.9)

        pp_a = _make_pain_point("1", "App crashes on launch")
        pp_b = _make_pain_point("2", "I love the new dark mode feature")

        fake_embeddings = np.array([[1.0, 0.0], [0.0, 1.0]])
        mock_model = MagicMock()
        mock_model.embed.return_value = iter(fake_embeddings)
        mock_text_embedding_cls.return_value = mock_model

        # Similarity matrix — items are not similar.
        mock_cosine_similarity.return_value = np.array(
            [[1.0, 0.3], [0.3, 1.0]]
        )

        result = dedup.deduplicate([pp_a, pp_b])

        assert len(result) == 2
        assert result[0].id == "pp-1"
        assert result[1].id == "pp-2"
        # Frequencies should remain unchanged (no merge happened).
        assert result[0].frequency == 1
        assert result[1].frequency == 1

    # -- merged items accumulate frequency --------------------------------

    @patch("painpoint_miner.analysis.dedup.cosine_similarity")
    @patch("painpoint_miner.analysis.dedup.TextEmbedding")
    def test_deduplicate_merged_accumulates_frequency(
        self, mock_text_embedding_cls, mock_cosine_similarity
    ):
        """When items are merged, frequencies must be summed."""
        from painpoint_miner.analysis.dedup import PainPointDeduplicator

        dedup = PainPointDeduplicator(similarity_threshold=0.9)

        pp_a = _make_pain_point(
            "1", "slow loading", frequency=5, platforms=[Platform.TWITTER]
        )
        pp_b = _make_pain_point(
            "2", "very slow loading", frequency=3, platforms=[Platform.ZHIHU]
        )
        pp_c = _make_pain_point(
            "3", "extremely slow loading", frequency=2, platforms=[Platform.WEIBO]
        )

        fake_embeddings = np.eye(3, dtype=float)
        mock_model = MagicMock()
        mock_model.embed.return_value = iter(fake_embeddings)
        mock_text_embedding_cls.return_value = mock_model

        # All three are mutually similar (above threshold).
        mock_cosine_similarity.return_value = np.array(
            [
                [1.0, 0.95, 0.92],
                [0.95, 1.0, 0.91],
                [0.92, 0.91, 1.0],
            ]
        )

        result = dedup.deduplicate([pp_a, pp_b, pp_c])

        # All three should be merged into one.
        assert len(result) == 1
        merged = result[0]

        # Frequency should be the sum: 5 + 3 + 2 = 10.
        assert merged.frequency == 10

        # All platforms should be present.
        assert set(merged.platforms) == {Platform.TWITTER, Platform.ZHIHU, Platform.WEIBO}

        # All source post IDs should be present.
        assert set(merged.source_post_ids) == {"post-1", "post-2", "post-3"}

    # -- mixed: some similar, some different ------------------------------

    @patch("painpoint_miner.analysis.dedup.cosine_similarity")
    @patch("painpoint_miner.analysis.dedup.TextEmbedding")
    def test_deduplicate_mixed_similarity(
        self, mock_text_embedding_cls, mock_cosine_similarity
    ):
        """When only a subset is similar, only those are merged."""
        from painpoint_miner.analysis.dedup import PainPointDeduplicator

        dedup = PainPointDeduplicator(similarity_threshold=0.9)

        pp_a = _make_pain_point("1", "crash bug", frequency=2)
        pp_b = _make_pain_point("2", "app crash", frequency=3)
        pp_c = _make_pain_point("3", "love dark mode", frequency=1)

        fake_embeddings = np.eye(3, dtype=float)
        mock_model = MagicMock()
        mock_model.embed.return_value = iter(fake_embeddings)
        mock_text_embedding_cls.return_value = mock_model

        # a <-> b similar, a <-> c and b <-> c not similar.
        mock_cosine_similarity.return_value = np.array(
            [
                [1.0, 0.95, 0.2],
                [0.95, 1.0, 0.25],
                [0.2, 0.25, 1.0],
            ]
        )

        result = dedup.deduplicate([pp_a, pp_b, pp_c])

        # pp_a and pp_b merged, pp_c kept separate => 2 results.
        assert len(result) == 2
        # First result is the merge of pp_a + pp_b.
        assert result[0].id == "pp-1"
        assert result[0].frequency == 5  # 2 + 3
        # Second result is pp_c unchanged.
        assert result[1].id == "pp-3"
        assert result[1].frequency == 1
