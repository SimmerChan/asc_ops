# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
时效性计算测试
"""

import math
import pytest
from datetime import datetime, timedelta

from src.asc_ops.ranker.scoring.recency import RecencyCalculator, RecencyScore
from src.asc_ops.ranker.scoring.config import RankingConfig


class TestRecencyScore:
    """RecencyScore 数据类测试"""

    def test_recency_score_creation(self):
        """测试 RecencyScore 创建"""
        score = RecencyScore(
            total=0.8,
            days_since_update=7,
            lambda_value=0.05
        )

        assert score.total == 0.8
        assert score.days_since_update == 7
        assert score.lambda_value == 0.05


class TestRecencyCalculator:
    """RecencyCalculator 测试"""

    def setup_method(self):
        """测试前设置"""
        self.config = RankingConfig()
        self.calculator = RecencyCalculator(self.config)
        self.reference_time = datetime(2026, 4, 10, 12, 0, 0)

    def test_calculate_zero_days(self):
        """测试 0 天 = 1.0"""
        last_updated = self.reference_time
        score = self.calculator.calculate(last_updated, self.reference_time)

        assert score.total == 1.0
        assert score.days_since_update == 0

    def test_calculate_seven_days(self):
        """测试 7 天衰减"""
        last_updated = self.reference_time - timedelta(days=7)
        score = self.calculator.calculate(last_updated, self.reference_time)

        expected = math.exp(-0.05 * 7)
        assert abs(score.total - expected) < 0.01
        assert score.days_since_update == 7

    def test_calculate_thirty_days(self):
        """测试 30 天衰减"""
        last_updated = self.reference_time - timedelta(days=30)
        score = self.calculator.calculate(last_updated, self.reference_time)

        expected = math.exp(-0.05 * 30)
        assert abs(score.total - expected) < 0.01
        assert score.days_since_update == 30

    def test_calculate_ninety_days(self):
        """测试 90 天衰减"""
        last_updated = self.reference_time - timedelta(days=90)
        score = self.calculator.calculate(last_updated, self.reference_time)

        expected = math.exp(-0.05 * 90)
        assert abs(score.total - expected) < 0.01
        assert score.days_since_update == 90

    def test_calculate_exceeds_max_days(self):
        """测试超过最大天数限制"""
        last_updated = self.reference_time - timedelta(days=500)
        score = self.calculator.calculate(last_updated, self.reference_time)

        # 超过 max_recency_days 的天数应该被限制
        assert score.days_since_update == 500
        # 但分数应该用 capped days 计算
        expected = math.exp(-0.05 * 365)  # 用 365 计算
        assert abs(score.total - expected) < 0.01

    def test_calculate_future_date(self):
        """测试未来日期（返回0天差异）"""
        last_updated = self.reference_time + timedelta(days=10)
        score = self.calculator.calculate(last_updated, self.reference_time)

        assert score.total == 1.0
        assert score.days_since_update == 0

    def test_calculate_from_string_iso_format(self):
        """测试从 ISO 格式字符串解析"""
        last_updated = "2026-04-03T12:00:00"
        score = self.calculator.calculate(last_updated, self.reference_time)

        assert score.days_since_update == 7

    def test_calculate_from_string_with_z(self):
        """测试从带 Z 的 ISO 格式解析"""
        last_updated = "2026-04-03T12:00:00Z"
        score = self.calculator.calculate(last_updated, self.reference_time)

        # 时间戳 "2026-04-03T12:00:00Z" 转换为本地时间后，与 reference_time 的天数差
        # 由于时区转换，结果可能是 6 天或 7 天
        assert score.days_since_update in (6, 7)

    def test_calculate_from_unix_timestamp(self):
        """测试从 Unix 时间戳解析"""
        timestamp = int((self.reference_time - timedelta(days=30)).timestamp())
        score = self.calculator.calculate(timestamp, self.reference_time)

        assert score.days_since_update == 30

    def test_calculate_from_metadata(self):
        """测试从元数据计算"""
        metadata = {
            "last_updated": (self.reference_time - timedelta(days=14)).isoformat()
        }
        score = self.calculator.calculate_from_metadata(metadata)

        assert score.days_since_update == 14

    def test_calculate_from_metadata_updated_at(self):
        """测试从 updated_at 字段计算"""
        metadata = {
            "updated_at": (self.reference_time - timedelta(days=21)).isoformat()
        }
        score = self.calculator.calculate_from_metadata(metadata)

        assert score.days_since_update == 21

    def test_calculate_from_metadata_no_date(self):
        """测试无日期时的默认分数"""
        metadata = {}
        score = self.calculator.calculate_from_metadata(metadata)

        assert score.total == self.config.default_accuracy
        assert score.days_since_update == self.config.max_recency_days

    def test_get_decay_table(self):
        """测试衰减表示例"""
        table = self.calculator.get_decay_table(max_days=30)

        assert len(table) > 0
        # 检查第一个值 (0 天)
        assert table[0] == (0, 1.0)
        # 检查后续值
        for days, score in table:
            if days > 0:
                assert score < 1.0
                assert score > 0

    def test_custom_lambda(self):
        """测试自定义衰减系数"""
        config = RankingConfig(recency_lambda=0.1)
        calculator = RecencyCalculator(config)

        last_updated = self.reference_time - timedelta(days=10)
        score = calculator.calculate(last_updated, self.reference_time)

        expected = math.exp(-0.1 * 10)
        assert abs(score.total - expected) < 0.01
