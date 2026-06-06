"""JSON 结构化导出。"""

import json
from pathlib import Path

from ..models.base import AnalysisReport
from .base import BaseExporter


class JsonExporter(BaseExporter):
    """JSON 导出器。使用 Pydantic 的 JSON 序列化。"""

    @property
    def format_name(self) -> str:
        return "json"

    async def export(self, report: AnalysisReport, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        data = json.loads(report.model_dump_json())
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return output_path
