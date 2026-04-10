# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
GPU 算子知识数据模型
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class GPUPlatform(Enum):
    """GPU 平台来源"""
    CUDA = "cuda"
    CUTLASS = "cutlass"
    CUBLAS = "cublas"
    CUDNN = "cudnn"


class MappingEquivalenceLevel(Enum):
    """跨平台映射等价级别"""
    EXACT = "exact"              # 完全等价，可直接替换
    SIMILAR = "similar"          # 功能相似，需适配
    CONCEPTUAL_ONLY = "conceptual_only"  # 概念相似，无直接映射


@dataclass
class GPUKernelArchitecture:
    """GPU Kernel 架构信息"""
    compute_capability: str = ""  # 如 "8.0", "9.0"
    warp_size: int = 32
    max_threads_per_block: int = 1024
    shared_memory_per_block: int = 49152
    registers_per_thread: int = 255


@dataclass
class GPUKernelPerformance:
    """GPU Kernel 性能特征"""
    memory_pattern: str = ""  # "coalesced", "tiled", "strided"
    cache_usage: str = ""      # "shared", "local", "none"
    occupancy: Optional[float] = None  # 0.0 ~ 1.0
    estimated_flops: Optional[int] = None
    memory_bandwidth_gbps: Optional[int] = None


@dataclass
class GPUKernelKnowledge:
    """GPU 算子知识"""
    kernel_id: str
    kernel_name: str
    platform: GPUPlatform

    description: str = ""
    category: str = ""  # "matmul", "conv", "reduction", etc.

    architecture: GPUKernelArchitecture = field(default_factory=GPUKernelArchitecture)
    performance: GPUKernelPerformance = field(default_factory=GPUKernelPerformance)

    template_parameters: List[str] = field(default_factory=list)
    launch_parameters: Dict[str, Any] = field(default_factory=dict)

    source_file: str = ""
    source_repo: str = ""
    source_url: str = ""

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class GPURepository:
    """GPU 代码仓库信息"""
    repo_id: str
    repo_name: str
    platform: GPUPlatform

    clone_url: str = ""
    local_path: str = ""
    api_surface: List[str] = field(default_factory=list)  # 导出的主要 API 列表

    documentation_url: str = ""
    version: str = ""

    last_fetch_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class GPUAPIInfo:
    """GPU API 信息"""
    api_id: str
    api_name: str
    platform: GPUPlatform

    full_signature: str = ""
    description: str = ""

    parameters: List[str] = field(default_factory=list)
    return_type: str = ""

    category: str = ""
    subcategory: str = ""

    source_file: str = ""
    documentation_url: str = ""

    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class CrossPlatformMapping:
    """GPU → NPU 跨平台映射"""
    mapping_id: str
    gpu_api: str
    npu_api: str
    platform: GPUPlatform

    equivalence_level: MappingEquivalenceLevel

    adaptation_notes: str = ""
    usage_example: str = ""

    source: str = ""  # "manual", "llm_generated", "community"

    confidence: float = 0.5

    related_mappings: List[str] = field(default_factory=list)  # 关联的其他映射 ID

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
