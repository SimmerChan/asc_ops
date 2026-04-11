# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
ExtractionQualityReporter 单元测试
"""

import pytest
from unittest.mock import Mock

from asc_ops.extractor.quality_reporter import (
    ExtractionQualityReporter,
    QualityReportStats,
    ProblemBug,
)


class TestQualityReportStats:
    """QualityReportStats 测试"""

    def test_all_zero(self):
        """无数据时应返回 0"""
        stats = QualityReportStats()
        assert stats.root_cause_fill_rate == 0.0
        assert stats.fix_pattern_fill_rate == 0.0
        assert stats.both_fill_rate == 0.0

    def test_full_bugs(self):
        """全部填充"""
        stats = QualityReportStats(
            total_bugs=10,
            bugs_with_root_cause=10,
            bugs_with_fix_pattern=10,
            bugs_with_both=10,
            bugs_with_neither=0,
        )
        assert stats.root_cause_fill_rate == 1.0
        assert stats.fix_pattern_fill_rate == 1.0
        assert stats.both_fill_rate == 1.0

    def test_partial_bugs(self):
        """部分填充"""
        stats = QualityReportStats(
            total_bugs=10,
            bugs_with_root_cause=7,
            bugs_with_fix_pattern=5,
            bugs_with_both=4,
            bugs_with_neither=2,
        )
        assert stats.root_cause_fill_rate == 0.7
        assert stats.fix_pattern_fill_rate == 0.5
        assert stats.both_fill_rate == 0.4

    def test_to_dict(self):
        """转换为字典"""
        stats = QualityReportStats(
            total_bugs=10,
            bugs_with_root_cause=7,
            bugs_with_fix_pattern=5,
            bugs_with_both=4,
            bugs_with_neither=2,
        )
        d = stats.to_dict()
        assert d["total_bugs"] == 10
        assert d["bugs_with_root_cause"] == 7
        assert d["root_cause_fill_rate"] == "70.0%"


class TestProblemBug:
    """ProblemBug 测试"""

    def test_problem_bug_creation(self):
        """问题记录创建"""
        bug = ProblemBug(
            bug_id="BUG-123",
            operator_id="Matmul",
            source_repo="ascend-cann",
            source_pr="456",
            bug_title="Memory leak",
            missing_fields=["root_cause", "fix_pattern"],
        )
        assert bug.bug_id == "BUG-123"
        assert bug.operator_id == "Matmul"
        assert len(bug.missing_fields) == 2


class TestExtractionQualityReporter:
    """ExtractionQualityReporter 测试"""

    def test_generate_report_no_client(self):
        """无 ChromaDB 客户端时返回空统计"""
        reporter = ExtractionQualityReporter(chroma_client=None)
        stats = reporter.generate_report()
        assert stats.total_bugs == 0

    def test_generate_report_empty_collection(self):
        """空 collection"""
        mock_chroma = Mock()
        mock_chroma.get_collection.return_value.get.return_value = {
            "ids": [],
            "documents": [],
            "metadatas": [],
        }

        reporter = ExtractionQualityReporter(chroma_client=mock_chroma)
        stats = reporter.generate_report()
        assert stats.total_bugs == 0

    def test_generate_report_with_data(self):
        """有数据的统计"""
        mock_chroma = Mock()
        mock_chroma.get_collection.return_value.get.return_value = {
            "ids": ["bug1", "bug2", "bug3"],
            "documents": ["doc1", "doc2", "doc3"],
            "metadatas": [
                {"has_root_cause": True, "has_fix_pattern": True},
                {"has_root_cause": True, "has_fix_pattern": False},
                {"has_root_cause": False, "has_fix_pattern": False},
            ],
        }

        reporter = ExtractionQualityReporter(chroma_client=mock_chroma)
        stats = reporter.generate_report()

        assert stats.total_bugs == 3
        assert stats.bugs_with_root_cause == 2
        assert stats.bugs_with_fix_pattern == 1
        assert stats.bugs_with_both == 1
        assert stats.bugs_with_neither == 1

    def test_get_problem_bugs_missing_both(self):
        """获取两者都缺失的问题记录"""
        mock_chroma = Mock()
        mock_chroma.get_collection.return_value.get.return_value = {
            "ids": ["bug1", "bug2", "bug3"],
            "documents": ["doc1", "doc2", "doc3"],
            "metadatas": [
                {
                    "has_root_cause": True,
                    "has_fix_pattern": True,
                    "operator_id": "Matmul",
                    "source_repo": "repo1",
                    "source_pr": "1",
                    "bug_title": "Bug 1",
                },
                {
                    "has_root_cause": False,
                    "has_fix_pattern": False,
                    "operator_id": "Add",
                    "source_repo": "repo2",
                    "source_pr": "2",
                    "bug_title": "Bug 2",
                },
                {
                    "has_root_cause": False,
                    "has_fix_pattern": True,
                    "operator_id": "Conv2d",
                    "source_repo": "repo3",
                    "source_pr": "3",
                    "bug_title": "Bug 3",
                },
            ],
        }

        reporter = ExtractionQualityReporter(chroma_client=mock_chroma)
        problems = reporter.get_problem_bugs(missing_both=True, limit=10)

        # 只应返回两者都缺失的 bug2
        assert len(problems) == 1
        assert problems[0].bug_id == "bug2"
        assert "root_cause" in problems[0].missing_fields
        assert "fix_pattern" in problems[0].missing_fields

    def test_get_problem_bugs_missing_either(self):
        """获取任一字段缺失的问题记录"""
        mock_chroma = Mock()
        mock_chroma.get_collection.return_value.get.return_value = {
            "ids": ["bug1", "bug2", "bug3"],
            "documents": ["doc1", "doc2", "doc3"],
            "metadatas": [
                {
                    "has_root_cause": True,
                    "has_fix_pattern": True,
                    "operator_id": "Matmul",
                    "source_repo": "repo1",
                    "source_pr": "1",
                    "bug_title": "Bug 1",
                },
                {
                    "has_root_cause": False,
                    "has_fix_pattern": False,
                    "operator_id": "Add",
                    "source_repo": "repo2",
                    "source_pr": "2",
                    "bug_title": "Bug 2",
                },
                {
                    "has_root_cause": False,
                    "has_fix_pattern": True,
                    "operator_id": "Conv2d",
                    "source_repo": "repo3",
                    "source_pr": "3",
                    "bug_title": "Bug 3",
                },
            ],
        }

        reporter = ExtractionQualityReporter(chroma_client=mock_chroma)
        problems = reporter.get_problem_bugs(missing_both=False, limit=10)

        # bug2 和 bug3 都缺失至少一个字段
        assert len(problems) == 2
        bug_ids = [p.bug_id for p in problems]
        assert "bug2" in bug_ids
        assert "bug3" in bug_ids

    def test_generate_markdown_report(self):
        """生成 Markdown 报告"""
        mock_chroma = Mock()
        mock_chroma.get_collection.return_value.get.return_value = {
            "ids": ["bug1", "bug2"],
            "documents": ["doc1", "doc2"],
            "metadatas": [
                {
                    "has_root_cause": True,
                    "has_fix_pattern": False,
                    "operator_id": "Matmul",
                    "source_repo": "repo1",
                    "source_pr": "1",
                    "bug_title": "Bug 1",
                },
                {
                    "has_root_cause": False,
                    "has_fix_pattern": False,
                    "operator_id": "Add",
                    "source_repo": "repo2",
                    "source_pr": "2",
                    "bug_title": "Bug 2",
                },
            ],
        }

        reporter = ExtractionQualityReporter(chroma_client=mock_chroma)
        markdown = reporter.generate_markdown_report(include_problems=True, problem_limit=10)

        assert "# Bug 知识抽取质量报告" in markdown
        assert "总记录数" in markdown
        assert "root_cause" in markdown
        assert "bug2" in markdown

    def test_print_summary(self):
        """打印摘要"""
        mock_chroma = Mock()
        mock_chroma.get_collection.return_value.get.return_value = {
            "ids": ["bug1"],
            "documents": ["doc1"],
            "metadatas": [
                {"has_root_cause": True, "has_fix_pattern": True},
            ],
        }

        reporter = ExtractionQualityReporter(chroma_client=mock_chroma)
        # 不应抛出异常
        reporter.print_summary()
