# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
跨平台映射引擎

GPU API → NPU API 映射查询
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from ..gpu_collector.models import (
    CrossPlatformMapping,
    GPUPlatform,
    MappingEquivalenceLevel,
)

from .predefined_mappings import (
    get_predefined_mapping,
    get_all_predefined_apis,
    CUDA_MAPPINGS,
    CUTLASS_MAPPINGS,
    CUBLAS_MAPPINGS,
)

logger = logging.getLogger(__name__)


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

    def __init__(self, use_llm_enhancement: bool = False):
        """
        初始化映射引擎

        Args:
            use_llm_enhancement: 是否使用 LLM 增强未匹配 API 的映射
        """
        self._use_llm_enhancement = use_llm_enhancement
        self._cache: Dict[str, MappingResult] = {}

    def find_mapping(
        self,
        gpu_api: str,
        platform: str = "cuda",
        include_notes: bool = True,
    ) -> Optional[MappingResult]:
        """
        查找 GPU API 的 NPU 映射

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

        # 查找预定义映射
        mapping_info = get_predefined_mapping(gpu_api, gpu_platform)

        if mapping_info:
            result = MappingResult(
                gpu_api=gpu_api,
                npu_api=mapping_info["npu_api"],
                equivalence_level=mapping_info["equivalence"],
                adaptation_notes=mapping_info.get("notes", "") if include_notes else "",
                confidence=1.0 if mapping_info["equivalence"] == MappingEquivalenceLevel.EXACT else 0.8,
                source="predefined",
            )
            self._cache[cache_key] = result
            return result

        # 如果启用 LLM 增强，生成建议
        if self._use_llm_enhancement:
            return self._generate_llm_mapping(gpu_api, gpu_platform)

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
        mappings = self._get_platform_mappings(gpu_platform)

        # 简单的相似度匹配：基于 API 名称前缀/后缀
        results = []
        api_lower = gpu_api.lower()

        for known_api, info in mappings.items():
            if self._calculate_similarity(api_lower, known_api.lower()) > 0.3:
                results.append(MappingResult(
                    gpu_api=known_api,
                    npu_api=info["npu_api"],
                    equivalence_level=info["equivalence"],
                    adaptation_notes=info.get("notes", ""),
                    confidence=self._calculate_similarity(api_lower, known_api.lower()),
                    source="predefined",
                ))

        # 按相似度排序
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results[:limit]

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
        mappings = self._get_platform_mappings(gpu_platform)

        results = []
        for gpu_api, info in mappings.items():
            # 根据 API 名称推断类别
            if category == "sync" and any(s in gpu_api.lower() for s in ["sync", "fence", "shuffle"]):
                results.append(MappingResult(
                    gpu_api=gpu_api,
                    npu_api=info["npu_api"],
                    equivalence_level=info["equivalence"],
                    adaptation_notes=info.get("notes", ""),
                    source="predefined",
                ))
            elif category == "atomic" and "atomic" in gpu_api.lower():
                results.append(MappingResult(
                    gpu_api=gpu_api,
                    npu_api=info["npu_api"],
                    equivalence_level=info["equivalence"],
                    adaptation_notes=info.get("notes", ""),
                    source="predefined",
                ))

        return results

    def get_supported_apis(self, platform: str = "cuda") -> List[str]:
        """获取支持的 GPU API 列表"""
        gpu_platform = self._normalize_platform(platform)
        mappings = self._get_platform_mappings(gpu_platform)
        return list(mappings.keys())

    def get_mapping_stats(self) -> Dict[str, Any]:
        """获取映射统计信息"""
        return {
            "total_cuda_mappings": len(CUDA_MAPPINGS),
            "total_cutlass_mappings": len(CUTLASS_MAPPINGS),
            "total_cublas_mappings": len(CUBLAS_MAPPINGS),
            "exact_mappings": sum(
                1 for m in CUDA_MAPPINGS.values()
                if m["equivalence"] == MappingEquivalenceLevel.EXACT
            ),
            "similar_mappings": sum(
                1 for m in CUDA_MAPPINGS.values()
                if m["equivalence"] == MappingEquivalenceLevel.SIMILAR
            ),
            "cached_mappings": len(self._cache),
        }

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

    def _get_platform_mappings(self, platform: GPUPlatform) -> Dict:
        """获取平台的映射表"""
        if platform == GPUPlatform.CUDA:
            return CUDA_MAPPINGS
        elif platform == GPUPlatform.CUTLASS:
            return CUTLASS_MAPPINGS
        elif platform == GPUPlatform.CUBLAS:
            return CUBLAS_MAPPINGS
        return {}

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

    def _generate_llm_mapping(
        self,
        gpu_api: str,
        platform: GPUPlatform,
    ) -> Optional[MappingResult]:
        """
        使用 LLM 生成映射建议

        (占位实现，后续可接入 LLM)
        """
        # TODO: 接入 LLM 生成映射建议
        logger.info(f"LLM mapping generation not implemented for {gpu_api}")
        return None

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
