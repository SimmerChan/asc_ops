# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
跨平台映射模块

GPU API → NPU API 映射引擎
"""

from .engine import MapperEngine, MappingResult
from .predefined_mappings import (
    get_predefined_mapping,
    get_all_predefined_apis,
    CUDA_MAPPINGS,
    CUTLASS_MAPPINGS,
    CUBLAS_MAPPINGS,
)

__all__ = [
    "MapperEngine",
    "MappingResult",
    "get_predefined_mapping",
    "get_all_predefined_apis",
    "CUDA_MAPPINGS",
    "CUTLASS_MAPPINGS",
    "CUBLAS_MAPPINGS",
]
