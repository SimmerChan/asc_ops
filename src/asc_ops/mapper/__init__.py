# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
跨平台映射模块

GPU API → NPU API 映射引擎
"""

from .engine import MapperEngine, MappingResult

__all__ = [
    "MapperEngine",
    "MappingResult",
]
