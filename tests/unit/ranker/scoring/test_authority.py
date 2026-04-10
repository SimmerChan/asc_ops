# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
权威性评估测试
"""

import pytest

from src.asc_ops.ranker.scoring.authority import (
    AuthorityScorer,
    AuthorityScore,
    SourceType,
    ContributorLevel,
)
from src.asc_ops.ranker.scoring.config import RankingConfig


class TestSourceType:
    """SourceType 枚举测试"""

    def test_source_type_values(self):
        """测试 SourceType 值"""
        assert SourceType.OFFICIAL.value == "official"
        assert SourceType.COMMUNITY.value == "community"
        assert SourceType.OTHER.value == "other"


class TestContributorLevel:
    """ContributorLevel 枚举测试"""

    def test_contributor_level_values(self):
        """测试 ContributorLevel 值"""
        assert ContributorLevel.CORE.value == "core"
        assert ContributorLevel.ACTIVE.value == "active"
        assert ContributorLevel.NEWCOMER.value == "newcomer"


class TestAuthorityScore:
    """AuthorityScore 数据类测试"""

    def test_authority_score_creation(self):
        """测试 AuthorityScore 创建"""
        score = AuthorityScore(
            total=0.8,
            source_weight=1.0,
            contributor_weight=0.8,
            source_type=SourceType.OFFICIAL,
            contributor_level=ContributorLevel.ACTIVE
        )

        assert score.total == 0.8
        assert score.source_weight == 1.0
        assert score.contributor_weight == 0.8
        assert score.source_type == SourceType.OFFICIAL
        assert score.contributor_level == ContributorLevel.ACTIVE


class TestAuthorityScorer:
    """AuthorityScorer 测试"""

    def setup_method(self):
        """测试前设置"""
        self.config = RankingConfig()
        self.scorer = AuthorityScorer(self.config)

    def test_calculate_official_core(self):
        """测试官方+核心贡献者 = 1.0"""
        score = self.scorer.calculate(
            source_type=SourceType.OFFICIAL,
            contributor_level=ContributorLevel.CORE
        )

        assert score.total == 1.0
        assert score.source_weight == 1.0
        assert score.contributor_weight == 1.0

    def test_calculate_official_active(self):
        """测试官方+活跃贡献者 = 0.8"""
        score = self.scorer.calculate(
            source_type=SourceType.OFFICIAL,
            contributor_level=ContributorLevel.ACTIVE
        )

        assert score.total == 0.8
        assert score.source_weight == 1.0
        assert score.contributor_weight == 0.8

    def test_calculate_official_newcomer(self):
        """测试官方+新人 = 0.6"""
        score = self.scorer.calculate(
            source_type=SourceType.OFFICIAL,
            contributor_level=ContributorLevel.NEWCOMER
        )

        assert score.total == 0.6

    def test_calculate_community_active(self):
        """测试社区+活跃贡献者 = 0.56"""
        score = self.scorer.calculate(
            source_type=SourceType.COMMUNITY,
            contributor_level=ContributorLevel.ACTIVE
        )

        assert score.total == pytest.approx(0.56, rel=1e-9)
        assert score.source_weight == 0.7
        assert score.contributor_weight == 0.8

    def test_calculate_other_default(self):
        """测试其他来源 + 默认贡献者"""
        score = self.scorer.calculate(
            source_type=SourceType.OTHER
        )

        # 其他来源 = 0.5, 默认活跃 = 0.8
        assert score.total == 0.4  # 0.5 * 0.8

    def test_calculate_from_string(self):
        """测试从字符串创建"""
        score = self.scorer.calculate(
            source_type="official",
            contributor_level="core"
        )

        assert score.total == 1.0
        assert score.source_type == SourceType.OFFICIAL

    def test_calculate_invalid_source_type(self):
        """测试无效的来源类型"""
        score = self.scorer.calculate(source_type="invalid_type")

        # 无效类型应该回退到 OTHER
        assert score.source_type == SourceType.OTHER
        assert score.source_weight == 0.5

    def test_calculate_from_metadata(self):
        """测试从元数据计算"""
        metadata = {
            "source_type": "official",
            "contributor_level": "core",
            "author": "test_user"
        }

        score = self.scorer.calculate_from_metadata(metadata)

        assert score.total == 1.0
        assert score.source_type == SourceType.OFFICIAL
        assert score.contributor_level == ContributorLevel.CORE

    def test_calculate_from_metadata_defaults(self):
        """测试从元数据计算（使用默认值）"""
        metadata = {}

        score = self.scorer.calculate_from_metadata(metadata)

        assert score.source_type == SourceType.OTHER
        assert score.contributor_level == ContributorLevel.ACTIVE  # 默认

    def test_custom_config(self):
        """测试自定义配置"""
        config = RankingConfig(
            source_weights={"official": 1.0, "community": 0.8, "other": 0.6},
            contributor_weights={"core": 1.0, "active": 0.9, "newcomer": 0.7}
        )
        scorer = AuthorityScorer(config)

        score = scorer.calculate(
            source_type=SourceType.COMMUNITY,
            contributor_level=ContributorLevel.ACTIVE
        )

        # 0.8 * 0.9 = 0.72
        assert score.total == pytest.approx(0.72, rel=1e-9)
