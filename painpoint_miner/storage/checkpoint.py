"""断点续传 — 原子写入 JSONL checkpoint。"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import aiosqlite

logger = logging.getLogger("painpoint_miner")


class Checkpoint:
    """流水线状态检查点。

    使用原子写入（.tmp → os.replace）确保崩溃安全。
    状态同时持久化到 SQLite 和 JSONL 文件。
    """

    def __init__(self, db_path: Path):
        self._db_path = db_path

    async def _get_db(self) -> aiosqlite.Connection:
        db = await aiosqlite.connect(self._db_path)
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
        return db

    async def save(self, state: dict) -> None:
        """原子保存流水线状态到 SQLite。"""
        db = await self._get_db()
        try:
            state_json = json.dumps(state, ensure_ascii=False, default=str)
            await db.execute(
                """
                INSERT INTO checkpoints (created_at, state) VALUES (?, ?)
                """,
                (datetime.now().isoformat(), state_json),
            )
            await db.commit()
            logger.info("Checkpoint saved")
        finally:
            await db.close()

    async def save_to_file(self, state: dict, file_path: Path) -> None:
        """原子写入 JSONL 文件（.tmp → os.replace）。

        在 Windows 上 os.replace 是原子的（即使目标存在）。
        """
        tmp_path = file_path.with_suffix(".tmp")
        content = json.dumps(
            {"saved_at": datetime.now().isoformat(), **state},
            ensure_ascii=False,
            default=str,
        )

        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())

        os.replace(str(tmp_path), str(file_path))
        logger.info("Checkpoint file saved to %s", file_path)

    async def load_latest(self) -> Optional[dict]:
        """加载最近的 checkpoint。"""
        db = await self._get_db()
        try:
            cursor = await db.execute(
                "SELECT state FROM checkpoints ORDER BY created_at DESC LIMIT 1"
            )
            row = await cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None
        finally:
            await db.close()

    async def load_from_file(self, file_path: Path) -> Optional[dict]:
        """从 JSONL 文件加载 checkpoint。"""
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if not content:
                return None
            return json.loads(content)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load checkpoint from %s: %s", file_path, e)
            return None
