# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
优化知识抽取器测试
"""

import pytest

from src.asc_ops.extractor.opt_extractor import (
    OptimizationExtractor,
    OptimizationExtractionResult,
)


class TestOptimizationExtractor:
    """优化知识抽取器测试"""

    def setup_method(self):
        """设置测试"""
        self.extractor = OptimizationExtractor()

    def test_extract_optimization_pr(self):
        """提取优化 PR"""
        result = self.extractor.extract(
            pr_title="perf: improve Matmul memory usage",
            pr_body="Reduced memory footprint by 30% through better buffer management",
            source_repo="ascend-cann",
            source_pr="5678",
        )

        assert isinstance(result, OptimizationExtractionResult)
        assert result.source_repo == "ascend-cann"
        assert result.source_pr == "5678"
        assert result.extraction_success is True

    def test_extract_non_optimization_pr(self):
        """非优化 PR"""
        result = self.extractor.extract(
            pr_title="fix: memory leak in Matmul",
            pr_body="This is a bug fix",
            source_repo="ascend-cann",
            source_pr="1234",
        )

        assert result.extraction_success is False
        assert result.error_message == "Not an optimization PR"

    def test_extract_memory_optimization_type(self):
        """内存优化类型"""
        result = self.extractor.extract(
            pr_title="perf: reduce memory allocation in Matmul",
            pr_body="Optimization description",
            source_repo="ascend-cann",
            source_pr="100",
        )

        assert "memory" in result.optimization_type

    def test_extract_pipeline_optimization_type(self):
        """流水线优化类型"""
        result = self.extractor.extract(
            pr_title="perf: pipeline optimization for VecCompute",
            pr_body="Enabled pipelining",
            source_repo="ascend-cann",
            source_pr="101",
        )

        assert "pipeline" in result.optimization_type

    def test_extract_improvement_ratio_percent(self):
        """提取百分比提升"""
        text = "Performance improved by 30%"

        ratio = self.extractor._extract_improvement_ratio(text)

        assert ratio is not None
        assert abs(ratio - 0.3) < 0.01

    def test_extract_improvement_ratio_x(self):
        """提取倍数提升"""
        text = "Achieved 2x speedup"

        ratio = self.extractor._extract_improvement_ratio(text)

        assert ratio is not None
        assert abs(ratio - 1.0) < 0.01  # 2x = 1.0 improvement

    def test_extract_operator(self):
        """提取算子"""
        result = self.extractor.extract(
            pr_title="perf: optimize VecReduceMax",
            pr_body="Optimization description",
            source_repo="ascend-cann",
            source_pr="200",
        )

        assert result.operator_id == "VecReduceMax"

    def test_generate_opt_id(self):
        """生成优化 ID"""
        opt_id = self.extractor._generate_opt_id("ascend-cann", "5678")

        assert "OPT" in opt_id
        assert "5678" in opt_id


class TestOptimizationExtractionResult:
    """OptimizationExtractionResult 测试"""

    def test_to_dict(self):
        """转换为字典"""
        result = OptimizationExtractionResult(
            opt_id="OPT-123",
            operator_id="Matmul",
            source_repo="ascend-cann",
            source_pr="5678",
            opt_title="Memory optimization",
            optimization_type=["memory"],
            optimization_description="Reduced memory",
            improvement_ratio=0.3,
            before_metrics={"memory": "100MB"},
            after_metrics={"memory": "70MB"},
            related_apis=["Matmul"],
            extraction_success=True,
        )

        data = result.to_dict()

        assert data["opt_id"] == "OPT-123"
        assert data["optimization_type"] == ["memory"]
        assert data["improvement_ratio"] == 0.3
        assert data["extraction_success"] is True
