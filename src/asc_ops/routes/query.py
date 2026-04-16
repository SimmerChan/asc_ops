# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
查询 API 路由
"""

import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..knowledge_query import (
    KnowledgeQueryService,
    DevelopmentQueryResult,
    TroubleshootingResult,
    PossibleCause,
)
from ..models import AscendCAPIDefinition
from ..storage.redis_client import RedisClient

router = APIRouter()

# 请求模型
class DevelopmentQueryRequest(BaseModel):
    """开发查询请求"""
    operator_name: str = Field(..., description="算子名称")
    query_type: str = Field(default="all", description="查询类型: bug | optimization | all")
    api_filter: Optional[List[str]] = Field(default=None, description="API过滤列表")
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="最低置信度")
    limit: int = Field(default=10, ge=1, le=100, description="返回数量")


class TroubleshootingQueryRequest(BaseModel):
    """问题排查查询请求"""
    symptom: str = Field(..., description="问题症状描述")
    operator_name: Optional[str] = Field(default=None, description="算子名称")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    used_apis: Optional[List[str]] = Field(default=None, description="使用的API列表")
    include_related: bool = Field(default=False, description="是否包含关联知识")
    include_api_details: bool = Field(default=False, description="是否包含API详情")
    limit: int = Field(default=5, ge=1, le=50, description="返回数量")


class APIQueryRequest(BaseModel):
    """API查询请求"""
    api_name: Optional[str] = Field(default=None, description="API名称（精确匹配）")
    semantic_query: Optional[str] = Field(default=None, description="语义搜索查询")
    category: Optional[str] = Field(default=None, description="API类别")
    subcategory: Optional[str] = Field(default=None, description="API子类别")
    include_examples: bool = Field(default=False, description="是否包含使用示例")
    limit: int = Field(default=10, ge=1, le=100, description="返回数量")


# 响应模型
class APIResponse(BaseModel):
    """统一API响应"""
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    meta: Optional[dict] = None


# 共享的查询服务实例
_query_service: Optional[KnowledgeQueryService] = None


def get_query_service() -> KnowledgeQueryService:
    """获取查询服务实例"""
    global _query_service
    if _query_service is None:
        redis_client = RedisClient(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", "6379")),
            db=int(os.environ.get("REDIS_DB", "0")),
            password=os.environ.get("REDIS_PASSWORD"),
            mock=False,
        )
        _query_service = KnowledgeQueryService(
            redis_client=redis_client,
            chroma_db_path=os.environ.get("CHROMA_DB_PATH", "./data/chroma_db"),
        )
    return _query_service


@router.post("/development", response_model=APIResponse)
async def query_for_development(request: DevelopmentQueryRequest):
    """
    主动开发查询

    在开发前查询算子的 Bug 注意事项和优化经验
    """
    try:
        service = get_query_service()
        result = await service.query_for_development(
            operator_name=request.operator_name,
            query_type=request.query_type,
            api_filter=request.api_filter,
            min_confidence=request.min_confidence,
            limit=request.limit,
        )

        # 转换为字典
        bug_fixes = []
        for bug in result.bug_fixes:
            bug_fixes.append({
                "bug_id": bug.bug_id,
                "operator_id": bug.operator_id,
                "bug_title": bug.bug_title,
                "symptom": bug.symptom,
                "severity": bug.severity.value,
                "category": bug.category.value,
                "root_cause": bug.root_cause,
                "trigger_conditions": bug.trigger_conditions,
                "fix_pattern": bug.fix_pattern,
                "workarounds": bug.workarounds,
                "related_apis": bug.related_apis,
                "confidence": bug.confidence,
            })

        optimizations = []
        for opt in result.optimizations:
            optimizations.append({
                "opt_id": opt.opt_id,
                "operator_id": opt.operator_id,
                "opt_title": opt.opt_title,
                "optimization_type": opt.optimization_type,
                "optimization_description": opt.optimization_description,
                "improvement_ratio": opt.improvement_ratio,
                "related_apis": opt.related_apis,
                "confidence": opt.confidence,
            })

        return APIResponse(
            success=True,
            data={
                "operator_name": result.operator_name,
                "query_type": result.query_type,
                "total_count": result.total_count,
                "bug_fixes": bug_fixes,
                "optimizations": optimizations,
            },
            meta={"count": result.total_count},
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/troubleshooting", response_model=APIResponse)
async def query_for_troubleshooting(request: TroubleshootingQueryRequest):
    """
    被动问题排查查询

    根据症状查询可能的原因和建议
    """
    try:
        service = get_query_service()
        result = await service.query_for_troubleshooting(
            symptom=request.symptom,
            operator_name=request.operator_name,
            error_message=request.error_message,
            used_apis=request.used_apis,
            include_related=request.include_related,
            include_api_details=request.include_api_details,
            limit=request.limit,
        )

        # 转换 PossibleCause
        possible_causes = []
        for cause in result.possible_causes:
            possible_causes.append({
                "bug_id": cause.bug_id,
                "description": cause.description,
                "confidence": cause.confidence,
                "root_cause": cause.root_cause,
                "trigger_conditions": cause.trigger_conditions,
                "suggested_fix": cause.suggested_fix,
                "suggested_checks": cause.suggested_checks,
            })

        # 转换关联 API
        related_apis = []
        for api in result.related_apis:
            related_apis.append({
                "api_id": api.api_id,
                "canonical_name": api.canonical_name,
                "category": api.category,
                "description": api.description,
            })

        return APIResponse(
            success=True,
            data={
                "symptom": result.symptom,
                "possible_causes": possible_causes,
                "related_apis": related_apis,
            },
            meta={"cause_count": len(possible_causes)},
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api", response_model=APIResponse)
async def query_api(
    api_name: Optional[str] = None,
    semantic_query: Optional[str] = None,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    include_examples: bool = False,
    limit: int = 10,
):
    """
    API查询

    精确匹配或语义搜索 API 定义
    """
    try:
        if not api_name and not semantic_query:
            raise HTTPException(
                status_code=400,
                detail="api_name or semantic_query must be provided",
            )

        service = get_query_service()
        result = await service.query_api(
            api_name=api_name,
            semantic_query=semantic_query,
            category=category,
            subcategory=subcategory,
            include_examples=include_examples,
            limit=limit,
        )

        # 转换 API 定义
        apis = []
        for api in result:
            api_dict = {
                "api_id": api.api_id,
                "canonical_name": api.canonical_name,
                "full_signature": api.full_signature,
                "category": api.category,
                "subcategory": api.subcategory,
                "description": api.description,
                "confidence": api.confidence,
            }

            if include_examples and api.usage_examples:
                api_dict["usage_examples"] = [
                    {"scenario": ex.scenario, "code": ex.code}
                    for ex in api.usage_examples
                ]

            apis.append(api_dict)

        return APIResponse(
            success=True,
            data={"apis": apis},
            meta={"count": len(apis)},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
