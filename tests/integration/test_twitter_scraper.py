"""Twitter API v2 抓取器集成测试（mock httpx）。"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from painpoint_miner.models.enums import Platform
from painpoint_miner.models.base import RawPost
from painpoint_miner.scrapers.twitter.api_v2_scraper import TwitterApiV2Scraper


TWITTER_SEARCH_RESPONSE = {
    "data": [
        {
            "id": "123",
            "text": "这个产品太难用了，完全不值得这个价格",
            "author_id": "user_001",
            "created_at": "2024-01-15T10:30:00.000Z",
            "public_metrics": {
                "like_count": 42,
                "reply_count": 10,
                "retweet_count": 5,
            },
            "entities": {
                "hashtags": [{"tag": "吐槽"}],
            },
        }
    ],
    "includes": {
        "users": [
            {"id": "user_001", "username": "testuser"}
        ]
    },
    "meta": {},
}

TWITTER_COMMENTS_RESPONSE = {
    "data": [
        {
            "id": "456",
            "text": "我也遇到了同样的问题",
            "author_id": "user_002",
            "public_metrics": {"like_count": 5},
        }
    ],
    "meta": {},
}

TWITTER_EMPTY_RESPONSE = {
    "meta": {},
}


class TestTwitterApiV2Scraper:
    """Twitter API v2 抓取器测试。"""

    def test_platform(self):
        scraper = TwitterApiV2Scraper(bearer_token="test_token")
        assert scraper.platform == Platform.TWITTER
        assert scraper.name == "Twitter-API-v2"

    @pytest.mark.asyncio
    async def test_health_check_no_token(self):
        scraper = TwitterApiV2Scraper(bearer_token="")
        result = await scraper.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_search_posts(self):
        scraper = TwitterApiV2Scraper(bearer_token="test_token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = TWITTER_SEARCH_RESPONSE

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            async with scraper:
                posts = []
                async for post in scraper.search_posts(["难用"], limit=10):
                    posts.append(post)

        assert len(posts) == 1
        assert posts[0].platform == Platform.TWITTER
        assert posts[0].post_id == "123"
        assert posts[0].author_name == "testuser"
        assert posts[0].likes == 42
        assert "吐槽" in posts[0].hashtags

    @pytest.mark.asyncio
    async def test_search_posts_empty(self):
        scraper = TwitterApiV2Scraper(bearer_token="test_token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = TWITTER_EMPTY_RESPONSE

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            async with scraper:
                posts = []
                async for post in scraper.search_posts(["测试"], limit=10):
                    posts.append(post)
        assert posts == []

    @pytest.mark.asyncio
    async def test_get_comments(self):
        scraper = TwitterApiV2Scraper(bearer_token="test_token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = TWITTER_COMMENTS_RESPONSE

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        post = RawPost(
            platform=Platform.TWITTER,
            post_id="123",
            author_id="h1",
            content="test",
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            async with scraper:
                comments = []
                async for comment in scraper.get_comments(post, limit=10):
                    comments.append(comment)

        assert len(comments) == 1
        assert comments[0].comment_id == "456"
        assert comments[0].platform == Platform.TWITTER
