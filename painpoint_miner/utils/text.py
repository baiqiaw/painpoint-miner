"""文本清洗和语言检测工具。"""

import re
from html import unescape


def clean_html(text: str) -> str:
    """移除 HTML 标签，解码 HTML 实体。"""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def clean_whitespace(text: str) -> str:
    """将连续空白（含换行）压缩为单个空格。"""
    return re.sub(r"\s+", " ", text).strip()


def remove_emoji(text: str) -> str:
    """移除常见 emoji 字符（保留中文和基本 Unicode）。"""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002600-\U000026FF"  # misc symbols
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U000027BF"  # enclosed CJK letters and months (narrow range)
        "\U0001F926-\U0001F937"  # supplemental
        "\U0000FE0F"             # variation selector
        "\U0000200D"             # zero width joiner
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text)


def normalize_text(text: str) -> str:
    """完整文本清洗流水线。"""
    text = clean_html(text)
    text = clean_whitespace(text)
    return text


def detect_language(text: str) -> str:
    """简单的语言检测（基于字符比例）。

    Returns:
        "zh" (中文为主), "en" (英文为主), "mixed" (混合), "unknown"
    """
    if not text:
        return "unknown"

    chinese_chars = len(re.findall(r"[一-鿿]", text))
    latin_chars = len(re.findall(r"[a-zA-Z]", text))
    total = chinese_chars + latin_chars

    if total == 0:
        return "unknown"

    chinese_ratio = chinese_chars / total
    latin_ratio = latin_chars / total

    if chinese_ratio > 0.6:
        return "zh"
    if latin_ratio > 0.6:
        return "en"
    return "mixed"


def truncate(text: str, max_length: int = 500) -> str:
    """截断文本，保留前 max_length 个字符，添加省略号。"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."
