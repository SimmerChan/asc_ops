# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
反馈 API 路由

提供知识纠错反馈和质量反馈接口
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..quality.feedback import FeedbackAPI, CorrectionType, CorrectionStats
from ..quality.citation_tracker import CitationTracker, CitationStats

router = APIRouter()

# 请求模型
class CorrectionReportRequest(BaseModel):
    """纠错报告请求"""
    entity_id: str = Field(..., description="实体 ID (bug_id 或 opt_id)")
    entity_type: str = Field(..., description="实体类型: bug | optimization | api")
    correction_type: str = Field(..., description="纠错类型: wrong | incomplete | outdated | misleading")
    user_id: Optional[str] = Field(default=None, description="用户 ID")
    description: Optional[str] = Field(default=None, description="纠错描述")
    suggested_fix: Optional[str] = Field(default=None, description="建议修复")


class CitationQueryRequest(BaseModel):
    """引用查询请求"""
    entity_id: str = Field(..., description="实体 ID")
    entity_type: str = Field(..., description="实体类型: bug | optimization | api")


# 响应模型
class CorrectionResponse(BaseModel):
    """纠错响应"""
    success: bool
    entity_id: str
    entity_type: str
    correction_type: str
    correction_count: int
    total_corrections: int
    threshold_exceeded: bool
    alert_triggered: bool


class CitationResponse(BaseModel):
    """引用统计响应"""
    entity_id: str
    entity_type: str
    citation_count: int
    correction_count: int
    error_rate: float
    accuracy: float
    last_cited_at: Optional[str]
    last_corrected_at: Optional[str]


class TopCitedResponse(BaseModel):
    """高引用条目响应"""
    entity_id: str
    citation_count: int


class TopInaccurateResponse(BaseModel):
    """高错误率条目响应"""
    entity_id: str
    error_rate: float
    citation_count: int
    correction_count: int


# 共享服务实例
_feedback_api: Optional[FeedbackAPI] = None
_citation_tracker: Optional[CitationTracker] = None


def get_feedback_api() -> FeedbackAPI:
    """获取反馈服务实例"""
    global _feedback_api
    if _feedback_api is None:
        _feedback_api = FeedbackAPI()
    return _feedback_api


def get_citation_tracker() -> CitationTracker:
    """获取引用追踪器实例"""
    global _citation_tracker
    if _citation_tracker is None:
        _citation_tracker = CitationTracker()
    return _citation_tracker


@router.post("/correction", response_model=CorrectionResponse)
async def report_correction(request: CorrectionReportRequest):
    """
    上报知识纠错反馈

    用户发现知识错误时提交纠错报告，系统会：
    1. 记录纠错次数
    2. 更新引用追踪器的纠错统计
    3. 如果纠错次数超过阈值，触发告警
    """
    try:
        api = get_feedback_api()
        result = await api.report_correction(
            entity_id=request.entity_id,
            entity_type=request.entity_type,
            correction_type=request.correction_type,
            user_id=request.user_id,
            description=request.description,
            suggested_fix=request.suggested_fix,
        )

        return CorrectionResponse(
            success=result["success"],
            entity_id=result["entity_id"],
            entity_type=result["entity_type"],
            correction_type=result["correction_type"],
            correction_count=result["correction_count"],
            total_corrections=result["total_corrections"],
            threshold_exceeded=result["threshold_exceeded"],
            alert_triggered=result["alert_triggered"],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/correction/stats/{entity_type}/{entity_id}")
async def get_correction_stats(entity_type: str, entity_id: str):
    """
    获取实体的纠错统计

    Returns纠错总数、按类型分布、最近报告时间
    """
    try:
        api = get_feedback_api()
        stats = api.get_correction_stats(entity_id, entity_type)

        return {
            "success": True,
            "data": {
                "entity_id": stats.entity_id,
                "entity_type": stats.entity_type,
                "total_corrections": stats.total_corrections,
                "by_type": stats.by_type,
                "last_reported_at": stats.last_reported_at.isoformat() if stats.last_reported_at else None,
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/citation/stats/{entity_type}/{entity_id}")
async def get_citation_stats(entity_type: str, entity_id: str):
    """
    获取实体的引用统计

    Returns引用次数、纠错次数、错误率、准确性
    """
    try:
        tracker = get_citation_tracker()
        stats = tracker.get_stats(entity_id, entity_type)

        return {
            "success": True,
            "data": {
                "entity_id": stats.entity_id,
                "entity_type": stats.entity_type,
                "citation_count": stats.citation_count,
                "correction_count": stats.correction_count,
                "error_rate": stats.error_rate,
                "accuracy": stats.accuracy,
                "last_cited_at": stats.last_cited_at.isoformat() if stats.last_cited_at else None,
                "last_corrected_at": stats.last_corrected_at.isoformat() if stats.last_corrected_at else None,
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/citation/top/{entity_type}")
async def get_top_cited(entity_type: str, limit: int = 10):
    """
    获取引用次数最多的知识条目

    用于分析热门知识和高价值知识
    """
    try:
        tracker = get_citation_tracker()
        results = tracker.get_top_cited(entity_type, limit=limit)

        return {
            "success": True,
            "data": {
                "entity_type": entity_type,
                "top_cited": results,
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/citation/accuracy/{entity_type}")
async def get_top_inaccurate(entity_type: str, min_citations: int = 5, limit: int = 10):
    """
    获取错误率最高的知识条目

    用于发现需要优先审核的知识
    """
    try:
        tracker = get_citation_tracker()
        results = tracker.get_top_inaccurate(entity_type, min_citations=min_citations, limit=limit)

        return {
            "success": True,
            "data": {
                "entity_type": entity_type,
                "min_citations": min_citations,
                "top_inaccurate": results,
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity/types")
async def get_entity_types():
    """
    获取所有有统计数据的实体类型
    """
    try:
        tracker = get_citation_tracker()
        types = tracker.get_entity_types()

        return {
            "success": True,
            "data": {
                "entity_types": types,
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
