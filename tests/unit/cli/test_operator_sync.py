# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
CLI 算子同步测试
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.asc_ops.cli.operator_sync import (
    OperatorPR,
    OperatorSyncResult,
    OperatorSync,
    ASCEND_REPOS,
    add_operator_sync_parser,
)


class TestOperatorPR:
    """算子 PR 测试"""

    def test_pr_creation(self):
        """创建 PR 对象"""
        pr = OperatorPR(
            pr_number=1,
            title="test pr",
            body="test body",
            state="open",
            merged_at=None,
            author="testuser",
            labels=["bug"],
            repo="ascend/test",
        )

        assert pr.pr_number == 1
        assert pr.title == "test pr"
        assert pr.state == "open"

    def test_is_merged_true(self):
        """is_merged 为 True 的情况"""
        pr = OperatorPR(
            pr_number=1,
            title="test",
            body="",
            state="closed",
            merged_at=datetime.now(),
            author="user",
            labels=[],
            repo="test",
        )

        assert pr.is_merged is True

    def test_is_merged_false_open(self):
        """is_merged 为 False (状态 open)"""
        pr = OperatorPR(
            pr_number=1,
            title="test",
            body="",
            state="open",
            merged_at=None,
            author="user",
            labels=[],
            repo="test",
        )

        assert pr.is_merged is False

    def test_is_merged_false_no_merged_at(self):
        """is_merged 为 False (merged_at 为 None)"""
        pr = OperatorPR(
            pr_number=1,
            title="test",
            body="",
            state="closed",
            merged_at=None,
            author="user",
            labels=[],
            repo="test",
        )

        assert pr.is_merged is False


class TestOperatorSyncResult:
    """同步结果测试"""

    def test_result_creation(self):
        """创建结果对象"""
        result = OperatorSyncResult(
            total_prs=10,
            bug_prs=3,
            optimization_prs=5,
            bug_knowledge_count=2,
            optimization_knowledge_count=4,
        )

        assert result.total_prs == 10
        assert result.bug_prs == 3
        assert result.optimization_prs == 5
        assert result.bug_knowledge_count == 2
        assert result.optimization_knowledge_count == 4
        assert result.errors == []

    def test_result_with_errors(self):
        """带错误的结果"""
        result = OperatorSyncResult(
            total_prs=5,
            errors=["repo1: error1", "repo2: error2"],
        )

        assert len(result.errors) == 2


class TestOperatorSync:
    """算子同步器测试"""

    def test_init_default(self):
        """默认初始化"""
        sync = OperatorSync()

        assert sync._since_date is None
        assert sync._repo_filter == ASCEND_REPOS

    def test_init_with_since_date(self):
        """带日期初始化"""
        since = datetime(2024, 1, 1)
        sync = OperatorSync(since_date=since)

        assert sync._since_date == since

    def test_init_with_repo_filter(self):
        """带仓库过滤器初始化"""
        repos = ["ascend/cann-a", "ascend/cann-b"]
        sync = OperatorSync(repo_filter=repos)

        assert sync._repo_filter == repos

    @pytest.mark.asyncio
    async def test_sync_repository_mock(self):
        """测试仓库同步 (模拟)"""
        sync = OperatorSync(repo_filter=["ascend/test"])

        result = await sync.sync_repository("ascend/test")

        assert result.total_prs >= 0
        assert result.errors == []


class TestASCEND_REPOS:
    """昇腾仓库列表测试"""

    def test_repos_not_empty(self):
        """仓库列表非空"""
        assert len(ASCEND_REPOS) > 0

    def test_repo_format(self):
        """仓库格式正确"""
        for repo in ASCEND_REPOS:
            assert "/" in repo
            parts = repo.split("/")
            assert len(parts) == 2
            assert parts[0] == "ascend"


class TestAddParser:
    """CLI 参数解析测试"""

    def test_add_parser(self):
        """测试添加子命令解析器"""
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()

        result = add_operator_sync_parser(subparsers)

        assert result is not None
