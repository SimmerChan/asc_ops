# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
GPU-NPU 等价分析引擎

使用 LLM 分析 GPU 算子仓和 NPU 算子仓的代码对，发现等价关系
"""

import logging
import asyncio
import json
import re
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
from .atomic_parser import AtomicCodeParser, AtomicAPICall

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

    async def analyze_file_pair_atomic(
        self,
        gpu_file: Path,
        npu_file: Path,
        gpu_platform: GPUPlatform = GPUPlatform.CUDA,
    ) -> List[FilePairAnalysis]:
        """
        原子级分析：提取文件中的原子 API 调用，对每个 API pair 单独进行 GPU→NPU 映射分析

        Args:
            gpu_file: GPU 代码文件路径
            npu_file: NPU 代码文件路径
            gpu_platform: GPU 平台类型

        Returns:
            FilePairAnalysis 结果列表（每个原子 API pair 一个结果）
        """
        try:
            # 读取文件内容
            gpu_code = gpu_file.read_text(encoding="utf-8")
            npu_code = npu_file.read_text(encoding="utf-8")

            # 提取原子 API
            gpu_apis = AtomicCodeParser.extract_gpu_apis(gpu_code)
            npu_apis = AtomicCodeParser.extract_npu_apis(npu_code)

            if not gpu_apis:
                logger.warning(f"No GPU APIs extracted from {gpu_file}")
                return []

            if not npu_apis:
                logger.warning(f"No NPU APIs extracted from {npu_file}")
                return []

            # 创建 API pairs
            api_pairs = AtomicCodeParser.create_api_pairs(gpu_apis, npu_apis)

            if not api_pairs:
                logger.warning(f"No API pairs created for {gpu_file} - {npu_file}")
                return []

            logger.info(f"Created {len(api_pairs)} API pairs from {gpu_file.name}")

            # 对每个 pair 进行 LLM 分析
            results = []
            for gpu_api, npu_api in api_pairs:
                result = await self._analyze_atomic_pair(
                    gpu_api=gpu_api,
                    npu_api=npu_api,
                    gpu_platform=gpu_platform,
                    gpu_file=str(gpu_file),
                    npu_file=str(npu_file),
                )
                results.append(result)

                # 控制请求速率
                await asyncio.sleep(0.1)

            return results

        except Exception as e:
            logger.error(f"Failed atomic analysis for {gpu_file} - {npu_file}: {e}")
            return []

    async def _analyze_atomic_pair(
        self,
        gpu_api: AtomicAPICall,
        npu_api: AtomicAPICall,
        gpu_platform: GPUPlatform,
        gpu_file: str,
        npu_file: str,
    ) -> FilePairAnalysis:
        """分析单个原子 API pair"""

        # 构建原子分析 prompt
        prompt = self._build_atomic_analysis_prompt(
            gpu_api_name=gpu_api.api_name,
            gpu_api_type=gpu_api.api_type,
            gpu_context=gpu_api.context,
            npu_api_name=npu_api.api_name,
            npu_api_type=npu_api.api_type,
            npu_context=npu_api.context,
            gpu_platform=gpu_platform,
        )

        # 调用 LLM
        result = await self._call_llm_with_retry(prompt)

        return FilePairAnalysis(
            gpu_file=gpu_file,
            npu_file=npu_file,
            gpu_api=gpu_api.api_name,
            result=result,
            gpu_platform=gpu_platform,
            parsing_failed=result.parsing_failed,
        )

    def _build_atomic_analysis_prompt(
        self,
        gpu_api_name: str,
        gpu_api_type: str,
        gpu_context: str,
        npu_api_name: str,
        npu_api_type: str,
        npu_context: str,
        gpu_platform: GPUPlatform,
    ) -> str:
        """构建原子级分析 prompt"""

        prompt = f"""You are an expert in GPU (CUDA/CUB) to Huawei AscendC NPU cross-platform optimization.

Analyze the following GPU and NPU API pair to determine their functional equivalence.

## GPU API
- API Name: {gpu_api_name}
- Type: {gpu_api_type}
- Code Context:
```{gpu_platform.value}
{gpu_context}
```

## NPU API
- API Name: {npu_api_name}
- Type: {npu_api_type}
- Code Context:
```cpp
{npu_context}
```

## Analysis Task

Determine:
1. Are these two APIs implementing the same operation?
2. What is the exact NPU equivalent API name?
3. What adaptation is needed to migrate from GPU to NPU?

## Output Format

Respond with a JSON object:
{{
    "is_equivalent": true/false,
    "npu_equivalent": "API name" or "N/A",
    "equivalence_level": "exact|similar|conceptual",
    "confidence": 0.0-1.0,
    "adaptation_notes": "Brief notes on differences",
    "optimization_hints": "tiling|shared_memory|tensor_core|none"
}}

Rules:
- npu_equivalent: The main AscendC API name that provides equivalent functionality
- equivalence_level: exact (direct replacement), similar (with parameter changes), conceptual (same idea)
- If no equivalent exists, set is_equivalent=false and npu_equivalent="N/A"
"""
        return prompt

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
                    max_tokens=2048,  # 需要足够空间给 thinking + text
                    temperature=self._temperature,
                )

                # 解析 JSON - LLM 可能返回 markdown 格式
                raw_content = response.content
                if raw_content.startswith("```"):
                    # 提取 markdown 中的 JSON
                    json_match = re.search(r'\{[\s\S]*\}', raw_content)
                    if json_match:
                        raw_content = json_match.group()
                data = json.loads(raw_content)
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
        """解析 LLM 返回的 JSON 结果

        LLM 可能返回 markdown 格式的 JSON (```json ... ```)，需要先提取
        """
        # 如果 data 不是 dict 类型（可能是字符串形式的 JSON），先尝试解析
        if isinstance(data, str):
            # 尝试从 markdown 代码块中提取 JSON
            json_match = re.search(r'\{[\s\S]*\}', data)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

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

        # 存储所有非 parsing_failed 的结果（不仅仅是 is_equivalent=true 的）
        # 包括 conceptual 级别的映射用于知识积累
        if analysis.result.parsing_failed:
            logger.info(f"Skipping parsing failed: {analysis.gpu_api}")
            return False

        # 转换为 CrossPlatformMapping
        mapping = analysis.result.to_cross_platform_mapping(
            gpu_api=analysis.gpu_api,
            platform=analysis.gpu_platform,
        )

        # 根据置信度和等价级别确定 source
        if analysis.result.is_equivalent and analysis.result.confidence >= 0.8:
            source = "llm_high_conf"
        elif analysis.result.is_equivalent:
            source = "llm_equivalent"
        else:
            source = "llm_suggested"

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
