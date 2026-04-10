# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
GPU 采集器测试
"""

import pytest

from src.asc_ops.gpu_collector import (
    GPUPlatform,
    GPUKernelKnowledge,
    GPUAPIInfo,
    CrossPlatformMapping,
    MappingEquivalenceLevel,
    GPUKernelExtractor,
    GPUAPIExtractor,
    CrossPlatformMappingExtractor,
    GPUStorage,
    CUTLASSCollector,
    cuBLASCollector,
)


class TestGPUKernelExtractor:
    """GPU Kernel 提取器测试"""

    def setup_method(self):
        """设置测试"""
        self.extractor = GPUKernelExtractor()

    def test_extract_kernel_names(self):
        """提取 kernel 名称"""
        source = """
        // CUTLASS kernel for GEMM
        cutlass_gemm_16x64x128<<<grid, block>>>(args...);
        void cutlass_conv2d_fprop(args);
        """

        names = self.extractor._extract_kernel_names(source)
        assert len(names) >= 1

    def test_extract_from_source(self):
        """从源代码提取 kernel"""
        source = """
        // CUTLASS GEMM kernel
        void cutlass_gemm_16x64x128(args) {
            // kernel implementation
        }
        """

        results = self.extractor.extract_from_source(
            source_code=source,
            platform=GPUPlatform.CUTLASS,
            source_file="test.cuh",
        )

        assert len(results) >= 1
        assert results[0].platform == GPUPlatform.CUTLASS

    def test_extract_template_params(self):
        """提取模板参数"""
        source = """
        template <typename ElementA, typename ElementB, typename ElementC>
        void cutlass_gemm_kernel(args) {}
        """

        params = self.extractor._extract_template_params(source)
        assert len(params) > 0


class TestGPUAPIExtractor:
    """GPU API 提取器测试"""

    def setup_method(self):
        """设置测试"""
        self.extractor = GPUAPIExtractor()

    def test_extract_api_signatures(self):
        """提取 API 签名"""
        source = """
        void __syncthreads();
        int wmma::load_matrix_sync(fragment &frag, pointer ptr, int ldm);
        """

        results = self.extractor.extract_from_source(
            source_code=source,
            platform=GPUPlatform.CUDA,
        )

        assert len(results) >= 1
        api_names = [r.api_name for r in results]
        assert "__syncthreads" in api_names or "load_matrix_sync" in api_names

    def test_parse_parameters(self):
        """解析参数列表"""
        params_str = "int m, int n, const float *alpha, const float *A"
        params = self.extractor._parse_parameters(params_str)

        assert len(params) == 4
        assert "m" in params
        assert "n" in params


class TestCrossPlatformMappingExtractor:
    """跨平台映射提取器测试"""

    def setup_method(self):
        """设置测试"""
        self.extractor = CrossPlatformMappingExtractor()

    def test_add_predefined_mapping(self):
        """添加预定义映射"""
        self.extractor.add_predefined_mapping(
            gpu_api="__syncthreads",
            npu_api="SyncAll",
            platform=GPUPlatform.CUDA,
            equivalence_level="exact",
            notes="无参数差异",
        )

        mapping = self.extractor.find_mapping("__syncthreads")
        assert mapping is not None
        assert mapping.npu_api == "SyncAll"
        assert mapping.equivalence_level == MappingEquivalenceLevel.EXACT

    def test_find_nonexistent_mapping(self):
        """查找不存在的映射"""
        mapping = self.extractor.find_mapping("nonexistent_api")
        assert mapping is None

    def test_get_all_mappings(self):
        """获取所有映射"""
        self.extractor.add_predefined_mapping(
            gpu_api="test_api_1",
            npu_api="npu_api_1",
            platform=GPUPlatform.CUDA,
            equivalence_level="exact",
        )
        self.extractor.add_predefined_mapping(
            gpu_api="test_api_2",
            npu_api="npu_api_2",
            platform=GPUPlatform.CUTLASS,
            equivalence_level="similar",
        )

        all_mappings = self.extractor.get_all_mappings()
        assert len(all_mappings) >= 2


class TestGPUStorage:
    """GPU 存储测试"""

    def setup_method(self):
        """设置测试"""
        self.storage = GPUStorage(use_mock=True)

    def test_store_kernel(self):
        """存储 kernel"""
        kernel = GPUKernelKnowledge(
            kernel_id="test_kernel_1",
            kernel_name="cutlass_gemm",
            platform=GPUPlatform.CUTLASS,
            description="Test kernel",
        )

        result = self.storage.store_kernel(kernel)
        assert result is True

        retrieved = self.storage.get_kernel("test_kernel_1")
        assert retrieved is not None
        assert retrieved.kernel_name == "cutlass_gemm"

    def test_store_api(self):
        """存储 API"""
        api = GPUAPIInfo(
            api_id="test_api_1",
            api_name="__syncthreads",
            platform=GPUPlatform.CUDA,
            full_signature="void __syncthreads()",
            description="Synchronize threads",
        )

        result = self.storage.store_api(api)
        assert result is True

        retrieved = self.storage.get_api("test_api_1")
        assert retrieved is not None
        assert retrieved.api_name == "__syncthreads"

    def test_store_mapping(self):
        """存储映射"""
        mapping = CrossPlatformMapping(
            mapping_id="test_map_1",
            gpu_api="__syncthreads",
            npu_api="SyncAll",
            platform=GPUPlatform.CUDA,
            equivalence_level=MappingEquivalenceLevel.EXACT,
        )

        result = self.storage.store_mapping(mapping)
        assert result is True

        retrieved = self.storage.get_mapping("__syncthreads")
        assert retrieved is not None
        assert retrieved.npu_api == "SyncAll"

    def test_search_kernels(self):
        """搜索 kernels"""
        # 存储多个 kernels
        for i in range(3):
            kernel = GPUKernelKnowledge(
                kernel_id=f"gemm_kernel_{i}",
                kernel_name=f"cutlass_gemm_{i}",
                platform=GPUPlatform.CUTLASS,
                description=f"GEMM kernel {i}",
            )
            self.storage.store_kernel(kernel)

        results = self.storage.search_kernels("gemm")
        assert len(results) >= 3

    def test_get_stats(self):
        """获取统计信息"""
        self.storage.store_kernel(GPUKernelKnowledge(
            kernel_id="k1",
            kernel_name="k1",
            platform=GPUPlatform.CUTLASS,
        ))
        self.storage.store_api(GPUAPIInfo(
            api_id="a1",
            api_name="a1",
            platform=GPUPlatform.CUDA,
        ))

        stats = self.storage.get_stats()
        assert stats["kernels"] >= 1
        assert stats["apis"] >= 1


class TestCUTLASSCollector:
    """CUTLASS 采集器测试"""

    def setup_method(self):
        """设置测试"""
        self.collector = CUTLASSCollector()

    def test_collect_from_content(self):
        """从内容采集"""
        source = """
        // CUTLASS GEMM kernel
        void cutlass_gemm_16x64x128(args) {}
        """

        kernels = self.collector.collect_from_content(
            content=source,
            source_file="test.cuh",
        )

        assert len(kernels) >= 1

    def test_create_repository_info(self):
        """创建仓库信息"""
        repo = self.collector.create_repository_info()

        assert repo.repo_name == "NVIDIA CUTLASS"
        assert repo.platform == GPUPlatform.CUTLASS
        assert len(repo.api_surface) > 0

    def test_extract_kernel_signature(self):
        """提取 kernel 签名"""
        source = """
        template <typename ElementA, typename ElementB>
        void cutlass_gemm_kernel(arguments) {}
        """

        sig = self.collector.extract_kernel_signature(source, "cutlass_gemm_kernel")
        assert sig is not None
        assert "cutlass_gemm_kernel" in sig


class TestCUBLASCollector:
    """cuBLAS 采集器测试"""

    def setup_method(self):
        """设置测试"""
        self.collector = cuBLASCollector()

    def test_collect_core_apis(self):
        """采集核心 APIs"""
        docs_content = """
        cublasSgemm: Single precision GEMM
        cublasDgemm: Double precision GEMM
        """

        apis = self.collector.collect_from_documentation(docs_content)

        assert len(apis) >= 1
        api_names = [a.api_name for a in apis]
        assert "cublasSgemm" in api_names

    def test_categorize_api(self):
        """API 分类"""
        category, subcategory = self.collector._categorize_api("cublasSgemm")
        assert category == "compute"

        category, subcategory = self.collector._categorize_api("cublasSetVector")
        assert category == "memory"

    def test_create_repository_info(self):
        """创建仓库信息"""
        repo = self.collector.create_repository_info()

        assert repo.repo_name == "NVIDIA cuBLAS"
        assert repo.platform == GPUPlatform.CUBLAS
        assert len(repo.api_surface) > 0
