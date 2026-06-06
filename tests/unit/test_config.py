"""配置加载单元测试。"""

import pytest
from pathlib import Path

from painpoint_miner.config.settings import (
    AnalysisConfig,
    DedupConfig,
    PrivacyConfig,
    RateLimitConfig,
    ScrapingConfig,
    Settings,
    load_settings,
)
from painpoint_miner.models.enums import AnalysisMode, Platform


class TestScrapingConfig:
    def test_defaults(self):
        cfg = ScrapingConfig()
        assert Platform.XIAOHONGSHU in cfg.platforms
        assert cfg.max_posts_per_keyword == 100
        assert cfg.rate_limit.global_daily_limit == 5000


class TestAnalysisConfig:
    def test_defaults(self):
        cfg = AnalysisConfig()
        assert cfg.mode == AnalysisMode.MERGED
        assert cfg.batch_size == 15
        assert cfg.embedding.model == "intfloat/multilingual-e5-large"
        assert cfg.dedup.similarity_threshold == 0.9


class TestPrivacyConfig:
    def test_defaults(self):
        cfg = PrivacyConfig()
        assert cfg.anonymize is True
        assert cfg.attribution_mode is False
        assert cfg.retention_days == 30


class TestSettings:
    def test_defaults(self):
        s = Settings()
        assert s.scraping.max_posts_per_keyword == 100
        assert s.privacy.anonymize is True
        assert s.tikhub_api_key == ""

    def test_api_keys_default_empty(self):
        s = Settings()
        assert s.tikhub_api_key == ""
        assert s.twitter_bearer_token == ""
        assert s.anthropic_api_key == ""

    def test_load_settings_no_file(self):
        """无配置文件时使用默认值。"""
        s = load_settings()
        assert s.scraping.max_posts_per_keyword == 100


class TestDedupConfig:
    def test_threshold_bounds(self):
        DedupConfig(similarity_threshold=0.0)
        DedupConfig(similarity_threshold=1.0)
        with pytest.raises(Exception):
            DedupConfig(similarity_threshold=-0.1)
        with pytest.raises(Exception):
            DedupConfig(similarity_threshold=1.1)
