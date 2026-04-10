# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
管理 API 路由
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime

from ..models import KnowledgeStats

router = APIRouter()


class APIResponse(BaseModel):
    """统一API响应"""
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    meta: Optional[dict] = None


class SyncRequest(BaseModel):
    """同步请求"""
    sync_type: str = Field(
        default="all",
        description="同步类型: api | operator | all",
    )
    force: bool = Field(default=False, description="是否强制全量同步")


class StatusResponse(BaseModel):
    """状态响应"""
    status: str
    version: str
    uptime_seconds: float
    knowledge_stats: Optional[dict] = None


# 全局状态
_start_time = datetime.now()


@router.get("/status", response_model=APIResponse)
async def get_status():
    """
    获取服务状态

    返回服务状态和知识库统计信息
    """
    try:
        uptime = (datetime.now() - _start_time).total_seconds()

        # TODO: 从实际存储获取统计信息
        stats = KnowledgeStats(
            api_count=0,
            operator_count=0,
            bug_fix_count=0,
            optimization_count=0,
            storage_size_mb=0.0,
            last_sync_time=None,
        )

        return APIResponse(
            success=True,
            data={
                "status": "running",
                "version": "0.1.0",
                "uptime_seconds": uptime,
                "knowledge_stats": {
                    "api_count": stats.api_count,
                    "operator_count": stats.operator_count,
                    "bug_fix_count": stats.bug_fix_count,
                    "optimization_count": stats.optimization_count,
                    "storage_size_mb": stats.storage_size_mb,
                    "last_sync_time": (
                        stats.last_sync_time.isoformat()
                        if stats.last_sync_time
                        else None
                    ),
                },
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync", response_model=APIResponse)
async def trigger_sync(request: SyncRequest):
    """
    触发同步

    手动触发 API 或算子知识的增量同步
    """
    try:
        sync_type = request.sync_type

        if sync_type not in ("api", "operator", "all"):
            raise HTTPException(
                status_code=400,
                detail="sync_type must be one of: api, operator, all",
            )

        # TODO: 实现实际的同步逻辑
        # 这里返回占位响应
        return APIResponse(
            success=True,
            data={
                "sync_type": sync_type,
                "status": "sync_triggered",
                "message": f"{sync_type} sync has been triggered",
            },
            meta={"force": request.force},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@router.get("/stats", response_model=APIResponse)
async def get_stats():
    """
    获取知识库统计信息

    返回各知识库的条目数量
    """
    try:
        # TODO: 从实际存储获取统计信息
        stats = KnowledgeStats(
            api_count=0,
            operator_count=0,
            bug_fix_count=0,
            optimization_count=0,
            storage_size_mb=0.0,
            last_sync_time=None,
        )

        return APIResponse(
            success=True,
            data={
                "api_count": stats.api_count,
                "operator_count": stats.operator_count,
                "bug_fix_count": stats.bug_fix_count,
                "optimization_count": stats.optimization_count,
                "storage_size_mb": stats.storage_size_mb,
                "last_sync_time": (
                    stats.last_sync_time.isoformat()
                    if stats.last_sync_time
                    else None
                ),
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
