# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
反馈接口测试
"""

import pytest
from datetime import datetime

from src.asc_ops.quality.feedback import (
    FeedbackAPI,
    CorrectionType,
    CorrectionReport,
    CorrectionStats,
)


class TestFeedbackAPI:
    """FeedbackAPI 测试"""

    @pytest.fixture
    def api(self):
        """创建反馈 API (使用 mock Redis)"""
        from src.asc_ops.storage.redis_client import RedisClient
        from src.asc_ops.quality.citation_tracker import CitationTracker
        redis_client = RedisClient(mock=True)
        citation_tracker = CitationTracker(redis_client)
        return FeedbackAPI(redis_client, citation_tracker)

    @pytest.fixture
    def tracker(self, api):
        return api.citation_tracker

    @pytest.mark.asyncio
    async def test_report_correction_wrong(self, api, tracker):
        """测试上报知识错误纠错"""
        result = await api.report_correction(
            entity_id="bug_001",
            entity_type="bug",
            correction_type="wrong",
            description="知识描述错误"
        )

        assert result["success"] is True
        assert result["entity_id"] == "bug_001"
        assert result["correction_type"] == "wrong"
        assert result["correction_count"] == 1
        assert result["threshold_exceeded"] is False

    @pytest.mark.asyncio
    async def test_report_correction_incomplete(self, api):
        """测试上报知识不完整纠错"""
        result = await api.report_correction(
            entity_id="opt_001",
            entity_type="optimization",
            correction_type="incomplete",
            description="缺少性能数据"
        )

        assert result["success"] is True
        assert result["correction_type"] == "incomplete"

    @pytest.mark.asyncio
    async def test_report_correction_outdated(self, api):
        """测试上报知识过时纠错"""
        result = await api.report_correction(
            entity_id="api_001",
            entity_type="api",
            correction_type="outdated",
            description="API 签名已变更"
        )

        assert result["success"] is True
        assert result["correction_type"] == "outdated"

    @pytest.mark.asyncio
    async def test_report_correction_misleading(self, api):
        """测试上报知识误导纠错"""
        result = await api.report_correction(
            entity_id="bug_002",
            entity_type="bug",
            correction_type="misleading"
        )

        assert result["success"] is True
        assert result["correction_type"] == "misleading"

    @pytest.mark.asyncio
    async def test_report_correction_unknown_type(self, api):
        """测试未知纠错类型 (应降级为 WRONG)"""
        result = await api.report_correction(
            entity_id="bug_003",
            entity_type="bug",
            correction_type="unknown_type"
        )

        assert result["success"] is True
        assert result["correction_type"] == "wrong"

    @pytest.mark.asyncio
    async def test_report_correction_accumulates(self, api):
        """测试纠错计数累积"""
        # 上报多个不同类型的纠错
        await api.report_correction("bug_004", "bug", "wrong")
        await api.report_correction("bug_004", "bug", "wrong")
        await api.report_correction("bug_004", "bug", "incomplete")

        stats = api.get_correction_stats("bug_004", "bug")
        assert stats.total_corrections == 3
        assert stats.by_type["wrong"] == 2
        assert stats.by_type["incomplete"] == 1

    @pytest.mark.asyncio
    async def test_report_correction_threshold_exceeded(self, api):
        """测试超过纠错阈值"""
        # 设置较低的阈值
        api.set_correction_threshold(3, "bug")

        # 上报 3 次纠错
        await api.report_correction("bug_005", "bug", "wrong")
        await api.report_correction("bug_005", "bug", "wrong")
        result = await api.report_correction("bug_005", "bug", "wrong")

        assert result["threshold_exceeded"] is True
        assert result["alert_triggered"] is True

    def test_get_total_corrections(self, api):
        """测试获取总纠错次数"""
        # 直接设置纠错计数 (不通过 report_correction)
        api._incr("ascendc:corrections:bug:bug_006:wrong")
        api._incr("ascendc:corrections:bug:bug_006:wrong")
        api._incr("ascendc:corrections:bug:bug_006:incomplete")

        total = api.get_total_corrections("bug_006", "bug")
        assert total == 3

    def test_get_correction_stats(self, api):
        """测试获取纠错统计"""
        # 设置一些纠错
        api._incr("ascendc:corrections:bug:bug_007:wrong")
        api._incr("ascendc:corrections:bug:bug_007:wrong")
        api._incr("ascendc:corrections:bug:bug_007:outdated")

        stats = api.get_correction_stats("bug_007", "bug")

        assert stats.entity_id == "bug_007"
        assert stats.entity_type == "bug"
        assert stats.total_corrections == 3
        assert stats.by_type["wrong"] == 2
        assert stats.by_type["outdated"] == 1

    def test_get_correction_reports(self, api):
        """测试获取纠错报告列表"""
        # 通过 report_correction 添加报告
        import asyncio
        asyncio.run(api.report_correction(
            entity_id="bug_008",
            entity_type="bug",
            correction_type="wrong",
            user_id="user_001",
            description="Test description",
            suggested_fix="Suggested fix here"
        ))

        reports = api.get_correction_reports("bug_008", "bug", limit=10)

        assert len(reports) == 1
        assert reports[0].entity_id == "bug_008"
        assert reports[0].correction_type == CorrectionType.WRONG
        assert reports[0].user_id == "user_001"
        assert reports[0].description == "Test description"
        assert reports[0].suggested_fix == "Suggested fix here"

    def test_normalize_entity_type(self, api):
        """测试实体类型规范化"""
        assert api._normalize_entity_type("bug") == "bug"
        assert api._normalize_entity_type("bugs") == "bug"
        assert api._normalize_entity_type("bugfix") == "bug"
        assert api._normalize_entity_type("optimization") == "optimization"
        assert api._normalize_entity_type("opt") == "optimization"
        assert api._normalize_entity_type("api") == "api"

    def test_set_correction_threshold(self, api):
        """测试设置纠错阈值"""
        api.set_correction_threshold(10, "bug")

        threshold = api._get_threshold("bug")
        assert threshold == 10

    def test_set_correction_threshold_global(self, api):
        """测试设置全局纠错阈值"""
        api.set_correction_threshold(20)

        threshold = api._get_threshold("optimization")
        assert threshold == 20


class TestCorrectionType:
    """CorrectionType 枚举测试"""

    def test_all_types_exist(self):
        """测试所有纠错类型都存在"""
        assert CorrectionType.WRONG.value == "wrong"
        assert CorrectionType.INCOMPLETE.value == "incomplete"
        assert CorrectionType.OUTDATED.value == "outdated"
        assert CorrectionType.MISLEADING.value == "misleading"


class TestCorrectionReport:
    """CorrectionReport 数据类测试"""

    def test_create_report(self):
        """测试创建纠错报告"""
        report = CorrectionReport(
            entity_id="bug_001",
            entity_type="bug",
            correction_type=CorrectionType.WRONG,
            user_id="user_001",
            description="Test description",
            suggested_fix="Fix suggestion",
            reported_at=datetime.now()
        )

        assert report.entity_id == "bug_001"
        assert report.correction_type == CorrectionType.WRONG
        assert report.description == "Test description"


class TestCorrectionStats:
    """CorrectionStats 数据类测试"""

    def test_create_stats(self):
        """测试创建纠错统计"""
        stats = CorrectionStats(
            entity_id="bug_001",
            entity_type="bug",
            total_corrections=5,
            by_type={"wrong": 3, "incomplete": 2},
            last_reported_at=datetime.now()
        )

        assert stats.total_corrections == 5
        assert stats.by_type["wrong"] == 3
        assert stats.by_type["incomplete"] == 2
