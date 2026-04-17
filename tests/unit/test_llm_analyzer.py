# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
GPUNPUAnalysisEngine 单元测试
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from src.asc_ops.mapper.llm_analyzer import (
    GPUNPUAnalysisEngine,
    AnalysisResult,
    FilePairAnalysis,
    ANALYSIS_PROMPT_TEMPLATE,
)
from src.asc_ops.gpu_collector.models import (
    GPUPlatform,
    MappingEquivalenceLevel,
    CrossPlatformMapping,
)
from src.asc_ops.gpu_collector.storage import GPUStorage


class TestGPUNPUAnalysisEngine:
    """GPUNPUAnalysisEngine 测试"""

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM 客户端"""
        client = AsyncMock()
        client.chat = AsyncMock()
        return client

    @pytest.fixture
    def mock_storage(self):
        """Mock GPU 存储"""
        return GPUStorage(use_mock=True)

    @pytest.fixture
    def engine(self, mock_llm_client, mock_storage):
        """创建分析引擎"""
        return GPUNPUAnalysisEngine(
            llm_client=mock_llm_client,
            storage=mock_storage,
            max_retries=3,
            max_tokens_per_pair=2000,
            max_pairs_per_call=50,
            temperature=0.1,
        )

    def test_init(self, engine):
        """测试初始化"""
        assert engine._max_retries == 3
        assert engine._max_tokens_per_pair == 2000
        assert engine._max_pairs_per_call == 50
        assert engine._temperature == 0.1

    def test_infer_gpu_api(self, engine):
        """测试 GPU API 推断"""
        # 从文件名推断
        assert engine._infer_gpu_api("", "cublas_sgemm.cu") == "CUBLAS_SGEMM"
        assert engine._infer_gpu_api("", "wmma_mma_kernel.cu") == "WMMA_MMA"
        assert engine._infer_gpu_api("", "gemm_op.cu") == "GEMM"

    def test_build_analysis_prompt(self, engine):
        """测试 Prompt 构建"""
        gpu_code = "void mykernel() { }"
        npu_code = "void mykernel() { }"

        prompt = engine._build_analysis_prompt(
            gpu_code=gpu_code,
            npu_code=npu_code,
            gpu_platform=GPUPlatform.CUDA,
        )

        assert "CUDA" in prompt
        assert gpu_code in prompt
        assert npu_code in prompt
        assert "is_equivalent" in prompt
        assert "confidence" in prompt

    def test_parse_analysis_result(self, engine):
        """测试结果解析"""
        data = {
            "is_equivalent": True,
            "npu_equivalent": "Matmul",
            "equivalence_level": "exact",
            "confidence": 0.95,
            "adaptation_notes": "Direct replacement",
            "optimization_hints": "tensor_core",
        }

        result = engine._parse_analysis_result(data)

        assert result.is_equivalent is True
        assert result.npu_equivalent == "Matmul"
        assert result.equivalence_level == MappingEquivalenceLevel.EXACT
        assert result.confidence == 0.95
        assert result.parsing_failed is False

    def test_parse_analysis_result_similar(self, engine):
        """测试相似映射解析"""
        data = {
            "is_equivalent": True,
            "npu_equivalent": "VecShuffle",
            "equivalence_level": "similar",
            "confidence": 0.7,
            "adaptation_notes": "Different parameter order",
            "optimization_hints": "warp",
        }

        result = engine._parse_analysis_result(data)

        assert result.is_equivalent is True
        assert result.npu_equivalent == "VecShuffle"
        assert result.equivalence_level == MappingEquivalenceLevel.SIMILAR
        assert result.confidence == 0.7

    def test_parse_analysis_result_parsing_failed(self, engine):
        """测试解析失败处理"""
        data = {
            "is_equivalent": False,
            # 缺少必要字段
        }

        result = engine._parse_analysis_result(data)

        assert result.npu_equivalent == "N/A"
        assert result.confidence == 0.0
        assert result.parsing_failed is False  # JSON 解析成功了

    @pytest.mark.asyncio
    async def test_analyze_file_pair_no_llm(self, tmp_path):
        """测试无 LLM 客户端时的处理"""
        engine = GPUNPUAnalysisEngine(llm_client=None, storage=None)

        # 创建临时文件
        gpu_file = tmp_path / "test_gpu.cu"
        gpu_file.write_text("void gpu_func() { }")

        npu_file = tmp_path / "test_npu.cpp"
        npu_file.write_text("void npu_func() { }")

        result = await engine.analyze_file_pair(gpu_file, npu_file)

        assert result.parsing_failed is True
        assert result.result.parsing_failed is True

    @pytest.mark.asyncio
    async def test_analyze_file_pair_success(self, engine, mock_llm_client, tmp_path):
        """测试成功分析"""
        from src.asc_ops.llm.responses import LLMResponse

        # 设置 mock 响应
        mock_response = LLMResponse(
            content=json.dumps({
                "is_equivalent": True,
                "npu_equivalent": "Matmul",
                "equivalence_level": "exact",
                "confidence": 0.95,
                "adaptation_notes": "Direct replacement",
                "optimization_hints": "tensor_core",
            }),
            model="claude",
            provider="anthropic",
        )
        mock_llm_client.chat.return_value = mock_response

        # 创建临时文件
        gpu_file = tmp_path / "cublas_sgemm.cu"
        gpu_file.write_text("void cublasSgemm() { }")

        npu_file = tmp_path / "matmul.cpp"
        npu_file.write_text("void Matmul() { }")

        result = await engine.analyze_file_pair(gpu_file, npu_file)

        assert result.gpu_api == "CUBLAS_SGEMM"
        assert result.result.is_equivalent is True
        assert result.result.npu_equivalent == "Matmul"
        assert result.result.confidence == 0.95
        assert result.parsing_failed is False

    @pytest.mark.asyncio
    async def test_analyze_file_pair_json_error(self, engine, mock_llm_client, tmp_path):
        """测试 JSON 解析错误重试"""
        from src.asc_ops.llm.responses import LLMResponse

        # 第一次返回无效 JSON，第二次返回有效 JSON
        mock_llm_client.chat.side_effect = [
            LLMResponse(content="invalid json", model="claude", provider="anthropic"),
            LLMResponse(content=json.dumps({
                "is_equivalent": True,
                "npu_equivalent": "Matmul",
                "equivalence_level": "exact",
                "confidence": 0.9,
                "adaptation_notes": "",
                "optimization_hints": "none",
            }), model="claude", provider="anthropic"),
        ]

        # 创建临时文件
        gpu_file = tmp_path / "test.cu"
        gpu_file.write_text("void test() { }")

        npu_file = tmp_path / "test.cpp"
        npu_file.write_text("void test() { }")

        result = await engine.analyze_file_pair(gpu_file, npu_file)

        assert result.result.is_equivalent is True
        assert mock_llm_client.chat.call_count == 2

    @pytest.mark.asyncio
    async def test_analyze_multiple_pairs(self, engine, mock_llm_client, tmp_path):
        """测试批量分析"""
        from src.asc_ops.llm.responses import LLMResponse

        mock_response = LLMResponse(content=json.dumps({
            "is_equivalent": True,
            "npu_equivalent": "Matmul",
            "equivalence_level": "exact",
            "confidence": 0.9,
            "adaptation_notes": "",
            "optimization_hints": "none",
        }), model="claude", provider="anthropic")
        mock_llm_client.chat.return_value = mock_response

        # 创建多对文件
        file_pairs = []
        for i in range(3):
            gpu_file = tmp_path / f"test_{i}.cu"
            gpu_file.write_text(f"void test{i}() {{ }}")
            npu_file = tmp_path / f"test_{i}.cpp"
            npu_file.write_text(f"void test{i}() {{ }}")
            file_pairs.append((gpu_file, npu_file))

        results = await engine.analyze_multiple_pairs(file_pairs)

        assert len(results) == 3
        for result in results:
            assert result.result.is_equivalent is True


class TestAnalysisResult:
    """AnalysisResult 测试"""

    def test_to_cross_platform_mapping(self):
        """测试转换为 CrossPlatformMapping"""
        result = AnalysisResult(
            is_equivalent=True,
            npu_equivalent="Matmul",
            equivalence_level=MappingEquivalenceLevel.EXACT,
            confidence=0.95,
            adaptation_notes="Direct replacement",
            optimization_hints="tensor_core",
        )

        mapping = result.to_cross_platform_mapping(
            gpu_api="cublasSgemm",
            platform=GPUPlatform.CUBLAS,
        )

        assert isinstance(mapping, CrossPlatformMapping)
        assert mapping.gpu_api == "cublasSgemm"
        assert mapping.npu_api == "Matmul"
        assert mapping.equivalence_level == MappingEquivalenceLevel.EXACT
        assert mapping.confidence == 0.95
        assert mapping.source == "llm_suggested"


class TestStorageIntegration:
    """存储集成测试"""

    def test_store_analysis_result_dry_run(self, tmp_path):
        """测试 dry-run 模式"""
        engine = GPUNPUAnalysisEngine(llm_client=None, storage=None)

        analysis = FilePairAnalysis(
            gpu_file=str(tmp_path / "test.cu"),
            npu_file=str(tmp_path / "test.cpp"),
            gpu_api="cublasSgemm",
            result=AnalysisResult(
                is_equivalent=True,
                npu_equivalent="Matmul",
                equivalence_level=MappingEquivalenceLevel.EXACT,
                confidence=0.95,
                adaptation_notes="",
                optimization_hints="none",
            ),
        )

        result = engine.store_analysis_result(analysis, dry_run=True)
        assert result is True

    def test_store_analysis_result_with_storage(self, tmp_path):
        """测试带存储的分析结果"""
        storage = GPUStorage(use_mock=True)
        engine = GPUNPUAnalysisEngine(llm_client=None, storage=storage)

        analysis = FilePairAnalysis(
            gpu_file=str(tmp_path / "test.cu"),
            npu_file=str(tmp_path / "test.cpp"),
            gpu_api="cublasSgemm",
            result=AnalysisResult(
                is_equivalent=True,
                npu_equivalent="Matmul",
                equivalence_level=MappingEquivalenceLevel.EXACT,
                confidence=0.95,
                adaptation_notes="",
                optimization_hints="none",
            ),
        )

        result = engine.store_analysis_result(analysis, dry_run=False)
        assert result is True

        # 验证存储
        stored = storage.search_cross_platform_mappings("cublas")
        assert len(stored) == 1


# 需要导入 json
import json
