"""LLM 和分析组件单元测试。"""

import pytest

from painpoint_miner.llm.claude_provider import ClaudeProvider, MockLLMProvider
from painpoint_miner.llm.prompt_templates import (
    format_items_block,
    format_posts_block,
)
from painpoint_miner.analysis.extractor import PainPointExtractor
from painpoint_miner.models import (
    PainPoint,
    PainType,
    Platform,
    RawPost,
    Sentiment,
    Severity,
)


class TestPromptTemplates:
    """Prompt 模板测试。"""

    def test_format_posts_block(self):
        posts = [
            {"platform": "xiaohongshu", "content": "太难用了", "title": "吐槽", "likes": 42, "comments_count": 10},
            {"platform": "weibo", "content": "客服不回复", "likes": 100},
        ]
        block = format_posts_block(posts)
        assert "### 帖子 0" in block
        assert "### 帖子 1" in block
        assert "xiaohongshu" in block
        assert "太难用了" in block
        assert "吐槽" in block

    def test_format_items_block(self):
        items = ["痛点A", "痛点B"]
        block = format_items_block(items)
        assert "0. 痛点A" in block
        assert "1. 痛点B" in block


class TestMockLLMProvider:
    """MockLLMProvider 测试。"""

    @pytest.mark.asyncio
    async def test_extract_pain_points(self):
        provider = MockLLMProvider()
        results = await provider.extract_pain_points(
            [{"content": "test", "platform": "test"}]
        )
        assert len(results) == 1
        assert results[0]["has_pain_point"] is True
        assert len(results[0]["pain_points"]) == 1

    @pytest.mark.asyncio
    async def test_generate_cluster_label(self):
        provider = MockLLMProvider()
        label = await provider.generate_cluster_label(["描述1", "描述2"])
        assert label == "UI/UX 问题"

    @pytest.mark.asyncio
    async def test_custom_pain_points(self):
        custom = [
            {
                "post_index": 0,
                "has_pain_point": True,
                "pain_points": [
                    {"description": "自定义痛点", "pain_type": "bug", "severity": 5}
                ],
            }
        ]
        provider = MockLLMProvider(pain_points=custom)
        results = await provider.extract_pain_points([{"content": "test"}])
        assert results[0]["pain_points"][0]["description"] == "自定义痛点"


class TestClaudeProviderJsonParsing:
    """LLM JSON 解析测试（共享 parse_llm_json_response）。"""

    def test_parse_clean_json(self):
        from painpoint_miner.llm.utils import parse_llm_json_response

        text = '[{"post_index": 0, "has_pain_point": true, "pain_points": []}]'
        result = parse_llm_json_response(text)
        assert len(result) == 1
        assert result[0]["post_index"] == 0

    def test_parse_json_with_markdown(self):
        from painpoint_miner.llm.utils import parse_llm_json_response

        text = '```json\n[{"post_index": 0, "has_pain_point": true, "pain_points": []}]\n```'
        result = parse_llm_json_response(text)
        assert len(result) == 1

    def test_parse_json_embedded_in_text(self):
        from painpoint_miner.llm.utils import parse_llm_json_response

        text = 'Here are the results:\n[{"post_index": 0, "has_pain_point": true, "pain_points": []}]\nDone.'
        result = parse_llm_json_response(text)
        assert len(result) == 1

    def test_parse_invalid_json_returns_empty(self):
        from painpoint_miner.llm.utils import parse_llm_json_response

        text = "This is not JSON at all"
        result = parse_llm_json_response(text)
        assert result == []


class TestPainPointExtractor:
    """痛点提取器测试。"""

    @pytest.mark.asyncio
    async def test_extract_with_mock(self):
        mock_llm = MockLLMProvider()
        extractor = PainPointExtractor(llm=mock_llm, batch_size=10)

        posts = [
            RawPost(
                platform=Platform.XIAOHONGSHU,
                post_id="xhs_001",
                author_id="h1",
                content="太难用了",
            ),
        ]

        results = await extractor.extract(posts, mode="merged")
        assert len(results) >= 1
        assert results[0].description != ""
        assert results[0].source_post_ids[0] == "xhs_001"

    @pytest.mark.asyncio
    async def test_extract_empty_posts(self):
        mock_llm = MockLLMProvider()
        extractor = PainPointExtractor(llm=mock_llm)

        results = await extractor.extract([], mode="merged")
        assert results == []

    @pytest.mark.asyncio
    async def test_extract_id_increments(self):
        mock_llm = MockLLMProvider()
        extractor = PainPointExtractor(llm=mock_llm)

        posts = [
            RawPost(
                platform=Platform.WEIBO,
                post_id="wb_001",
                author_id="h1",
                content="test",
            ),
        ]

        r1 = await extractor.extract(posts)
        r2 = await extractor.extract(posts)
        # ID 应递增
        assert r2[0].id != r1[0].id
