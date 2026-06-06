"""TikHub 响应模型测试。"""

import pytest

from painpoint_miner.models.tikhub_models import (
    TikHubCommentResponse,
    TikHubDouyinVideo,
    TikHubSearchResponse,
    TikHubWeiboPost,
    TikHubXhsNote,
    TikHubZhihuAnswer,
)


class TestTikHubSearchResponse:
    def test_defaults(self):
        resp = TikHubSearchResponse()
        assert resp.code == 200
        assert resp.data == []
        assert resp.has_more is False

    def test_with_data(self):
        resp = TikHubSearchResponse(
            data=[{"id": "1", "title": "test"}],
            total=1,
            has_more=True,
            cursor="next_page",
        )
        assert len(resp.data) == 1
        assert resp.cursor == "next_page"


class TestTikHubXhsNote:
    def test_create(self):
        note = TikHubXhsNote(
            id="xhs_001",
            title="测试笔记",
            desc="内容描述",
            liked_count=100,
            note_id="note_001",
        )
        assert note.liked_count == 100
        assert note.note_id == "note_001"


class TestTikHubWeiboPost:
    def test_create(self):
        post = TikHubWeiboPost(
            id="wb_001",
            desc="微博内容",
            reposts_count=10,
        )
        assert post.reposts_count == 10


class TestTikHubDouyinVideo:
    def test_create(self):
        video = TikHubDouyinVideo(
            id="dy_001",
            desc="抖音视频描述",
            aweme_id="aw_001",
            duration=15000,
        )
        assert video.duration == 15000


class TestTikHubZhihuAnswer:
    def test_create(self):
        answer = TikHubZhihuAnswer(
            id="zh_001",
            question_title="有什么好用的工具？",
            voteup_count=50,
        )
        assert answer.voteup_count == 50


class TestTikHubCommentResponse:
    def test_defaults(self):
        resp = TikHubCommentResponse()
        assert resp.code == 200
        assert resp.comments == []
