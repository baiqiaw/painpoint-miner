"""抖音 TikHub 抓取器。"""

from datetime import datetime

from ...models.base import RawComment, RawPost
from ...models.enums import Platform
from .base_scraper import TikHubBaseScraper
from .client import TikHubClient


class DouyinScraper(TikHubBaseScraper):
    """抖音抓取器（通过 TikHub API）。"""

    def __init__(self, client: TikHubClient):
        super().__init__(client, Platform.DOUYIN)

    @property
    def name(self) -> str:
        return "TikHub-Douyin"

    def _get_search_path(self) -> str:
        return "/api/v1/douyin/web/search-video"

    def _get_comments_path(self, post_id: str) -> str:
        return f"/api/v1/douyin/web/video-comments/{post_id}"

    def _map_to_post(self, item: dict) -> RawPost:
        author = item.get("author", {})
        ts = None
        ct = item.get("create_time")
        if ct:
            try:
                ts = datetime.fromtimestamp(int(ct))
            except (OSError, ValueError, TypeError):
                pass

        return RawPost(
            platform=Platform.DOUYIN,
            post_id=item.get("aweme_id", str(item.get("id", ""))),
            author_id=str(author.get("uid", author.get("user_id", ""))),
            author_name=str(author.get("nickname", "")),
            content=item.get("desc", ""),
            title="",
            likes=item.get("statistics", {}).get("digg_count", item.get("liked_count", 0)),
            comments_count=item.get("statistics", {}).get("comment_count", item.get("comment_count", 0)),
            shares=item.get("statistics", {}).get("share_count", item.get("share_count", 0)),
            timestamp=ts,
            extra={
                "duration": item.get("duration", 0),
                "video_url": item.get("video", {}).get("play_addr", {}).get("url_list", [""])[0] if isinstance(item.get("video"), dict) else "",
            },
        )

    def _map_to_comment(self, item: dict, post_id: str) -> RawComment:
        author = item.get("user", {})
        return RawComment(
            platform=Platform.DOUYIN,
            comment_id=str(item.get("cid", item.get("id", ""))),
            post_id=post_id,
            author_id=str(author.get("uid", author.get("user_id", ""))),
            author_name=str(author.get("nickname", "")),
            content=item.get("text", ""),
            likes=item.get("digg_count", item.get("like_count", 0)),
            parent_comment_id=item.get("reply_id"),
        )
