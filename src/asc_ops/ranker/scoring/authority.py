# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
权威性评估模块

基于来源类型和贡献者级别计算权威性分数
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union

from .config import RankingConfig


class SourceType(Enum):
    """来源类型"""
    OFFICIAL = "official"      # 昇腾官方
    COMMUNITY = "community"    # 社区贡献
    OTHER = "other"            # 其他来源


class ContributorLevel(Enum):
    """贡献者级别"""
    CORE = "core"              # 核心贡献者
    ACTIVE = "active"          # 活跃贡献者
    NEWCOMER = "newcomer"      # 新人


@dataclass
class AuthorityScore:
    """权威性评分结果"""
    total: float               # 总分 [0, 1]
    source_weight: float       # 来源权重
    contributor_weight: float  # 贡献者权重
    source_type: SourceType
    contributor_level: ContributorLevel


class AuthorityScorer:
    """权威性评估器

    计算公式: AuthorityScore = SourceWeight × ContributorWeight

    来源权重:
    - official (昇腾官方): 1.0
    - community (社区): 0.7
    - other (其他): 0.5

    贡献者权重:
    - core (核心贡献者): 1.0
    - active (活跃贡献者): 0.8
    - newcomer (新人): 0.6
    """

    def __init__(self, config: RankingConfig):
        """
        初始化权威性评估器

        Args:
            config: 排序配置
        """
        self.config = config

    def calculate(
        self,
        source_type: Union[SourceType, str],
        contributor_level: Union[ContributorLevel, str, None] = None,
        author: Optional[str] = None
    ) -> AuthorityScore:
        """
        计算权威性分数

        Args:
            source_type: 来源类型 (枚举或字符串)
            contributor_level: 贡献者级别 (可选，默认为 ACTIVE)
            author: 作者标识 (暂未使用，预留扩展)

        Returns:
            AuthorityScore: 权威性评分结果
        """
        # 解析 source_type
        if isinstance(source_type, str):
            try:
                source_type = SourceType(source_type)
            except ValueError:
                source_type = SourceType.OTHER

        # 获取来源权重
        source_weight = self.config.source_weights.get(source_type.value, 0.5)

        # 获取贡献者权重
        if contributor_level is None:
            contributor_weight = 0.8  # 默认活跃贡献者
        elif isinstance(contributor_level, str):
            contributor_weight = self.config.contributor_weights.get(
                contributor_level, 0.8
            )
        else:
            contributor_weight = self.config.contributor_weights.get(
                contributor_level.value, 0.8
            )

        # 综合分数 = 来源权重 × 贡献者权重
        total = source_weight * contributor_weight

        # 确保 contributor_level 是枚举类型
        if isinstance(contributor_level, str):
            try:
                contributor_level = ContributorLevel(contributor_level)
            except ValueError:
                contributor_level = ContributorLevel.ACTIVE
        elif contributor_level is None:
            contributor_level = ContributorLevel.ACTIVE

        return AuthorityScore(
            total=total,
            source_weight=source_weight,
            contributor_weight=contributor_weight,
            source_type=source_type,
            contributor_level=contributor_level
        )

    def calculate_from_metadata(self, metadata: dict) -> AuthorityScore:
        """
        从元数据计算权威性分数

        Args:
            metadata: 包含 source_type, contributor_level, author 的字典

        Returns:
            AuthorityScore: 权威性评分结果
        """
        source_type = metadata.get("source_type", "other")

        # 尝试获取 contributor_level
        contributor_level = metadata.get("contributor_level")
        if contributor_level is None:
            contributor_level = metadata.get("contributor_level", "active")

        author = metadata.get("author")

        return self.calculate(source_type, contributor_level, author)
