"""Markdown 分类报告导出。"""

from datetime import datetime
from pathlib import Path

from ..models.base import AnalysisReport
from .base import BaseExporter


REPORT_TEMPLATE = """# 用户痛点分析报告

## 基本信息

| 项目 | 值 |
|------|-----|
| **查询关键词** | {keywords} |
| **分析时间** | {timestamp} |
| **抓取帖子总数** | {total_posts} |
| **发现痛点数** | {total_pain_points} |
| **主题类别数** | {total_clusters} |

## 平台分布

{platform_table}

## 分析摘要

{summary}

## 主题聚类

{clusters_section}

## 痛点详情

{pain_points_section}

---

*本报告由 PainPoint Miner 自动生成*
*⚠️ 数据来源：{data_source_disclaimer}*
"""


class MarkdownExporter(BaseExporter):
    """Markdown 报告导出器。"""

    @property
    def format_name(self) -> str:
        return "markdown"

    async def export(self, report: AnalysisReport, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        keywords = "、".join(report.query_keywords)
        timestamp = report.scrape_timestamp.strftime("%Y-%m-%d %H:%M:%S")
        total_posts = report.total_posts_scraped
        total_pain_points = len(report.pain_points)
        total_clusters = len(report.topic_clusters)
        summary = report.summary or "无摘要"

        # 平台分布表
        platform_rows = []
        for platform, count in report.platform_breakdown.items():
            platform_rows.append(f"| {platform} | {count} |")
        platform_table = "| 平台 | 帖子数 |\n|------|--------|\n" + "\n".join(
            platform_rows
        ) if platform_rows else "无数据"

        # 聚类部分
        clusters_section = ""
        for cluster in report.topic_clusters:
            clusters_section += f"### 簇 {cluster.id}: {cluster.label}\n"
            clusters_section += f"- **大小**: {cluster.size} 个痛点\n"
            clusters_section += f"- **关键词**: {', '.join(cluster.keywords)}\n\n"

        # 痛点详情
        pain_points_section = ""
        for i, pp in enumerate(report.pain_points, 1):
            pain_points_section += f"### {i}. {pp.description}\n"
            pain_points_section += f"- **类型**: {pp.pain_type.value}\n"
            pain_points_section += f"- **严重度**: {'⭐' * pp.severity.value} ({pp.severity.value}/5)\n"
            pain_points_section += f"- **情感**: {pp.sentiment_label.value} ({pp.sentiment_score:.2f})\n"
            pain_points_section += f"- **频率**: {pp.frequency} 次\n"
            pain_points_section += f"- **平台**: {', '.join(p.value for p in pp.platforms)}\n"
            if pp.evidence_quotes:
                for quote in pp.evidence_quotes:
                    pain_points_section += f'> "{quote}"\n'
            pain_points_section += "\n"

        content = REPORT_TEMPLATE.format(
            keywords=keywords,
            timestamp=timestamp,
            total_posts=total_posts,
            total_pain_points=total_pain_points,
            total_clusters=total_clusters,
            platform_table=platform_table,
            summary=summary,
            clusters_section=clusters_section or "未形成有效聚类",
            pain_points_section=pain_points_section or "未发现痛点",
            data_source_disclaimer="Data obtained via TikHub API / Twitter API. User assumes responsibility for verifying data source legality.",
        )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return output_path
