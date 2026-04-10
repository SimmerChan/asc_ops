# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
置信度感知排序流水线集成测试
"""

import pytest
from datetime import datetime, timedelta

from src.asc_ops.ranker import (
    ConfidenceRanker,
    RankingConfig,
)
from src.asc_ops.ranker.scoring import (
    SourceType,
    ContributorLevel,
)


class TestRankingPipeline:
    """排序流水线集成测试"""

    def setup_method(self):
        """测试前设置"""
        self.config = RankingConfig()
        self.ranker = ConfidenceRanker(config=self.config)
        self.reference_time = datetime(2026, 4, 10, 12, 0, 0)

    def test_single_item_ranking(self):
        """测试单项排序"""
        items = [
            {
                "id": "bug_001",
                "metadata": {
                    "source_type": "official",
                    "contributor_level": "core",
                    "last_updated": self.reference_time.isoformat(),
                    "citation_count": 100,
                    "correction_count": 0
                }
            }
        ]

        ranked = self.ranker.rank_results_sync(items, top_k=5)

        assert len(ranked) == 1
        assert ranked[0].id == "bug_001"
        # 官方 + 核心 + 今天 + 无错误 = 高分
        assert ranked[0].score.authority.total == 1.0
        assert ranked[0].score.recency.total > 0.99

    def test_multiple_items_sorted_by_confidence(self):
        """测试多项按置信度排序"""
        items = [
            {
                "id": "low_priority",
                "metadata": {
                    "source_type": "other",
                    "contributor_level": "newcomer",
                    "last_updated": (self.reference_time - timedelta(days=180)).isoformat(),
                    "citation_count": 10,
                    "correction_count": 5
                }
            },
            {
                "id": "high_priority",
                "metadata": {
                    "source_type": "official",
                    "contributor_level": "core",
                    "last_updated": (self.reference_time - timedelta(days=7)).isoformat(),
                    "citation_count": 100,
                    "correction_count": 0
                }
            }
        ]

        ranked = self.ranker.rank_results_sync(items)

        assert len(ranked) == 2
        # high_priority 应该有更高的综合分数
        assert ranked[0].id == "high_priority"
        assert ranked[0].score.total > ranked[1].score.total

    def test_same_source_different_recency(self):
        """测试相同来源不同时效性的排序"""
        items = [
            {
                "id": "old_item",
                "metadata": {
                    "source_type": "official",
                    "contributor_level": "active",
                    "last_updated": (self.reference_time - timedelta(days=90)).isoformat(),
                    "citation_count": 0,
                    "correction_count": 0
                }
            },
            {
                "id": "recent_item",
                "metadata": {
                    "source_type": "official",
                    "contributor_level": "active",
                    "last_updated": (self.reference_time - timedelta(days=7)).isoformat(),
                    "citation_count": 0,
                    "correction_count": 0
                }
            }
        ]

        ranked = self.ranker.rank_results_sync(items)

        assert len(ranked) == 2
        # recent_item 应该排在前（时效性更好）
        assert ranked[0].id == "recent_item"
        # recent_item 的 recency 分数应该更高
        assert ranked[0].score.recency.total > ranked[1].score.recency.total

    def test_same_recency_different_source(self):
        """测试相同时效性不同来源的排序"""
        items = [
            {
                "id": "community_item",
                "metadata": {
                    "source_type": "community",
                    "contributor_level": "active",
                    "last_updated": (self.reference_time - timedelta(days=30)).isoformat(),
                    "citation_count": 0,
                    "correction_count": 0
                }
            },
            {
                "id": "official_item",
                "metadata": {
                    "source_type": "official",
                    "contributor_level": "active",
                    "last_updated": (self.reference_time - timedelta(days=30)).isoformat(),
                    "citation_count": 0,
                    "correction_count": 0
                }
            }
        ]

        ranked = self.ranker.rank_results_sync(items)

        assert len(ranked) == 2
        # official_item 应该排在前（权威性更高）
        assert ranked[0].id == "official_item"
        assert ranked[0].score.authority.total > ranked[1].score.authority.total

    def test_top_k_limit(self):
        """测试 top_k 限制"""
        items = [
            {
                "id": f"item_{i}",
                "metadata": {
                    "source_type": "official",
                    "contributor_level": "core",
                    "last_updated": (self.reference_time - timedelta(days=i)).isoformat(),
                    "citation_count": 0,
                    "correction_count": 0
                }
            }
            for i in range(10)
        ]

        ranked = self.ranker.rank_results_sync(items, top_k=3)

        assert len(ranked) == 3
        # 最新的应该排第一
        assert ranked[0].id == "item_0"

    def test_empty_results(self):
        """测试空结果"""
        ranked = self.ranker.rank_results_sync([])
        assert len(ranked) == 0

    def test_all_low_quality_items(self):
        """测试所有低质量条目"""
        items = [
            {
                "id": "low_quality_1",
                "metadata": {
                    "source_type": "other",
                    "contributor_level": "newcomer",
                    "last_updated": (self.reference_time - timedelta(days=365)).isoformat(),
                    "citation_count": 1,
                    "correction_count": 1
                }
            },
            {
                "id": "low_quality_2",
                "metadata": {
                    "source_type": "other",
                    "contributor_level": "newcomer",
                    "last_updated": (self.reference_time - timedelta(days=365)).isoformat(),
                    "citation_count": 2,
                    "correction_count": 2
                }
            }
        ]

        ranked = self.ranker.rank_results_sync(items)

        assert len(ranked) == 2
        # 两者都应该有较低但非零的分数
        for item in ranked:
            assert item.score.total >= 0
            assert item.score.total <= 0.5

    def test_mixed_quality_items(self):
        """测试混合质量条目"""
        items = [
            {
                "id": "excellent",
                "metadata": {
                    "source_type": "official",
                    "contributor_level": "core",
                    "last_updated": (self.reference_time - timedelta(days=7)).isoformat(),
                    "citation_count": 100,
                    "correction_count": 0
                }
            },
            {
                "id": "good",
                "metadata": {
                    "source_type": "official",
                    "contributor_level": "active",
                    "last_updated": (self.reference_time - timedelta(days=30)).isoformat(),
                    "citation_count": 50,
                    "correction_count": 5
                }
            },
            {
                "id": "poor",
                "metadata": {
                    "source_type": "community",
                    "contributor_level": "newcomer",
                    "last_updated": (self.reference_time - timedelta(days=180)).isoformat(),
                    "citation_count": 10,
                    "correction_count": 8
                }
            }
        ]

        ranked = self.ranker.rank_results_sync(items)

        assert len(ranked) == 3
        # excellent 应该第一
        assert ranked[0].id == "excellent"
        # poor 应该最后
        assert ranked[2].id == "poor"
        # good 在中间
        assert ranked[1].id == "good"


class TestConfidenceBreakdown:
    """置信度分数分解测试"""

    def setup_method(self):
        """测试前设置"""
        self.ranker = ConfidenceRanker()
        self.reference_time = datetime(2026, 4, 10, 12, 0, 0)

    def test_explain_score_breakdown(self):
        """测试分数分解"""
        metadata = {
            "source_type": "official",
            "contributor_level": "active",
            "last_updated": (self.reference_time - timedelta(days=30)).isoformat(),
            "citation_count": 50,
            "correction_count": 5
        }

        explanation = self.ranker.explain_score(metadata)

        assert "total_score" in explanation
        assert "breakdown" in explanation
        assert "weights" in explanation

        # 检查 breakdown 结构
        breakdown = explanation["breakdown"]
        assert "authority" in breakdown
        assert "recency" in breakdown
        assert "accuracy" in breakdown

        # 检查权重
        weights = explanation["weights"]
        assert weights["authority"] == 0.5
        assert weights["recency"] == 0.3
        assert weights["accuracy"] == 0.2

    def test_score_calculation_formula(self):
        """测试分数计算公式"""
        metadata = {
            "source_type": "official",  # 权重 1.0
            "contributor_level": "active",  # 权重 0.8
            "last_updated": self.reference_time.isoformat(),  # 0 天，e^0 = 1.0
            "citation_count": 100,
            "correction_count": 0  # 1 - 0/100 = 1.0
        }

        score = self.ranker.calculate_composite_score(metadata)

        # Authority = 1.0 * 0.8 = 0.8
        assert score.authority.total == 0.8
        # Recency = e^(-0.05 * 0) = 1.0
        assert score.recency.total == 1.0
        # Accuracy = 1 - 0/100 = 1.0
        assert score.accuracy.total == 1.0
        # Total = 0.5 * 0.8 + 0.3 * 1.0 + 0.2 * 1.0 = 0.4 + 0.3 + 0.2 = 0.9
        assert score.total == pytest.approx(0.9, rel=1e-9)
