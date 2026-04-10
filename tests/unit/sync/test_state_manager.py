# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
同步状态管理器测试
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

from src.asc_ops.sync.state_manager import (
    SyncStateManager,
    SyncState,
    SyncStatus,
)


class TestSyncStatus:
    """SyncStatus 枚举测试"""

    def test_status_values(self):
        """测试状态枚举值"""
        assert SyncStatus.IDLE.value == "idle"
        assert SyncStatus.SYNCING.value == "syncing"
        assert SyncStatus.COMPLETED.value == "completed"
        assert SyncStatus.FAILED.value == "failed"

    def test_status_from_string(self):
        """测试从字符串创建状态"""
        assert SyncStatus("idle") == SyncStatus.IDLE
        assert SyncStatus("syncing") == SyncStatus.SYNCING
        assert SyncStatus("completed") == SyncStatus.COMPLETED
        assert SyncStatus("failed") == SyncStatus.FAILED


class TestSyncState:
    """SyncState 数据类测试"""

    def test_default_state(self):
        """测试默认状态"""
        state = SyncState()

        assert state.status == SyncStatus.IDLE
        assert state.last_sync_at is None
        assert state.started_at is None
        assert state.completed_at is None
        assert state.new_apis == []
        assert state.changed_apis == []
        assert state.deleted_apis == []
        assert state.failed_apis == []
        assert state.sync_type is None
        assert state.error_message is None

    def test_to_dict(self):
        """测试转换为字典"""
        state = SyncState(
            status=SyncStatus.SYNCING,
            last_sync_at="2026-04-10T12:00:00",
            started_at="2026-04-10T12:00:00",
            new_apis=["api1", "api2"],
            changed_apis=["api3"],
            failed_apis=[],
        )

        data = state.to_dict()

        assert data["status"] == "syncing"
        assert data["last_sync_at"] == "2026-04-10T12:00:00"
        assert data["started_at"] == "2026-04-10T12:00:00"
        assert data["new_apis"] == ["api1", "api2"]
        assert data["changed_apis"] == ["api3"]
        assert data["failed_apis"] == []

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "status": "completed",
            "last_sync_at": "2026-04-10T12:00:00",
            "started_at": "2026-04-10T11:55:00",
            "completed_at": "2026-04-10T12:00:00",
            "new_apis": ["api1"],
            "changed_apis": ["api2", "api3"],
            "deleted_apis": ["api4"],
            "failed_apis": [],
            "sync_type": "api",
            "error_message": None,
        }

        state = SyncState.from_dict(data)

        assert state.status == SyncStatus.COMPLETED
        assert state.last_sync_at == "2026-04-10T12:00:00"
        assert state.started_at == "2026-04-10T11:55:00"
        assert state.completed_at == "2026-04-10T12:00:00"
        assert state.new_apis == ["api1"]
        assert state.changed_apis == ["api2", "api3"]
        assert state.deleted_apis == ["api4"]
        assert state.failed_apis == []
        assert state.sync_type == "api"

    def test_from_dict_with_none(self):
        """测试从 None 创建"""
        state = SyncState.from_dict(None)

        assert state.status == SyncStatus.IDLE
        assert state.last_sync_at is None

    def test_from_dict_with_missing_fields(self):
        """测试从缺少字段的字典创建"""
        data = {"status": "idle"}

        state = SyncState.from_dict(data)

        assert state.status == SyncStatus.IDLE
        assert state.last_sync_at is None
        assert state.new_apis == []


class TestSyncStateManagerMemory:
    """SyncStateManager 内存存储测试"""

    def test_init_without_redis(self):
        """测试不使用 Redis 初始化"""
        manager = SyncStateManager()

        assert manager._use_redis is False
        assert manager._redis is None

    def test_get_sync_status_idle(self):
        """测试获取初始状态"""
        manager = SyncStateManager()
        status = manager.get_sync_status()

        assert status.status == SyncStatus.IDLE
        assert status.started_at is None
        assert status.completed_at is None

    def test_start_sync(self):
        """测试开始同步"""
        manager = SyncStateManager()
        manager.start_sync(sync_type="api")

        status = manager.get_sync_status()

        assert status.status == SyncStatus.SYNCING
        assert status.sync_type == "api"
        assert status.started_at is not None
        assert status.completed_at is None

    def test_complete_sync(self):
        """测试完成同步"""
        manager = SyncStateManager()
        manager.start_sync(sync_type="api")
        manager.complete_sync(
            new_apis=["api1", "api2"],
            changed_apis=["api3"],
            deleted_apis=[],
            failed_apis=[],
        )

        status = manager.get_sync_status()

        assert status.status == SyncStatus.COMPLETED
        assert status.completed_at is not None
        assert status.last_sync_at is not None
        assert status.new_apis == ["api1", "api2"]
        assert status.changed_apis == ["api3"]
        assert status.deleted_apis == []
        assert status.failed_apis == []

    def test_fail_sync(self):
        """测试同步失败"""
        manager = SyncStateManager()
        manager.start_sync(sync_type="api")
        manager.fail_sync("Network error")

        status = manager.get_sync_status()

        assert status.status == SyncStatus.FAILED
        assert status.completed_at is not None
        assert status.error_message == "Network error"

    def test_update_progress(self):
        """测试更新进度"""
        manager = SyncStateManager()
        manager.start_sync(sync_type="api")
        manager.update_progress(
            new_apis=["api1"],
            changed_apis=["api2"],
            failed_apis=["api3"],
        )

        status = manager.get_sync_status()

        assert status.new_apis == ["api1"]
        assert status.changed_apis == ["api2"]
        assert status.failed_apis == ["api3"]

    def test_reset(self):
        """测试重置状态"""
        manager = SyncStateManager()
        manager.start_sync(sync_type="api")
        manager.complete_sync(new_apis=["api1"])
        manager.reset()

        status = manager.get_sync_status()

        assert status.status == SyncStatus.IDLE
        assert status.last_sync_at is None
        assert status.new_apis == []


class TestSyncStateManagerRedis:
    """SyncStateManager Redis 存储测试"""

    @pytest.fixture
    def mock_redis(self):
        """创建模拟 Redis 客户端"""
        redis = MagicMock()
        redis.get = MagicMock(side_effect=self._mock_get)
        redis.set = MagicMock(side_effect=self._mock_set)
        redis.delete = MagicMock(side_effect=self._mock_delete)
        return redis

    def _mock_get(self, key):
        """模拟 GET"""
        return self._storage.get(key)

    def _mock_set(self, key, value):
        """模拟 SET"""
        self._storage[key] = value

    def _mock_delete(self, key):
        """模拟 DELETE"""
        self._storage.pop(key, None)

    @pytest.fixture(autouse=True)
    def setup_mock_storage(self):
        """设置模拟存储"""
        self._storage = {}

    def test_init_with_redis(self, mock_redis):
        """测试使用 Redis 初始化"""
        manager = SyncStateManager(redis_client=mock_redis)

        assert manager._use_redis is True
        assert manager._redis is mock_redis

    def test_start_sync_with_redis(self, mock_redis):
        """测试使用 Redis 开始同步"""
        manager = SyncStateManager(redis_client=mock_redis)
        manager.start_sync(sync_type="all")

        status = manager.get_sync_status()

        assert status.status == SyncStatus.SYNCING
        assert status.sync_type == "all"
        assert status.started_at is not None

    def test_complete_sync_with_redis(self, mock_redis):
        """测试使用 Redis 完成同步"""
        manager = SyncStateManager(redis_client=mock_redis)
        manager.start_sync(sync_type="api")
        manager.complete_sync(
            new_apis=["api1", "api2"],
            changed_apis=["api3"],
        )

        status = manager.get_sync_status()

        assert status.status == SyncStatus.COMPLETED
        assert status.new_apis == ["api1", "api2"]
        assert status.changed_apis == ["api3"]
        # 验证 Redis 被正确调用
        mock_redis.set.assert_called()

    def test_fail_sync_with_redis(self, mock_redis):
        """测试使用 Redis 同步失败"""
        manager = SyncStateManager(redis_client=mock_redis)
        manager.start_sync(sync_type="api")
        manager.fail_sync("Connection timeout")

        status = manager.get_sync_status()

        assert status.status == SyncStatus.FAILED
        assert status.error_message == "Connection timeout"

    def test_state_persistence(self, mock_redis):
        """测试状态持久化"""
        manager = SyncStateManager(redis_client=mock_redis)

        # 第一次设置
        manager.start_sync(sync_type="api")
        manager.update_progress(new_apis=["api1"])

        # 创建新 manager 实例（模拟重启）
        manager2 = SyncStateManager(redis_client=mock_redis)
        status = manager2.get_sync_status()

        # 验证状态被正确恢复
        assert status.status == SyncStatus.SYNCING
        assert status.sync_type == "api"
        assert status.new_apis == ["api1"]


class TestSyncStateManagerEdgeCases:
    """SyncStateManager 边界情况测试"""

    def test_complete_without_start(self):
        """测试未开始就完成"""
        manager = SyncStateManager()
        manager.complete_sync(new_apis=["api1"])

        status = manager.get_sync_status()
        assert status.status == SyncStatus.COMPLETED

    def test_fail_without_start(self):
        """测试未开始就失败"""
        manager = SyncStateManager()
        manager.fail_sync("Error")

        status = manager.get_sync_status()
        assert status.status == SyncStatus.FAILED

    def test_multiple_completes(self):
        """测试多次完成"""
        manager = SyncStateManager()
        manager.complete_sync(new_apis=["api1"])
        manager.complete_sync(new_apis=["api2"], changed_apis=["api3"])

        status = manager.get_sync_status()
        # 第二次调用会覆盖第一次的数据
        assert status.new_apis == ["api2"]
        assert status.changed_apis == ["api3"]

    def test_start_overwrites_previous(self):
        """测试开始会覆盖之前的状态"""
        manager = SyncStateManager()
        manager.start_sync(sync_type="api")
        manager.complete_sync(new_apis=["api1"])
        manager.start_sync(sync_type="operator")

        status = manager.get_sync_status()

        assert status.status == SyncStatus.SYNCING
        assert status.sync_type == "operator"
        # 新的开始应该清空之前的结果
        assert status.new_apis == []
