"""数据模型单元测试。"""

import pytest
from datetime import datetime

from painpoint_miner.models import (
    AnalysisMode,
    AnalysisReport,
    CostSummary,
    PainPoint,
    PainType,
    PipelineConfig,
    Platform,
    RawComment,
    RawPost,
    Sentiment,
    Severity,
    TopicCluster,
)


class TestPlatform:
    """Platform 枚举测试。"""

    def test_all_platforms(self):
        assert set(Platform) == {
            Platform.TWITTER,
            Platform.XIAOHONGSHU,
            Platform.WEIBO,
            Platform.DOUYIN,
            Platform.ZHIHU,
        }

    def test_string_values(self):
        assert Platform.XIAOHONGSHU.value == "xiaohongshu"
        assert Platform.TWITTER.value == "twitter"


class TestRawPost:
    """RawPost 模型测试。"""

    def test_create_minimal(self):
        post = RawPost(
            platform=Platform.WEIBO,
            post_id="wb_001",
            author_id="user_001",
            content="测试内容",
        )
        assert post.platform == Platform.WEIBO
        assert post.likes == 0
        assert post.comments_count == 0
        assert post.hashtags == []
        assert post.extra == {}

    def test_create_full(self, sample_raw_post):
        assert sample_raw_post.platform == Platform.XIAOHONGSHU
        assert sample_raw_post.likes == 42
        assert "吐槽" in sample_raw_post.hashtags

    def test_serialization_roundtrip(self, sample_raw_post):
        """Pydantic JSON 序列化往返。"""
        json_str = sample_raw_post.model_dump_json()
        restored = RawPost.model_validate_json(json_str)
        assert restored.post_id == sample_raw_post.post_id
        assert restored.content == sample_raw_post.content
        assert restored.platform == sample_raw_post.platform


class TestRawComment:
    """RawComment 模型测试。"""

    def test_create_minimal(self):
        comment = RawComment(
            platform=Platform.ZHIHU,
            comment_id="cmt_001",
            post_id="q_001",
            author_id="user_001",
            content="评论内容",
        )
        assert comment.parent_comment_id is None
        assert comment.likes == 0

    def test_nested_comment(self):
        comment = RawComment(
            platform=Platform.WEIBO,
            comment_id="cmt_002",
            post_id="wb_001",
            author_id="user_002",
            content="回复",
            parent_comment_id="cmt_001",
        )
        assert comment.parent_comment_id == "cmt_001"


class TestPainPoint:
    """PainPoint 模型测试。"""

    def test_create_with_defaults(self):
        pp = PainPoint(
            id="pp_001",
            description="测试痛点",
        )
        assert pp.pain_type == PainType.OTHER
        assert pp.severity == Severity.MODERATE
        assert pp.sentiment_score == 0.0
        assert pp.frequency == 1

    def test_sentiment_score_bounds(self):
        """情感分数必须在 [-1.0, 1.0] 范围内。"""
        with pytest.raises(Exception):
            PainPoint(id="pp_001", description="test", sentiment_score=1.5)
        with pytest.raises(Exception):
            PainPoint(id="pp_001", description="test", sentiment_score=-1.5)

    def test_valid_sentiment_score(self, sample_pain_point):
        assert -1.0 <= sample_pain_point.sentiment_score <= 1.0

    def test_all_pain_types(self):
        types = set(PainType)
        assert len(types) == 8
        assert PainType.UX_PROBLEM in types
        assert PainType.BUG in types


class TestAnalysisReport:
    """AnalysisReport 模型测试。"""

    def test_create_empty(self):
        report = AnalysisReport(query_keywords=["测试"])
        assert report.total_posts_scraped == 0
        assert report.pain_points == []
        assert report.topic_clusters == []

    def test_with_pain_points(self, sample_pain_point):
        report = AnalysisReport(
            query_keywords=["难用", "贵"],
            total_posts_scraped=100,
            pain_points=[sample_pain_point],
            platform_breakdown={"xiaohongshu": 50, "weibo": 50},
        )
        assert len(report.pain_points) == 1
        assert report.platform_breakdown["xiaohongshu"] == 50


class TestPipelineConfig:
    """PipelineConfig 模型测试。"""

    def test_defaults(self):
        config = PipelineConfig(
            keywords=["测试"],
            platforms=[Platform.XIAOHONGSHU],
        )
        assert config.max_posts_per_keyword == 100
        assert config.analysis_mode == AnalysisMode.MERGED
        assert config.dedup_threshold == 0.9
        assert config.max_llm_budget_usd is None

    def test_dedup_threshold_bounds(self):
        with pytest.raises(Exception):
            PipelineConfig(
                keywords=["测试"],
                platforms=[Platform.XIAOHONGSHU],
                dedup_threshold=1.5,
            )


class TestTopicCluster:
    def test_create(self):
        cluster = TopicCluster(id=1, label="UI 抱怨", size=10)
        assert cluster.size == 10
        assert cluster.pain_point_ids == []


class TestCostSummary:
    def test_model_dump(self):
        cs = CostSummary(
            total_input_tokens=1000,
            total_output_tokens=500,
            total_calls=10,
            estimated_cost_usd=0.05,
            model_used="claude-haiku-4-5-20251001",
        )
        d = cs.model_dump()
        assert d["total_calls"] == 10
        assert d["estimated_cost_usd"] == 0.05
