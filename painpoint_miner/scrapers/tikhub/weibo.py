"""微博 TikHub 抓取器。"""

from datetime import datetime

from ...models.base import RawComment, RawPost
from ...models.enums import Platform
from .base_scraper import TikHubBaseScraper
from .client import TikHubClient


class WeiboScraper(TikHubBaseScraper):
    """微博抓取器（通过 TikHub API）。"""

    def __init__(self, client: TikHubClient):
        super().__init__(client, Platform.WEIBO)

    @property
    def name(self) -> str:
        return "TikHub-Weibo"

    def _get_search_path(self) -> str:
        return "/api/v1/weibo/web/search"

    def _get_comments_path(self, post_id: str) -> str:
        return f"/api/v1/weibo/web/comments/{post_id}"

    def _map_to_post(self, item: dict) -> RawPost:
        author = item.get("user", item.get("author", {}))
        ts = None
        ct = item.get("created_at")
        if ct:
            try:
                ts = datetime.fromisoformat(str(ct).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        return RawPost(
            platform=Platform.WEIBO,
            post_id=str(item.get("id", item.get("mblog_id", ""))),
            author_id=str(author.get("id", "")),
            author_name=str(author.get("screen_name", author.get("name", ""))),
            content=item.get("text", item.get("desc", "")),
            title="",
            likes=item.get("attitudes_count", item.get("liked_count", 0)),
            comments_count=item.get("comments_count", 0),
            shares=item.get("reposts_count", item.get("share_count", 0)),
            timestamp=ts,
            extra={"source": item.get("source", "")},
        )

    def _map_to_comment(self, item: dict, post_id: str) -> RawComment:
        author = item.get("user", {})
        return RawComment(
            platform=Platform.WEIBO,
            comment_id=str(item.get("id", "")),
            post_id=post_id,
            author_id=str(author.get("id", "")),
            author_name=str(author.get("screen_name", "")),
            content=item.get("text", ""),
            likes=item.get("like_count", item.get("like_counts", 0)),
            parent_comment_id=item.get("reply_comment_id"),
        )
