# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
查询管道集成测试

测试查询 API 到存储的完整流程
"""

import pytest

from src.asc_ops.mapper import MapperEngine, MappingResult
from src.asc_ops.gpu_collector.models import GPUPlatform, MappingEquivalenceLevel


class TestQueryPipeline:
    """查询管道测试"""

    def test_exact_mapping_query(self):
        """精确映射查询"""
        engine = MapperEngine()

        result = engine.find_mapping("__syncthreads", "cuda")

        assert result is not None
        assert result.npu_api == "SyncAll"
        assert result.equivalence_level == MappingEquivalenceLevel.EXACT

    def test_similar_mapping_query(self):
        """相似映射查询"""
        engine = MapperEngine()

        result = engine.find_mapping("wmma::load_matrix_sync", "cuda")

        assert result is not None
        assert result.is_exact is False

    def test_nonexistent_mapping_query(self):
        """不存在的映射查询"""
        engine = MapperEngine()

        result = engine.find_mapping("nonexistent_gpu_api_xyz", "cuda")

        assert result is None

    def test_similar_apis_query(self):
        """相似 API 查询"""
        engine = MapperEngine()

        results = engine.find_similar("__syncthreads", "cuda")

        assert len(results) >= 1

    def test_mapping_by_category(self):
        """按类别查询映射"""
        engine = MapperEngine()

        sync_results = engine.find_by_category("sync", "cuda")

        assert len(sync_results) >= 1

        atomic_results = engine.find_by_category("atomic", "cuda")

        assert len(atomic_results) >= 1

    def test_cublas_mapping_query(self):
        """cuBLAS 映射查询"""
        engine = MapperEngine()

        result = engine.find_mapping("cublasSgemm", "cublas")

        assert result is not None
        assert result.npu_api == "Matmul"

    def test_cutlass_mapping_query(self):
        """CUTLASS 映射查询"""
        engine = MapperEngine()

        result = engine.find_mapping("cutlass::gemm::device::Gemm", "cutlass")

        assert result is not None
        assert result.is_exact is False

    def test_mapping_stats(self):
        """映射统计"""
        engine = MapperEngine()

        stats = engine.get_mapping_stats()

        assert stats["total_cuda_mappings"] > 0
        assert stats["exact_mappings"] > 0
        assert stats["similar_mappings"] > 0

    def test_mapping_cache(self):
        """映射缓存"""
        engine = MapperEngine()

        # 首次查询
        result1 = engine.find_mapping("__syncthreads", "cuda")

        # 再次查询
        result2 = engine.find_mapping("__syncthreads", "cuda")

        assert result1 is not None
        assert result2 is not None
        assert result1.npu_api == result2.npu_api

        # 验证缓存统计
        stats = engine.get_mapping_stats()
        assert stats["cached_mappings"] >= 1

    def test_cache_clear(self):
        """缓存清空"""
        engine = MapperEngine()

        # 添加到缓存
        engine.find_mapping("__syncthreads", "cuda")
        engine.find_mapping("atomicAdd", "cuda")

        # 清空
        engine.clear_cache()

        # 验证
        stats = engine.get_mapping_stats()
        assert stats["cached_mappings"] == 0


class TestMappingResultConversion:
    """映射结果转换测试"""

    def test_to_cross_platform_mapping(self):
        """转换为 CrossPlatformMapping"""
        result = MappingResult(
            gpu_api="__syncthreads",
            npu_api="SyncAll",
            equivalence_level=MappingEquivalenceLevel.EXACT,
            adaptation_notes="完全等价",
            confidence=0.95,
            source="predefined",
        )

        mapping = result.to_cross_platform_mapping(
            platform=GPUPlatform.CUDA,
            mapping_id="test_id",
        )

        assert mapping.gpu_api == "__syncthreads"
        assert mapping.npu_api == "SyncAll"
        assert mapping.platform == GPUPlatform.CUDA
        assert mapping.equivalence_level == MappingEquivalenceLevel.EXACT

    def test_is_exact_property(self):
        """is_exact 属性"""
        exact = MappingResult(
            gpu_api="api1",
            npu_api="npu1",
            equivalence_level=MappingEquivalenceLevel.EXACT,
            adaptation_notes="",
        )
        assert exact.is_exact is True

        similar = MappingResult(
            gpu_api="api2",
            npu_api="npu2",
            equivalence_level=MappingEquivalenceLevel.SIMILAR,
            adaptation_notes="",
        )
        assert similar.is_exact is False
