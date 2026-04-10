# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
准确性计算模块

基于纠错率和引用次数计算知识准确性分数
"""

from dataclasses import dataclass
from typing import Optional

from .config import RankingConfig


@dataclass
class AccuracyScore:
    """准确性评分结果"""
    total: float               # 总分 [0, 1]
    correction_count: int      # 纠错次数
    citation_count: int       # 引用次数
    error_rate: float          # 错误率


class AccuracyCalculator:
    """准确性评估器

    基于纠错率和引用次数计算准确性:
    AccuracyScore = 1 - corrections / citations

    规则:
    - 有引用时: accuracy = 1 - (corrections / citations)
    - 无引用时: 使用默认准确性 (0.5)
    - 错误率超过 100% 时返回 0
    """

    def __init__(self, config: RankingConfig, redis_client=None):
        """
        初始化准确性评估器

        Args:
            config: 排序配置
            redis_client: Redis 客户端 (可选，用于异步获取统计数据)
        """
        self.config = config
        self.redis = redis_client

    async def calculate(
        self,
        entity_id: str,
        entity_type: str,
        citation_count: Optional[int] = None,
        correction_count: Optional[int] = None
    ) -> AccuracyScore:
        """
        异步计算准确性分数

        Args:
            entity_id: 实体ID
            entity_type: 实体类型 (bug | optimization | api)
            citation_count: 引用次数 (可选，从Redis获取)
            correction_count: 纠错次数 (可选，从Redis获取)

        Returns:
            AccuracyScore: 准确性评分结果
        """
        # 如果未提供，从 Redis 获取
        if citation_count is None or correction_count is None:
            if self.redis:
                citation_count, correction_count = await self._fetch_from_redis(
                    entity_id, entity_type
                )
            else:
                citation_count = 0
                correction_count = 0

        return self.calculate_sync(
            citation_count or 0,
            correction_count or 0
        )

    def calculate_sync(
        self,
        citation_count: int,
        correction_count: int
    ) -> AccuracyScore:
        """
        同步计算准确性分数

        Args:
            citation_count: 引用次数
            correction_count: 纠错次数

        Returns:
            AccuracyScore: 准确性评分结果
        """
        if citation_count == 0:
            # 无引用，使用默认分数
            error_rate = 0.0
            total = self.config.default_accuracy
        else:
            error_rate = correction_count / citation_count
            total = max(0, 1 - error_rate)

        return AccuracyScore(
            total=total,
            correction_count=correction_count,
            citation_count=citation_count,
            error_rate=error_rate
        )

    async def _fetch_from_redis(
        self,
        entity_id: str,
        entity_type: str
    ) -> tuple[int, int]:
        """
        从 Redis 获取引用和纠错统计

        Args:
            entity_id: 实体ID
            entity_type: 实体类型

        Returns:
            (citation_count, correction_count) tuple
        """
        prefix = f"ascendc:stats:{entity_type}"

        citations_key = f"{prefix}:citation:{entity_id}"
        corrections_key = f"{prefix}:correction:{entity_id}"

        try:
            citations = await self.redis.get(citations_key)
            corrections = await self.redis.get(corrections_key)
        except Exception:
            # Redis 操作失败，返回默认值
            return 0, 0

        return int(citations or 0), int(corrections or 0)

    def calculate_from_metadata(self, metadata: dict) -> AccuracyScore:
        """
        从元数据计算准确性分数

        Args:
            metadata: 包含 citation_count, correction_count 的字典

        Returns:
            AccuracyScore: 准确性评分结果
        """
        citation_count = metadata.get("citation_count", 0)
        correction_count = metadata.get("correction_count", 0)

        # 也支持其他可能的字段名
        if citation_count == 0:
            citation_count = metadata.get("citations", 0)
        if correction_count == 0:
            correction_count = metadata.get("corrections", 0)

        return self.calculate_sync(citation_count, correction_count)

    def calculate_batch(
        self,
        items: list[dict]
    ) -> list[AccuracyScore]:
        """
        批量计算准确性分数

        Args:
            items: 包含 citation_count, correction_count 的字典列表

        Returns:
            AccuracyScore 列表
        """
        return [
            self.calculate_from_metadata(item)
            for item in items
        ]
