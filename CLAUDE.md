# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

**asc_ops** (AscendC Operator Knowledge Base) 是一个面向 Coding Agent 的昇腾 AscendC 算子知识检索系统，提供 GPU→NPU 跨平台映射、Bug 修复经验查询和 API 知识检索能力。

## 常用命令

### 运行服务
```bash
# MCP Server (stdio协议，用于 Coding Agent 集成)
python -m src.asc_ops.mcp.cli

# FastAPI 服务器 (REST API)
python -m src.asc_ops.server
```

### 测试
```bash
# 运行所有测试 (716个)
python -m pytest

# 运行特定测试
python -m pytest tests/unit/test_knowledge_query.py -v
python -m pytest tests/integration/ -v

# 查看测试覆盖率
python -m pytest --cov=src.asc_ops --cov-report=html
```

### 代码质量
```bash
# 格式化
black src/

# 检查
ruff check src/
```

## 架构概览

```
┌─────────────────────────────────────────────┐
│         Coding Agent (MCP Client)           │
└─────────────────┬───────────────────────────┘
                  │ stdio
                  ▼
┌─────────────────────────────────────────────┐
│  MCP Server (src/asc_ops/mcp/)             │
│  ├── cli.py        # 入口点                 │
│  ├── server.py     # MCP 协议实现           │
│  └── tools.py      # 工具定义               │
└─────────────────┬───────────────────────────┘
                  │
    ┌─────────────┴─────────────┐
    ▼                           ▼
┌──────────────┐         ┌──────────────┐
│ ChromaDB     │         │ Redis        │
│ (向量存储)    │         │ (KV存储)     │
│              │         │              │
│ • API 向量   │         │ • 元数据     │
│ • Bug 向量   │         │ • 置信度    │
│ • 映射向量   │         │ • 引用计数   │
└──────────────┘         └──────────────┘
```

## 核心模块

| 模块 | 路径 | 说明 |
|------|------|------|
| **知识查询** | `knowledge_query.py` | 统一查询服务入口 |
| **存储层** | `storage/` | ChromaDB + Redis 封装 |
| **MCP接口** | `mcp/` | Agent 集成协议 |
| **映射引擎** | `mapper/engine.py` | GPU→NPU 跨平台映射 |
| **置信度排序** | `ranker/` | Authority × Recency × Accuracy |
| **知识抽取** | `extractor/` | Bug/优化知识提取 |
| **数据采集** | `collector/` | 官方文档和 Git 仓库采集 |

## 存储设计

### ChromaDB Collections
- `ascend_apis`: 1120 个官方 API (100% nav_path 覆盖)
- `bug_fixes`: 1203+ Bug 修复经验
- `optimizations`: 13+ 优化方案
- `cross_platform_mappings`: 57+ GPU→NPU 映射

### Redis Keys
- 引用计数追踪 (`cite:{type}:{id}`)
- 置信度评分缓存
- 知识统计

## Embedder 系统 (关键)

**统一使用 `get_embedder()` 单例**，位于 `collector/embedder.py`。

```python
from collector.embedder import get_embedder
embedder = get_embedder()
```

**ChromaDB Collection 创建时必须禁用默认 embedding**：
```python
collection = client.get_or_create_collection(
    name=name,
    metadata={"hnsw:space": "cosine"},
    embedding_function=None  # 关键：禁用 ChromaDB 默认 embedding
)
```

支持的 embedder 类型 (`EMBEDDING_EMBEDDER_TYPE`):
- `qwen`: Qwen3-Embedding-0.6B (Apple Silicon MPS)
- `sentence_transformers`: HuggingFace 模型
- `mock`: 仅精确查询，无语义搜索

## 关键数据流

### 查询流程 (KnowledgeQueryService)
1. 接收查询请求
2. 从 ChromaDB 精确/向量查询
3. 应用置信度排序 (Ranker)
4. 记录引用计数 (Redis)
5. 返回排序结果

### GPU→NPU 映射流程 (MapperEngine)
1. 接收 GPU API 名称
2. 查询 ChromaDB cross_platform_mappings
3. 使用 LLM 分析语义相似度
4. 返回最佳映射建议

## 配置

环境变量配置 (详见 `.env.example`):
- `CHROMA_DB_PATH`: ChromaDB 路径
- `REDIS_HOST/PORT`: Redis 连接
- `ANTHROPIC_API_KEY`: LLM 调用
- `EMBEDDING_EMBEDDER_TYPE`: 向量化模型类型

## 测试结构

```
tests/
├── unit/          # 单元测试 (collector, extractor, ranker, quality 等)
├── integration/   # 集成测试 (查询管道、排序管道)
└── e2e/          # 端到端测试 (MCP 集成、采集流程)
```

## 注意事项

1. **ChromaDB embedding_function=None**: 必须显式设置以避免使用默认 all-MiniLM-L6-v2 模型导致向量维度不匹配 (384 vs 1024)

2. **Redis mock**: 开发环境可用 `USE_MOCK_STORAGE=true` 绕过 Redis 依赖

3. **知识存储**: `extractor/knowledge_storage.py` 管理所有 ChromaDB 和 Redis 操作，是数据写入的统一入口