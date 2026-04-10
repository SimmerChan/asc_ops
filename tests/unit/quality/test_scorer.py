# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
知识质量评分器测试
"""

import pytest

from src.asc_ops.quality.scorer import (
    QualityScorer,
    QualityScore,
    CompletenessScore,
    AccuracyScore,
    QualityLevel,
    APIKnowledgeChecker,
    BugFixKnowledgeChecker,
    OptimizationKnowledgeChecker,
)


class TestCompletenessScore:
    """CompletenessScore 测试"""

    def test_required_completeness_full(self):
        """全部必填字段已填"""
        score = CompletenessScore(
            total_required=5,
            filled_required=5,
            total_optional=3,
            filled_optional=0,
        )
        assert score.required_completeness == 1.0

    def test_required_completeness_partial(self):
        """部分必填字段已填"""
        score = CompletenessScore(
            total_required=5,
            filled_required=3,
            total_optional=3,
            filled_optional=0,
        )
        assert score.required_completeness == 0.6

    def test_optional_completeness(self):
        """可选字段完整度"""
        score = CompletenessScore(
            total_required=5,
            filled_required=5,
            total_optional=4,
            filled_optional=2,
        )
        assert score.optional_completeness == 0.5

    def test_overall_completeness(self):
        """总体完整度"""
        score = CompletenessScore(
            total_required=5,
            filled_required=5,
            total_optional=4,
            filled_optional=4,
        )
        # 1.0 * 0.7 + 1.0 * 0.3 = 1.0
        assert score.overall_completeness == 1.0

    def test_overall_completeness_mixed(self):
        """混合情况"""
        score = CompletenessScore(
            total_required=5,
            filled_required=4,  # 0.8
            total_optional=4,
            filled_optional=2,  # 0.5
        )
        # 0.8 * 0.7 + 0.5 * 0.3 = 0.56 + 0.15 = 0.71
        assert abs(score.overall_completeness - 0.71) < 0.01


class TestAccuracyScore:
    """AccuracyScore 测试"""

    def test_perfect_score(self):
        """满分准确性"""
        score = AccuracyScore(score=1.0, issues=[])
        assert score.score == 1.0

    def test_with_issues(self):
        """有问题的准确性"""
        score = AccuracyScore(
            score=0.6,
            issues=["问题1", "问题2"],
        )
        assert score.score == 0.6
        assert len(score.issues) == 2


class TestQualityLevel:
    """QualityLevel 测试"""

    def test_excellent_threshold(self):
        """优秀等级阈值"""
        assert QualityLevel.EXCELLENT.value == "excellent"

    def test_good_threshold(self):
        """良好等级"""
        assert QualityLevel.GOOD.value == "good"

    def test_fair_threshold(self):
        """一般等级"""
        assert QualityLevel.FAIR.value == "fair"

    def test_poor_threshold(self):
        """较差等级"""
        assert QualityLevel.POOR.value == "poor"


class TestAPIKnowledgeChecker:
    """API 知识检查器测试"""

    def test_complete_knowledge(self):
        """完整的 API 知识"""
        checker = APIKnowledgeChecker()

        knowledge = {
            "api_id": "AscendC.Matmul",
            "canonical_name": "Matmul",
            "full_signature": "Matmul(Tensor a, Tensor b) -> Tensor",
            "category": "compute",
            "description": "Matrix multiplication operator",
            "parameters": [],
            "return_value": {},
        }

        score = checker.check_completeness(knowledge)

        assert score.required_completeness == 1.0
        assert len(score.missing_required) == 0

    def test_missing_required_fields(self):
        """缺失必填字段"""
        checker = APIKnowledgeChecker()

        knowledge = {
            "api_id": "AscendC.Matmul",
            # 缺少其他必填字段
        }

        score = checker.check_completeness(knowledge)

        assert score.required_completeness < 1.0
        assert len(score.missing_required) > 0
        assert "canonical_name" in score.missing_required

    def test_accuracy_check(self):
        """准确性检查"""
        checker = APIKnowledgeChecker()

        # 正常情况
        knowledge = {
            "full_signature": "Matmul(Tensor a, Tensor b) -> Tensor",
            "description": "This is a valid description for matrix multiplication",
        }

        accuracy = checker.check_accuracy(knowledge)
        assert accuracy.score == 1.0

        # 描述过短
        knowledge_short = {
            "full_signature": "Matmul(Tensor a, Tensor b) -> Tensor",
            "description": "Short",
        }

        accuracy_short = checker.check_accuracy(knowledge_short)
        assert accuracy_short.score < 1.0
        assert len(accuracy_short.issues) > 0


class TestBugFixKnowledgeChecker:
    """Bug 修复知识检查器测试"""

    def test_complete_knowledge(self):
        """完整的 Bug 修复知识"""
        checker = BugFixKnowledgeChecker()

        knowledge = {
            "bug_id": "BUG001",
            "operator_id": "Matmul",
            "source_repo": "ascend-cann",
            "source_pr": "1234",
            "bug_title": "Memory leak in Matmul",
            "root_cause": "Buffer not released after operation",
            "fix_pattern": "Added buffer.release() after computation",
            "trigger_conditions": ["large input size"],
            "workarounds": [],
        }

        score = checker.check_completeness(knowledge)

        assert score.required_completeness == 1.0
        assert len(score.missing_required) == 0

    def test_missing_root_cause(self):
        """缺失根因"""
        checker = BugFixKnowledgeChecker()

        knowledge = {
            "bug_id": "BUG001",
            "operator_id": "Matmul",
            "source_repo": "ascend-cann",
            "source_pr": "1234",
            "bug_title": "Memory leak",
            # 缺少 root_cause 和 fix_pattern
        }

        score = checker.check_completeness(knowledge)

        assert "root_cause" in score.missing_required
        assert "fix_pattern" in score.missing_required


class TestOptimizationKnowledgeChecker:
    """优化知识检查器测试"""

    def test_complete_knowledge_with_metrics(self):
        """有量化指标"""
        checker = OptimizationKnowledgeChecker()

        knowledge = {
            "opt_id": "OPT001",
            "operator_id": "Matmul",
            "source_repo": "ascend-cann",
            "source_pr": "5678",
            "opt_title": "Memory optimization for Matmul",
            "optimization_type": ["memory"],
            "optimization_description": "Reduced memory footprint by 30%",
            "improvement_ratio": 0.3,
            "before_metrics": {"memory": "100MB"},
            "after_metrics": {"memory": "70MB"},
        }

        score = checker.check_completeness(knowledge)
        accuracy = checker.check_accuracy(knowledge)

        assert score.required_completeness == 1.0
        assert accuracy.score == 1.0

    def test_missing_quantitative_metrics(self):
        """缺少量化指标"""
        checker = OptimizationKnowledgeChecker()

        knowledge = {
            "opt_id": "OPT001",
            "operator_id": "Matmul",
            "source_repo": "ascend-cann",
            "source_pr": "5678",
            "opt_title": "Memory optimization",
            "optimization_type": ["memory"],
            "optimization_description": "Improved memory usage",
            # 缺少 improvement_ratio 和 metrics
        }

        accuracy = checker.check_accuracy(knowledge)

        assert accuracy.score < 1.0
        assert len(accuracy.issues) > 0


class TestQualityScorer:
    """QualityScorer 测试"""

    def test_score_api_complete(self):
        """评估完整 API 知识"""
        scorer = QualityScorer()

        knowledge = {
            "api_id": "AscendC.Matmul",
            "canonical_name": "Matmul",
            "full_signature": "Matmul(Tensor a, Tensor b) -> Tensor",
            "category": "compute",
            "description": "Matrix multiplication operator",
        }

        score = scorer.score_api(knowledge)

        assert isinstance(score, QualityScore)
        assert score.overall_score > 0.8
        assert score.quality_level in [QualityLevel.EXCELLENT, QualityLevel.GOOD]
        assert score.is_low_quality is False

    def test_score_api_incomplete(self):
        """评估不完整 API 知识"""
        scorer = QualityScorer()

        knowledge = {
            "api_id": "AscendC.Matmul",
            # 缺少大部分必填字段
        }

        score = scorer.score_api(knowledge)

        assert score.is_low_quality is True
        assert score.completeness.required_completeness < 0.5

    def test_score_api_with_confidence(self):
        """评估 API 知识带置信度"""
        scorer = QualityScorer()

        knowledge = {
            "api_id": "AscendC.Matmul",
            "canonical_name": "Matmul",
            "full_signature": "Matmul(Tensor a, Tensor b) -> Tensor",
            "category": "compute",
            "description": "Matrix multiplication operator",
        }

        score_no_conf = scorer.score_api(knowledge, confidence=None)
        score_with_conf = scorer.score_api(knowledge, confidence=0.5)

        # 有置信度时会混合计算
        assert score_with_conf.overall_score != score_no_conf.overall_score

    def test_score_bugfix(self):
        """评估 Bug 修复知识"""
        scorer = QualityScorer()

        knowledge = {
            "bug_id": "BUG001",
            "operator_id": "Matmul",
            "source_repo": "ascend-cann",
            "source_pr": "1234",
            "bug_title": "Memory leak",
            "root_cause": "Buffer not released after operation",
            "fix_pattern": "Added buffer.release()",
        }

        score = scorer.score_bugfix(knowledge)

        assert isinstance(score, QualityScore)
        assert score.overall_score > 0

    def test_score_optimization(self):
        """评估优化知识"""
        scorer = QualityScorer()

        knowledge = {
            "opt_id": "OPT001",
            "operator_id": "Matmul",
            "source_repo": "ascend-cann",
            "source_pr": "5678",
            "opt_title": "Memory optimization",
            "optimization_type": ["memory"],
            "optimization_description": "Reduced memory footprint",
            "improvement_ratio": 0.3,
        }

        score = scorer.score_optimization(knowledge)

        assert isinstance(score, QualityScore)
        assert score.overall_score > 0

    def test_low_quality_detection(self):
        """低质量检测"""
        scorer = QualityScorer()

        # 严重不完整的知识
        knowledge = {
            "api_id": "AscendC.Matmul",
            # 缺少几乎所有字段
        }

        score = scorer.score_api(knowledge)

        assert score.is_low_quality is True
        assert score.quality_level == QualityLevel.POOR
