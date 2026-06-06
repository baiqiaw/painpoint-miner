"""存储层单元测试。"""

import pytest
from pathlib import Path

from painpoint_miner.storage.cache import Cache
from painpoint_miner.storage.checkpoint import Checkpoint
from painpoint_miner.storage.migrations import run_migrations, get_current_version
from painpoint_miner.models import Platform, RawComment, RawPost


class TestMigrations:
    """Schema 迁移测试。"""

    @pytest.mark.asyncio
    async def test_fresh_db_gets_v1(self, tmp_db):
        applied = await run_migrations(tmp_db)
        assert 1 in applied

    @pytest.mark.asyncio
    async def test_idempotent(self, tmp_db):
        await run_migrations(tmp_db)
        applied = await run_migrations(tmp_db)
        assert applied == []  # 重复运行不应再次应用


class TestCache:
    """缓存测试。"""

    @pytest.mark.asyncio
    async def test_is_scraped_false_initially(self, tmp_db):
        await run_migrations(tmp_db)
        cache = Cache(tmp_db)
        assert not await cache.is_scraped(Platform.XIAOHONGSHU, "xhs_001")

    @pytest.mark.asyncio
    async def test_save_and_check(self, tmp_db):
        await run_migrations(tmp_db)
        cache = Cache(tmp_db)
        post = RawPost(
            platform=Platform.XIAOHONGSHU,
            post_id="xhs_001",
            author_id="hashed_user_001",
            content="测试内容",
        )
        await cache.save_post(post)
        assert await cache.is_scraped(Platform.XIAOHONGSHU, "xhs_001")

    @pytest.mark.asyncio
    async def test_filter_new_posts(self, tmp_db):
        await run_migrations(tmp_db)
        cache = Cache(tmp_db)
        post1 = RawPost(
            platform=Platform.XIAOHONGSHU,
            post_id="xhs_001",
            author_id="h1",
            content="内容1",
        )
        post2 = RawPost(
            platform=Platform.XIAOHONGSHU,
            post_id="xhs_002",
            author_id="h2",
            content="内容2",
        )
        await cache.save_post(post1)
        new = await cache.filter_new_posts([post1, post2])
        assert len(new) == 1
        assert new[0].post_id == "xhs_002"

    @pytest.mark.asyncio
    async def test_save_comment(self, tmp_db):
        await run_migrations(tmp_db)
        cache = Cache(tmp_db)
        comment = RawComment(
            platform=Platform.WEIBO,
            comment_id="cmt_001",
            post_id="wb_001",
            author_id="h1",
            content="评论内容",
        )
        await cache.save_comment(comment)
        # 评论通过 post_id 关联，不单独检查 is_scraped


class TestCheckpoint:
    """断点续传测试。"""

    @pytest.mark.asyncio
    async def test_save_and_load(self, tmp_db):
        await run_migrations(tmp_db)
        cp = Checkpoint(tmp_db)
        state = {"phase": "scraping", "completed_platforms": ["xiaohongshu"]}
        await cp.save(state)
        loaded = await cp.load_latest()
        assert loaded is not None
        assert loaded["phase"] == "scraping"

    @pytest.mark.asyncio
    async def test_load_empty(self, tmp_db):
        await run_migrations(tmp_db)
        cp = Checkpoint(tmp_db)
        loaded = await cp.load_latest()
        assert loaded is None

    @pytest.mark.asyncio
    async def test_save_and_load_file(self, tmp_path):
        cp = Checkpoint(tmp_path / "dummy.db")  # 不需要实际 db
        file_path = tmp_path / "checkpoint.jsonl"
        state = {"phase": "analysis", "progress": 0.5}
        await cp.save_to_file(state, file_path)
        loaded = await cp.load_from_file(file_path)
        assert loaded is not None
        assert loaded["phase"] == "analysis"
        assert loaded["progress"] == 0.5

    @pytest.mark.asyncio
    async def test_load_missing_file(self, tmp_path):
        cp = Checkpoint(tmp_path / "dummy.db")
        loaded = await cp.load_from_file(tmp_path / "nonexistent.jsonl")
        assert loaded is None
