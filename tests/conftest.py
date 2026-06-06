"""测试配置和共享 fixtures。"""

import asyncio
import os
import sys
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest

# Windows asyncio 兼容性
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """临时 SQLite 数据库路径。"""
    return tmp_path / "test.db"


@pytest.fixture
def sample_raw_post():
    """示例 RawPost。"""
    from painpoint_miner.models import Platform, RawPost

    return RawPost(
        platform=Platform.XIAOHONGSHU,
        post_id="xhs_12345",
        author_id="user_original_001",
        author_name="测试用户A",
        content="这个产品太难用了，按钮找不到在哪里",
        title="吐槽一下某产品",
        likes=42,
        comments_count=15,
        shares=3,
        hashtags=["吐槽", "难用"],
    )


@pytest.fixture
def sample_raw_comment():
    """示例 RawComment。"""
    from painpoint_miner.models import Platform, RawComment

    return RawComment(
        platform=Platform.XIAOHONGSHU,
        comment_id="comment_001",
        post_id="xhs_12345",
        author_id="user_original_002",
        author_name="测试用户B",
        content="我也觉得，设计太差了",
        likes=5,
    )


@pytest.fixture
def sample_pain_point():
    """示例 PainPoint。"""
    from painpoint_miner.models import PainPoint, PainType, Platform, Sentiment, Severity

    return PainPoint(
        id="pp_001",
        source_post_ids=["xhs_12345"],
        platforms=[Platform.XIAOHONGSHU],
        description="按钮位置不明显，用户难以找到功能入口",
        pain_type=PainType.UX_PROBLEM,
        severity=Severity.MAJOR,
        sentiment_score=-0.7,
        sentiment_label=Sentiment.NEGATIVE,
        frequency=15,
        evidence_quotes=["这个产品太难用了，按钮找不到在哪里"],
    )
