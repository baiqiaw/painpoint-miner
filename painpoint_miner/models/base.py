"""PainPoint Miner - 核心数据模型。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .enums import AnalysisMode, PainType, Platform, Sentiment, Severity


class RawPost(BaseModel):
    """通用帖子模型 — 所有平台抓取结果的统一格式。"""

    platform: Platform
    post_id: str
    author_id: str  # 匿名化后为加盐哈希
    author_name: str = ""  # 匿名化后为空
    content: str
    title: str = ""
    url: str = ""
    timestamp: Optional[datetime] = None
    likes: int = 0
    comments_count: int = 0
    shares: int = 0
    media_urls: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    extra: dict = Field(default_factory=dict)


class RawComment(BaseModel):
    """通用评论模型。"""

    platform: Platform
    comment_id: str
    post_id: str
    author_id: str  # 匿名化后为加盐哈希
    author_name: str = ""  # 匿名化后为空
    content: str
    timestamp: Optional[datetime] = None
    likes: int = 0
    parent_comment_id: Optional[str] = None
    extra: dict = Field(default_factory=dict)


class PainPoint(BaseModel):
    """痛点分析结果。"""

    id: str
    source_post_ids: list[str] = Field(default_factory=list)
    platforms: list[Platform] = Field(default_factory=list)
    description: str
    pain_type: PainType = PainType.OTHER
    severity: Severity = Severity.MODERATE
    sentiment_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    sentiment_label: Sentiment = Sentiment.NEUTRAL
    frequency: int = 1
    topic_cluster_id: Optional[int] = None
    evidence_quotes: list[str] = Field(default_factory=list)
    user_demographics: Optional[dict] = None
    extracted_at: datetime = Field(default_factory=datetime.now)


class TopicCluster(BaseModel):
    """聚类主题。"""

    id: int
    label: str
    pain_point_ids: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    size: int = 0


class CostSummary(BaseModel):
    """LLM 调用成本汇总。"""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_calls: int = 0
    estimated_cost_usd: float = 0.0
    model_used: str = ""


class PipelineConfig(BaseModel):
    """流水线运行配置。"""

    keywords: list[str]
    platforms: list[Platform]
    max_posts_per_keyword: int = 100
    max_comments_per_post: int = 50
    analysis_mode: AnalysisMode = AnalysisMode.MERGED
    llm_model: str = "claude-haiku-4-5-20251001"
    dedup_threshold: float = Field(default=0.9, ge=0.0, le=1.0)
    max_llm_budget_usd: Optional[float] = None
    output_dir: str = "./output"
    output_formats: list[str] = Field(default_factory=lambda: ["markdown", "json", "excel"])


class AnalysisReport(BaseModel):
    """完整分析报告。"""

    query_keywords: list[str]
    scrape_timestamp: datetime = Field(default_factory=datetime.now)
    total_posts_scraped: int = 0
    total_comments_scraped: int = 0
    pain_points: list[PainPoint] = Field(default_factory=list)
    topic_clusters: list[TopicCluster] = Field(default_factory=list)
    summary: str = ""
    platform_breakdown: dict[str, int] = Field(default_factory=dict)
    cost_summary: Optional[CostSummary] = None
