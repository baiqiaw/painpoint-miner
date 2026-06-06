"""异步令牌桶限速器。"""

import asyncio
import time


class RateLimiter:
    """异步令牌桶限速器。

    支持 per-platform 和全局速率限制。
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst: int = 10,
    ):
        self._rate = requests_per_minute / 60.0  # tokens per second
        self._max_tokens = float(burst)
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        """补充令牌。"""
        now = time.monotonic()
        elapsed = now - self._last_refill
        new_tokens = elapsed * self._rate
        self._tokens = min(self._max_tokens, self._tokens + new_tokens)
        self._last_refill = now

    async def acquire(self) -> None:
        """获取一个令牌，如果没有可用令牌则等待。"""
        async with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return

            # 计算需要等待的时间
            wait_time = (1.0 - self._tokens) / self._rate
            await asyncio.sleep(wait_time)
            self._tokens = 0.0

    async def __aenter__(self) -> "RateLimiter":
        await self.acquire()
        return self

    async def __aexit__(self, *exc: object) -> None:
        pass
