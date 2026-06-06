"""抽象导出接口。"""

from abc import ABC, abstractmethod
from pathlib import Path

from ..models.base import AnalysisReport


class BaseExporter(ABC):
    """导出器抽象基类。"""

    @abstractmethod
    async def export(self, report: AnalysisReport, output_path: Path) -> Path:
        """将报告导出到指定路径。

        Returns:
            实际输出文件路径。
        """

    @property
    @abstractmethod
    def format_name(self) -> str:
        """导出格式名称。"""
