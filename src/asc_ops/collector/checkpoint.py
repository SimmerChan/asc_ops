# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
断点续采模块

提供采集进度跟踪和断点续采能力
"""

import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FailedAPI:
    """失败的 API"""
    api_id: str
    error: str
    attempts: int = 0
    last_attempt_at: Optional[str] = None


@dataclass
class CollectionCheckpoint:
    """采集断点"""
    collection_type: str  # "api" | "operator" | "bug_fix" | "optimization"
    total: int = 0
    completed: List[str] = field(default_factory=list)  # 已完成的 api_ids
    failed: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # api_id -> {error, attempts, last_attempt}
    last_batch_id: int = 0
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    status: str = "pending"  # "pending" | "running" | "paused" | "completed" | "failed"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "collection_type": self.collection_type,
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "last_batch_id": self.last_batch_id,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CollectionCheckpoint":
        """从字典创建"""
        return cls(
            collection_type=data.get("collection_type", ""),
            total=data.get("total", 0),
            completed=data.get("completed", []),
            failed=data.get("failed", {}),
            last_batch_id=data.get("last_batch_id", 0),
            started_at=data.get("started_at"),
            updated_at=data.get("updated_at"),
            status=data.get("status", "pending"),
        )


class CheckpointManager:
    """
    断点管理器

    使用 Redis 或本地文件存储断点
    """

    def __init__(
        self,
        storage_path: Optional[str] = None,
        use_redis: bool = False,
        redis_client=None,
    ):
        """
        初始化断点管理器

        Args:
            storage_path: 本地存储路径
            use_redis: 是否使用 Redis
            redis_client: Redis 客户端 (当 use_redis=True 时需要)
        """
        self._storage_path = storage_path
        self._use_redis = use_redis
        self._redis = redis_client
        self._cache: Dict[str, CollectionCheckpoint] = {}

        if not use_redis and storage_path:
            Path(storage_path).mkdir(parents=True, exist_ok=True)

        logger.info(
            f"CheckpointManager initialized: path={storage_path}, use_redis={use_redis}"
        )

    def _get_key(self, collection_type: str) -> str:
        """获取 Redis key"""
        return f"checkpoint:{collection_type}"

    def _get_file_path(self, collection_type: str) -> Path:
        """获取本地文件路径"""
        return Path(self._storage_path) / f"checkpoint_{collection_type}.json"

    def save_checkpoint(self, checkpoint: CollectionCheckpoint) -> None:
        """
        保存断点

        Args:
            checkpoint: 断点对象
        """
        checkpoint.updated_at = datetime.now().isoformat()

        if self._use_redis and self._redis:
            key = self._get_key(checkpoint.collection_type)
            self._redis.set(key, json.dumps(checkpoint.to_dict()))
        else:
            file_path = self._get_file_path(checkpoint.collection_type)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(checkpoint.to_dict(), f, ensure_ascii=False, indent=2)

        self._cache[checkpoint.collection_type] = checkpoint
        logger.debug(f"Checkpoint saved: {checkpoint.collection_type}")

    def load_checkpoint(self, collection_type: str) -> Optional[CollectionCheckpoint]:
        """
        加载断点

        Args:
            collection_type: 采集类型

        Returns:
            断点对象，如果不存在返回 None
        """
        # 先检查缓存
        if collection_type in self._cache:
            return self._cache[collection_type]

        checkpoint = None

        if self._use_redis and self._redis:
            key = self._get_key(collection_type)
            data = self._redis.get(key)
            if data:
                checkpoint = CollectionCheckpoint.from_dict(json.loads(data))
        else:
            file_path = self._get_file_path(collection_type)
            if file_path.exists():
                with open(file_path, encoding="utf-8") as f:
                    checkpoint = CollectionCheckpoint.from_dict(json.load(f))

        if checkpoint:
            self._cache[collection_type] = checkpoint

        return checkpoint

    def delete_checkpoint(self, collection_type: str) -> None:
        """
        删除断点

        Args:
            collection_type: 采集类型
        """
        if collection_type in self._cache:
            del self._cache[collection_type]

        if self._use_redis and self._redis:
            key = self._get_key(collection_type)
            self._redis.delete(key)
        else:
            file_path = self._get_file_path(collection_type)
            if file_path.exists():
                file_path.unlink()

        logger.info(f"Checkpoint deleted: {collection_type}")

    def mark_completed(
        self,
        collection_type: str,
        api_id: str,
        batch_id: Optional[int] = None,
    ) -> None:
        """
        标记 API 为已完成

        Args:
            collection_type: 采集类型
            api_id: API ID
            batch_id: 批次 ID (可选)
        """
        checkpoint = self.load_checkpoint(collection_type)
        if not checkpoint:
            checkpoint = CollectionCheckpoint(collection_type=collection_type)

        if api_id not in checkpoint.completed:
            checkpoint.completed.append(api_id)

        if batch_id is not None:
            checkpoint.last_batch_id = batch_id

        self.save_checkpoint(checkpoint)

    def mark_failed(
        self,
        collection_type: str,
        api_id: str,
        error: str,
    ) -> None:
        """
        标记 API 为失败

        Args:
            collection_type: 采集类型
            api_id: API ID
            error: 错误信息
        """
        checkpoint = self.load_checkpoint(collection_type)
        if not checkpoint:
            checkpoint = CollectionCheckpoint(collection_type=collection_type)

        failed_info = checkpoint.failed.get(api_id, {})
        failed_info["error"] = error
        failed_info["attempts"] = failed_info.get("attempts", 0) + 1
        failed_info["last_attempt_at"] = datetime.now().isoformat()
        checkpoint.failed[api_id] = failed_info

        self.save_checkpoint(checkpoint)

    def is_completed(self, collection_type: str, api_id: str) -> bool:
        """
        检查 API 是否已完成

        Args:
            collection_type: 采集类型
            api_id: API ID

        Returns:
            是否已完成
        """
        checkpoint = self.load_checkpoint(collection_type)
        if not checkpoint:
            return False
        return api_id in checkpoint.completed

    def get_pending_apis(
        self,
        collection_type: str,
        all_api_ids: List[str],
    ) -> List[str]:
        """
        获取待采集的 API 列表

        Args:
            collection_type: 采集类型
            all_api_ids: 所有 API IDs

        Returns:
            待采集的 API IDs (排除已完成的)
        """
        checkpoint = self.load_checkpoint(collection_type)
        if not checkpoint:
            return all_api_ids

        completed_set = set(checkpoint.completed)
        pending = [api_id for api_id in all_api_ids if api_id not in completed_set]

        logger.info(
            f"Pending APIs: {len(pending)}/{len(all_api_ids)} "
            f"(completed: {len(checkpoint.completed)}, failed: {len(checkpoint.failed)})"
        )

        return pending

    def get_progress(self, collection_type: str) -> Dict[str, Any]:
        """
        获取采集进度

        Args:
            collection_type: 采集类型

        Returns:
            进度信息
        """
        checkpoint = self.load_checkpoint(collection_type)
        if not checkpoint:
            return {
                "total": 0,
                "completed": 0,
                "failed": 0,
                "pending": 0,
                "progress": 0.0,
                "status": "not_started",
            }

        total = checkpoint.total
        completed = len(checkpoint.completed)
        failed = len(checkpoint.failed)
        pending = total - completed - failed
        progress = (completed / total * 100) if total > 0 else 0.0

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "progress": round(progress, 2),
            "status": checkpoint.status,
        }

    def reset(self, collection_type: str) -> None:
        """
        重置采集进度

        Args:
            collection_type: 采集类型
        """
        checkpoint = CollectionCheckpoint(collection_type=collection_type)
        self.save_checkpoint(checkpoint)
        logger.info(f"Checkpoint reset: {collection_type}")
