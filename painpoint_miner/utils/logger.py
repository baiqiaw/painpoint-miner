"""结构化日志配置。"""

import logging
import sys

from rich.logging import RichHandler


def get_logger(name: str = "painpoint_miner", level: int = logging.INFO) -> logging.Logger:
    """获取带 Rich 格式化的 logger。"""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    handler = RichHandler(
        console=console if "_rich_console" in dir() else None,
        show_time=True,
        show_path=False,
        markup=True,
    )
    handler.setLevel(level)
    logger.addHandler(handler)
    logger.setLevel(level)
    return logger


# 模块级 logger
logger = get_logger()
