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
        # 中文关键词
        "新增", "实现", "支持", "添加",
    }

    # Feature 类负向关键词 (压制 bugfix 信号)
    FEATURE_NEGATIVE = {
        "新增", "实现", "支持", "添加",
    }

    # 单字关键词集合 (用于改进中文分词)
    SINGLE_CHAR_KEYWORDS = {
        # BugFix 相关单字
        "修", "复", "正", "补", "错", "误", "故", "障",
        "异", "崩", "败", "缺", "回",
        # Optimization 相关单字
        "优", "化", "速", "提", "升", "加", "快",
        # Feature 相关单字
        "新", "增", "添", "开", "发",
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

        # 负向关键词过滤：当 feature 类关键词与 bugfix 类关键词同时出现时，降低 bugfix 置信度
        if bugfix_score > 0 and feature_score > 0:
            words = set(self._tokenize(combined_text))
            feature_negative_matches = words.intersection(self.FEATURE_NEGATIVE)
            if feature_negative_matches:
                # 有负向特征词，bugfix 置信度降低 50%
                bugfix_score *= 0.5
                # 重新计算最高分
                scores = [
                    (PRType.BUGFIX, bugfix_score),
                    (PRType.OPTIMIZATION, optim_score),
                    (PRType.FEATURE, feature_score),
                ]
                best_type, best_score = max(scores, key=lambda x: x[1])
            else:
                best_type, best_score = max(
                    [(PRType.BUGFIX, bugfix_score),
                     (PRType.OPTIMIZATION, optim_score),
                     (PRType.FEATURE, feature_score)],
                    key=lambda x: x[1]
                )
        else:
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

        # 直接在文本中检查中文 bugfix 关键词 (应对分词无法拆分的情况)
        # 例如 "精度修复" 包含 "修复"，"FAG sink精度修复" 包含 "修复"
        for keyword in self.BUGFIX_HIGH_WEIGHT:
            if len(keyword) >= 2 and keyword in text:
                # 检查是否已经被 token 匹配了
                if keyword not in words:
                    score += self.HIGH_WEIGHT * 0.8  # 子串匹配给较高权重

        # 归一化 (最多扣 2 个高权重词)
        normalized = min(score / (self.HIGH_WEIGHT * 2), 1.0)

        return normalized

    def _calculate_optim_score(self, text: str) -> float:
        """计算 Optimization 分数"""
        words = set(self._tokenize(text))

        score = 0.0

        # 高权重关键词匹配 (token 级别)
        high_matches = words.intersection(self.OPTIM_HIGH_WEIGHT)
        score += len(high_matches) * self.HIGH_WEIGHT

        # 低权重关键词匹配 (token 级别)
        low_matches = words.intersection(self.OPTIM_LOW_WEIGHT)
        score += len(low_matches) * self.LOW_WEIGHT

        # 直接在文本中检查中文 optimization 关键词 (应对分词无法拆分的情况)
        for keyword in self.OPTIM_HIGH_WEIGHT:
            if len(keyword) >= 2 and keyword in text:
                if keyword not in words:
                    score += self.HIGH_WEIGHT * 0.8

        # 归一化
        normalized = min(score / (self.HIGH_WEIGHT * 2), 1.0)

        return normalized

    def _calculate_feature_score(self, text: str) -> float:
        """计算 Feature 分数"""
        words = set(self._tokenize(text))

        matches = words.intersection(self.FEATURE_KEYWORDS)

        # 直接在文本中检查 feature 关键词 (应对分词无法拆分的情况)
        for keyword in self.FEATURE_KEYWORDS:
            if len(keyword) >= 2 and keyword in text and keyword not in words:
                matches.add(keyword)

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
            | self.SINGLE_CHAR_KEYWORDS
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

        改进：先提取单字关键词，再进行2-4字符切分
        """
        # 转小写
        text = text.lower()

        # 去除常见前缀 (fix:, feat:, optim: 等) 但保留关键词本身
        text = re.sub(r"\b([a-z]+):", r"\1", text)

        # 分割英文单词
        english_words = re.findall(r"[a-z]+", text)

        # 提取单字关键词 (优先匹配)
        single_chars = [c for c in text if c in self.SINGLE_CHAR_KEYWORDS]

        # 提取中文词组 (2-4个字符的连续中文)
        chinese_words = re.findall(r"[\u4e00-\u9fff]{2,4}", text)

        return english_words + single_chars + chinese_words

    # ==================== LLM Fallback ====================

    LLM_FALLBACK_THRESHOLD = 0.5
    REDIS_KEY_PREFIX = "pr:classifier:"
    REDIS_TTL = 7 * 24 * 60 * 60  # 7 days

    # LLM Prompt 模板
    LLM_SYSTEM_PROMPT = """你是一个 PR 分类专家，专门对华为 CANN 算子仓库的 PR 进行分类。

分类类型：
- bugfix: 代码 bug 修复、异常行为修正、错误纠正
- optimization: 性能优化、内存优化、算子加速
- feature: 新增算子、新功能支持
- unknown: 信息不足或类型模糊

重要判断标准：
- 标题含"修复/解决/修正"且代码确实在改 bug → bugfix
- 标题含"新增/实现/支持"且是新增功能 → feature
- 标题含"优化/提升/加速"且是性能改进 → optimization
- 同时含"新增"和"修复"：看主体是新增功能还是修复已有问题"""

    LLM_USER_TEMPLATE = """## PR 信息
标题: {title}
描述: {body}
代码变更摘要: {diff_summary}

请分类这个 PR 并返回 JSON：
{{
  "type": "bugfix|optimization|feature|unknown",
  "confidence": 0.0-1.0,
  "reason": "分类理由（20字内）"
}}"""

    async def classify_with_llm(
        self,
        title: str,
        body: str = "",
        diff_summary: str = "",
        llm_client=None,
        redis_client=None,
        provider: str = "anthropic",
    ) -> ClassificationResult:
        """
        使用 LLM 进行分类 (Fallback 模式)

        当规则层置信度 < 0.5 时调用此方法

        Args:
            title: PR 标题
            body: PR 描述
            diff_summary: diff 摘要 (前500字符)
            llm_client: 可选的 LLM 客户端
            redis_client: 可选的 Redis 客户端 (用于缓存)
            provider: 默认 Provider

        Returns:
            ClassificationResult: LLM 分类结果
        """
        import json
        import hashlib

        # 生成缓存 key
        cache_key = self._generate_cache_key(title, body)

        # 尝试从缓存读取
        if redis_client:
            cached = redis_client.get(cache_key)
            if cached:
                logger.debug(f"LLM classification cache hit: {title[:30]}")
                try:
                    data = json.loads(cached)
                    return ClassificationResult(
                        pr_type=PRType(data["type"]),
                        confidence=data["confidence"],
                        matched_keywords=data.get("matched_keywords", []),
                        reason=data.get("reason", ""),
                    )
                except (json.JSONDecodeError, KeyError):
                    pass

        # 获取 LLM 客户端
        if llm_client is None:
            llm_client = await self._create_llm_client(provider)

        # 构建消息
        from ..llm.messages import Message, MessageRole
        messages = [
            Message(role=MessageRole.SYSTEM, content=self.LLM_SYSTEM_PROMPT),
            Message(
                role=MessageRole.USER,
                content=self.LLM_USER_TEMPLATE.format(
                    title=title,
                    body=body[:500] if body else "",
                    diff_summary=diff_summary[:500] if diff_summary else "",
                ),
            ),
        ]

        # 调用 LLM
        response = await llm_client.chat(messages=messages)

        # 解析响应
        try:
            # 尝试从 response 的 content 中提取 JSON
            content = response.content if hasattr(response, "content") else str(response)

            # 提取 JSON (处理可能的 markdown 代码块)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())

            result = ClassificationResult(
                pr_type=PRType(data["type"]),
                confidence=float(data["confidence"]),
                matched_keywords=data.get("matched_keywords", []),
                reason=data.get("reason", ""),
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            # 降级：返回 unknown
            result = ClassificationResult(
                pr_type=PRType.UNKNOWN,
                confidence=0.0,
                matched_keywords=[],
                reason=f"LLM parse error: {str(e)[:50]}",
            )

        # 缓存结果
        if redis_client and result.pr_type != PRType.UNKNOWN:
            try:
                cache_data = json.dumps({
                    "type": result.pr_type.value,
                    "confidence": result.confidence,
                    "matched_keywords": result.matched_keywords,
                    "reason": result.reason,
                })
                redis_client.set(cache_key, cache_data, ex=self.REDIS_TTL)
            except Exception as e:
                logger.warning(f"Failed to cache LLM result: {e}")

        return result

    def _generate_cache_key(self, title: str, body: str) -> str:
        """生成缓存 key"""
        import hashlib
        content = f"{title}|{body[:200]}"
        hash_value = hashlib.md5(content.encode()).hexdigest()[:16]
        return f"{self.REDIS_KEY_PREFIX}{hash_value}"

    async def _create_llm_client(self, provider: str):
        """创建 LLM 客户端"""
        import os
        from pathlib import Path

        # 尝试加载 .env 文件
        env_path = Path(__file__).parent.parent.parent.parent / ".env"
        if env_path.exists():
            from dotenv import load_dotenv
            load_dotenv(env_path)

        # 从环境变量获取 API key
        api_key = ""
        api_base = None

        provider_lower = provider.lower()
        if provider_lower == "minimax":
            api_key = os.environ.get("MINIMAX_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY", "")
            api_base = os.environ.get("MINIMAX_API_BASE") or os.environ.get("ANTHROPIC_API_BASE")
        elif provider_lower == "anthropic":
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            api_base = os.environ.get("ANTHROPIC_API_BASE")
        elif provider_lower == "openai":
            api_key = os.environ.get("OPENAI_API_KEY", "")
            api_base = os.environ.get("OPENAI_API_BASE")
        elif provider_lower == "zhipu":
            api_key = os.environ.get("ZHIPU_API_KEY", "")
            api_base = os.environ.get("ZHIPU_API_BASE")

        from ..llm import UnifiedLLMClient
        client = UnifiedLLMClient(
            provider=provider,
            api_key=api_key,
            api_base=api_base,
        )
        await client.connect()
        return client
