# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
优化知识抽取器

从 optimization PR 中抽取优化知识
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

from .classifier import PRClassifier, PRType

if TYPE_CHECKING:
    from ..llm import UnifiedLLMClient

logger = logging.getLogger(__name__)


# LLM 抽取 Prompt 模板
OPT_EXTRACTION_PROMPT = """Extract optimization knowledge from this PR:

Title: {pr_title}
Body: {pr_body}

Extract the following information in JSON format:
{{
    "optimization_type": ["type1", "type2", ...],  // memory, pipeline, vectorization, computation, io, cache, parallel
    "optimization_description": "What optimization was done? (1-2 sentences)",
    "improvement_ratio": 0.3,  // 30% improvement as a decimal (null if not specified)
    "before_metrics": {{"metric_name": "value"}},  // metrics before optimization (null if not specified)
    "after_metrics": {{"metric_name": "value"}},  // metrics after optimization (null if not specified)
    "related_apis": ["API1", "API2", ...]  // AscendC APIs involved
}}

Rules:
- If a field cannot be determined, use null
- optimization_type should be from the allowed types: memory, pipeline, vectorization, computation, io, cache, parallel
- improvement_ratio should be a decimal (0.3 = 30%), not a percentage or multiplier
- related_apis should be AscendC API names like Matmul, VecReduce, etc.
- Only extract information that is explicitly stated in the PR
"""


@dataclass
class OptimizationExtractionResult:
    """优化知识抽取结果"""
    opt_id: str
    operator_id: str
    source_repo: str
    source_pr: str

    opt_title: str
    optimization_type: List[str]  # 分块/流水/向量化/内存优化等
    optimization_description: Optional[str]

    improvement_ratio: Optional[float] = None  # 性能提升比例
    before_metrics: Optional[dict] = None
    after_metrics: Optional[dict] = None

    related_apis: List[str] = field(default_factory=list)

    extraction_success: bool = False
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "opt_id": self.opt_id,
            "operator_id": self.operator_id,
            "source_repo": self.source_repo,
            "source_pr": self.source_pr,
            "opt_title": self.opt_title,
            "optimization_type": self.optimization_type,
            "optimization_description": self.optimization_description,
            "improvement_ratio": self.improvement_ratio,
            "before_metrics": self.before_metrics,
            "after_metrics": self.after_metrics,
            "related_apis": self.related_apis,
            "extraction_success": self.extraction_success,
            "error_message": self.error_message,
        }


class OptimizationExtractor:
    """
    优化知识抽取器

    从 optimization PR 中提取:
    - 优化类型 (optimization_type)
    - 优化描述 (optimization_description)
    - 量化指标 (improvement_ratio, before/after metrics)

    支持 LLM 增强模式 (use_llm=True) 来提升抽取质量
    """

    # 优化类型关键词
    OPTIMIZATION_TYPES = {
        "memory": ["memory", "buffer", "allocation", "footprint"],
        "pipeline": ["pipeline", "pipelining", "流水"],
        "vectorization": ["vector", "vectorization", "simd", "向量化"],
        "computation": ["compute", "computation", "算子融合", "fusion"],
        "io": ["io", "bandwidth", "带宽"],
        "cache": ["cache", "caching", "缓存"],
        "parallel": ["parallel", "concurrency", "并行"],
    }

    # 量化指标模式
    RATIO_PATTERNS = [
        r"(\d+(?:\.\d+)?)\s*[xX%]",  # 2x, 30%, 1.5X
        r"improvement[:\s]+(\d+(?:\.\d+)?)\s*(?:%|percent)",  # improvement: 30%
        r"(\d+(?:\.\d+)?)\s*(?:times|faster|reduction)",  # 2x faster, 30% reduction
    ]

    # 性能指标关键词
    METRICS_KEYWORDS = ["ms", "fps", "throughput", "latency", "bandwidth", "memory", "time"]

    def __init__(self, llm_client: Optional["UnifiedLLMClient"] = None):
        """
        初始化优化抽取器

        Args:
            llm_client: 可选的 LLM 客户端，用于 LLM 增强抽取
        """
        self.classifier = PRClassifier()
        self._llm_client = llm_client
        logger.info(f"OptimizationExtractor initialized (llm_client={'provided' if llm_client else 'None'})")

    def extract(
        self,
        pr_title: str,
        pr_body: str,
        source_repo: str,
        source_pr: str,
        use_llm: bool = False,
    ) -> OptimizationExtractionResult:
        """
        从 PR 抽取优化知识 (同步版本)

        Args:
            pr_title: PR 标题
            pr_body: PR 描述
            source_repo: 来源仓库
            source_pr: PR 编号
            use_llm: 是否使用 LLM 增强 (仅当 llm_client 已提供时有效)

        Returns:
            OptimizationExtractionResult: 抽取结果
        """
        # 先分类确认是 optimization
        classification = self.classifier.classify(pr_title, pr_body)
        if classification.pr_type != PRType.OPTIMIZATION:
            logger.warning(f"PR {source_pr} is not an optimization, skipped")
            return OptimizationExtractionResult(
                opt_id=self._generate_opt_id(source_repo, source_pr),
                operator_id=self._extract_operator(pr_title),
                source_repo=source_repo,
                source_pr=source_pr,
                opt_title=pr_title,
                optimization_type=[],
                optimization_description=None,
                extraction_success=False,
                error_message="Not an optimization PR",
            )

        # 合并文本
        full_text = f"{pr_title}\n{pr_body}"

        # 提取各字段
        opt_id = self._generate_opt_id(source_repo, source_pr)
        operator_id = self._extract_operator(pr_title)
        optimization_type = self._extract_optimization_type(full_text)
        optimization_description = self._extract_description(full_text)
        improvement_ratio = self._extract_improvement_ratio(full_text)
        before_metrics, after_metrics = self._extract_metrics(full_text)
        related_apis = self._extract_related_apis(full_text)

        success = len(optimization_type) > 0 or optimization_description is not None

        logger.info(
            f"Optimization extraction for {source_repo}#{source_pr}: "
            f"success={success}, types={optimization_type}, "
            f"ratio={improvement_ratio}"
        )

        return OptimizationExtractionResult(
            opt_id=opt_id,
            operator_id=operator_id,
            source_repo=source_repo,
            source_pr=source_pr,
            opt_title=pr_title,
            optimization_type=optimization_type,
            optimization_description=optimization_description,
            improvement_ratio=improvement_ratio,
            before_metrics=before_metrics,
            after_metrics=after_metrics,
            related_apis=related_apis,
            extraction_success=success,
        )

    async def extract_async(
        self,
        pr_title: str,
        pr_body: str,
        source_repo: str,
        source_pr: str,
        use_llm: bool = False,
    ) -> OptimizationExtractionResult:
        """
        从 PR 抽取优化知识 (异步版本，支持 LLM 增强)

        Args:
            pr_title: PR 标题
            pr_body: PR 描述
            source_repo: 来源仓库
            source_pr: PR 编号
            use_llm: 是否使用 LLM 增强

        Returns:
            OptimizationExtractionResult: 抽取结果
        """
        # 先用规则抽取
        result = self.extract(pr_title, pr_body, source_repo, source_pr)

        # LLM 增强
        if use_llm and self._llm_client:
            llm_result = await self._llm_extract(pr_title, pr_body)
            if llm_result:
                result = self._merge_results(result, llm_result)

        return result

    async def _llm_extract(
        self,
        pr_title: str,
        pr_body: str,
    ) -> Optional[OptimizationExtractionResult]:
        """
        使用 LLM 抽取优化知识

        Args:
            pr_title: PR 标题
            pr_body: PR 描述

        Returns:
            OptimizationExtractionResult 或 None (如果 LLM 抽取失败)
        """
        if not self._llm_client:
            return None

        try:
            from ..llm import Message, MessageRole

            # 构建 prompt
            prompt = OPT_EXTRACTION_PROMPT.format(
                pr_title=pr_title,
                pr_body=pr_body,
            )

            messages = [
                Message(role=MessageRole.USER, content=prompt)
            ]

            response = await self._llm_client.chat(
                messages=messages,
                max_tokens=1024,
                temperature=0.3,
            )

            # 解析 JSON 响应
            import json
            try:
                data = json.loads(response.content)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse LLM response as JSON: {response.content[:200]}")
                return None

            # 转换为 OptimizationExtractionResult
            return OptimizationExtractionResult(
                opt_id="",  # 稍后填充
                operator_id=self._extract_operator(pr_title),
                source_repo="",
                source_pr="",
                opt_title=pr_title,
                optimization_type=data.get("optimization_type", []),
                optimization_description=data.get("optimization_description"),
                improvement_ratio=data.get("improvement_ratio"),
                before_metrics=data.get("before_metrics"),
                after_metrics=data.get("after_metrics"),
                related_apis=data.get("related_apis", []),
                extraction_success=True,
            )

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return None

    def _merge_results(
        self,
        rule_result: OptimizationExtractionResult,
        llm_result: OptimizationExtractionResult,
    ) -> OptimizationExtractionResult:
        """
        合并规则抽取和 LLM 抽取结果

        LLM 结果优先，规则结果作为 fallback
        """
        return OptimizationExtractionResult(
            opt_id=rule_result.opt_id,
            operator_id=llm_result.operator_id or rule_result.operator_id,
            source_repo=rule_result.source_repo,
            source_pr=rule_result.source_pr,
            opt_title=rule_result.opt_title,
            optimization_type=llm_result.optimization_type or rule_result.optimization_type,
            optimization_description=llm_result.optimization_description or rule_result.optimization_description,
            improvement_ratio=llm_result.improvement_ratio or rule_result.improvement_ratio,
            before_metrics=llm_result.before_metrics or rule_result.before_metrics,
            after_metrics=llm_result.after_metrics or rule_result.after_metrics,
            related_apis=llm_result.related_apis or rule_result.related_apis,
            extraction_success=rule_result.extraction_success or llm_result.extraction_success,
        )

    def _generate_opt_id(self, source_repo: str, source_pr: str) -> str:
        """生成优化 ID"""
        repo_short = source_repo.split("/")[-1] if "/" in source_repo else source_repo
        return f"OPT-{repo_short}-{source_pr}"

    def _extract_operator(self, text: str) -> str:
        """从文本提取算子名称"""
        # 查找类似 Matmul, VecReduce, Tensor 等模式
        patterns = [
            r"\b([A-Z][a-z]+[A-Za-z]*)\b",
            r"(Matmul|Vec|Tensor|Buffer|Kernel)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if len(match) > 3:
                    return match

        return "unknown"

    def _extract_optimization_type(self, text: str) -> List[str]:
        """提取优化类型"""
        text_lower = text.lower()
        found_types = []

        for opt_type, keywords in self.OPTIMIZATION_TYPES.items():
            for keyword in keywords:
                if keyword in text_lower:
                    if opt_type not in found_types:
                        found_types.append(opt_type)
                    break

        return found_types

    def _extract_description(self, text: str) -> Optional[str]:
        """提取优化描述"""
        # 尝试提取第一段包含关键词的描述
        sentences = text.split(".")
        for sentence in sentences[:3]:
            if len(sentence) > 20:
                # 检查是否包含优化相关关键词
                if any(kw in sentence.lower() for kw in ["optim", "improve", "performance", "reduce"]):
                    return sentence.strip()

        # 如果没找到，返回第一段
        if sentences and len(sentences[0]) > 10:
            return sentences[0].strip()

        return None

    def _extract_improvement_ratio(self, text: str) -> Optional[float]:
        """提取性能提升比例"""
        text_lower = text.lower()

        for pattern in self.RATIO_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                value_str = match.group(1)
                value = float(value_str)

                # 处理百分比
                if "%" in match.group(0) or "percent" in match.group(0):
                    value = value / 100.0

                # 处理倍数 (x)
                if "x" in match.group(0).lower():
                    value = value - 1.0  # 2x -> 1.0 improvement

                return value

        return None

    def _extract_metrics(
        self,
        text: str,
    ) -> tuple[Optional[dict], Optional[dict]]:
        """提取性能指标 (before/after)"""
        before_metrics = None
        after_metrics = None

        # 查找 before/after 模式
        before_pattern = r"before[:\s]+([^\n,]+(?:\n[^\n,]+)?)"
        after_pattern = r"after[:\s]+([^\n,]+(?:\n[^\n,]+)?)"

        before_match = re.search(before_pattern, text.lower())
        after_match = re.search(after_pattern, text.lower())

        if before_match:
            before_metrics = {"raw": before_match.group(1).strip()}
        if after_match:
            after_metrics = {"raw": after_match.group(1).strip()}

        return before_metrics, after_metrics

    def _extract_related_apis(self, text: str) -> List[str]:
        """提取关联的 API"""
        apis = []

        # 查找 AscendC:: 模式
        matches = re.findall(r"AscendC::(\w+)", text)
        apis.extend(matches)

        # 查找大写开头的函数调用
        matches = re.findall(r"\b([A-Z][a-z]+)\s*\(", text)
        for match in matches:
            if len(match) > 3:
                apis.append(match)

        # 去重
        seen = set()
        unique = []
        for api in apis:
            if api not in seen:
                seen.add(api)
                unique.append(api)

        return unique[:10]
