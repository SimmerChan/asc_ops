# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
结果排序与融合模块

实现多策略结果融合: 向量相似度 + BM25 关键词 + 置信度
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """查询类型"""
    SEMANTIC = "semantic"  # 语义查询
    EXACT = "exact"  # 精确查询
    HYBRID = "hybrid"  # 混合查询


@dataclass
class ScoredResult:
    """带分数的检索结果"""
    id: str
    score: float
    query_type: QueryType = QueryType.SEMANTIC
    vector_score: Optional[float] = None
    bm25_score: Optional[float] = None
    confidence_score: Optional[float] = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        """验证分数"""
        self.score = max(0.0, min(1.0, self.score))


@dataclass
class FusionConfig:
    """融合配置"""
    vector_weight: float = 0.6
    bm25_weight: float = 0.3
    confidence_weight: float = 0.1

    # BM25 参数
    bm25_k1: float = 1.5
    bm25_b: float = 0.75

    # 最低分数阈值
    min_score_threshold: float = 0.1

    def __post_init__(self):
        """验证权重和为1"""
        total = self.vector_weight + self.bm25_weight + self.confidence_weight
        if abs(total - 1.0) > 0.01:
            logger.warning(
                f"Fusion weights sum to {total}, normalizing to 1.0"
            )
            # 归一化
            self.vector_weight /= total
            self.bm25_weight /= total
            self.confidence_weight /= total


class ResultFusion:
    """
    结果融合器

    将向量检索、BM25、置信度三种分数按权重融合
    """

    def __init__(self, config: Optional[FusionConfig] = None):
        """
        初始化融合器

        Args:
            config: 融合配置
        """
        self.config = config or FusionConfig()
        logger.info(
            f"ResultFusion initialized: "
            f"vector={self.config.vector_weight}, "
            f"bm25={self.config.bm25_weight}, "
            f"confidence={self.config.confidence_weight}"
        )

    def fuse(
        self,
        vector_results: List[ScoredResult],
        bm25_results: List[ScoredResult],
        confidence_scores: dict = None,
    ) -> List[ScoredResult]:
        """
        融合多种检索结果

        Args:
            vector_results: 向量检索结果
            bm25_results: BM25 检索结果
            confidence_scores: 置信度分数字典 {id: confidence_score}

        Returns:
            List[ScoredResult]: 融合后的排序结果
        """
        confidence_scores = confidence_scores or {}

        # 构建所有结果的评分映射
        all_results: dict[str, ScoredResult] = {}

        # 添加向量结果
        for result in vector_results:
            result.vector_score = result.score
            all_results[result.id] = result

        # 添加/融合 BM25 结果
        for result in bm25_results:
            if result.id in all_results:
                # 融合已有的结果
                existing = all_results[result.id]
                existing.bm25_score = result.score
                # 更新总分为两种分数的加权平均
                existing.score = (
                    existing.vector_score * 0.5 +
                    result.score * 0.5
                ) if existing.vector_score else result.score
            else:
                result.bm25_score = result.score
                all_results[result.id] = result

        # 应用置信度分数
        for result_id, result in all_results.items():
            if result_id in confidence_scores:
                result.confidence_score = confidence_scores[result_id]

        # 计算最终融合分数
        fused_results = []
        for result in all_results.values():
            final_score = self._calculate_fused_score(result)
            result.score = final_score

            if final_score >= self.config.min_score_threshold:
                fused_results.append(result)

        # 按分数排序
        fused_results.sort(key=lambda x: x.score, reverse=True)

        logger.debug(
            f"Fused {len(vector_results)} vector + {len(bm25_results)} bm25 "
            f"-> {len(fused_results)} results"
        )

        return fused_results

    def _calculate_fused_score(self, result: ScoredResult) -> float:
        """计算融合分数"""
        vector_s = result.vector_score or 0.0
        bm25_s = result.bm25_score or 0.0
        conf_s = result.confidence_score or 0.5  # 默认 0.5

        fused = (
            vector_s * self.config.vector_weight +
            bm25_s * self.config.bm25_weight +
            conf_s * self.config.confidence_weight
        )

        return fused

    def rerank(
        self,
        results: List[ScoredResult],
        top_k: int = 10,
    ) -> List[ScoredResult]:
        """
        重排序结果

        Args:
            results: 初始结果列表
            top_k: 返回前 k 个结果

        Returns:
            List[ScoredResult]: 重排序后的结果
        """
        # 重新计算所有结果的融合分数
        for result in results:
            result.score = self._calculate_fused_score(result)

        # 排序
        results.sort(key=lambda x: x.score, reverse=True)

        return results[:top_k]


class IntentRouter:
    """
    意图路由

    根据查询内容判断查询类型并路由到合适的检索策略
    """

    # 精确查询关键词
    EXACT_KEYWORDS = [
        "api", "function", "method", "class",
        "exact", "specific", "precise",
    ]

    # 语义查询关键词
    SEMANTIC_KEYWORDS = [
        "how", "what", "why", "when",
        "explain", "describe", "understand",
        "similar", "related", "like",
    ]

    def classify(self, query: str) -> QueryType:
        """
        判断查询类型

        Args:
            query: 用户查询

        Returns:
            QueryType: 查询类型
        """
        # 分词
        words = set(query.lower().split())

        # 检查是否包含精确查询关键词 (整词匹配)
        for keyword in self.EXACT_KEYWORDS:
            if keyword in words:
                return QueryType.EXACT

        # 检查是否包含语义查询关键词 (整词匹配)
        for keyword in self.SEMANTIC_KEYWORDS:
            if keyword in words:
                return QueryType.SEMANTIC

        # 默认混合查询
        return QueryType.HYBRID

    def should_use_bm25(self, query: str) -> bool:
        """
        判断是否使用 BM25

        Args:
            query: 用户查询

        Returns:
            bool: 是否使用 BM25
        """
        query_type = self.classify(query)
        return query_type in (QueryType.EXACT, QueryType.HYBRID)

    def should_use_vector(self, query: str) -> bool:
        """
        判断是否使用向量检索

        Args:
            query: 用户查询

        Returns:
            bool: 是否使用向量检索
        """
        query_type = self.classify(query)
        return query_type in (QueryType.SEMANTIC, QueryType.HYBRID)


class Ranker:
    """
    排序器

    统一接口，结合意图路由和结果融合提供排序能力
    """

    def __init__(self, fusion_config: Optional[FusionConfig] = None):
        """
        初始化排序器

        Args:
            fusion_config: 融合配置
        """
        self.fusion = ResultFusion(fusion_config)
        self.intent_router = IntentRouter()

        logger.info("Ranker initialized")

    def rank_results(
        self,
        query: str,
        vector_results: List[ScoredResult],
        bm25_results: List[ScoredResult] = None,
        confidence_scores: dict = None,
        top_k: int = 10,
    ) -> List[ScoredResult]:
        """
        排序结果

        Args:
            query: 用户查询
            vector_results: 向量检索结果
            bm25_results: BM25 检索结果 (可选)
            confidence_scores: 置信度分数字典
            top_k: 返回前 k 个结果

        Returns:
            List[ScoredResult]: 排序后的结果
        """
        # 判断查询类型
        query_type = self.intent_router.classify(query)
        logger.debug(f"Query type: {query_type.value}")

        # 如果没有 BM25 结果，创建空列表
        bm25_results = bm25_results or []

        # 融合结果
        if bm25_results:
            fused = self.fusion.fuse(
                vector_results,
                bm25_results,
                confidence_scores,
            )
        else:
            # 只有向量结果，直接应用置信度
            for result in vector_results:
                if confidence_scores and result.id in confidence_scores:
                    result.confidence_score = confidence_scores[result.id]
                result.score = self.fusion._calculate_fused_score(result)

            fused = sorted(
                vector_results,
                key=lambda x: x.score,
                reverse=True,
            )

        # 返回 top_k
        return fused[:top_k]
