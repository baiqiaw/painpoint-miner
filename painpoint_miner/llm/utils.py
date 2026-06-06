"""LLM 共享工具函数。"""

import json
import logging
import re

logger = logging.getLogger("painpoint_miner")


def parse_llm_json_response(text: str) -> list[dict]:
    """从 LLM 响应中解析 JSON 列表。

    处理以下格式：
    - 纯 JSON 数组/对象
    - Markdown 代码块包裹的 JSON
    - 嵌入在文本中的 JSON 数组
    - 无效 JSON → 返回空列表
    """
    text = text.strip()

    # 移除 markdown 代码块标记
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
        pass

    # 尝试提取 JSON 数组
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    logger.warning("Failed to parse LLM JSON response")
    return []
