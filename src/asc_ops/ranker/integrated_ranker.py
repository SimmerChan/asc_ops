# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
综合排序器模块

整合权威性、时效性、准确性三个维度提供置信度感知排序能力
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, List

from .scoring.config import RankingConfig, DEFAULT_RANKING_CONFIG
from .scoring.authority import AuthorityScorer, AuthorityScore
from .scoring.recency import RecencyCalculator, RecencyScore
from .scoring.accuracy import AccuracyCalculator, AccuracyScore

logger = logging.getLogger(__name__)


@dataclass
class CompositeScore:
    """综合评分结果

    包含权威性、时效性、准确性三个维度的分数和最终综合分数
    """
    total: float               # 综合分数 [0, 1]
    authority: AuthorityScore
    recency: RecencyScore
    accuracy: AccuracyScore
    weights: tuple[float, float, float]  # (authority_w, recency_w, accuracy_w)

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "total": self.total,
            "authority": self.authority.total,
            "authority_source_weight": self.authority.source_weight,
            "authority_contributor_weight": self.authority.contributor_weight,
            "recency": self.recency.total,
            "recency_days": self.recency.days_since_update,
            "accuracy": self.accuracy.total,
            "accuracy_corrections": self.accuracy.correction_count,
            "accuracy_citations": self.accuracy.citation_count,
            "weights": self.weights
        }


@dataclass
class RankedItem:
    """排序项"""
    id: str
    score: CompositeScore
    metadata: dict = field(default_factory=dict)
    original_score: Optional[float] = None  # 原始检索分数


class ConfidenceRanker:
    """置信度感知排序器

    综合考虑权威性、时效性、准确性对结果进行重排序

    排序公式:
    ConfidenceScore = w1 × AuthorityScore + w2 × RecencyScore + w3 × AccuracyScore

    默认权重:
    - Authority: 0.5
    - Recency: 0.3
    - Accuracy: 0.2
    """

    def __init__(
        self,
        config: Optional[RankingConfig] = None,
        redis_client=None
    ):
        """
        初始化置信度排序器

        Args:
            config: 排序配置 (可选，使用默认配置)
            redis_client: Redis 客户端 (可选，用于异步获取引用统计)
        """
        self.config = config or DEFAULT_RANKING_CONFIG
        self.redis = redis_client

        # 初始化各维度评估器
        self.authority_scorer = AuthorityScorer(self.config)
        self.recency_calculator = RecencyCalculator(self.config)
        self.accuracy_calculator = AccuracyCalculator(self.config, redis_client)

        logger.info(
            f"ConfidenceRanker initialized: "
            f"authority={self.config.authority_weight}, "
            f"recency={self.config.recency_weight}, "
            f"accuracy={self.config.accuracy_weight}"
        )

    def calculate_composite_score(
        self,
        metadata: dict,
        citation_count: Optional[int] = None,
        correction_count: Optional[int] = None
    ) -> CompositeScore:
        """
        计算单个条目的综合分数

        Args:
            metadata: 条目元数据
            citation_count: 引用次数 (可选)
            correction_count: 纠错次数 (可选)

        Returns:
            CompositeScore: 综合评分结果
        """
        # 权威性评分
        authority = self.authority_scorer.calculate_from_metadata(metadata)

        # 时效性评分
        recency = self.recency_calculator.calculate_from_metadata(metadata)

        # 准确性评分
        if citation_count is not None or correction_count is not None:
            accuracy = self.accuracy_calculator.calculate_sync(
                citation_count or 0,
                correction_count or 0
            )
        else:
            accuracy = self.accuracy_calculator.calculate_from_metadata(metadata)

        # 加权综合
        w1, w2, w3 = (
            self.config.authority_weight,
            self.config.recency_weight,
            self.config.accuracy_weight
        )
        total = w1 * authority.total + w2 * recency.total + w3 * accuracy.total

        return CompositeScore(
            total=total,
            authority=authority,
            recency=recency,
            accuracy=accuracy,
            weights=(w1, w2, w3)
        )

    async def rank_results(
        self,
        results: List[dict],
        top_k: int = 5
    ) -> List[RankedItem]:
        """
        对检索结果进行重排序 (异步版本)

        Args:
            results: 检索结果列表，每项包含 id/score/metadata
            top_k: 返回前 k 项

        Returns:
            List[RankedItem]: 排序后的结果列表
        """
        scored_results = []

        for item in results:
            # 获取 ID
            item_id = (
                item.get("id") or
                item.get("bug_id") or
                item.get("opt_id") or
                item.get("operator_id") or
                item.get("api_id") or
                str(item)
            )

            # 获取/构建元数据
            metadata = item.get("metadata", {})
            if not metadata:
                # 从 item 本身提取可用字段
                metadata = {
                    k: v for k, v in item.items()
                    if k not in ("id", "score", "operator_id", "bug_id", "opt_id", "api_id")
                }

            # 补充元数据
            if "last_updated" not in metadata and "updated_at" in item:
                metadata["last_updated"] = item["updated_at"]

            # 计算综合分数
            composite = self.calculate_composite_score(metadata)

            scored_results.append(RankedItem(
                id=item_id,
                score=composite,
                metadata=metadata,
                original_score=item.get("score")
            ))

        # 按综合分数降序排列
        scored_results.sort(key=lambda x: x.score.total, reverse=True)

        logger.debug(f"Ranked {len(results)} results, returning top {top_k}")

        return scored_results[:top_k]

    def rank_results_sync(
        self,
        results: List[dict],
        top_k: int = 5
    ) -> List[RankedItem]:
        """
        对检索结果进行重排序 (同步版本)

        Args:
            results: 检索结果列表，每项包含 id/score/metadata
            top_k: 返回前 k 项

        Returns:
            List[RankedItem]: 排序后的结果列表
        """
        scored_results = []

        for item in results:
            # 获取 ID
            item_id = (
                item.get("id") or
                item.get("bug_id") or
                item.get("opt_id") or
                item.get("operator_id") or
                item.get("api_id") or
                str(item)
            )

            # 获取/构建元数据
            metadata = item.get("metadata", {})
            if not metadata:
                metadata = {
                    k: v for k, v in item.items()
                    if k not in ("id", "score", "operator_id", "bug_id", "opt_id", "api_id")
                }

            # 计算综合分数
            composite = self.calculate_composite_score(metadata)

            scored_results.append(RankedItem(
                id=item_id,
                score=composite,
                metadata=metadata,
                original_score=item.get("score")
            ))

        # 按综合分数降序排列
        scored_results.sort(key=lambda x: x.score.total, reverse=True)

        return scored_results[:top_k]

    def explain_score(self, metadata: dict) -> dict:
        """
        解释单个条目的分数构成 (用于调试)

        Args:
            metadata: 条目元数据

        Returns:
            dict: 分数解释
        """
        composite = self.calculate_composite_score(metadata)

        return {
            "total_score": composite.total,
            "breakdown": {
                "authority": {
                    "score": composite.authority.total,
                    "source_weight": composite.authority.source_weight,
                    "contributor_weight": composite.authority.contributor_weight,
                    "source_type": composite.authority.source_type.value,
                    "contributor_level": composite.authority.contributor_level.value,
                },
                "recency": {
                    "score": composite.recency.total,
                    "days_since_update": composite.recency.days_since_update,
                    "lambda": composite.recency.lambda_value,
                },
                "accuracy": {
                    "score": composite.accuracy.total,
                    "correction_count": composite.accuracy.correction_count,
                    "citation_count": composite.accuracy.citation_count,
                    "error_rate": composite.accuracy.error_rate,
                }
            },
            "weights": {
                "authority": composite.weights[0],
                "recency": composite.weights[1],
                "accuracy": composite.weights[2],
            }
        }
