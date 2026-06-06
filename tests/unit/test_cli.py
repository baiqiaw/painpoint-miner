"""CLI 单元测试 — Click CliRunner。"""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from painpoint_miner.cli import cli, main
from painpoint_miner.models.enums import Platform


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runner():
    """Click CliRunner 实例。"""
    return CliRunner()


@pytest.fixture
def mock_settings():
    """构造一个模拟 Settings 对象，提供 CLI run 命令所需的全部嵌套属性。"""
    settings = MagicMock()

    # scraping
    settings.scraping.platforms = [Platform.XIAOHONGSHU, Platform.WEIBO]
    settings.scraping.max_posts_per_keyword = 100
    settings.scraping.max_comments_per_post = 50

    # analysis
    settings.analysis.llm_model = "claude-haiku-4-5-20251001"
    settings.analysis.dedup.similarity_threshold = 0.9
    settings.analysis.max_llm_budget_usd = 10.0
    settings.analysis.batch_size = 15
    settings.analysis.embedding.model = "intfloat/multilingual-e5-large"
    settings.analysis.clustering.min_cluster_size = 3

    # export
    settings.export.output_dir = "./output"
    settings.export.formats = ["markdown", "json"]

    # encryption
    settings.encryption_passphrase = "test-salt"

    return settings


# ---------------------------------------------------------------------------
# cli group & version
# ---------------------------------------------------------------------------


class TestCliGroup:
    """测试 cli 组和 version 选项。"""

    def test_cli_help(self, runner):
        """cli --help 正常输出。"""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "PainPoint Miner" in result.output

    def test_cli_version(self, runner):
        """cli --version 显示版本号。"""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


# ---------------------------------------------------------------------------
# run command
# ---------------------------------------------------------------------------


class TestRunCommand:
    """测试 run 命令的各种选项组合。"""

    def test_run_without_accept_tos_risk_exits_1(self, runner):
        """不带 --accept-tos-risk 时应退出码为 1。"""
        result = runner.invoke(cli, ["run"])
        assert result.exit_code == 1
        assert "accept-tos-risk" in result.output

    def test_run_accept_tos_dry_run(self, runner, mock_settings):
        """--accept-tos-risk --dry-run 应成功并输出 Dry run 完成。"""
        with patch("painpoint_miner.cli._get_or_create_settings", return_value=mock_settings):
            result = runner.invoke(cli, ["run", "--accept-tos-risk", "--dry-run"])
        assert result.exit_code == 0
        assert "Dry run 完成" in result.output

    def test_run_dry_run_shows_config_summary(self, runner, mock_settings):
        """dry-run 应输出配置摘要（关键词、平台等）。"""
        with patch("painpoint_miner.cli._get_or_create_settings", return_value=mock_settings):
            result = runner.invoke(cli, ["run", "--accept-tos-risk", "--dry-run"])
        assert result.exit_code == 0
        assert "配置摘要" in result.output

    def test_run_with_custom_keywords(self, runner, mock_settings):
        """--keywords 选项应传入自定义关键词。"""
        with patch("painpoint_miner.cli._get_or_create_settings", return_value=mock_settings):
            result = runner.invoke(
                cli,
                [
                    "run",
                    "--accept-tos-risk",
                    "--dry-run",
                    "--keywords", "难用",
                    "--keywords", "太贵",
                ],
            )
        assert result.exit_code == 0
        assert "难用" in result.output
        assert "太贵" in result.output

    def test_run_with_custom_platforms(self, runner, mock_settings):
        """--platforms 选项应传入自定义平台。"""
        with patch("painpoint_miner.cli._get_or_create_settings", return_value=mock_settings):
            result = runner.invoke(
                cli,
                [
                    "run",
                    "--accept-tos-risk",
                    "--dry-run",
                    "--platforms", "xiaohongshu",
                ],
            )
        assert result.exit_code == 0
        assert "xiaohongshu" in result.output

    def test_run_with_output_option(self, runner, mock_settings):
        """--output 选项应设置自定义输出目录。"""
        with patch("painpoint_miner.cli._get_or_create_settings", return_value=mock_settings):
            result = runner.invoke(
                cli,
                [
                    "run",
                    "--accept-tos-risk",
                    "--dry-run",
                    "--output", "/tmp/test_output",
                ],
            )
        assert result.exit_code == 0
        assert "/tmp/test_output" in result.output

    def test_run_with_config_option(self, runner, mock_settings):
        """--config 选项应被传递到 _get_or_create_settings。"""
        with patch("painpoint_miner.cli._get_or_create_settings", return_value=mock_settings) as mock_load:
            result = runner.invoke(
                cli,
                [
                    "run",
                    "--accept-tos-risk",
                    "--dry-run",
                    "--config", "my_config.yaml",
                ],
            )
        assert result.exit_code == 0
        mock_load.assert_called_once()
        # 第一个参数应为 Path("my_config.yaml")
        call_arg = mock_load.call_args[0][0]
        assert str(call_arg) == "my_config.yaml"

    def test_run_uses_default_keywords_when_none_provided(self, runner, mock_settings):
        """未提供 --keywords 时应使用默认关键词列表。"""
        with patch("painpoint_miner.cli._get_or_create_settings", return_value=mock_settings):
            result = runner.invoke(cli, ["run", "--accept-tos-risk", "--dry-run"])
        assert result.exit_code == 0
        # 默认关键词：产品难用、太贵了、客服不回复
        assert "产品难用" in result.output
        assert "太贵了" in result.output
        assert "客服不回复" in result.output

    def test_run_uses_settings_platforms_when_none_provided(self, runner, mock_settings):
        """未提供 --platforms 时应使用 settings 中的平台。"""
        with patch("painpoint_miner.cli._get_or_create_settings", return_value=mock_settings):
            result = runner.invoke(cli, ["run", "--accept-tos-risk", "--dry-run"])
        assert result.exit_code == 0
        # mock_settings.scraping.platforms 包含 xiaohongshu, weibo
        assert "xiaohongshu" in result.output
        assert "weibo" in result.output

    def test_run_help(self, runner):
        """run --help 显示帮助信息。"""
        result = runner.invoke(cli, ["run", "--help"])
        assert result.exit_code == 0
        assert "执行痛点抓取与分析流水线" in result.output
        assert "--keywords" in result.output
        assert "--platforms" in result.output
        assert "--accept-tos-risk" in result.output
        assert "--dry-run" in result.output


# ---------------------------------------------------------------------------
# main entry point
# ---------------------------------------------------------------------------


class TestMain:
    """测试 main() 入口函数。"""

    def test_main_invokes_cli(self):
        """main() 应调用 cli()。"""
        with patch("painpoint_miner.cli.cli") as mock_cli:
            main()
            mock_cli.assert_called_once()
