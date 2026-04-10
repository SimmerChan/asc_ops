# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
准确性计算测试
"""

import pytest

from src.asc_ops.ranker.scoring.accuracy import AccuracyCalculator, AccuracyScore
from src.asc_ops.ranker.scoring.config import RankingConfig


class TestAccuracyScore:
    """AccuracyScore 数据类测试"""

    def test_accuracy_score_creation(self):
        """测试 AccuracyScore 创建"""
        score = AccuracyScore(
            total=0.9,
            correction_count=1,
            citation_count=10,
            error_rate=0.1
        )

        assert score.total == 0.9
        assert score.correction_count == 1
        assert score.citation_count == 10
        assert score.error_rate == 0.1


class TestAccuracyCalculator:
    """AccuracyCalculator 测试"""

    def setup_method(self):
        """测试前设置"""
        self.config = RankingConfig()
        self.calculator = AccuracyCalculator(self.config)

    def test_calculate_sync_no_citations(self):
        """测试无引用时使用默认分数"""
        score = self.calculator.calculate_sync(0, 0)

        assert score.total == self.config.default_accuracy  # 0.5
        assert score.citation_count == 0
        assert score.correction_count == 0
        assert score.error_rate == 0.0

    def test_calculate_sync_perfect(self):
        """测试完美准确性（无纠错）"""
        score = self.calculator.calculate_sync(100, 0)

        assert score.total == 1.0
        assert score.error_rate == 0.0

    def test_calculate_sync_some_corrections(self):
        """测试有部分纠错"""
        score = self.calculator.calculate_sync(100, 10)

        assert score.total == 0.9  # 1 - 10/100
        assert score.error_rate == 0.1

    def test_calculate_sync_many_corrections(self):
        """测试高纠错率"""
        score = self.calculator.calculate_sync(100, 50)

        assert score.total == 0.5  # 1 - 50/100
        assert score.error_rate == 0.5

    def test_calculate_sync_all_wrong(self):
        """测试全部错误"""
        score = self.calculator.calculate_sync(100, 100)

        assert score.total == 0.0
        assert score.error_rate == 1.0

    def test_calculate_sync_low_citations(self):
        """测试低引用高纠错"""
        score = self.calculator.calculate_sync(5, 4)

        assert score.total == pytest.approx(0.2, rel=1e-9)
        assert score.error_rate == 0.8

    def test_calculate_from_metadata(self):
        """测试从元数据计算"""
        metadata = {
            "citation_count": 50,
            "correction_count": 5
        }
        score = self.calculator.calculate_from_metadata(metadata)

        assert score.total == 0.9  # 1 - 5/50
        assert score.citation_count == 50
        assert score.correction_count == 5

    def test_calculate_from_metadata_alternate_fields(self):
        """测试从替代字段名计算"""
        metadata = {
            "citations": 20,
            "corrections": 2
        }
        score = self.calculator.calculate_from_metadata(metadata)

        assert score.total == 0.9

    def test_calculate_from_metadata_no_data(self):
        """测试无数据时使用默认值"""
        metadata = {}
        score = self.calculator.calculate_from_metadata(metadata)

        assert score.total == self.config.default_accuracy

    def test_calculate_batch(self):
        """测试批量计算"""
        items = [
            {"citation_count": 100, "correction_count": 0},
            {"citation_count": 50, "correction_count": 5},
            {},
        ]
        scores = self.calculator.calculate_batch(items)

        assert len(scores) == 3
        assert scores[0].total == 1.0
        assert scores[1].total == 0.9
        assert scores[2].total == self.config.default_accuracy

    def test_custom_default_accuracy(self):
        """测试自定义默认准确性"""
        config = RankingConfig(default_accuracy=0.7)
        calculator = AccuracyCalculator(config)

        score = calculator.calculate_sync(0, 0)

        assert score.total == 0.7
