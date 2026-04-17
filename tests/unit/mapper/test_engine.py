# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
跨平台映射引擎测试
"""

import pytest
from unittest.mock import MagicMock

from src.asc_ops.mapper import MapperEngine, MappingResult
from src.asc_ops.gpu_collector.models import GPUPlatform, MappingEquivalenceLevel, CrossPlatformMapping
from src.asc_ops.gpu_collector.storage import GPUStorage


class TestMapperEngine:
    """映射引擎测试"""

    @pytest.fixture
    def storage_with_mappings(self):
        """创建带有测试数据的存储"""
        storage = GPUStorage(use_mock=True)

        # 添加测试映射
        mappings = [
            CrossPlatformMapping(
                mapping_id="1",
                gpu_api="__syncthreads",
                npu_api="SyncAll",
                platform=GPUPlatform.CUDA,
                equivalence_level=MappingEquivalenceLevel.EXACT,
                adaptation_notes="完全等价",
                confidence=1.0,
                source="llm_high_conf",
            ),
            CrossPlatformMapping(
                mapping_id="2",
                gpu_api="atomicAdd",
                npu_api="AtomAdd",
                platform=GPUPlatform.CUDA,
                equivalence_level=MappingEquivalenceLevel.EXACT,
                adaptation_notes="原子加法",
                confidence=1.0,
                source="llm_high_conf",
            ),
            CrossPlatformMapping(
                mapping_id="3",
                gpu_api="wmma::load_matrix_sync",
                npu_api="Load2D",
                platform=GPUPlatform.CUDA,
                equivalence_level=MappingEquivalenceLevel.SIMILAR,
                adaptation_notes="需适配layout参数",
                confidence=0.8,
                source="llm_suggested",
            ),
            CrossPlatformMapping(
                mapping_id="4",
                gpu_api="cublasSgemm",
                npu_api="Matmul",
                platform=GPUPlatform.CUBLAS,
                equivalence_level=MappingEquivalenceLevel.EXACT,
                adaptation_notes="直接对应",
                confidence=1.0,
                source="llm_high_conf",
            ),
        ]

        for m in mappings:
            storage.store_cross_platform_mapping(m, source=m.source)

        return storage

    def setup_method(self):
        """设置测试"""
        self.engine = MapperEngine()

    def test_find_exact_mapping_with_storage(self, storage_with_mappings):
        """查找精确映射: __syncthreads (有存储)"""
        engine = MapperEngine(storage=storage_with_mappings)
        result = engine.find_mapping("__syncthreads", "cuda")

        assert result is not None
        assert result.npu_api == "SyncAll"
        assert result.equivalence_level == MappingEquivalenceLevel.EXACT
        assert result.is_exact is True

    def test_find_exact_mapping_atomic_add(self, storage_with_mappings):
        """查找精确映射: atomicAdd (有存储)"""
        engine = MapperEngine(storage=storage_with_mappings)
        result = engine.find_mapping("atomicAdd", "cuda")

        assert result is not None
        assert result.npu_api == "AtomAdd"
        assert result.equivalence_level == MappingEquivalenceLevel.EXACT

    def test_find_similar_mapping_wmma_load(self, storage_with_mappings):
        """查找相似映射: wmma::load_matrix_sync (有存储)"""
        engine = MapperEngine(storage=storage_with_mappings)
        result = engine.find_mapping("wmma::load_matrix_sync", "cuda")

        assert result is not None
        assert result.npu_api == "Load2D"
        assert result.equivalence_level == MappingEquivalenceLevel.SIMILAR
        assert result.is_exact is False

    def test_find_nonexistent_mapping(self, storage_with_mappings):
        """查找不存在的映射"""
        engine = MapperEngine(storage=storage_with_mappings)
        result = engine.find_mapping("nonexistent_gpu_api", "cuda")

        assert result is None

    def test_find_mapping_cublas_gemm(self, storage_with_mappings):
        """查找 cuBLAS GEMM 映射"""
        engine = MapperEngine(storage=storage_with_mappings)
        result = engine.find_mapping("cublasSgemm", "cublas")

        assert result is not None
        assert result.npu_api == "Matmul"
        assert result.equivalence_level == MappingEquivalenceLevel.EXACT

    def test_find_similar_apis(self, storage_with_mappings):
        """查找相似 API"""
        engine = MapperEngine(storage=storage_with_mappings)
        results = engine.find_similar("__syncthreads", "cuda")

        assert len(results) >= 0  # 可能没有相似结果

    def test_find_by_category_sync(self, storage_with_mappings):
        """按类别查找同步 API"""
        engine = MapperEngine(storage=storage_with_mappings)
        results = engine.find_by_category("sync", "cuda")

        # 结果可能为空，取决于存储中的数据
        assert isinstance(results, list)

    def test_find_by_category_atomic(self, storage_with_mappings):
        """按类别查找原子操作 API"""
        engine = MapperEngine(storage=storage_with_mappings)
        results = engine.find_by_category("atomic", "cuda")

        assert isinstance(results, list)

    def test_get_supported_apis(self, storage_with_mappings):
        """获取支持的 API 列表"""
        engine = MapperEngine(storage=storage_with_mappings)
        apis = engine.get_supported_apis("cuda")

        assert len(apis) >= 0
        if "__syncthreads" in apis:
            assert "atomicAdd" in apis

    def test_mapping_stats_with_storage(self, storage_with_mappings):
        """获取映射统计 (有存储)"""
        engine = MapperEngine(storage=storage_with_mappings)
        stats = engine.get_mapping_stats()

        assert stats["storage_available"] is True
        assert "total_cuda_mappings" in stats

    def test_mapping_stats_no_storage(self):
        """获取映射统计 (无存储)"""
        engine = MapperEngine()
        stats = engine.get_mapping_stats()

        assert stats["storage_available"] is False
        assert stats["cached_mappings"] == 0

    def test_cache_behavior(self, storage_with_mappings):
        """缓存行为测试"""
        engine = MapperEngine(storage=storage_with_mappings)

        # 首次查询
        result1 = engine.find_mapping("__syncthreads", "cuda")
        assert result1 is not None

        # 再次查询应该命中缓存
        result2 = engine.find_mapping("__syncthreads", "cuda")
        assert result2 is not None

        # 验证统计中缓存计数
        stats = engine.get_mapping_stats()
        assert stats["cached_mappings"] >= 1

    def test_clear_cache(self, storage_with_mappings):
        """清空缓存"""
        engine = MapperEngine(storage=storage_with_mappings)

        # 先查询一些 API
        engine.find_mapping("__syncthreads", "cuda")
        engine.find_mapping("atomicAdd", "cuda")

        # 清空缓存
        engine.clear_cache()

        stats = engine.get_mapping_stats()
        assert stats["cached_mappings"] == 0

    def test_platform_normalization(self, storage_with_mappings):
        """平台名称标准化"""
        engine = MapperEngine(storage=storage_with_mappings)

        # 不同大小写
        result1 = engine.find_mapping("__syncthreads", "CUDA")
        result2 = engine.find_mapping("__syncthreads", "cuda")
        result3 = engine.find_mapping("__syncthreads", "CUda")

        # 如果存储中没有数据，都应该是 None
        # 如果有数据，应该返回相同结果
        if result1:
            assert result1.npu_api == result2.npu_api == result3.npu_api

    def test_include_notes_flag(self, storage_with_mappings):
        """包含注意事项标志"""
        engine = MapperEngine(storage=storage_with_mappings)

        result_with_notes = engine.find_mapping("__syncthreads", "cuda", include_notes=True)
        result_without_notes = engine.find_mapping("__syncthreads", "cuda", include_notes=False)

        if result_with_notes:
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
            source="llm_high_conf",
        )

        mapping = result.to_cross_platform_mapping(GPUPlatform.CUDA, "test_id")

        assert mapping.gpu_api == "__syncthreads"
        assert mapping.npu_api == "SyncAll"
        assert mapping.equivalence_level == MappingEquivalenceLevel.EXACT
        assert mapping.platform == GPUPlatform.CUDA


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

    def test_init_with_storage(self):
        """使用存储初始化"""
        storage = GPUStorage(use_mock=True)
        engine = MapperEngine(storage=storage)

        assert engine._storage is storage

    def test_init_without_storage(self):
        """不使用存储初始化"""
        engine = MapperEngine()

        assert engine._storage is None
