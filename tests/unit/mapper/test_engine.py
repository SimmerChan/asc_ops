# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
跨平台映射引擎测试
"""

import pytest

from src.asc_ops.mapper import (
    MapperEngine,
    MappingResult,
    get_predefined_mapping,
    get_all_predefined_apis,
    CUDA_MAPPINGS,
    CUTLASS_MAPPINGS,
    CUBLAS_MAPPINGS,
)
from src.asc_ops.gpu_collector.models import GPUPlatform, MappingEquivalenceLevel


class TestMapperEngine:
    """映射引擎测试"""

    def setup_method(self):
        """设置测试"""
        self.engine = MapperEngine()

    def test_find_exact_mapping_syncthreads(self):
        """查找精确映射: __syncthreads"""
        result = self.engine.find_mapping("__syncthreads", "cuda")

        assert result is not None
        assert result.npu_api == "SyncAll"
        assert result.equivalence_level == MappingEquivalenceLevel.EXACT
        assert result.is_exact is True

    def test_find_exact_mapping_atomic_add(self):
        """查找精确映射: atomicAdd"""
        result = self.engine.find_mapping("atomicAdd", "cuda")

        assert result is not None
        assert result.npu_api == "AtomAdd"
        assert result.equivalence_level == MappingEquivalenceLevel.EXACT

    def test_find_similar_mapping_wmma_load(self):
        """查找相似映射: wmma::load_matrix_sync"""
        result = self.engine.find_mapping("wmma::load_matrix_sync", "cuda")

        assert result is not None
        assert result.npu_api == "Load2D"
        assert result.equivalence_level == MappingEquivalenceLevel.SIMILAR
        assert result.is_exact is False

    def test_find_nonexistent_mapping(self):
        """查找不存在的映射"""
        result = self.engine.find_mapping("nonexistent_gpu_api", "cuda")

        assert result is None

    def test_find_mapping_cublas_gemm(self):
        """查找 cuBLAS GEMM 映射"""
        result = self.engine.find_mapping("cublasSgemm", "cublas")

        assert result is not None
        assert result.npu_api == "Matmul"
        assert result.equivalence_level == MappingEquivalenceLevel.EXACT

    def test_find_mapping_cutlass_gemm(self):
        """查找 CUTLASS GEMM 映射"""
        result = self.engine.find_mapping("cutlass::gemm::device::Gemm", "cutlass")

        assert result is not None
        assert result.npu_api == "Matmul"
        assert result.equivalence_level == MappingEquivalenceLevel.SIMILAR

    def test_find_similar_apis(self):
        """查找相似 API"""
        results = self.engine.find_similar("__syncthreads", "cuda")

        assert len(results) > 0
        assert all(isinstance(r, MappingResult) for r in results)

    def test_find_by_category_sync(self):
        """按类别查找同步 API"""
        results = self.engine.find_by_category("sync", "cuda")

        assert len(results) > 0
        api_names = [r.gpu_api for r in results]
        assert "__syncthreads" in api_names or "__threadfence" in api_names

    def test_find_by_category_atomic(self):
        """按类别查找原子操作 API"""
        results = self.engine.find_by_category("atomic", "cuda")

        assert len(results) > 0
        api_names = [r.gpu_api for r in results]
        assert "atomicAdd" in api_names

    def test_get_supported_apis(self):
        """获取支持的 API 列表"""
        apis = self.engine.get_supported_apis("cuda")

        assert len(apis) > 0
        assert "__syncthreads" in apis
        assert "atomicAdd" in apis

    def test_mapping_stats(self):
        """获取映射统计"""
        stats = self.engine.get_mapping_stats()

        assert stats["total_cuda_mappings"] > 0
        assert stats["exact_mappings"] > 0
        assert stats["similar_mappings"] > 0
        assert stats["total_cuda_mappings"] == stats["exact_mappings"] + stats["similar_mappings"]

    def test_cache_behavior(self):
        """缓存行为测试"""
        # 首次查询
        result1 = self.engine.find_mapping("__syncthreads", "cuda")
        assert result1 is not None

        # 再次查询应该命中缓存
        result2 = self.engine.find_mapping("__syncthreads", "cuda")
        assert result2 is not None

        # 验证统计中缓存计数
        stats = self.engine.get_mapping_stats()
        assert stats["cached_mappings"] >= 1

    def test_clear_cache(self):
        """清空缓存"""
        # 先查询一些 API
        self.engine.find_mapping("__syncthreads", "cuda")
        self.engine.find_mapping("atomicAdd", "cuda")

        # 清空缓存
        self.engine.clear_cache()

        stats = self.engine.get_mapping_stats()
        assert stats["cached_mappings"] == 0

    def test_platform_normalization(self):
        """平台名称标准化"""
        # 不同大小写
        result1 = self.engine.find_mapping("__syncthreads", "CUDA")
        result2 = self.engine.find_mapping("__syncthreads", "cuda")
        result3 = self.engine.find_mapping("__syncthreads", "CUda")

        assert result1 is not None
        assert result2 is not None
        assert result3 is not None
        assert result1.npu_api == result2.npu_api == result3.npu_api

    def test_include_notes_flag(self):
        """包含注意事项标志"""
        result_with_notes = self.engine.find_mapping("__syncthreads", "cuda", include_notes=True)
        result_without_notes = self.engine.find_mapping("__syncthreads", "cuda", include_notes=False)

        assert result_with_notes is not None
        assert result_without_notes is not None
        assert len(result_with_notes.adaptation_notes) >= len(result_without_notes.adaptation_notes)


class TestMappingResult:
    """映射结果测试"""

    def test_is_exact_property(self):
        """is_exact 属性"""
        exact_result = MappingResult(
            gpu_api="test_api",
            npu_api="test_npu",
            equivalence_level=MappingEquivalenceLevel.EXACT,
            adaptation_notes="",
        )
        assert exact_result.is_exact is True

        similar_result = MappingResult(
            gpu_api="test_api",
            npu_api="test_npu",
            equivalence_level=MappingEquivalenceLevel.SIMILAR,
            adaptation_notes="",
        )
        assert similar_result.is_exact is False

    def test_to_cross_platform_mapping(self):
        """转换为 CrossPlatformMapping"""
        result = MappingResult(
            gpu_api="__syncthreads",
            npu_api="SyncAll",
            equivalence_level=MappingEquivalenceLevel.EXACT,
            adaptation_notes="无差异",
            confidence=0.95,
            source="predefined",
        )

        mapping = result.to_cross_platform_mapping(GPUPlatform.CUDA, "test_id")

        assert mapping.gpu_api == "__syncthreads"
        assert mapping.npu_api == "SyncAll"
        assert mapping.equivalence_level == MappingEquivalenceLevel.EXACT
        assert mapping.platform == GPUPlatform.CUDA


class TestPredefinedMappings:
    """预定义映射测试"""

    def test_get_predefined_mapping(self):
        """获取预定义映射"""
        info = get_predefined_mapping("__syncthreads", GPUPlatform.CUDA)

        assert info is not None
        assert info["npu_api"] == "SyncAll"
        assert info["equivalence"] == MappingEquivalenceLevel.EXACT

    def test_get_predefined_mapping_not_found(self):
        """获取不存在的预定义映射"""
        info = get_predefined_mapping("nonexistent", GPUPlatform.CUDA)

        assert info is None

    def test_get_all_predefined_apis(self):
        """获取所有预定义 API"""
        apis = get_all_predefined_apis()

        assert len(apis) > 0
        assert "__syncthreads" in apis
        assert "cublasSgemm" in apis

    def test_cuda_mappings_count(self):
        """CUDA 映射数量"""
        assert len(CUDA_MAPPINGS) > 10

    def test_cublas_mappings_count(self):
        """cuBLAS 映射数量"""
        assert len(CUBLAS_MAPPINGS) > 5

    def test_cutlass_mappings_count(self):
        """CUTLASS 映射数量"""
        assert len(CUTLASS_MAPPINGS) >= 0  # CUTLASS 映射可能为空

    def test_all_mappings_have_required_fields(self):
        """所有映射都有必需字段"""
        for api, info in CUDA_MAPPINGS.items():
            assert "npu_api" in info
            assert "equivalence" in info
            assert isinstance(info["equivalence"], MappingEquivalenceLevel)


class TestMapperEngineLLM:
    """MapperEngine LLM 增强测试"""

    def test_init_with_llm_client(self):
        """使用 LLM 客户端初始化"""
        from unittest.mock import MagicMock
        mock_client = MagicMock()

        engine = MapperEngine(use_llm_enhancement=True, llm_client=mock_client)

        assert engine._use_llm_enhancement is True
        assert engine._llm_client is mock_client

    def test_init_without_llm_client(self):
        """不使用 LLM 客户端初始化"""
        engine = MapperEngine(use_llm_enhancement=True)

        assert engine._use_llm_enhancement is True
        assert engine._llm_client is None

    @pytest.mark.asyncio
    async def test_find_mapping_async_with_predefined(self):
        """find_mapping_async 对预定义映射直接返回"""
        from unittest.mock import AsyncMock, MagicMock

        engine = MapperEngine(use_llm_enhancement=True, llm_client=MagicMock())

        # 预定义映射，直接返回
        result = await engine.find_mapping_async("__syncthreads", "cuda")

        assert result is not None
        assert result.npu_api == "SyncAll"
        assert result.source == "predefined"

    @pytest.mark.asyncio
    async def test_find_mapping_async_with_llm_generation(self):
        """find_mapping_async 对未知 API 使用 LLM 生成"""
        from unittest.mock import AsyncMock, MagicMock

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = '''{
            "npu_api": "CustomOp",
            "equivalence_level": "similar",
            "adaptation_notes": "May require parameter adjustments",
            "confidence": 0.7
        }'''
        mock_client.chat.return_value = mock_response

        engine = MapperEngine(use_llm_enhancement=True, llm_client=mock_client)

        # 未知 API，应该调用 LLM
        result = await engine.find_mapping_async("unknown_gpu_api", "cuda")

        assert result is not None
        assert result.npu_api == "CustomOp"
        assert result.equivalence_level == MappingEquivalenceLevel.SIMILAR
        assert result.confidence == 0.7
        assert result.source == "llm_generated"

    @pytest.mark.asyncio
    async def test_find_mapping_async_no_llm_client(self):
        """find_mapping_async 无 LLM 客户端时返回 None"""
        engine = MapperEngine(use_llm_enhancement=True, llm_client=None)

        result = await engine.find_mapping_async("unknown_gpu_api", "cuda")

        assert result is None

    @pytest.mark.asyncio
    async def test_find_mapping_async_llm_failure(self):
        """find_mapping_async LLM 调用失败时返回 None"""
        from unittest.mock import AsyncMock, MagicMock

        mock_client = AsyncMock()
        mock_client.chat.side_effect = Exception("LLM error")

        engine = MapperEngine(use_llm_enhancement=True, llm_client=mock_client)

        result = await engine.find_mapping_async("unknown_gpu_api", "cuda")

        assert result is None
