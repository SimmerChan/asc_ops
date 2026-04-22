# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
CUDA API 语义分析器

使用 LLM 为 CUDA API 生成语义描述，用于后续向量检索匹配 AscendC API
"""

import logging
import json
import asyncio
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, TYPE_CHECKING

from .models import GPUAPIInfo, GPUPlatform
from .doc_scraper import CUDAAPIScrapedData

if TYPE_CHECKING:
    from ..llm import UnifiedLLMClient
    from ..llm.messages import Message

logger = logging.getLogger(__name__)


# CUDA API 语义分析 Prompt 模板
SEMANTIC_ANALYSIS_PROMPT = """You are an expert in GPU (CUDA) to Huawei Ascend NPU (AscendC) cross-platform migration.

For the following CUDA API, generate a semantic description that will be used for vector similarity search against AscendC NPU APIs.

## CUDA API Information
- Name: {api_name}
- Signature: {signature}
- Category: {category}
- Parameters: {parameters}
- Return Type: {return_type}
- Description: {description}

## Task

Generate a concise semantic description (2-3 sentences) that captures:
1. What this CUDA API does (its core functionality)
2. What type of operation it performs (memory, compute, synchronization, etc.)
3. How it might relate to NPU operations

The description should be suitable for embedding-based similarity search to find equivalent or similar AscendC NPU APIs.

## Output Format

Respond with ONLY a JSON object (no markdown, no explanation):
{{
    "semantic_description": "Your 2-3 sentence semantic description here",
    "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
    "operation_type": "memory|compute|synchronization|communication|reduction|allocation|other",
    " complexity_hint": "low|medium|high"
}}

Rules:
- semantic_description: Must be 2-3 sentences, be specific about functionality
- keywords: 5 most relevant keywords for retrieval
- operation_type: Primary operation category
- complexity_hint: How complex the API is to port to NPU
"""


@dataclass
class SemanticAnalysisResult:
    """语义分析结果"""
    api_name: str
    semantic_description: str
    keywords: List[str]
    operation_type: str
    complexity_hint: str
    parsing_failed: bool = False
    raw_response: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "api_name": self.api_name,
            "semantic_description": self.semantic_description,
            "keywords": self.keywords,
            "operation_type": self.operation_type,
            "complexity_hint": self.complexity_hint,
        }


@dataclass
class BatchAnalysisResult:
    """批量分析结果"""
    total: int
    successful: int
    failed: int
    results: List[SemanticAnalysisResult]
    errors: List[Dict[str, str]]


class CUDASemanticAnalyzer:
    """
    CUDA API 语义分析器

    使用 LLM 为 CUDA API 生成语义描述
    """

    def __init__(
        self,
        llm_client: Optional["UnifiedLLMClient"] = None,
        max_retries: int = 3,
        batch_size: int = 50,
        temperature: float = 0.1,
    ):
        """
        初始化语义分析器

        Args:
            llm_client: LLM 客户端
            max_retries: JSON 解析失败最大重试次数
            batch_size: 每批处理的 API 数量
            temperature: LLM temperature
        """
        self._llm_client = llm_client
        self._max_retries = max_retries
        self._batch_size = batch_size
        self._temperature = temperature

        logger.info(
            f"CUDASemanticAnalyzer initialized (batch_size={batch_size}, "
            f"max_retries={max_retries})"
        )

    async def analyze_api(
        self,
        api_data: CUDAAPIScrapedData,
    ) -> SemanticAnalysisResult:
        """
        分析单个 CUDA API

        Args:
            api_data: CUDA API 采集数据

        Returns:
            SemanticAnalysisResult
        """
        if self._llm_client is None:
            logger.warning("No LLM client, using fallback analysis")
            return self._fallback_analysis(api_data)

        prompt = self._build_prompt(api_data)

        for attempt in range(self._max_retries):
            try:
                response = await self._llm_client.generate(
                    prompt=prompt,
                    temperature=self._temperature,
                    max_tokens=500,
                )

                result = self._parse_response(response.content, api_data.api_name)
                if result and not result.parsing_failed:
                    return result

                logger.warning(
                    f"Attempt {attempt + 1} failed for {api_data.api_name}: "
                    f"parsing failed"
                )

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {api_data.api_name}: {e}")

        # 回退到默认分析
        logger.info(f"Falling back to default analysis for {api_data.api_name}")
        return self._fallback_analysis(api_data)

    async def analyze_batch(
        self,
        apis: List[CUDAAPIScrapedData],
        progress_callback: Optional[callable] = None,
    ) -> BatchAnalysisResult:
        """
        批量分析 CUDA APIs

        Args:
            apis: CUDA API 列表
            progress_callback: 进度回调函数 (completed, total)

        Returns:
            BatchAnalysisResult
        """
        results = []
        errors = []
        successful = 0
        failed = 0

        # 分批处理
        for i in range(0, len(apis), self._batch_size):
            batch = apis[i:i + self._batch_size]
            logger.info(f"Processing batch {i // self._batch_size + 1}, "
                       f"APIs {i + 1}-{min(i + self._batch_size, len(apis))}")

            batch_tasks = [self.analyze_api(api) for api in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    errors.append({
                        "api_name": batch[j].api_name,
                        "error": str(result),
                    })
                    failed += 1
                    logger.error(f"Failed to analyze {batch[j].api_name}: {result}")
                else:
                    results.append(result)
                    if not result.parsing_failed:
                        successful += 1

                # 调用进度回调
                if progress_callback:
                    progress_callback(len(results) + failed, len(apis))

        return BatchAnalysisResult(
            total=len(apis),
            successful=successful,
            failed=failed,
            results=results,
            errors=errors,
        )

    def _build_prompt(self, api_data: CUDAAPIScrapedData) -> str:
        """构建分析 prompt"""
        return SEMANTIC_ANALYSIS_PROMPT.format(
            api_name=api_data.api_name,
            signature=api_data.full_signature or "N/A",
            category=api_data.category,
            parameters=", ".join(api_data.parameters) if api_data.parameters else "N/A",
            return_type=api_data.return_type or "N/A",
            description=api_data.description or "No description available",
        )

    def _parse_response(
        self,
        content: str,
        api_name: str,
    ) -> Optional[SemanticAnalysisResult]:
        """解析 LLM 响应"""
        try:
            # 清理响应内容
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            data = json.loads(content)

            return SemanticAnalysisResult(
                api_name=api_name,
                semantic_description=data.get("semantic_description", ""),
                keywords=data.get("keywords", []),
                operation_type=data.get("operation_type", "other"),
                complexity_hint=data.get("complexity_hint", "medium"),
                parsing_failed=False,
                raw_response=content,
            )

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error for {api_name}: {e}")
            return SemanticAnalysisResult(
                api_name=api_name,
                semantic_description="",
                keywords=[],
                operation_type="other",
                complexity_hint="medium",
                parsing_failed=True,
                raw_response=content,
            )

    def _fallback_analysis(
        self,
        api_data: CUDAAPIScrapedData,
    ) -> SemanticAnalysisResult:
        """回退分析（当 LLM 不可用时）"""
        # 基于 API 名称和分类生成简单的语义描述
        category_hints = {
            "warp-shuffle": "Warp-level shuffle operation for data exchange between threads within a warp without shared memory",
            "warp-vote": "Warp-level vote/broadcast operation for collective thread decisions",
            "warp-reduce": "Warp-level reduction operation for aggregating values across threads",
            "memory-management": "CUDA memory allocation, copy, or initialization operation",
            "stream-management": "CUDA stream management for asynchronous operation ordering",
            "event-management": "CUDA event tracking for synchronization and timing",
        }

        description_template = category_hints.get(
            api_data.category,
            f"CUDA {api_data.category} operation"
        )

        # 提取关键词
        keywords = [api_data.category.split("-")[0]]
        if "shuffle" in api_data.category:
            keywords.append("warp")
            keywords.append("shuffle")
        if "vote" in api_data.category:
            keywords.append("warp")
            keywords.append("vote")
        if "reduce" in api_data.category:
            keywords.append("warp")
            keywords.append("reduction")
        if "memory" in api_data.category:
            keywords.append("memory")
            keywords.append("allocation")

        keywords.append(api_data.api_name.replace("_", ""))

        return SemanticAnalysisResult(
            api_name=api_data.api_name,
            semantic_description=f"{api_data.api_name}: {description_template}. "
                               f"Part of CUDA {api_data.category} API group.",
            keywords=list(set(keywords))[:5],
            operation_type=api_data.category.split("-")[0] if "-" in api_data.category else "other",
            complexity_hint="medium",
            parsing_failed=False,
        )

    def apply_analysis_to_gpu_api(
        self,
        api: GPUAPIInfo,
        analysis: SemanticAnalysisResult,
    ) -> GPUAPIInfo:
        """
        将语义分析结果应用到 GPUAPIInfo 对象

        Args:
            api: GPUAPIInfo 对象
            analysis: 语义分析结果

        Returns:
            更新后的 GPUAPIInfo
        """
        # 更新 description
        if not api.description:
            api.description = analysis.semantic_description

        return api


async def analyze_cuda_apis_with_llm(
    apis: List[CUDAAPIScrapedData],
    llm_client: Optional["UnifiedLLMClient"] = None,
    batch_size: int = 50,
    progress_callback: Optional[callable] = None,
) -> BatchAnalysisResult:
    """
    使用 LLM 批量分析 CUDA API

    Args:
        apis: CUDA API 列表
        llm_client: LLM 客户端
        batch_size: 批大小
        progress_callback: 进度回调

    Returns:
        BatchAnalysisResult
    """
    analyzer = CUDASemanticAnalyzer(
        llm_client=llm_client,
        batch_size=batch_size,
    )
    return await analyzer.analyze_batch(apis, progress_callback)


if __name__ == "__main__":
    import asyncio

    async def main():
        """测试语义分析"""
        logging.basicConfig(level=logging.INFO)

        # 测试数据
        test_apis = [
            CUDAAPIScrapedData(
                api_name="__shfl_up_sync",
                full_signature="T __shfl_up_sync(unsigned mask, T var, int delta)",
                description="Exchange value among threads in a warp with source thread offset by delta modulo warp size.",
                category="warp-shuffle",
                subcategory="shuffle",
                parameters=["unsigned mask", "T var", "int delta"],
                return_type="T",
                documentation_url="https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html",
            ),
        ]

        analyzer = CUDASemanticAnalyzer()
        result = await analyzer.analyze_batch(test_apis)

        print(f"\nAnalysis complete:")
        print(f"  Total: {result.total}")
        print(f"  Successful: {result.successful}")
        print(f"  Failed: {result.failed}")
        for r in result.results:
            print(f"  - {r.api_name}: {r.semantic_description[:50]}...")

    asyncio.run(main())
