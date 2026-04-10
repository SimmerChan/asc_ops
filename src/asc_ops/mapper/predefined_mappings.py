# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
预定义 GPU → NPU 映射表

包含核心同步、内存、计算 API 的精确映射
"""

from typing import Optional, Dict, Any

from ..gpu_collector.models import GPUPlatform, MappingEquivalenceLevel


# CUDA → NPU 核心映射
CUDA_MAPPINGS = {
    # 同步 API
    "__syncthreads": {
        "npu_api": "SyncAll",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "完全等价，无参数差异",
    },
    "__threadfence": {
        "npu_api": "SyncCk",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "同步同一 block 内的所有线程",
    },
    "__threadfence_block": {
        "npu_api": "SyncCk",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "等同于 SyncCk",
    },
    "__threadfence_system": {
        "npu_api": "SyncGlobal",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "全局同步，跨设备",
    },

    # 内存顺序
    "__threadfence_memory": {
        "npu_api": "MemFence",
        "equivalence": MappingEquivalenceLevel.SIMILAR,
        "notes": "内存栅栏，需适配具体实现",
    },

    # Warp 级原语
    "__shfl": {
        "npu_api": "VecShuffle",
        "equivalence": MappingEquivalenceLevel.SIMILAR,
        "notes": "Warp 内线程数据交换，支持多种模式",
    },
    "__shfl_up": {
        "npu_api": "VecShuffleUp",
        "equivalence": MappingEquivalenceLevel.SIMILAR,
        "notes": "向上 shuffle",
    },
    "__shfl_down": {
        "npu_api": "VecShuffleDown",
        "equivalence": MappingEquivalenceLevel.SIMILAR,
        "notes": "向下 shuffle",
    },
    "__shfl_xor": {
        "npu_api": "VecShuffleXor",
        "equivalence": MappingEquivalenceLevel.SIMILAR,
        "notes": "异或 shuffle",
    },
    "__ballot": {
        "npu_api": "VecActiveCount",
        "equivalence": MappingEquivalenceLevel.SIMILAR,
        "notes": "Warp 内投票",
    },
    "__any": {
        "npu_api": "VecAny",
        "equivalence": MappingEquivalenceLevel.SIMILAR,
        "notes": "Warp 内任意线程条件为真",
    },
    "__all": {
        "npu_api": "VecAll",
        "equivalence": MappingEquivalenceLevel.SIMILAR,
        "notes": "Warp 内所有线程条件为真",
    },

    # 原子操作
    "atomicAdd": {
        "npu_api": "AtomAdd",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "原子加法",
    },
    "atomicExch": {
        "npu_api": "AtomExch",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "原子交换",
    },
    "atomicCAS": {
        "npu_api": "AtomCmp",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "原子比较并交换",
    },
    "atomicMin": {
        "npu_api": "AtomMin",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "原子最小值",
    },
    "atomicMax": {
        "npu_api": "AtomMax",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "原子最大值",
    },

    # WMMA (Tensor Core)
    "wmma::load_matrix_sync": {
        "npu_api": "Load2D",
        "equivalence": MappingEquivalenceLevel.SIMILAR,
        "notes": "NPU 使用 Load2D，需适配 layout 参数 (row_major/col_major)",
    },
    "wmma::store_matrix_sync": {
        "npu_api": "Store2D",
        "equivalence": MappingEquivalenceLevel.SIMILAR,
        "notes": "NPU 使用 Store2D，需适配 layout 参数",
    },
    "wmma::mma_sync": {
        "npu_api": "Matmul",
        "equivalence": MappingEquivalenceLevel.SIMILAR,
        "notes": "Tensor Core 矩阵乘法，NPU 使用 Matmul 替代",
    },

    # 内存拷贝
    "memcpy": {
        "npu_api": "DataCopy",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "内存拷贝，支持异步版本",
    },
    "memset": {
        "npu_api": "Set",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "内存设置",
    },

    # 流/事件
    "cudaStreamCreate": {
        "npu_api": "CreateStream",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "创建流",
    },
    "cudaStreamSynchronize": {
        "npu_api": "SyncStream",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "流同步",
    },
    "cudaEventCreate": {
        "npu_api": "CreateEvent",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "创建事件",
    },
    "cudaEventRecord": {
        "npu_api": "RecordEvent",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "记录事件到流",
    },
    "cudaEventSync": {
        "npu_api": "SyncEvent",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "事件同步",
    },
}


# CUTLASS → NPU 映射
CUTLASS_MAPPINGS = {
    "cutlass::gemm::device::Gemm": {
        "npu_api": "Matmul",
        "equivalence": MappingEquivalenceLevel.SIMILAR,
        "notes": "CUTLASS GEMM 对应 NPU Matmul，需适配 template 参数",
    },
    "cutlass::conv::device::Conv2d": {
        "npu_api": "卷积 API",
        "equivalence": MappingEquivalenceLevel.SIMILAR,
        "notes": "CUTLASS Conv2d 对应 NPU 卷积 API",
    },
    "cutlass::warp::WarpMma": {
        "npu_api": "WarpMatmul",
        "equivalence": MappingEquivalenceLevel.SIMILAR,
        "notes": "Warp 级矩阵乘法",
    },
}


# cuBLAS → NPU 映射
CUBLAS_MAPPINGS = {
    "cublasSgemm": {
        "npu_api": "Matmul",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "单精度 GEMM 直接对应",
    },
    "cublasDgemm": {
        "npu_api": "Matmul",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "双精度 GEMM 直接对应",
    },
    "cublasHgemm": {
        "npu_api": "Matmul",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "半精度 GEMM 直接对应 (FP16)",
    },
    "cublasGemmEx": {
        "npu_api": "Matmul",
        "equivalence": MappingEquivalenceLevel.SIMILAR,
        "notes": "混合精度 GEMM，NPU Matmul 支持多种数据类型",
    },
    "cublasCreate": {
        "npu_api": "CreateHandle",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "创建 cuBLAS handle，NPU 使用 CreateHandle",
    },
    "cublasDestroy": {
        "npu_api": "DestroyHandle",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "销毁 handle",
    },
    "cublasSetVector": {
        "npu_api": "SetVector",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "设置向量数据",
    },
    "cublasGetVector": {
        "npu_api": "GetVector",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "获取向量数据",
    },
    "cublasSaxpy": {
        "npu_api": "Axpy",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "单精度向量缩放加法 y = alpha*x + y",
    },
    "cublasDaxpy": {
        "npu_api": "Axpy",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "双精度向量缩放加法",
    },
    "cublasScopy": {
        "npu_api": "Copy",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "向量拷贝",
    },
    "cublasSdot": {
        "npu_api": "Dot",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "单精度点积",
    },
    "cublasDdot": {
        "npu_api": "Dot",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "双精度点积",
    },
    "cublasSnrm2": {
        "npu_api": "Nrm2",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "单精度 L2 范数",
    },
    "cublasIsamax": {
        "npu_api": "Amax",
        "equivalence": MappingEquivalenceLevel.EXACT,
        "notes": "查找单精度向量最大绝对值索引",
    },
}


def get_predefined_mapping(
    gpu_api: str,
    platform: GPUPlatform,
) -> Optional[Dict[str, Any]]:
    """
    获取预定义映射

    Args:
        gpu_api: GPU API 名称
        platform: GPU 平台

    Returns:
        映射信息或 None
    """
    if platform == GPUPlatform.CUDA:
        return CUDA_MAPPINGS.get(gpu_api)
    elif platform == GPUPlatform.CUTLASS:
        return CUTLASS_MAPPINGS.get(gpu_api)
    elif platform == GPUPlatform.CUBLAS:
        return CUBLAS_MAPPINGS.get(gpu_api)
    return None


def get_all_predefined_apis() -> list:
    """获取所有预定义 API 列表"""
    apis = []
    apis.extend(CUDA_MAPPINGS.keys())
    apis.extend(CUTLASS_MAPPINGS.keys())
    apis.extend(CUBLAS_MAPPINGS.keys())
    return apis
