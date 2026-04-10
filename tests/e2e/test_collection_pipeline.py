# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
采集管道集成测试

测试采集 → 存储 → 查询完整流程
"""

import pytest

from src.asc_ops.gpu_collector import (
    GPUStorage,
    GPUPlatform,
    GPUKernelKnowledge,
    GPUAPIInfo,
    CrossPlatformMapping,
    MappingEquivalenceLevel,
    CUTLASSCollector,
    cuBLASCollector,
    GPUKernelExtractor,
)


class TestCollectionPipeline:
    """采集管道测试"""

    def test_cutlass_collect_and_store(self, gpu_storage):
        """CUTLASS 采集并存储"""
        collector = CUTLASSCollector()

        # 采集
        source = """
        // CUTLASS GEMM kernel
        void cutlass_gemm_16x64x128(arguments) {}
        """
        kernels = collector.collect_from_content(source, "test.cuh")

        assert len(kernels) >= 1

        # 存储
        for kernel in kernels:
            result = gpu_storage.store_kernel(kernel)
            assert result is True

        # 验证
        retrieved = gpu_storage.get_kernel(kernels[0].kernel_id)
        assert retrieved is not None
        assert retrieved.kernel_name == kernels[0].kernel_name

    def test_cublas_collect_and_store(self, gpu_storage):
        """cuBLAS 采集并存储"""
        collector = cuBLASCollector()

        # 采集
        docs_content = "cublasSgemm API documentation"
        apis = collector.collect_from_documentation(docs_content)

        assert len(apis) >= 1

        # 存储
        for api in apis:
            result = gpu_storage.store_api(api)
            assert result is True

    def test_kernel_extraction_pipeline(self, gpu_storage):
        """Kernel 提取管道"""
        extractor = GPUKernelExtractor()

        source = """
        // GEMM kernel
        void cutlass_gemm_16x64x128(args) {
            // implementation
        }

        // Conv kernel
        void cutlass_conv2d_fprop(args) {}
        """

        # 提取
        kernels = extractor.extract_from_source(
            source_code=source,
            platform=GPUPlatform.CUTLASS,
            source_file="test.cuh",
        )

        assert len(kernels) >= 1

        # 存储
        for kernel in kernels:
            gpu_storage.store_kernel(kernel)

        # 统计
        stats = gpu_storage.get_stats()
        assert stats["kernels"] >= 1

    def test_storage_stats(self, gpu_storage):
        """存储统计"""
        # 添加数据
        kernel = GPUKernelKnowledge(
            kernel_id="test_k1",
            kernel_name="test_kernel",
            platform=GPUPlatform.CUTLASS,
        )
        gpu_storage.store_kernel(kernel)

        api = GPUAPIInfo(
            api_id="test_a1",
            api_name="test_api",
            platform=GPUPlatform.CUDA,
        )
        gpu_storage.store_api(api)

        mapping = CrossPlatformMapping(
            mapping_id="test_m1",
            gpu_api="test_gpu",
            npu_api="test_npu",
            platform=GPUPlatform.CUDA,
            equivalence_level=MappingEquivalenceLevel.EXACT,
        )
        gpu_storage.store_mapping(mapping)

        stats = gpu_storage.get_stats()

        assert stats["kernels"] >= 1
        assert stats["apis"] >= 1
        assert stats["mappings"] >= 1


class TestQueryPipeline:
    """查询管道测试"""

    def test_kernel_search(self, gpu_storage):
        """Kernel 搜索"""
        # 添加测试数据
        kernel = GPUKernelKnowledge(
            kernel_id="gemm_kernel_1",
            kernel_name="cutlass_gemm",
            platform=GPUPlatform.CUTLASS,
            description="GEMM kernel for matrix multiplication",
        )
        gpu_storage.store_kernel(kernel)

        # 搜索
        results = gpu_storage.search_kernels("gemm")

        assert len(results) >= 1
        assert any("gemm" in k.kernel_name.lower() for k in results)

    def test_api_search(self, gpu_storage):
        """API 搜索"""
        # 添加测试数据
        api = GPUAPIInfo(
            api_id="sync_api_1",
            api_name="__syncthreads",
            platform=GPUPlatform.CUDA,
            description="Synchronize threads in a block",
        )
        gpu_storage.store_api(api)

        # 搜索
        results = gpu_storage.search_apis("syncthreads")

        assert len(results) >= 1

    def test_mapping_lookup(self, gpu_storage):
        """映射查找"""
        # 添加测试数据
        mapping = CrossPlatformMapping(
            mapping_id="sync_map",
            gpu_api="__syncthreads",
            npu_api="SyncAll",
            platform=GPUPlatform.CUDA,
            equivalence_level=MappingEquivalenceLevel.EXACT,
        )
        gpu_storage.store_mapping(mapping)

        # 查找
        result = gpu_storage.get_mapping("__syncthreads")

        assert result is not None
        assert result.npu_api == "SyncAll"
