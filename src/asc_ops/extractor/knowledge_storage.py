# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
知识存储模块

将抽取的 Bug/优化知识存入 ChromaDB + Redis
"""

import logging
from typing import List, Optional

from .bug_extractor import BugExtractionResult
from .opt_extractor import OptimizationExtractionResult

logger = logging.getLogger(__name__)


class KnowledgeStorage:
    """
    知识存储管理器

    负责将 Bug 修复知识和优化知识存储到 ChromaDB + Redis
    """

    def __init__(
        self,
        chroma_client=None,
        redis_client=None,
    ):
        """
        初始化知识存储

        Args:
            chroma_client: ChromaDB 客户端
            redis_client: Redis 客户端
        """
        self._chroma = chroma_client
        self._redis = redis_client

        logger.info("KnowledgeStorage initialized")

    def store_bugfix(
        self,
        result: BugExtractionResult,
        collection_name: str = "bug_fixes",
    ) -> bool:
        """
        存储 Bug 修复知识

        Args:
            result: Bug 抽取结果
            collection_name: ChromaDB collection 名称

        Returns:
            bool: 是否存储成功
        """
        if not result.extraction_success:
            logger.warning(f"BugFix {result.bug_id} extraction failed, skipping storage")
            return False

        try:
            # 生成向量描述文本
            text_content = self._generate_bugfix_text(result)

            # 存储到 ChromaDB (向量)
            if self._chroma:
                self._chroma.add(
                    collection=collection_name,
                    documents=[text_content],
                    metadatas=[self._bugfix_to_metadata(result)],
                    ids=[result.bug_id],
                )

            # 存储到 Redis (结构化数据)
            if self._redis:
                self._store_bugfix_redis(result)

            logger.info(f"BugFix {result.bug_id} stored successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to store BugFix {result.bug_id}: {e}")
            return False

    def store_optimization(
        self,
        result: OptimizationExtractionResult,
        collection_name: str = "optimizations",
    ) -> bool:
        """
        存储优化知识

        Args:
            result: 优化抽取结果
            collection_name: ChromaDB collection 名称

        Returns:
            bool: 是否存储成功
        """
        if not result.extraction_success:
            logger.warning(f"Optimization {result.opt_id} extraction failed, skipping storage")
            return False

        try:
            # 生成向量描述文本
            text_content = self._generate_optimization_text(result)

            # 存储到 ChromaDB (向量)
            if self._chroma:
                self._chroma.add(
                    collection=collection_name,
                    documents=[text_content],
                    metadatas=[self._optimization_to_metadata(result)],
                    ids=[result.opt_id],
                )

            # 存储到 Redis (结构化数据)
            if self._redis:
                self._store_optimization_redis(result)

            logger.info(f"Optimization {result.opt_id} stored successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to store Optimization {result.opt_id}: {e}")
            return False

    def _generate_bugfix_text(self, result: BugExtractionResult) -> str:
        """生成 BugFix 向量化文本"""
        parts = [
            result.bug_title,
        ]

        if result.root_cause:
            parts.append(f"Root cause: {result.root_cause}")

        if result.fix_pattern:
            parts.append(f"Fix: {result.fix_pattern}")

        if result.trigger_conditions:
            parts.append(f"Trigger conditions: {', '.join(result.trigger_conditions)}")

        if result.related_apis:
            parts.append(f"Related APIs: {', '.join(result.related_apis)}")

        return " | ".join(parts)

    def _generate_optimization_text(self, result: OptimizationExtractionResult) -> str:
        """生成 Optimization 向量化文本"""
        parts = [
            result.opt_title,
        ]

        if result.optimization_type:
            parts.append(f"Optimization type: {', '.join(result.optimization_type)}")

        if result.optimization_description:
            parts.append(f"Description: {result.optimization_description}")

        if result.improvement_ratio:
            parts.append(f"Improvement: {result.improvement_ratio * 100:.1f}%")

        if result.related_apis:
            parts.append(f"Related APIs: {', '.join(result.related_apis)}")

        return " | ".join(parts)

    def _bugfix_to_metadata(self, result: BugExtractionResult) -> dict:
        """BugFix 转换为 metadata"""
        return {
            "type": "bugfix",
            "operator_id": result.operator_id,
            "source_repo": result.source_repo,
            "source_pr": result.source_pr,
            "bug_title": result.bug_title,
            "has_root_cause": result.root_cause is not None,
            "has_fix_pattern": result.fix_pattern is not None,
            "related_apis": ",".join(result.related_apis) if result.related_apis else "",
            "trigger_count": len(result.trigger_conditions),
            "workaround_count": len(result.workarounds),
        }

    def _optimization_to_metadata(self, result: OptimizationExtractionResult) -> dict:
        """Optimization 转换为 metadata"""
        return {
            "type": "optimization",
            "operator_id": result.operator_id,
            "source_repo": result.source_repo,
            "source_pr": result.source_pr,
            "opt_title": result.opt_title,
            "optimization_types": ",".join(result.optimization_type) if result.optimization_type else "",
            "has_improvement_ratio": result.improvement_ratio is not None,
            "improvement_ratio": str(result.improvement_ratio) if result.improvement_ratio else "",
            "has_metrics": result.before_metrics is not None or result.after_metrics is not None,
            "related_apis": ",".join(result.related_apis) if result.related_apis else "",
        }

    def _store_bugfix_redis(self, result: BugExtractionResult) -> None:
        """存储 BugFix 到 Redis"""
        key = f"bugfix:{result.bug_id}"

        self._redis.hset(key, mapping={
            "bug_id": result.bug_id,
            "operator_id": result.operator_id,
            "source_repo": result.source_repo,
            "source_pr": result.source_pr,
            "bug_title": result.bug_title,
            "root_cause": result.root_cause or "",
            "fix_pattern": result.fix_pattern or "",
            "trigger_conditions": "|".join(result.trigger_conditions),
            "workarounds": "|".join(result.workarounds),
            "related_apis": "|".join(result.related_apis),
        })

        # 添加到算子索引
        self._redis.sadd(f"operator:{result.operator_id}:bugs", result.bug_id)

    def _store_optimization_redis(self, result: OptimizationExtractionResult) -> None:
        """存储 Optimization 到 Redis"""
        key = f"optimization:{result.opt_id}"

        self._redis.hset(key, mapping={
            "opt_id": result.opt_id,
            "operator_id": result.operator_id,
            "source_repo": result.source_repo,
            "source_pr": result.source_pr,
            "opt_title": result.opt_title,
            "optimization_type": "|".join(result.optimization_type),
            "optimization_description": result.optimization_description or "",
            "improvement_ratio": str(result.improvement_ratio) if result.improvement_ratio else "",
            "related_apis": "|".join(result.related_apis),
        })

        # 添加到算子索引
        for opt_type in result.optimization_type:
            self._redis.sadd(f"operator:{result.operator_id}:opts:{opt_type}", result.opt_id)

    def is_duplicate(self, source_repo: str, source_pr: str) -> bool:
        """
        检查是否重复抽取

        Args:
            source_repo: 来源仓库
            source_pr: PR 编号

        Returns:
            bool: 是否重复
        """
        if not self._redis:
            return False

        # 检查 bugfix
        bug_key = f"bugfix:lookup:{source_repo}:{source_pr}"
        if self._redis.exists(bug_key):
            return True

        # 检查 optimization
        opt_key = f"optimization:lookup:{source_repo}:{source_pr}"
        if self._redis.exists(opt_key):
            return True

        return False

    def mark_processed(self, source_repo: str, source_pr: str, knowledge_type: str) -> None:
        """
        标记为已处理

        Args:
            source_repo: 来源仓库
            source_pr: PR 编号
            knowledge_type: "bugfix" | "optimization"
        """
        if not self._redis:
            return

        key = f"{knowledge_type}:lookup:{source_repo}:{source_pr}"
        self._redis.set(key, "1")

    def get_bugfix_count(self, operator_id: str = None) -> int:
        """
        获取 BugFix 数量

        Args:
            operator_id: 算子 ID (可选)

        Returns:
            int: BugFix 数量
        """
        if not self._redis:
            return 0

        if operator_id:
            return self._redis.scard(f"operator:{operator_id}:bugs")
        else:
            # 统计所有 bugfix key
            count = 0
            for key in self._redis.scan_iter("bugfix:*"):
                if ":lookup:" not in key:
                    count += 1
            return count

    def get_optimization_count(self, operator_id: str = None, opt_type: str = None) -> int:
        """
        获取 Optimization 数量

        Args:
            operator_id: 算子 ID (可选)
            opt_type: 优化类型 (可选)

        Returns:
            int: Optimization 数量
        """
        if not self._redis:
            return 0

        if operator_id and opt_type:
            return self._redis.scard(f"operator:{operator_id}:opts:{opt_type}")
        elif operator_id:
            # 统计该算子所有类型的优化
            count = 0
            for key in self._redis.scan_iter(f"operator:{operator_id}:opts:*"):
                count += self._redis.scard(key)
            return count
        else:
            # 统计所有 optimization key
            count = 0
            for key in self._redis.scan_iter("optimization:*"):
                if ":lookup:" not in key:
                    count += 1
            return count
