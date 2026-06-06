"""工具函数单元测试。"""

import asyncio
import time

import pytest

from painpoint_miner.utils.text import (
    clean_html,
    clean_whitespace,
    detect_language,
    normalize_text,
    remove_emoji,
    truncate,
)
from painpoint_miner.utils.rate_limiter import RateLimiter
from painpoint_miner.utils.cost import BudgetExceededError, CostTracker


class TestTextUtils:
    """文本处理工具测试。"""

    def test_clean_html_basic(self):
        assert clean_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_clean_html_entities(self):
        assert clean_html("A &amp; B &lt; C") == "A & B < C"

    def test_clean_whitespace(self):
        assert clean_whitespace("hello   world\n\nfoo") == "hello world foo"

    def test_remove_emoji(self):
        text = "太开心了 😊 今天天气很好 ☀️"
        result = remove_emoji(text)
        assert "😊" not in result
        assert "太开心了" in result
        assert "今天天气很好" in result

    def test_normalize_text(self):
        text = "<p>  测试&nbsp;内容  </p>"
        assert normalize_text(text) == "测试 内容"

    def test_detect_language_chinese(self):
        assert detect_language("这个产品太差了") == "zh"

    def test_detect_language_english(self):
        assert detect_language("This product is terrible") == "en"

    def test_detect_language_mixed(self):
        assert detect_language("这个iPhone不好用") == "mixed"

    def test_detect_language_empty(self):
        assert detect_language("") == "unknown"

    def test_truncate_short(self):
        assert truncate("hello", 10) == "hello"

    def test_truncate_long(self):
        result = truncate("a" * 600, 500)
        assert len(result) == 503  # 500 + "..."
        assert result.endswith("...")


class TestRateLimiter:
    """令牌桶限速器测试。"""

    @pytest.mark.asyncio
    async def test_allows_burst(self):
        """允许突发请求（不超过 burst 容量）。"""
        limiter = RateLimiter(requests_per_minute=60, burst=5)
        start = time.monotonic()
        for _ in range(5):
            await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.5  # 5 次突发应几乎瞬时完成

    @pytest.mark.asyncio
    async def test_blocks_after_burst(self):
        """突发后需要等待。"""
        limiter = RateLimiter(requests_per_minute=60, burst=3)
        for _ in range(3):
            await limiter.acquire()
        # 第 4 次请求应需要等待
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed > 0.5  # 应等待约 1 秒

    @pytest.mark.asyncio
    async def test_context_manager(self):
        limiter = RateLimiter(requests_per_minute=60, burst=10)
        async with limiter:
            pass  # 不应抛异常


class TestCostTracker:
    """成本追踪器测试。"""

    def test_track_single_call(self):
        tracker = CostTracker(model="claude-haiku-4-5-20251001")
        cost = tracker.track(input_tokens=1000, output_tokens=500)
        assert cost > 0
        assert tracker.within_budget()

    def test_total_accumulation(self):
        tracker = CostTracker(model="claude-haiku-4-5-20251001")
        tracker.track(input_tokens=1000, output_tokens=500)
        tracker.track(input_tokens=2000, output_tokens=1000)
        summary = tracker.summary()
        assert summary.total_input_tokens == 3000
        assert summary.total_output_tokens == 1500
        assert summary.total_calls == 2

    def test_budget_exceeded(self):
        tracker = CostTracker(budget=0.001, model="claude-haiku-4-5-20251001")
        # 一次大额调用超出预算
        tracker.track(input_tokens=100_000, output_tokens=50_000)
        assert not tracker.within_budget()

    def test_budget_exceeded_raises(self):
        tracker = CostTracker(budget=0.001, model="claude-haiku-4-5-20251001")
        tracker.track(input_tokens=100_000, output_tokens=50_000)
        with pytest.raises(BudgetExceededError) as exc_info:
            tracker.check_and_raise()
        assert exc_info.value.budget == 0.001
        assert exc_info.value.spent > 0.001

    def test_no_budget_limit(self):
        tracker = CostTracker(budget=None)
        tracker.track(input_tokens=1_000_000, output_tokens=500_000)
        assert tracker.within_budget()  # 无限制始终返回 True

    def test_summary_to_dict(self):
        tracker = CostTracker(model="claude-haiku-4-5-20251001")
        tracker.track(input_tokens=1000, output_tokens=500)
        d = tracker.summary().to_dict()
        assert "total_calls" in d
        assert "estimated_cost_usd" in d
