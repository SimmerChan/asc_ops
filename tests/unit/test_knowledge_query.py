# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
知识查询服务测试
"""

import pytest
from unittest.mock import MagicMock, patch
import asyncio

from src.asc_ops.knowledge_query import (
    KnowledgeQueryService,
    DevelopmentQueryResult,
    TroubleshootingResult,
    PossibleCause,
)


class TestKnowledgeQueryService:
    """知识查询服务测试"""

    def setup_method(self):
        """设置测试"""
        self.mock_chroma = MagicMock()
        self.mock_redis = MagicMock()
        self.service = KnowledgeQueryService(
            chroma_client=self.mock_chroma,
            redis_client=self.mock_redis,
        )

    def test_service_initialization(self):
        """服务初始化"""
        assert self.service._chroma is not None
        assert self.service._redis is not None
        assert self.service._storage is not None
        assert self.service._ranker is not None

    @pytest.mark.asyncio
    async def test_query_for_development_bug_only(self):
        """查询开发知识 - 仅 Bug"""
        self.mock_redis.smembers.return_value = {"BUG-ascend-cann-1234"}
        self.mock_redis.hgetall.return_value = {
            "bug_id": "BUG-ascend-cann-1234",
            "operator_id": "Matmul",
            "source_repo": "ascend-cann",
            "source_pr": "1234",
            "bug_title": "Memory leak in Matmul",
            "symptom": "High memory usage",
            "severity": "MAJOR",
            "category": "MEMORY",
            "root_cause": "Buffer not released",
            "trigger_conditions": "large input",
            "fix_pattern": "Added release()",
            "workarounds": "",
            "related_apis": "Matmul",
            "confidence": "0.8",
            "extraction_method": "LLM",
            "review_status": "approved",
        }

        result = await self.service.query_for_development(
            operator_name="Matmul",
            query_type="bug",
            limit=10,
        )

        assert isinstance(result, DevelopmentQueryResult)
        assert result.operator_name == "Matmul"
        assert result.query_type == "bug"
        assert len(result.bug_fixes) == 1
        assert result.bug_fixes[0].bug_title == "Memory leak in Matmul"
        assert len(result.optimizations) == 0

    @pytest.mark.asyncio
    async def test_query_for_development_optimization_only(self):
        """查询开发知识 - 仅优化"""
        self.mock_redis.smembers.return_value = set()
        self.mock_redis.hgetall.return_value = {}

        result = await self.service.query_for_development(
            operator_name="Matmul",
            query_type="optimization",
            limit=10,
        )

        assert isinstance(result, DevelopmentQueryResult)
        assert result.operator_name == "Matmul"
        assert result.query_type == "optimization"
        assert len(result.optimizations) == 0

    @pytest.mark.asyncio
    async def test_query_for_development_all(self):
        """查询开发知识 - 全部"""
        # Mock bug query
        self.mock_redis.smembers.side_effect = [
            {"BUG-ascend-cann-1234"},
            {"OPT-ascend-cann-5678"},
        ]
        self.mock_redis.hgetall.side_effect = [
            {
                "bug_id": "BUG-ascend-cann-1234",
                "operator_id": "Matmul",
                "source_repo": "ascend-cann",
                "source_pr": "1234",
                "bug_title": "Memory leak",
                "symptom": "High memory",
                "severity": "MAJOR",
                "category": "MEMORY",
                "root_cause": "Buffer not released",
                "trigger_conditions": "",
                "fix_pattern": "Added release()",
                "workarounds": "",
                "related_apis": "Matmul",
                "confidence": "0.8",
                "extraction_method": "LLM",
                "review_status": "approved",
            },
            {
                "opt_id": "OPT-ascend-cann-5678",
                "operator_id": "Matmul",
                "source_repo": "ascend-cann",
                "source_pr": "5678",
                "opt_title": "Memory optimization",
                "optimization_type": "memory",
                "optimization_description": "Reduced memory usage",
                "improvement_ratio": "0.3",
                "related_apis": "Matmul",
                "confidence": "0.7",
                "extraction_method": "LLM",
                "review_status": "approved",
            },
        ]

        result = await self.service.query_for_development(
            operator_name="Matmul",
            query_type="all",
            limit=10,
        )

        assert isinstance(result, DevelopmentQueryResult)
        assert result.operator_name == "Matmul"
        assert result.query_type == "all"

    @pytest.mark.asyncio
    async def test_query_for_troubleshooting(self):
        """查询问题排查"""
        self.mock_redis.smembers.return_value = set()
        self.mock_redis.hgetall.return_value = {}
        self.mock_chroma.get_collection.return_value.query.return_value = {
            "ids": [["BUG-1"]],
            "metadatas": [[{"operator_id": "Matmul"}]],
            "documents": [["Memory leak in Matmul"]],
        }

        result = await self.service.query_for_troubleshooting(
            symptom="Matmul crash",
            operator_name="Matmul",
            limit=5,
        )

        assert isinstance(result, TroubleshootingResult)
        assert result.symptom == "Matmul crash"

    @pytest.mark.asyncio
    async def test_query_api_exact_match(self):
        """精确查询 API"""
        self.mock_chroma.get_collection.return_value.get.return_value = {
            "ids": ["Exp"],
            "metadatas": [{
                "canonical_name": "Exp",
                "full_signature": "void Exp(Position2f pos)",
                "category": "tensor",
                "subcategory": "tensor creation",
                "description": "Create a tensor expression",
                "version_info": "1.0",
                "confidence": "1.0",
            }],
            "documents": ["Create a tensor expression"],
        }

        result = await self.service.query_api(api_name="Exp")

        assert len(result) == 1
        assert result[0].canonical_name == "Exp"

    @pytest.mark.asyncio
    async def test_query_api_semantic(self):
        """语义查询 API"""
        self.mock_chroma.get_collection.return_value.query.return_value = {
            "ids": [["Exp", "Log"]],
            "metadatas": [[
                {"canonical_name": "Exp", "category": "tensor"},
                {"canonical_name": "Log", "category": "tensor"},
            ]],
            "documents": [["Create exponential tensor", "Create log tensor"]],
        }

        result = await self.service.query_api(
            semantic_query="tensor creation functions",
            limit=10,
        )

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_query_api_with_category_filter(self):
        """按类别过滤查询 API"""
        self.mock_chroma.get_collection.return_value.get.return_value = {
            "ids": ["Matmul"],
            "metadatas": [{
                "canonical_name": "Matmul",
                "category": "compute",
                "subcategory": "matrix",
            }],
            "documents": ["Matrix multiplication"],
        }

        result = await self.service.query_api(
            api_name="Matmul",
            category="compute",
        )

        assert len(result) == 1
        assert result[0].category == "compute"

    @pytest.mark.asyncio
    async def test_query_api_not_found(self):
        """API 未找到"""
        self.mock_chroma.get_collection.return_value.get.return_value = {
            "ids": [],
            "metadatas": [],
            "documents": [],
        }

        result = await self.service.query_api(api_name="NonExistent")

        assert len(result) == 0

    def test_generate_checks(self):
        """生成建议检查项"""
        from src.asc_ops.models import BugFixKnowledge, BugSeverity, BugCategory

        bug = BugFixKnowledge(
            bug_id="BUG-1",
            operator_id="Matmul",
            source_repo="ascend-cann",
            source_pr="1234",
            bug_title="Memory leak",
            symptom="High memory",
            severity=BugSeverity.MAJOR,
            category=BugCategory.MEMORY,
            trigger_conditions=["large input", "empty tensor"],
            workarounds=["use smaller input"],
            related_apis=["Matmul"],
            confidence=0.8,
        )

        checks = self.service._generate_checks(bug)

        assert len(checks) > 0
        assert any("触发条件" in c for c in checks)


class TestDevelopmentQueryResult:
    """DevelopmentQueryResult 测试"""

    def test_result_creation(self):
        """创建结果"""
        from src.asc_ops.models import BugFixKnowledge, OptimizationKnowledge, BugSeverity, BugCategory

        bug = BugFixKnowledge(
            bug_id="BUG-1",
            operator_id="Matmul",
            source_repo="ascend-cann",
            source_pr="1234",
            bug_title="Memory leak",
            symptom="High memory",
            severity=BugSeverity.MAJOR,
            category=BugCategory.MEMORY,
        )

        result = DevelopmentQueryResult(
            operator_name="Matmul",
            query_type="all",
            total_count=2,
            bug_fixes=[bug],
            optimizations=[],
        )

        assert result.operator_name == "Matmul"
        assert result.total_count == 2
        assert len(result.bug_fixes) == 1


class TestTroubleshootingResult:
    """TroubleshootingResult 测试"""

    def test_result_creation(self):
        """创建结果"""
        cause = PossibleCause(
            bug_id="BUG-1",
            description="Memory leak",
            confidence=0.8,
            root_cause="Buffer not released",
            trigger_conditions=["large input"],
            suggested_fix="Added release()",
        )

        result = TroubleshootingResult(
            symptom="High memory",
            possible_causes=[cause],
        )

        assert result.symptom == "High memory"
        assert len(result.possible_causes) == 1
        assert result.possible_causes[0].root_cause == "Buffer not released"


class TestPossibleCause:
    """PossibleCause 测试"""

    def test_cause_creation(self):
        """创建可能原因"""
        cause = PossibleCause(
            bug_id="BUG-1",
            description="Memory leak in Matmul",
            confidence=0.85,
            root_cause="Buffer not properly released",
            trigger_conditions=["input size > 1024", "empty tensor"],
            suggested_fix="Call Release() after computation",
            suggested_checks=["Check buffer lifecycle", "Verify memory cleanup"],
        )

        assert cause.bug_id == "BUG-1"
        assert cause.confidence == 0.85
        assert len(cause.trigger_conditions) == 2
        assert len(cause.suggested_checks) == 2
