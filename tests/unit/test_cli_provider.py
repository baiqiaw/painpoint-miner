"""ClaudeCliProvider 单元测试。"""

import json
from unittest.mock import MagicMock, patch

import pytest

from painpoint_miner.llm.claude_cli_provider import ClaudeCliProvider
from painpoint_miner.llm.utils import parse_llm_json_response
from painpoint_miner.utils.cost import CostTracker


class TestClaudeCliProviderInit:
    """初始化测试。"""

    def test_default_values(self):
        provider = ClaudeCliProvider()
        assert provider._cli_command == "claude-glm"
        assert provider._model == "claude-haiku-4-5-20251001"
        assert provider._cost_tracker is None

    def test_custom_values(self):
        tracker = CostTracker(budget=5.0, model="test")
        provider = ClaudeCliProvider(
            cli_command="my-claude",
            model="claude-sonnet-4-6",
            cost_tracker=tracker,
        )
        assert provider._cli_command == "my-claude"
        assert provider._model == "claude-sonnet-4-6"
        assert provider._cost_tracker is tracker


class TestParseJsonResponse:
    """parse_llm_json_response 共享函数测试。"""

    def test_valid_json_array(self):
        text = '[{"a": 1}, {"b": 2}]'
        result = parse_llm_json_response(text)
        assert len(result) == 2

    def test_valid_json_object_wrapped(self):
        text = '{"a": 1}'
        result = parse_llm_json_response(text)
        assert isinstance(result, list)
        assert result[0]["a"] == 1

    def test_json_in_markdown_code_block(self):
        text = '```json\n[{"test": true}]\n```'
        result = parse_llm_json_response(text)
        assert result[0]["test"] is True

    def test_invalid_json_returns_empty(self):
        result = parse_llm_json_response("not json at all")
        assert result == []

    def test_empty_string_returns_empty(self):
        result = parse_llm_json_response("")
        assert result == []


class TestParseResponse:
    """_parse_response 内部方法测试。"""

    def test_parse_valid_json_output(self):
        provider = ClaudeCliProvider()
        raw = json.dumps({
            "type": "result",
            "result": '[{"desc": "test"}]',
            "usage": {"input_tokens": 100, "output_tokens": 50},
        })
        text = provider._parse_response(raw)
        assert text == '[{"desc": "test"}]'

    def test_parse_non_json_fallback(self):
        provider = ClaudeCliProvider()
        text = provider._parse_response("plain text response")
        assert text == "plain text response"

    def test_parse_tracks_cost(self):
        tracker = CostTracker(budget=10.0, model="test")
        provider = ClaudeCliProvider(cost_tracker=tracker)
        raw = json.dumps({
            "result": "hello",
            "usage": {"input_tokens": 1000, "output_tokens": 200},
        })
        provider._parse_response(raw)
        summary = tracker.summary()
        assert summary.total_input_tokens == 1000
        assert summary.total_output_tokens == 200

    def test_parse_without_usage_no_crash(self):
        tracker = CostTracker(budget=10.0, model="test")
        provider = ClaudeCliProvider(cost_tracker=tracker)
        raw = json.dumps({"result": "hello"})
        provider._parse_response(raw)
        summary = tracker.summary()
        assert summary.total_input_tokens == 0


class TestRunSubprocess:
    """_run_subprocess 测试。"""

    @patch("painpoint_miner.llm.claude_cli_provider.subprocess.run")
    def test_success_returns_parsed_text(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "result": "test output",
                "usage": {"input_tokens": 50, "output_tokens": 10},
            }),
        )
        provider = ClaudeCliProvider()
        # 创建临时 prompt 文件
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test prompt")
            path = f.name

        try:
            result = provider._run_subprocess(path)
            assert result == "test output"
        finally:
            Path(path).unlink()

    @patch("painpoint_miner.llm.claude_cli_provider.subprocess.run")
    def test_failure_raises_runtime_error(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="command not found",
        )
        provider = ClaudeCliProvider()
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test")
            path = f.name

        try:
            with pytest.raises(RuntimeError, match="claude-glm CLI failed"):
                provider._run_subprocess(path)
        finally:
            Path(path).unlink()


class TestExtractPainPoints:
    """extract_pain_points 集成测试（mock _call_cli）。"""

    @pytest.mark.asyncio
    async def test_merged_mode(self):
        provider = ClaudeCliProvider()
        response = json.dumps([
            {
                "post_index": 0,
                "has_pain_point": True,
                "pain_points": [
                    {
                        "description": "太难用了",
                        "pain_type": "ux_problem",
                        "severity": 3,
                        "sentiment_score": -0.5,
                        "sentiment_label": "negative",
                        "evidence_quote": "按钮找不到",
                    }
                ],
            }
        ])

        with patch.object(provider, "_call_cli", return_value=response):
            result = await provider.extract_pain_points(
                [{"content": "按钮找不到"}], mode="merged"
            )

        assert len(result) == 1
        assert result[0]["pain_points"][0]["description"] == "太难用了"


class TestIsAvailable:
    """is_available 类方法测试。"""

    @patch("painpoint_miner.llm.claude_cli_provider.subprocess.run")
    def test_available(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert ClaudeCliProvider.is_available() is True

    @patch("painpoint_miner.llm.claude_cli_provider.subprocess.run")
    def test_not_available(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        assert ClaudeCliProvider.is_available() is False

    @patch("painpoint_miner.llm.claude_cli_provider.subprocess.run")
    def test_timeout(self, mock_run):
        import subprocess as sp

        mock_run.side_effect = sp.TimeoutExpired(cmd="test", timeout=10)
        assert ClaudeCliProvider.is_available() is False
