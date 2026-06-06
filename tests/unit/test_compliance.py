"""合规模块单元测试。"""

import pytest
from pathlib import Path

from painpoint_miner.compliance.anonymizer import Anonymizer
from painpoint_miner.compliance.tos import TosAcceptance
from painpoint_miner.models import Platform, RawComment, RawPost


class TestAnonymizer:
    """匿名化器测试。"""

    def test_hash_id_deterministic(self):
        """相同输入产生相同哈希。"""
        anon = Anonymizer(salt="test-salt")
        h1 = anon._hash_id("user_001")
        h2 = anon._hash_id("user_001")
        assert h1 == h2

    def test_hash_id_different_users(self):
        """不同用户产生不同哈希。"""
        anon = Anonymizer(salt="test-salt")
        h1 = anon._hash_id("user_001")
        h2 = anon._hash_id("user_002")
        assert h1 != h2

    def test_hash_id_salt_sensitive(self):
        """不同 salt 产生不同哈希。"""
        a1 = Anonymizer(salt="salt-A")
        a2 = Anonymizer(salt="salt-B")
        assert a1._hash_id("user_001") != a2._hash_id("user_001")

    def test_hash_id_length(self):
        """哈希长度固定为 16 字符。"""
        anon = Anonymizer()
        h = anon._hash_id("user_001")
        assert len(h) == 16

    def test_anonymize_post(self, sample_raw_post):
        anon = Anonymizer(salt="test-salt")
        result = anon.anonymize_post(sample_raw_post)
        assert result.author_id != "user_original_001"
        assert result.author_id == anon._hash_id("user_original_001")
        assert result.author_name == ""
        assert result.content == sample_raw_post.content  # 内容不变
        assert result.post_id == sample_raw_post.post_id  # 帖子 ID 不变

    def test_anonymize_comment(self, sample_raw_comment):
        anon = Anonymizer(salt="test-salt")
        result = anon.anonymize_comment(sample_raw_comment)
        assert result.author_id != "user_original_002"
        assert result.author_name == ""
        assert result.content == sample_raw_comment.content

    def test_anonymize_posts_batch(self, sample_raw_post):
        anon = Anonymizer()
        posts = [sample_raw_post]
        results = anon.anonymize_posts(posts)
        assert len(results) == 1
        assert results[0].author_name == ""

    def test_anonymize_comments_batch(self, sample_raw_comment):
        anon = Anonymizer()
        comments = [sample_raw_comment]
        results = anon.anonymize_comments(comments)
        assert len(results) == 1
        assert results[0].author_name == ""


class TestTosAcceptance:
    """ToS 确认管理测试。"""

    @pytest.mark.asyncio
    async def test_not_accepted_initially(self, tmp_db):
        tos = TosAcceptance(tmp_db)
        await tos.ensure_table()
        accepted = await tos.is_accepted([Platform.XIAOHONGSHU])
        assert accepted is False

    @pytest.mark.asyncio
    async def test_record_and_check(self, tmp_db):
        tos = TosAcceptance(tmp_db)
        await tos.ensure_table()
        platforms = [Platform.XIAOHONGSHU, Platform.WEIBO]
        await tos.record_acceptance(platforms)
        accepted = await tos.is_accepted(platforms)
        assert accepted is True

    @pytest.mark.asyncio
    async def test_different_platforms_not_accepted(self, tmp_db):
        tos = TosAcceptance(tmp_db)
        await tos.ensure_table()
        await tos.record_acceptance([Platform.XIAOHONGSHU])
        # 不同平台列表 → 不同 hash → 未接受
        accepted = await tos.is_accepted([Platform.XIAOHONGSHU, Platform.WEIBO])
        assert accepted is False

    def test_tos_hash_deterministic(self):
        platforms = [Platform.XIAOHONGSHU, Platform.WEIBO]
        h1 = TosAcceptance.compute_tos_hash(platforms)
        h2 = TosAcceptance.compute_tos_hash(platforms)
        assert h1 == h2

    def test_tos_hash_order_independent(self):
        """平台列表顺序不影响 hash。"""
        h1 = TosAcceptance.compute_tos_hash([Platform.XIAOHONGSHU, Platform.WEIBO])
        h2 = TosAcceptance.compute_tos_hash([Platform.WEIBO, Platform.XIAOHONGSHU])
        assert h1 == h2
