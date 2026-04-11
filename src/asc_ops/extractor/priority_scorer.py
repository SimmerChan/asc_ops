# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
优先级评分引擎

对bug记录按优先级排序，优先抽取高价值知识
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Set

from ..storage.chroma_client import ChromaDBClient
from ..storage.redis_client import RedisClient
from ..quality.citation_tracker import CitationTracker

logger = logging.getLogger(__name__)

# 核心算子列表（OperatorScore = 1.0）
CORE_OPERATORS: Set[str] = {
    "Matmul", "MatMul",
    "Add", "VecAdd",
    "Conv2d", "Conv",
    "Reduce", "VecReduce",
    "Transpose", "TransposeBatchMatmul",
    "BatchMatmul", "BMM",
    "Gemm", "GEMM",
    "Softmax", "LayerNorm",
    "Resize", "ResizeBilinear",
    "Pooling", "MaxPool", "AvgPool",
}

# 算子名称变体映射
OPERATOR_ALIASES: dict = {
    "matmul": "Matmul",
    "bmm": "BatchMatmul",
    "conv2d": "Conv2d",
    "vecadd": "VecAdd",
    "vecreduce": "VecReduce",
    "transpose": "Transpose",
    "tbmm": "TransposeBatchMatmul",
    "tbm": "TransposeBatchMatmul",
    "softmax": "Softmax",
    "layernorm": "LayerNorm",
    "resize": "Resize",
    "pooling": "Pooling",
}


@dataclass
class BugPriorityItem:
    """Bug优先级条目"""
    bug_id: str
    operator_id: str
    source_repo: str
    source_pr: str
    bug_title: str
    has_root_cause: bool
    has_fix_pattern: bool
    citation_count: int = 0
    priority_score: float = 0.0
    priority_rank: int = 0

    def __lt__(self, other: "BugPriorityItem") -> bool:
        return self.priority_score > other.priority_score


class PriorityScorer:
    """
    优先级评分器

    按三个维度计算优先级分数:
    - CitationScore: 引用频率 (权重 0.4)
    - OperatorScore: 算子重要性 (权重 0.3)
    - MissingFieldScore: 字段缺失程度 (权重 0.3)
    """

    CITATION_WEIGHT = 0.4
    OPERATOR_WEIGHT = 0.3
    MISSING_FIELD_WEIGHT = 0.3

    def __init__(
        self,
        chroma_client: Optional[ChromaDBClient] = None,
        redis_client: Optional[RedisClient] = None,
        citation_tracker: Optional[CitationTracker] = None,
    ):
        """
        初始化优先级评分器

        Args:
            chroma_client: ChromaDB 客户端
            redis_client: Redis 客户端
            citation_tracker: 引用追踪器
        """
        self._chroma = chroma_client
        self._redis = redis_client
        self._citation_tracker = citation_tracker or CitationTracker(redis_client)

    def calculate_priority_queue(
        self,
        limit: Optional[int] = None,
        collection_name: str = "bug_fixes",
    ) -> List[BugPriorityItem]:
        """
        计算优先级队列

        Args:
            limit: 返回数量限制
            collection_name: ChromaDB collection 名称

        Returns:
            按优先级排序的 Bug 列表
        """
        # 1. 获取所有 bug 记录
        bugs = self._get_all_bugs(collection_name)

        if not bugs:
            logger.warning("No bugs found in collection")
            return []

        # 2. 获取最大引用次数（用于归一化）
        max_citations = max(b.citation_count for b in bugs) if bugs else 1
        if max_citations == 0:
            max_citations = 1

        # 3. 计算优先级分数
        for bug in bugs:
            # CitationScore: 归一化引用次数
            citation_score = bug.citation_count / max_citations if max_citations > 0 else 0

            # OperatorScore: 核心算子得1.0，其他得0.5
            operator_score = self._calculate_operator_score(bug.operator_id)

            # MissingFieldScore: 两者都空得1.0，部分空得0.5，无缺失得0
            missing_score = self._calculate_missing_field_score(bug.has_root_cause, bug.has_fix_pattern)

            # 综合分数
            bug.priority_score = (
                self.CITATION_WEIGHT * citation_score +
                self.OPERATOR_WEIGHT * operator_score +
                self.MISSING_FIELD_WEIGHT * missing_score
            )

        # 4. 按分数降序排列
        sorted_bugs = sorted(bugs)

        # 5. 设置排名
        for i, bug in enumerate(sorted_bugs):
            bug.priority_rank = i + 1

        # 6. 截取 limit
        if limit:
            sorted_bugs = sorted_bugs[:limit]

        logger.info(f"Priority queue calculated: {len(sorted_bugs)} bugs")
        return sorted_bugs

    def _get_all_bugs(self, collection_name: str) -> List[BugPriorityItem]:
        """获取所有 bug 记录"""
        bugs = []

        if not self._chroma:
            logger.warning("No ChromaDB client, cannot get bugs")
            return bugs

        try:
            collection = self._chroma.get_collection(collection_name)

            # 获取所有 bug 数据
            # ChromaDB 的 get() 需要 id 列表，先用 where={} 查询全部
            results = collection.get(limit=10000)

            if not results or not results.get("ids"):
                logger.warning(f"No bugs found in collection {collection_name}")
                return bugs

            ids = results["ids"]
            documents = results.get("documents", [])
            metadatas = results.get("metadatas", [])

            for i, bug_id in enumerate(ids):
                metadata = metadatas[i] if i < len(metadatas) else {}

                # 获取引用次数
                citation_count = 0
                try:
                    stats = self._citation_tracker.get_stats(bug_id, "bug")
                    citation_count = stats.citation_count
                except Exception:
                    pass

                bug = BugPriorityItem(
                    bug_id=bug_id,
                    operator_id=metadata.get("operator_id", "unknown"),
                    source_repo=metadata.get("source_repo", ""),
                    source_pr=metadata.get("source_pr", ""),
                    bug_title=metadata.get("bug_title", ""),
                    has_root_cause=metadata.get("has_root_cause", False),
                    has_fix_pattern=metadata.get("has_fix_pattern", False),
                    citation_count=citation_count,
                )
                bugs.append(bug)

            logger.info(f"Retrieved {len(bugs)} bugs from ChromaDB")

        except Exception as e:
            logger.error(f"Error getting bugs from ChromaDB: {e}")

        return bugs

    def _calculate_operator_score(self, operator_id: str) -> float:
        """
        计算算子重要性分数

        Args:
            operator_id: 算子 ID

        Returns:
            1.0 如果是核心算子，0.5 否则
        """
        if not operator_id:
            return 0.5

        op_upper = operator_id.strip().title()

        # 检查是否是核心算子
        if op_upper in CORE_OPERATORS:
            return 1.0

        # 检查别名
        op_lower = operator_id.lower()
        if op_lower in OPERATOR_ALIASES:
            canonical = OPERATOR_ALIASES[op_lower]
            if canonical in CORE_OPERATORS:
                return 1.0

        return 0.5

    def _calculate_missing_field_score(
        self,
        has_root_cause: bool,
        has_fix_pattern: bool
    ) -> float:
        """
        计算字段缺失程度分数

        Args:
            has_root_cause: 是否有 root_cause
            has_fix_pattern: 是否有 fix_pattern

        Returns:
            1.0 两者都空，0.5 部分空，0 无缺失
        """
        if not has_root_cause and not has_fix_pattern:
            return 1.0
        elif has_root_cause != has_fix_pattern:
            return 0.5
        else:
            return 0.0

    def get_top_bugs_by_citations(
        self,
        limit: int = 10,
        collection_name: str = "bug_fixes"
    ) -> List[BugPriorityItem]:
        """获取引用次数最多的 bug"""
        queue = self.calculate_priority_queue(limit=None, collection_name=collection_name)
        # 按引用次数排序
        queue.sort(key=lambda x: x.citation_count, reverse=True)
        return queue[:limit]

    def get_most_incomplete_bugs(
        self,
        limit: int = 10,
        collection_name: str = "bug_fixes"
    ) -> List[BugPriorityItem]:
        """获取缺失字段最多的 bug"""
        queue = self.calculate_priority_queue(limit=None, collection_name=collection_name)
        # 按缺失分数排序
        queue.sort(key=lambda x: (
            not x.has_root_cause,
            not x.has_fix_pattern,
            x.citation_count
        ), reverse=True)
        return queue[:limit]
