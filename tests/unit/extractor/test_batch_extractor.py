# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
BatchBugExtractor 单元测试
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from asc_ops.extractor.batch_extractor import (
    BatchBugExtractor,
    BatchExtractionStats,
    BatchExtractionResult,
)
from asc_ops.extractor.priority_scorer import BugPriorityItem
from asc_ops.extractor.bug_extractor import BugExtractionResult


class TestBatchBugExtractor:
    """BatchBugExtractor 测试"""

    def test_calculate_confidence_full_fields(self):
        """完整字段应得高分"""
        extractor = BatchBugExtractor(
            priority_scorer=Mock(),
            knowledge_storage=Mock(),
        )

        result = BugExtractionResult(
            bug_id="test",
            operator_id="Add",
            source_repo="repo",
            source_pr="1",
            bug_title="Test Bug",
            root_cause="This is a detailed root cause analysis with more than 20 chars",
            fix_pattern="This is a detailed fix pattern with more than 20 chars",
            trigger_conditions=["condition1", "condition2"],
            related_apis=["API1", "API2"],
            extraction_success=True,
        )

        confidence = extractor._calculate_confidence(result)
        assert confidence > 0.7

    def test_calculate_confidence_partial_fields(self):
        """部分字段应得中等分"""
        extractor = BatchBugExtractor(
            priority_scorer=Mock(),
            knowledge_storage=Mock(),
        )

        result = BugExtractionResult(
            bug_id="test",
            operator_id="Add",
            source_repo="repo",
            source_pr="1",
            bug_title="Test Bug",
            root_cause="Root cause here",
            fix_pattern=None,  # 缺失
            trigger_conditions=[],
            related_apis=[],
            extraction_success=True,
        )

        confidence = extractor._calculate_confidence(result)
        assert 0.3 < confidence < 0.7

    def test_calculate_confidence_empty(self):
        """无字段应得低分"""
        extractor = BatchBugExtractor(
            priority_scorer=Mock(),
            knowledge_storage=Mock(),
        )

        result = BugExtractionResult(
            bug_id="test",
            operator_id="Add",
            source_repo="repo",
            source_pr="1",
            bug_title="Test Bug",
            root_cause=None,
            fix_pattern=None,
            trigger_conditions=[],
            related_apis=[],
            extraction_success=False,
        )

        confidence = extractor._calculate_confidence(result)
        assert confidence < 0.3

    def test_batch_extraction_stats_to_dict(self):
        """测试统计转为字典"""
        stats = BatchExtractionStats(
            total=10,
            success=6,
            partial=2,
            failed=1,
            skipped=1,
            root_cause_filled=5,
            fix_pattern_filled=4,
            low_confidence=2,
            total_duration_seconds=12.345,
        )

        d = stats.to_dict()
        assert d["total"] == 10
        assert d["success"] == 6
        assert d["partial"] == 2
        assert d["failed"] == 1
        assert d["duration_seconds"] == 12.35


class TestBatchExtractionResult:
    """BatchExtractionResult 测试"""

    def test_result_structure(self):
        """测试结果结构"""
        stats = BatchExtractionStats(total=5, success=3)
        result = BatchExtractionResult(
            stats=stats,
            updated_bugs=[{"bug_id": "b1"}, {"bug_id": "b2"}],
            failed_bugs=[{"bug_id": "b3", "error": "failed"}],
        )

        assert result.stats.total == 5
        assert result.stats.success == 3
        assert len(result.updated_bugs) == 2
        assert len(result.failed_bugs) == 1
