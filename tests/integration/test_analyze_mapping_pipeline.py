# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
GPU-NPU 等价分析集成测试

测试 CLI → GPUNPUAnalysisEngine → GPUStorage 完整链路
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from src.asc_ops.mapper.llm_analyzer import GPUNPUAnalysisEngine, FilePairAnalysis, AnalysisResult
from src.asc_ops.gpu_collector.models import GPUPlatform, MappingEquivalenceLevel
from src.asc_ops.gpu_collector.storage import GPUStorage


class TestAnalyzeMappingPipeline:
    """分析链路集成测试"""

    @pytest.fixture
    def temp_repos(self, tmp_path):
        """创建临时 GPU 和 NPU 仓库"""
        gpu_repo = tmp_path / "gpu_repo"
        npu_repo = tmp_path / "npu_repo"
        gpu_repo.mkdir()
        npu_repo.mkdir()

        # 创建 GPU 代码文件
        (gpu_repo / "cublas_sgemm.cu").write_text("""
void cublasSgemm(cublasHandle_t handle, int m, int n, int k,
                 const float* A, const float* B, float* C) {
    float alpha = 1.0f;
    float beta = 0.0f;
    cublasSgemm_v2(handle, CUBLAS_OP_N, CUBLAS_OP_N,
                   m, n, k, &alpha, A, m, B, k, &beta, C, m);
}
""")

        # 创建 NPU 代码文件
        (npu_repo / "matmul.cpp").write_text("""
void Matmul(int m, int n, int k,
            const float* a, const float* b, float* c) {
    // AscendC Matmul implementation
    MatmulKernel<<<...>>>(a, b, c, m, n, k);
}
""")

        return {"gpu_repo": gpu_repo, "npu_repo": npu_repo}

    @pytest.fixture
    def mock_llm_response(self):
        """Mock LLM 响应"""
        from src.asc_ops.llm.responses import LLMResponse

        return LLMResponse(
            content=json.dumps({
                "is_equivalent": True,
                "npu_equivalent": "Matmul",
                "equivalence_level": "exact",
                "confidence": 0.92,
                "adaptation_notes": "Direct replacement",
                "optimization_hints": "tensor_core",
            }),
            model="claude",
            provider="anthropic",
        )

    @pytest.mark.asyncio
    async def test_analyze_file_pair_integration(
        self, temp_repos, mock_llm_response
    ):
        """测试完整分析链路"""
        # 创建 mock LLM 客户端
        mock_client = AsyncMock()
        mock_client.chat.return_value = mock_llm_response

        # 创建存储
        storage = GPUStorage(use_mock=True)

        # 创建分析引擎
        engine = GPUNPUAnalysisEngine(
            llm_client=mock_client,
            storage=storage,
        )

        # 执行分析
        gpu_file = temp_repos["gpu_repo"] / "cublas_sgemm.cu"
        npu_file = temp_repos["npu_repo"] / "matmul.cpp"

        result = await engine.analyze_file_pair(
            gpu_file=gpu_file,
            npu_file=npu_file,
            gpu_platform=GPUPlatform.CUBLAS,
        )

        # 验证分析结果
        assert result.gpu_api == "CUBLAS_SGEMM"
        assert result.gpu_platform == GPUPlatform.CUBLAS
        assert result.result.is_equivalent is True
        assert result.result.npu_equivalent == "Matmul"
        assert result.result.confidence == 0.92
        assert result.result.equivalence_level == MappingEquivalenceLevel.EXACT
        assert result.parsing_failed is False

        # 验证存储
        stored = engine.store_analysis_result(result, dry_run=False)
        assert stored is True

        # 验证存储查询
        mappings = storage.search_cross_platform_mappings("cublas")
        assert len(mappings) == 1
        assert mappings[0].npu_api == "Matmul"
        assert mappings[0].equivalence_level == MappingEquivalenceLevel.EXACT

    @pytest.mark.asyncio
    async def test_analyze_multiple_pairs_integration(self, tmp_path):
        """测试批量分析链路"""
        # 创建 mock LLM 客户端
        mock_client = AsyncMock()
        mock_client.chat.return_value = LLMResponse(
            content=json.dumps({
                "is_equivalent": True,
                "npu_equivalent": "Matmul",
                "equivalence_level": "exact",
                "confidence": 0.9,
                "adaptation_notes": "",
                "optimization_hints": "tensor_core",
            }),
            model="claude",
            provider="anthropic",
        )

        storage = GPUStorage(use_mock=True)
        engine = GPUNPUAnalysisEngine(
            llm_client=mock_client,
            storage=storage,
        )

        # 创建多对文件
        gpu_repo = tmp_path / "gpu"
        npu_repo = tmp_path / "npu"
        gpu_repo.mkdir()
        npu_repo.mkdir()

        file_pairs = []
        for i in range(3):
            gpu_file = gpu_repo / f"gemm_{i}.cu"
            npu_file = npu_repo / f"gemm_{i}.cpp"
            gpu_file.write_text(f"void gemm_{i}() {{ }}")
            npu_file.write_text(f"void gemm_{i}() {{ }}")
            file_pairs.append((gpu_file, npu_file))

        # 批量分析
        results = await engine.analyze_multiple_pairs(file_pairs)

        assert len(results) == 3
        for r in results:
            assert r.result.is_equivalent is True

        # 批量存储
        success, failed = engine.store_analysis_results(results, dry_run=False)
        assert success == 3
        assert failed == 0

        # 验证
        mappings = storage.search_cross_platform_mappings("gemm")
        assert len(mappings) == 3

    def test_store_analysis_with_platform(self):
        """测试不同平台的存储"""
        storage = GPUStorage(use_mock=True)
        engine = GPUNPUAnalysisEngine(llm_client=None, storage=storage)

        # CUTLASS 平台
        analysis = FilePairAnalysis(
            gpu_file="/path/to/cutlass_gemm.cu",
            npu_file="/path/to/npu_gemm.cpp",
            gpu_api="CUTLASS_GEMM",
            gpu_platform=GPUPlatform.CUTLASS,
            result=AnalysisResult(
                is_equivalent=True,
                npu_equivalent="Matmul",
                equivalence_level=MappingEquivalenceLevel.EXACT,
                confidence=0.95,
                adaptation_notes="",
                optimization_hints="tensor_core",
            ),
        )

        success = engine.store_analysis_result(analysis, dry_run=False)
        assert success is True

        mappings = storage.search_cross_platform_mappings("cutlass")
        assert len(mappings) == 1
        assert mappings[0].platform == GPUPlatform.CUTLASS

    def test_dry_run_mode(self):
        """测试 dry-run 模式不存储"""
        storage = GPUStorage(use_mock=True)
        engine = GPUNPUAnalysisEngine(llm_client=None, storage=storage)

        analysis = FilePairAnalysis(
            gpu_file="/path/to/test.cu",
            npu_file="/path/to/test.cpp",
            gpu_api="TEST",
            gpu_platform=GPUPlatform.CUDA,
            result=AnalysisResult(
                is_equivalent=True,
                npu_equivalent="Test",
                equivalence_level=MappingEquivalenceLevel.EXACT,
                confidence=0.9,
                adaptation_notes="",
                optimization_hints="none",
            ),
        )

        # dry-run
        result = engine.store_analysis_result(analysis, dry_run=True)
        assert result is True

        # 验证没有存储
        mappings = storage.search_cross_platform_mappings("test")
        assert len(mappings) == 0

    def test_confidence_based_source(self):
        """测试置信度分流"""
        storage = GPUStorage(use_mock=True)
        engine = GPUNPUAnalysisEngine(llm_client=None, storage=storage)

        # 高置信度 >= 0.8
        high_conf_analysis = FilePairAnalysis(
            gpu_file="/path/to/high.cu",
            npu_file="/path/to/high.cpp",
            gpu_api="HIGH_CONF",
            gpu_platform=GPUPlatform.CUDA,
            result=AnalysisResult(
                is_equivalent=True,
                npu_equivalent="Matmul",
                equivalence_level=MappingEquivalenceLevel.EXACT,
                confidence=0.9,
                adaptation_notes="",
                optimization_hints="none",
            ),
        )

        success = engine.store_analysis_result(high_conf_analysis, dry_run=False)
        assert success is True

        # 低置信度 < 0.8
        low_conf_analysis = FilePairAnalysis(
            gpu_file="/path/to/low.cu",
            npu_file="/path/to/low.cpp",
            gpu_api="LOW_CONF",
            gpu_platform=GPUPlatform.CUDA,
            result=AnalysisResult(
                is_equivalent=True,
                npu_equivalent="Matmul",
                equivalence_level=MappingEquivalenceLevel.SIMILAR,
                confidence=0.6,
                adaptation_notes="",
                optimization_hints="none",
            ),
        )

        success = engine.store_analysis_result(low_conf_analysis, dry_run=False)
        assert success is True

        # 验证存储
        mappings = storage.search_cross_platform_mappings("conf")
        assert len(mappings) == 2


# 需要导入 LLMResponse
from src.asc_ops.llm.responses import LLMResponse
