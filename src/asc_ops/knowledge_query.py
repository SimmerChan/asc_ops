# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
知识查询服务
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from .models import (
    BugFixKnowledge,
    OptimizationKnowledge,
    AscendCAPIDefinition,
    KnowledgeStats,
)
from .storage import ChromaDBClient, RedisClient
from .storage.collections import CollectionType
from .ranker import Ranker, FusionConfig, ScoredResult, QueryType, ConfidenceRanker, RankingConfig
from .extractor.knowledge_storage import KnowledgeStorage
from .quality import CitationTracker, FeedbackAPI
from .collector.embedder import QwenEmbedder
from .config import get_config

logger = logging.getLogger(__name__)


class KnowledgeQueryService:
    """知识查询服务"""

    def __init__(
        self,
        chroma_client: Optional[ChromaDBClient] = None,
        redis_client: Optional[RedisClient] = None,
        chroma_db_path: Optional[str] = None,
        base_url: str = "http://localhost:8000",
    ):
        """
        初始化知识查询服务

        Args:
            chroma_client: ChromaDB 客户端 (优先级最高)
            redis_client: Redis 客户端
            chroma_db_path: ChromaDB 持久化目录 (用于创建持久化客户端)
            base_url: API 基础 URL (用于 API 详情获取)
        """
        if chroma_client is not None:
            self._chroma = chroma_client
        else:
            # 优先使用传入的路径，否则从配置读取
            from .config import get_config
            db_path = chroma_db_path or get_config().chroma.db_path
            self._chroma = ChromaDBClient(persist_directory=db_path)
        self._redis = redis_client or RedisClient(mock=True)
        self._storage = KnowledgeStorage(
            chroma_client=self._chroma,
            redis_client=self._redis,
        )
        self._ranker = Ranker(FusionConfig())
        self._confidence_ranker = ConfidenceRanker(
            config=RankingConfig(),
            redis_client=self._redis
        )
        # 初始化 QwenEmbedder 用于 API 语义查询
        embedder_config = get_config().embedding
        self._embedder = QwenEmbedder(
            model_name=embedder_config.model_name,
            model_path=embedder_config.model_path,
            embedding_dim=embedder_config.embedding_dim or 1024,
            batch_size=embedder_config.batch_size or 8,
            device=embedder_config.device or "mps",
        )
        self._citation_tracker = CitationTracker(self._redis)
        self._feedback_api = FeedbackAPI(self._redis, self._citation_tracker)
        self.base_url = base_url

        logger.info("KnowledgeQueryService initialized")

    async def query_for_development(
        self,
        operator_name: str,
        query_type: str = "all",
        api_filter: Optional[List[str]] = None,
        min_confidence: float = 0.5,
        limit: int = 10,
        use_confidence_ranking: bool = True,
    ) -> "DevelopmentQueryResult":
        """
        主动开发查询

        Args:
            operator_name: 算子名称
            query_type: "bug" | "optimization" | "all"
            api_filter: API过滤列表
            min_confidence: 最低置信度
            limit: 返回数量
            use_confidence_ranking: 是否使用置信度感知排序

        Returns:
            DevelopmentQueryResult
        """
        bug_fixes = []
        optimizations = []

        # 查询 Bug 修复知识
        if query_type in ("bug", "all"):
            bug_fixes = await self._query_bugs_by_operator(
                operator_name,
                min_confidence=min_confidence,
                limit=limit if query_type == "bug" else limit // 2,
            )

        # 查询优化知识
        if query_type in ("optimization", "all"):
            optimizations = await self._query_optimizations_by_operator(
                operator_name,
                min_confidence=min_confidence,
                limit=limit if query_type == "optimization" else limit // 2,
            )

        # 应用置信度排序
        if use_confidence_ranking:
            bug_fixes = await self._apply_confidence_ranking(bug_fixes, "bug")
            optimizations = await self._apply_confidence_ranking(optimizations, "optimization")

        # 记录引用 (追踪知识被查询的次数)
        self._record_citations_for_results(bug_fixes, "bug")
        self._record_citations_for_results(optimizations, "optimization")

        return DevelopmentQueryResult(
            operator_name=operator_name,
            query_type=query_type,
            total_count=len(bug_fixes) + len(optimizations),
            bug_fixes=bug_fixes,
            optimizations=optimizations,
        )

    async def query_for_troubleshooting(
        self,
        symptom: str,
        operator_name: Optional[str] = None,
        error_message: Optional[str] = None,
        used_apis: Optional[List[str]] = None,
        include_related: bool = False,
        include_api_details: bool = False,
        use_confidence_ranking: bool = True,
        limit: int = 5,
    ) -> "TroubleshootingResult":
        """
        被动问题排查查询

        Args:
            symptom: 问题症状描述
            operator_name: 算子名称
            error_message: 错误信息
            used_apis: 使用的API列表
            include_related: 是否包含关联知识
            include_api_details: 是否包含API详情
            use_confidence_ranking: 是否使用置信度感知排序 (默认True)
            limit: 返回数量

        Returns:
            TroubleshootingResult
        """
        # 构建综合查询文本
        query_parts = [symptom]
        if operator_name:
            query_parts.append(operator_name)
        if error_message:
            query_parts.append(error_message)
        if used_apis:
            query_parts.extend(used_apis)

        combined_query = " ".join(query_parts)

        # 查询相关的 Bug 知识
        bug_fixes = await self._query_bugs_semantic(
            combined_query,
            operator_name=operator_name,
            limit=limit,
        )

        # 应用置信度感知排序
        if use_confidence_ranking and bug_fixes:
            bug_fixes = await self._apply_confidence_ranking(bug_fixes, "bug")

        # 转换为 PossibleCause
        possible_causes = []
        for bug in bug_fixes:
            possible_causes.append(PossibleCause(
                bug_id=bug.bug_id,
                description=bug.bug_title,
                confidence=bug.confidence,
                root_cause=bug.root_cause or "Unknown",
                trigger_conditions=bug.trigger_conditions,
                suggested_fix=bug.fix_pattern,
                suggested_checks=self._generate_checks(bug),
            ))

        # 记录引用 (追踪知识被查询的次数)
        self._record_citations_for_results(bug_fixes, "bug")

        # 查询关联 API
        related_apis = []
        if include_api_details and used_apis:
            for api_name in used_apis[:3]:
                api_defs = await self.query_api(api_name=api_name, limit=1)
                related_apis.extend(api_defs)

        return TroubleshootingResult(
            symptom=symptom,
            possible_causes=possible_causes,
            related_apis=related_apis if include_api_details else [],
        )

    async def query_api(
        self,
        api_name: Optional[str] = None,
        semantic_query: Optional[str] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        include_examples: bool = False,
        limit: int = 10,
    ) -> List[AscendCAPIDefinition]:
        """
        API查询

        Args:
            api_name: API名称（精确匹配）
            semantic_query: 语义搜索查询
            category: API类别
            subcategory: API子类别
            include_examples: 是否包含使用示例
            limit: 返回数量

        Returns:
            API定义列表
        """
        results = []

        # 优先精确查询
        if api_name:
            results = await self._query_api_exact(api_name)
            if results:
                # 过滤类别和子类别
                if category:
                    results = [r for r in results if r.category == category]
                if subcategory:
                    results = [r for r in results if r.subcategory == subcategory]
                return results[:limit]

        # 语义搜索
        if semantic_query:
            results = await self._query_api_semantic(
                semantic_query,
                category=category,
                subcategory=subcategory,
                limit=limit,
            )
        elif not api_name:
            # 如果都没有指定，返回空
            return []

        # 过滤示例
        if not include_examples:
            for api in results:
                api.usage_examples = []

        return results[:limit]

    async def _query_bugs_by_operator(
        self,
        operator_name: str,
        min_confidence: float = 0.5,
        limit: int = 10,
    ) -> List[BugFixKnowledge]:
        """根据算子名称查询 Bug 修复知识"""
        try:
            # 从 Redis 获取该算子的所有 bug IDs
            bug_ids_key = f"operator:{operator_name}:bugs"
            bug_ids = self._redis.smembers(bug_ids_key)

            if not bug_ids:
                # 尝试模糊匹配
                bug_ids = self._redis.smembers(f"operator:{operator_name.lower()}:bugs")

            if not bug_ids:
                return []

            # 从 Redis 获取详细信息
            bugs = []
            for bug_id in list(bug_ids)[:limit]:
                bug_key = f"bugfix:{bug_id}"
                bug_data = self._redis.hgetall(bug_key)
                if bug_data:
                    bug = self._bug_from_redis(bug_data)
                    if bug and bug.confidence >= min_confidence:
                        bugs.append(bug)

            return bugs

        except Exception as e:
            logger.error(f"Failed to query bugs for operator {operator_name}: {e}")
            return []

    async def _query_optimizations_by_operator(
        self,
        operator_name: str,
        min_confidence: float = 0.5,
        limit: int = 10,
    ) -> List[OptimizationKnowledge]:
        """根据算子名称查询优化知识"""
        try:
            # 从 Redis 获取该算子的所有 optimization IDs
            # 存储层使用 operator:{name}:opts:{type} 模式，需要用 scan_iter 匹配
            opt_ids = set()
            for key in self._redis.scan_iter(f"operator:{operator_name}:opts:*"):
                ids = self._redis.smembers(key)
                opt_ids.update(ids)

            if not opt_ids:
                # 尝试小写版本
                for key in self._redis.scan_iter(f"operator:{operator_name.lower()}:opts:*"):
                    ids = self._redis.smembers(key)
                    opt_ids.update(ids)

            if not opt_ids:
                return []

            # 从 Redis 获取详细信息
            optimizations = []
            for opt_id in list(opt_ids)[:limit]:
                opt_key = f"optimization:{opt_id}"
                opt_data = self._redis.hgetall(opt_key)
                if opt_data:
                    opt = self._optimization_from_redis(opt_data)
                    if opt and opt.confidence >= min_confidence:
                        optimizations.append(opt)

            return optimizations

        except Exception as e:
            logger.error(f"Failed to query optimizations for operator {operator_name}: {e}")
            return []

    async def _query_bugs_semantic(
        self,
        query: str,
        operator_name: Optional[str] = None,
        limit: int = 5,
    ) -> List[BugFixKnowledge]:
        """语义查询 Bug 修复知识"""
        try:
            # 获取 bug_fixes collection
            collection = self._chroma.get_collection("bug_fixes")

            # 查询向量
            results = collection.query(
                query_texts=[query],
                n_results=limit,
                where={"operator_id": operator_name} if operator_name else None,
            )

            if not results or not results.get("ids"):
                return []

            bugs = []
            for i, bug_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                bug_key = f"bugfix:{bug_id}"
                bug_data = self._redis.hgetall(bug_key)
                if bug_data:
                    bug = self._bug_from_redis(bug_data)
                    if bug:
                        bugs.append(bug)

            return bugs

        except Exception as e:
            logger.error(f"Failed to semantic query bugs: {e}")
            return []

    async def _query_api_exact(
        self,
        api_name: str,
    ) -> List[AscendCAPIDefinition]:
        """精确查询 API"""
        try:
            # 获取 ascend_apis collection
            collection = self._chroma.get_collection("ascend_apis")

            # 查询
            results = collection.get(
                where={"canonical_name": api_name},
            )

            if not results or not results.get("ids"):
                # 尝试模糊匹配
                results = collection.get(
                    where_document={"$contains": api_name},
                )

            if not results or not results.get("ids"):
                return []

            apis = []
            for i, api_id in enumerate(results["ids"]):
                metadata = results["metadatas"][i] if results.get("metadatas") else {}
                document = results["documents"][i] if results.get("documents") else ""
                api = self._api_from_chroma(api_id, metadata, document)
                apis.append(api)

            return apis

        except Exception as e:
            logger.error(f"Failed to exact query API {api_name}: {e}")
            return []

    async def _query_api_semantic(
        self,
        query: str,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        limit: int = 10,
    ) -> List[AscendCAPIDefinition]:
        """语义查询 API"""
        try:
            # 获取 ascend_apis collection
            collection = self._chroma.get_collection("ascend_apis")

            # 使用 QwenEmbedder 生成查询向量
            query_embedding = self._embedder.encode_api(query)

            # 构建 where 条件
            where = None
            if category or subcategory:
                where = {}
                if category:
                    where["category"] = category
                if subcategory:
                    where["subcategory"] = subcategory

            # 使用 embedding 向量查询
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=where,
            )

            if not results or not results.get("ids"):
                return []

            apis = []
            for i, api_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                document = results["documents"][0][i] if results.get("documents") else ""
                api = self._api_from_chroma(api_id, metadata, document)
                apis.append(api)

            return apis

        except Exception as e:
            logger.error(f"Failed to semantic query APIs: {e}")
            return []

    def _bug_from_redis(self, data: dict) -> Optional[BugFixKnowledge]:
        """从 Redis 数据构建 BugFixKnowledge"""
        try:
            from .models import BugSeverity, BugCategory, ExtractionMethod

            severity_str = data.get("severity", "MINOR")
            try:
                severity = BugSeverity(severity_str)
            except ValueError:
                severity = BugSeverity.MINOR

            category_str = data.get("category", "CORRECTNESS")
            try:
                category = BugCategory(category_str)
            except ValueError:
                category = BugCategory.CORRECTNESS

            extraction_str = data.get("extraction_method", "LLM")
            try:
                extraction_method = ExtractionMethod(extraction_str)
            except ValueError:
                extraction_method = ExtractionMethod.LLM

            return BugFixKnowledge(
                bug_id=data.get("bug_id", ""),
                operator_id=data.get("operator_id", ""),
                source_repo=data.get("source_repo", ""),
                source_pr=data.get("source_pr", ""),
                bug_title=data.get("bug_title", ""),
                symptom=data.get("symptom", ""),
                severity=severity,
                category=category,
                root_cause=data.get("root_cause"),
                trigger_conditions=data.get("trigger_conditions", "").split("|") if data.get("trigger_conditions") else [],
                fix_pattern=data.get("fix_pattern", ""),
                workarounds=data.get("workarounds", "").split("|") if data.get("workarounds") else [],
                related_apis=data.get("related_apis", "").split("|") if data.get("related_apis") else [],
                confidence=float(data.get("confidence", 0.5)),
                extraction_method=extraction_method,
                review_status=data.get("review_status", "pending"),
            )
        except Exception as e:
            logger.error(f"Failed to parse bug data: {e}")
            return None

    def _optimization_from_redis(self, data: dict) -> Optional[OptimizationKnowledge]:
        """从 Redis 数据构建 OptimizationKnowledge"""
        try:
            from .models import ExtractionMethod

            extraction_str = data.get("extraction_method", "LLM")
            try:
                extraction_method = ExtractionMethod(extraction_str)
            except ValueError:
                extraction_method = ExtractionMethod.LLM

            improvement = data.get("improvement_ratio")
            improvement_ratio = float(improvement) if improvement else None

            return OptimizationKnowledge(
                opt_id=data.get("opt_id", ""),
                operator_id=data.get("operator_id", ""),
                source_repo=data.get("source_repo", ""),
                source_pr=data.get("source_pr", ""),
                opt_title=data.get("opt_title", ""),
                optimization_type=data.get("optimization_type", "").split("|") if data.get("optimization_type") else [],
                optimization_description=data.get("optimization_description", ""),
                improvement_ratio=improvement_ratio,
                related_apis=data.get("related_apis", "").split("|") if data.get("related_apis") else [],
                confidence=float(data.get("confidence", 0.5)),
                extraction_method=extraction_method,
                review_status=data.get("review_status", "pending"),
            )
        except Exception as e:
            logger.error(f"Failed to parse optimization data: {e}")
            return None

    def _api_from_chroma(self, api_id: str, metadata: dict, document: str) -> AscendCAPIDefinition:
        """从 ChromaDB 数据构建 AscendCAPIDefinition"""
        from .models import APISourceInfo, APIParameter, APIReturnValue

        params = []
        if metadata.get("parameters"):
            try:
                import json
                params_data = json.loads(metadata["parameters"])
                for p in params_data:
                    params.append(APIParameter(
                        name=p.get("name", ""),
                        type=p.get("type", ""),
                        description=p.get("description", ""),
                        required=p.get("required", True),
                    ))
            except Exception:
                pass

        return_value = None
        if metadata.get("return_value"):
            try:
                import json
                rv_data = json.loads(metadata["return_value"])
                return_value = APIReturnValue(
                    type=rv_data.get("type", ""),
                    description=rv_data.get("description", ""),
                )
            except Exception:
                pass

        source = None
        if metadata.get("source_type"):
            source = APISourceInfo(
                source_type=metadata.get("source_type", "official"),
                source_url=metadata.get("source_url", ""),
            )

        return AscendCAPIDefinition(
            api_id=api_id,
            canonical_name=metadata.get("name", api_id),  # metadata存的是"name"
            full_signature=metadata.get("full_signature", ""),
            category=metadata.get("category", "unknown"),
            subcategory=metadata.get("subcategory", ""),
            description=document or metadata.get("description", ""),
            parameters=params,
            return_value=return_value or APIReturnValue(type="void", description=""),
            version_info=metadata.get("version_info", ""),
            source=source,
            confidence=float(metadata.get("confidence", 1.0)),
        )

    async def _apply_confidence_ranking(
        self,
        items: list,
        item_type: str = "bug"
    ) -> list:
        """
        应用置信度感知排序

        Args:
            items: 知识条目列表 (BugFixKnowledge or OptimizationKnowledge)
            item_type: 条目类型 (bug | optimization)

        Returns:
            排序后的列表
        """
        if not items:
            return items

        # 转换为 dict 格式供 ranker 使用
        item_dicts = []
        for item in items:
            # 推导 source_type (official: ascend 官方仓, community: 其他)
            source_repo = getattr(item, "source_repo", "")
            if "ascend" in source_repo.lower() or "huawei" in source_repo.lower():
                source_type = "official"
            elif source_repo:
                source_type = "community"
            else:
                source_type = "other"

            # 获取引用统计 (用于准确性评分)
            item_id = getattr(item, "bug_id", None) or getattr(item, "opt_id", None) or str(item)
            citation_stats = self._citation_tracker.get_stats(item_id, item_type)

            # 构建元数据
            metadata = {
                "source_type": source_type,
                "contributor_level": "active",  # 默认值
                "updated_at": getattr(item, "updated_at", None),
                "confidence": getattr(item, "confidence", 0.5),
                "source_repo": source_repo,
                "source_pr": getattr(item, "source_pr", ""),
                # 引用追踪数据 (用于准确性评分)
                "citation_count": citation_stats.citation_count,
                "correction_count": citation_stats.correction_count,
            }

            item_dict = {
                "id": item_id,
                "score": getattr(item, "confidence", 0.5),
                "metadata": metadata,
            }
            item_dicts.append(item_dict)

        # 使用置信度排序器排序
        ranked_items = await self._confidence_ranker.rank_results(item_dicts, top_k=len(item_dicts))

        # 按排序顺序重新组织原始对象，并更新置信度
        id_to_item = {
            getattr(item, "bug_id", None) or getattr(item, "opt_id", None): item
            for item in items
        }
        id_to_ranked = {item.id: item for item in ranked_items}

        sorted_items = []
        for item in items:
            item_id = getattr(item, "bug_id", None) or getattr(item, "opt_id", None)
            if item_id in id_to_ranked:
                ranked_item = id_to_ranked[item_id]
                # 更新置信度为综合评分
                item.confidence = ranked_item.score.total
                sorted_items.append(item)

        return sorted_items

    def _record_citations_for_results(
        self,
        items: list,
        item_type: str = "bug"
    ) -> None:
        """
        记录查询结果的引用

        Args:
            items: 知识条目列表 (BugFixKnowledge or OptimizationKnowledge)
            item_type: 条目类型 (bug | optimization)
        """
        if not items:
            return

        for item in items:
            item_id = getattr(item, "bug_id", None) or getattr(item, "opt_id", None)
            if item_id:
                self._citation_tracker.record_citation(item_id, item_type)

    def _generate_checks(self, bug: BugFixKnowledge) -> List[str]:
        """生成建议检查项"""
        checks = []

        if bug.trigger_conditions:
            checks.append(f"检查是否满足触发条件: {', '.join(bug.trigger_conditions[:2])}")

        if bug.related_apis:
            checks.append(f"检查相关 API 使用: {', '.join(bug.related_apis[:2])}")

        if bug.workarounds:
            checks.append(f"考虑临时规避方案: {bug.workarounds[0]}")

        return checks


@dataclass
class DevelopmentQueryResult:
    """开发查询结果"""
    operator_name: str
    query_type: str
    total_count: int
    bug_fixes: List[BugFixKnowledge]
    optimizations: List[OptimizationKnowledge]
    related_knowledge: List = field(default_factory=list)


@dataclass
class TroubleshootingResult:
    """问题排查结果"""
    symptom: str
    possible_causes: List["PossibleCause"]
    related_knowledge: List = field(default_factory=list)
    related_apis: List[AscendCAPIDefinition] = field(default_factory=list)


@dataclass
class PossibleCause:
    """可能原因"""
    bug_id: str
    description: str
    confidence: float
    root_cause: str
    trigger_conditions: List[str]
    suggested_fix: str
    suggested_checks: List[str] = field(default_factory=list)
