"""TikHub API 响应的 Pydantic 验证模型。

防止 TikHub API schema 变更导致静默数据错误。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TikHubSearchResult(BaseModel):
    """TikHub 搜索结果通用字段。"""

    id: str
    title: str = ""
    desc: str = ""
    create_time: Optional[int] = None
    liked_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    author: Optional[dict] = None
    extra: dict = Field(default_factory=dict)


class TikHubXhsNote(TikHubSearchResult):
    """小红书笔记。"""

    note_id: str = ""
    type: str = ""
    tag_list: list[dict] = Field(default_factory=list)
    image_list: list[dict] = Field(default_factory=list)
    video: Optional[dict] = None


class TikHubWeiboPost(TikHubSearchResult):
    """微博帖子。"""

    mblog_id: str = ""
    reposts_count: int = 0
    pics: list[dict] = Field(default_factory=list)
    source: str = ""


class TikHubDouyinVideo(TikHubSearchResult):
    """抖音视频。"""

    aweme_id: str = ""
    video_url: str = ""
    duration: int = 0
    music: Optional[dict] = None


class TikHubZhihuAnswer(TikHubSearchResult):
    """知乎回答。"""

    question_id: str = ""
    answer_id: str = ""
    voteup_count: int = 0
    question_title: str = ""


class TikHubSearchResponse(BaseModel):
    """TikHub 搜索 API 通用响应。"""

    code: int = 200
    message: str = "ok"
    data: list[dict] = Field(default_factory=list)
    total: int = 0
    has_more: bool = False
    cursor: Optional[str] = None


class TikHubCommentResponse(BaseModel):
    """TikHub 评论 API 响应。"""

    code: int = 200
    message: str = "ok"
    comments: list[dict] = Field(default_factory=list)
    total: int = 0
    has_more: bool = False
    cursor: Optional[str] = None
