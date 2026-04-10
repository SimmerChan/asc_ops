# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
置信度计算引擎

实现 API、Bug修复、优化知识的置信度评分算法
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class APISourceType(Enum):
    """API 来源类型"""
    OFFICIAL = "official"
    COMMUNITY = "community"


class ReviewStatus(Enum):
    """审核状态"""
    PENDING = "pending"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class ConfidenceScore:
    """置信度评分结果"""
    total_score: float
    is_low_confidence: bool = False
    breakdown: dict = field(default_factory=dict)

    def __post_init__(self):
        """验证分数范围"""
        self.total_score = max(0.0, min(1.0, self.total_score))
        self.is_low_confidence = self.total_score < 0.3

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "total_score": round(self.total_score, 3),
            "is_low_confidence": self.is_low_confidence,
            "breakdown": {k: round(v, 3) if isinstance(v, float) else v
                         for k, v in self.breakdown.items()},
        }


class ConfidenceCalculator(ABC):
    """置信度计算器基类"""

    # 置信度阈值
    LOW_CONFIDENCE_THRESHOLD = 0.3

    @abstractmethod
    def calculate(self, *args, **kwargs) -> ConfidenceScore:
        """计算置信度"""
        pass

    def _create_score(
        self,
        total: float,
        breakdown: dict,
    ) -> ConfidenceScore:
        """创建置信度评分"""
        return ConfidenceScore(
            total_score=total,
            is_low_confidence=total < self.LOW_CONFIDENCE_THRESHOLD,
            breakdown=breakdown,
        )


class APIConfidenceCalculator(ConfidenceCalculator):
    """
    API 置信度计算器

    公式: 来源权重 × 完整度 × 时效性
    - 来源权重: 官方 1.0, 社区 0.7
    - 完整度: 字段缺失扣分 (每缺失一个关键字段扣 0.1)
    - 时效性: 超过1年扣分 (每超1年扣 0.05, 最多扣 0.2)
    """

    # 关键字段 (缺失会扣分)
    CRITICAL_FIELDS = [
        "api_id",
        "canonical_name",
        "full_signature",
        "category",
        "description",
    ]

    # API 来源权重
    SOURCE_WEIGHTS = {
        APISourceType.OFFICIAL: 1.0,
        APISourceType.COMMUNITY: 0.7,
    }

    # 时效性扣分配置
    RECENCY_THRESHOLD_YEARS = 1
    RECENCY_PENALTY_PER_YEAR = 0.05
    MAX_RECENCY_PENALTY = 0.2

    def calculate(
        self,
        source_type: APISourceType,
        last_updated: datetime,
        missing_fields: list = None,
        **kwargs,
    ) -> ConfidenceScore:
        """
        计算 API 置信度

        Args:
            source_type: 来源类型
            last_updated: 最后更新时间
            missing_fields: 缺失的关键字段列表

        Returns:
            ConfidenceScore: 置信度评分
        """
        missing_fields = missing_fields or []

        # 来源权重
        source_weight = self.SOURCE_WEIGHTS.get(source_type, 0.7)
        breakdown = {"source_weight": source_weight}

        # 完整度 (每缺失一个关键字段扣 0.1)
        missing_count = len(missing_fields)
        completeness_penalty = min(missing_count * 0.1, 0.5)  # 最多扣 0.5
        completeness_score = 1.0 - completeness_penalty
        breakdown["completeness_score"] = completeness_score
        breakdown["missing_fields_count"] = missing_count

        # 时效性 (超过1年每超1年扣0.05, 最多扣0.2)
        age_years = (datetime.now() - last_updated).days / 365.0
        recency_penalty = min(
            max(0, age_years - self.RECENCY_THRESHOLD_YEARS) * self.RECENCY_PENALTY_PER_YEAR,
            self.MAX_RECENCY_PENALTY,
        )
        recency_score = 1.0 - recency_penalty
        breakdown["recency_score"] = recency_score
        breakdown["age_years"] = round(age_years, 2)

        # 综合得分
        total_score = source_weight * completeness_score * recency_score
        breakdown["total"] = total_score

        logger.debug(
            f"API confidence: source={source_weight}, "
            f"completeness={completeness_score}, recency={recency_score}, "
            f"total={total_score}"
        )

        return self._create_score(total_score, breakdown)


class BugFixConfidenceCalculator(ConfidenceCalculator):
    """
    Bug 修复知识置信度计算器

    公式: 根因完整度 × 修复方案完整度 × 来源权重 × 审核状态
    - 根因完整度: 有描述为 1.0, 无为 0.0
    - 修复方案完整度: 有 fix_pattern 为 1.0, 无为 0.3
    - 来源权重: PR 审核通过 1.0, 未审核 0.8
    - 审核状态: approved 1.0, reviewed 0.9, pending 0.7
    """

    # 审核状态权重
    REVIEW_STATUS_WEIGHTS = {
        ReviewStatus.APPROVED: 1.0,
        ReviewStatus.REVIEWED: 0.9,
        ReviewStatus.PENDING: 0.7,
        ReviewStatus.REJECTED: 0.0,
    }

    # 来源权重
    SOURCE_WEIGHTS = {
        "pr_approved": 1.0,
        "pr_merged": 0.8,
        "commit": 0.6,
    }

    def calculate(
        self,
        has_root_cause: bool,
        has_fix_pattern: bool,
        review_status: ReviewStatus,
        source_type: str = "pr_merged",
        has_trigger_conditions: bool = False,
        has_workarounds: bool = False,
        **kwargs,
    ) -> ConfidenceScore:
        """
        计算 Bug 修复知识置信度

        Args:
            has_root_cause: 是否有根因描述
            has_fix_pattern: 是否有修复方案
            review_status: 审核状态
            source_type: 来源类型 (pr_approved, pr_merged, commit)
            has_trigger_conditions: 是否有触发条件
            has_workarounds: 是否有 workaround

        Returns:
            ConfidenceScore: 置信度评分
        """
        # 根因完整度
        root_cause_score = 1.0 if has_root_cause else 0.0
        breakdown = {"root_cause_score": root_cause_score}

        # 修复方案完整度
        fix_pattern_score = 1.0 if has_fix_pattern else 0.3
        breakdown["fix_pattern_score"] = fix_pattern_score

        # 额外信息加成
        extra_info_score = 1.0
        if has_trigger_conditions:
            extra_info_score += 0.1
        if has_workarounds:
            extra_info_score += 0.1
        extra_info_score = min(extra_info_score, 1.2)  # 最多加成 0.2
        breakdown["extra_info_score"] = extra_info_score

        # 来源权重
        source_weight = self.SOURCE_WEIGHTS.get(source_type, 0.8)
        breakdown["source_weight"] = source_weight

        # 审核状态权重
        review_weight = self.REVIEW_STATUS_WEIGHTS.get(review_status, 0.7)
        breakdown["review_status_weight"] = review_weight

        # 综合得分
        total_score = (
            root_cause_score
            * fix_pattern_score
            * extra_info_score
            * source_weight
            * review_weight
        )
        breakdown["total"] = total_score

        logger.debug(
            f"BugFix confidence: root_cause={root_cause_score}, "
            f"fix={fix_pattern_score}, extra={extra_info_score}, "
            f"source={source_weight}, review={review_weight}, "
            f"total={total_score}"
        )

        return self._create_score(total_score, breakdown)


class OptimizationConfidenceCalculator(ConfidenceCalculator):
    """
    优化知识置信度计算器

    公式: 量化指标存在 × 描述完整度 × 来源权重
    - 量化指标: 有 improvement_ratio 为 1.0, 无为 0.6
    - 描述完整度: 有 optimization_description 为 1.0, 无为 0.5
    - 来源权重: 同 BugFix
    """

    # 量化指标权重
    HAS_METRICS_SCORE = 1.0
    NO_METRICS_SCORE = 0.6

    # 描述完整度
    HAS_DESCRIPTION_SCORE = 1.0
    NO_DESCRIPTION_SCORE = 0.5

    # 来源权重
    SOURCE_WEIGHTS = {
        "pr_approved": 1.0,
        "pr_merged": 0.8,
        "commit": 0.6,
    }

    def calculate(
        self,
        has_improvement_ratio: bool,
        has_description: bool,
        optimization_types: list = None,
        source_type: str = "pr_merged",
        review_status: ReviewStatus = ReviewStatus.PENDING,
        **kwargs,
    ) -> ConfidenceScore:
        """
        计算优化知识置信度

        Args:
            has_improvement_ratio: 是否有量化提升指标
            has_description: 是否有优化描述
            optimization_types: 优化类型列表
            source_type: 来源类型
            review_status: 审核状态

        Returns:
            ConfidenceScore: 置信度评分
        """
        optimization_types = optimization_types or []

        # 量化指标
        metrics_score = (
            self.HAS_METRICS_SCORE if has_improvement_ratio
            else self.NO_METRICS_SCORE
        )
        breakdown = {"metrics_score": metrics_score}

        # 描述完整度
        description_score = (
            self.HAS_DESCRIPTION_SCORE if has_description
            else self.NO_DESCRIPTION_SCORE
        )
        breakdown["description_score"] = description_score

        # 优化类型加成 (有明确的优化类型加 0.1)
        type_bonus = 0.1 if optimization_types else 0.0
        breakdown["type_bonus"] = type_bonus

        # 来源权重
        source_weight = self.SOURCE_WEIGHTS.get(source_type, 0.8)
        breakdown["source_weight"] = source_weight

        # 审核状态权重 (优化知识权重较低)
        review_weight_map = {
            ReviewStatus.APPROVED: 1.0,
            ReviewStatus.REVIEWED: 0.9,
            ReviewStatus.PENDING: 0.8,
            ReviewStatus.REJECTED: 0.0,
        }
        review_weight = review_weight_map.get(review_status, 0.8)
        breakdown["review_status_weight"] = review_weight

        # 综合得分
        total_score = (
            metrics_score
            * description_score
            * (1.0 + type_bonus)
            * source_weight
            * review_weight
        )
        breakdown["total"] = total_score

        logger.debug(
            f"Optimization confidence: metrics={metrics_score}, "
            f"desc={description_score}, type_bonus={type_bonus}, "
            f"source={source_weight}, review={review_weight}, "
            f"total={total_score}"
        )

        return self._create_score(total_score, breakdown)


class ConfidenceEngine:
    """
    置信度计算引擎

    统一接口计算各类知识的置信度
    """

    def __init__(self):
        """初始化置信度引擎"""
        self.api_calculator = APIConfidenceCalculator()
        self.bugfix_calculator = BugFixConfidenceCalculator()
        self.optimization_calculator = OptimizationConfidenceCalculator()

        logger.info("ConfidenceEngine initialized")

    def calculate_api_confidence(
        self,
        source_type: APISourceType,
        last_updated: datetime,
        missing_fields: list = None,
    ) -> ConfidenceScore:
        """
        计算 API 置信度

        Args:
            source_type: 来源类型
            last_updated: 最后更新时间
            missing_fields: 缺失字段列表

        Returns:
            ConfidenceScore: 置信度评分
        """
        return self.api_calculator.calculate(
            source_type=source_type,
            last_updated=last_updated,
            missing_fields=missing_fields,
        )

    def calculate_bugfix_confidence(
        self,
        has_root_cause: bool,
        has_fix_pattern: bool,
        review_status: ReviewStatus,
        source_type: str = "pr_merged",
        has_trigger_conditions: bool = False,
        has_workarounds: bool = False,
    ) -> ConfidenceScore:
        """
        计算 Bug 修复知识置信度

        Args:
            has_root_cause: 是否有根因
            has_fix_pattern: 是否有修复方案
            review_status: 审核状态
            source_type: 来源类型
            has_trigger_conditions: 是否有触发条件
            has_workarounds: 是否有 workaround

        Returns:
            ConfidenceScore: 置信度评分
        """
        return self.bugfix_calculator.calculate(
            has_root_cause=has_root_cause,
            has_fix_pattern=has_fix_pattern,
            review_status=review_status,
            source_type=source_type,
            has_trigger_conditions=has_trigger_conditions,
            has_workarounds=has_workarounds,
        )

    def calculate_optimization_confidence(
        self,
        has_improvement_ratio: bool,
        has_description: bool,
        optimization_types: list = None,
        source_type: str = "pr_merged",
        review_status: ReviewStatus = ReviewStatus.PENDING,
    ) -> ConfidenceScore:
        """
        计算优化知识置信度

        Args:
            has_improvement_ratio: 是否有量化指标
            has_description: 是否有描述
            optimization_types: 优化类型列表
            source_type: 来源类型
            review_status: 审核状态

        Returns:
            ConfidenceScore: 置信度评分
        """
        return self.optimization_calculator.calculate(
            has_improvement_ratio=has_improvement_ratio,
            has_description=has_description,
            optimization_types=optimization_types,
            source_type=source_type,
            review_status=review_status,
        )
