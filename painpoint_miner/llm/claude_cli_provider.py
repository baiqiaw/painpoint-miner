"""本地 Claude CLI Provider — 通过 claude-glm 命令行调用 LLM。"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from ..utils.cost import CostTracker
from .base import BaseLLMProvider
from .prompt_templates import (
    CLUSTER_LABEL_PROMPT,
    MERGED_EXTRACTION_PROMPT,
    SPLIT_EXTRACTION_PROMPT,
    SPLIT_SENTIMENT_PROMPT,
    format_items_block,
    format_posts_block,
)
from .utils import parse_llm_json_response

logger = logging.getLogger("painpoint_miner")

# 安全的命令名字符白名单
import re

_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


def _validate_safe_name(value: str, field: str) -> str:
    """校验命令名/模型名只含安全字符。"""
    if not _SAFE_NAME_RE.match(value):
        raise ValueError(f"{field} contains unsafe characters: {value!r}")
    return value


class ClaudeCliProvider(BaseLLMProvider):
    """通过本地 Claude CLI（如 claude-glm）调用 LLM。

    免去 Anthropic API Key 配置，直接复用本地已认证的 CLI。
    """

    def __init__(
        self,
        cli_command: str = "claude-glm",
        model: str = "claude-haiku-4-5-20251001",
        cost_tracker: Optional[CostTracker] = None,
    ):
        _validate_safe_name(cli_command, "cli_command")
        _validate_safe_name(model, "model")
        self._cli_command = cli_command
        self._model = model
        self._cost_tracker = cost_tracker

    async def _call_cli(self, system: str, user: str) -> str:
        """调用 claude-glm CLI 并返回响应文本。"""
        full_prompt = f"{system}\n\n{user}"

        # 写入临时文件，通过 stdin 管道传递（避免 shell 拼接注入）
        fd, prompt_path = tempfile.mkstemp(suffix=".txt", text=True)
        try:
            os.chmod(prompt_path, 0o600)  # 仅所有者读写
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(full_prompt)
            result = await asyncio.to_thread(self._run_subprocess, prompt_path)
        finally:
            Path(prompt_path).unlink(missing_ok=True)

        return result

    def _run_subprocess(self, prompt_path: str) -> str:
        """同步执行子进程 — 使用参数列表（非 shell 拼接）防止注入。"""
        cmd = [self._cli_command, "-p", "--output-format", "json", "--model", self._model]

        try:
            with open(prompt_path, "r", encoding="utf-8") as stdin_file:
                proc = subprocess.run(
                    cmd,
                    stdin=stdin_file,
                    capture_output=True,
                    text=True,
                    timeout=300,
                    encoding="utf-8",
                )
        except FileNotFoundError:
            raise RuntimeError(
                f"CLI '{self._cli_command}' 未找到。请确认已安装并在 PATH 中可用。"
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"{self._cli_command} 执行超时（300秒）")

        if proc.returncode != 0:
            logger.error("%s CLI error: %s", self._cli_command, proc.stderr[:500])
            raise RuntimeError(
                f"{self._cli_command} CLI failed (exit {proc.returncode}): {proc.stderr[:200]}"
            )

        return self._parse_response(proc.stdout)

    def _parse_response(self, raw_output: str) -> str:
        """解析 CLI JSON 输出，提取文本并追踪成本。"""
        try:
            data = json.loads(raw_output.strip())
        except json.JSONDecodeError:
            logger.warning("CLI output is not valid JSON, returning raw text")
            return raw_output.strip()

        text = data.get("result", "").strip()

        # 追踪成本
        if self._cost_tracker and "usage" in data:
            usage = data["usage"]
            self._cost_tracker.track(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                model=self._model,
            )

        return text

    async def extract_pain_points(
        self,
        posts: list[dict],
        mode: str = "merged",
    ) -> list[dict]:
        """提取痛点。"""
        posts_block = format_posts_block(posts)
        system = "你是专业的用户反馈分析师。只返回 JSON 格式的分析结果。"

        if mode == "merged":
            user = MERGED_EXTRACTION_PROMPT.format(posts_block=posts_block)
        else:
            user = SPLIT_EXTRACTION_PROMPT.format(posts_block=posts_block)

        response_text = await self._call_cli(system, user)
        return parse_llm_json_response(response_text)

    async def extract_sentiment(self, descriptions: list[str]) -> list[dict]:
        """独立情感分析。"""
        items_block = format_items_block(descriptions)
        system = "你是情感分析专家。只返回 JSON 格式结果。"
        user = SPLIT_SENTIMENT_PROMPT.format(items_block=items_block)

        response_text = await self._call_cli(system, user)
        return parse_llm_json_response(response_text)

    async def generate_cluster_label(
        self, cluster_descriptions: list[str]
    ) -> str:
        """为聚类生成标签。"""
        descriptions = "\n".join(f"- {d}" for d in cluster_descriptions[:20])
        system = "你是一个简洁的主题标签生成器。只返回标签文本。"
        user = CLUSTER_LABEL_PROMPT.format(descriptions=descriptions)

        return await self._call_cli(system, user)

    @classmethod
    def is_available(cls, cli_command: str = "claude-glm") -> bool:
        """检查 CLI 是否可用（使用 shutil.which 安全检测）。"""
        try:
            _validate_safe_name(cli_command, "cli_command")
        except ValueError:
            return False

        if shutil.which(cli_command):
            return True

        # Windows: 尝试通过 PowerShell 查找
        import sys

        if sys.platform == "win32":
            try:
                result = subprocess.run(
                    ["powershell.exe", "-Command", f"Get-Command {cli_command} -ErrorAction SilentlyContinue"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return result.returncode == 0 and bool(result.stdout.strip())
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return False

        return False
