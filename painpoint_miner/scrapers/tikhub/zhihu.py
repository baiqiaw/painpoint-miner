"""知乎 TikHub 抓取器。"""

from datetime import datetime

from ...models.base import RawComment, RawPost
from ...models.enums import Platform
from .base_scraper import TikHubBaseScraper
from .client import TikHubClient


class ZhihuScraper(TikHubBaseScraper):
    """知乎抓取器（通过 TikHub API）。"""

    def __init__(self, client: TikHubClient):
        super().__init__(client, Platform.ZHIHU)

    @property
    def name(self) -> str:
        return "TikHub-Zhihu"

    def _get_search_path(self) -> str:
        return "/api/v1/zhihu/web/search"

    def _get_comments_path(self, post_id: str) -> str:
        return f"/api/v1/zhihu/web/answer-comments/{post_id}"

    def _map_to_post(self, item: dict) -> RawPost:
        author = item.get("author", {})
        question = item.get("question", {})
        ts = None
        ct = item.get("created_time") or item.get("created_at")
        if ct:
            try:
                ts = datetime.fromtimestamp(int(ct))
            except (OSError, ValueError, TypeError):
                pass

        return RawPost(
            platform=Platform.ZHIHU,
            post_id=str(item.get("id", item.get("answer_id", ""))),
            author_id=str(author.get("id", author.get("url_token", ""))),
            author_name=str(author.get("name", "")),
            content=item.get("content", item.get("excerpt", "")),
            title=question.get("title", item.get("question_title", "")),
            likes=item.get("voteup_count", item.get("liked_count", 0)),
            comments_count=item.get("comment_count", 0),
            shares=0,
            timestamp=ts,
            extra={
                "question_id": str(question.get("id", item.get("question_id", ""))),
                "type": item.get("type", ""),
            },
        )

    def _map_to_comment(self, item: dict, post_id: str) -> RawComment:
        author = item.get("author", {})
        return RawComment(
            platform=Platform.ZHIHU,
            comment_id=str(item.get("id", "")),
            post_id=post_id,
            author_id=str(author.get("id", author.get("url_token", ""))),
            author_name=str(author.get("name", "")),
            content=item.get("content", ""),
            likes=item.get("vote_count", item.get("like_count", 0)),
            parent_comment_id=item.get("reply_comment_id"),
        )
