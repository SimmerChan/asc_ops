# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
引用追踪模块

追踪知识的引用次数和纠错次数，支持引用频率分析和时效性排序
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from ..storage.redis_client import RedisClient

logger = logging.getLogger(__name__)


class EntityType(Enum):
    """实体类型"""
    BUG = "bug"
    OPTIMIZATION = "optimization"
    API = "api"


@dataclass
class CitationStats:
    """引用统计"""
    entity_id: str
    entity_type: str
    citation_count: int
    correction_count: int
    last_cited_at: Optional[datetime] = None
    last_corrected_at: Optional[datetime] = None

    @property
    def error_rate(self) -> float:
        """错误率"""
        if self.citation_count == 0:
            return 0.0
        return self.correction_count / self.citation_count

    @property
    def accuracy(self) -> float:
        """准确性 (1 - 错误率)"""
        return 1.0 - self.error_rate

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "citation_count": self.citation_count,
            "correction_count": self.correction_count,
            "error_rate": round(self.error_rate, 4),
            "accuracy": round(self.accuracy, 4),
            "last_cited_at": self.last_cited_at.isoformat() if self.last_cited_at else None,
            "last_corrected_at": self.last_corrected_at.isoformat() if self.last_corrected_at else None,
        }


class CitationTracker:
    """
    引用追踪器

    追踪知识条目的引用次数和纠错次数

    Redis Key Pattern (统一为 ascendc:stats:* 前缀):
    - ascendc:stats:citation:{entity_type} -> Sorted Set (entity_id -> citation_count)
    - ascendc:stats:correction:{entity_type} -> Sorted Set (entity_id -> correction_count)
    - ascendc:stats:last_cited:{entity_type}:{entity_id} -> String (ISO timestamp)
    - ascendc:stats:last_corrected:{entity_type}:{entity_id} -> String (ISO timestamp)
    """

    # 统一前缀：ascendc:stats:*
    CITATION_KEY = "ascendc:stats:citation:{entity_type}"
    CORRECTION_KEY = "ascendc:stats:correction:{entity_type}"
    LAST_CITED_KEY = "ascendc:stats:last_cited:{entity_type}:{entity_id}"
    LAST_CORRECTED_KEY = "ascendc:stats:last_corrected:{entity_type}:{entity_id}"

    def __init__(self, redis_client: Optional[RedisClient] = None):
        """
        初始化引用追踪器

        Args:
            redis_client: Redis 客户端 (可选，默认使用 mock)
        """
        self.redis = redis_client or RedisClient(mock=True)
        logger.info("CitationTracker initialized")

    def _get_citation_key(self, entity_type: str) -> str:
        """获取引用集合的 key"""
        return self.CITATION_KEY.format(entity_type=entity_type)

    def _get_correction_key(self, entity_type: str) -> str:
        """获取纠错集合的 key"""
        return self.CORRECTION_KEY.format(entity_type=entity_type)

    def _get_last_cited_key(self, entity_type: str, entity_id: str) -> str:
        """获取最后引用时间的 key"""
        return self.LAST_CITED_KEY.format(entity_type=entity_type, entity_id=entity_id)

    def _get_last_corrected_key(self, entity_type: str, entity_id: str) -> str:
        """获取最后纠错时间的 key"""
        return self.LAST_CORRECTED_KEY.format(entity_type=entity_type, entity_id=entity_id)

    def record_citation(
        self,
        entity_id: str,
        entity_type: str,
        timestamp: Optional[datetime] = None
    ) -> int:
        """
        记录一次引用

        Args:
            entity_id: 实体 ID
            entity_type: 实体类型 (bug | optimization | api)
            timestamp: 引用时间 (可选，默认当前时间)

        Returns:
            新的引用总数
        """
        if timestamp is None:
            timestamp = datetime.now()

        entity_type = self._normalize_entity_type(entity_type)

        # 使用 Redis zincrby 增加引用计数
        citation_key = self._get_citation_key(entity_type)
        new_count = self._zincrby(citation_key, entity_id, 1)

        # 记录最后引用时间
        last_cited_key = self._get_last_cited_key(entity_type, entity_id)
        self.redis.set(last_cited_key, timestamp.isoformat())

        logger.debug(f"Recorded citation for {entity_type}:{entity_id}, count={new_count}")
        return int(new_count)

    def record_correction(
        self,
        entity_id: str,
        entity_type: str,
        timestamp: Optional[datetime] = None
    ) -> int:
        """
        记录一次纠错

        Args:
            entity_id: 实体 ID
            entity_type: 实体类型
            timestamp: 纠错时间 (可选，默认当前时间)

        Returns:
            新的纠错总数
        """
        if timestamp is None:
            timestamp = datetime.now()

        entity_type = self._normalize_entity_type(entity_type)

        # 增加纠错计数
        correction_key = self._get_correction_key(entity_type)
        new_count = self._zincrby(correction_key, entity_id, 1)

        # 记录最后纠错时间
        last_corrected_key = self._get_last_corrected_key(entity_type, entity_id)
        self.redis.set(last_corrected_key, timestamp.isoformat())

        logger.debug(f"Recorded correction for {entity_type}:{entity_id}, count={new_count}")
        return int(new_count)

    def get_stats(self, entity_id: str, entity_type: str) -> CitationStats:
        """
        获取实体的引用统计

        Args:
            entity_id: 实体 ID
            entity_type: 实体类型

        Returns:
            CitationStats: 引用统计
        """
        entity_type = self._normalize_entity_type(entity_type)

        # 获取引用计数
        citation_key = self._get_citation_key(entity_type)
        citation_count = self._zscore(citation_key, entity_id) or 0

        # 获取纠错计数
        correction_key = self._get_correction_key(entity_type)
        correction_count = self._zscore(correction_key, entity_id) or 0

        # 获取最后引用时间
        last_cited_key = self._get_last_cited_key(entity_type, entity_id)
        last_cited_str = self.redis.get(last_cited_key)
        last_cited_at = self._parse_datetime(last_cited_str)

        # 获取最后纠错时间
        last_corrected_key = self._get_last_corrected_key(entity_type, entity_id)
        last_corrected_str = self.redis.get(last_corrected_key)
        last_corrected_at = self._parse_datetime(last_corrected_str)

        return CitationStats(
            entity_id=entity_id,
            entity_type=entity_type,
            citation_count=int(citation_count),
            correction_count=int(correction_count),
            last_cited_at=last_cited_at,
            last_corrected_at=last_corrected_at,
        )

    def get_top_cited(
        self,
        entity_type: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        获取引用次数最多的知识条目

        Args:
            entity_type: 实体类型
            limit: 返回数量

        Returns:
            List of {entity_id, citation_count}
        """
        entity_type = self._normalize_entity_type(entity_type)
        citation_key = self._get_citation_key(entity_type)

        # 使用 zrevrange 获取 top N
        results = self._zrevrange(citation_key, 0, limit - 1, withscores=True)

        return [
            {"entity_id": item_id, "citation_count": int(score)}
            for item_id, score in results
        ]

    def get_top_inaccurate(
        self,
        entity_type: str,
        min_citations: int = 5,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        获取错误率最高的知识条目

        Args:
            entity_type: 实体类型
            min_citations: 最小引用数 (过滤低引用条目)
            limit: 返回数量

        Returns:
            List of {entity_id, error_rate, citation_count, correction_count}
        """
        entity_type = self._normalize_entity_type(entity_type)

        # 获取所有实体及其引用/纠错计数
        citation_key = self._get_citation_key(entity_type)
        correction_key = self._get_correction_key(entity_type)

        all_citations = self._zrange(citation_key, 0, -1, withscores=True)
        all_corrections = self._zrange(correction_key, 0, -1, withscores=True)

        # 构建映射
        citation_map = {item_id: int(score) for item_id, score in all_citations}
        correction_map = {item_id: int(score) for item_id, score in all_corrections}

        # 计算错误率并过滤
        items = []
        for entity_id, citations in citation_map.items():
            corrections = correction_map.get(entity_id, 0)
            if citations >= min_citations:
                error_rate = corrections / citations if citations > 0 else 0
                items.append({
                    "entity_id": entity_id,
                    "error_rate": round(error_rate, 4),
                    "citation_count": citations,
                    "correction_count": corrections,
                })

        # 按错误率排序
        items.sort(key=lambda x: x["error_rate"], reverse=True)
        return items[:limit]

    def get_entity_types(self) -> List[str]:
        """获取所有有统计数据的实体类型"""
        types = []
        for et in EntityType:
            citation_key = self._get_citation_key(et.value)
            if self._zcard(citation_key) > 0:
                types.append(et.value)
        return types

    def delete_stats(self, entity_id: str, entity_type: str) -> bool:
        """
        删除实体的统计数据

        Args:
            entity_id: 实体 ID
            entity_type: 实体类型

        Returns:
            是否成功删除
        """
        entity_type = self._normalize_entity_type(entity_type)

        citation_key = self._get_citation_key(entity_type)
        correction_key = self._get_correction_key(entity_type)
        last_cited_key = self._get_last_cited_key(entity_type, entity_id)
        last_corrected_key = self._get_last_corrected_key(entity_type, entity_id)

        # 从 sorted set 中移除
        self._zrem(citation_key, entity_id)
        self._zrem(correction_key, entity_id)

        # 删除时间戳
        self.redis.delete(last_cited_key, last_corrected_key)

        logger.info(f"Deleted stats for {entity_type}:{entity_id}")
        return True

    def _normalize_entity_type(self, entity_type: str) -> str:
        """规范化实体类型"""
        # 尝试匹配枚举
        try:
            return EntityType(entity_type).value
        except ValueError:
            pass

        # 尝试字符串匹配
        type_map = {
            "bug": EntityType.BUG.value,
            "bugs": EntityType.BUG.value,
            "bugfix": EntityType.BUG.value,
            "optimization": EntityType.OPTIMIZATION.value,
            "opt": EntityType.OPTIMIZATION.value,
            "opts": EntityType.OPTIMIZATION.value,
            "api": EntityType.API.value,
            "apis": EntityType.API.value,
        }
        return type_map.get(entity_type.lower(), entity_type)

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        """解析 datetime 字符串"""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    # ==================== Sorted Set 操作 ====================
    # 这些方法扩展了 RedisClient 的基本功能

    def _zincrby(self, key: str, member: str, amount: float) -> float:
        """增加 sorted set 中成员的分数"""
        if self.redis.is_mock:
            # Mock 实现
            if not hasattr(self.redis, '_sorted_sets'):
                self.redis._sorted_sets = {}
            if key not in self.redis._sorted_sets:
                self.redis._sorted_sets[key] = {}
            current = self.redis._sorted_sets[key].get(member, 0)
            new_score = current + amount
            self.redis._sorted_sets[key][member] = new_score
            return new_score
        else:
            return self.redis._client.zincrby(key, amount, member)

    def _zscore(self, key: str, member: str) -> Optional[float]:
        """获取 sorted set 中成员的分数"""
        if self.redis.is_mock:
            if not hasattr(self.redis, '_sorted_sets'):
                self.redis._sorted_sets = {}
            return self.redis._sorted_sets.get(key, {}).get(member)
        else:
            return self.redis._client.zscore(key, member)

    def _zrange(self, key: str, start: int, end: int, withscores: bool = False) -> List:
        """获取 sorted set 中指定范围的成员"""
        if self.redis.is_mock:
            if not hasattr(self.redis, '_sorted_sets'):
                self.redis._sorted_sets = {}
            data = self.redis._sorted_sets.get(key, {})
            items = sorted(data.items(), key=lambda x: x[1])
            if end == -1:
                result = items[start:]
            else:
                result = items[start:end + 1]
            if withscores:
                return result
            return [item[0] for item in result]
        else:
            return self.redis._client.zrange(key, start, end, withscores=withscores)

    def _zrevrange(self, key: str, start: int, end: int, withscores: bool = False) -> List:
        """获取 sorted set 中指定范围的成员 (按分数降序)"""
        if self.redis.is_mock:
            if not hasattr(self.redis, '_sorted_sets'):
                self.redis._sorted_sets = {}
            data = self.redis._sorted_sets.get(key, {})
            items = sorted(data.items(), key=lambda x: x[1], reverse=True)
            if end == -1:
                result = items[start:]
            else:
                result = items[start:end + 1]
            if withscores:
                return result
            return [item[0] for item in result]
        else:
            return self.redis._client.zrevrange(key, start, end, withscores=withscores)

    def _zcard(self, key: str) -> int:
        """获取 sorted set 的基数 (成员数量)"""
        if self.redis.is_mock:
            if not hasattr(self.redis, '_sorted_sets'):
                self.redis._sorted_sets = {}
            return len(self.redis._sorted_sets.get(key, {}))
        else:
            return self.redis._client.zcard(key)

    def _zrem(self, key: str, *members: str) -> int:
        """从 sorted set 中移除成员"""
        if self.redis.is_mock:
            if not hasattr(self.redis, '_sorted_sets'):
                self.redis._sorted_sets = {}
            if key not in self.redis._sorted_sets:
                return 0
            removed = 0
            for member in members:
                if member in self.redis._sorted_sets[key]:
                    del self.redis._sorted_sets[key][member]
                    removed += 1
            return removed
        else:
            return self.redis._client.zrem(key, *members)
