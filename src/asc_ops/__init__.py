# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
AscendC Operator Knowledge Base

为Coding Agent提供昇腾AscendC算子知识检索支持
"""

__version__ = "0.1.0"
__author__ = "SimmerChan"
__license__ = "Apache 2.0"

from .knowledge_query import KnowledgeQueryService
from .models import (
    BugFixKnowledge,
    OptimizationKnowledge,
    AscendCAPIDefinition,
    KnowledgeStats,
)

__all__ = [
    "KnowledgeQueryService",
    "BugFixKnowledge",
    "OptimizationKnowledge",
    "AscendCAPIDefinition",
    "KnowledgeStats",
]
