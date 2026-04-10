# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
CLI sync 命令测试
"""

import argparse
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from io import StringIO

from src.asc_ops.cli.sync import (
    add_sync_parser,
    show_sync_status,
    run_sync,
)
from src.asc_ops.sync.state_manager import SyncStateManager, SyncStatus


class TestAddSyncParser:
    """测试 add_sync_parser 函数"""

    def test_add_sync_parser(self):
        """测试解析器创建"""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        result_parser = add_sync_parser(subparsers)

        assert result_parser is not None
        assert "sync" in result_parser.format_help().lower()

    def test_sync_parser_api_flag(self):
        """测试 --api 标志"""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        add_sync_parser(subparsers)

        args = parser.parse_args(["sync", "--api"])
        assert args.api is True
        assert args.command == "sync"

    def test_sync_parser_operator_flag(self):
        """测试 --operator 标志"""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        add_sync_parser(subparsers)

        args = parser.parse_args(["sync", "--operator"])
        assert args.operator is True

    def test_sync_parser_all_flag(self):
        """测试 --all 标志"""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        add_sync_parser(subparsers)

        args = parser.parse_args(["sync", "--all"])
        assert args.all is True

    def test_sync_parser_status_flag(self):
        """测试 --status 标志"""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        add_sync_parser(subparsers)

        args = parser.parse_args(["sync", "--status"])
        assert args.status is True

    def test_sync_parser_force_flag(self):
        """测试 --force 标志"""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        add_sync_parser(subparsers)

        args = parser.parse_args(["sync", "--force"])
        assert args.force is True

    def test_sync_parser_verbose_flag(self):
        """测试 --verbose 标志"""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        add_sync_parser(subparsers)

        args = parser.parse_args(["sync", "--verbose"])
        assert args.verbose is True

    def test_sync_parser_default_no_flags(self):
        """测试无标志时的默认值"""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        add_sync_parser(subparsers)

        args = parser.parse_args(["sync"])
        assert args.api is False
        assert args.operator is False
        assert args.all is False
        assert args.status is False
        assert args.force is False
        assert args.verbose is False


class TestShowSyncStatus:
    """测试 show_sync_status 函数"""

    @pytest.fixture
    def mock_state_manager(self):
        """创建模拟状态管理器"""
        manager = MagicMock(spec=SyncStateManager)
        manager.get_sync_status.return_value.new_apis = []
        manager.get_sync_status.return_value.changed_apis = []
        manager.get_sync_status.return_value.deleted_apis = []
        manager.get_sync_status.return_value.failed_apis = []
        manager.get_sync_status.return_value.status = SyncStatus.IDLE
        manager.get_sync_status.return_value.last_sync_at = None
        manager.get_sync_status.return_value.started_at = None
        manager.get_sync_status.return_value.completed_at = None
        return manager

    def test_show_idle_status(self, mock_state_manager):
        """测试显示空闲状态"""
        with patch("sys.stdout", new_callable=StringIO):
            result = asyncio.run(show_sync_status(mock_state_manager))

        assert result == 0

    def test_show_syncing_status(self, mock_state_manager):
        """测试显示同步中状态"""
        mock_state_manager.get_sync_status.return_value.new_apis = ["api1", "api2"]
        mock_state_manager.get_sync_status.return_value.changed_apis = ["api3"]
        mock_state_manager.get_sync_status.return_value.status = SyncStatus.SYNCING
        mock_state_manager.get_sync_status.return_value.started_at = "2026-04-10T12:00:00"

        with patch("sys.stdout", new_callable=StringIO):
            result = asyncio.run(show_sync_status(mock_state_manager))

        assert result == 0

    def test_show_completed_with_results(self, mock_state_manager):
        """测试显示完成状态及结果"""
        mock_state_manager.get_sync_status.return_value.new_apis = ["api1", "api2", "api3"]
        mock_state_manager.get_sync_status.return_value.changed_apis = ["api4"]
        mock_state_manager.get_sync_status.return_value.deleted_apis = ["api5"]
        mock_state_manager.get_sync_status.return_value.status = SyncStatus.COMPLETED
        mock_state_manager.get_sync_status.return_value.last_sync_at = "2026-04-10T12:00:00"
        mock_state_manager.get_sync_status.return_value.started_at = "2026-04-10T11:55:00"
        mock_state_manager.get_sync_status.return_value.completed_at = "2026-04-10T12:00:00"

        with patch("sys.stdout", new_callable=StringIO):
            result = asyncio.run(show_sync_status(mock_state_manager))

        assert result == 0

    def test_show_with_failed_apis(self, mock_state_manager):
        """测试显示有失败 API 的状态"""
        mock_state_manager.get_sync_status.return_value.new_apis = ["api1"]
        mock_state_manager.get_sync_status.return_value.failed_apis = ["api2", "api3"]
        mock_state_manager.get_sync_status.return_value.status = SyncStatus.COMPLETED
        mock_state_manager.get_sync_status.return_value.last_sync_at = "2026-04-10T12:00:00"
        mock_state_manager.get_sync_status.return_value.started_at = "2026-04-10T11:55:00"
        mock_state_manager.get_sync_status.return_value.completed_at = "2026-04-10T12:00:00"

        with patch("sys.stdout", new_callable=StringIO):
            result = asyncio.run(show_sync_status(mock_state_manager))

        assert result == 0


class TestRunSync:
    """测试 run_sync 函数"""

    @pytest.fixture
    def mock_args(self):
        """创建模拟命令行参数"""
        args = MagicMock()
        args.verbose = False
        args.status = False
        args.api = False
        args.operator = False
        args.all = False
        args.force = False
        return args

    @pytest.mark.asyncio
    async def test_run_sync_with_status_flag(self, mock_args):
        """测试 --status 标志"""
        mock_args.status = True

        with patch("src.asc_ops.cli.sync.get_config") as mock_config:
            with patch("src.asc_ops.cli.sync.SyncStateManager") as mock_sm_class:
                mock_sm = MagicMock()
                mock_sm_class.return_value = mock_sm
                mock_sm.get_sync_status.return_value.new_apis = []
                mock_sm.get_sync_status.return_value.changed_apis = []
                mock_sm.get_sync_status.return_value.deleted_apis = []
                mock_sm.get_sync_status.return_value.failed_apis = []
                mock_sm.get_sync_status.return_value.status = SyncStatus.IDLE
                mock_sm.get_sync_status.return_value.last_sync_at = None
                mock_sm.get_sync_status.return_value.started_at = None
                mock_sm.get_sync_status.return_value.completed_at = None

                result = await run_sync(mock_args)

                assert result == 0

    @pytest.mark.asyncio
    async def test_run_sync_api_default(self, mock_args):
        """测试默认同步 API"""
        mock_args.api = False  # 默认值

        with patch("src.asc_ops.cli.sync.get_config") as mock_config:
            with patch("src.asc_ops.cli.sync.SyncStateManager") as mock_sm_class:
                mock_sm = MagicMock()
                mock_sm_class.return_value = mock_sm
                mock_sm.get_sync_status.return_value.status = SyncStatus.IDLE
                mock_sm.start_sync = MagicMock()
                mock_sm.complete_sync = MagicMock()

                with patch("src.asc_ops.cli.sync.sync_apis", new_callable=AsyncMock) as mock_sync_apis:
                    mock_sync_apis.return_value = True

                    result = await run_sync(mock_args)

                    assert result == 0
                    mock_sm.start_sync.assert_called_once_with("api")

    @pytest.mark.asyncio
    async def test_run_sync_with_force(self, mock_args):
        """测试强制同步"""
        mock_args.force = True

        with patch("src.asc_ops.cli.sync.get_config") as mock_config:
            with patch("src.asc_ops.cli.sync.SyncStateManager") as mock_sm_class:
                mock_sm = MagicMock()
                mock_sm_class.return_value = mock_sm
                mock_sm.get_sync_status.return_value.status = SyncStatus.SYNCING
                mock_sm.start_sync = MagicMock()
                mock_sm.complete_sync = MagicMock()

                with patch("src.asc_ops.cli.sync.sync_apis", new_callable=AsyncMock) as mock_sync_apis:
                    mock_sync_apis.return_value = True

                    result = await run_sync(mock_args)

                    assert result == 0
                    mock_sm.start_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_sync_already_syncing(self, mock_args):
        """测试同步已在进行中"""
        mock_args.force = False

        with patch("src.asc_ops.cli.sync.get_config") as mock_config:
            with patch("src.asc_ops.cli.sync.SyncStateManager") as mock_sm_class:
                mock_sm = MagicMock()
                mock_sm_class.return_value = mock_sm
                mock_sm.get_sync_status.return_value.status = SyncStatus.SYNCING
                mock_sm.get_sync_status.return_value.started_at = "2026-04-10T12:00:00"

                with patch("sys.stdout", new_callable=StringIO):
                    result = await run_sync(mock_args)

                    assert result == 1

    @pytest.mark.asyncio
    async def test_run_sync_all(self, mock_args):
        """测试全量同步"""
        mock_args.all = True

        with patch("src.asc_ops.cli.sync.get_config") as mock_config:
            with patch("src.asc_ops.cli.sync.SyncStateManager") as mock_sm_class:
                mock_sm = MagicMock()
                mock_sm_class.return_value = mock_sm
                mock_sm.get_sync_status.return_value.status = SyncStatus.IDLE
                mock_sm.start_sync = MagicMock()
                mock_sm.complete_sync = MagicMock()

                with patch("src.asc_ops.cli.sync.sync_apis", new_callable=AsyncMock) as mock_sync_apis:
                    with patch("src.asc_ops.cli.sync.sync_operators", new_callable=AsyncMock) as mock_sync_ops:
                        mock_sync_apis.return_value = True
                        mock_sync_ops.return_value = True

                        result = await run_sync(mock_args)

                        assert result == 0
                        mock_sm.start_sync.assert_called_once_with("all")

    @pytest.mark.asyncio
    async def test_run_sync_exception(self, mock_args):
        """测试异常处理"""
        mock_args.api = True

        with patch("src.asc_ops.cli.sync.get_config") as mock_config:
            with patch("src.asc_ops.cli.sync.SyncStateManager") as mock_sm_class:
                mock_sm = MagicMock()
                mock_sm_class.return_value = mock_sm
                mock_sm.get_sync_status.return_value.status = SyncStatus.IDLE
                mock_sm.start_sync = MagicMock(side_effect=Exception("Test error"))

                result = await run_sync(mock_args)

                assert result == 1
