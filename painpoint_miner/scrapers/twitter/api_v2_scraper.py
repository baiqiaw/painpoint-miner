"""Twitter API v2 抓取器（使用 httpx 直接调用，推荐方案）。"""

import logging
from typing import AsyncGenerator, Optional

import httpx

from ...models.base import RawComment, RawPost
from ...models.enums import Platform
from ...utils.rate_limiter import RateLimiter
from ..base import BaseScraper

logger = logging.getLogger("painpoint_miner")

TWITTER_API_BASE = "https://api.twitter.com/2"


class TwitterApiV2Scraper(BaseScraper):
    """Twitter/X 抓取器（官方 API v2，推荐）。

    使用 httpx 直接调用 Twitter API v2，无需 tweepy 异步兼容性问题。
    需要开发者账号和 Bearer Token。
    """

    def __init__(
        self,
        bearer_token: str,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        self._bearer_token = bearer_token
        self._rate_limiter = rate_limiter or RateLimiter(
            requests_per_minute=30, burst=5
        )
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def platform(self) -> Platform:
        return Platform.TWITTER

    @property
    def name(self) -> str:
        return "Twitter-API-v2"

    async def _initialize(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=TWITTER_API_BASE,
            headers={
                "Authorization": f"Bearer {self._bearer_token}",
                "User-Agent": "PainPointMiner/1.0",
            },
            timeout=30.0,
        )

    async def _cleanup(self) -> None:
        if self._client:
            await self._client.aclose()

    async def health_check(self) -> bool:
        if not self._bearer_token or not self._client:
            return False
        try:
            resp = await self._client.get("/users/me")
            return resp.status_code == 200
        except Exception:
            return False

    async def search_posts(
        self, keywords: list[str], limit: int
    ) -> AsyncGenerator[RawPost, None]:
        """搜索推文（recent search）。"""
        if not self._client:
            return

        query = " ".join(keywords) + " -is:retweet"
        count = 0
        next_token = None

        while count < limit:
            await self._rate_limiter.acquire()

            params: dict = {
                "query": query,
                "max_results": min(100, max(10, limit - count)),
                "tweet.fields": "created_at,public_metrics,author_id,entities,lang",
                "expansions": "author_id",
                "user.fields": "username",
            }
            if next_token:
                params["next_token"] = next_token

            try:
                resp = await self._client.get("/tweets/search/recent", params=params)
                if resp.status_code == 429:
                    logger.warning("Twitter rate limit hit")
                    return
                if resp.status_code != 200:
                    logger.error("Twitter search error: %d", resp.status_code)
                    return

                data = resp.json()
            except Exception as e:
                logger.error("Twitter search failed: %s", e)
                return

            tweets = data.get("data", [])
            if not tweets:
                break

            users = {}
            for u in data.get("includes", {}).get("users", []):
                users[u["id"]] = u

            for tweet in tweets:
                author = users.get(tweet.get("author_id", ""), {})
                metrics = tweet.get("public_metrics", {})
                entities = tweet.get("entities", {})

                yield RawPost(
                    platform=Platform.TWITTER,
                    post_id=tweet["id"],
                    author_id=tweet.get("author_id", ""),
                    author_name=author.get("username", ""),
                    content=tweet.get("text", ""),
                    likes=metrics.get("like_count", 0),
                    comments_count=metrics.get("reply_count", 0),
                    shares=metrics.get("retweet_count", 0),
                    hashtags=[h.get("tag", "") for h in entities.get("hashtags", [])],
                )
                count += 1
                if count >= limit:
                    return

            meta = data.get("meta", {})
            next_token = meta.get("next_token")
            if not next_token:
                break

    async def get_comments(
        self, post: RawPost, limit: int
    ) -> AsyncGenerator[RawComment, None]:
        """获取推文回复。"""
        if not self._client:
            return

        count = 0
        next_token = None

        while count < limit:
            await self._rate_limiter.acquire()

            params: dict = {
                "query": f"conversation_id:{post.post_id}",
                "max_results": min(100, max(10, limit - count)),
                "tweet.fields": "created_at,public_metrics,author_id",
            }
            if next_token:
                params["next_token"] = next_token

            try:
                resp = await self._client.get("/tweets/search/recent", params=params)
                if resp.status_code != 200:
                    return

                data = resp.json()
            except Exception as e:
                logger.error("Twitter comments failed: %s", e)
                return

            tweets = data.get("data", [])
            if not tweets:
                break

            for tweet in tweets:
                metrics = tweet.get("public_metrics", {})
                yield RawComment(
                    platform=Platform.TWITTER,
                    comment_id=tweet["id"],
                    post_id=post.post_id,
                    author_id=tweet.get("author_id", ""),
                    content=tweet.get("text", ""),
                    likes=metrics.get("like_count", 0),
                )
                count += 1
                if count >= limit:
                    return

            next_token = data.get("meta", {}).get("next_token")
            if not next_token:
                break
