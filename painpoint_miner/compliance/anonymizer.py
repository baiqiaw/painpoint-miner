"""PII 匿名化处理 — 加盐哈希，抓取后立即执行。"""

import hashlib
from typing import Optional

from ..models.base import RawComment, RawPost


class Anonymizer:
    """用户身份匿名化器。

    使用加盐 SHA-256 哈希替代原始用户 ID。
    注意：这是假名化（pseudonymization），非不可逆匿名化。
    假名化数据仍受 PIPL 第51条和 GDPR Recital 26 约束。
    """

    def __init__(self, salt: str = "painpoint-miner-default-salt"):
        self._salt = salt

    def _hash_id(self, raw_id: str) -> str:
        """对原始 ID 进行加盐哈希。"""
        return hashlib.sha256(
            f"{self._salt}:{raw_id}".encode()
        ).hexdigest()[:16]

    def anonymize_post(self, post: RawPost) -> RawPost:
        """匿名化帖子：用户ID→哈希，清除用户名。"""
        return post.model_copy(
            update={
                "author_id": self._hash_id(post.author_id),
                "author_name": "",
            }
        )

    def anonymize_comment(self, comment: RawComment) -> RawComment:
        """匿名化评论：用户ID→哈希，清除用户名。"""
        return comment.model_copy(
            update={
                "author_id": self._hash_id(comment.author_id),
                "author_name": "",
            }
        )

    def anonymize_posts(self, posts: list[RawPost]) -> list[RawPost]:
        """批量匿名化帖子。"""
        return [self.anonymize_post(p) for p in posts]

    def anonymize_comments(
        self, comments: list[RawComment]
    ) -> list[RawComment]:
        """批量匿名化评论。"""
        return [self.anonymize_comment(c) for c in comments]
