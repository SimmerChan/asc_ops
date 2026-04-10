# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
引用追踪器测试
"""

import pytest
from datetime import datetime, timedelta

from src.asc_ops.quality.citation_tracker import (
    CitationTracker,
    CitationStats,
    EntityType,
)


class TestCitationTracker:
    """CitationTracker 测试"""

    @pytest.fixture
    def tracker(self):
        """创建引用追踪器 (使用 mock Redis)"""
        from src.asc_ops.storage.redis_client import RedisClient
        redis_client = RedisClient(mock=True)
        return CitationTracker(redis_client)

    def test_init(self, tracker):
        """测试初始化"""
        assert tracker.redis is not None
        assert tracker.redis.is_mock is True

    def test_record_citation(self, tracker):
        """测试记录引用"""
        entity_id = "bug_001"
        entity_type = "bug"

        count = tracker.record_citation(entity_id, entity_type)
        assert count == 1

        # 再次引用
        count = tracker.record_citation(entity_id, entity_type)
        assert count == 2

    def test_record_citation_with_timestamp(self, tracker):
        """测试带时间戳的引用记录"""
        entity_id = "bug_002"
        entity_type = "bug"
        timestamp = datetime.now() - timedelta(days=1)

        tracker.record_citation(entity_id, entity_type, timestamp)
        stats = tracker.get_stats(entity_id, entity_type)

        assert stats.citation_count == 1
        assert stats.last_cited_at is not None
        # 应该比当前时间早
        assert stats.last_cited_at < datetime.now()

    def test_record_correction(self, tracker):
        """测试记录纠错"""
        entity_id = "bug_003"
        entity_type = "bug"

        count = tracker.record_correction(entity_id, entity_type)
        assert count == 1

        count = tracker.record_correction(entity_id, entity_type)
        assert count == 2

    def test_get_stats(self, tracker):
        """测试获取统计信息"""
        entity_id = "bug_004"
        entity_type = "bug"

        # 记录一些引用和纠错
        tracker.record_citation(entity_id, entity_type)
        tracker.record_citation(entity_id, entity_type)
        tracker.record_citation(entity_id, entity_type)
        tracker.record_correction(entity_id, entity_type)

        stats = tracker.get_stats(entity_id, entity_type)

        assert stats.entity_id == entity_id
        assert stats.entity_type == entity_type
        assert stats.citation_count == 3
        assert stats.correction_count == 1
        assert stats.error_rate == pytest.approx(1/3, rel=1e-2)
        assert stats.accuracy == pytest.approx(2/3, rel=1e-2)

    def test_get_stats_no_data(self, tracker):
        """测试获取不存在的实体统计"""
        stats = tracker.get_stats("nonexistent", "bug")

        assert stats.citation_count == 0
        assert stats.correction_count == 0
        assert stats.error_rate == 0.0
        assert stats.accuracy == 1.0

    def test_get_top_cited(self, tracker):
        """测试获取 Top 引用"""
        # 记录多个实体的引用
        tracker.record_citation("bug_001", "bug")
        tracker.record_citation("bug_001", "bug")
        tracker.record_citation("bug_001", "bug")
        tracker.record_citation("bug_002", "bug")
        tracker.record_citation("bug_002", "bug")
        tracker.record_citation("bug_003", "bug")

        top = tracker.get_top_cited("bug", limit=3)

        assert len(top) == 3
        assert top[0]["entity_id"] == "bug_001"
        assert top[0]["citation_count"] == 3
        assert top[1]["entity_id"] == "bug_002"
        assert top[1]["citation_count"] == 2

    def test_get_top_inaccurate(self, tracker):
        """测试获取高错误率实体"""
        # bug_001: 3 citations, 1 correction -> error_rate = 0.33
        tracker.record_citation("bug_001", "bug")
        tracker.record_citation("bug_001", "bug")
        tracker.record_citation("bug_001", "bug")
        tracker.record_correction("bug_001", "bug")

        # bug_002: 5 citations, 2 corrections -> error_rate = 0.4
        tracker.record_citation("bug_002", "bug")
        tracker.record_citation("bug_002", "bug")
        tracker.record_citation("bug_002", "bug")
        tracker.record_citation("bug_002", "bug")
        tracker.record_citation("bug_002", "bug")
        tracker.record_correction("bug_002", "bug")
        tracker.record_correction("bug_002", "bug")

        # bug_003: 10 citations, 0 corrections -> error_rate = 0 (满足 min_citations 但错误率为 0)
        for _ in range(10):
            tracker.record_citation("bug_003", "bug")

        top = tracker.get_top_inaccurate("bug", min_citations=3, limit=10)

        # 所有 3 个都满足 min_citations=3
        assert len(top) == 3
        # bug_002 的错误率最高，排第一
        assert top[0]["entity_id"] == "bug_002"
        assert top[0]["error_rate"] == pytest.approx(0.4, rel=1e-2)

    def test_normalize_entity_type(self, tracker):
        """测试实体类型规范化"""
        assert tracker._normalize_entity_type("bug") == "bug"
        assert tracker._normalize_entity_type("bugs") == "bug"
        assert tracker._normalize_entity_type("bugfix") == "bug"
        assert tracker._normalize_entity_type("optimization") == "optimization"
        assert tracker._normalize_entity_type("opt") == "optimization"
        assert tracker._normalize_entity_type("api") == "api"
        assert tracker._normalize_entity_type("API") == "api"

    def test_delete_stats(self, tracker):
        """测试删除统计"""
        entity_id = "bug_005"
        entity_type = "bug"

        tracker.record_citation(entity_id, entity_type)
        tracker.record_correction(entity_id, entity_type)

        result = tracker.delete_stats(entity_id, entity_type)
        assert result is True

        stats = tracker.get_stats(entity_id, entity_type)
        assert stats.citation_count == 0
        assert stats.correction_count == 0


class TestCitationStats:
    """CitationStats 数据类测试"""

    def test_error_rate_no_citations(self):
        """无引用时的错误率"""
        stats = CitationStats(
            entity_id="test",
            entity_type="bug",
            citation_count=0,
            correction_count=0
        )
        assert stats.error_rate == 0.0

    def test_accuracy_calculation(self):
        """准确性计算"""
        stats = CitationStats(
            entity_id="test",
            entity_type="bug",
            citation_count=10,
            correction_count=2
        )
        assert stats.error_rate == pytest.approx(0.2, rel=1e-2)
        assert stats.accuracy == pytest.approx(0.8, rel=1e-2)

    def test_to_dict(self):
        """测试转换为字典"""
        stats = CitationStats(
            entity_id="test",
            entity_type="bug",
            citation_count=5,
            correction_count=1,
            last_cited_at=datetime(2026, 4, 1, 12, 0, 0),
            last_corrected_at=datetime(2026, 4, 2, 12, 0, 0)
        )

        d = stats.to_dict()
        assert d["entity_id"] == "test"
        assert d["entity_type"] == "bug"
        assert d["citation_count"] == 5
        assert d["correction_count"] == 1
        assert d["error_rate"] == pytest.approx(0.2, rel=1e-2)
        assert d["accuracy"] == pytest.approx(0.8, rel=1e-2)
