# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
排序和置信度模块

提供置信度计算、结果融合和排序能力
"""

from .confidence import (
    ConfidenceEngine,
    ConfidenceScore,
    APISourceType,
    BugFixConfidenceCalculator,
    OptimizationConfidenceCalculator,
    ReviewStatus,
)
from .fusion import (
    ResultFusion,
    FusionConfig,
    IntentRouter,
    QueryType,
    Ranker,
    ScoredResult,
)
from .bm25 import BM25Index, BM25Document
from .scoring import (
    RankingConfig,
    DEFAULT_RANKING_CONFIG,
    AuthorityScorer,
    AuthorityScore,
    SourceType,
    ContributorLevel,
    RecencyCalculator,
    RecencyScore,
    AccuracyCalculator,
    AccuracyScore,
)
from .integrated_ranker import (
    ConfidenceRanker,
    CompositeScore,
    RankedItem,
)

__all__ = [
    # Confidence
    "ConfidenceEngine",
    "ConfidenceScore",
    "APISourceType",
    "BugFixConfidenceCalculator",
    "OptimizationConfidenceCalculator",
    "ReviewStatus",
    # Fusion
    "ResultFusion",
    "FusionConfig",
    "IntentRouter",
    "QueryType",
    "Ranker",
    "ScoredResult",
    # BM25
    "BM25Index",
    "BM25Document",
    # Scoring
    "RankingConfig",
    "DEFAULT_RANKING_CONFIG",
    "AuthorityScorer",
    "AuthorityScore",
    "SourceType",
    "ContributorLevel",
    "RecencyCalculator",
    "RecencyScore",
    "AccuracyCalculator",
    "AccuracyScore",
    # Integrated Ranker
    "ConfidenceRanker",
    "CompositeScore",
    "RankedItem",
]
