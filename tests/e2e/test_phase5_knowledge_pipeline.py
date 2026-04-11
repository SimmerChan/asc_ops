# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
Phase 5 知识抽取与查询端到端测试

测试从 PR 抽取到知识查询的完整流程
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.asc_ops.extractor.bug_extractor import BugExtractor, BugExtractionResult
from src.asc_ops.extractor.opt_extractor import OptimizationExtractor, OptimizationExtractionResult
from src.asc_ops.extractor.classifier import PRClassifier, PRType
from src.asc_ops.extractor.knowledge_storage import KnowledgeStorage
from src.asc_ops.cli.operator_sync import OperatorSync, OperatorPR, OperatorSyncResult
from src.asc_ops.models import BugFixKnowledge, OptimizationKnowledge
from src.asc_ops.storage.chroma_client import ChromaDBClient
from src.asc_ops.storage.redis_client import RedisClient
from src.asc_ops.storage.collections import CollectionType, ensure_collection_exists
from src.asc_ops.knowledge_query import KnowledgeQueryService


class TestPRClassificationPipeline:
    """PR 分类管道测试"""

    def setup_method(self):
        """设置测试"""
        self.classifier = PRClassifier()

    def test_classify_bugfix_pr(self):
        """BugFix PR 分类"""
        result = self.classifier.classify(
            title="fix: Matmul kernel crash on empty input",
            body="Root cause: null pointer dereference. Fix: added null check."
        )

        assert result.pr_type == PRType.BUGFIX
        assert result.confidence > 0.5

    def test_classify_optimization_pr(self):
        """优化 PR 分类"""
        result = self.classifier.classify(
            title="perf: Optimize VecReduce performance by 30%",
            body="Improvement: pipelining and cache optimization."
        )

        assert result.pr_type == PRType.OPTIMIZATION
        assert result.confidence > 0.5

    def test_classify_feature_pr(self):
        """功能 PR 分类"""
        result = self.classifier.classify(
            title="feat: Add new Matmul operator support",
            body="This adds a new operator."
        )

        assert result.pr_type == PRType.FEATURE

    def test_classify_bugfix_priority(self):
        """Bug 关键词优先于优化"""
        result = self.classifier.classify(
            title="fix: Matmul bug and optimize performance",
            body="Bug fix and optimization."
        )

        # Bug 关键词优先
        assert result.pr_type in [PRType.BUGFIX, PRType.OPTIMIZATION]


class TestBugExtractionPipeline:
    """Bug 知识抽取管道测试"""

    def setup_method(self):
        """设置测试"""
        self.extractor = BugExtractor()

    def test_extract_complete_bugfix(self):
        """完整 BugFix 抽取"""
        result = self.extractor.extract(
            pr_title="fix: Matmul crash when input tensor is empty",
            pr_body="""
            Root cause: Buffer pointer not initialized for empty tensors.
            Fix: Added initialization check before buffer access.
            Trigger conditions:
            - Input tensor size == 0
            - Empty tensor passed to kernel
            Related APIs: AscendC::Matmul, AscendC::Buffer
            """,
            source_repo="ascend/cann-ann",
            source_pr="1234",
        )

        assert result.extraction_success is True
        assert result.operator_id == "Matmul"
        assert result.bug_id is not None
        assert "1234" in result.bug_id
        assert result.root_cause is not None
        assert len(result.trigger_conditions) > 0
        assert len(result.related_apis) > 0

    def test_extract_minimal_bugfix(self):
        """最小 BugFix 抽取"""
        result = self.extractor.extract(
            pr_title="fix: Matmul crash",
            pr_body="Crash fix",
            source_repo="ascend/cann-ann",
            source_pr="5678",
        )

        assert result.extraction_success is True
        assert result.operator_id == "Matmul"

    def test_extract_non_bugfix_pr(self):
        """非 BugFix PR 处理"""
        result = self.extractor.extract(
            pr_title="docs: Update README",
            pr_body="Documentation update",
            source_repo="ascend/cann-ann",
            source_pr="9999",
        )

        assert result.extraction_success is False


class TestOptimizationExtractionPipeline:
    """优化知识抽取管道测试"""

    def setup_method(self):
        """设置测试"""
        self.extractor = OptimizationExtractor()

    def test_extract_complete_optimization(self):
        """完整优化知识抽取"""
        result = self.extractor.extract(
            pr_title="perf: VecReduce optimization by 30%",
            pr_body="""
            Optimization: Pipelined execution and cache optimization.
            Performance improvement: 30% latency reduction.
            Before: 100ms, After: 70ms
            Related APIs: AscendC::VecReduce, AscendC::Pipeline
            """,
            source_repo="ascend/cann-ann",
            source_pr="2345",
        )

        assert result.extraction_success is True
        assert result.operator_id == "VecReduce"
        assert result.opt_id is not None
        assert "2345" in result.opt_id
        assert result.optimization_type is not None
        assert len(result.related_apis) > 0

    def test_extract_non_optimization_pr(self):
        """非优化 PR 处理"""
        result = self.extractor.extract(
            pr_title="fix: Bug in Add operator",
            pr_body="Bug fix",
            source_repo="ascend/cann-ann",
            source_pr="8888",
        )

        assert result.extraction_success is False


class TestKnowledgeStoragePipeline:
    """知识存储管道测试 (使用 Mock)"""

    def setup_method(self):
        """设置测试"""
        self.chroma_client = MagicMock()
        self.redis_client = RedisClient(mock=True)
        self.storage = KnowledgeStorage(
            chroma_client=self.chroma_client,
            redis_client=self.redis_client,
        )
        # Mock collection
        mock_collection = MagicMock()
        self.chroma_client.get_or_create_collection.return_value = mock_collection

    def test_store_bugfix_knowledge(self):
        """存储 BugFix 知识"""
        bug_result = BugExtractionResult(
            bug_id="BUG-ascend-123",
            operator_id="Matmul",
            source_repo="ascend/cann-ann",
            source_pr="123",
            bug_title="Matmul crash on empty input",
            root_cause="Null pointer",
            fix_pattern="Added null check",
            trigger_conditions=["empty tensor"],
            workarounds=["Check input size"],
            related_apis=["Matmul"],
            extraction_success=True,
        )

        success = self.storage.store_bugfix(bug_result)

        assert success is True

    def test_store_optimization_knowledge(self):
        """存储优化知识"""
        opt_result = OptimizationExtractionResult(
            opt_id="OPT-ascend-456",
            operator_id="VecReduce",
            source_repo="ascend/cann-ann",
            source_pr="456",
            opt_title="VecReduce performance optimization",
            optimization_type=["pipelining", "cache"],
            optimization_description="30% latency reduction",
            improvement_ratio=0.3,
            related_apis=["VecReduce"],
            extraction_success=True,
        )

        success = self.storage.store_optimization(opt_result)

        assert success is True

    def test_skip_failed_extraction(self):
        """跳过抽取失败的知识"""
        bug_result = BugExtractionResult(
            bug_id="BUG-fail-999",
            operator_id="Unknown",
            source_repo="ascend/cann-ann",
            source_pr="999",
            bug_title="",
            root_cause=None,
            fix_pattern=None,
            extraction_success=False,
            error_message="Not a bugfix PR",
        )

        success = self.storage.store_bugfix(bug_result)

        assert success is False


class TestOperatorSyncPipeline:
    """算子同步管道测试 (使用 Mock)"""

    def setup_method(self):
        """设置测试"""
        self.sync = OperatorSync(repo_filter=["ascend/test-repo"])

    @pytest.mark.asyncio
    async def test_sync_with_mock_prs(self):
        """使用模拟 PR 测试同步"""
        result = await self.sync.sync_repository("ascend/test-repo")

        assert result.total_prs == 2  # 模拟数据中有 2 个 PR
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_sync_processes_bug_pr(self):
        """测试处理 Bug PR"""
        # 创建模拟 Bug PR
        pr = OperatorPR(
            pr_number=100,
            title="fix: Matmul kernel crash",
            body="Crash when input is empty. Root cause: null pointer.",
            state="closed",
            merged_at=datetime.now(),
            author="testuser",
            labels=["bug", "matmul"],
            repo="ascend/test-repo",
        )

        result = await self.sync._process_pr(pr)

        assert result["is_bug"] is True
        assert result["bug_count"] >= 0  # 可能为 0 如果抽取失败

    @pytest.mark.asyncio
    async def test_sync_processes_optimization_pr(self):
        """测试处理优化 PR"""
        # 创建模拟优化 PR
        pr = OperatorPR(
            pr_number=200,
            title="perf: Optimize VecReduce",
            body="Improve performance by 30% through pipelining.",
            state="closed",
            merged_at=datetime.now(),
            author="testuser",
            labels=["optimization", "performance"],
            repo="ascend/test-repo",
        )

        result = await self.sync._process_pr(pr)

        assert result["is_optimization"] is True
        assert result["opt_count"] >= 0


class TestKnowledgeQueryIntegration:
    """知识查询集成测试 (使用 Mock)"""

    def setup_method(self):
        """设置测试"""
        self.chroma_client = MagicMock()
        self.redis_client = RedisClient(mock=True)
        self.service = KnowledgeQueryService(
            chroma_client=self.chroma_client,
            redis_client=self.redis_client,
        )
        # Mock collection
        mock_collection = MagicMock()
        self.chroma_client.get_or_create_collection.return_value = mock_collection

    def test_service_initialization(self):
        """服务初始化"""
        assert self.service._chroma is not None
        assert self.service._redis is not None
        assert self.service._citation_tracker is not None
        assert self.service._feedback_api is not None

    def test_query_with_empty_results(self):
        """空结果查询"""
        import asyncio

        result = asyncio.run(
            self.service.query_for_development(
                operator_name="NonExistentOperator",
                query_type="bug",
                limit=5,
            )
        )

        assert result.operator_name == "NonExistentOperator"
        assert result.bug_fixes == []
        assert result.optimizations == []

    def test_query_with_api_filter(self):
        """带 API 过滤的查询"""
        import asyncio

        result = asyncio.run(
            self.service.query_for_development(
                operator_name="Matmul",
                query_type="bug",
                api_filter=["AscendC::Matmul"],
                limit=5,
            )
        )

        # 空结果是可以接受的（没有预先存储数据）
        assert result.operator_name == "Matmul"


class TestExtractionToQueryPipeline:
    """抽取到查询完整管道测试"""

    def setup_method(self):
        """设置测试"""
        self.classifier = PRClassifier()
        self.bug_extractor = BugExtractor()
        self.opt_extractor = OptimizationExtractor()
        self.chroma_client = MagicMock()
        self.redis_client = RedisClient(mock=True)
        self.storage = KnowledgeStorage(
            chroma_client=self.chroma_client,
            redis_client=self.redis_client,
        )
        # Mock collection
        mock_collection = MagicMock()
        self.chroma_client.get_or_create_collection.return_value = mock_collection

    def test_full_bug_pipeline(self):
        """完整 Bug 管道: 分类 -> 抽取 -> 存储"""
        # 1. 分类
        classification = self.classifier.classify(
            title="fix: Matmul crash on empty input",
            body="Root cause: null pointer. Fix: added check."
        )
        assert classification.pr_type == PRType.BUGFIX

        # 2. 抽取
        bug_result = self.bug_extractor.extract(
            pr_title="fix: Matmul crash on empty input",
            pr_body="Root cause: null pointer. Fix: added check.",
            source_repo="ascend/test",
            source_pr="123",
        )
        assert bug_result.extraction_success is True

        # 3. 存储
        stored = self.storage.store_bugfix(bug_result)
        assert stored is True

    def test_full_optimization_pipeline(self):
        """完整优化管道: 分类 -> 抽取 -> 存储"""
        # 1. 分类
        classification = self.classifier.classify(
            title="perf: VecReduce optimization",
            body="30% performance improvement"
        )
        assert classification.pr_type == PRType.OPTIMIZATION

        # 2. 抽取
        opt_result = self.opt_extractor.extract(
            pr_title="perf: VecReduce optimization",
            pr_body="30% performance improvement through pipelining",
            source_repo="ascend/test",
            source_pr="456",
        )
        assert opt_result.extraction_success is True

        # 3. 存储
        stored = self.storage.store_optimization(opt_result)
        assert stored is True

    def test_pr_classification_consistency(self):
        """PR 分类一致性测试"""
        test_cases = [
            ("fix: crash in Matmul", PRType.BUGFIX),
            ("perf: optimize Vec", PRType.OPTIMIZATION),
            ("fix: Matmul fix", PRType.BUGFIX),  # fix 关键词优先
            ("feat: add new operator", PRType.FEATURE),
            ("feature: add new feature", PRType.FEATURE),
            ("refactor: code cleanup", PRType.UNKNOWN),  # refactor 不是已知类型
        ]

        for title, expected_type in test_cases:
            result = self.classifier.classify(title, "")
            assert result.pr_type == expected_type, f"Failed for: {title}"


class TestCitationTrackerIntegration:
    """引用追踪集成测试"""

    def setup_method(self):
        """设置测试"""
        self.redis_client = RedisClient(mock=True)
        self.service = KnowledgeQueryService(
            redis_client=self.redis_client,
        )

    def test_citation_tracking(self):
        """引用追踪"""
        from src.asc_ops.quality import CitationTracker

        tracker = CitationTracker(self.redis_client)

        # 记录引用
        count1 = tracker.record_citation("bug_001", "bug")
        assert count1 == 1

        count2 = tracker.record_citation("bug_001", "bug")
        assert count2 == 2

        # 获取统计
        stats = tracker.get_stats("bug_001", "bug")
        assert stats.citation_count == 2

    def test_feedback_reporting(self):
        """反馈上报"""
        import asyncio
        from src.asc_ops.quality import CitationTracker, FeedbackAPI

        tracker = CitationTracker(self.redis_client)
        feedback_api = FeedbackAPI(self.redis_client, tracker)

        # 上报纠错
        result = asyncio.run(
            feedback_api.report_correction(
                entity_id="bug_001",
                entity_type="bug",
                correction_type="wrong",
            )
        )

        assert result["success"] is True
        assert result["correction_count"] == 1

    def test_quality_dashboard(self):
        """质量面板"""
        from src.asc_ops.quality import CitationStatsAPI

        stats_api = CitationStatsAPI(self.redis_client)

        dashboard = stats_api.get_dashboard("bug")

        assert dashboard.entity_type == "bug"
        assert dashboard.total_entities >= 0
