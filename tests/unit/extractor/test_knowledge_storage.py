# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
知识存储模块测试
"""

import pytest
from unittest.mock import MagicMock

from src.asc_ops.extractor.knowledge_storage import KnowledgeStorage
from src.asc_ops.extractor.bug_extractor import BugExtractionResult
from src.asc_ops.extractor.opt_extractor import OptimizationExtractionResult


class TestKnowledgeStorage:
    """知识存储测试"""

    def setup_method(self):
        """设置测试"""
        self.mock_chroma = MagicMock()
        self.mock_redis = MagicMock()
        self.storage = KnowledgeStorage(
            chroma_client=self.mock_chroma,
            redis_client=self.mock_redis,
        )

    def test_store_bugfix_success(self):
        """成功存储 BugFix"""
        result = BugExtractionResult(
            bug_id="BUG-ascend-cann-1234",
            operator_id="Matmul",
            source_repo="ascend-cann",
            source_pr="1234",
            bug_title="Memory leak in Matmul",
            root_cause="Buffer not released",
            fix_pattern="Added release() call",
            trigger_conditions=["large input"],
            workarounds=["use smaller input"],
            related_apis=["Matmul", "Buffer"],
            extraction_success=True,
        )

        success = self.storage.store_bugfix(result)

        assert success is True
        self.mock_chroma.add.assert_called_once()
        self.mock_redis.hset.assert_called_once()
        self.mock_redis.sadd.assert_called_once()

    def test_store_bugfix_failure_skips_storage(self):
        """抽取失败的 BugFix 跳过存储"""
        result = BugExtractionResult(
            bug_id="BUG-ascend-cann-1234",
            operator_id="Matmul",
            source_repo="ascend-cann",
            source_pr="1234",
            bug_title="Memory leak in Matmul",
            root_cause=None,
            fix_pattern=None,
            extraction_success=False,
            error_message="Not a bugfix PR",
        )

        success = self.storage.store_bugfix(result)

        assert success is False
        self.mock_chroma.add.assert_not_called()
        self.mock_redis.hset.assert_not_called()

    def test_store_optimization_success(self):
        """成功存储 Optimization"""
        result = OptimizationExtractionResult(
            opt_id="OPT-ascend-cann-5678",
            operator_id="VecReduce",
            source_repo="ascend-cann",
            source_pr="5678",
            opt_title="Pipeline optimization",
            optimization_type=["pipeline"],
            optimization_description="Enabled pipelining",
            improvement_ratio=0.3,
            before_metrics={"latency": "100ms"},
            after_metrics={"latency": "70ms"},
            related_apis=["VecReduce"],
            extraction_success=True,
        )

        success = self.storage.store_optimization(result)

        assert success is True
        self.mock_chroma.add.assert_called_once()
        self.mock_redis.hset.assert_called_once()
        self.mock_redis.sadd.assert_called_once()

    def test_store_optimization_failure_skips_storage(self):
        """抽取失败的 Optimization 跳过存储"""
        result = OptimizationExtractionResult(
            opt_id="OPT-ascend-cann-5678",
            operator_id="VecReduce",
            source_repo="ascend-cann",
            source_pr="5678",
            opt_title="Pipeline optimization",
            optimization_type=[],
            optimization_description=None,
            extraction_success=False,
            error_message="Not an optimization PR",
        )

        success = self.storage.store_optimization(result)

        assert success is False
        self.mock_chroma.add.assert_not_called()
        self.mock_redis.hset.assert_not_called()

    def test_store_bugfix_without_chroma(self):
        """没有 ChromaDB 时只存 Redis"""
        storage = KnowledgeStorage(chroma_client=None, redis_client=self.mock_redis)

        result = BugExtractionResult(
            bug_id="BUG-ascend-cann-1234",
            operator_id="Matmul",
            source_repo="ascend-cann",
            source_pr="1234",
            bug_title="Memory leak in Matmul",
            root_cause="Buffer not released",
            fix_pattern="Added release()",
            extraction_success=True,
        )

        success = storage.store_bugfix(result)

        assert success is True
        self.mock_chroma.add.assert_not_called()
        self.mock_redis.hset.assert_called_once()

    def test_store_bugfix_without_redis(self):
        """没有 Redis 时只存 ChromaDB"""
        storage = KnowledgeStorage(chroma_client=self.mock_chroma, redis_client=None)

        result = BugExtractionResult(
            bug_id="BUG-ascend-cann-1234",
            operator_id="Matmul",
            source_repo="ascend-cann",
            source_pr="1234",
            bug_title="Memory leak in Matmul",
            root_cause="Buffer not released",
            fix_pattern="Added release()",
            extraction_success=True,
        )

        success = storage.store_bugfix(result)

        assert success is True
        self.mock_chroma.add.assert_called_once()
        self.mock_redis.hset.assert_not_called()

    def test_generate_bugfix_text(self):
        """生成 BugFix 向量化文本"""
        result = BugExtractionResult(
            bug_id="BUG-ascend-cann-1234",
            operator_id="Matmul",
            source_repo="ascend-cann",
            source_pr="1234",
            bug_title="Memory leak in Matmul",
            root_cause="Buffer not released",
            fix_pattern="Added release()",
            trigger_conditions=["large input", "empty tensor"],
            related_apis=["Matmul", "Buffer"],
            extraction_success=True,
        )

        text = self.storage._generate_bugfix_text(result)

        assert "Memory leak in Matmul" in text
        assert "Root cause:" in text
        assert "Fix:" in text
        assert "Trigger conditions:" in text
        assert "Related APIs:" in text

    def test_generate_optimization_text(self):
        """生成 Optimization 向量化文本"""
        result = OptimizationExtractionResult(
            opt_id="OPT-ascend-cann-5678",
            operator_id="VecReduce",
            source_repo="ascend-cann",
            source_pr="5678",
            opt_title="Pipeline optimization for VecReduce",
            optimization_type=["pipeline", "memory"],
            optimization_description="Enabled pipelining",
            improvement_ratio=0.3,
            related_apis=["VecReduce"],
            extraction_success=True,
        )

        text = self.storage._generate_optimization_text(result)

        assert "Pipeline optimization for VecReduce" in text
        assert "Optimization type:" in text
        assert "Description:" in text
        assert "Improvement:" in text
        assert "Related APIs:" in text

    def test_bugfix_to_metadata(self):
        """BugFix 转换为 metadata"""
        result = BugExtractionResult(
            bug_id="BUG-ascend-cann-1234",
            operator_id="Matmul",
            source_repo="ascend-cann",
            source_pr="1234",
            bug_title="Memory leak",
            root_cause="Buffer not released",
            fix_pattern="Added release()",
            trigger_conditions=["large input"],
            workarounds=[],
            related_apis=["Matmul"],
            extraction_success=True,
        )

        metadata = self.storage._bugfix_to_metadata(result)

        assert metadata["type"] == "bugfix"
        assert metadata["operator_id"] == "Matmul"
        assert metadata["source_repo"] == "ascend-cann"
        assert metadata["has_root_cause"] is True
        assert metadata["has_fix_pattern"] is True
        assert metadata["trigger_count"] == 1
        assert metadata["workaround_count"] == 0

    def test_optimization_to_metadata(self):
        """Optimization 转换为 metadata"""
        result = OptimizationExtractionResult(
            opt_id="OPT-ascend-cann-5678",
            operator_id="VecReduce",
            source_repo="ascend-cann",
            source_pr="5678",
            opt_title="Pipeline optimization",
            optimization_type=["pipeline", "memory"],
            optimization_description="Enabled pipelining",
            improvement_ratio=0.3,
            before_metrics={"latency": "100ms"},
            after_metrics={"latency": "70ms"},
            related_apis=["VecReduce"],
            extraction_success=True,
        )

        metadata = self.storage._optimization_to_metadata(result)

        assert metadata["type"] == "optimization"
        assert metadata["operator_id"] == "VecReduce"
        assert metadata["source_repo"] == "ascend-cann"
        assert metadata["has_improvement_ratio"] is True
        assert metadata["improvement_ratio"] == "0.3"
        assert metadata["has_metrics"] is True

    def test_is_duplicate_bugfix(self):
        """检查 BugFix 是否重复"""
        self.mock_redis.exists.return_value = True

        is_dup = self.storage.is_duplicate("ascend-cann", "1234")

        assert is_dup is True
        self.mock_redis.exists.assert_any_call("bugfix:lookup:ascend-cann:1234")

    def test_is_duplicate_optimization(self):
        """检查 Optimization 是否重复"""
        self.mock_redis.exists.side_effect = [False, True]

        is_dup = self.storage.is_duplicate("ascend-cann", "5678")

        assert is_dup is True
        self.mock_redis.exists.assert_any_call("optimization:lookup:ascend-cann:5678")

    def test_is_not_duplicate(self):
        """不重复"""
        self.mock_redis.exists.return_value = False

        is_dup = self.storage.is_duplicate("ascend-cann", "9999")

        assert is_dup is False

    def test_is_duplicate_without_redis(self):
        """没有 Redis 时不重复"""
        storage = KnowledgeStorage(chroma_client=self.mock_chroma, redis_client=None)

        is_dup = storage.is_duplicate("ascend-cann", "1234")

        assert is_dup is False

    def test_mark_processed(self):
        """标记已处理"""
        self.storage.mark_processed("ascend-cann", "1234", "bugfix")

        self.mock_redis.set.assert_called_once_with(
            "bugfix:lookup:ascend-cann:1234", "1"
        )

    def test_get_bugfix_count_all(self):
        """获取所有 BugFix 数量"""
        self.mock_redis.scan_iter.side_effect = lambda pattern: iter([
            "bugfix:BUG-1",
            "bugfix:BUG-2",
            "bugfix:lookup:ascend-cann:1234",
        ])

        count = self.storage.get_bugfix_count()

        assert count == 2

    def test_get_bugfix_count_by_operator(self):
        """按算子获取 BugFix 数量"""
        self.mock_redis.scard.return_value = 5

        count = self.storage.get_bugfix_count(operator_id="Matmul")

        assert count == 5
        self.mock_redis.scard.assert_called_once_with("operator:Matmul:bugs")

    def test_get_optimization_count_all(self):
        """获取所有 Optimization 数量"""
        self.mock_redis.scan_iter.side_effect = lambda pattern: iter([
            "optimization:OPT-1",
            "optimization:OPT-2",
            "optimization:OPT-3",
            "optimization:lookup:ascend-cann:5678",
        ])

        count = self.storage.get_optimization_count()

        assert count == 3

    def test_get_optimization_count_by_operator_and_type(self):
        """按算子和类型获取 Optimization 数量"""
        self.mock_redis.scard.return_value = 3

        count = self.storage.get_optimization_count(operator_id="Matmul", opt_type="memory")

        assert count == 3
        self.mock_redis.scard.assert_called_once_with("operator:Matmul:opts:memory")

    def test_store_bugfix_redis_content(self):
        """BugFix Redis 存储内容"""
        result = BugExtractionResult(
            bug_id="BUG-ascend-cann-1234",
            operator_id="Matmul",
            source_repo="ascend-cann",
            source_pr="1234",
            bug_title="Memory leak",
            root_cause="Buffer not released",
            fix_pattern="Added release()",
            trigger_conditions=["large input"],
            workarounds=["use smaller input"],
            related_apis=["Matmul"],
            extraction_success=True,
        )

        self.storage.store_bugfix(result)

        call_args = self.mock_redis.hset.call_args
        mapping = call_args[1]["mapping"]

        assert mapping["bug_id"] == "BUG-ascend-cann-1234"
        assert mapping["operator_id"] == "Matmul"
        assert mapping["root_cause"] == "Buffer not released"
        assert mapping["fix_pattern"] == "Added release()"
        assert mapping["trigger_conditions"] == "large input"
        assert mapping["workarounds"] == "use smaller input"

    def test_store_optimization_redis_content(self):
        """Optimization Redis 存储内容"""
        result = OptimizationExtractionResult(
            opt_id="OPT-ascend-cann-5678",
            operator_id="VecReduce",
            source_repo="ascend-cann",
            source_pr="5678",
            opt_title="Pipeline optimization",
            optimization_type=["pipeline", "memory"],
            optimization_description="Enabled pipelining",
            improvement_ratio=0.3,
            related_apis=["VecReduce"],
            extraction_success=True,
        )

        self.storage.store_optimization(result)

        call_args = self.mock_redis.hset.call_args
        mapping = call_args[1]["mapping"]

        assert mapping["opt_id"] == "OPT-ascend-cann-5678"
        assert mapping["operator_id"] == "VecReduce"
        assert mapping["optimization_type"] == "pipeline|memory"
        assert mapping["optimization_description"] == "Enabled pipelining"
        assert mapping["improvement_ratio"] == "0.3"

    def test_store_bugfix_failure_stores_when_flag(self):
        """抽取失败的 BugFix 在 store_failed=True 时存储"""
        result = BugExtractionResult(
            bug_id="BUG-ascend-cann-1234",
            operator_id="Matmul",
            source_repo="ascend-cann",
            source_pr="1234",
            bug_title="Memory leak in Matmul",
            root_cause=None,
            fix_pattern=None,
            extraction_success=False,
            error_message="Rule extraction failed",
        )

        success = self.storage.store_bugfix(result, store_failed=True)

        assert success is True
        # 不应存储到 ChromaDB
        self.mock_chroma.add.assert_not_called()
        # 应存储到 Redis
        self.mock_redis.hset.assert_called()
        self.mock_redis.sadd.assert_called()

    def test_store_optimization_failure_stores_when_flag(self):
        """抽取失败的 Optimization 在 store_failed=True 时存储"""
        result = OptimizationExtractionResult(
            opt_id="OPT-ascend-cann-5678",
            operator_id="VecReduce",
            source_repo="ascend-cann",
            source_pr="5678",
            opt_title="Pipeline optimization",
            optimization_type=[],
            optimization_description=None,
            extraction_success=False,
            error_message="Rule extraction failed",
        )

        success = self.storage.store_optimization(result, store_failed=True)

        assert success is True
        self.mock_chroma.add.assert_not_called()
        self.mock_redis.hset.assert_called()
        self.mock_redis.sadd.assert_called()

    def test_get_failed_bugfixes(self):
        """获取失败的 BugFix 列表"""
        self.mock_redis.smembers.return_value = {"BUG-ascend-cann-1234", "BUG-ascend-cann-5678"}
        self.mock_redis.hgetall.side_effect = [
            {
                "bug_id": "BUG-ascend-cann-1234",
                "operator_id": "Matmul",
                "source_repo": "ascend-cann",
                "source_pr": "1234",
                "bug_title": "Memory leak",
                "error_message": "extraction_failed",
            },
            {
                "opt_id": "OPT-ascend-cann-5678",
                "operator_id": "VecReduce",
                "source_repo": "ascend-cann",
                "source_pr": "5678",
                "opt_title": "Pipeline opt",
                "error_message": "extraction_failed",
            },
        ]

        failed = self.storage.get_failed_bugfixes()

        assert len(failed) == 2
        self.mock_redis.smembers.assert_called_with("bugfix:failed:all")

    def test_get_failed_optimizations(self):
        """获取失败的 Optimization 列表"""
        self.mock_redis.smembers.return_value = {"OPT-ascend-cann-5678"}
        self.mock_redis.hgetall.return_value = {
            "opt_id": "OPT-ascend-cann-5678",
            "operator_id": "VecReduce",
            "source_repo": "ascend-cann",
            "source_pr": "5678",
            "opt_title": "Pipeline opt",
            "error_message": "extraction_failed",
        }

        failed = self.storage.get_failed_optimizations()

        assert len(failed) == 1
        assert failed[0]["opt_id"] == "OPT-ascend-cann-5678"

    def test_mark_retry_success(self):
        """标记重试成功"""
        self.storage.mark_retry_success(bug_id="BUG-ascend-cann-1234")

        self.mock_redis.srem.assert_called_with("bugfix:failed:all", "BUG-ascend-cann-1234")
        self.mock_redis.delete.assert_called_with("bugfix:failed:BUG-ascend-cann-1234")

    def test_failed_bugfix_without_redis(self):
        """没有 Redis 时 store_failed=True 返回 False"""
        storage = KnowledgeStorage(chroma_client=self.mock_chroma, redis_client=None)

        result = BugExtractionResult(
            bug_id="BUG-ascend-cann-1234",
            operator_id="Matmul",
            source_repo="ascend-cann",
            source_pr="1234",
            bug_title="Memory leak",
            root_cause=None,
            fix_pattern=None,
            extraction_success=False,
        )

        success = storage.store_bugfix(result, store_failed=True)

        assert success is False
