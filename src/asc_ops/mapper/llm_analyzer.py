# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
GPU-NPU 等价分析引擎

使用 LLM 分析 GPU 算子仓和 NPU 算子仓的代码对，发现等价关系
"""

import logging
import asyncio
import json
import uuid
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple, TYPE_CHECKING
from pathlib import Path

from ..gpu_collector.models import (
    CrossPlatformMapping,
    GPUPlatform,
    MappingEquivalenceLevel,
)
from ..gpu_collector.storage import GPUStorage
from .predefined_mappings import get_predefined_mapping

if TYPE_CHECKING:
    from ..llm import UnifiedLLMClient
    from ..llm.messages import Message

logger = logging.getLogger(__name__)


# LLM 分析 Prompt 模板
ANALYSIS_PROMPT_TEMPLATE = """You are an expert in GPU (CUDA/CUTLASS/cuBLAS) to Huawei Ascend NPU (AscendC) cross-platform optimization.

Analyze the following GPU and NPU code pair to determine their functional equivalence.

## GPU Code ({gpu_platform})
```{gpu_code_type}
{gpu_code}
```

## NPU Code (AscendC)
```{npu_code_type}
{npu_code}
```

## Analysis Task

Determine:
1. Are these two code segments implementing the same operation?
2. What is the NPU equivalent API for the GPU API shown?
3. What adaptation is needed to migrate from GPU to NPU?
4. What optimization patterns can be transferred (tiling, shared memory, Tensor Core)?

## Output Format

Respond with a JSON object:
{{
    "is_equivalent": true/false,
    "npu_equivalent": "Matmul" or "N/A",
    "equivalence_level": "exact|similar|conceptual",
    "confidence": 0.0-1.0,
    "adaptation_notes": "Brief notes on differences and required changes",
    "optimization_hints": "tiling|shared_memory|tensor_core|none"
}}

Rules:
- npu_equivalent: The main AscendC API name that provides equivalent functionality
- equivalence_level: exact (direct replacement), similar (with parameter/interface changes), conceptual (same idea, different implementation)
- confidence: How certain you are about this mapping (0.0-1.0)
- optimization_hints: What GPU optimization patterns can transfer to NPU
- If no equivalent exists, set is_equivalent=false and npu_equivalent="N/A"
"""


@dataclass
class AnalysisResult:
    """分析结果"""
    is_equivalent: bool
    npu_equivalent: str
    equivalence_level: MappingEquivalenceLevel
    confidence: float
    adaptation_notes: str
    optimization_hints: str
    parsing_failed: bool = False

    def to_cross_platform_mapping(
        self,
        gpu_api: str,
        platform: GPUPlatform,
        mapping_id: Optional[str] = None,
    ) -> CrossPlatformMapping:
        """转换为 CrossPlatformMapping"""
        return CrossPlatformMapping(
            mapping_id=mapping_id or str(uuid.uuid4()),
            gpu_api=gpu_api,
            npu_api=self.npu_equivalent,
            platform=platform,
            equivalence_level=self.equivalence_level,
            adaptation_notes=self.adaptation_notes,
            confidence=self.confidence,
            source="llm_suggested",
        )


@dataclass
class FilePairAnalysis:
    """文件对分析结果"""
    gpu_file: str
    npu_file: str
    gpu_api: str
    result: AnalysisResult
    gpu_platform: GPUPlatform = GPUPlatform.CUDA
    parsing_failed: bool = False


class GPUNPUAnalysisEngine:
    """
    GPU-NPU 等价分析引擎

    使用 LLM 分析 GPU 和 NPU 代码对，发现等价关系并提取优化知识
    """

    def __init__(
        self,
        llm_client: Optional["UnifiedLLMClient"] = None,
        storage: Optional[GPUStorage] = None,
        max_retries: int = 3,
        max_tokens_per_pair: int = 2000,
        max_pairs_per_call: int = 50,
        temperature: float = 0.1,
    ):
        """
        初始化分析引擎

        Args:
            llm_client: LLM 客户端
            storage: GPU 存储实例
            max_retries: JSON 解析失败最大重试次数
            max_tokens_per_pair: 每对代码最大 token 数
            max_pairs_per_call: 单次调用最大分析文件对数
            temperature: LLM temperature
        """
        self._llm_client = llm_client
        self._storage = storage
        self._max_retries = max_retries
        self._max_tokens_per_pair = max_tokens_per_pair
        self._max_pairs_per_call = max_pairs_per_call
        self._temperature = temperature

        logger.info(
            f"GPUNPUAnalysisEngine initialized (max_retries={max_retries}, "
            f"max_tokens={max_tokens_per_pair}, max_pairs={max_pairs_per_call})"
        )

    async def analyze_file_pair(
        self,
        gpu_file: Path,
        npu_file: Path,
        gpu_platform: GPUPlatform = GPUPlatform.CUDA,
        gpu_api_name: Optional[str] = None,
    ) -> FilePairAnalysis:
        """
        分析一对 GPU 和 NPU 文件

        Args:
            gpu_file: GPU 代码文件路径
            npu_file: NPU 代码文件路径
            gpu_platform: GPU 平台类型
            gpu_api_name: GPU API 名称（可选，从文件推断）

        Returns:
            FilePairAnalysis 结果
        """
        try:
            # 读取文件内容
            gpu_code = gpu_file.read_text(encoding="utf-8")
            npu_code = npu_file.read_text(encoding="utf-8")

            # 推断 GPU API 名称（从文件名或内容）
            if gpu_api_name is None:
                gpu_api_name = self._infer_gpu_api(gpu_code, gpu_file.name)

            # 构建 prompt
            prompt = self._build_analysis_prompt(
                gpu_code=gpu_code,
                npu_code=npu_code,
                gpu_platform=gpu_platform,
            )

            # 调用 LLM
            result = await self._call_llm_with_retry(prompt)

            return FilePairAnalysis(
                gpu_file=str(gpu_file),
                npu_file=str(npu_file),
                gpu_api=gpu_api_name,
                result=result,
                gpu_platform=gpu_platform,
                parsing_failed=result.parsing_failed,
            )

        except Exception as e:
            logger.error(f"Failed to analyze file pair {gpu_file} - {npu_file}: {e}")
            return FilePairAnalysis(
                gpu_file=str(gpu_file),
                npu_file=str(npu_file),
                gpu_api=gpu_api_name or "unknown",
                result=AnalysisResult(
                    is_equivalent=False,
                    npu_equivalent="N/A",
                    equivalence_level=MappingEquivalenceLevel.CONCEPTUAL_ONLY,
                    confidence=0.0,
                    adaptation_notes=f"Analysis failed: {str(e)}",
                    optimization_hints="none",
                    parsing_failed=True,
                ),
                gpu_platform=gpu_platform,
                parsing_failed=True,
            )

    async def analyze_multiple_pairs(
        self,
        file_pairs: List[tuple[Path, Path]],
        gpu_platform: GPUPlatform = GPUPlatform.CUDA,
    ) -> List[FilePairAnalysis]:
        """
        批量分析多对文件

        Args:
            file_pairs: [(gpu_file, npu_file), ...] 列表
            gpu_platform: GPU 平台类型

        Returns:
            FilePairAnalysis 结果列表
        """
        results = []

        for gpu_file, npu_file in file_pairs[:self._max_pairs_per_call]:
            result = await self.analyze_file_pair(gpu_file, npu_file, gpu_platform)
            results.append(result)

            # Token 预算控制：每对分析后检查
            await asyncio.sleep(0.1)  # 避免请求过快

        return results

    def _infer_gpu_api(self, code: str, filename: str) -> str:
        """从文件名或代码内容推断 GPU API 名称"""
        # 从文件名推断
        name = filename.split(".")[0]
        if name.endswith("_kernel"):
            name = name.replace("_kernel", "")
        if name.endswith("_op"):
            name = name.replace("_op", "")

        return name.upper()

    def _build_analysis_prompt(
        self,
        gpu_code: str,
        npu_code: str,
        gpu_platform: GPUPlatform,
    ) -> str:
        """构建分析 prompt"""
        # 截断代码以控制 token
        gpu_code = gpu_code[: self._max_tokens_per_pair * 4]  # 粗略估计
        npu_code = npu_code[: self._max_tokens_per_pair * 4]

        # 确定 GPU 代码类型
        gpu_code_type = "cuda" if gpu_platform == GPUPlatform.CUDA else gpu_platform.value

        return ANALYSIS_PROMPT_TEMPLATE.format(
            gpu_platform=gpu_platform.value.upper(),
            gpu_code_type=gpu_code_type,
            gpu_code=gpu_code,
            npu_code_type="cpp",
            npu_code=npu_code,
        )

    async def _call_llm_with_retry(
        self,
        prompt: str,
    ) -> AnalysisResult:
        """调用 LLM 并处理 JSON 解析失败重试"""
        if not self._llm_client:
            logger.warning("LLM client not provided, returning empty result")
            return AnalysisResult(
                is_equivalent=False,
                npu_equivalent="N/A",
                equivalence_level=MappingEquivalenceLevel.CONCEPTUAL_ONLY,
                confidence=0.0,
                adaptation_notes="LLM client not available",
                optimization_hints="none",
                parsing_failed=True,
            )

        from ..llm import Message, MessageRole

        messages = [Message(role=MessageRole.USER, content=prompt)]
        backoff = 1.0

        for attempt in range(self._max_retries):
            try:
                response = await self._llm_client.chat(
                    messages=messages,
                    max_tokens=512,
                    temperature=self._temperature,
                )

                # 解析 JSON
                data = json.loads(response.content)
                return self._parse_analysis_result(data)

            except json.JSONDecodeError as e:
                logger.warning(
                    f"JSON parsing failed (attempt {attempt + 1}/{self._max_retries}): {e}"
                )
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(backoff)
                    backoff *= 2  # exponential backoff
                else:
                    logger.error(f"JSON parsing failed after {self._max_retries} attempts")
                    return AnalysisResult(
                        is_equivalent=False,
                        npu_equivalent="N/A",
                        equivalence_level=MappingEquivalenceLevel.CONCEPTUAL_ONLY,
                        confidence=0.0,
                        adaptation_notes=f"JSON parsing failed: {str(e)}",
                        optimization_hints="none",
                        parsing_failed=True,
                    )

            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(backoff)
                    backoff *= 2
                else:
                    return AnalysisResult(
                        is_equivalent=False,
                        npu_equivalent="N/A",
                        equivalence_level=MappingEquivalenceLevel.CONCEPTUAL_ONLY,
                        confidence=0.0,
                        adaptation_notes=f"LLM call failed: {str(e)}",
                        optimization_hints="none",
                        parsing_failed=True,
                    )

        return AnalysisResult(
            is_equivalent=False,
            npu_equivalent="N/A",
            equivalence_level=MappingEquivalenceLevel.CONCEPTUAL_ONLY,
            confidence=0.0,
            adaptation_notes="Max retries exceeded",
            optimization_hints="none",
            parsing_failed=True,
        )

    def _parse_analysis_result(self, data: Dict[str, Any]) -> AnalysisResult:
        """解析 LLM 返回的 JSON 结果"""
        is_equivalent = data.get("is_equivalent", False)
        npu_equivalent = data.get("npu_equivalent", "N/A")

        # 解析 equivalence_level
        equiv_str = data.get("equivalence_level", "conceptual").lower()
        if equiv_str == "exact":
            equiv_level = MappingEquivalenceLevel.EXACT
        elif equiv_str == "similar":
            equiv_level = MappingEquivalenceLevel.SIMILAR
        else:
            equiv_level = MappingEquivalenceLevel.CONCEPTUAL_ONLY

        return AnalysisResult(
            is_equivalent=is_equivalent,
            npu_equivalent=npu_equivalent,
            equivalence_level=equiv_level,
            confidence=float(data.get("confidence", 0.0)),
            adaptation_notes=data.get("adaptation_notes", ""),
            optimization_hints=data.get("optimization_hints", "none"),
            parsing_failed=False,
        )

    def store_analysis_result(
        self,
        analysis: FilePairAnalysis,
        dry_run: bool = False,
    ) -> bool:
        """
        存储分析结果

        Args:
            analysis: 分析结果
            dry_run: 是否为 dry-run 模式（不存储）

        Returns:
            是否成功
        """
        if dry_run:
            logger.info(f"Dry-run: would store {analysis.gpu_api} -> {analysis.result.npu_equivalent}")
            return True

        if not analysis.result.is_equivalent:
            logger.info(f"Skipping non-equivalent mapping: {analysis.gpu_api}")
            return False

        # 转换为 CrossPlatformMapping
        mapping = analysis.result.to_cross_platform_mapping(
            gpu_api=analysis.gpu_api,
            platform=analysis.gpu_platform,
        )

        # 根据置信度确定 source
        source = "llm_high_conf" if analysis.result.confidence >= 0.8 else "llm_suggested"

        # 存储
        if self._storage:
            return self._storage.store_cross_platform_mapping(mapping, source=source)

        logger.warning("No storage configured, skipping storage")
        return False

    def store_analysis_results(
        self,
        analyses: List[FilePairAnalysis],
        dry_run: bool = False,
    ) -> Tuple[int, int]:
        """
        批量存储分析结果

        Args:
            analyses: 分析结果列表
            dry_run: 是否为 dry-run 模式

        Returns:
            (成功数, 失败数)
        """
        if dry_run:
            equivalent_count = sum(1 for a in analyses if a.result.is_equivalent)
            logger.info(f"Dry-run: would store {equivalent_count} mappings")
            return (equivalent_count, 0)

        success = 0
        failed = 0

        for analysis in analyses:
            if self.store_analysis_result(analysis, dry_run=False):
                success += 1
            else:
                failed += 1

        logger.info(f"Storage complete: {success} succeeded, {failed} failed")
        return (success, failed)
