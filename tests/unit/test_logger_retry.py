"""Logger 和 Retry 工具单元测试。"""

import logging

import pytest


class TestLogger:
    """get_logger 测试。"""

    def test_returns_logger(self):
        """返回 Logger 实例。"""
        from painpoint_miner.utils.logger import get_logger

        result = get_logger("test_logger_unit")
        assert isinstance(result, logging.Logger)
        assert result.name == "test_logger_unit"

    def test_logger_has_handler(self):
        """Logger 有 handler。"""
        from painpoint_miner.utils.logger import get_logger

        logger = get_logger("test_handler_check")
        assert len(logger.handlers) > 0

    def test_returns_same_logger_on_repeat_call(self):
        """重复调用返回同一个 logger。"""
        from painpoint_miner.utils.logger import get_logger

        l1 = get_logger("test_idempotent")
        l2 = get_logger("test_idempotent")
        assert l1 is l2

    def test_default_level_info(self):
        """默认日志级别为 INFO。"""
        from painpoint_miner.utils.logger import get_logger

        logger = get_logger("test_level_default")
        assert logger.level == logging.INFO

    def test_custom_level(self):
        """可设置自定义日志级别。"""
        from painpoint_miner.utils.logger import get_logger

        logger = get_logger("test_level_custom", level=logging.DEBUG)
        assert logger.level == logging.DEBUG

    def test_module_logger_exists(self):
        """模块级 logger 已创建。"""
        from painpoint_miner.utils import logger as logger_module

        assert logger_module.logger is not None
        assert isinstance(logger_module.logger, logging.Logger)


class TestRetry:
    """with_retry 装饰器测试。"""

    @pytest.mark.asyncio
    async def test_no_retry_on_success(self):
        """成功时不重试。"""
        from painpoint_miner.utils.retry import with_retry

        call_count = 0

        @with_retry(max_attempts=3)
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await success_func()
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_failure_then_success(self):
        """失败后重试成功。"""
        from painpoint_miner.utils.retry import with_retry

        call_count = 0

        @with_retry(max_attempts=3, base_wait=0.01, max_wait=0.1)
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("temporary")
            return "recovered"

        result = await flaky_func()
        assert result == "recovered"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        """重试耗尽后抛出 RetryError（包装原始异常）。"""
        from tenacity import RetryError
        from painpoint_miner.utils.retry import with_retry

        @with_retry(max_attempts=2, base_wait=0.01, max_wait=0.1, retry_on=(ValueError,))
        async def always_fail():
            raise ValueError("persistent")

        with pytest.raises(RetryError):
            await always_fail()

    @pytest.mark.asyncio
    async def test_retry_specific_exception_type(self):
        """仅重试指定类型的异常。"""
        from painpoint_miner.utils.retry import with_retry

        call_count = 0

        @with_retry(max_attempts=3, base_wait=0.01, retry_on=(ConnectionError,))
        async def type_error_func():
            nonlocal call_count
            call_count += 1
            raise TypeError("wrong type")

        with pytest.raises(TypeError):
            await type_error_func()

        # TypeError 不在 retry_on 中，不重试
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_preserves_function_name(self):
        """装饰器保留原函数名。"""
        from painpoint_miner.utils.retry import with_retry

        @with_retry()
        async def my_function():
            pass

        assert my_function.__name__ == "my_function"
