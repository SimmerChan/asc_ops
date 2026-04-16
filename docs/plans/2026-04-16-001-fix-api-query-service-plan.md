---
title: API 查询服务可用性修复
type: fix
status: active
date: 2026-04-16
---

# API 查询服务可用性修复

## Overview

修复 API 查询服务，使其能正确读取持久化的 848 个 API 数据。

## Problem Frame

`KnowledgeQueryService` 使用临时 `ChromaDBClient()` 初始化，无法访问 `./data/chroma_db` 中存储的 848 个 API。`query_api` 总是返回空结果。

## Root Cause

`KnowledgeQueryService.__init__` 中:
```python
self._chroma = chroma_client or ChromaDBClient()  # 无 persist_directory
```

而 API 数据存储在 `./data/chroma_db`:
```python
chroma = ChromaDBClient(persist_directory='./data/chroma_db')  # 有持久化
```

## Key Technical Decisions

- **方案**: 修改 `KnowledgeQueryService` 支持通过 `chroma_db_path` 参数传入持久化目录
- **配置来源**: `config.py` 中的 `ChromaDBConfig.db_path`
- **优先级**: 显式参数 > 配置 > 临时客户端

## Implementation Units

- [x] **Unit 1: 修改 KnowledgeQueryService 支持持久化路径** ✅

**Goal:** 让 KnowledgeQueryService 能读取 `./data/chroma_db` 中的数据

**Requirements:** R1

**Dependencies:** None

**Files:**
- Modify: `src/asc_ops/knowledge_query.py`

**Approach:**
1. 在 `__init__` 中添加 `chroma_db_path: Optional[str] = None` 参数
2. 当 `chroma_client` 为 None 时:
   - 优先使用传入的 `chroma_db_path`
   - 若无，则调用 `get_config().chroma.db_path`
   - 使用该路径创建 `ChromaDBClient(persist_directory=path)`

**Execution note:** 简单参数添加，无额外风险

**Verification:**
```bash
cd /Users/huangshilei/Documents/pythonprojects/asc_ops
PYTHONPATH=. python -c "
import asyncio
from asc_ops.knowledge_query import KnowledgeQueryService

async def test():
    service = KnowledgeQueryService()
    result = await service.query_api(semantic_query='LocalTensor creation', limit=3)
    print(f'Results: {len(result)} APIs')
    for api in result[:2]:
        print(f'  - {api.canonical_name}')

asyncio.run(test())
"
# 应输出非空结果
```

---

- [x] **Unit 2: 验证 API 语义搜索质量** ✅

**Goal:** 确认语义搜索返回有意义的结果

**Requirements:** R1

**Dependencies:** Unit 1

**Files:** None (验证为主)

**Test scenarios:**
- `semantic_query='LocalTensor creation'` 返回相关 API
- `semantic_query='DataCopy synchronization'` 返回相关 API
- `api_name='LocalTensor'` 精确匹配正常工作

**Verification:**
- 查询结果的相关性 (结果 > 0)
- 响应延迟 < 500ms

---

- [ ] **Unit 3: API 查询结果置信度排序** (Deferred - 可选增强)

**Goal:** API 查询结果使用 ConfidenceRanker 排序

**Requirements:** R2

**Dependencies:** Unit 1, Unit 2

**Files:**
- Modify: `src/asc_ops/knowledge_query.py`

**Approach:**

关键问题: `_apply_confidence_ranking` 期望的元数据结构与 `AscendCAPIDefinition` 不匹配。需要创建专用的 `_rank_api_results` 方法。

```python
async def _rank_api_results(
    self,
    apis: List[AscendCAPIDefinition],
    top_k: int = 10,
) -> List[AscendCAPIDefinition]:
    """
    对 API 查询结果应用置信度排序

    API 的元数据来自 ChromaDB metadata，包含:
    - source_type: 官方/社区
    - confidence: 解析置信度
    - last_updated: 更新时间
    """
    if not apis:
        return apis

    # 转换为 ranker 需要的格式
    api_dicts = []
    for api in apis:
        metadata = {
            "source_type": api.source.source_type if api.source else "official",
            "updated_at": api.last_updated.isoformat() if api.last_updated else None,
            "confidence": api.confidence,
            "category": api.category,
        }
        api_dicts.append({
            "id": api.api_id,
            "score": api.confidence,
            "metadata": metadata,
        })

    # 排序
    ranked = await self._confidence_ranker.rank_results(api_dicts, top_k=top_k)

    # 映射回原始对象
    id_to_api = {api.api_id: api for api in apis}
    sorted_apis = []
    for ranked_item in ranked:
        if ranked_item.id in id_to_api:
            api = id_to_api[ranked_item.id]
            api.confidence = ranked_item.score.total
            sorted_apis.append(api)

    return sorted_apis
```

**Note:** API 的 `source_type` 来自 `api.source.source_type`，若无则为 "official"。API 没有 `source_repo`/`source_pr`/`citation_count` 等字段，所以置信度排序主要依赖 `source_type` 和 `confidence`。

**Verification:**
- 高置信度 (source=official, confidence=1.0) API 排在前面
- 返回顺序与原始相似度分数不完全一致 (说明排序生效)

---

## Open Questions

### Resolved During Planning

1. **PYTHONPATH 问题**: 实际验证命令使用 `PYTHONPATH=.` + `from asc_ops.knowledge_query import`
2. **置信度排序元数据**: API 缺少 `source_repo` 等字段，但有 `source.source_type` 和 `confidence`，足够用于基础排序

### Deferred to Implementation

3. **API 精确匹配的性能**: 精确匹配可能每次都扫描全表，是否需要优化？

---

## System-Wide Impact

- **KnowledgeQueryService**: 新增 `chroma_db_path` 参数
- **API 查询**: 结果顺序可能因置信度排序而改变
- **配置**: 从 `config.chroma.db_path` 读取默认路径
