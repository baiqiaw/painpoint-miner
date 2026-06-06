"""SQLite Schema 迁移管理。"""

import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger("painpoint_miner")

# 迁移脚本列表（按版本号顺序）
MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scraped_posts (
            platform TEXT NOT NULL,
            post_id TEXT NOT NULL,
            author_hash TEXT NOT NULL,
            content TEXT NOT NULL,
            title TEXT DEFAULT '',
            url TEXT DEFAULT '',
            timestamp TEXT,
            likes INTEGER DEFAULT 0,
            comments_count INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            scraped_at TEXT NOT NULL,
            extra TEXT DEFAULT '{}',
            PRIMARY KEY (platform, post_id)
        );

        CREATE TABLE IF NOT EXISTS scraped_comments (
            platform TEXT NOT NULL,
            comment_id TEXT NOT NULL,
            post_id TEXT NOT NULL,
            author_hash TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT,
            likes INTEGER DEFAULT 0,
            scraped_at TEXT NOT NULL,
            extra TEXT DEFAULT '{}',
            PRIMARY KEY (platform, comment_id)
        );

        CREATE TABLE IF NOT EXISTS tos_acceptance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            accepted_at TEXT NOT NULL,
            platforms TEXT NOT NULL,
            tos_version_hash TEXT NOT NULL,
            accepted INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS checkpoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            state TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_posts_scraped_at
            ON scraped_posts(scraped_at);
        CREATE INDEX IF NOT EXISTS idx_comments_scraped_at
            ON scraped_comments(scraped_at);
        """,
    ),
]


async def get_current_version(db: aiosqlite.Connection) -> int:
    """获取当前 schema 版本。"""
    try:
        cursor = await db.execute(
            "SELECT MAX(version) FROM schema_version"
        )
        row = await cursor.fetchone()
        return row[0] if row[0] is not None else 0
    except aiosqlite.OperationalError:
        return 0


async def run_migrations(db_path: Path) -> list[int]:
    """执行所有待运行的迁移。

    Returns:
        已应用的迁移版本号列表。
    """
    applied: list[int] = []

    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")

        current = await get_current_version(db)

        for version, sql in MIGRATIONS:
            if version > current:
                logger.info("Applying migration v%d", version)
                await db.executescript(sql)
                await db.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, datetime('now'))",
                    (version,),
                )
                await db.commit()
                applied.append(version)
                logger.info("Migration v%d applied", version)

    return applied
