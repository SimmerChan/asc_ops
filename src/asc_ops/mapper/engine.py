# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
跨平台映射引擎

GPU API → NPU API 映射查询
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, TYPE_CHECKING

from ..gpu_collector.models import (
    CrossPlatformMapping,
    GPUPlatform,
    MappingEquivalenceLevel,
)

if TYPE_CHECKING:
    from ..llm import UnifiedLLMClient
    from ..gpu_collector.storage import GPUStorage

logger = logging.getLogger(__name__)


# LLM 映射生成 Prompt 模板
MAPPING_GENERATION_PROMPT = """You are an expert in GPU (CUDA/CUTLASS/CUBLAS) to NPU (AscendC) API migration.

Given a GPU API, generate the most likely NPU (AscendC) equivalent mapping.

GPU API: {gpu_api}
GPU Platform: {platform}

Consider:
1. API naming patterns (AscendC follows similar conventions)
2. Functionality equivalence
3. Common migration patterns

Respond in JSON format:
{{
    "npu_api": "corresponding AscendC API name or closest equivalent",
    "equivalence_level": "exact|similar|conceptual",
    "adaptation_notes": "Key differences or migration notes (1-2 sentences)",
    "confidence": 0.0-1.0
}}

Rules:
- npu_api should be a plausible AscendC API name (e.g., Matmul, VecReduce, Tensor)
- equivalence_level: exact (direct replacement), similar (with changes), conceptual (same idea, different API)
- confidence reflects how certain you are about this mapping
- If no plausible mapping exists, use "N/A" for npu_api and "unknown" for equivalence_level
"""


@dataclass
class MappingResult:
    """映射查询结果"""
    gpu_api: str
    npu_api: str
    equivalence_level: MappingEquivalenceLevel
    adaptation_notes: str
    confidence: float = 1.0
    source: str = "predefined"

    @property
    def is_exact(self) -> bool:
        """是否为精确映射"""
        return self.equivalence_level == MappingEquivalenceLevel.EXACT

    def to_cross_platform_mapping(
        self,
        platform: GPUPlatform,
        mapping_id: str,
    ) -> CrossPlatformMapping:
        """转换为 CrossPlatformMapping 对象"""
        return CrossPlatformMapping(
            mapping_id=mapping_id,
            gpu_api=self.gpu_api,
            npu_api=self.npu_api,
            platform=platform,
            equivalence_level=self.equivalence_level,
            adaptation_notes=self.adaptation_notes,
            source=self.source,
            confidence=self.confidence,
        )


class MapperEngine:
    """
    跨平台映射引擎

    提供 GPU API 到 NPU API 的映射查询
    """

    def __init__(
        self,
        use_llm_enhancement: bool = False,
        llm_client: Optional["UnifiedLLMClient"] = None,
        storage: Optional["GPUStorage"] = None,
    ):
        """
        初始化映射引擎

        Args:
            use_llm_enhancement: 是否使用 LLM 增强未匹配 API 的映射
            llm_client: LLM 客户端 (用于生成映射建议)
            storage: GPU 存储实例 (用于查询 cross_platform_mappings)
        """
        self._use_llm_enhancement = use_llm_enhancement
        self._llm_client = llm_client
        self._storage = storage
        self._cache: Dict[str, MappingResult] = {}

        logger.info(f"MapperEngine initialized (llm_enhancement={use_llm_enhancement}, storage={storage is not None})")

    def find_mapping(
        self,
        gpu_api: str,
        platform: str = "cuda",
        include_notes: bool = True,
    ) -> Optional[MappingResult]:
        """
        查找 GPU API 的 NPU 映射 (同步版本)

        Args:
            gpu_api: GPU API 名称
            platform: GPU 平台 (cuda/cutlass/cublas/cudnn)
            include_notes: 是否包含适配注意事项

        Returns:
            MappingResult 或 None
        """
        # 标准化平台
        gpu_platform = self._normalize_platform(platform)

        # 检查缓存
        cache_key = f"{gpu_api}:{gpu_platform.value}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 优先从存储查询
        if self._storage:
            result = self._lookup_from_storage(gpu_api, gpu_platform, include_notes)
            if result:
                self._cache[cache_key] = result
                return result
            return None

        return None

    def _lookup_from_storage(
        self,
        gpu_api: str,
        gpu_platform: GPUPlatform,
        include_notes: bool = True,
    ) -> Optional[MappingResult]:
        """从存储中查询映射"""
        if not self._storage:
            return None

        try:
            # 查询 cross_platform_mappings
            mappings = self._storage.search_cross_platform_mappings(
                query=gpu_api,
                platform=gpu_platform,
                min_confidence=0.5,
                limit=10,
            )

            # 精确匹配 gpu_api
            for mapping in mappings:
                if mapping.gpu_api.lower() == gpu_api.lower():
                    return MappingResult(
                        gpu_api=mapping.gpu_api,
                        npu_api=mapping.npu_api,
                        equivalence_level=mapping.equivalence_level,
                        adaptation_notes=mapping.adaptation_notes if include_notes else "",
                        confidence=mapping.confidence,
                        source=mapping.source,
                    )

            # 如果没有精确匹配但有高置信度结果，返回第一个
            if mappings and mappings[0].confidence >= 0.8:
                mapping = mappings[0]
                return MappingResult(
                    gpu_api=mapping.gpu_api,
                    npu_api=mapping.npu_api,
                    equivalence_level=mapping.equivalence_level,
                    adaptation_notes=mapping.adaptation_notes if include_notes else "",
                    confidence=mapping.confidence,
                    source=mapping.source,
                )

        except Exception as e:
            logger.warning(f"Storage lookup failed for {gpu_api}: {e}")

        return None

    async def find_mapping_async(
        self,
        gpu_api: str,
        platform: str = "cuda",
        include_notes: bool = True,
    ) -> Optional[MappingResult]:
        """
        查找 GPU API 的 NPU 映射 (异步版本，支持 LLM 增强)

        Args:
            gpu_api: GPU API 名称
            platform: GPU 平台 (cuda/cutlass/cublas/cudnn)
            include_notes: 是否包含适配注意事项

        Returns:
            MappingResult 或 None
        """
        # 标准化平台
        gpu_platform = self._normalize_platform(platform)

        # 检查缓存
        cache_key = f"{gpu_api}:{gpu_platform.value}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 优先从存储查询
        if self._storage:
            result = self._lookup_from_storage(gpu_api, gpu_platform, include_notes)
            if result:
                self._cache[cache_key] = result
                return result

            # 如果启用 LLM 增强，生成建议
            if self._use_llm_enhancement:
                llm_result = await self._generate_llm_mapping(gpu_api, gpu_platform)
                if llm_result:
                    self._cache[cache_key] = llm_result
                    return llm_result
            return None

        return None

    def find_similar(
        self,
        gpu_api: str,
        platform: str = "cuda",
        limit: int = 3,
    ) -> List[MappingResult]:
        """
        查找相似的 GPU API 映射

        Args:
            gpu_api: GPU API 名称
            platform: GPU 平台
            limit: 返回数量限制

        Returns:
            相似的 MappingResult 列表
        """
        gpu_platform = self._normalize_platform(platform)

        # 如果有存储，使用向量搜索找相似
        if self._storage:
            try:
                mappings = self._storage.search_cross_platform_mappings(
                    query=gpu_api,
                    platform=gpu_platform,
                    min_confidence=0.3,
                    limit=limit * 2,
                )

                results = []
                api_lower = gpu_api.lower()
                for mapping in mappings:
                    sim = self._calculate_similarity(api_lower, mapping.gpu_api.lower())
                    if sim > 0.3:
                        results.append(MappingResult(
                            gpu_api=mapping.gpu_api,
                            npu_api=mapping.npu_api,
                            equivalence_level=mapping.equivalence_level,
                            adaptation_notes=mapping.adaptation_notes,
                            confidence=sim,
                            source=mapping.source,
                        ))

                results.sort(key=lambda x: x.confidence, reverse=True)
                return results[:limit]
            except Exception as e:
                logger.warning(f"Storage similarity search failed: {e}")

        return []

    def find_by_category(
        self,
        category: str,
        platform: str = "cuda",
    ) -> List[MappingResult]:
        """
        按类别查找映射

        Args:
            category: 类别 (如 "sync", "memory", "compute")
            platform: GPU 平台

        Returns:
            该类别的 MappingResult 列表
        """
        gpu_platform = self._normalize_platform(platform)

        # 如果有存储，从存储查询
        if self._storage:
            try:
                # 查询该平台的所有映射
                mappings = self._storage.search_cross_platform_mappings(
                    query=category,
                    platform=gpu_platform,
                    min_confidence=0.0,
                    limit=100,
                )

                results = []
                for mapping in mappings:
                    # 根据 API 名称推断类别
                    api_lower = mapping.gpu_api.lower()
                    if category == "sync" and any(s in api_lower for s in ["sync", "fence", "shuffle"]):
                        results.append(MappingResult(
                            gpu_api=mapping.gpu_api,
                            npu_api=mapping.npu_api,
                            equivalence_level=mapping.equivalence_level,
                            adaptation_notes=mapping.adaptation_notes,
                            source=mapping.source,
                        ))
                    elif category == "atomic" and "atomic" in api_lower:
                        results.append(MappingResult(
                            gpu_api=mapping.gpu_api,
                            npu_api=mapping.npu_api,
                            equivalence_level=mapping.equivalence_level,
                            adaptation_notes=mapping.adaptation_notes,
                            source=mapping.source,
                        ))

                return results
            except Exception as e:
                logger.warning(f"Storage category search failed: {e}")

        return []

    def get_supported_apis(self, platform: str = "cuda") -> List[str]:
        """获取支持的 GPU API 列表"""
        gpu_platform = self._normalize_platform(platform)

        if self._storage:
            try:
                mappings = self._storage.search_cross_platform_mappings(
                    query="",
                    platform=gpu_platform,
                    min_confidence=0.0,
                    limit=1000,
                )
                return list(set(m.gpu_api for m in mappings))
            except Exception as e:
                logger.warning(f"Storage get_supported_apis failed: {e}")

        return []

    def get_mapping_stats(self) -> Dict[str, Any]:
        """获取映射统计信息"""
        stats = {
            "cached_mappings": len(self._cache),
            "storage_available": self._storage is not None,
        }

        if self._storage:
            try:
                # 统计各平台映射数量
                for platform in [GPUPlatform.CUDA, GPUPlatform.CUTLASS, GPUPlatform.CUBLAS]:
                    mappings = self._storage.search_cross_platform_mappings(
                        query="",
                        platform=platform,
                        min_confidence=0.0,
                        limit=10000,
                    )
                    platform_key = f"total_{platform.value}_mappings"
                    stats[platform_key] = len(mappings)
                    stats[f"exact_{platform.value}_mappings"] = sum(
                        1 for m in mappings if m.equivalence_level == MappingEquivalenceLevel.EXACT
                    )
                    stats[f"similar_{platform.value}_mappings"] = sum(
                        1 for m in mappings if m.equivalence_level == MappingEquivalenceLevel.SIMILAR
                    )
            except Exception as e:
                logger.warning(f"Storage stats query failed: {e}")

        return stats

    def _normalize_platform(self, platform: str) -> GPUPlatform:
        """标准化平台名称"""
        platform = platform.lower()
        if platform == "cuda":
            return GPUPlatform.CUDA
        elif platform == "cutlass":
            return GPUPlatform.CUTLASS
        elif platform == "cublas":
            return GPUPlatform.CUBLAS
        elif platform == "cudnn":
            return GPUPlatform.CUDNN
        return GPUPlatform.CUDA

    def _calculate_similarity(self, api1: str, api2: str) -> float:
        """
        计算两个 API 名称的相似度

        简单的基于子串的相似度计算
        """
        if not api1 or not api2:
            return 0.0

        # 完全匹配
        if api1 == api2:
            return 1.0

        # 前缀匹配
        if api1.startswith(api2) or api2.startswith(api1):
            return 0.8

        # 子串匹配
        if api1 in api2 or api2 in api1:
            return 0.6

        # 共同子串
        shorter, longer = (api1, api2) if len(api1) < len(api2) else (api2, api1)
        common_chars = sum(1 for c in shorter if c in longer)
        if common_chars > 0:
            return common_chars / len(longer) * 0.5

        return 0.0

    async def _generate_llm_mapping(
        self,
        gpu_api: str,
        platform: GPUPlatform,
    ) -> Optional[MappingResult]:
        """
        使用 LLM 生成映射建议

        Args:
            gpu_api: GPU API 名称
            platform: GPU 平台

        Returns:
            MappingResult 或 None (如果 LLM 不可用或生成失败)
        """
        if not self._llm_client:
            logger.warning(f"LLM client not provided, cannot generate mapping for {gpu_api}")
            return None

        try:
            from ..llm import Message, MessageRole

            prompt = MAPPING_GENERATION_PROMPT.format(
                gpu_api=gpu_api,
                platform=platform.value.upper(),
            )

            messages = [
                Message(role=MessageRole.USER, content=prompt)
            ]

            response = await self._llm_client.chat(
                messages=messages,
                max_tokens=256,
                temperature=0.3,
            )

            # 解析 JSON 响应
            import json
            try:
                data = json.loads(response.content)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse LLM response as JSON: {response.content[:200]}")
                return None

            # 解析等价级别
            equiv_str = data.get("equivalence_level", "conceptual").lower()
            if equiv_str == "exact":
                equiv_level = MappingEquivalenceLevel.EXACT
            elif equiv_str == "similar":
                equiv_level = MappingEquivalenceLevel.SIMILAR
            else:
                equiv_level = MappingEquivalenceLevel.CONCEPTUAL

            result = MappingResult(
                gpu_api=gpu_api,
                npu_api=data.get("npu_api", "unknown"),
                equivalence_level=equiv_level,
                adaptation_notes=data.get("adaptation_notes", ""),
                confidence=float(data.get("confidence", 0.5)),
                source="llm_generated",
            )

            logger.info(f"LLM generated mapping for {gpu_api}: {result.npu_api} (confidence={result.confidence})")
            return result

        except Exception as e:
            logger.error(f"LLM mapping generation failed for {gpu_api}: {e}")
            return None

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
