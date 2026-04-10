# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
引用统计 API 模块

提供知识引用统计的查询接口，用于质量监控和数据分析
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any

from .citation_tracker import CitationTracker, CitationStats, EntityType
from .feedback import FeedbackAPI, CorrectionStats
from ..storage.redis_client import RedisClient

logger = logging.getLogger(__name__)


@dataclass
class QualityDashboard:
    """质量监控面板数据"""
    entity_type: str
    total_entities: int
    total_citations: int
    total_corrections: int
    avg_citations_per_entity: float
    avg_corrections_per_entity: float
    avg_accuracy: float
    top_cited: List[Dict[str, Any]]
    top_inaccurate: List[Dict[str, Any]]
    recently_corrected: List[Dict[str, Any]]
    generated_at: datetime = field(default_factory=datetime.now)


@dataclass
class EntityQualitySummary:
    """实体质量摘要"""
    entity_id: str
    entity_type: str
    citation_count: int
    correction_count: int
    accuracy: float
    quality_score: float  # 综合质量分数 [0, 1]
    needs_review: bool    # 是否需要人工审核


class CitationStatsAPI:
    """
    引用统计 API

    提供知识引用统计的查询接口

    主要功能:
    - 获取实体的引用/纠错统计
    - 获取 Top K 高引用/高错误率知识
    - 生成质量监控面板数据
    - 批量获取实体质量摘要
    """

    def __init__(
        self,
        redis_client: Optional[RedisClient] = None,
        citation_tracker: Optional[CitationTracker] = None,
        feedback_api: Optional[FeedbackAPI] = None
    ):
        """
        初始化引用统计 API

        Args:
            redis_client: Redis 客户端
            citation_tracker: 引用追踪器
            feedback_api: 反馈接口
        """
        self.redis = redis_client or RedisClient(mock=True)
        self.citation_tracker = citation_tracker or CitationTracker(self.redis)
        self.feedback_api = feedback_api or FeedbackAPI(self.redis, self.citation_tracker)
        logger.info("CitationStatsAPI initialized")

    def get_stats(self, entity_id: str, entity_type: str) -> Dict[str, Any]:
        """
        获取实体的完整统计信息

        Args:
            entity_id: 实体 ID
            entity_type: 实体类型

        Returns:
            Dict containing citation stats and correction stats
        """
        # 获取引用统计
        citation_stats = self.citation_tracker.get_stats(entity_id, entity_type)

        # 获取纠错统计
        correction_stats = self.feedback_api.get_correction_stats(entity_id, entity_type)

        return {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "citations": citation_stats.to_dict(),
            "corrections": {
                "total": correction_stats.total_corrections,
                "by_type": correction_stats.by_type,
                "last_reported_at": (
                    correction_stats.last_reported_at.isoformat()
                    if correction_stats.last_reported_at else None
                ),
            },
            "quality": {
                "accuracy": citation_stats.accuracy,
                "error_rate": citation_stats.error_rate,
                "needs_review": correction_stats.total_corrections >= 3,
            }
        }

    def get_quality_summary(self, entity_id: str, entity_type: str) -> EntityQualitySummary:
        """
        获取实体的质量摘要

        Args:
            entity_id: 实体 ID
            entity_type: 实体类型

        Returns:
            EntityQualitySummary
        """
        citation_stats = self.citation_tracker.get_stats(entity_id, entity_type)
        correction_stats = self.feedback_api.get_correction_stats(entity_id, entity_type)

        # 计算综合质量分数
        # 公式: accuracy * recency_boost - review_penalty
        # recency_boost: 如果最近有引用，增加分数
        # review_penalty: 如果有纠错，降低分数
        base_quality = citation_stats.accuracy

        # 时效性提升 (最多 +0.1)
        recency_boost = 0.0
        if citation_stats.last_cited_at:
            days_since_cited = (datetime.now() - citation_stats.last_cited_at).days
            if days_since_cited <= 7:
                recency_boost = 0.1
            elif days_since_cited <= 30:
                recency_boost = 0.05

        # 纠错惩罚 (根据纠错次数)
        review_penalty = 0.0
        if correction_stats.total_corrections >= 10:
            review_penalty = 0.5
        elif correction_stats.total_corrections >= 5:
            review_penalty = 0.3
        elif correction_stats.total_corrections >= 1:
            review_penalty = 0.1

        quality_score = max(0, min(1, base_quality + recency_boost - review_penalty))

        return EntityQualitySummary(
            entity_id=entity_id,
            entity_type=entity_type,
            citation_count=citation_stats.citation_count,
            correction_count=correction_stats.total_corrections,
            accuracy=citation_stats.accuracy,
            quality_score=quality_score,
            needs_review=correction_stats.total_corrections >= 3 or quality_score < 0.5
        )

    def get_top_cited(
        self,
        entity_type: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        获取引用最多的知识条目

        Args:
            entity_type: 实体类型
            limit: 返回数量

        Returns:
            List of {entity_id, citation_count, quality_summary}
        """
        top_items = self.citation_tracker.get_top_cited(entity_type, limit)

        result = []
        for item in top_items:
            entity_id = item["entity_id"]
            quality = self.get_quality_summary(entity_id, entity_type)
            result.append({
                "entity_id": entity_id,
                "citation_count": item["citation_count"],
                "quality_score": round(quality.quality_score, 4),
                "accuracy": round(quality.accuracy, 4),
                "needs_review": quality.needs_review,
            })

        return result

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
            min_citations: 最小引用数
            limit: 返回数量

        Returns:
            List of {entity_id, error_rate, citation_count, correction_count}
        """
        return self.citation_tracker.get_top_inaccurate(entity_type, min_citations, limit)

    def get_dashboard(self, entity_type: str) -> QualityDashboard:
        """
        生成质量监控面板数据

        Args:
            entity_type: 实体类型

        Returns:
            QualityDashboard
        """
        # 获取 Top cited
        top_cited_raw = self.citation_tracker.get_top_cited(entity_type, limit=10)
        top_cited = []
        total_citations = 0
        for item in top_cited_raw:
            total_citations += item["citation_count"]
            top_cited.append({
                "entity_id": item["entity_id"],
                "citation_count": item["citation_count"],
            })

        # 获取 Top inaccurate
        top_inaccurate = self.get_top_inaccurate(entity_type, min_citations=3, limit=10)

        # 获取总实体数和总引用数
        entity_count = self.citation_tracker._zcard(
            self.citation_tracker._get_citation_key(entity_type)
        )

        # 获取最近被纠错的实体
        recently_corrected = self._get_recently_corrected(entity_type, limit=10)

        # 计算平均值
        avg_citations = total_citations / entity_count if entity_count > 0 else 0

        # 计算平均准确性 (从 top_cited 计算)
        avg_accuracy = 0.0
        if top_cited:
            total_accuracy = sum(
                self.citation_tracker.get_stats(item["entity_id"], entity_type).accuracy
                for item in top_cited
            )
            avg_accuracy = total_accuracy / len(top_cited)

        return QualityDashboard(
            entity_type=entity_type,
            total_entities=entity_count,
            total_citations=total_citations,
            total_corrections=sum(item["correction_count"] for item in top_inaccurate),
            avg_citations_per_entity=round(avg_citations, 2),
            avg_corrections_per_entity=0,  # 需要单独计算
            avg_accuracy=round(avg_accuracy, 4),
            top_cited=top_cited,
            top_inaccurate=top_inaccurate,
            recently_corrected=recently_corrected,
        )

    def get_bulk_quality(
        self,
        entity_ids: List[str],
        entity_type: str
    ) -> List[EntityQualitySummary]:
        """
        批量获取多个实体的质量摘要

        Args:
            entity_ids: 实体 ID 列表
            entity_type: 实体类型

        Returns:
            List of EntityQualitySummary
        """
        return [
            self.get_quality_summary(eid, entity_type)
            for eid in entity_ids
        ]

    def _get_recently_corrected(
        self,
        entity_type: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取最近被纠错的实体"""
        # 获取所有有纠错的实体
        correction_key = self.citation_tracker._get_correction_key(entity_type)
        entities_with_corrections = self.citation_tracker._zrange(
            correction_key, 0, -1, withscores=True
        )

        results = []
        for entity_id, score in entities_with_corrections[:limit * 2]:  # 多取一些
            if len(results) >= limit:
                break

            citation_stats = self.citation_tracker.get_stats(entity_id, entity_type)
            if citation_stats.last_corrected_at:
                results.append({
                    "entity_id": entity_id,
                    "correction_count": citation_stats.correction_count,
                    "last_corrected_at": citation_stats.last_corrected_at.isoformat(),
                    "accuracy": round(citation_stats.accuracy, 4),
                })

        # 按最后纠错时间排序
        results.sort(
            key=lambda x: x.get("last_corrected_at", ""),
            reverse=True
        )

        return results[:limit]

    def export_stats_csv(self, entity_type: str) -> str:
        """
        导出统计为 CSV 格式

        Args:
            entity_type: 实体类型

        Returns:
            CSV 格式字符串
        """
        import csv
        import io

        top_cited = self.get_top_cited(entity_type, limit=100)
        top_inaccurate = self.get_top_inaccurate(entity_type, min_citations=1, limit=100)

        output = io.StringIO()
        writer = csv.writer(output)

        # 写入表头
        writer.writerow([
            "entity_id", "citation_count", "correction_count",
            "accuracy", "quality_score", "needs_review", "inaccuracy_rank"
        ])

        # 合并数据
        all_entity_ids = set()
        for item in top_cited:
            all_entity_ids.add(item["entity_id"])
        for item in top_inaccurate:
            all_entity_ids.add(item["entity_id"])

        inaccuracy_rank_map = {
            item["entity_id"]: i + 1
            for i, item in enumerate(top_inaccurate)
        }

        for entity_id in all_entity_ids:
            citation_count = 0
            accuracy = 0
            quality_score = 0
            needs_review = False
            inaccuracy_rank = inaccuracy_rank_map.get(entity_id, "")

            for item in top_cited:
                if item["entity_id"] == entity_id:
                    citation_count = item["citation_count"]
                    accuracy = item["accuracy"]
                    quality_score = item["quality_score"]
                    needs_review = item["needs_review"]
                    break

            for item in top_inaccurate:
                if item["entity_id"] == entity_id:
                    correction_count = item.get("correction_count", 0)
                    break
            else:
                correction_count = 0

            writer.writerow([
                entity_id,
                citation_count,
                correction_count,
                round(accuracy, 4),
                round(quality_score, 4),
                "Yes" if needs_review else "No",
                inaccuracy_rank
            ])

        return output.getvalue()
