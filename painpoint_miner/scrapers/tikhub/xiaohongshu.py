"""小红书 TikHub 抓取器。"""

from datetime import datetime
from typing import Optional

from ...models.base import RawComment, RawPost
from ...models.enums import Platform
from ...models.tikhub_models import TikHubXhsNote
from .base_scraper import TikHubBaseScraper
from .client import TikHubClient


class XiaohongshuScraper(TikHubBaseScraper):
    """小红书抓取器（通过 TikHub API）。"""

    def __init__(self, client: TikHubClient):
        super().__init__(client, Platform.XIAOHONGSHU)

    @property
    def name(self) -> str:
        return "TikHub-Xiaohongshu"

    def _get_search_path(self) -> str:
        return "/api/v1/xiaohongshu/web/search-notes"

    def _get_comments_path(self, post_id: str) -> str:
        return f"/api/v1/xiaohongshu/web/note-comments/{post_id}"

    def _map_to_post(self, item: dict) -> RawPost:
        note = TikHubXhsNote.model_validate(item) if "note_id" in item else TikHubXhsNote(**{k: item.get(k, "") for k in ["id", "title", "desc"]})
        author = item.get("author", {})
        ts = None
        if note.create_time:
            try:
                ts = datetime.fromtimestamp(note.create_time)
            except (OSError, ValueError):
                pass

        return RawPost(
            platform=Platform.XIAOHONGSHU,
            post_id=note.note_id or note.id,
            author_id=str(author.get("user_id", "")),
            author_name=str(author.get("nickname", "")),
            content=note.desc,
            title=note.title,
            likes=note.liked_count,
            comments_count=note.comment_count,
            shares=note.share_count,
            hashtags=[t.get("name", "") for t in note.tag_list if isinstance(t, dict)],
            timestamp=ts,
            extra={"note_type": note.type, "raw_id": note.id},
        )

    def _map_to_comment(self, item: dict, post_id: str) -> RawComment:
        author = item.get("user_info", item.get("author", {}))
        ts = None
        ct = item.get("create_time") or item.get("created_at")
        if ct:
            try:
                ts = datetime.fromtimestamp(int(ct)) if isinstance(ct, (int, float)) else None
            except (OSError, ValueError):
                pass

        return RawComment(
            platform=Platform.XIAOHONGSHU,
            comment_id=str(item.get("id", item.get("comment_id", ""))),
            post_id=post_id,
            author_id=str(author.get("user_id", author.get("user_id_red", ""))),
            author_name=str(author.get("nickname", "")),
            content=item.get("content", ""),
            likes=item.get("like_count", 0),
            timestamp=ts,
            parent_comment_id=item.get("sub_comment_id"),
        )
