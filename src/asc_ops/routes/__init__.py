# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
API 路由模块
"""

from .query import router as query_router
from .management import router as management_router

__all__ = [
    "query_router",
    "management_router",
]
