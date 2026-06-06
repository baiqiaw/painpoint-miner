"""本地 Claude CLI Provider — 通过 claude-glm 命令行调用 LLM。"""

import asyncio
import json
import logging
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

logger = logging.getLogger("painpoint_miner")


class ClaudeCliProvider(BaseLLMProvider):
    """通过本地 Claude CLI（claude-glm）调用 LLM。

    免去 Anthropic API Key 配置，直接复用本地已认证的 CLI。
    """

    def __init__(
        self,
        cli_command: str = "claude-glm",
        model: str = "claude-haiku-4-5-20251001",
        cost_tracker: Optional[CostTracker] = None,
    ):
        self._cli_command = cli_command
        self._model = model
        self._cost_tracker = cost_tracker

    async def _call_cli(self, system: str, user: str) -> str:
        """调用 claude-glm CLI 并返回响应文本。"""
        # 构建完整 prompt（system + user 合并）
        full_prompt = f"{system}\n\n{user}"

        # 写入临时文件避免 shell 转义和长度限制
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(full_prompt)
            prompt_path = f.name

        try:
            result = await asyncio.to_thread(
                self._run_subprocess, prompt_path
            )
        finally:
            Path(prompt_path).unlink(missing_ok=True)

        return result

    def _run_subprocess(self, prompt_path: str) -> str:
        """同步执行子进程。"""
        # 通过 powershell 调用（Windows 环境 claude-glm 在 PowerShell 中可用）
        import sys

        if sys.platform == "win32":
            cmd = (
                f'Get-Content "{prompt_path}" -Raw | '
                f'{self._cli_command} -p --output-format json '
                f'--model {self._model}'
            )
            proc = subprocess.run(
                ["powershell.exe", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=300,
                encoding="utf-8",
            )
        else:
            with open(prompt_path, "r", encoding="utf-8") as f:
                proc = subprocess.run(
                    [self._cli_command, "-p", "--output-format", "json", "--model", self._model],
                    stdin=f,
                    capture_output=True,
                    text=True,
                    timeout=300,
                    encoding="utf-8",
                )

        if proc.returncode != 0:
            logger.error("claude-glm CLI error: %s", proc.stderr[:500])
            raise RuntimeError(f"claude-glm CLI failed (exit {proc.returncode}): {proc.stderr[:200]}")

        return self._parse_response(proc.stdout)

    def _parse_response(self, raw_output: str) -> str:
        """解析 CLI JSON 输出，提取文本并追踪成本。"""
        try:
            data = json.loads(raw_output.strip())
        except json.JSONDecodeError:
            # 非 JSON，直接返回文本
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

    @staticmethod
    def _parse_json_response(text: str) -> list[dict]:
        """从响应中解析 JSON（复用 ClaudeProvider 的逻辑）。"""
        import re

        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
            text = text.strip()

        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
            return [result]
        except json.JSONDecodeError:
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            logger.warning("Failed to parse LLM JSON response")
            return []

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
        return self._parse_json_response(response_text)

    async def extract_sentiment(self, descriptions: list[str]) -> list[dict]:
        """独立情感分析。"""
        items_block = format_items_block(descriptions)
        system = "你是情感分析专家。只返回 JSON 格式结果。"
        user = SPLIT_SENTIMENT_PROMPT.format(items_block=items_block)

        response_text = await self._call_cli(system, user)
        return self._parse_json_response(response_text)

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
        """检查 CLI 是否可用。"""
        import sys

        try:
            if sys.platform == "win32":
                result = subprocess.run(
                    ["powershell.exe", "-Command", f"{cli_command} --version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            else:
                result = subprocess.run(
                    [cli_command, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
