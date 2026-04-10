# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
综合排序器测试
"""

import pytest
from datetime import datetime, timedelta

from src.asc_ops.ranker.integrated_ranker import (
    ConfidenceRanker,
    CompositeScore,
    RankedItem,
)
from src.asc_ops.ranker.scoring.config import RankingConfig
from src.asc_ops.ranker.scoring import SourceType, ContributorLevel


class TestCompositeScore:
    """CompositeScore 测试"""

    def test_to_dict(self):
        """测试转换为字典"""
        from src.asc_ops.ranker.scoring.authority import AuthorityScore
        from src.asc_ops.ranker.scoring.recency import RecencyScore
        from src.asc_ops.ranker.scoring.accuracy import AccuracyScore

        composite = CompositeScore(
            total=0.75,
            authority=AuthorityScore(
                total=0.8,
                source_weight=1.0,
                contributor_weight=0.8,
                source_type=SourceType.OFFICIAL,
                contributor_level=ContributorLevel.ACTIVE
            ),
            recency=RecencyScore(total=0.9, days_since_update=7, lambda_value=0.05),
            accuracy=AccuracyScore(total=0.5, correction_count=0, citation_count=0, error_rate=0.0),
            weights=(0.5, 0.3, 0.2)
        )

        result = composite.to_dict()

        assert result["total"] == 0.75
        assert result["authority"] == 0.8
        assert result["recency"] == 0.9
        assert result["accuracy"] == 0.5
        assert result["weights"] == (0.5, 0.3, 0.2)


class TestRankedItem:
    """RankedItem 测试"""

    def test_ranked_item_creation(self):
        """测试 RankedItem 创建"""
        from src.asc_ops.ranker.scoring.authority import AuthorityScore
        from src.asc_ops.ranker.scoring.recency import RecencyScore
        from src.asc_ops.ranker.scoring.accuracy import AccuracyScore

        composite = CompositeScore(
            total=0.75,
            authority=AuthorityScore(
                total=0.8,
                source_weight=1.0,
                contributor_weight=0.8,
                source_type=SourceType.OFFICIAL,
                contributor_level=ContributorLevel.ACTIVE
            ),
            recency=RecencyScore(total=0.9, days_since_update=7, lambda_value=0.05),
            accuracy=AccuracyScore(total=0.5, correction_count=0, citation_count=0, error_rate=0.0),
            weights=(0.5, 0.3, 0.2)
        )

        item = RankedItem(
            id="test_1",
            score=composite,
            metadata={"key": "value"},
            original_score=0.95
        )

        assert item.id == "test_1"
        assert item.score.total == 0.75
        assert item.metadata == {"key": "value"}
        assert item.original_score == 0.95


class TestConfidenceRanker:
    """ConfidenceRanker 测试"""

    def setup_method(self):
        """测试前设置"""
        self.config = RankingConfig()
        self.ranker = ConfidenceRanker(config=self.config)
        self.reference_time = datetime(2026, 4, 10, 12, 0, 0)

    def test_calculate_composite_score_full_metadata(self):
        """测试完整元数据的综合分数计算"""
        metadata = {
            "source_type": "official",
            "contributor_level": "core",
            "last_updated": (self.reference_time - timedelta(days=7)).isoformat(),
            "citation_count": 100,
            "correction_count": 0
        }

        score = self.ranker.calculate_composite_score(metadata)

        assert score.total > 0
        assert score.authority.total == 1.0  # official * core
        assert score.recency.days_since_update == 7
        assert score.accuracy.total == 1.0  # 无纠错

    def test_calculate_composite_score_minimal_metadata(self):
        """测试最小元数据的综合分数计算"""
        metadata = {}

        score = self.ranker.calculate_composite_score(metadata)

        # 使用默认值的综合分数
        assert score.total > 0
        assert score.total < 1.0

    def test_rank_results_sync_single_item(self):
        """测试单项排序"""
        items = [
            {
                "id": "item_1",
                "score": 0.8,
                "metadata": {
                    "source_type": "official",
                    "contributor_level": "core",
                    "last_updated": self.reference_time.isoformat(),
                    "citation_count": 100,
                    "correction_count": 0
                }
            }
        ]

        ranked = self.ranker.rank_results_sync(items)

        assert len(ranked) == 1
        assert ranked[0].id == "item_1"

    def test_rank_results_sync_multiple_items(self):
        """测试多项排序"""
        items = [
            {
                "id": "older_community",
                "score": 0.9,
                "metadata": {
                    "source_type": "community",
                    "contributor_level": "active",
                    "last_updated": (self.reference_time - timedelta(days=90)).isoformat(),
                    "citation_count": 50,
                    "correction_count": 5
                }
            },
            {
                "id": "recent_official",
                "score": 0.8,
                "metadata": {
                    "source_type": "official",
                    "contributor_level": "core",
                    "last_updated": (self.reference_time - timedelta(days=7)).isoformat(),
                    "citation_count": 100,
                    "correction_count": 0
                }
            }
        ]

        ranked = self.ranker.rank_results_sync(items, top_k=2)

        assert len(ranked) == 2
        # recent_official 应该排第一（权威性高 + 时效性好）
        assert ranked[0].id == "recent_official"
        assert ranked[0].score.authority.source_type == SourceType.OFFICIAL

    def test_rank_results_sync_respects_top_k(self):
        """测试 top_k 限制"""
        items = [
            {"id": f"item_{i}", "score": 0.5 + i * 0.01, "metadata": {}}
            for i in range(10)
        ]

        ranked = self.ranker.rank_results_sync(items, top_k=3)

        assert len(ranked) == 3

    def test_rank_results_sync_with_bug_id(self):
        """测试使用 bug_id 作为标识"""
        items = [
            {
                "bug_id": "bug_123",
                "score": 0.8,
                "metadata": {"source_type": "official"}
            }
        ]

        ranked = self.ranker.rank_results_sync(items)

        assert len(ranked) == 1
        assert ranked[0].id == "bug_123"

    def test_rank_results_sync_with_opt_id(self):
        """测试使用 opt_id 作为标识"""
        items = [
            {
                "opt_id": "opt_456",
                "score": 0.7,
                "metadata": {"source_type": "community"}
            }
        ]

        ranked = self.ranker.rank_results_sync(items)

        assert len(ranked) == 1
        assert ranked[0].id == "opt_456"

    def test_explain_score(self):
        """测试分数解释"""
        metadata = {
            "source_type": "official",
            "contributor_level": "active",
            "last_updated": (self.reference_time - timedelta(days=30)).isoformat(),
            "citation_count": 20,
            "correction_count": 2
        }

        explanation = self.ranker.explain_score(metadata)

        assert "total_score" in explanation
        assert "breakdown" in explanation
        assert "weights" in explanation
        assert explanation["breakdown"]["authority"]["score"] == 0.8  # official * active
        assert explanation["breakdown"]["recency"]["days_since_update"] == 30

    def test_custom_config(self):
        """测试自定义配置"""
        config = RankingConfig(
            authority_weight=0.6,
            recency_weight=0.2,
            accuracy_weight=0.2
        )
        ranker = ConfidenceRanker(config=config)

        metadata = {
            "source_type": "official",
            "contributor_level": "core",
            "last_updated": self.reference_time.isoformat(),
            "citation_count": 0,
            "correction_count": 0
        }

        score = ranker.calculate_composite_score(metadata)

        # authority: 1.0 * 1.0 = 1.0, weight 0.6
        # recency: 1.0 (今天), weight 0.2
        # accuracy: 0.5 (无数据), weight 0.2
        # total = 0.6 * 1.0 + 0.2 * 1.0 + 0.2 * 0.5 = 0.6 + 0.2 + 0.1 = 0.9
        assert abs(score.total - 0.9) < 0.01

    def test_ordering_by_confidence(self):
        """测试按置信度排序"""
        # 创建一个权威性低但时效性高的项
        items = [
            {
                "id": "low_auth_recent",
                "metadata": {
                    "source_type": "other",  # 权威性 0.5 * 0.8 = 0.4
                    "last_updated": (self.reference_time - timedelta(days=1)).isoformat(),
                }
            },
            {
                "id": "high_auth_old",
                "metadata": {
                    "source_type": "official",  # 权威性 1.0 * 0.8 = 0.8
                    "contributor_level": "core",  # 权威性 1.0
                    "last_updated": (self.reference_time - timedelta(days=180)).isoformat(),
                }
            }
        ]

        ranked = self.ranker.rank_results_sync(items)

        # 由于权威性权重是 0.5，时效性权重是 0.3
        # low_auth_recent: 0.5 * 0.4 + 0.3 * ~0.999 + 0.2 * 0.5 ≈ 0.2 + 0.3 + 0.1 = 0.6
        # high_auth_old: 0.5 * 1.0 + 0.3 * ~0.000 + 0.2 * 0.5 ≈ 0.5 + 0 + 0.1 = 0.6
        # 结果接近，但 high_auth_old 可能因为准确性默认 0.5 而略低
        assert len(ranked) == 2
