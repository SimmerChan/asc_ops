# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
GitCodeDiffProvider 单元测试
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import os

from asc_ops.extractor.gitcode_diff_provider import GitCodeDiffProvider, MAX_DIFF_LENGTH


class TestGitCodeDiffProvider:
    """GitCodeDiffProvider 测试"""

    def test_parse_bug_id_valid(self):
        """有效 bug_id 正确解析"""
        provider = GitCodeDiffProvider()

        test_cases = [
            ("BUG-cann/ops-nn-1244", ("cann/ops-nn", 1244)),
            ("BUG-cann/ops-math-703", ("cann/ops-math", 703)),
            ("BUG-cann/ops-transformer-942", ("cann/ops-transformer", 942)),
        ]

        for bug_id, expected in test_cases:
            result = provider.parse_bug_id(bug_id)
            assert result == expected, f"Failed for {bug_id}"

    def test_parse_bug_id_invalid(self):
        """无效 bug_id 返回 None"""
        provider = GitCodeDiffProvider()

        invalid_ids = [
            "invalid-id",
            "BUG-",  # 缺少部分
            "BUG-cann/-1234",  # 缺少 repo 名
            "",  # 空字符串
        ]

        for bug_id in invalid_ids:
            result = provider.parse_bug_id(bug_id)
            assert result is None, f"Should return None for {bug_id}"

    def test_parse_bug_id_legacy_format(self):
        """旧格式 bug_id 也被支持"""
        provider = GitCodeDiffProvider()

        # 旧格式 BUG-ops-nn-1244 会被自动转换
        result = provider.parse_bug_id("BUG-ops-nn-1244")
        assert result == ("cann/ops-nn", 1244)

        # _parse_legacy 也支持
        legacy_result = provider._parse_legacy("BUG-ops-nn-1244")
        assert legacy_result == ("cann/ops-nn", 1244)

    @patch('requests.Session')
    def test_get_diff_success(self, mock_session_class):
        """成功获取 diff"""
        # Mock session
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock PR files API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "filename": "test.cpp",
                "additions": 10,
                "deletions": 5,
                "patch": {
                    "diff": "@@ -1,5 +1,6 @@\n old line\n+new line"
                }
            }
        ]
        mock_session.get.return_value = mock_response

        provider = GitCodeDiffProvider()
        provider._session = mock_session

        result = provider.get_diff("BUG-cann/ops-nn-1244")

        assert result is not None
        assert "test.cpp" in result
        assert "old line" in result
        assert "new line" in result

    @patch('requests.Session')
    def test_get_diff_truncation(self, mock_session_class):
        """过长的 diff 被截断"""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # 创建超长 diff
        long_diff = "x" * (MAX_DIFF_LENGTH + 1000)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "filename": "large.cpp",
                "additions": 1000,
                "deletions": 500,
                "patch": {"diff": long_diff}
            }
        ]
        mock_session.get.return_value = mock_response

        provider = GitCodeDiffProvider()
        provider._session = mock_session

        result = provider.get_diff("BUG-cann/ops-nn-1244")

        assert result is not None
        assert len(result) <= MAX_DIFF_LENGTH + 100  # 包含截断标记
        assert "diff truncated" in result

    @patch('requests.Session')
    def test_get_diff_api_error(self, mock_session_class):
        """API 返回错误时返回 None"""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_response = Mock()
        mock_response.status_code = 404
        mock_session.get.return_value = mock_response

        provider = GitCodeDiffProvider()
        provider._session = mock_session

        result = provider.get_diff("BUG-cann/ops-nn-99999")

        assert result is None

    @patch('requests.Session')
    def test_get_diff_empty_response(self, mock_session_class):
        """空响应时返回 None"""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error_code": 404, "error_message": "not found"}
        mock_session.get.return_value = mock_response

        provider = GitCodeDiffProvider()
        provider._session = mock_session

        result = provider.get_diff("BUG-cann/ops-nn-1244")

        assert result is None

    def test_merge_diffs(self):
        """合并多个文件的 diff"""
        provider = GitCodeDiffProvider()

        files = [
            {
                "filename": "file1.cpp",
                "additions": 10,
                "deletions": 5,
                "patch": {"diff": "diff content 1"}
            },
            {
                "filename": "file2.cpp",
                "additions": 20,
                "deletions": 10,
                "patch": {"diff": "diff content 2"}
            }
        ]

        result = provider._merge_diffs(files)

        assert "file1.cpp" in result
        assert "file2.cpp" in result
        assert "diff content 1" in result
        assert "diff content 2" in result

    def test_merge_diffs_empty(self):
        """空文件列表返回空字符串"""
        provider = GitCodeDiffProvider()

        result = provider._merge_diffs([])
        assert result == ""

    @patch('requests.Session')
    def test_get_diff_with_context(self, mock_session_class):
        """获取 diff 及上下文信息"""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock PR API response
        pr_response = Mock()
        pr_response.status_code = 200
        pr_response.json.return_value = {
            "title": "Test PR",
            "body": "PR description",
        }

        # Mock files API response
        files_response = Mock()
        files_response.status_code = 200
        files_response.json.return_value = [
            {
                "filename": "test.cpp",
                "additions": 10,
                "deletions": 5,
                "patch": {"diff": "test diff"}
            }
        ]

        mock_session.get.side_effect = [pr_response, files_response]

        provider = GitCodeDiffProvider()
        provider._session = mock_session

        result = provider.get_diff_with_context("BUG-cann/ops-nn-1244")

        assert result is not None
        assert result["pr_title"] == "Test PR"
        assert result["pr_body"] == "PR description"
        assert "test diff" in result["diff"]
        assert len(result["files"]) == 1
        assert result["files"][0]["filename"] == "test.cpp"


class TestBugIdParsingEdgeCases:
    """Bug ID 解析边界测试"""

    def test_bug_id_with_special_repo_name(self):
        """特殊仓库名解析"""
        provider = GitCodeDiffProvider()

        result = provider.parse_bug_id("BUG-cann/ops-cv-1234")
        assert result == ("cann/ops-cv", 1234)

    def test_legacy_format_conversion(self):
        """旧格式转换为新格式"""
        provider = GitCodeDiffProvider()

        # ops-nn -> cann/ops-nn
        result = provider._parse_legacy("BUG-ops-nn-1234")
        assert result == ("cann/ops-nn", 1234)

        # ops-math -> cann/ops-math
        result = provider._parse_legacy("BUG-ops-math-5678")
        assert result == ("cann/ops-math", 5678)
