"""Playwright 浏览器生命周期管理。"""

import logging
from typing import Optional

from playwright.async_api import Browser, BrowserContext, async_playwright

from ..config.settings import ProxyConfig

logger = logging.getLogger("painpoint_miner")

USER_AGENT = "PainPointMiner/1.0 (+https://github.com/user/painpoint-miner)"


class BrowserManager:
    """Playwright 浏览器生命周期管理（无 stealth，固定 UA）。

    使用 async context manager 管理 Browser 和 Context 生命周期。
    """

    def __init__(self, proxy: Optional[ProxyConfig] = None):
        self._proxy = proxy
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._playwright = None

    async def __aenter__(self) -> "BrowserManager":
        await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.stop()

    async def start(self) -> None:
        """启动浏览器。"""
        self._playwright = await async_playwright().start()

        launch_kwargs: dict = {}
        if self._proxy and self._proxy.enabled and self._proxy.url:
            launch_kwargs["proxy"] = {"server": self._proxy.url}

        self._browser = await self._playwright.chromium.launch(**launch_kwargs)
        self._context = await self._browser.new_context(
            user_agent=USER_AGENT,
            locale="zh-CN",
        )
        logger.info("Browser started with UA: %s", USER_AGENT)

    async def stop(self) -> None:
        """关闭浏览器。"""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser stopped")

    @property
    def context(self) -> BrowserContext:
        """获取浏览器上下文。"""
        if self._context is None:
            raise RuntimeError("Browser not started. Use async with.")
        return self._context
