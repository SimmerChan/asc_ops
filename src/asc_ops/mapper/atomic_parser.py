# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
原子级 API 提取器

从 GPU/NPU 代码中提取原子 API 调用
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)


@dataclass
class AtomicAPICall:
    """原子 API 调用"""
    api_name: str
    api_type: str  # "cuda", "cub", "cutlass", "atomic", "npu", "aclnn", "ascendc"
    context: str  # 代码上下文（周围几行）
    line_number: int


# GPU 原子 API 模式
GPU_API_PATTERNS = {
    # CUDA 运行时 API
    "cuda": [
        r"\bcudaMalloc\s*\(",
        r"\bcudaMemcpy\s*\(",
        r"\bcudaMemset\s*\(",
        r"\bcudaFree\s*\(",
        r"\bcudaStreamCreate\s*\(",
        r"\bcudaStreamDestroy\s*\(",
        r"\bcudaStreamSync\b",
        r"\bcudaEventCreate\s*\(",
        r"\bcudaEventRecord\s*\(",
        r"\bcudaEventSync\b",
        r"\bcudaGetLastError\s*\(",
        r"\bcudaPeekAtLastError\s*\(",
        r"\bcudaDeviceSynchronize\s*\(",
    ],
    # CUB 库 API (类型引用 + 方法调用)
    "cub": [
        r"\bcub::BlockScan\s*<",
        r"\bcub::WarpScan\s*<",
        r"\bcub::BlockReduce\s*<",
        r"\bcub::WarpReduce\s*<",
        r"\bcub::DeviceScan\s*",
        r"\bcub::DeviceSort\s*",
        r"\bcub::DeviceReduce\s*",
        r"\bcub::DeviceRadixSort\s*",
        r"BlockScan::TempStorage",
        r"BlockScan::InclusiveSum",
        r"BlockScan::ExclusiveSum",
    ],
    # 自定义 Kernel 调用 (FBGEMM 等)
    "custom_kernel": [
        r"\binclusive_sum_scan_kernel\s*\(",
        r"\bbinary_search_range\s*\(",
        r"\bkeyed_jagged_index_select_dim\d?_kernel\s*\(",
        r"\bindex_select_scalar_cumsum_kernel\s*\(",
        r"\bsparse_emb_forward_kernel\s*\(",
        r"\bgemm_kernel\s*\(",
    ],
    # CUTLASS API
    "cutlass": [
        r"\bcutlass::\w+",
        r"\bcutlass_\w+_\w+\s*\(",
        r"\bcutlass_gemm\s*\(",
        r"\bCUTLASS_CHECK\s*\(",
    ],
    # CUDA 原子操作
    "atomic": [
        r"\batomicAdd\s*\(",
        r"\batomicExch\s*\(",
        r"\batomicCAS\s*\(",
        r"\batomicMin\s*\(",
        r"\batomicMax\s*\(",
        r"\batomicAnd\s*\(",
        r"\batomicOr\s*\(",
        r"\batomicXor\s*\(",
    ],
    # CUDA 同步原语
    "sync": [
        r"\b__syncthreads\s*\(",
        r"\b__threadfence\s*\(",
        r"\b__threadfence_block\s*\(",
        r"\b__threadfence_system\s*\(",
        r"\bsyncwarp\s*\(",
    ],
    # CUDA PTX 内在函数
    "ptx": [
        r"\bmov\.u32\s*\(",
        r"\bld\.global\.b\d+\s*\(",
        r"\bst\.global\.b\d+\s*\(",
        r"\bshl\.b\d+\s*\(",
        r"\b shr\.b\d+\s*\(",
    ],
    # WMMA (Tensor Core)
    "wmma": [
        r"\bwmma::load_matrix_sync\s*\(",
        r"\bwmma::store_matrix_sync\s*\(",
        r"\bwmma::mma_sync\s*\(",
        r"\bwmma::fill_fragment\s*\(",
    ],
    # Thrust (CUDA STL)
    "thrust": [
        r"\bthrust::\w+",
        r"\bthrust::device_ptr",
    ],
}

# NPU 原子 API 模式
NPU_API_PATTERNS = {
    # ACLNN 库 API
    "aclnn": [
        r"\baclnn\w+\s*\(",
        r"\baclnnAdd\s*\(",
        r"\baclnnMatmul\s*\(",
        r"\baclnnConv2d\s*\(",
        r"\baclnnRelu\s*\(",
        r"\baclnnMaxPool2d\s*\(",
        r"\baclnnBatchNorm\s*\(",
        r"\baclnnSoftmax\s*\(",
        r"\baclnnSigmoid\s*\(",
        r"\baclnnTanh\s*\(",
        r"\baclnnDropout\s*\(",
        r"\baclnnCat\s*\(",
        r"\baclnnConcat\s*\(",
        r"\baclnnSplit\s*\(",
        r"\baclnnReshape\s*\(",
        r"\baclnnTranspose\s*\(",
        r"\baclnnPermute\s*\(",
        r"\baclnnGather\s*\(",
        r"\baclnnScatter\s*\(",
        r"\baclnnIndexSelect\s*\(",
        r"\baclnnGelu\s*\(",
        r"\baclnnLayerNorm\s*\(",
        r"\baclnnEmbedding\s*\(",
        r"\baclnnCrossEntropyLoss\s*\(",
    ],
    # ACLNN 异步操作 (EXEC_NPU_CMD 宏包装)
    "aclnn_async": [
        r"\bEXEC_NPU_CMD\s*\(\s*aclnn\w+",
        r"\baclnnSelectDim1ToPermute",
        r"\baclnnPermute2dSparseData",
        r"\basynchronous_complete_cumsum_npu",
        r"\baclnnWait\s*\(",
        r"\baclnnAddAsync\s*\(",
        r"\baclnnMatmulAsync\s*\(",
        r"\baclnnConv2dAsync\s*\(",
    ],
    # AscendC 核心 API
    "ascendc": [
        r"\bLoad2D\s*\(",
        r"\bStore2D\s*\(",
        r"\bMatmul\s*\(",
        r"\bGemm\s*\(",
        r"\bSyncAll\s*\(",
        r"\bLocalTensor\s*\(",
        r"\bTensor\s*\(",
        r"\bGetLocalTensor\s*\(",
        r"\bGetGlobalTensor\s*\(",
        r"\bAlloc\s*\(",
        r"\bFree\s*\(",
        r"\bFill\s*\(",
        r"\bCopy\s*\(",
        r"\bAdd\s*\(",
        r"\bSub\s*\(",
        r"\bMul\s*\(",
        r"\bDiv\s*\(",
    ],
    # AscendC 数据移动
    "ascendc_movement": [
        r"\bDataMove\s*\(",
        r"\bSet\s*\(",
        r"\bBroadcast\s*\(",
        r"\bReduce\s*\(",
        r"\bReshape\s*\(",
        r"\bBroadcastTo\s*\(",
        r"\bReduceSum\s*\(",
    ],
}


class AtomicCodeParser:
    """原子级 API 代码解析器"""

    @staticmethod
    def extract_gpu_apis(code: str, context_lines: int = 3) -> List[AtomicAPICall]:
        """
        从 GPU 代码中提取原子 API 调用

        Args:
            code: GPU 源代码
            context_lines: 上下文行数

        Returns:
            原子 API 调用列表
        """
        results: List[AtomicAPICall] = []
        seen: Dict[str, int] = {}  # api_name -> first line number

        lines = code.split("\n")

        for api_type, patterns in GPU_API_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, code):
                    api_name = AtomicCodeParser._extract_api_name(match.group(), api_type)

                    # 去重：同一 API 只记录第一次出现
                    if api_name not in seen:
                        seen[api_name] = match.start()

                        # 提取上下文
                        line_num = code[:match.start()].count("\n")
                        context = AtomicCodeParser._extract_context(lines, line_num, context_lines)

                        results.append(AtomicAPICall(
                            api_name=api_name,
                            api_type=api_type,
                            context=context,
                            line_number=line_num + 1,
                        ))

        return results

    @staticmethod
    def extract_npu_apis(code: str, context_lines: int = 3) -> List[AtomicAPICall]:
        """
        从 NPU 代码中提取原子 API 调用

        Args:
            code: NPU 源代码
            context_lines: 上下文行数

        Returns:
            原子 API 调用列表
        """
        results: List[AtomicAPICall] = []
        seen: Dict[str, int] = {}

        lines = code.split("\n")

        for api_type, patterns in NPU_API_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, code):
                    api_name = AtomicCodeParser._extract_api_name(match.group(), api_type)

                    if api_name not in seen:
                        seen[api_name] = match.start()

                        line_num = code[:match.start()].count("\n")
                        context = AtomicCodeParser._extract_context(lines, line_num, context_lines)

                        results.append(AtomicAPICall(
                            api_name=api_name,
                            api_type=api_type,
                            context=context,
                            line_number=line_num + 1,
                        ))

        return results

    @staticmethod
    def _extract_api_name(match_str: str, api_type: str) -> str:
        """从匹配字符串中提取 API 名称"""
        name = match_str.strip()
        # 移除函数调用括号
        if name.endswith("("):
            name = name[:-1]
        # 移除 EXEC_NPU_CMD 宏调用中的前缀
        if "EXEC_NPU_CMD" in name:
            # 提取宏参数中的实际 API 名
            import re
            m = re.search(r'aclnn\w+', name)
            if m:
                name = m.group()
        return name

    @staticmethod
    def _extract_context(lines: List[str], line_num: int, context_lines: int) -> str:
        """提取代码上下文"""
        start = max(0, line_num - context_lines)
        end = min(len(lines), line_num + context_lines + 1)
        return "\n".join(lines[start:end])

    @staticmethod
    def create_api_pairs(
        gpu_apis: List[AtomicAPICall],
        npu_apis: List[AtomicAPICall],
    ) -> List[Tuple[AtomicAPICall, AtomicAPICall]]:
        """
        创建 GPU-NPU API 对

        策略：
        1. 相同类型的 API 优先配对（如 cub -> aclnn_async）
        2. 不同类型但语义相似的配对（如 atomic -> ascendc）

        Args:
            gpu_apis: GPU API 列表
            npu_apis: NPU API 列表

        Returns:
            (GPU API, NPU API) 元组列表
        """
        pairs: List[Tuple[AtomicAPICall, AtomicAPICall]] = []

        # 按类型分组
        gpu_by_type: Dict[str, List[AtomicAPICall]] = {}
        npu_by_type: Dict[str, List[AtomicAPICall]] = {}

        for api in gpu_apis:
            gpu_by_type.setdefault(api.api_type, []).append(api)

        for api in npu_apis:
            npu_by_type.setdefault(api.api_type, []).append(api)

        # 类型匹配映射
        TYPE_AFFINITY = {
            # GPU type -> NPU type 优先级
            "cub": ["aclnn_async", "ascendc"],
            "atomic": ["ascendc", "aclnn"],
            "sync": ["ascendc"],
            "wmma": ["ascendc", "aclnn"],
            "cuda": ["aclnn", "ascendc"],
            "ptx": ["ascendc"],
        }

        for gpu_type, npu_types in TYPE_AFFINITY.items():
            if gpu_type not in gpu_by_type:
                continue

            for npu_type in npu_types:
                if npu_type not in npu_by_type:
                    continue

                # 配对同类型的 API
                for gpu_api in gpu_by_type[gpu_type]:
                    for npu_api in npu_by_type[npu_type]:
                        pairs.append((gpu_api, npu_api))

        return pairs


def extract_atomic_mappings_from_file_pair(
    gpu_code: str,
    npu_code: str,
) -> List[Tuple[str, str, str]]:
    """
    从文件对中提取原子 API 映射对

    Args:
        gpu_code: GPU 源代码
        npu_code: NPU 源代码

    Returns:
        [(gpu_api, npu_api, context), ...] 列表
    """
    gpu_apis = AtomicCodeParser.extract_gpu_apis(gpu_code)
    npu_apis = AtomicCodeParser.extract_npu_apis(npu_code)

    pairs = AtomicCodeParser.create_api_pairs(gpu_apis, npu_apis)

    return [(gpu.api_name, npu.api_name, f"GPU:\n{gpu.context}\n\nNPU:\n{npu.context}") for gpu, npu in pairs]


if __name__ == "__main__":
    # 简单测试
    test_code = """
    #include <cub/cub.cuh>

    __global__ void my_kernel(float* data) {
        int idx = blockIdx.x * blockDim.x + threadIdx.x;
        atomicAdd(&data[0], 1.0f);
        cub::BlockScan(temp_storage);
        __syncthreads();
    }
    """

    apis = AtomicCodeParser.extract_gpu_apis(test_code)
    print("Extracted GPU APIs:")
    for api in apis:
        print(f"  - {api.api_name} ({api.api_type}) at line {api.line_number}")
