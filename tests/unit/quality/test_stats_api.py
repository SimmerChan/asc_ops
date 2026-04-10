# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
引用统计 API 测试
"""

import pytest
from datetime import datetime, timedelta

from src.asc_ops.quality.stats_api import (
    CitationStatsAPI,
    QualityDashboard,
    EntityQualitySummary,
)


class TestCitationStatsAPI:
    """CitationStatsAPI 测试"""

    @pytest.fixture
    def api(self):
        """创建引用统计 API (使用 mock Redis)"""
        from src.asc_ops.storage.redis_client import RedisClient
        redis_client = RedisClient(mock=True)
        return CitationStatsAPI(redis_client)

    @pytest.fixture
    def tracker(self, api):
        return api.citation_tracker

    @pytest.fixture
    def feedback(self, api):
        return api.feedback_api

    def test_init(self, api):
        """测试初始化"""
        assert api.redis is not None
        assert api.citation_tracker is not None
        assert api.feedback_api is not None

    def test_get_stats(self, api, tracker, feedback):
        """测试获取完整统计信息"""
        import asyncio
        # 记录一些引用和纠错
        tracker.record_citation("bug_001", "bug")
        tracker.record_citation("bug_001", "bug")
        # 通过 report_correction 记录纠错（FeedbackAPI 的键结构）
        asyncio.run(feedback.report_correction("bug_001", "bug", "wrong"))

        stats = api.get_stats("bug_001", "bug")

        assert stats["entity_id"] == "bug_001"
        assert stats["entity_type"] == "bug"
        assert stats["citations"]["citation_count"] == 2
        assert stats["corrections"]["total"] == 1
        assert "accuracy" in stats["quality"]
        assert "error_rate" in stats["quality"]

    def test_get_quality_summary_no_data(self, api):
        """测试无数据时的质量摘要"""
        summary = api.get_quality_summary("nonexistent", "bug")

        assert summary.entity_id == "nonexistent"
        assert summary.citation_count == 0
        assert summary.correction_count == 0
        assert summary.accuracy == 1.0
        assert summary.quality_score == 1.0  # 无数据时默认满分

    def test_get_quality_summary_with_corrections(self, api, tracker, feedback):
        """测试有纠错时的质量摘要"""
        import asyncio
        # 记录引用和纠错
        for _ in range(10):
            tracker.record_citation("bug_002", "bug")
        # 通过 report_correction 记录纠错
        asyncio.run(feedback.report_correction("bug_002", "bug", "wrong"))

        summary = api.get_quality_summary("bug_002", "bug")

        assert summary.citation_count == 10
        assert summary.correction_count == 1
        assert summary.accuracy == pytest.approx(0.9, rel=1e-2)
        assert summary.quality_score < 1.0  # 有纠错应该降低分数

    def test_get_quality_summary_review_threshold(self, api, tracker, feedback):
        """测试质量摘要的审核标记"""
        import asyncio
        # 记录 5 次引用和 3 次纠错 (达到审核阈值)
        for _ in range(5):
            tracker.record_citation("bug_003", "bug")
        for _ in range(3):
            asyncio.run(feedback.report_correction("bug_003", "bug", "wrong"))

        summary = api.get_quality_summary("bug_003", "bug")

        assert summary.needs_review is True

    def test_get_top_cited(self, api, tracker):
        """测试获取 Top 引用列表"""
        # 记录不同引用次数
        for _ in range(5):
            tracker.record_citation("bug_001", "bug")
        for _ in range(3):
            tracker.record_citation("bug_002", "bug")
        for _ in range(1):
            tracker.record_citation("bug_003", "bug")

        top = api.get_top_cited("bug", limit=3)

        assert len(top) == 3
        assert top[0]["entity_id"] == "bug_001"
        assert top[0]["citation_count"] == 5
        assert "quality_score" in top[0]
        assert "accuracy" in top[0]

    def test_get_top_inaccurate(self, api, tracker):
        """测试获取高错误率列表"""
        # bug_001: 10 citations, 2 corrections -> error_rate = 0.2
        for _ in range(10):
            tracker.record_citation("bug_001", "bug")
        for _ in range(2):
            tracker.record_correction("bug_001", "bug")

        # bug_002: 10 citations, 4 corrections -> error_rate = 0.4
        for _ in range(10):
            tracker.record_citation("bug_002", "bug")
        for _ in range(4):
            tracker.record_correction("bug_002", "bug")

        # bug_003: 2 citations, 1 correction -> error_rate = 0.5 but below min_citations
        for _ in range(2):
            tracker.record_citation("bug_003", "bug")
        tracker.record_correction("bug_003", "bug")

        top = api.get_top_inaccurate("bug", min_citations=5, limit=10)

        assert len(top) == 2
        # bug_002 错误率更高
        assert top[0]["entity_id"] == "bug_002"
        assert top[0]["error_rate"] == pytest.approx(0.4, rel=1e-2)
        assert top[1]["entity_id"] == "bug_001"
        assert top[1]["error_rate"] == pytest.approx(0.2, rel=1e-2)

    def test_get_dashboard(self, api, tracker):
        """测试生成质量监控面板"""
        # 记录一些数据
        for _ in range(5):
            tracker.record_citation("bug_001", "bug")
        for _ in range(3):
            tracker.record_citation("bug_002", "bug")

        dashboard = api.get_dashboard("bug")

        assert dashboard.entity_type == "bug"
        assert dashboard.total_entities == 2
        assert dashboard.total_citations == 8
        assert dashboard.avg_citations_per_entity == 4.0
        assert isinstance(dashboard.top_cited, list)
        assert isinstance(dashboard.top_inaccurate, list)

    def test_get_bulk_quality(self, api, tracker):
        """测试批量获取质量摘要"""
        for _ in range(5):
            tracker.record_citation("bug_001", "bug")
        for _ in range(3):
            tracker.record_citation("bug_002", "bug")

        summaries = api.get_bulk_quality(["bug_001", "bug_002"], "bug")

        assert len(summaries) == 2
        assert summaries[0].entity_id == "bug_001"
        assert summaries[0].citation_count == 5
        assert summaries[1].entity_id == "bug_002"
        assert summaries[1].citation_count == 3

    def test_export_stats_csv(self, api, tracker):
        """测试导出 CSV 格式"""
        for _ in range(5):
            tracker.record_citation("bug_001", "bug")

        csv_output = api.export_stats_csv("bug")

        assert "entity_id" in csv_output
        assert "citation_count" in csv_output
        assert "bug_001" in csv_output

    def test_get_recently_corrected(self, api, tracker, feedback):
        """测试获取最近被纠错的实体"""
        # 记录不同时间的纠错
        old_time = datetime.now() - timedelta(days=10)
        recent_time = datetime.now() - timedelta(days=1)

        tracker.record_citation("bug_001", "bug")
        tracker.record_correction("bug_001", "bug", old_time)

        tracker.record_citation("bug_002", "bug")
        tracker.record_correction("bug_002", "bug", recent_time)

        recently_corrected = api._get_recently_corrected("bug", limit=10)

        # bug_002 的纠错更新，应该排在前面
        assert len(recently_corrected) == 2
        assert recently_corrected[0]["entity_id"] == "bug_002"


class TestQualityDashboard:
    """QualityDashboard 数据类测试"""

    def test_create_dashboard(self):
        """测试创建质量监控面板"""
        dashboard = QualityDashboard(
            entity_type="bug",
            total_entities=10,
            total_citations=100,
            total_corrections=5,
            avg_citations_per_entity=10.0,
            avg_corrections_per_entity=0.5,
            avg_accuracy=0.95,
            top_cited=[],
            top_inaccurate=[],
            recently_corrected=[]
        )

        assert dashboard.entity_type == "bug"
        assert dashboard.total_entities == 10
        assert dashboard.total_citations == 100
        assert dashboard.generated_at is not None


class TestEntityQualitySummary:
    """EntityQualitySummary 数据类测试"""

    def test_create_summary(self):
        """测试创建实体质量摘要"""
        summary = EntityQualitySummary(
            entity_id="bug_001",
            entity_type="bug",
            citation_count=10,
            correction_count=1,
            accuracy=0.9,
            quality_score=0.85,
            needs_review=False
        )

        assert summary.entity_id == "bug_001"
        assert summary.citation_count == 10
        assert summary.correction_count == 1
        assert summary.accuracy == 0.9
        assert summary.quality_score == 0.85
        assert summary.needs_review is False
