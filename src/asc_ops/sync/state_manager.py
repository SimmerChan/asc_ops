# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
同步状态管理模块

管理增量同步的状态存储和查询
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """同步状态"""
    IDLE = "idle"
    SYNCING = "syncing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SyncState:
    """同步状态数据"""
    status: SyncStatus = SyncStatus.IDLE
    last_sync_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    new_apis: List[str] = field(default_factory=list)
    changed_apis: List[str] = field(default_factory=list)
    deleted_apis: List[str] = field(default_factory=list)
    failed_apis: List[str] = field(default_factory=list)
    sync_type: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "status": self.status.value,
            "last_sync_at": self.last_sync_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "new_apis": self.new_apis,
            "changed_apis": self.changed_apis,
            "deleted_apis": self.deleted_apis,
            "failed_apis": self.failed_apis,
            "sync_type": self.sync_type,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SyncState":
        """从字典创建"""
        if data is None:
            return cls()
        return cls(
            status=SyncStatus(data.get("status", "idle")),
            last_sync_at=data.get("last_sync_at"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            new_apis=data.get("new_apis", []),
            changed_apis=data.get("changed_apis", []),
            deleted_apis=data.get("deleted_apis", []),
            failed_apis=data.get("failed_apis", []),
            sync_type=data.get("sync_type"),
            error_message=data.get("error_message"),
        )


class SyncStateManager:
    """
    同步状态管理器

    使用 Redis 存储同步状态，支持断点续采
    """

    # Redis key 前缀
    KEY_PREFIX = "asc_ops:sync:state"

    # 各字段对应的 key
    KEYS = {
        "status": "status",
        "last_sync_at": "last_sync_at",
        "started_at": "started_at",
        "completed_at": "completed_at",
        "new_apis": "new_apis",
        "changed_apis": "changed_apis",
        "deleted_apis": "deleted_apis",
        "failed_apis": "failed_apis",
        "sync_type": "sync_type",
        "error_message": "error_message",
    }

    def __init__(self, redis_client=None):
        """
        初始化同步状态管理器

        Args:
            redis_client: Redis 客户端实例 (可选，不提供则使用内存存储)
        """
        self._redis = redis_client
        self._use_redis = redis_client is not None
        self._memory_state: Dict[str, Any] = {}

        logger.info(
            f"SyncStateManager initialized: use_redis={self._use_redis}"
        )

    def _get_key(self, field: str) -> str:
        """获取完整 Redis key"""
        return f"{self.KEY_PREFIX}:{field}"

    def _get_state(self) -> SyncState:
        """获取当前同步状态"""
        if self._use_redis and self._redis:
            return self._get_state_from_redis()
        return self._get_state_from_memory()

    def _get_state_from_redis(self) -> SyncState:
        """从 Redis 获取状态"""
        data = {}
        for field_name, key in self.KEYS.items():
            full_key = self._get_key(key)
            value = self._redis.get(full_key)
            if value is not None:
                if field_name in ("new_apis", "changed_apis", "deleted_apis", "failed_apis"):
                    data[field_name] = json.loads(value) if value else []
                else:
                    data[field_name] = value
        return SyncState.from_dict(data)

    def _get_state_from_memory(self) -> SyncState:
        """从内存获取状态"""
        return SyncState.from_dict(self._memory_state)

    def _save_state(self, state: SyncState) -> None:
        """保存同步状态"""
        if self._use_redis and self._redis:
            self._save_state_to_redis(state)
        else:
            self._save_state_to_memory(state)

    def _save_state_to_redis(self, state: SyncState) -> None:
        """保存状态到 Redis"""
        data = state.to_dict()
        for field_name, key in self.KEYS.items():
            full_key = self._get_key(key)
            value = data.get(field_name)
            if value is not None:
                if isinstance(value, list):
                    self._redis.set(full_key, json.dumps(value))
                else:
                    self._redis.set(full_key, value)
            else:
                self._redis.delete(full_key)

    def _save_state_to_memory(self, state: SyncState) -> None:
        """保存状态到内存"""
        self._memory_state = state.to_dict()

    def get_sync_status(self) -> SyncState:
        """
        获取当前同步状态

        Returns:
            SyncState: 当前同步状态
        """
        return self._get_state()

    def start_sync(self, sync_type: str = "all") -> None:
        """
        开始同步

        Args:
            sync_type: 同步类型 (api/operator/all)
        """
        now = datetime.now().isoformat()
        state = self._get_state()

        state.status = SyncStatus.SYNCING
        state.started_at = now
        state.completed_at = None
        state.sync_type = sync_type
        state.error_message = None
        # 清空本次同步的结果
        state.new_apis = []
        state.changed_apis = []
        state.deleted_apis = []
        state.failed_apis = []

        self._save_state(state)
        logger.info(f"Sync started: type={sync_type}, started_at={now}")

    def complete_sync(
        self,
        new_apis: Optional[List[str]] = None,
        changed_apis: Optional[List[str]] = None,
        deleted_apis: Optional[List[str]] = None,
        failed_apis: Optional[List[str]] = None,
    ) -> None:
        """
        完成同步

        Args:
            new_apis: 新增的 API IDs
            changed_apis: 变更的 API IDs
            deleted_apis: 删除的 API IDs
            failed_apis: 失败的 API IDs
        """
        now = datetime.now().isoformat()
        state = self._get_state()

        state.status = SyncStatus.COMPLETED
        state.completed_at = now
        state.last_sync_at = now

        if new_apis is not None:
            state.new_apis = new_apis
        if changed_apis is not None:
            state.changed_apis = changed_apis
        if deleted_apis is not None:
            state.deleted_apis = deleted_apis
        if failed_apis is not None:
            state.failed_apis = failed_apis

        self._save_state(state)
        logger.info(
            f"Sync completed: new={len(state.new_apis)}, "
            f"changed={len(state.changed_apis)}, "
            f"deleted={len(state.deleted_apis)}, "
            f"failed={len(state.failed_apis)}"
        )

    def fail_sync(self, error_message: str) -> None:
        """
        同步失败

        Args:
            error_message: 错误信息
        """
        now = datetime.now().isoformat()
        state = self._get_state()

        state.status = SyncStatus.FAILED
        state.completed_at = now
        state.error_message = error_message

        self._save_state(state)
        logger.error(f"Sync failed: {error_message}")

    def update_progress(
        self,
        new_apis: Optional[List[str]] = None,
        changed_apis: Optional[List[str]] = None,
        deleted_apis: Optional[List[str]] = None,
        failed_apis: Optional[List[str]] = None,
    ) -> None:
        """
        更新同步进度

        Args:
            new_apis: 新增的 API IDs
            changed_apis: 变更的 API IDs
            deleted_apis: 删除的 API IDs
            failed_apis: 失败的 API IDs
        """
        state = self._get_state()

        if new_apis is not None:
            state.new_apis = new_apis
        if changed_apis is not None:
            state.changed_apis = changed_apis
        if deleted_apis is not None:
            state.deleted_apis = deleted_apis
        if failed_apis is not None:
            state.failed_apis = failed_apis

        self._save_state(state)

    def reset(self) -> None:
        """重置同步状态"""
        state = SyncState()
        self._save_state(state)
        logger.info("Sync state reset")
