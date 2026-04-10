# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
排序配置模块

定义置信度感知排序所需的配置参数
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RankingConfig:
    """排序配置

    置信度感知排序层配置，包含权威性、时效性、准确性三个维度的权重和参数
    """

    # 权重配置 (默认: 权威性50%, 时效性30%, 准确性20%)
    authority_weight: float = 0.5
    recency_weight: float = 0.3
    accuracy_weight: float = 0.2

    # 权威性配置
    source_weights: dict = field(default_factory=lambda: {
        "official": 1.0,   # 昇腾官方
        "community": 0.7,  # 社区
        "other": 0.5        # 其他
    })
    contributor_weights: dict = field(default_factory=lambda: {
        "core": 1.0,       # 核心贡献者
        "active": 0.8,     # 活跃贡献者
        "newcomer": 0.6    # 新人
    })

    # 时效性配置
    recency_lambda: float = 0.05  # 指数衰减系数
    max_recency_days: int = 365   # 最大时效天数

    # 准确性配置
    default_accuracy: float = 0.5  # 无引用时的默认准确性

    def __post_init__(self):
        """验证配置"""
        # 验证权重和为1
        total = self.authority_weight + self.recency_weight + self.accuracy_weight
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"Weights must sum to 1.0, got {total}. "
                f"authority={self.authority_weight}, "
                f"recency={self.recency_weight}, "
                f"accuracy={self.accuracy_weight}"
            )

        # 验证 recency_lambda
        if self.recency_lambda <= 0:
            raise ValueError(f"recency_lambda must be positive, got {self.recency_lambda}")

        # 验证 default_accuracy
        if not 0 <= self.default_accuracy <= 1:
            raise ValueError(f"default_accuracy must be in [0, 1], got {self.default_accuracy}")

    def with_weights(
        self,
        authority: Optional[float] = None,
        recency: Optional[float] = None,
        accuracy: Optional[float] = None
    ) -> "RankingConfig":
        """创建新的配置，修改部分权重"""
        import copy
        new_config = copy.deepcopy(self)
        if authority is not None:
            new_config.authority_weight = authority
        if recency is not None:
            new_config.recency_weight = recency
        if accuracy is not None:
            new_config.accuracy_weight = accuracy
        return new_config


# 全局默认配置
DEFAULT_RANKING_CONFIG = RankingConfig()
