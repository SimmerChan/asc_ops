# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
Bug 知识抽取器测试
"""

import pytest

from src.asc_ops.extractor.bug_extractor import (
    BugExtractor,
    BugExtractionResult,
)


class TestBugExtractor:
    """Bug 知识抽取器测试"""

    def setup_method(self):
        """设置测试"""
        self.extractor = BugExtractor()

    def test_extract_bugfix_pr(self):
        """提取 BugFix PR"""
        result = self.extractor.extract(
            pr_title="fix: memory leak in Matmul",
            pr_body="Root cause: buffer not released. Fix: added release call.",
            source_repo="ascend-cann",
            source_pr="1234",
        )

        assert isinstance(result, BugExtractionResult)
        assert result.source_repo == "ascend-cann"
        assert result.source_pr == "1234"
        assert result.extraction_success is True

    def test_extract_non_bugfix_pr(self):
        """非 BugFix PR"""
        result = self.extractor.extract(
            pr_title="feat: add new Matmul operator",
            pr_body="This adds a new operator",
            source_repo="ascend-cann",
            source_pr="5678",
        )

        assert result.extraction_success is False
        assert result.error_message == "Not a bugfix PR"

    def test_extract_operator_from_title(self):
        """从标题提取算子"""
        result = self.extractor.extract(
            pr_title="fix: crash in VecReduceMax when input is empty",
            pr_body="The bug causes crash",
            source_repo="ascend-cann",
            source_pr="100",
        )

        assert result.operator_id == "VecReduceMax"

    def test_generate_bug_id(self):
        """生成 Bug ID"""
        bug_id = self.extractor._generate_bug_id("ascend-cann", "1234")
        assert "BUG" in bug_id
        assert "1234" in bug_id

    def test_extract_root_cause(self):
        """提取根因"""
        text = "Root cause: buffer not properly released after computation"

        root_cause = self.extractor._extract_root_cause(text)

        assert root_cause is not None
        assert "buffer" in root_cause.lower()

    def test_extract_fix_pattern(self):
        """提取修复方案"""
        text = "Fix: added buffer.release() after computation"

        fix_pattern = self.extractor._extract_fix_pattern(text)

        assert fix_pattern is not None
        # 至少应该包含 fix 关键词后的内容
        assert "buffer" in fix_pattern.lower()

    def test_extract_related_apis(self):
        """提取关联 API"""
        text = "The fix involves AscendC::Matmul and AscendC::Buffer"

        apis = self.extractor._extract_related_apis(text)

        assert "Matmul" in apis
        assert "Buffer" in apis

    def test_extract_trigger_conditions(self):
        """提取触发条件"""
        text = "Trigger when: input size is zero, case with empty tensor"

        conditions = self.extractor._extract_trigger_conditions(text)

        assert len(conditions) > 0


class TestBugExtractionResult:
    """BugExtractionResult 测试"""

    def test_to_dict(self):
        """转换为字典"""
        result = BugExtractionResult(
            bug_id="BUG-123",
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

        data = result.to_dict()

        assert data["bug_id"] == "BUG-123"
        assert data["root_cause"] == "Buffer not released"
        assert data["extraction_success"] is True
