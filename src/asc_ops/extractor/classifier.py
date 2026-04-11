# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
PR 分类器

从 commit/PR 中自动分类 bugfix / optimization / feature
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class PRType(Enum):
    """PR 类型"""
    BUGFIX = "bugfix"
    OPTIMIZATION = "optimization"
    FEATURE = "feature"
    UNKNOWN = "unknown"


@dataclass
class ClassificationResult:
    """分类结果"""
    pr_type: PRType
    confidence: float  # 0.0 - 1.0
    matched_keywords: List[str]
    reason: str

    def to_dict(self) -> dict:
        return {
            "pr_type": self.pr_type.value,
            "confidence": round(self.confidence, 3),
            "matched_keywords": self.matched_keywords,
            "reason": self.reason,
        }


class PRClassifier:
    """
    PR 分类器

    基于关键词匹配判断 PR 类型
    - bugfix: fix, bug, patch, resolve, close
    - optimization: optim, perf, improve, speed, memory, performance
    - feature: feat, add, implement, new, support
    """

    # BugFix 关键词 (高权重)
    BUGFIX_HIGH_WEIGHT = {
        "fix", "bug", "patch", "resolve", "close",
        "hotfix", "bugfix", "bug-fix",
        # 中文关键词
        "修复", "解决", "修正", "修补",
    }

    # BugFix 关键词 (低权重)
    BUGFIX_LOW_WEIGHT = {
        "error", "issue", "problem", "crash", "fail",
        "exception", "incorrect", "wrong",
        # 中文关键词
        "异常", "问题", "错误", "失败", "崩溃",
        "精度", "回归", "缺陷", "故障",
    }

    # Optimization 关键词 (高权重)
    OPTIM_HIGH_WEIGHT = {
        "optim", "perf", "performance", "speed", "fast",
        "memory", "throughput", "latency", "efficiency",
        # 中文关键词
        "优化", "加速", "提升", "改进",
    }

    # Optimization 关键词 (低权重)
    OPTIM_LOW_WEIGHT = {
        "improve", "enhance", "better", "reduce", "minimize",
        "maximize", "boost", "accelerate",
        # 中文关键词
        "改善", "增强", "提高", "缩减", "降低",
    }

    # Feature 关键词
    FEATURE_KEYWORDS = {
        "feat", "feature", "add", "new", "implement",
        "support", "introduce", "create",
    }

    # 权重配置
    HIGH_WEIGHT = 0.9
    LOW_WEIGHT = 0.6
    KEYWORD_MATCH_WEIGHT = 0.3  # 关键词匹配的基础分数

    def classify(
        self,
        title: str,
        body: str = "",
        commit_message: str = "",
    ) -> ClassificationResult:
        """
        分类 PR

        Args:
            title: PR 标题
            body: PR 描述
            commit_message: Commit 消息

        Returns:
            ClassificationResult: 分类结果
        """
        # 合并所有文本
        combined_text = f"{title} {body} {commit_message}".lower()

        # 提取关键词
        bugfix_score = self._calculate_bugfix_score(combined_text)
        optim_score = self._calculate_optim_score(combined_text)
        feature_score = self._calculate_feature_score(combined_text)

        # 确定最高分数的类型
        scores = [
            (PRType.BUGFIX, bugfix_score),
            (PRType.OPTIMIZATION, optim_score),
            (PRType.FEATURE, feature_score),
        ]

        best_type, best_score = max(scores, key=lambda x: x[1])

        # 如果最高分数低于阈值，标记为 UNKNOWN
        if best_score < 0.3:
            best_type = PRType.UNKNOWN
            best_score = 0.0

        # 获取匹配的关键词
        matched = self._extract_matched_keywords(combined_text)

        reason = self._generate_reason(best_type, best_score, matched)

        logger.debug(
            f"PR classified as {best_type.value} "
            f"(confidence: {best_score:.2f}): {title[:50]}"
        )

        return ClassificationResult(
            pr_type=best_type,
            confidence=best_score,
            matched_keywords=matched,
            reason=reason,
        )

    def _calculate_bugfix_score(self, text: str) -> float:
        """计算 BugFix 分数"""
        words = set(self._tokenize(text))

        score = 0.0

        # 高权重关键词匹配
        high_matches = words.intersection(self.BUGFIX_HIGH_WEIGHT)
        score += len(high_matches) * self.HIGH_WEIGHT

        # 低权重关键词匹配
        low_matches = words.intersection(self.BUGFIX_LOW_WEIGHT)
        score += len(low_matches) * self.LOW_WEIGHT

        # 归一化 (最多扣 2 个高权重词)
        normalized = min(score / (self.HIGH_WEIGHT * 2), 1.0)

        return normalized

    def _calculate_optim_score(self, text: str) -> float:
        """计算 Optimization 分数"""
        words = set(self._tokenize(text))

        score = 0.0

        # 高权重关键词匹配
        high_matches = words.intersection(self.OPTIM_HIGH_WEIGHT)
        score += len(high_matches) * self.HIGH_WEIGHT

        # 低权重关键词匹配
        low_matches = words.intersection(self.OPTIM_LOW_WEIGHT)
        score += len(low_matches) * self.LOW_WEIGHT

        # 归一化
        normalized = min(score / (self.HIGH_WEIGHT * 2), 1.0)

        return normalized

    def _calculate_feature_score(self, text: str) -> float:
        """计算 Feature 分数"""
        words = set(self._tokenize(text))

        matches = words.intersection(self.FEATURE_KEYWORDS)

        if not matches:
            return 0.0

        # 基础分数
        score = self.KEYWORD_MATCH_WEIGHT

        # 每多一个关键词加 0.1
        score += (len(matches) - 1) * 0.1

        return min(score, 1.0)

    def _extract_matched_keywords(self, text: str) -> List[str]:
        """提取匹配的关键词"""
        words = set(self._tokenize(text))

        all_keywords = (
            self.BUGFIX_HIGH_WEIGHT
            | self.BUGFIX_LOW_WEIGHT
            | self.OPTIM_HIGH_WEIGHT
            | self.OPTIM_LOW_WEIGHT
            | self.FEATURE_KEYWORDS
        )

        return list(words.intersection(all_keywords))

    def _generate_reason(
        self,
        pr_type: PRType,
        confidence: float,
        matched: List[str],
    ) -> str:
        """生成原因说明"""
        if not matched:
            return "No matching keywords found"

        if confidence >= 0.8:
            conf_desc = "strongly indicated"
        elif confidence >= 0.5:
            conf_desc = "moderately indicated"
        else:
            conf_desc = "weakly indicated"

        type_desc = {
            PRType.BUGFIX: "bug fix",
            PRType.OPTIMIZATION: "optimization",
            PRType.FEATURE: "new feature",
            PRType.UNKNOWN: "unknown type",
        }[pr_type]

        return f"PR is {conf_desc} as {type_desc} based on keywords: {', '.join(matched[:5])}"

    def _tokenize(self, text: str) -> List[str]:
        """
        分词

        将文本分割为单词/词组，去除常见前缀和标点
        支持中英文
        """
        # 转小写
        text = text.lower()

        # 去除常见前缀 (fix:, feat:, optim: 等) 但保留关键词本身
        text = re.sub(r"\b([a-z]+):", r"\1", text)

        # 分割英文单词
        english_words = re.findall(r"[a-z]+", text)

        # 提取中文词组 (2-4个字符的连续中文)
        chinese_words = re.findall(r"[\u4e00-\u9fff]{2,4}", text)

        return english_words + chinese_words
