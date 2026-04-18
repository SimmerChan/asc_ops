# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
时效性计算模块

基于指数衰减模型计算知识时效性分数
"""

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Union, Optional

from .config import RankingConfig


@dataclass
class RecencyScore:
    """时效性评分结果"""
    total: float               # 总分 [0, 1]
    days_since_update: int     # 距离上次更新的天数
    lambda_value: float        # 使用的衰减系数


class RecencyCalculator:
    """时效性计算器

    使用指数衰减模型:
    RecencyScore = e^(-λ × days)

    其中:
    - λ (lambda): 衰减系数，默认 0.05
    - days: 距离上次更新的天数

    衰减示例:
    - 0 天: 1.0
    - 7 天: 0.70
    - 30 天: 0.22
    - 90 天: 0.01
    """

    def __init__(self, config: RankingConfig):
        """
        初始化时效性计算器

        Args:
            config: 排序配置
        """
        self.config = config

    def calculate(
        self,
        last_updated: Union[datetime, str, int],
        reference_time: Optional[datetime] = None
    ) -> RecencyScore:
        """
        计算时效性分数

        Args:
            last_updated: 上次更新时间 (datetime对象、ISO字符串或Unix时间戳)
            reference_time: 参考时间，默认为当前时间

        Returns:
            RecencyScore: 时效性评分结果
        """
        if reference_time is None:
            reference_time = datetime.now()

        # 解析时间
        if isinstance(last_updated, str):
            try:
                last_updated_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                # 如果是 aware datetime，移除时区信息（统一使用本地时间计算）
                if last_updated_dt.tzinfo is not None:
                    last_updated_dt = last_updated_dt.astimezone().replace(tzinfo=None)
            except ValueError:
                # 尝试解析为 Unix 时间戳
                try:
                    last_updated_dt = datetime.fromtimestamp(float(last_updated))
                except ValueError:
                    # 无法解析，返回默认分数
                    return RecencyScore(
                        total=self.config.default_accuracy,
                        days_since_update=self.config.max_recency_days,
                        lambda_value=self.config.recency_lambda
                    )
        elif isinstance(last_updated, int):
            try:
                last_updated_dt = datetime.fromtimestamp(last_updated)
            except ValueError:
                return RecencyScore(
                    total=self.config.default_accuracy,
                    days_since_update=self.config.max_recency_days,
                    lambda_value=self.config.recency_lambda
                )
        else:
            last_updated_dt = last_updated

        # 计算天数差
        delta = reference_time - last_updated_dt
        days = max(0, delta.days)

        # 限制最大天数
        capped_days = min(days, self.config.max_recency_days)

        # 指数衰减计算: e^(-λ × days)
        lambda_val = self.config.recency_lambda
        score = math.exp(-lambda_val * capped_days)

        return RecencyScore(
            total=score,
            days_since_update=days,
            lambda_value=lambda_val
        )

    def calculate_from_metadata(
        self,
        metadata: dict,
        reference_time: Optional[datetime] = None,
    ) -> RecencyScore:
        """
        从元数据计算时效性分数

        Args:
            metadata: 包含 last_updated/updated_at/timestamp 的字典
            reference_time: 参考时间，默认为当前时间

        Returns:
            RecencyScore: 时效性评分结果
        """
        # 尝试多个可能的时间字段
        last_updated = (
            metadata.get("last_updated") or
            metadata.get("updated_at") or
            metadata.get("timestamp") or
            metadata.get("last_sync_time")
        )

        if last_updated is None:
            # 无时间信息，返回默认分数
            return RecencyScore(
                total=self.config.default_accuracy,
                days_since_update=self.config.max_recency_days,
                lambda_value=self.config.recency_lambda
            )

        return self.calculate(last_updated, reference_time=reference_time)

    def get_decay_table(self, max_days: int = 90) -> list[tuple[int, float]]:
        """
        获取衰减表示例 (用于调试和文档)

        Args:
            max_days: 最大天数

        Returns:
            list of (days, score) tuples
        """
        return [
            (days, round(math.exp(-self.config.recency_lambda * days), 4))
            for days in range(0, max_days + 1, 7)
        ]
