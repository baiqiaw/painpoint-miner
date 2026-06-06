"""SQLite 缓存 — 增量抓取去重。"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite

from ..models.base import RawComment, RawPost
from ..models.enums import Platform

logger = logging.getLogger("painpoint_miner")


class Cache:
    """抓取结果缓存。

    - WAL 模式并发安全
    - 自动清理过期数据
    - 仅存储匿名化后的数据
    """

    def __init__(self, db_path: Path):
        self._db_path = db_path

    async def _get_db(self) -> aiosqlite.Connection:
        db = await aiosqlite.connect(self._db_path)
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
        return db

    async def is_scraped(self, platform: Platform, post_id: str) -> bool:
        """检查帖子是否已抓取。"""
        db = await self._get_db()
        try:
            cursor = await db.execute(
                "SELECT 1 FROM scraped_posts WHERE platform = ? AND post_id = ?",
                (platform.value, post_id),
            )
            row = await cursor.fetchone()
            return row is not None
        finally:
            await db.close()

    async def save_post(self, post: RawPost) -> None:
        """缓存匿名化后的帖子。"""
        db = await self._get_db()
        try:
            await db.execute(
                """
                INSERT OR REPLACE INTO scraped_posts
                    (platform, post_id, author_hash, content, title, url,
                     timestamp, likes, comments_count, shares, scraped_at, extra)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    post.platform.value,
                    post.post_id,
                    post.author_id,  # 已匿名化为哈希
                    post.content,
                    post.title,
                    post.url,
                    post.timestamp.isoformat() if post.timestamp else None,
                    post.likes,
                    post.comments_count,
                    post.shares,
                    datetime.now().isoformat(),
                    json.dumps(post.extra),
                ),
            )
            await db.commit()
        finally:
            await db.close()

    async def save_comment(self, comment: RawComment) -> None:
        """缓存匿名化后的评论。"""
        db = await self._get_db()
        try:
            await db.execute(
                """
                INSERT OR REPLACE INTO scraped_comments
                    (platform, comment_id, post_id, author_hash, content,
                     timestamp, likes, scraped_at, extra)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    comment.platform.value,
                    comment.comment_id,
                    comment.post_id,
                    comment.author_id,
                    comment.content,
                    comment.timestamp.isoformat() if comment.timestamp else None,
                    comment.likes,
                    datetime.now().isoformat(),
                    json.dumps(comment.extra),
                ),
            )
            await db.commit()
        finally:
            await db.close()

    async def filter_new_posts(
        self, posts: list[RawPost]
    ) -> list[RawPost]:
        """过滤掉已缓存的帖子。"""
        new_posts = []
        for post in posts:
            if not await self.is_scraped(post.platform, post.post_id):
                new_posts.append(post)
        return new_posts

    async def cleanup_expired(self, retention_days: int = 30) -> int:
        """清理过期缓存数据。

        Returns:
            删除的记录数。
        """
        db = await self._get_db()
        try:
            cursor = await db.execute(
                """
                DELETE FROM scraped_posts
                WHERE scraped_at < datetime('now', ?)
                """,
                (f"-{retention_days} days",),
            )
            posts_deleted = cursor.rowcount

            cursor = await db.execute(
                """
                DELETE FROM scraped_comments
                WHERE scraped_at < datetime('now', ?)
                """,
                (f"-{retention_days} days",),
            )
            comments_deleted = cursor.rowcount

            await db.commit()
            total = posts_deleted + comments_deleted
            if total > 0:
                logger.info(
                    "Cleaned up %d expired records (retention: %d days)",
                    total,
                    retention_days,
                )
            return total
        finally:
            await db.close()
