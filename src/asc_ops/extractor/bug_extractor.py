# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
Bug 知识抽取器

从 bugfix PR 中抽取 Bug 修复知识
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from .classifier import PRClassifier, PRType

if TYPE_CHECKING:
    from ..llm import UnifiedLLMClient
    from ..llm.messages import Message

logger = logging.getLogger(__name__)


# LLM 抽取 Prompt 模板
BUG_EXTRACTION_PROMPT = """Extract bug knowledge from this PR:

Title: {pr_title}
Body: {pr_body}

Extract the following information in JSON format:
{{
    "root_cause": "What caused the bug? (describe in 1-2 sentences)",
    "fix_pattern": "How was it fixed? (describe the fix approach)",
    "trigger_conditions": ["condition 1 that triggers the bug", "condition 2..."],
    "related_apis": ["API 1", "API 2..."]
}}

Rules:
- If a field cannot be determined, use null
- trigger_conditions should be a list of specific scenarios (max 5)
- related_apis should be AscendC API names like Matmul, VecReduce, etc.
- Only extract information that is explicitly stated in the PR
"""


@dataclass
class BugExtractionResult:
    """Bug 知识抽取结果"""
    bug_id: str
    operator_id: str
    source_repo: str
    source_pr: str

    bug_title: str
    root_cause: Optional[str]
    fix_pattern: Optional[str]
    trigger_conditions: List[str] = field(default_factory=list)
    workarounds: List[str] = field(default_factory=list)
    related_apis: List[str] = field(default_factory=list)

    extraction_success: bool = False
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "bug_id": self.bug_id,
            "operator_id": self.operator_id,
            "source_repo": self.source_repo,
            "source_pr": self.source_pr,
            "bug_title": self.bug_title,
            "root_cause": self.root_cause,
            "fix_pattern": self.fix_pattern,
            "trigger_conditions": self.trigger_conditions,
            "workarounds": self.workarounds,
            "related_apis": self.related_apis,
            "extraction_success": self.extraction_success,
            "error_message": self.error_message,
        }


class BugExtractor:
    """
    Bug 知识抽取器

    从 bugfix PR 中提取:
    - 根因 (root_cause)
    - 触发条件 (trigger_conditions)
    - 修复方案 (fix_pattern)
    - 关联 API (related_apis)

    支持 LLM 增强模式 (use_llm=True) 来提升抽取质量
    """

    # 常见的 API 调用模式
    API_PATTERNS = [
        r"AscendC::(\w+)",
        r"(\w+)\s*\(",  # 函数调用
    ]

    # 根因关键词
    ROOT_CAUSE_KEYWORDS = [
        "because", "caused by", "due to", "reason",
        "root cause", "origin", "originates",
    ]

    # 修复方案关键词
    FIX_PATTERN_KEYWORDS = [
        "fix", "patch", "change", "update", "modify",
        "add", "remove", "replace", "fixes",
    ]

    # 触发条件关键词
    TRIGGER_KEYWORDS = [
        "when", "if", "case", "scenario", "input",
        "condition", "trigger", "occurs",
    ]

    def __init__(self, llm_client: Optional["UnifiedLLMClient"] = None):
        """
        初始化 Bug 抽取器

        Args:
            llm_client: 可选的 LLM 客户端，用于 LLM 增强抽取
        """
        self.classifier = PRClassifier()
        self._llm_client = llm_client
        logger.info(f"BugExtractor initialized (llm_client={'provided' if llm_client else 'None'})")

    def extract(
        self,
        pr_title: str,
        pr_body: str,
        source_repo: str,
        source_pr: str,
        use_llm: bool = False,
    ) -> BugExtractionResult:
        """
        从 PR 抽取 Bug 知识 (同步版本)

        Args:
            pr_title: PR 标题
            pr_body: PR 描述
            source_repo: 来源仓库
            source_pr: PR 编号
            use_llm: 是否使用 LLM 增强 (仅当 llm_client 已提供时有效)

        Returns:
            BugExtractionResult: 抽取结果
        """
        # 先分类确认是 bugfix
        classification = self.classifier.classify(pr_title, pr_body)
        if classification.pr_type != PRType.BUGFIX:
            logger.warning(f"PR {source_pr} is not a bugfix, skipped")
            return BugExtractionResult(
                bug_id=self._generate_bug_id(source_repo, source_pr),
                operator_id=self._extract_operator(pr_title),
                source_repo=source_repo,
                source_pr=source_pr,
                bug_title=pr_title,
                root_cause=None,
                fix_pattern=None,
                extraction_success=False,
                error_message="Not a bugfix PR",
            )

        # 合并文本
        full_text = f"{pr_title}\n{pr_body}"

        # 提取各字段
        bug_id = self._generate_bug_id(source_repo, source_pr)
        operator_id = self._extract_operator(pr_title)
        root_cause = self._extract_root_cause(full_text)
        fix_pattern = self._extract_fix_pattern(full_text)
        trigger_conditions = self._extract_trigger_conditions(full_text)
        related_apis = self._extract_related_apis(full_text)

        success = root_cause is not None or fix_pattern is not None

        logger.info(
            f"Bug extraction for {source_repo}#{source_pr}: "
            f"success={success}, has_root_cause={root_cause is not None}, "
            f"has_fix_pattern={fix_pattern is not None}"
        )

        return BugExtractionResult(
            bug_id=bug_id,
            operator_id=operator_id,
            source_repo=source_repo,
            source_pr=source_pr,
            bug_title=pr_title,
            root_cause=root_cause,
            fix_pattern=fix_pattern,
            trigger_conditions=trigger_conditions,
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
    ) -> BugExtractionResult:
        """
        从 PR 抽取 Bug 知识 (异步版本，支持 LLM 增强)

        Args:
            pr_title: PR 标题
            pr_body: PR 描述
            source_repo: 来源仓库
            source_pr: PR 编号
            use_llm: 是否使用 LLM 增强

        Returns:
            BugExtractionResult: 抽取结果
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
    ) -> Optional[BugExtractionResult]:
        """
        使用 LLM 抽取 Bug 知识

        Args:
            pr_title: PR 标题
            pr_body: PR 描述

        Returns:
            BugExtractionResult 或 None (如果 LLM 抽取失败)
        """
        if not self._llm_client:
            return None

        try:
            from ..llm import Message, MessageRole

            # 构建 prompt
            prompt = BUG_EXTRACTION_PROMPT.format(
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

            # 转换为 BugExtractionResult
            return BugExtractionResult(
                bug_id="",  # 稍后填充
                operator_id=self._extract_operator(pr_title),
                source_repo="",
                source_pr="",
                bug_title=pr_title,
                root_cause=data.get("root_cause"),
                fix_pattern=data.get("fix_pattern"),
                trigger_conditions=data.get("trigger_conditions", []),
                related_apis=data.get("related_apis", []),
                extraction_success=True,
            )

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return None

    def _merge_results(
        self,
        rule_result: BugExtractionResult,
        llm_result: BugExtractionResult,
    ) -> BugExtractionResult:
        """
        合并规则抽取和 LLM 抽取结果

        LLM 结果优先，规则结果作为 fallback
        """
        return BugExtractionResult(
            bug_id=rule_result.bug_id,
            operator_id=llm_result.operator_id or rule_result.operator_id,
            source_repo=rule_result.source_repo,
            source_pr=rule_result.source_pr,
            bug_title=rule_result.bug_title,
            root_cause=llm_result.root_cause or rule_result.root_cause,
            fix_pattern=llm_result.fix_pattern or rule_result.fix_pattern,
            trigger_conditions=llm_result.trigger_conditions or rule_result.trigger_conditions,
            related_apis=llm_result.related_apis or rule_result.related_apis,
            extraction_success=rule_result.extraction_success or llm_result.extraction_success,
        )

    def _generate_bug_id(self, source_repo: str, source_pr: str) -> str:
        """生成 Bug ID"""
        repo_short = source_repo.split("/")[-1] if "/" in source_repo else source_repo
        return f"BUG-{repo_short}-{source_pr}"

    def _extract_operator(self, text: str) -> str:
        """
        从文本提取算子名称

        假设算子名称是大写开头的单词
        """
        import re

        # 查找类似 Matmul, VecReduce, Tensor 等模式
        patterns = [
            r"\b([A-Z][a-z]+[A-Za-z]*)\b",  # 大写开头的驼峰词
            r"(Matmul|Vec|Tensor|Buffer|Kernel)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                # 返回第一个有意义的匹配
                for match in matches:
                    if len(match) > 3:  # 过滤太短的
                        return match

        return "unknown"

    def _extract_root_cause(self, text: str) -> Optional[str]:
        """提取根因"""
        import re

        text_lower = text.lower()

        # 查找根因描述
        for keyword in self.ROOT_CAUSE_KEYWORDS:
            pattern = rf"{keyword}[:\s]+([^\n.]+)"
            match = re.search(pattern, text_lower)
            if match:
                result = match.group(1).strip()
                if len(result) > 10:  # 确保不是噪声
                    return result

        # 如果没找到明确的根因描述，尝试提取第一段作为描述
        sentences = text.split(".")
        for sentence in sentences[:3]:  # 只看前3句
            if len(sentence) > 20:
                return sentence.strip()

        return None

    def _extract_fix_pattern(self, text: str) -> Optional[str]:
        """提取修复方案"""
        import re

        text_lower = text.lower()

        # 查找 fix 后的描述
        for keyword in self.FIX_PATTERN_KEYWORDS:
            pattern = rf"{keyword}[:\s]+([^\n.]+)"
            match = re.search(pattern, text_lower)
            if match:
                result = match.group(1).strip()
                if len(result) > 5:
                    return result

        # 尝试提取 "the solution is" 或 "the fix" 后面的内容
        solution_patterns = [
            r"solution[:\s]+([^\n.]+)",
            r"the fix[:\s]+([^\n.]+)",
            r"patched by[:\s]+([^\n.]+)",
        ]

        for pattern in solution_patterns:
            match = re.search(pattern, text_lower)
            if match:
                return match.group(1).strip()

        return None

    def _extract_trigger_conditions(self, text: str) -> List[str]:
        """提取触发条件"""
        import re

        conditions = []
        text_lower = text.lower()

        for keyword in self.TRIGGER_KEYWORDS:
            pattern = rf"{keyword}[:\s]+([^\n.!,]+)"
            matches = re.findall(pattern, text_lower)
            for match in matches:
                if len(match) > 5:
                    conditions.append(match.strip())

        # 去重
        seen = set()
        unique = []
        for c in conditions:
            if c not in seen:
                seen.add(c)
                unique.append(c)

        return unique[:5]  # 最多5个

    def _extract_related_apis(self, text: str) -> List[str]:
        """提取关联的 API"""
        import re

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

        return unique[:10]  # 最多10个
