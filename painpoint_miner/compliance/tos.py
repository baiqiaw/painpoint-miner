"""ToS 确认管理 — 持久化到 SQLite，含版本追踪。"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite

from ..models.enums import Platform


class TosAcceptance:
    """服务条款确认管理器。

    将 ToS 接受状态持久化到 SQLite：
    - 时间戳
    - 接受的平台列表
    - ToS 内容版本哈希
    - 用户确认标志
    """

    def __init__(self, db_path: Path):
        self._db_path = db_path

    async def _get_db(self) -> aiosqlite.Connection:
        db = await aiosqlite.connect(self._db_path)
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
        return db

    async def ensure_table(self) -> None:
        """确保 tos_acceptance 表存在。"""
        db = await self._get_db()
        try:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS tos_acceptance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    accepted_at TEXT NOT NULL,
                    platforms TEXT NOT NULL,
                    tos_version_hash TEXT NOT NULL,
                    accepted INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            await db.commit()
        finally:
            await db.close()

    @staticmethod
    def compute_tos_hash(platforms: list[Platform]) -> str:
        """计算 ToS 版本哈希（基于平台列表）。"""
        sorted_platforms = sorted(p.value for p in platforms)
        content = json.dumps(sorted_platforms)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def is_accepted(
        self, platforms: list[Platform]
    ) -> bool:
        """检查用户是否已接受当前版本的 ToS。"""
        db = await self._get_db()
        try:
            current_hash = self.compute_tos_hash(platforms)
            cursor = await db.execute(
                """
                SELECT accepted FROM tos_acceptance
                WHERE tos_version_hash = ?
                AND accepted = 1
                ORDER BY accepted_at DESC LIMIT 1
                """,
                (current_hash,),
            )
            row = await cursor.fetchone()
            return row is not None
        finally:
            await db.close()

    async def record_acceptance(
        self, platforms: list[Platform]
    ) -> None:
        """记录用户的 ToS 接受。"""
        db = await self._get_db()
        try:
            tos_hash = self.compute_tos_hash(platforms)
            platform_str = json.dumps([p.value for p in platforms])
            await db.execute(
                """
                INSERT INTO tos_acceptance (accepted_at, platforms, tos_version_hash, accepted)
                VALUES (?, ?, ?, 1)
                """,
                (datetime.now().isoformat(), platform_str, tos_hash),
            )
            await db.commit()
        finally:
            await db.close()
