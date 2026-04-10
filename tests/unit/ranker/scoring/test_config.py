# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
排序配置测试
"""

import pytest

from src.asc_ops.ranker.scoring.config import RankingConfig, DEFAULT_RANKING_CONFIG


class TestRankingConfig:
    """RankingConfig 测试"""

    def test_default_values(self):
        """测试默认配置值"""
        config = RankingConfig()

        assert config.authority_weight == 0.5
        assert config.recency_weight == 0.3
        assert config.accuracy_weight == 0.2
        assert config.recency_lambda == 0.05
        assert config.max_recency_days == 365
        assert config.default_accuracy == 0.5

    def test_default_source_weights(self):
        """测试默认来源权重"""
        config = RankingConfig()

        assert config.source_weights["official"] == 1.0
        assert config.source_weights["community"] == 0.7
        assert config.source_weights["other"] == 0.5

    def test_default_contributor_weights(self):
        """测试默认贡献者权重"""
        config = RankingConfig()

        assert config.contributor_weights["core"] == 1.0
        assert config.contributor_weights["active"] == 0.8
        assert config.contributor_weights["newcomer"] == 0.6

    def test_weight_sum_validation(self):
        """测试权重和验证"""
        # 正确权重应该通过
        config = RankingConfig(
            authority_weight=0.5,
            recency_weight=0.3,
            accuracy_weight=0.2
        )
        assert config.authority_weight == 0.5

        # 错误权重应该抛出异常
        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            RankingConfig(
                authority_weight=0.6,
                recency_weight=0.3,
                accuracy_weight=0.2
            )

    def test_negative_lambda_validation(self):
        """测试负数 lambda 验证"""
        with pytest.raises(ValueError, match="recency_lambda must be positive"):
            RankingConfig(recency_lambda=-0.1)

    def test_invalid_default_accuracy(self):
        """测试无效的 default_accuracy 验证"""
        with pytest.raises(ValueError, match="default_accuracy must be in"):
            RankingConfig(default_accuracy=1.5)

    def test_with_weights(self):
        """测试 with_weights 方法"""
        config = RankingConfig()
        new_config = config.with_weights(authority=0.6, recency=0.2, accuracy=0.2)

        assert new_config.authority_weight == 0.6
        assert new_config.recency_weight == 0.2
        assert new_config.accuracy_weight == 0.2
        # 原始配置不变
        assert config.authority_weight == 0.5

    def test_global_default_config(self):
        """测试全局默认配置"""
        assert DEFAULT_RANKING_CONFIG is not None
        assert isinstance(DEFAULT_RANKING_CONFIG, RankingConfig)
        assert DEFAULT_RANKING_CONFIG.authority_weight == 0.5
