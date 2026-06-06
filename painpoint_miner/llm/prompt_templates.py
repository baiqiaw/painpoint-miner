"""Prompt 模板 — 痛点提取 + 情感分析。

注意：模板中的 JSON 示例花括号必须双写 {{ }}，只有占位符用单花括号。
"""

MERGED_EXTRACTION_PROMPT = """你是一位专业的用户反馈分析师。分析以下社交媒体帖子，提取用户痛点。

## 痛点定义
痛点是指用户表达的抱怨、不满、未满足的需求或问题。

## 分析要求
对每个包含痛点的帖子，提取：
1. **description**: 痛点简明描述（一句话）
2. **pain_type**: 类型，必须是以下之一：ux_problem, performance, missing_feature, pricing, customer_service, bug, onboarding, other
3. **severity**: 严重度 1-5（1=微不足道，5=极其严重）
4. **sentiment_score**: 情感分数 -1.0 到 1.0（-1=极度负面，1=极度正面）
5. **sentiment_label**: 情感标签，必须是以下之一：very_negative, negative, neutral, positive, very_positive
6. **evidence_quote**: 原文中支持该痛点的关键引用

## 输出格式
返回 JSON 数组，每个元素对应一个帖子中的痛点：
```json
[
  {{
    "post_index": 0,
    "has_pain_point": true,
    "pain_points": [
      {{
        "description": "...",
        "pain_type": "...",
        "severity": 3,
        "sentiment_score": -0.5,
        "sentiment_label": "negative",
        "evidence_quote": "..."
      }}
    ]
  }}
]
```

如果帖子不包含痛点，设置 "has_pain_point": false，"pain_points": []。

## 待分析的帖子

{posts_block}"""

SPLIT_EXTRACTION_PROMPT = """你是一位专业的用户反馈分析师。分析以下社交媒体帖子，判断每个帖子是否包含用户痛点。

痛点定义：用户表达的抱怨、不满、未满足的需求或问题。

对每个包含痛点的帖子，提取：
1. **description**: 痛点简明描述
2. **pain_type**: ux_problem | performance | missing_feature | pricing | customer_service | bug | onboarding | other
3. **severity**: 1-5
4. **evidence_quote**: 支持引用

返回 JSON 数组：
```json
[
  {{
    "post_index": 0,
    "has_pain_point": true,
    "pain_points": [{{"description": "...", "pain_type": "...", "severity": 3, "evidence_quote": "..."}}]
  }}
]
```

{posts_block}"""

SPLIT_SENTIMENT_PROMPT = """对以下痛点描述进行情感分析。

对每个痛点，返回：
- **sentiment_score**: -1.0（极度负面）到 1.0（极度正面）
- **sentiment_label**: very_negative | negative | neutral | positive | very_positive

返回 JSON 数组：
```json
[
  {{"index": 0, "sentiment_score": -0.7, "sentiment_label": "negative"}},
  ...
]
```

痛点列表：
{items_block}"""

CLUSTER_LABEL_PROMPT = """根据以下痛点描述列表，生成一个简洁的主题标签（5-10个中文字符）。

痛点描述：
{descriptions}

只返回标签文本，不要其他内容。"""


def format_posts_block(posts: list[dict]) -> str:
    """将帖子列表格式化为 prompt 中的文本块。"""
    lines = []
    for i, post in enumerate(posts):
        lines.append(f"### 帖子 {i}")
        lines.append(f"平台: {post.get('platform', 'unknown')}")
        lines.append(f"内容: {post.get('content', '')}")
        if post.get('title'):
            lines.append(f"标题: {post['title']}")
        lines.append(f"互动: {post.get('likes', 0)} 赞, {post.get('comments_count', 0)} 评论")
        lines.append("")
    return "\n".join(lines)


def format_items_block(items: list[str]) -> str:
    """将字符串列表格式化为编号列表。"""
    return "\n".join(f"{i}. {item}" for i, item in enumerate(items))
