---
title: 修复优化知识查询 - 键名不匹配 + 算子名称缺失
type: fix
status: completed
date: 2026-04-16
---

# 修复优化知识查询

## Problem Frame

优化知识查询返回空结果，原因有两层：

**层1 - 查询键名不匹配（阻塞性）**：
- `KnowledgeQueryService._query_optimizations_by_operator()` 查询 `operator:{name}:opts`
- `KnowledgeStorage._store_optimization_redis()` 存储到 `operator:{name}:opts:{opt_type}`
- 键名模式不一致，导致 SMEMBERS 永远返回空集

**层2 - 算子名称提取失败（数据质量）**：
- 冷启动导入时，优化抽取器 `_extract_operator()` 对中文 PR 标题提取失败
- 11 条优化记录 `operator_id` 全部为 "unknown"
- `bug_extractor.py` 的 `_extract_operator()` 能正确提取英文算子名，但 `opt_extractor.py` 的实现相同却失败

## Requirements Trace

- R1: 修复优化查询返回空结果
- R2: 修复后优化知识可按算子名称正确筛选

## Scope Boundaries

**在范围内：**
- 修复 `_query_optimizations_by_operator()` 键名查询模式
- 修复 `opt_extractor.py` 算子名称提取逻辑
- 重新导入优化知识建立正确索引

**不在范围内：**
- 修复历史已存储的 bug 数据（bug 数据正常）
- 增量同步管道验证（独立问题）

## Key Technical Decisions

- **Decision**: 使用 `scan_iter` 模式匹配而非硬编码键名
  - **Rationale**: 存储层使用 `operator:{name}:opts:{type}` 多级索引，查询层需要兼容
  - **Alternatives considered**: 改存储层为扁平结构，但需要迁移已有数据

## Implementation Units

- [ ] **Unit 1: 修复优化查询键名模式**

**Goal:** 让 `_query_optimizations_by_operator()` 能正确查询到存储的优化数据

**Files:**
- Modify: `src/asc_ops/knowledge_query.py`

**Approach:**
1. 将 `opt_ids_key = f"operator:{operator_name}:opts"` 改为使用 `scan_iter` 扫描 `operator:{operator_name}:opts:*`
2. 收集所有匹配的 key 的 members
3. 查询仍然使用 `optimization:{opt_id}` 获取详情

**Patterns to follow:**
- 参考 `knowledge_storage.py` 第 468-475 行 `count_optimizations_by_operator` 使用 `scan_iter` 的模式

**Verification:**
```python
# 直接验证
PYTHONPATH=. python -c "
from src.asc_ops.storage.redis_client import RedisClient
rc = RedisClient(host='localhost', port=6379, db=0, mock=False)
# 验证 scan_iter 能找到现有索引
keys = list(rc._client.scan_iter('operator:*:opts:*'))
print(f'Found {len(keys)} optimization index keys')
"
```

---

- [ ] **Unit 2: 修复优化抽取器算子名称提取**

**Goal:** 让 `_extract_operator()` 能从中文 PR 标题中提取算子名称

**Files:**
- Modify: `src/asc_ops/extractor/opt_extractor.py`

**Approach:**
1. 对比 `bug_extractor.py` 和 `opt_extractor.py` 的 `_extract_operator()` 实现
2. 发现 `opt_extractor.py` 第 371-385 行 `_extract_operator()` 与 bug 版相同
3. 问题可能是 PR 标题格式差异导致正则匹配失败
4. 添加中文算子名提取支持（常见算子名称列表匹配）

**Patterns to follow:**
- `bug_extractor.py` 第 443-465 行 `_extract_operator()` 已有正确的英文提取逻辑
- 添加中文关键词匹配作为 fallback

**Test scenarios:**
- "【社区任务】Real算子AscendC实现" → 提取 "Real"
- "memory优化：Matmul性能提升" → 提取 "Matmul"
- "VecReduce向量化优化" → 提取 "VecReduce"

**Verification:**
```python
PYTHONPATH=. python -c "
from src.asc_ops.extractor.opt_extractor import OptimizationExtractor
ext = OptimizationExtractor()

tests = [
    '【社区任务】Real算子AscendC实现',
    'memory优化：Matmul性能提升',
    'VecReduce向量化优化',
]
for t in tests:
    op = ext._extract_operator(t)
    print(f'{t[:30]}... → {op}')
"
```

---

- [ ] **Unit 3: 重新导入优化知识**

**Goal:** 使用修复后的抽取器重新导入优化知识，建立正确的算子索引

**Files:**
- Run: `python scripts/cold_start/import_bug_opt_knowledge.py --repo ops-math --limit 50`

**Approach:**
1. 先用 `--dry-run` 验证抽取逻辑
2. 全量重新导入（覆盖已有数据）
3. 验证 `operator:Real:opts:*` 等正确索引被创建

**Verification:**
```python
PYTHONPATH=. python -c "
from src.asc_ops.storage.redis_client import RedisClient
rc = RedisClient(host='localhost', port=6379, db=0, mock=False)
keys = list(rc._client.scan_iter('operator:*:opts:*'))
print(f'Optimization index keys: {len(keys)}')
# 应该看到 operator:Real:opts:memory 等正确索引
"
```

---

- [ ] **Unit 4: 验证优化查询功能**

**Goal:** 端到端验证优化查询返回正确结果

**Files:**
- Test: `tests/api/test_query_routes.py`

**Approach:**
添加优化查询测试用例，或运行现有测试验证

**Test scenarios:**
- `query_for_development('Real', query_type='optimization')` 返回 >0 结果
- 返回的 optimization 有正确的 `operator_id`（非 "unknown"）

## Dependencies

```
Unit 1 (查询修复) → Unit 4 (验证)
Unit 2 (抽取器修复) → Unit 3 (重新导入) → Unit 4 (验证)
```

## Risks & Mitigation

| 风险 | 影响 | 缓解 |
|------|------|------|
| 重新导入覆盖已有数据 | 低 - 抽取器修复后重新抽取质量更高 | 先 dry-run 验证 |
| 中文算子名提取仍失败 | 中 - 需要人工确认提取规则 | 添加已知算子名列表 fallback |

## Open Questions

### Deferred to Implementation
- 是否需要迁移已有的 11 条优化数据（直接删除重建 vs 批量更新 operator_id）？
