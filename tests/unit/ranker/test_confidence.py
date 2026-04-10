# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
置信度计算引擎测试
"""

import pytest
from datetime import datetime, timedelta

from src.asc_ops.ranker.confidence import (
    ConfidenceEngine,
    ConfidenceScore,
    APISourceType,
    APIConfidenceCalculator,
    BugFixConfidenceCalculator,
    OptimizationConfidenceCalculator,
    ReviewStatus,
)


class TestConfidenceScore:
    """ConfidenceScore 数据类测试"""

    def test_score_clamping(self):
        """测试分数钳制在 0-1 范围"""
        # 大于 1 的分数应该被钳制到 1
        score = ConfidenceScore(total_score=1.5, breakdown={})
        assert score.total_score == 1.0

        # 小于 0 的分数应该被钳制到 0
        score = ConfidenceScore(total_score=-0.5, breakdown={})
        assert score.total_score == 0.0

    def test_low_confidence_threshold(self):
        """测试低置信度阈值"""
        # 分数 >= 0.3 不是低置信度
        score = ConfidenceScore(total_score=0.3, breakdown={})
        assert score.is_low_confidence is False

        # 分数 < 0.3 是低置信度
        score = ConfidenceScore(total_score=0.29, breakdown={})
        assert score.is_low_confidence is True

    def test_to_dict(self):
        """测试转换为字典"""
        score = ConfidenceScore(total_score=0.75, breakdown={"factor1": 0.9, "factor2": 0.8})
        result = score.to_dict()

        assert result["total_score"] == 0.75
        assert result["is_low_confidence"] is False
        assert result["breakdown"]["factor1"] == 0.9


class TestAPIConfidenceCalculator:
    """API 置信度计算器测试"""

    def test_official_source_full_completeness_recent(self):
        """官方来源 + 完整字段 + 近期更新 = 高置信度"""
        calc = BugFixConfidenceCalculator()  # 使用基类的通用计算方式
        score = calc.calculate(
            has_root_cause=True,
            has_fix_pattern=True,
            review_status=ReviewStatus.APPROVED,
        )

        # 对于 API 计算器应该用 API 专用计算器
        from src.asc_ops.ranker.confidence import APIConfidenceCalculator
        api_calc = APIConfidenceCalculator()

        score = api_calc.calculate(
            source_type=APISourceType.OFFICIAL,
            last_updated=datetime.now(),
            missing_fields=[],
        )

        assert score.total_score == 1.0
        assert score.is_low_confidence is False

    def test_community_source(self):
        """社区来源置信度低于官方"""
        api_calc = APIConfidenceCalculator()

        official_score = api_calc.calculate(
            source_type=APISourceType.OFFICIAL,
            last_updated=datetime.now(),
            missing_fields=[],
        )

        community_score = api_calc.calculate(
            source_type=APISourceType.COMMUNITY,
            last_updated=datetime.now(),
            missing_fields=[],
        )

        assert official_score.total_score > community_score.total_score

    def test_missing_fields_penalty(self):
        """缺失字段扣分"""
        api_calc = APIConfidenceCalculator()

        full_score = api_calc.calculate(
            source_type=APISourceType.OFFICIAL,
            last_updated=datetime.now(),
            missing_fields=[],
        )

        missing_score = api_calc.calculate(
            source_type=APISourceType.OFFICIAL,
            last_updated=datetime.now(),
            missing_fields=["description", "parameters"],
        )

        assert full_score.total_score > missing_score.total_score

    def test_staleness_penalty(self):
        """过时扣分"""
        api_calc = APIConfidenceCalculator()

        recent_score = api_calc.calculate(
            source_type=APISourceType.OFFICIAL,
            last_updated=datetime.now(),
            missing_fields=[],
        )

        # 2 年前更新的 API
        old_date = datetime.now() - timedelta(days=730)
        old_score = api_calc.calculate(
            source_type=APISourceType.OFFICIAL,
            last_updated=old_date,
            missing_fields=[],
        )

        assert recent_score.total_score > old_score.total_score


class TestBugFixConfidenceCalculator:
    """Bug 修复知识置信度计算器测试"""

    def test_complete_bugfix_high_confidence(self):
        """完整的 bugfix 高置信度"""
        calc = BugFixConfidenceCalculator()

        score = calc.calculate(
            has_root_cause=True,
            has_fix_pattern=True,
            review_status=ReviewStatus.APPROVED,
            source_type="pr_approved",
            has_trigger_conditions=True,
            has_workarounds=True,
        )

        assert score.total_score > 0.8
        assert score.is_low_confidence is False

    def test_missing_root_cause_low_confidence(self):
        """缺失根因 = 0 根因分数"""
        calc = BugFixConfidenceCalculator()

        score = calc.calculate(
            has_root_cause=False,
            has_fix_pattern=True,
            review_status=ReviewStatus.APPROVED,
        )

        assert score.breakdown["root_cause_score"] == 0.0

    def test_no_fix_pattern_penalty(self):
        """无修复方案扣分"""
        calc = BugFixConfidenceCalculator()

        with_fix = calc.calculate(
            has_root_cause=True,
            has_fix_pattern=True,
            review_status=ReviewStatus.PENDING,
        )

        without_fix = calc.calculate(
            has_root_cause=True,
            has_fix_pattern=False,
            review_status=ReviewStatus.PENDING,
        )

        assert with_fix.total_score > without_fix.total_score

    def test_review_status_weight(self):
        """审核状态权重"""
        calc = BugFixConfidenceCalculator()

        approved = calc.calculate(
            has_root_cause=True,
            has_fix_pattern=True,
            review_status=ReviewStatus.APPROVED,
        )

        pending = calc.calculate(
            has_root_cause=True,
            has_fix_pattern=True,
            review_status=ReviewStatus.PENDING,
        )

        assert approved.total_score > pending.total_score

    def test_source_type_weight(self):
        """来源类型权重"""
        calc = BugFixConfidenceCalculator()

        pr_approved = calc.calculate(
            has_root_cause=True,
            has_fix_pattern=True,
            review_status=ReviewStatus.PENDING,
            source_type="pr_approved",
        )

        commit_only = calc.calculate(
            has_root_cause=True,
            has_fix_pattern=True,
            review_status=ReviewStatus.PENDING,
            source_type="commit",
        )

        assert pr_approved.total_score > commit_only.total_score


class TestOptimizationConfidenceCalculator:
    """优化知识置信度计算器测试"""

    def test_with_improvement_ratio(self):
        """有量化指标"""
        calc = OptimizationConfidenceCalculator()

        with_ratio = calc.calculate(
            has_improvement_ratio=True,
            has_description=True,
            optimization_types=["memory"],
        )

        without_ratio = calc.calculate(
            has_improvement_ratio=False,
            has_description=True,
            optimization_types=["memory"],
        )

        assert with_ratio.total_score > without_ratio.total_score

    def test_has_description_bonus(self):
        """有描述加分"""
        calc = OptimizationConfidenceCalculator()

        with_desc = calc.calculate(
            has_improvement_ratio=False,
            has_description=True,
        )

        without_desc = calc.calculate(
            has_improvement_ratio=False,
            has_description=False,
        )

        assert with_desc.total_score > without_desc.total_score

    def test_optimization_type_bonus(self):
        """有优化类型加成"""
        calc = OptimizationConfidenceCalculator()

        with_types = calc.calculate(
            has_improvement_ratio=False,
            has_description=True,
            optimization_types=["pipeline", "memory"],
        )

        without_types = calc.calculate(
            has_improvement_ratio=False,
            has_description=True,
            optimization_types=[],
        )

        assert with_types.total_score > without_types.total_score

    def test_review_status_weight(self):
        """审核状态权重"""
        calc = OptimizationConfidenceCalculator()

        approved = calc.calculate(
            has_improvement_ratio=True,
            has_description=True,
            review_status=ReviewStatus.APPROVED,
        )

        pending = calc.calculate(
            has_improvement_ratio=True,
            has_description=True,
            review_status=ReviewStatus.PENDING,
        )

        assert approved.total_score > pending.total_score


class TestConfidenceEngine:
    """置信度计算引擎测试"""

    def test_engine_initialization(self):
        """引擎初始化"""
        engine = ConfidenceEngine()

        assert engine.api_calculator is not None
        assert engine.bugfix_calculator is not None
        assert engine.optimization_calculator is not None

    def test_calculate_api_confidence(self):
        """API 置信度计算"""
        engine = ConfidenceEngine()

        score = engine.calculate_api_confidence(
            source_type=APISourceType.OFFICIAL,
            last_updated=datetime.now(),
            missing_fields=[],
        )

        assert isinstance(score, ConfidenceScore)
        assert score.total_score == 1.0

    def test_calculate_bugfix_confidence(self):
        """BugFix 置信度计算"""
        engine = ConfidenceEngine()

        score = engine.calculate_bugfix_confidence(
            has_root_cause=True,
            has_fix_pattern=True,
            review_status=ReviewStatus.APPROVED,
        )

        assert isinstance(score, ConfidenceScore)
        assert score.total_score > 0

    def test_calculate_optimization_confidence(self):
        """Optimization 置信度计算"""
        engine = ConfidenceEngine()

        score = engine.calculate_optimization_confidence(
            has_improvement_ratio=True,
            has_description=True,
            optimization_types=["memory"],
        )

        assert isinstance(score, ConfidenceScore)
        assert score.total_score > 0
