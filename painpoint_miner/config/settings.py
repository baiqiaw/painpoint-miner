"""配置加载模块 — 支持 YAML + 环境变量 + .env。"""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..models.enums import AnalysisMode, Platform


class RateLimitConfig(BaseSettings):
    """速率限制配置。"""

    tikhub_requests_per_minute: int = 60
    twitter_requests_per_minute: int = 30
    global_daily_limit: int = 5000


class EmbeddingConfig(BaseSettings):
    """嵌入模型配置。"""

    model: str = "intfloat/multilingual-e5-large"


class ClusteringConfig(BaseSettings):
    """聚类配置。"""

    algorithm: str = "hdbscan"
    min_cluster_size: int = 3


class DedupConfig(BaseSettings):
    """去重配置。"""

    similarity_threshold: float = Field(default=0.9, ge=0.0, le=1.0)


class ScrapingConfig(BaseSettings):
    """抓取配置。"""

    platforms: list[Platform] = [
        Platform.XIAOHONGSHU,
        Platform.WEIBO,
        Platform.DOUYIN,
        Platform.ZHIHU,
    ]
    max_posts_per_keyword: int = 100
    max_comments_per_post: int = 50
    scrape_timeout_seconds: int = 300
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)


class AnalysisConfig(BaseSettings):
    """分析配置。"""

    mode: AnalysisMode = AnalysisMode.MERGED
    llm_model: str = "claude-haiku-4-5-20251001"
    batch_size: int = 15
    max_concurrent_llm_requests: int = 5
    max_llm_budget_usd: Optional[float] = 10.0
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    clustering: ClusteringConfig = Field(default_factory=ClusteringConfig)
    dedup: DedupConfig = Field(default_factory=DedupConfig)


class ExportConfig(BaseSettings):
    """导出配置。"""

    output_dir: str = "./output"
    formats: list[str] = Field(
        default_factory=lambda: ["markdown", "json", "excel"]
    )


class PrivacyConfig(BaseSettings):
    """隐私配置。"""

    anonymize: bool = True
    retention_days: int = 30
    attribution_mode: bool = False


class ProxyConfig(BaseSettings):
    """代理配置（单一代理，仅用于地域访问）。"""

    enabled: bool = False
    url: str = ""


class Settings(BaseSettings):
    """PainPoint Miner 全局配置。"""

    model_config = SettingsConfigDict(
        env_prefix="PPM_",
        env_nested_delimiter="__",
        yaml_file="config.yaml",
        yaml_file_encoding="utf-8",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    scraping: ScrapingConfig = Field(default_factory=ScrapingConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)

    # API 密钥 — 仅通过环境变量
    tikhub_api_key: str = Field(default="", alias="PPM_TIKHUB_API_KEY")
    twitter_bearer_token: str = Field(default="", alias="PPM_TWITTER_BEARER_TOKEN")
    anthropic_api_key: str = Field(default="", alias="PPM_ANTHROPIC_API_KEY")
    encryption_passphrase: str = Field(
        default="", alias="PPM_ENCRYPTION_PASSPHRASE"
    )


def load_settings(config_path: Optional[Path] = None) -> Settings:
    """加载配置。

    优先级：环境变量 > .env 文件 > config.yaml > 默认值。
    """
    kwargs: dict = {}
    if config_path and config_path.exists():
        kwargs["yaml_file"] = str(config_path)
    return Settings(**kwargs)
