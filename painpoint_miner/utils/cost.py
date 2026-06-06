"""LLM 调用成本追踪与预算强制执行。"""

from dataclasses import dataclass, field


class BudgetExceededError(Exception):
    """LLM 调用超出预算时抛出。"""

    def __init__(self, spent: float, budget: float):
        self.spent = spent
        self.budget = budget
        super().__init__(
            f"LLM budget exceeded: spent ${spent:.4f}, budget ${budget:.4f}"
        )


@dataclass
class CostSummary:
    """成本汇总（仅聚合指标，不记录 prompt 内容）。"""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_calls: int = 0
    estimated_cost_usd: float = 0.0
    model_used: str = ""

    def to_dict(self) -> dict:
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_calls": self.total_calls,
            "estimated_cost_usd": round(self.estimated_cost_usd, 4),
            "model_used": self.model_used,
        }


# 模型定价（每百万 token）
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
}


class CostTracker:
    """LLM 调用成本追踪器。

    仅记录聚合指标（token 数/金额），不记录 prompt 内容。
    超出预算时通过 check_and_raise() 通知 Pipeline 优雅退出。
    """

    def __init__(self, budget: float | None = None, model: str = ""):
        self._budget = budget
        self._model = model
        self._input_tokens = 0
        self._output_tokens = 0
        self._calls = 0
        self._total_cost = 0.0

    def track(self, input_tokens: int, output_tokens: int, model: str = "") -> float:
        """记录一次 LLM 调用成本。

        Returns:
            本次调用的估算成本（美元）。
        """
        effective_model = model or self._model
        pricing = MODEL_PRICING.get(effective_model, {"input": 1.0, "output": 5.0})

        cost = (
            input_tokens / 1_000_000 * pricing["input"]
            + output_tokens / 1_000_000 * pricing["output"]
        )

        self._input_tokens += input_tokens
        self._output_tokens += output_tokens
        self._calls += 1
        self._total_cost += cost
        self._model = effective_model

        return cost

    def within_budget(self) -> bool:
        """检查是否在预算内。"""
        if self._budget is None:
            return True
        return self._total_cost <= self._budget

    def check_and_raise(self) -> None:
        """超出预算时抛出 BudgetExceededError。

        Pipeline 应捕获此异常，保存 checkpoint 后优雅退出。
        """
        if not self.within_budget():
            raise BudgetExceededError(
                spent=self._total_cost, budget=self._budget
            )

    def summary(self) -> CostSummary:
        """返回成本汇总。"""
        return CostSummary(
            total_input_tokens=self._input_tokens,
            total_output_tokens=self._output_tokens,
            total_calls=self._calls,
            estimated_cost_usd=self._total_cost,
            model_used=self._model,
        )
