# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
PriorityScorer 单元测试
"""

import pytest
from unittest.mock import Mock, MagicMock

from asc_ops.extractor.priority_scorer import (
    PriorityScorer,
    BugPriorityItem,
    CORE_OPERATORS,
)


class TestPriorityScorer:
    """PriorityScorer 测试"""

    def test_calculate_operator_score_core_operators(self):
        """核心算子应该得1.0分"""
        scorer = PriorityScorer()

        for op in ["Matmul", "MatMul", "Add", "Conv2d", "Reduce", "Transpose"]:
            score = scorer._calculate_operator_score(op)
            assert score == 1.0, f"Operator {op} should score 1.0, got {score}"

    def test_calculate_operator_score_non_core_operators(self):
        """非核心算子应该得0.5分"""
        scorer = PriorityScorer()

        for op in ["CustomOp", "MyOperator", "unknown"]:
            score = scorer._calculate_operator_score(op)
            assert score == 0.5, f"Operator {op} should score 0.5, got {score}"

    def test_calculate_operator_score_aliases(self):
        """算子别名应该正确映射"""
        scorer = PriorityScorer()

        # 小写别名
        assert scorer._calculate_operator_score("matmul") == 1.0
        assert scorer._calculate_operator_score("conv2d") == 1.0

        # 变体
        assert scorer._calculate_operator_score("TBMM") == 1.0
        assert scorer._calculate_operator_score("bmm") == 1.0

    def test_calculate_missing_field_score_both_missing(self):
        """两者都缺失得1.0分"""
        scorer = PriorityScorer()

        score = scorer._calculate_missing_field_score(False, False)
        assert score == 1.0

    def test_calculate_missing_field_score_one_missing(self):
        """只有部分缺失得0.5分"""
        scorer = PriorityScorer()

        score = scorer._calculate_missing_field_score(True, False)
        assert score == 0.5

        score = scorer._calculate_missing_field_score(False, True)
        assert score == 0.5

    def test_calculate_missing_field_score_none_missing(self):
        """无缺失得0分"""
        scorer = PriorityScorer()

        score = scorer._calculate_missing_field_score(True, True)
        assert score == 0.0

    def test_bug_priority_item_sorting(self):
        """BugPriorityItem 应该按 priority_score 降序排序"""
        bug1 = BugPriorityItem(
            bug_id="bug1",
            operator_id="Add",
            source_repo="repo",
            source_pr="1",
            bug_title="Bug 1",
            has_root_cause=True,
            has_fix_pattern=True,
            priority_score=0.3
        )
        bug2 = BugPriorityItem(
            bug_id="bug2",
            operator_id="Matmul",
            source_repo="repo",
            source_pr="2",
            bug_title="Bug 2",
            has_root_cause=False,
            has_fix_pattern=False,
            priority_score=0.8
        )

        # bug2 分数更高，应该排在前面
        sorted_bugs = sorted([bug1, bug2])
        assert sorted_bugs[0].bug_id == "bug2"
        assert sorted_bugs[1].bug_id == "bug1"

    def test_priority_queue_empty_collection(self):
        """空 collection 应该返回空队列"""
        mock_chroma = Mock()
        mock_chroma.get_collection.return_value.get.return_value = {
            "ids": [],
            "documents": [],
            "metadatas": []
        }

        scorer = PriorityScorer(chroma_client=mock_chroma)
        queue = scorer.calculate_priority_queue()

        assert queue == []

    def test_priority_queue_with_mock_data(self):
        """使用模拟数据测试优先级计算"""
        mock_chroma = Mock()
        mock_chroma.get_collection.return_value.get.return_value = {
            "ids": ["bug1", "bug2", "bug3"],
            "documents": ["doc1", "doc2", "doc3"],
            "metadatas": [
                {
                    "operator_id": "Matmul",  # 核心算子
                    "source_repo": "repo1",
                    "source_pr": "1",
                    "bug_title": "Bug 1",
                    "has_root_cause": False,  # 缺失
                    "has_fix_pattern": False,  # 缺失
                },
                {
                    "operator_id": "CustomOp",  # 非核心算子
                    "source_repo": "repo2",
                    "source_pr": "2",
                    "bug_title": "Bug 2",
                    "has_root_cause": True,  # 有
                    "has_fix_pattern": False,  # 部分缺失
                },
                {
                    "operator_id": "Add",  # 核心算子
                    "source_repo": "repo3",
                    "source_pr": "3",
                    "bug_title": "Bug 3",
                    "has_root_cause": True,  # 有
                    "has_fix_pattern": True,  # 有
                },
            ]
        }

        scorer = PriorityScorer(chroma_client=mock_chroma, redis_client=Mock())

        # 不传 citation_tracker，使用 mock redis
        # 引用次数为0
        queue = scorer.calculate_priority_queue()

        assert len(queue) == 3

        # bug1 (核心算子 + 两者缺失) 分数最高
        assert queue[0].bug_id == "bug1"
        assert queue[0].has_root_cause == False
        assert queue[0].has_fix_pattern == False

        # bug3 (核心算子 + 无缺失) 分数次之（因为没有引用）
        # 但 MissingFieldScore = 0，所以排在后面
        assert queue[1].bug_id == "bug2"  # 部分缺失 + 非核心
        assert queue[2].bug_id == "bug3"  # 无缺失

    def test_citation_normalization(self):
        """引用次数应该被正确归一化"""
        mock_chroma = Mock()
        mock_chroma.get_collection.return_value.get.return_value = {
            "ids": ["bug1", "bug2"],
            "documents": ["doc1", "doc2"],
            "metadatas": [
                {
                    "operator_id": "Add",
                    "source_repo": "repo1",
                    "source_pr": "1",
                    "bug_title": "Bug 1",
                    "has_root_cause": False,
                    "has_fix_pattern": False,
                },
                {
                    "operator_id": "Add",
                    "source_repo": "repo2",
                    "source_pr": "2",
                    "bug_title": "Bug 2",
                    "has_root_cause": False,
                    "has_fix_pattern": False,
                },
            ]
        }

        # 模拟 citation_tracker 返回不同的引用次数
        mock_tracker = Mock()
        def mock_get_stats(bug_id, entity_type):
            if bug_id == "bug1":
                mock_stats = Mock()
                mock_stats.citation_count = 100
                return mock_stats
            else:
                mock_stats = Mock()
                mock_stats.citation_count = 50
                return mock_stats

        mock_tracker.get_stats.side_effect = mock_get_stats

        scorer = PriorityScorer(chroma_client=mock_chroma, citation_tracker=mock_tracker)
        queue = scorer.calculate_priority_queue()

        # bug1 引用100次，bug2引用50次
        # 归一化后 bug1 的 citation_score = 1.0, bug2 = 0.5
        # 由于两者都是核心算子+两者缺失，分数应该不同
        assert queue[0].citation_count == 100
        assert queue[1].citation_count == 50

    def test_priority_score_calculation(self):
        """验证优先级分数计算公式"""
        scorer = PriorityScorer()

        # CitationScore = 0.4 * citation/normalized
        # OperatorScore = 0.3 * operator_score
        # MissingFieldScore = 0.3 * missing_score

        # 最高分情况: 引用最多(1.0) + 核心算子(1.0) + 两者缺失(1.0)
        max_score = 0.4 * 1.0 + 0.3 * 1.0 + 0.3 * 1.0
        assert max_score == 1.0

        # 最低分情况: 无引用(0) + 非核心(0.5) + 无缺失(0)
        min_score = 0.4 * 0 + 0.3 * 0.5 + 0.3 * 0
        assert min_score == 0.15


class TestBugPriorityItem:
    """BugPriorityItem 测试"""

    def test_default_values(self):
        """测试默认值"""
        bug = BugPriorityItem(
            bug_id="test",
            operator_id="Add",
            source_repo="repo",
            source_pr="1",
            bug_title="Test",
            has_root_cause=True,
            has_fix_pattern=True,
        )

        assert bug.citation_count == 0
        assert bug.priority_score == 0.0
        assert bug.priority_rank == 0

    def test_sorting(self):
        """测试排序"""
        bugs = [
            BugPriorityItem("b1", "op", "r", "1", "t", True, True, priority_score=0.2),
            BugPriorityItem("b2", "op", "r", "2", "t", True, True, priority_score=0.8),
            BugPriorityItem("b3", "op", "r", "3", "t", True, True, priority_score=0.5),
        ]

        sorted_bugs = sorted(bugs)

        assert sorted_bugs[0].bug_id == "b2"  # 0.8
        assert sorted_bugs[1].bug_id == "b3"  # 0.5
        assert sorted_bugs[2].bug_id == "b1"  # 0.2
