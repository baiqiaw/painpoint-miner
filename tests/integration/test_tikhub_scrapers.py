"""TikHub 各平台抓取器集成测试（mock API 响应）。"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from painpoint_miner.models.enums import Platform
from painpoint_miner.scrapers.tikhub.client import TikHubClient
from painpoint_miner.scrapers.tikhub.xiaohongshu import XiaohongshuScraper
from painpoint_miner.scrapers.tikhub.weibo import WeiboScraper
from painpoint_miner.scrapers.tikhub.douyin import DouyinScraper
from painpoint_miner.scrapers.tikhub.zhihu import ZhihuScraper


# --- Mock 数据 ---

XHS_SEARCH_RESPONSE = {
    "code": 200,
    "data": [
        {
            "id": "xhs_raw_001",
            "note_id": "note_001",
            "title": "产品吐槽",
            "desc": "这个东西太难用了，按钮完全找不到",
            "liked_count": 42,
            "comment_count": 15,
            "share_count": 3,
            "create_time": 1700000000,
            "author": {"user_id": "user_001", "nickname": "用户A"},
            "tag_list": [{"name": "吐槽"}, {"name": "难用"}],
            "type": "normal",
        },
        {
            "id": "xhs_raw_002",
            "note_id": "note_002",
            "title": "太贵了",
            "desc": "价格翻了一倍，性价比太低了",
            "liked_count": 88,
            "comment_count": 30,
            "share_count": 5,
            "create_time": 1700001000,
            "author": {"user_id": "user_002", "nickname": "用户B"},
            "tag_list": [],
            "type": "normal",
        },
    ],
    "has_more": False,
    "total": 2,
}

XHS_COMMENTS_RESPONSE = {
    "code": 200,
    "comments": [
        {
            "id": "cmt_001",
            "content": "我也觉得，设计太差了",
            "like_count": 5,
            "user_info": {"user_id": "user_003", "nickname": "用户C"},
            "create_time": 1700002000,
        },
    ],
    "has_more": False,
}

WEIBO_SEARCH_RESPONSE = {
    "code": 200,
    "data": [
        {
            "id": "wb_001",
            "text": "这个服务态度太差了，等了三天没人回复",
            "user": {"id": "wb_user_001", "screen_name": "微博用户A"},
            "attitudes_count": 100,
            "comments_count": 50,
            "reposts_count": 20,
            "created_at": "2024-01-15T10:30:00+08:00",
            "source": "iPhone客户端",
        },
    ],
    "has_more": False,
}

DOUYIN_SEARCH_RESPONSE = {
    "code": 200,
    "data": [
        {
            "id": "dy_001",
            "aweme_id": "aw_001",
            "desc": "这个APP一直闪退，根本用不了",
            "author": {"uid": "dy_user_001", "nickname": "抖音用户A"},
            "liked_count": 200,
            "comment_count": 80,
            "share_count": 10,
            "create_time": 1700003000,
            "statistics": {"digg_count": 200, "comment_count": 80, "share_count": 10},
            "video": {"play_addr": {"url_list": ["https://example.com/video.mp4"]}},
        },
    ],
    "has_more": False,
}

ZHIHU_SEARCH_RESPONSE = {
    "code": 200,
    "data": [
        {
            "id": "zh_answer_001",
            "content": "作为付费用户，我觉得功能完全没有宣传的那么好，很多承诺的功能都没有上线",
            "author": {"id": "zh_user_001", "name": "知乎用户A"},
            "voteup_count": 150,
            "comment_count": 40,
            "created_time": 1700004000,
            "question": {"id": "q_001", "title": "XX产品怎么样？"},
        },
    ],
    "has_more": False,
}


def _make_mock_client(response_data: dict) -> TikHubClient:
    """创建返回固定响应的 mock TikHubClient。"""
    client = TikHubClient.__new__(TikHubClient)
    client._api_key = "test_key"
    client._base_url = "https://api.tikhub.io"
    client._rate_limiter = MagicMock()
    client._rate_limiter.acquire = AsyncMock()
    client._client = MagicMock()

    # Mock the request method
    call_count = [0]

    async def mock_get(path, params=None):
        call_count[0] += 1
        return response_data

    client.get = mock_get
    client.health_check = AsyncMock(return_value=True)
    return client


class TestXiaohongshuScraper:
    """小红书抓取器测试。"""

    @pytest.mark.asyncio
    async def test_search_posts(self):
        client = _make_mock_client(XHS_SEARCH_RESPONSE)
        scraper = XiaohongshuScraper(client)

        posts = []
        async for post in scraper.search_posts(["难用", "贵"], limit=10):
            posts.append(post)

        assert len(posts) == 2
        assert posts[0].platform == Platform.XIAOHONGSHU
        assert posts[0].post_id == "note_001"
        assert posts[0].author_id == "user_001"
        assert posts[0].author_name == "用户A"
        assert "吐槽" in posts[0].hashtags
        assert posts[0].likes == 42

    @pytest.mark.asyncio
    async def test_get_comments(self):
        client = _make_mock_client(XHS_COMMENTS_RESPONSE)
        scraper = XiaohongshuScraper(client)

        from painpoint_miner.models.base import RawPost
        post = RawPost(
            platform=Platform.XIAOHONGSHU,
            post_id="note_001",
            author_id="h1",
            content="test",
        )

        comments = []
        async for comment in scraper.get_comments(post, limit=10):
            comments.append(comment)

        assert len(comments) == 1
        assert comments[0].content == "我也觉得，设计太差了"
        assert comments[0].platform == Platform.XIAOHONGSHU

    def test_platform_property(self):
        client = _make_mock_client({})
        scraper = XiaohongshuScraper(client)
        assert scraper.platform == Platform.XIAOHONGSHU
        assert scraper.name == "TikHub-Xiaohongshu"


class TestWeiboScraper:
    """微博抓取器测试。"""

    @pytest.mark.asyncio
    async def test_search_posts(self):
        client = _make_mock_client(WEIBO_SEARCH_RESPONSE)
        scraper = WeiboScraper(client)

        posts = []
        async for post in scraper.search_posts(["客服不回复"], limit=10):
            posts.append(post)

        assert len(posts) == 1
        assert posts[0].platform == Platform.WEIBO
        assert posts[0].post_id == "wb_001"
        assert posts[0].likes == 100
        assert posts[0].extra["source"] == "iPhone客户端"

    def test_name(self):
        client = _make_mock_client({})
        scraper = WeiboScraper(client)
        assert scraper.name == "TikHub-Weibo"


class TestDouyinScraper:
    """抖音抓取器测试。"""

    @pytest.mark.asyncio
    async def test_search_posts(self):
        client = _make_mock_client(DOUYIN_SEARCH_RESPONSE)
        scraper = DouyinScraper(client)

        posts = []
        async for post in scraper.search_posts(["闪退"], limit=10):
            posts.append(post)

        assert len(posts) == 1
        assert posts[0].platform == Platform.DOUYIN
        assert posts[0].post_id == "aw_001"
        assert posts[0].likes == 200
        assert posts[0].extra["duration"] == 0

    def test_name(self):
        client = _make_mock_client({})
        scraper = DouyinScraper(client)
        assert scraper.name == "TikHub-Douyin"


class TestZhihuScraper:
    """知乎抓取器测试。"""

    @pytest.mark.asyncio
    async def test_search_posts(self):
        client = _make_mock_client(ZHIHU_SEARCH_RESPONSE)
        scraper = ZhihuScraper(client)

        posts = []
        async for post in scraper.search_posts(["功能缺失"], limit=10):
            posts.append(post)

        assert len(posts) == 1
        assert posts[0].platform == Platform.ZHIHU
        assert posts[0].post_id == "zh_answer_001"
        assert posts[0].title == "XX产品怎么样？"
        assert posts[0].likes == 150

    def test_name(self):
        client = _make_mock_client({})
        scraper = ZhihuScraper(client)
        assert scraper.name == "TikHub-Zhihu"


class TestTikHubClientError:
    """TikHub 客户端错误处理测试。"""

    @pytest.mark.asyncio
    async def test_empty_response(self):
        """空响应不报错，返回空列表。"""
        client = _make_mock_client({"code": 200, "data": [], "has_more": False})
        scraper = XiaohongshuScraper(client)

        posts = []
        async for post in scraper.search_posts(["测试"], limit=10):
            posts.append(post)
        assert posts == []

    @pytest.mark.asyncio
    async def test_health_check(self):
        client = _make_mock_client({})
        assert await client.health_check() is True
