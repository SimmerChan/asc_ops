# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
FastAPI应用入口
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AscendC Operator Knowledge Base",
    description="为Coding Agent提供昇腾AscendC算子知识检索支持",
    version="0.1.0",
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "name": "AscendC Operator Knowledge Base",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "0.1.0"}


# 路由（待实现）
# from .routes import query, management
# app.include_router(query.router, prefix="/api/v1/query", tags=["query"])
# app.include_router(management.router, prefix="/api/v1", tags=["management"])
