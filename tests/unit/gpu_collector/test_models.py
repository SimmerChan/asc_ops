# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
GPU 知识数据模型测试
"""

import pytest

from src.asc_ops.gpu_collector.models import (
    GPUPlatform,
    GPUKernelKnowledge,
    GPURepository,
    GPUAPIInfo,
    CrossPlatformMapping,
    MappingEquivalenceLevel,
    GPUKernelArchitecture,
    GPUKernelPerformance,
)


class TestGPUPlatform:
    """GPU 平台枚举测试"""

    def test_gpu_platform_values(self):
        """验证平台枚举值"""
        assert GPUPlatform.CUDA.value == "cuda"
        assert GPUPlatform.CUTLASS.value == "cutlass"
        assert GPUPlatform.CUBLAS.value == "cublas"
        assert GPUPlatform.CUDNN.value == "cudnn"

    def test_gpu_platform_count(self):
        """验证平台数量"""
        assert len(GPUPlatform) == 4


class TestMappingEquivalenceLevel:
    """映射等价级别枚举测试"""

    def test_equivalence_level_values(self):
        """验证等价级别枚举值"""
        assert MappingEquivalenceLevel.EXACT.value == "exact"
        assert MappingEquivalenceLevel.SIMILAR.value == "similar"
        assert MappingEquivalenceLevel.CONCEPTUAL_ONLY.value == "conceptual_only"

    def test_equivalence_level_count(self):
        """验证等价级别数量"""
        assert len(MappingEquivalenceLevel) == 3


class TestGPUKernelArchitecture:
    """GPU Kernel 架构信息测试"""

    def test_default_values(self):
        """默认架构值"""
        arch = GPUKernelArchitecture()

        assert arch.compute_capability == ""
        assert arch.warp_size == 32
        assert arch.max_threads_per_block == 1024
        assert arch.shared_memory_per_block == 49152
        assert arch.registers_per_thread == 255

    def test_custom_values(self):
        """自定义架构值"""
        arch = GPUKernelArchitecture(
            compute_capability="9.0",
            warp_size=64,
            max_threads_per_block=2048,
        )

        assert arch.compute_capability == "9.0"
        assert arch.warp_size == 64
        assert arch.max_threads_per_block == 2048


class TestGPUKernelPerformance:
    """GPU Kernel 性能特征测试"""

    def test_default_values(self):
        """默认性能特征"""
        perf = GPUKernelPerformance()

        assert perf.memory_pattern == ""
        assert perf.cache_usage == ""
        assert perf.occupancy is None

    def test_custom_values(self):
        """自定义性能特征"""
        perf = GPUKernelPerformance(
            memory_pattern="coalesced",
            cache_usage="shared",
            occupancy=0.75,
            estimated_flops=1000000000,
            memory_bandwidth_gbps=900,
        )

        assert perf.memory_pattern == "coalesced"
        assert perf.cache_usage == "shared"
        assert perf.occupancy == 0.75
        assert perf.estimated_flops == 1000000000


class TestGPUKernelKnowledge:
    """GPU Kernel 知识测试"""

    def test_kernel_creation(self):
        """创建 GPU Kernel 知识"""
        kernel = GPUKernelKnowledge(
            kernel_id="cutlass_16x64x128",
            kernel_name="cutlass_gemm",
            platform=GPUPlatform.CUTLASS,
            description="CUTLASS GEMM kernel",
            category="matmul",
        )

        assert kernel.kernel_id == "cutlass_16x64x128"
        assert kernel.kernel_name == "cutlass_gemm"
        assert kernel.platform == GPUPlatform.CUTLASS
        assert kernel.description == "CUTLASS GEMM kernel"
        assert kernel.category == "matmul"

    def test_kernel_with_architecture(self):
        """带架构信息的 GPU Kernel"""
        arch = GPUKernelArchitecture(
            compute_capability="8.0",
            warp_size=32,
        )
        kernel = GPUKernelKnowledge(
            kernel_id="cuda_matmul",
            kernel_name="wmma_matmul",
            platform=GPUPlatform.CUDA,
            architecture=arch,
        )

        assert kernel.architecture.compute_capability == "8.0"
        assert kernel.architecture.warp_size == 32

    def test_kernel_with_performance(self):
        """带性能特征的 GPU Kernel"""
        perf = GPUKernelPerformance(
            memory_pattern="tiled",
            occupancy=0.85,
        )
        kernel = GPUKernelKnowledge(
            kernel_id="cublas_gemm",
            kernel_name="gemm_ex",
            platform=GPUPlatform.CUBLAS,
            performance=perf,
        )

        assert kernel.performance.memory_pattern == "tiled"
        assert kernel.performance.occupancy == 0.85

    def test_kernel_with_template_parameters(self):
        """带模板参数的 GPU Kernel"""
        kernel = GPUKernelKnowledge(
            kernel_id="cutlass_template",
            kernel_name="cutlass_gemm_template",
            platform=GPUPlatform.CUTLASS,
            template_parameters=["ElementA", "ElementB", "ScalarC"],
        )

        assert len(kernel.template_parameters) == 3
        assert "ElementA" in kernel.template_parameters


class TestGPURepository:
    """GPU 代码仓库测试"""

    def test_repository_creation(self):
        """创建 GPU 仓库"""
        repo = GPURepository(
            repo_id="cutlass_main",
            repo_name="NVIDIA CUTLASS",
            platform=GPUPlatform.CUTLASS,
            clone_url="https://github.com/NVIDIA/cutlass.git",
            api_surface=["wmma::load_matrix_sync", "wmma::store_matrix_sync"],
        )

        assert repo.repo_id == "cutlass_main"
        assert repo.platform == GPUPlatform.CUTLASS
        assert len(repo.api_surface) == 2

    def test_repository_default_values(self):
        """仓库默认时间戳"""
        repo = GPURepository(
            repo_id="test_repo",
            repo_name="Test",
            platform=GPUPlatform.CUDA,
        )

        assert repo.created_at is not None
        assert repo.last_fetch_at is None


class TestGPUAPIInfo:
    """GPU API 信息测试"""

    def test_api_info_creation(self):
        """创建 GPU API 信息"""
        api = GPUAPIInfo(
            api_id="cuda_sync_threads",
            api_name="__syncthreads",
            platform=GPUPlatform.CUDA,
            full_signature="void __syncthreads()",
            description="Synchronize all threads in a block",
            category="sync",
            subcategory="barrier",
        )

        assert api.api_id == "cuda_sync_threads"
        assert api.api_name == "__syncthreads"
        assert api.full_signature == "void __syncthreads()"
        assert api.category == "sync"
        assert api.subcategory == "barrier"

    def test_api_info_with_parameters(self):
        """带参数的 GPU API"""
        api = GPUAPIInfo(
            api_id="wmma_load",
            api_name="wmma::load_matrix_sync",
            platform=GPUPlatform.CUDA,
            parameters=["fragment", "pointer", "ldm", "layout"],
            return_type="void",
        )

        assert len(api.parameters) == 4
        assert api.return_type == "void"


class TestCrossPlatformMapping:
    """跨平台映射测试"""

    def test_exact_mapping_creation(self):
        """创建精确映射"""
        mapping = CrossPlatformMapping(
            mapping_id="sync_threads_map",
            gpu_api="__syncthreads",
            npu_api="SyncAll",
            platform=GPUPlatform.CUDA,
            equivalence_level=MappingEquivalenceLevel.EXACT,
            adaptation_notes="无参数差异，直接替换",
            source="manual",
        )

        assert mapping.gpu_api == "__syncthreads"
        assert mapping.npu_api == "SyncAll"
        assert mapping.equivalence_level == MappingEquivalenceLevel.EXACT
        assert mapping.source == "manual"

    def test_similar_mapping_creation(self):
        """创建相似映射"""
        mapping = CrossPlatformMapping(
            mapping_id="wmma_load_map",
            gpu_api="wmma::load_matrix_sync",
            npu_api="Load2D",
            platform=GPUPlatform.CUDA,
            equivalence_level=MappingEquivalenceLevel.SIMILAR,
            adaptation_notes="需要适配 layout 参数",
            confidence=0.8,
        )

        assert mapping.equivalence_level == MappingEquivalenceLevel.SIMILAR
        assert mapping.confidence == 0.8

    def test_mapping_with_related(self):
        """带关联映射的映射"""
        mapping = CrossPlatformMapping(
            mapping_id="wmma_store_map",
            gpu_api="wmma::store_matrix_sync",
            npu_api="Store2D",
            platform=GPUPlatform.CUDA,
            equivalence_level=MappingEquivalenceLevel.SIMILAR,
            related_mappings=["wmma_load_map"],
        )

        assert len(mapping.related_mappings) == 1
        assert "wmma_load_map" in mapping.related_mappings

    def test_mapping_serialization(self):
        """映射可序列化"""
        mapping = CrossPlatformMapping(
            mapping_id="test_map",
            gpu_api="test_gpu_api",
            npu_api="test_npu_api",
            platform=GPUPlatform.CUTLASS,
            equivalence_level=MappingEquivalenceLevel.CONCEPTUAL_ONLY,
        )

        # 验证 dataclass 可以正常复制
        import copy
        mapping_copy = copy.deepcopy(mapping)
        assert mapping_copy.mapping_id == mapping.mapping_id
        assert mapping_copy.equivalence_level == mapping.equivalence_level
