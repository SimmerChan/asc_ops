# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
GitDiffProvider 单元测试
"""

import pytest
import subprocess
from unittest.mock import Mock, patch, MagicMock
import os

from asc_ops.extractor.git_diff_provider import GitDiffProvider, GIT_REPO_BASE_PATH, MAX_DIFF_LENGTH


class TestGitDiffProvider:
    """GitDiffProvider 测试"""

    def test_parse_bug_id_valid(self):
        """有效 bug_id 正确解析"""
        provider = GitDiffProvider()

        test_cases = [
            ("BUG-ops-nn-abc123", ("ops-nn", "abc123")),
            ("BUG-ops-math-4b6c97c09ca8209ed13a2d69f689cb8f69abede2", ("ops-math", "4b6c97c09ca8209ed13a2d69f689cb8f69abede2")),
            ("BUG-ops-nn-6f2c99daa49497580c42e4acf2111e2d76ce2f4d", ("ops-nn", "6f2c99daa49497580c42e4acf2111e2d76ce2f4d")),
        ]

        for bug_id, expected in test_cases:
            result = provider.parse_bug_id(bug_id)
            assert result == expected, f"Failed for {bug_id}"

    def test_parse_bug_id_invalid(self):
        """无效 bug_id 返回 None"""
        provider = GitDiffProvider()

        invalid_ids = [
            "invalid-id",
            "BUG-",  # 缺少部分
            "bug-ops-nn-abc123",  # 小写 bug
            "OPS-NN-abc123",  # 大写 OPS
            "",  # 空字符串
        ]

        for bug_id in invalid_ids:
            result = provider.parse_bug_id(bug_id)
            assert result is None, f"Should return None for {bug_id}"

    def test_parse_bug_id_with_complex_repo_name(self):
        """复杂仓库名解析"""
        provider = GitDiffProvider()

        # 仓库名可能包含多个连字符
        result = provider.parse_bug_id("BUG-fbgemm-ascend-abc123")
        assert result == ("fbgemm-ascend", "abc123")

    def test_get_diff_repo_not_found(self):
        """仓库路径不存在时返回 None"""
        provider = GitDiffProvider(repo_base_path="/tmp/nonexistent_repo_path")

        result = provider.get_diff("BUG-ops-nn-abc123")

        assert result is None

    def test_get_diff_invalid_bug_id(self):
        """无效 bug_id 返回 None"""
        provider = GitDiffProvider()

        result = provider.get_diff("invalid-bug-id")

        assert result is None

    @patch('subprocess.run')
    def test_get_diff_commit_not_found(self, mock_run):
        """commit 不存在时返回 None"""
        # 模拟 git rev-parse 失败（commit 不存在）
        mock_run.side_effect = subprocess.CalledProcessError(1, "git", output="")

        provider = GitDiffProvider()

        result = provider.get_diff("BUG-ops-nn-abc123")

        assert result is None

    @patch('subprocess.run')
    @patch('os.path.isdir')
    def test_get_diff_success(self, mock_isdir, mock_run):
        """成功获取 diff"""
        mock_isdir.return_value = True

        # 模拟 git 命令输出
        mock_run.side_effect = [
            Mock(returncode=0, stdout="abc123\n"),  # git rev-parse
            Mock(returncode=0, stdout="diff --git a/file.cpp b/file.cpp\n+added line\n"),  # git diff
        ]

        provider = GitDiffProvider()

        result = provider.get_diff("BUG-ops-nn-abc123")

        assert result is not None
        assert "diff --git" in result
        assert "added line" in result

    @patch('subprocess.run')
    @patch('os.path.isdir')
    def test_get_diff_truncation(self, mock_isdir, mock_run):
        """过长的 diff 被截断"""
        mock_isdir.return_value = True

        # 创建一个超长 diff
        long_diff = "x" * (MAX_DIFF_LENGTH + 1000)

        mock_run.side_effect = [
            Mock(returncode=0, stdout="abc123\n"),  # git rev-parse
            Mock(returncode=0, stdout=long_diff),  # git diff
        ]

        provider = GitDiffProvider()

        result = provider.get_diff("BUG-ops-nn-abc123")

        assert result is not None
        assert len(result) <= MAX_DIFF_LENGTH + 100  # 包含截断标记
        assert "... (diff truncated)" in result

    @patch('subprocess.run')
    @patch('os.path.isdir')
    def test_get_diff_git_command_fails(self, mock_isdir, mock_run):
        """git 命令失败时返回 None"""
        mock_isdir.return_value = True

        # git rev-parse 成功，但 git diff 失败
        mock_run.side_effect = [
            Mock(returncode=0, stdout="abc123\n"),  # git rev-parse
            subprocess.CalledProcessError(1, "git", output="diff failed"),  # git diff
        ]

        provider = GitDiffProvider()

        result = provider.get_diff("BUG-ops-nn-abc123")

        assert result is None

    def test_get_diff_with_real_git_repo(self):
        """使用真实 git 仓库测试（如果存在）"""
        provider = GitDiffProvider()

        # 使用已知的测试用例
        bug_id = "BUG-ops-math-4b6c97c09ca8209ed13a2d69f689cb8f69abede2"

        result = provider.get_diff(bug_id)

        # 如果仓库存在，应该返回有效 diff
        if result is not None:
            assert "diff --git" in result
            assert len(result) > 0


class TestBugIdParsing:
    """Bug ID 解析边界测试"""

    def test_bug_id_with_full_sha(self):
        """完整 SHA 解析"""
        provider = GitDiffProvider()
        sha = "4b6c97c09ca8209ed13a2d69f689cb8f69abede2"
        result = provider.parse_bug_id(f"BUG-ops-math-{sha}")

        assert result == ("ops-math", sha)

    def test_bug_id_with_short_sha(self):
        """短 SHA 解析"""
        provider = GitDiffProvider()
        result = provider.parse_bug_id("BUG-ops-nn-abc1234")

        assert result == ("ops-nn", "abc1234")

    def test_bug_id_repo_with_dashes(self):
        """带连字符的仓库名"""
        provider = GitDiffProvider()
        result = provider.parse_bug_id("BUG-HierarchicalKV-ascend-abc123")

        assert result == ("HierarchicalKV-ascend", "abc123")
