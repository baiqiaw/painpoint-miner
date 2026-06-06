"""AnalysisPipeline 和 ClaudeProvider / MockLLMProvider 单元测试。"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from painpoint_miner.models.base import (
    AnalysisReport,
    PainPoint,
    PipelineConfig,
)
from painpoint_miner.models.enums import (
    AnalysisMode,
    PainType,
    Platform,
    Sentiment,
    Severity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _async_generator(items):
    """将列表转换为异步生成器。"""
    for item in items:
        yield item


def _make_settings_mock() -> MagicMock:
    """创建具有 pipeline 所需全部嵌套属性的 Settings mock。"""
    settings = MagicMock()
    settings.privacy.retention_days = 30
    settings.privacy.anonymize = True
    return settings


def _make_pain_point(
    pid="pp_001",
    pain_type=PainType.UX_PROBLEM,
) -> PainPoint:
    """创建一个供测试使用的 PainPoint 实例。"""
    return PainPoint(
        id=pid,
        source_post_ids=["post_1"],
        platforms=[Platform.XIAOHONGSHU],
        description="按钮找不到",
        pain_type=pain_type,
        severity=Severity.MAJOR,
        sentiment_score=-0.7,
        sentiment_label=Sentiment.NEGATIVE,
        frequency=5,
        evidence_quotes=["太难用了"],
    )


def _make_pipeline_config() -> PipelineConfig:
    """创建一个供测试使用的 PipelineConfig 实例。"""
    return PipelineConfig(
        keywords=["测试"],
        platforms=[Platform.XIAOHONGSHU],
        max_posts_per_keyword=10,
        analysis_mode=AnalysisMode.MERGED,
    )


# ===================================================================
# AnalysisPipeline — _generate_summary tests
# ===================================================================


class TestGenerateSummary:
    """AnalysisPipeline._generate_summary() 的单元测试。"""

    def _make_pipeline(self) -> "AnalysisPipeline":
        """构建一个仅用于测试 _generate_summary 的 pipeline 实例。"""
        from painpoint_miner.analysis.pipeline import AnalysisPipeline

        return AnalysisPipeline(
            registry=MagicMock(),
            extractor=MagicMock(),
            clusterer=MagicMock(),
            deduplicator=MagicMock(),
            anonymizer=MagicMock(),
            llm=MagicMock(),
            settings=MagicMock(),
            db_path=":memory:",
        )

    def test_empty_pain_points_no_errors(self):
        """空痛点列表且无错误时，摘要仅包含总数行。"""
        pipeline = self._make_pipeline()
        result = pipeline._generate_summary([], [], [])
        assert result == "共发现 0 个用户痛点。"

    def test_with_clusters(self):
        """有聚类时，摘要包含聚类数量信息。"""
        pipeline = self._make_pipeline()
        pp = _make_pain_point()
        clusters = [MagicMock(), MagicMock(), MagicMock()]

        result = pipeline._generate_summary([pp], clusters, [])

        assert "共发现 1 个用户痛点。" in result
        assert "归纳为 3 个主题类别。" in result

    def test_with_errors(self):
        """有错误时，摘要包含错误数量信息。"""
        pipeline = self._make_pipeline()
        errors = ["twitter: timeout", "weibo: 403"]

        result = pipeline._generate_summary([], [], errors)

        assert "抓取过程中有 2 个平台出现错误。" in result

    def test_with_pain_type_distribution(self):
        """有痛点时，摘要包含痛点类型分布（最多 3 种）。"""
        pipeline = self._make_pipeline()
        pp1 = _make_pain_point(pid="pp_1", pain_type=PainType.UX_PROBLEM)
        pp2 = _make_pain_point(pid="pp_2", pain_type=PainType.UX_PROBLEM)
        pp3 = _make_pain_point(pid="pp_3", pain_type=PainType.PERFORMANCE)
        pp4 = _make_pain_point(pid="pp_4", pain_type=PainType.BUG)

        result = pipeline._generate_summary([pp1, pp2, pp3, pp4], [], [])

        assert "共发现 4 个用户痛点。" in result
        assert "ux_problem(2)" in result
        assert "performance(1)" in result
        assert "bug(1)" in result

    def test_top_three_types_only(self):
        """类型分布只显示前 3 种。"""
        pipeline = self._make_pipeline()
        types = [
            PainType.UX_PROBLEM,
            PainType.UX_PROBLEM,
            PainType.UX_PROBLEM,
            PainType.PERFORMANCE,
            PainType.PERFORMANCE,
            PainType.BUG,
            PainType.PRICING,
        ]
        pain_points = [
            _make_pain_point(pid=f"pp_{i}", pain_type=t)
            for i, t in enumerate(types)
        ]

        result = pipeline._generate_summary(pain_points, [], [])

        assert "ux_problem(3)" in result
        assert "performance(2)" in result
        assert "bug(1)" in result
        # pricing 不应出现在前 3
        assert "pricing" not in result

    def test_full_summary_with_all_sections(self):
        """所有部分同时存在时，摘要格式正确。"""
        pipeline = self._make_pipeline()
        pp = _make_pain_point()
        clusters = [MagicMock()]
        errors = ["platform_x: error"]

        result = pipeline._generate_summary([pp], clusters, errors)

        assert "共发现 1 个用户痛点。" in result
        assert "归纳为 1 个主题类别。" in result
        assert "抓取过程中有 1 个平台出现错误。" in result
        assert "主要痛点类型：" in result


# ===================================================================
# AnalysisPipeline — run() tests
# ===================================================================


class TestPipelineRun:
    """AnalysisPipeline.run() 的单元测试。"""

    @pytest.fixture()
    def mock_deps(self, tmp_path: Path):
        """为 AnalysisPipeline 提供所有 mock 依赖项。"""
        registry = MagicMock()
        extractor = MagicMock()
        clusterer = MagicMock()
        deduplicator = MagicMock()
        anonymizer = MagicMock()
        llm = AsyncMock()
        settings = _make_settings_mock()
        db_path = str(tmp_path / "test.db")

        return {
            "registry": registry,
            "extractor": extractor,
            "clusterer": clusterer,
            "deduplicator": deduplicator,
            "anonymizer": anonymizer,
            "llm": llm,
            "settings": settings,
            "db_path": db_path,
        }

    @pytest.mark.asyncio
    async def test_run_no_posts(self, mock_deps):
        """当爬虫未返回任何帖子时，pipeline 应正常完成并返回一个空报告。"""
        from painpoint_miner.analysis.pipeline import AnalysisPipeline

        # Mock scraper — 异步上下文管理器 + search_posts 异步生成器
        mock_scraper = AsyncMock()
        mock_scraper.__aenter__ = AsyncMock(return_value=mock_scraper)
        mock_scraper.__aexit__ = AsyncMock(return_value=False)
        mock_scraper.search_posts = MagicMock(
            return_value=_async_generator([])
        )

        mock_deps["registry"].get_scraper = AsyncMock(return_value=mock_scraper)

        pipeline = AnalysisPipeline(**mock_deps)
        config = _make_pipeline_config()

        with (
            patch("painpoint_miner.analysis.pipeline.run_migrations", new_callable=AsyncMock) as mock_migrations,
            patch("painpoint_miner.analysis.pipeline.Cache") as mock_cache_cls,
            patch("painpoint_miner.analysis.pipeline.Checkpoint") as mock_checkpoint_cls,
        ):
            mock_cache = AsyncMock()
            mock_cache.cleanup_expired = AsyncMock(return_value=0)
            mock_cache.is_scraped = AsyncMock(return_value=False)
            mock_cache_cls.return_value = mock_cache

            mock_checkpoint = AsyncMock()
            mock_checkpoint.load_latest = AsyncMock(return_value=None)
            mock_checkpoint.save = AsyncMock()
            mock_checkpoint_cls.return_value = mock_checkpoint

            report = await pipeline.run(config)

        # Assertions
        mock_migrations.assert_awaited_once()
        mock_cache.cleanup_expired.assert_awaited_once_with(30)
        mock_checkpoint.load_latest.assert_awaited_once()
        mock_checkpoint.save.assert_awaited_once()
        mock_deps["registry"].get_scraper.assert_awaited_once_with(Platform.XIAOHONGSHU)

        assert isinstance(report, AnalysisReport)
        assert report.query_keywords == ["测试"]
        assert report.pain_points == []
        assert report.topic_clusters == []
        assert report.total_posts_scraped == 0
        assert isinstance(report.summary, str)
        assert len(report.summary) > 0
        assert isinstance(report.platform_breakdown, dict)

    @pytest.mark.asyncio
    async def test_run_with_posts(self, mock_deps, sample_raw_post):
        """当爬虫返回帖子时，pipeline 应通过 extract/dedup/cluster 流程处理。"""
        from painpoint_miner.analysis.pipeline import AnalysisPipeline

        post = sample_raw_post

        # Mock scraper — search_posts 返回异步生成器（非 AsyncMock）
        mock_scraper = AsyncMock()
        mock_scraper.__aenter__ = AsyncMock(return_value=mock_scraper)
        mock_scraper.__aexit__ = AsyncMock(return_value=False)
        mock_scraper.search_posts = MagicMock(
            return_value=_async_generator([post])
        )
        mock_deps["registry"].get_scraper = AsyncMock(return_value=mock_scraper)

        # Mock extractor returns pain points
        pain_point = _make_pain_point()
        mock_deps["extractor"].extract = AsyncMock(return_value=[pain_point])

        # Mock deduplicator
        mock_deps["deduplicator"].deduplicate = MagicMock(return_value=[pain_point])

        # Mock clusterer — 返回真正的 TopicCluster 实例
        from painpoint_miner.models.base import TopicCluster

        mock_cluster = TopicCluster(
            id=1,
            label="UX 问题",
            pain_point_ids=[pain_point.id],
            keywords=["按钮", "UX"],
            size=1,
        )
        mock_deps["clusterer"].cluster = MagicMock(
            return_value=([pain_point], [mock_cluster])
        )

        # Mock anonymizer
        mock_deps["anonymizer"].anonymize_post = MagicMock(return_value=post)

        pipeline = AnalysisPipeline(**mock_deps)
        config = _make_pipeline_config()

        with (
            patch("painpoint_miner.analysis.pipeline.run_migrations", new_callable=AsyncMock),
            patch("painpoint_miner.analysis.pipeline.Cache") as mock_cache_cls,
            patch("painpoint_miner.analysis.pipeline.Checkpoint") as mock_checkpoint_cls,
        ):
            mock_cache = AsyncMock()
            mock_cache.cleanup_expired = AsyncMock(return_value=0)
            mock_cache.is_scraped = AsyncMock(return_value=False)
            mock_cache_cls.return_value = mock_cache

            mock_checkpoint = AsyncMock()
            mock_checkpoint.load_latest = AsyncMock(return_value=None)
            mock_checkpoint.save = AsyncMock()
            mock_checkpoint_cls.return_value = mock_checkpoint

            report = await pipeline.run(config)

        mock_deps["extractor"].extract.assert_awaited_once()
        mock_deps["deduplicator"].deduplicate.assert_called_once_with([pain_point])
        mock_deps["clusterer"].cluster.assert_called_once_with([pain_point])

        assert isinstance(report, AnalysisReport)
        assert len(report.pain_points) == 1
        assert report.pain_points[0].id == "pp_001"
        assert len(report.topic_clusters) == 1
        assert report.total_posts_scraped == 1

    @pytest.mark.asyncio
    async def test_run_scraper_error_continues(self, mock_deps):
        """当爬虫抛出异常时，pipeline 应捕获错误并继续执行。"""
        from painpoint_miner.analysis.pipeline import AnalysisPipeline

        # Scraper raises an error
        mock_scraper = AsyncMock()
        mock_scraper.__aenter__ = AsyncMock(return_value=mock_scraper)
        mock_scraper.__aexit__ = AsyncMock(return_value=False)
        mock_scraper.search_posts = AsyncMock(
            side_effect=RuntimeError("connection refused")
        )
        mock_deps["registry"].get_scraper = AsyncMock(return_value=mock_scraper)

        pipeline = AnalysisPipeline(**mock_deps)
        config = _make_pipeline_config()

        with (
            patch("painpoint_miner.analysis.pipeline.run_migrations", new_callable=AsyncMock),
            patch("painpoint_miner.analysis.pipeline.Cache") as mock_cache_cls,
            patch("painpoint_miner.analysis.pipeline.Checkpoint") as mock_checkpoint_cls,
        ):
            mock_cache = AsyncMock()
            mock_cache.cleanup_expired = AsyncMock(return_value=0)
            mock_cache_cls.return_value = mock_cache

            mock_checkpoint = AsyncMock()
            mock_checkpoint.load_latest = AsyncMock(return_value=None)
            mock_checkpoint.save = AsyncMock()
            mock_checkpoint_cls.return_value = mock_checkpoint

            report = await pipeline.run(config)

        assert isinstance(report, AnalysisReport)
        assert report.pain_points == []
        # The error is captured in the summary
        assert "抓取过程中有" in report.summary or "共发现 0" in report.summary

    @pytest.mark.asyncio
    async def test_run_anonymize_called_when_enabled(self, mock_deps, sample_raw_post):
        """当 settings.privacy.anonymize=True 时，匿名化器应被调用。"""
        from painpoint_miner.analysis.pipeline import AnalysisPipeline

        post = sample_raw_post
        mock_deps["settings"].privacy.anonymize = True

        mock_scraper = AsyncMock()
        mock_scraper.__aenter__ = AsyncMock(return_value=mock_scraper)
        mock_scraper.__aexit__ = AsyncMock(return_value=False)
        mock_scraper.search_posts = MagicMock(
            return_value=_async_generator([post])
        )
        mock_deps["registry"].get_scraper = AsyncMock(return_value=mock_scraper)
        mock_deps["anonymizer"].anonymize_post = MagicMock(return_value=post)

        pipeline = AnalysisPipeline(**mock_deps)
        config = _make_pipeline_config()

        with (
            patch("painpoint_miner.analysis.pipeline.run_migrations", new_callable=AsyncMock),
            patch("painpoint_miner.analysis.pipeline.Cache") as mock_cache_cls,
            patch("painpoint_miner.analysis.pipeline.Checkpoint") as mock_checkpoint_cls,
        ):
            mock_cache = AsyncMock()
            mock_cache.cleanup_expired = AsyncMock(return_value=0)
            mock_cache.is_scraped = AsyncMock(return_value=False)
            mock_cache_cls.return_value = mock_cache

            mock_checkpoint = AsyncMock()
            mock_checkpoint.load_latest = AsyncMock(return_value=None)
            mock_checkpoint.save = AsyncMock()
            mock_checkpoint_cls.return_value = mock_checkpoint

            report = await pipeline.run(config)

        mock_deps["anonymizer"].anonymize_post.assert_called_once_with(post)

    @pytest.mark.asyncio
    async def test_run_anonymize_not_called_when_disabled(self, mock_deps, sample_raw_post):
        """当 settings.privacy.anonymize=False 时，匿名化器不应被调用。"""
        from painpoint_miner.analysis.pipeline import AnalysisPipeline

        post = sample_raw_post
        mock_deps["settings"].privacy.anonymize = False

        mock_scraper = AsyncMock()
        mock_scraper.__aenter__ = AsyncMock(return_value=mock_scraper)
        mock_scraper.__aexit__ = AsyncMock(return_value=False)
        mock_scraper.search_posts = MagicMock(
            return_value=_async_generator([post])
        )
        mock_deps["registry"].get_scraper = AsyncMock(return_value=mock_scraper)
        mock_deps["anonymizer"].anonymize_post = MagicMock(return_value=post)

        pipeline = AnalysisPipeline(**mock_deps)
        config = _make_pipeline_config()

        with (
            patch("painpoint_miner.analysis.pipeline.run_migrations", new_callable=AsyncMock),
            patch("painpoint_miner.analysis.pipeline.Cache") as mock_cache_cls,
            patch("painpoint_miner.analysis.pipeline.Checkpoint") as mock_checkpoint_cls,
        ):
            mock_cache = AsyncMock()
            mock_cache.cleanup_expired = AsyncMock(return_value=0)
            mock_cache.is_scraped = AsyncMock(return_value=False)
            mock_cache_cls.return_value = mock_cache

            mock_checkpoint = AsyncMock()
            mock_checkpoint.load_latest = AsyncMock(return_value=None)
            mock_checkpoint.save = AsyncMock()
            mock_checkpoint_cls.return_value = mock_checkpoint

            report = await pipeline.run(config)

        mock_deps["anonymizer"].anonymize_post.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_extraction_failure_handled(self, mock_deps, sample_raw_post):
        """当 LLM 提取失败时，pipeline 应优雅处理并返回空痛点列表。"""
        from painpoint_miner.analysis.pipeline import AnalysisPipeline

        post = sample_raw_post

        mock_scraper = AsyncMock()
        mock_scraper.__aenter__ = AsyncMock(return_value=mock_scraper)
        mock_scraper.__aexit__ = AsyncMock(return_value=False)
        mock_scraper.search_posts = MagicMock(
            return_value=_async_generator([post])
        )
        mock_deps["registry"].get_scraper = AsyncMock(return_value=mock_scraper)
        mock_deps["anonymizer"].anonymize_post = MagicMock(return_value=post)

        # Extractor raises an exception
        mock_deps["extractor"].extract = AsyncMock(
            side_effect=RuntimeError("LLM API error")
        )

        pipeline = AnalysisPipeline(**mock_deps)
        config = _make_pipeline_config()

        with (
            patch("painpoint_miner.analysis.pipeline.run_migrations", new_callable=AsyncMock),
            patch("painpoint_miner.analysis.pipeline.Cache") as mock_cache_cls,
            patch("painpoint_miner.analysis.pipeline.Checkpoint") as mock_checkpoint_cls,
        ):
            mock_cache = AsyncMock()
            mock_cache.cleanup_expired = AsyncMock(return_value=0)
            mock_cache.is_scraped = AsyncMock(return_value=False)
            mock_cache_cls.return_value = mock_cache

            mock_checkpoint = AsyncMock()
            mock_checkpoint.load_latest = AsyncMock(return_value=None)
            mock_checkpoint.save = AsyncMock()
            mock_checkpoint_cls.return_value = mock_checkpoint

            report = await pipeline.run(config)

        assert isinstance(report, AnalysisReport)
        assert report.pain_points == []
        assert report.topic_clusters == []

    @pytest.mark.asyncio
    async def test_run_checkpoint_saved(self, mock_deps):
        """流水线完成后，checkpoint.save 应使用正确的状态调用。"""
        from painpoint_miner.analysis.pipeline import AnalysisPipeline

        mock_scraper = AsyncMock()
        mock_scraper.__aenter__ = AsyncMock(return_value=mock_scraper)
        mock_scraper.__aexit__ = AsyncMock(return_value=False)
        mock_scraper.search_posts = MagicMock(
            return_value=_async_generator([])
        )
        mock_deps["registry"].get_scraper = AsyncMock(return_value=mock_scraper)

        pipeline = AnalysisPipeline(**mock_deps)
        config = _make_pipeline_config()

        with (
            patch("painpoint_miner.analysis.pipeline.run_migrations", new_callable=AsyncMock),
            patch("painpoint_miner.analysis.pipeline.Cache") as mock_cache_cls,
            patch("painpoint_miner.analysis.pipeline.Checkpoint") as mock_checkpoint_cls,
        ):
            mock_cache = AsyncMock()
            mock_cache.cleanup_expired = AsyncMock(return_value=0)
            mock_cache_cls.return_value = mock_cache

            mock_checkpoint = AsyncMock()
            mock_checkpoint.load_latest = AsyncMock(return_value=None)
            mock_checkpoint.save = AsyncMock()
            mock_checkpoint_cls.return_value = mock_checkpoint

            await pipeline.run(config)

        saved_state = mock_checkpoint.save.call_args[0][0]
        assert saved_state["phase"] == "complete"
        assert saved_state["keywords"] == ["测试"]
        assert saved_state["platforms"] == ["xiaohongshu"]
        assert saved_state["posts_scraped"] == 0
        assert saved_state["pain_points_found"] == 0

    @pytest.mark.asyncio
    async def test_run_multiple_platforms(self, mock_deps, sample_raw_post):
        """使用多个平台时，pipeline 应从每个平台进行抓取。"""
        from painpoint_miner.analysis.pipeline import AnalysisPipeline

        post = sample_raw_post

        mock_scraper = AsyncMock()
        mock_scraper.__aenter__ = AsyncMock(return_value=mock_scraper)
        mock_scraper.__aexit__ = AsyncMock(return_value=False)
        mock_scraper.search_posts = MagicMock(
            return_value=_async_generator([post])
        )
        mock_deps["registry"].get_scraper = AsyncMock(return_value=mock_scraper)
        mock_deps["anonymizer"].anonymize_post = MagicMock(return_value=post)

        pipeline = AnalysisPipeline(**mock_deps)
        config = PipelineConfig(
            keywords=["测试"],
            platforms=[Platform.XIAOHONGSHU, Platform.WEIBO],
            max_posts_per_keyword=10,
            analysis_mode=AnalysisMode.MERGED,
        )

        with (
            patch("painpoint_miner.analysis.pipeline.run_migrations", new_callable=AsyncMock),
            patch("painpoint_miner.analysis.pipeline.Cache") as mock_cache_cls,
            patch("painpoint_miner.analysis.pipeline.Checkpoint") as mock_checkpoint_cls,
        ):
            mock_cache = AsyncMock()
            mock_cache.cleanup_expired = AsyncMock(return_value=0)
            mock_cache.is_scraped = AsyncMock(return_value=False)
            mock_cache_cls.return_value = mock_cache

            mock_checkpoint = AsyncMock()
            mock_checkpoint.load_latest = AsyncMock(return_value=None)
            mock_checkpoint.save = AsyncMock()
            mock_checkpoint_cls.return_value = mock_checkpoint

            report = await pipeline.run(config)

        assert mock_deps["registry"].get_scraper.call_count == 2
        assert "xiaohongshu" in report.platform_breakdown
        assert "weibo" in report.platform_breakdown


# ===================================================================
# ClaudeProvider — _parse_json_response tests
# ===================================================================


class TestParseJsonResponse:
    """ClaudeProvider._parse_json_response() 静态方法测试。"""

    def test_valid_json_array(self):
        """有效的 JSON 数组应原样返回。"""
        from painpoint_miner.llm.claude_provider import ClaudeProvider

        text = '[{"description": "按钮找不到", "pain_type": "ux_problem"}]'
        result = ClaudeProvider._parse_json_response(text)
        assert len(result) == 1
        assert result[0]["description"] == "按钮找不到"

    def test_valid_json_object_wrapped_in_list(self):
        """有效的 JSON 对象应包装在一个列表中。"""
        from painpoint_miner.llm.claude_provider import ClaudeProvider

        text = '{"description": "加载太慢", "pain_type": "performance"}'
        result = ClaudeProvider._parse_json_response(text)
        assert len(result) == 1
        assert result[0]["description"] == "加载太慢"

    def test_json_in_markdown_code_block(self):
        """JSON 包裹在 markdown 代码块中时应正确提取。"""
        from painpoint_miner.llm.claude_provider import ClaudeProvider

        text = '```json\n[{"description": "价格太高", "pain_type": "pricing"}]\n```'
        result = ClaudeProvider._parse_json_response(text)
        assert len(result) == 1
        assert result[0]["pain_type"] == "pricing"

    def test_json_in_markdown_code_block_no_language(self):
        """不带语言说明符的 JSON 包裹在 markdown 代码块中时应正确提取。"""
        from painpoint_miner.llm.claude_provider import ClaudeProvider

        text = '```\n[{"description": "bug崩溃"}]\n```'
        result = ClaudeProvider._parse_json_response(text)
        assert len(result) == 1
        assert result[0]["description"] == "bug崩溃"

    def test_json_embedded_in_text(self):
        """JSON 数组嵌入在周围文本中时，应通过 regex 提取。"""
        from painpoint_miner.llm.claude_provider import ClaudeProvider

        text = 'Here is the analysis:\n[{"a": 1}]\nEnd of analysis.'
        result = ClaudeProvider._parse_json_response(text)
        assert len(result) == 1
        assert result[0]["a"] == 1

    def test_invalid_json_returns_empty_list(self):
        """无效的 JSON 应返回一个空列表。"""
        from painpoint_miner.llm.claude_provider import ClaudeProvider

        result = ClaudeProvider._parse_json_response("this is not json at all")
        assert result == []

    def test_empty_string_returns_empty_list(self):
        """空字符串应返回一个空列表。"""
        from painpoint_miner.llm.claude_provider import ClaudeProvider

        result = ClaudeProvider._parse_json_response("")
        assert result == []

    def test_whitespace_only_returns_empty_list(self):
        """只包含空格的字符串应返回一个空列表。"""
        from painpoint_miner.llm.claude_provider import ClaudeProvider

        result = ClaudeProvider._parse_json_response("   \n\t  ")
        assert result == []

    def test_multiple_items_in_array(self):
        """包含多个对象的 JSON 数组应全部返回。"""
        from painpoint_miner.llm.claude_provider import ClaudeProvider

        text = json.dumps([
            {"description": "问题A"},
            {"description": "问题B"},
            {"description": "问题C"},
        ])
        result = ClaudeProvider._parse_json_response(text)
        assert len(result) == 3

    def test_nested_json_in_markdown(self):
        """JSON 包裹在带有嵌套内容的代码块中。"""
        from painpoint_miner.llm.claude_provider import ClaudeProvider

        payload = [{"key": "value", "nested": {"a": 1}}]
        text = f"```json\n{json.dumps(payload)}\n```"
        result = ClaudeProvider._parse_json_response(text)
        assert result[0]["nested"]["a"] == 1


# ===================================================================
# ClaudeProvider — __init__ tests
# ===================================================================


class TestClaudeProviderInit:
    """ClaudeProvider.__init__() 的测试。"""

    def test_init_with_api_key(self):
        """初始化时，应存储 api_key、model，且 client 应为 None。"""
        from painpoint_miner.llm.claude_provider import ClaudeProvider

        provider = ClaudeProvider(api_key="sk-test-key-123")
        assert provider._api_key == "sk-test-key-123"
        assert provider._model == "claude-haiku-4-5-20251001"
        assert provider._client is None
        assert provider._cost_tracker is None

    def test_init_with_custom_model(self):
        """使用自定义模型名称进行初始化。"""
        from painpoint_miner.llm.claude_provider import ClaudeProvider

        provider = ClaudeProvider(api_key="sk-test", model="claude-sonnet-4-20250514")
        assert provider._model == "claude-sonnet-4-20250514"

    def test_init_with_cost_tracker(self):
        """使用 CostTracker 实例进行初始化。"""
        from painpoint_miner.llm.claude_provider import ClaudeProvider

        tracker = MagicMock()
        provider = ClaudeProvider(api_key="sk-test", cost_tracker=tracker)
        assert provider._cost_tracker is tracker


# ===================================================================
# MockLLMProvider tests
# ===================================================================


class TestMockLLMProvider:
    """MockLLMProvider 的测试。"""

    @pytest.mark.asyncio
    async def test_default_behavior(self):
        """默认 MockLLMProvider 应返回一个带有示例痛点的列表。"""
        from painpoint_miner.llm.claude_provider import MockLLMProvider

        provider = MockLLMProvider()
        # Pass a single post to get one result
        result = await provider.extract_pain_points([{"content": "test"}])

        assert len(result) == 1
        assert result[0]["has_pain_point"] is True
        assert len(result[0]["pain_points"]) == 1
        assert result[0]["pain_points"][0]["pain_type"] == "ux_problem"

    @pytest.mark.asyncio
    async def test_custom_pain_points(self):
        """MockLLMProvider 使用自定义痛点数据时，应返回这些数据。"""
        from painpoint_miner.llm.claude_provider import MockLLMProvider

        custom = [
            {
                "post_index": 0,
                "has_pain_point": True,
                "pain_points": [
                    {
                        "description": "自定义痛点",
                        "pain_type": "performance",
                        "severity": 5,
                    }
                ],
            },
            {
                "post_index": 1,
                "has_pain_point": True,
                "pain_points": [
                    {
                        "description": "另一个痛点",
                        "pain_type": "bug",
                        "severity": 4,
                    }
                ],
            },
        ]

        provider = MockLLMProvider(pain_points=custom)
        result = await provider.extract_pain_points(
            [{"content": "post1"}, {"content": "post2"}]
        )

        assert len(result) == 2
        assert result[0]["pain_points"][0]["description"] == "自定义痛点"
        assert result[1]["pain_points"][0]["description"] == "另一个痛点"

    @pytest.mark.asyncio
    async def test_result_sliced_to_post_count(self):
        """结果应被切片以匹配输入的帖子数量。"""
        from painpoint_miner.llm.claude_provider import MockLLMProvider

        # Default has 1 pain point entry
        provider = MockLLMProvider()
        result = await provider.extract_pain_points(
            [{"content": "a"}, {"content": "b"}, {"content": "c"}]
        )

        # Default only has 1 entry, slicing [:3] gives just 1
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_generate_cluster_label(self):
        """generate_cluster_label 应返回预期的标签字符串。"""
        from painpoint_miner.llm.claude_provider import MockLLMProvider

        provider = MockLLMProvider()
        label = await provider.generate_cluster_label(
            ["按钮找不到", "界面混乱", "操作复杂"]
        )

        assert label == "UI/UX 问题"
        assert isinstance(label, str)

    @pytest.mark.asyncio
    async def test_empty_posts_returns_empty(self):
        """当传入空列表时，MockLLMProvider 应返回空结果。"""
        from painpoint_miner.llm.claude_provider import MockLLMProvider

        provider = MockLLMProvider()
        result = await provider.extract_pain_points([])
        assert result == []
