# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
知识质量评分器

实现知识完整性评估和审核流程
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set

logger = logging.getLogger(__name__)


class QualityLevel(Enum):
    """质量等级"""
    EXCELLENT = "excellent"  # >= 0.9
    GOOD = "good"  # >= 0.7
    FAIR = "fair"  # >= 0.5
    POOR = "poor"  # < 0.5


@dataclass
class CompletenessScore:
    """完整性评分"""
    total_required: int  # 必填字段总数
    filled_required: int  # 已填必填字段数
    total_optional: int  # 可选字段总数
    filled_optional: int  # 已填可选字段数
    missing_required: List[str] = field(default_factory=list)  # 缺失的必填字段

    @property
    def required_completeness(self) -> float:
        """必填字段完整度"""
        if self.total_required == 0:
            return 1.0
        return self.filled_required / self.total_required

    @property
    def optional_completeness(self) -> float:
        """可选字段完整度"""
        if self.total_optional == 0:
            return 1.0
        return self.filled_optional / self.total_optional

    @property
    def overall_completeness(self) -> float:
        """总体完整度 (必填权重更高)"""
        # 必填字段权重 0.7，可选字段权重 0.3
        return self.required_completeness * 0.7 + self.optional_completeness * 0.3

    def to_dict(self) -> dict:
        return {
            "total_required": self.total_required,
            "filled_required": self.filled_required,
            "total_optional": self.total_optional,
            "filled_optional": self.filled_optional,
            "missing_required": self.missing_required,
            "required_completeness": round(self.required_completeness, 3),
            "optional_completeness": round(self.optional_completeness, 3),
            "overall_completeness": round(self.overall_completeness, 3),
        }


@dataclass
class AccuracyScore:
    """准确性评分"""
    score: float  # 0.0 - 1.0
    issues: List[str] = field(default_factory=list)  # 发现的问题

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 3),
            "issues": self.issues,
        }


@dataclass
class QualityScore:
    """质量评分"""
    completeness: CompletenessScore
    accuracy: Optional[AccuracyScore]
    overall_score: float
    quality_level: QualityLevel
    is_low_quality: bool = False  # confidence < 0.3 或 completeness < 0.5

    def to_dict(self) -> dict:
        return {
            "completeness": self.completeness.to_dict(),
            "accuracy": self.accuracy.to_dict() if self.accuracy else None,
            "overall_score": round(self.overall_score, 3),
            "quality_level": self.quality_level.value,
            "is_low_quality": self.is_low_quality,
        }


class KnowledgeQualityChecker(ABC):
    """知识质量检查器基类"""

    # 质量等级阈值
    EXCELLENT_THRESHOLD = 0.9
    GOOD_THRESHOLD = 0.7
    FAIR_THRESHOLD = 0.5

    # 低质量阈值
    LOW_QUALITY_COMPLETENESS = 0.5
    LOW_QUALITY_CONFIDENCE = 0.3

    @abstractmethod
    def check_completeness(self, knowledge: dict) -> CompletenessScore:
        """检查完整性"""
        pass

    @abstractmethod
    def check_accuracy(self, knowledge: dict) -> AccuracyScore:
        """检查准确性"""
        pass

    def determine_quality_level(self, score: float) -> QualityLevel:
        """确定质量等级"""
        if score >= self.EXCELLENT_THRESHOLD:
            return QualityLevel.EXCELLENT
        elif score >= self.GOOD_THRESHOLD:
            return QualityLevel.GOOD
        elif score >= self.FAIR_THRESHOLD:
            return QualityLevel.FAIR
        else:
            return QualityLevel.POOR

    def is_low_quality(
        self,
        completeness: CompletenessScore,
        confidence: float = None,
    ) -> bool:
        """判断是否低质量"""
        if completeness.overall_completeness < self.LOW_QUALITY_COMPLETENESS:
            return True
        if confidence is not None and confidence < self.LOW_QUALITY_CONFIDENCE:
            return True
        return False


class APIKnowledgeChecker(KnowledgeQualityChecker):
    """
    API 知识质量检查器

    必填字段: api_id, canonical_name, full_signature, category, description
    可选字段: parameters, return_value, version_info, usage_examples, 注意事项, 禁忌
    """

    REQUIRED_FIELDS = {
        "api_id",
        "canonical_name",
        "full_signature",
        "category",
        "description",
    }

    OPTIONAL_FIELDS = {
        "parameters",
        "return_value",
        "version_info",
        "usage_examples",
        "注意事项",
        "禁忌",
    }

    def check_completeness(self, knowledge: dict) -> CompletenessScore:
        """检查 API 知识完整性"""
        missing_required = []

        for field in self.REQUIRED_FIELDS:
            if field not in knowledge or not knowledge[field]:
                missing_required.append(field)

        # 计算可选字段
        filled_optional = 0
        for field in self.OPTIONAL_FIELDS:
            if field in knowledge and knowledge[field]:
                filled_optional += 1

        return CompletenessScore(
            total_required=len(self.REQUIRED_FIELDS),
            filled_required=len(self.REQUIRED_FIELDS) - len(missing_required),
            total_optional=len(self.OPTIONAL_FIELDS),
            filled_optional=filled_optional,
            missing_required=missing_required,
        )

    def check_accuracy(self, knowledge: dict) -> AccuracyScore:
        """检查 API 知识准确性"""
        issues = []

        # 检查签名格式
        if "full_signature" in knowledge:
            sig = knowledge["full_signature"]
            if "(" not in sig or ")" not in sig:
                issues.append("签名格式可能不正确，缺少括号")

        # 检查描述长度
        if "description" in knowledge:
            desc = knowledge["description"]
            if len(desc) < 10:
                issues.append("描述过短，可能不完整")
            elif len(desc) > 5000:
                issues.append("描述过长，可能包含无关内容")

        # 计算准确性分数
        if not issues:
            score = 1.0
        else:
            # 每个问题扣 0.2
            score = max(0.0, 1.0 - len(issues) * 0.2)

        return AccuracyScore(score=score, issues=issues)


class BugFixKnowledgeChecker(KnowledgeQualityChecker):
    """
    Bug 修复知识质量检查器

    必填字段: bug_id, operator_id, source_repo, source_pr, bug_title, root_cause, fix_pattern
    可选字段: trigger_conditions, workarounds, related_apis, severity, category
    """

    REQUIRED_FIELDS = {
        "bug_id",
        "operator_id",
        "source_repo",
        "source_pr",
        "bug_title",
        "root_cause",
        "fix_pattern",
    }

    OPTIONAL_FIELDS = {
        "trigger_conditions",
        "workarounds",
        "related_apis",
        "severity",
        "category",
    }

    def check_completeness(self, knowledge: dict) -> CompletenessScore:
        """检查 Bug 修复知识完整性"""
        missing_required = []

        for field in self.REQUIRED_FIELDS:
            if field not in knowledge or not knowledge[field]:
                missing_required.append(field)

        # 检查列表字段
        list_fields = {"trigger_conditions", "workarounds", "related_apis"}
        filled_optional = 0
        for field in self.OPTIONAL_FIELDS:
            if field in knowledge:
                val = knowledge[field]
                if isinstance(val, list) and len(val) > 0:
                    filled_optional += 1
                elif val:  # 非空非列表
                    filled_optional += 1

        return CompletenessScore(
            total_required=len(self.REQUIRED_FIELDS),
            filled_required=len(self.REQUIRED_FIELDS) - len(missing_required),
            total_optional=len(self.OPTIONAL_FIELDS),
            filled_optional=filled_optional,
            missing_required=missing_required,
        )

    def check_accuracy(self, knowledge: dict) -> AccuracyScore:
        """检查 Bug 修复知识准确性"""
        issues = []

        # 检查根因描述长度
        if "root_cause" in knowledge:
            rc = knowledge["root_cause"]
            if len(rc) < 20:
                issues.append("根因描述过短，可能不完整")

        # 检查修复方案长度
        if "fix_pattern" in knowledge:
            fp = knowledge["fix_pattern"]
            if len(fp) < 10:
                issues.append("修复方案描述过短")

        # 检查是否包含代码相关关键词
        if "fix_pattern" in knowledge or "root_cause" in knowledge:
            text = f"{knowledge.get('fix_pattern', '')} {knowledge.get('root_cause', '')}"
            code_keywords = ["patch", "fix", "change", "update", "modify"]
            if not any(kw in text.lower() for kw in code_keywords):
                issues.append("修复方案可能不包含代码变更信息")

        # 计算准确性分数
        if not issues:
            score = 1.0
        else:
            score = max(0.0, 1.0 - len(issues) * 0.2)

        return AccuracyScore(score=score, issues=issues)


class OptimizationKnowledgeChecker(KnowledgeQualityChecker):
    """
    优化知识质量检查器

    必填字段: opt_id, operator_id, source_repo, source_pr, opt_title, optimization_type, optimization_description
    可选字段: improvement_ratio, before_metrics, after_metrics, related_apis
    """

    REQUIRED_FIELDS = {
        "opt_id",
        "operator_id",
        "source_repo",
        "source_pr",
        "opt_title",
        "optimization_type",
        "optimization_description",
    }

    OPTIONAL_FIELDS = {
        "improvement_ratio",
        "before_metrics",
        "after_metrics",
        "related_apis",
    }

    def check_completeness(self, knowledge: dict) -> CompletenessScore:
        """检查优化知识完整性"""
        missing_required = []

        for field in self.REQUIRED_FIELDS:
            if field not in knowledge or not knowledge[field]:
                missing_required.append(field)

        # 检查列表字段
        filled_optional = 0
        for field in self.OPTIONAL_FIELDS:
            if field in knowledge and knowledge[field]:
                val = knowledge[field]
                if isinstance(val, list) and len(val) > 0:
                    filled_optional += 1
                elif val:
                    filled_optional += 1

        return CompletenessScore(
            total_required=len(self.REQUIRED_FIELDS),
            filled_required=len(self.REQUIRED_FIELDS) - len(missing_required),
            total_optional=len(self.OPTIONAL_FIELDS),
            filled_optional=filled_optional,
            missing_required=missing_required,
        )

    def check_accuracy(self, knowledge: dict) -> AccuracyScore:
        """检查优化知识准确性"""
        issues = []

        # 检查是否有量化指标
        has_ratio = "improvement_ratio" in knowledge and knowledge["improvement_ratio"]
        has_metrics = "before_metrics" in knowledge and knowledge["before_metrics"]

        if not has_ratio and not has_metrics:
            issues.append("缺少量化性能指标")

        # 检查优化类型是否有效
        valid_types = {"memory", "pipeline", "vectorization", "computation", "io", "cache", "parallel"}
        opt_types = knowledge.get("optimization_type", [])
        if isinstance(opt_types, list):
            invalid = [t for t in opt_types if t.lower() not in valid_types]
            if invalid:
                issues.append(f"未识别的优化类型: {invalid}")

        # 计算准确性分数
        if not issues:
            score = 1.0
        else:
            score = max(0.0, 1.0 - len(issues) * 0.2)

        return AccuracyScore(score=score, issues=issues)


class QualityScorer:
    """
    质量评分器

    统一接口评估各类知识质量
    """

    def __init__(self):
        """初始化质量评分器"""
        self.api_checker = APIKnowledgeChecker()
        self.bugfix_checker = BugFixKnowledgeChecker()
        self.optimization_checker = OptimizationKnowledgeChecker()

        logger.info("QualityScorer initialized")

    def score_api(self, knowledge: dict, confidence: float = None) -> QualityScore:
        """
        评估 API 知识质量

        Args:
            knowledge: API 知识字典
            confidence: 置信度分数

        Returns:
            QualityScore: 质量评分
        """
        completeness = self.api_checker.check_completeness(knowledge)
        accuracy = self.api_checker.check_accuracy(knowledge)

        # 综合得分 = 完整度 * 0.6 + 准确性 * 0.4
        overall = completeness.overall_completeness * 0.6 + accuracy.score * 0.4

        # 如果有置信度，进一步调整
        if confidence is not None:
            overall = overall * 0.7 + confidence * 0.3

        quality_level = self.api_checker.determine_quality_level(overall)
        is_low = self.api_checker.is_low_quality(completeness, confidence)

        return QualityScore(
            completeness=completeness,
            accuracy=accuracy,
            overall_score=overall,
            quality_level=quality_level,
            is_low_quality=is_low,
        )

    def score_bugfix(self, knowledge: dict, confidence: float = None) -> QualityScore:
        """
        评估 Bug 修复知识质量

        Args:
            knowledge: Bug 修复知识字典
            confidence: 置信度分数

        Returns:
            QualityScore: 质量评分
        """
        completeness = self.bugfix_checker.check_completeness(knowledge)
        accuracy = self.bugfix_checker.check_accuracy(knowledge)

        # 综合得分
        overall = completeness.overall_completeness * 0.6 + accuracy.score * 0.4

        if confidence is not None:
            overall = overall * 0.7 + confidence * 0.3

        quality_level = self.bugfix_checker.determine_quality_level(overall)
        is_low = self.bugfix_checker.is_low_quality(completeness, confidence)

        return QualityScore(
            completeness=completeness,
            accuracy=accuracy,
            overall_score=overall,
            quality_level=quality_level,
            is_low_quality=is_low,
        )

    def score_optimization(self, knowledge: dict, confidence: float = None) -> QualityScore:
        """
        评估优化知识质量

        Args:
            knowledge: 优化知识字典
            confidence: 置信度分数

        Returns:
            QualityScore: 质量评分
        """
        completeness = self.optimization_checker.check_completeness(knowledge)
        accuracy = self.optimization_checker.check_accuracy(knowledge)

        # 综合得分
        overall = completeness.overall_completeness * 0.6 + accuracy.score * 0.4

        if confidence is not None:
            overall = overall * 0.7 + confidence * 0.3

        quality_level = self.optimization_checker.determine_quality_level(overall)
        is_low = self.optimization_checker.is_low_quality(completeness, confidence)

        return QualityScore(
            completeness=completeness,
            accuracy=accuracy,
            overall_score=overall,
            quality_level=quality_level,
            is_low_quality=is_low,
        )
