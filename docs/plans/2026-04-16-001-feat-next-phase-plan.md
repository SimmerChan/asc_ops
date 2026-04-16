---
title: 下一步开发计划 - 项目可用性评估
type: feat
status: active
date: 2026-04-16
---

# 下一步开发计划 - 项目可用性评估

## Overview

评估 AscendC 算子知识库距离真正可用的差距，规划下一步开发重点。

## Problem Frame

当前状态：Phase 1-3 和 API 采集已完成，但 MVP 尚未真正可用。存在多个缺失环节。

## 已完成组件分析

| 组件 | 计划 | 状态 | 说明 |
|------|------|------|------|
| 双存储架构 | Phase 1 | ✅ 完成 | ChromaDB + Redis |
| 原子化算子知识图谱 | Phase 2a | ✅ 完成 | Bug/优化知识已抽取 |
| 增量同步管道 | Phase 2b | ⚠️ 部分 | Webhook 接收服务存在，但未验证 |
| 置信度感知排序层 | Phase 3 | ✅ 完成 | AuthorityScorer/RecencyCalculator/AccuracyCalculator |
| API 采集 | A2 | ✅ 完成 | 834 个 API 已入库 |
| LLM 冷启动抽取 | - | ✅ 完成 | Bug 知识 root_cause/fix_pattern 补全 |
| 修正报告查询 | R2 | ❌ 未开始 | 待实现 |
| 告警机制 | R1 | ❌ 未开始 | 待确认渠道 |
| Redis 键前缀统一 | R3 | ❌ 未开始 | 待统一 |

## 当前 Gap 分析

### 1. API 查询服务未集成 (严重)

**问题**：`APIStorage` 已存储 848 个 API，但：
- `knowledge_query.py` 中没有 API 查询入口
- 没有 `query_api` 类似 `query_for_development` 的服务
- MCP 工具没有暴露 API 查询能力

**需要实现**：
- `APISearchService` - API 语义检索服务
- API 排序（复用 ConfidenceRanker）
- API 查询 API 端点

### 2. Bug/优化知识质量不达标 (中等)

**问题**：
- Phase 2a 冷启动导入的 Bug 知识缺失 `root_cause` 和 `fix_pattern`
- LLM 冷启动管道已完成，但未执行
- Phase 5 的 Bug/优化知识抽取未完成

**需要实现**：
- 执行 LLM 冷启动管道补全数据
- 验证 Bug 知识填充率

### 3. 排序层未集成到查询服务 (中等)

**问题**：`ConfidenceRanker` 已实现但：
- 未集成到 `KnowledgeQueryService`
- 查询结果未使用置信度排序

**需要实现**：
- 将 `ConfidenceRanker` 集成到 `KnowledgeQueryService`
- 配置排序权重

### 4. 修正报告 API 缺失 (低)

**问题**：计划 R2 未实现

**需要实现**：
- `/api/v1/quality/correction/reports` 端点

### 5. 告警机制缺失 (低)

**问题**：仅日志记录，无告警

**需要实现**：
- 飞书/钉钉 Webhook 集成（待用户确认）

## Priority Matrix

| 优先级 | 组件 | 工作量 | 价值 | 依赖 |
|--------|------|--------|------|------|
| P0 | API 查询服务 | 高 | 高 | 无 |
| P1 | 排序层集成 | 中 | 高 | 无 |
| P1 | LLM 冷启动执行 | 中 | 中 | API 查询 |
| P2 | 修正报告 API | 低 | 低 | 无 |
| P3 | 告警机制 | 低 | 中 | 用户确认 |

## Scope Boundaries

**在范围内:**
- API 语义检索服务和 API 端点
- ConfidenceRanker 集成到 KnowledgeQueryService
- 执行 LLM 冷启动管道补全 Bug 知识
- 修正报告查询 API

**不在范围内:**
- Web UI 管理界面
- 增量同步调度器完整实现
- 自动化修正流程
- 告警机制（待用户确认渠道）

## Implementation Units

- [ ] **Unit 1: API 查询服务 (APISearchService)**

**Goal:** 实现 API 语义检索能力，支持自然语言查询 CANN API

**Requirements:**
- R1: 自然语言查询 API（如 "如何创建 LocalTensor"）
- R2: 支持按分类过滤
- R3: 返回排序结果（相似度 + 置信度）

**Files:**
- Create: `src/asc_ops/ranker/api_ranker.py`
- Modify: `src/asc_ops/knowledge_query.py`
- Modify: `src/asc_ops/routes/query.py`
- Test: `tests/unit/ranker/test_api_ranker.py`

**Approach:**
- 复用 `QwenEmbedder` 和 `ChromaDBClient`
- 使用 API collection (`ascend_apis`) 检索
- 集成 `ConfidenceRanker` 排序
- 返回结构化 API 信息

**Test scenarios:**
- 查询 "LocalTensor 创建" 返回相关 API
- 查询 "DataCopy 同步" 返回相关 API
- 分类过滤正常工作

**Verification:**
- API 端点返回排序结果
- 向量检索延迟 < 200ms

---

- [ ] **Unit 2: 排序层集成到 KnowledgeQueryService**

**Goal:** 将 ConfidenceRanker 集成到主查询服务

**Requirements:**
- R1: `query_for_development` 使用置信度排序
- R2: 配置可调的排序权重

**Files:**
- Modify: `src/asc_ops/knowledge_query.py`

**Approach:**
- 在 `KnowledgeQueryService.__init__` 中初始化 `ConfidenceRanker`
- `query_for_development` 结果经过 `ConfidenceRanker.rank_results` 重排
- 支持通过配置调整权重

**Verification:**
- 相同查询多次返回结果顺序稳定
- 权威来源的结果排在前

---

- [ ] **Unit 3: LLM 冷启动管道执行**

**Goal:** 执行批量 LLM 抽取，补全 Bug 知识 `root_cause` 和 `fix_pattern`

**Files:**
- `src/asc_ops/extractor/batch_extractor.py` (已创建)
- `src/asc_ops/extractor/priority_scorer.py` (已创建)
- `scripts/llm_retry_batch.py` (已创建)

**Approach:**
- 执行 `python scripts/llm_retry_batch.py --limit 100 --report-only` 先生成质量报告
- 执行 `python scripts/llm_retry_batch.py --limit 100` 执行批量抽取
- 验证填充率提升

**Verification:**
- Top 100 bug 的 root_cause 填充率 > 70%
- Top 100 bug 的 fix_pattern 填充率 > 50%

---

- [ ] **Unit 4: 修正报告查询 API**

**Goal:** 实现 `/api/v1/quality/correction/reports` 端点

**Requirements:**
- R4.1: 按时间范围查询
- R4.2: 按实体类型过滤
- R4.3: 按修正类型过滤
- R4.4: 分页支持

**Files:**
- Modify: `src/asc_ops/routes/feedback.py`

**Approach:**
- 使用 Redis sorted set 存储 `correction:{entity_type}:{entity_id}`
- 实现 `GET /api/v1/quality/correction/reports` 端点
- 参数: `entity_type`, `correction_type`, `start_date`, `end_date`, `page`, `page_size`

**Verification:**
- `GET /api/v1/quality/correction/reports?entity_type=bug` 返回 bug 纠错列表

---

## System-Wide Impact

- **API**: 新增 API 查询端点
- **排序**: KnowledgeQueryService 结果顺序改变
- **存储**: LLM 抽取更新 Bug 知识记录

## Risks & Dependencies

| 风险 | 影响 | 缓解 |
|------|------|------|
| API 查询性能不达标 | 高 | 优化 ChromaDB 查询，添加索引 |
| LLM 抽取失败 | 中 | 使用已有 fallback 逻辑 |
| 排序权重调参困难 | 中 | 提供配置接口 |

## Next Steps

1. **立即执行**: Unit 1 (API 查询服务) - 最优先
2. **短期**: Unit 2 (排序层集成) + Unit 3 (LLM 冷启动)
3. **中期**: Unit 4 (修正报告 API)
4. **待确认**: 告警机制 (R1)

## Open Questions

### 需要用户决策
1. **API 查询优先级**: API 查询应该优先于 Bug/优化知识查询吗？
2. **排序权重**: 默认权重 Authority=0.5, Recency=0.3, Accuracy=0.2 是否合适？
3. **告警渠道**: 飞书还是钉钉？

### Deferred to Implementation
4. **LLM 批次大小**: 每次抽取多少条记录合适？（建议 100 条/批）
5. **API 缓存策略**: 是否需要缓存高频查询结果？
