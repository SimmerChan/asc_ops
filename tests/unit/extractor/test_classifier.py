# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
PR 分类器测试
"""

import pytest

from src.asc_ops.extractor.classifier import (
    PRClassifier,
    PRType,
    ClassificationResult,
)


class TestPRType:
    """PRType 枚举测试"""

    def test_pr_type_values(self):
        """测试 PR 类型值"""
        assert PRType.BUGFIX.value == "bugfix"
        assert PRType.OPTIMIZATION.value == "optimization"
        assert PRType.FEATURE.value == "feature"
        assert PRType.UNKNOWN.value == "unknown"


class TestPRClassifier:
    """PR 分类器测试"""

    def setup_method(self):
        """设置测试"""
        self.classifier = PRClassifier()

    def test_classify_bugfix_explicit(self):
        """显式 BugFix 关键词"""
        result = self.classifier.classify(
            title="fix: memory leak in Matmul",
        )

        assert result.pr_type == PRType.BUGFIX
        assert result.confidence >= 0.5
        assert "fix" in result.matched_keywords

    def test_classify_bugfix_hotfix(self):
        """Hotfix"""
        result = self.classifier.classify(
            title="hotfix: patch for crash bug",
        )

        assert result.pr_type == PRType.BUGFIX

    def test_classify_optimization_explicit(self):
        """显式 Optimization 关键词"""
        result = self.classifier.classify(
            title="perf: improve VecReduceMax throughput",
        )

        assert result.pr_type == PRType.OPTIMIZATION
        assert result.confidence >= 0.5
        assert "perf" in result.matched_keywords

    def test_classify_optimization_memory(self):
        """Memory 优化"""
        result = self.classifier.classify(
            title="memory: reduce buffer size in Matmul",
        )

        assert result.pr_type == PRType.OPTIMIZATION

    def test_classify_feature_explicit(self):
        """显式 Feature 关键词"""
        result = self.classifier.classify(
            title="feat: add new Matmul operator",
        )

        assert result.pr_type == PRType.FEATURE
        assert "feat" in result.matched_keywords

    def test_classify_mixed_keywords(self):
        """混合关键词"""
        # fix 和 perf 同时出现时，权重高的获胜
        result = self.classifier.classify(
            title="fix perf: memory leak causing performance issue",
        )

        # Bugfix 关键词更明确
        assert result.pr_type in [PRType.BUGFIX, PRType.OPTIMIZATION]

    def test_classify_no_keywords(self):
        """无关键词"""
        result = self.classifier.classify(
            title="update README",
        )

        assert result.pr_type == PRType.UNKNOWN
        assert result.confidence == 0.0

    def test_classify_with_body(self):
        """包含 body 的分类"""
        result = self.classifier.classify(
            title="fix bug",
            body="This patch fixes the memory leak issue",
        )

        assert result.pr_type == PRType.BUGFIX

    def test_classify_with_commit_message(self):
        """包含 commit message 的分类"""
        result = self.classifier.classify(
            title="update",
            commit_message="fix: resolve crash on large input",
        )

        assert result.pr_type == PRType.BUGFIX

    def test_tokenize(self):
        """分词测试"""
        words = self.classifier._tokenize("fix: memory leak in Matmul")

        assert "fix" in words
        assert "memory" in words
        assert "leak" in words
        assert "matmul" in words

    def test_tokenize_prefix_removal(self):
        """前缀去除"""
        words = self.classifier._tokenize("fix: update: add: multiple prefixes")

        assert "fix" in words
        assert "update" in words
        assert "add" in words

    def test_confidence_calculation(self):
        """置信度计算"""
        result = self.classifier.classify(
            title="fix: fix: fix: multiple fix keywords",
        )

        # 多个高权重关键词应该有高置信度
        assert result.confidence >= 0.5


class TestClassificationResult:
    """ClassificationResult 测试"""

    def test_to_dict(self):
        """转换为字典"""
        result = ClassificationResult(
            pr_type=PRType.BUGFIX,
            confidence=0.8,
            matched_keywords=["fix", "bug"],
            reason="strongly indicated",
        )

        data = result.to_dict()

        assert data["pr_type"] == "bugfix"
        assert data["confidence"] == 0.8
        assert len(data["matched_keywords"]) == 2
