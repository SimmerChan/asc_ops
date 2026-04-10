# AscendC算子知识库 - 完整设计计划

**文档版本**: v1.0
**创建日期**: 2026-04-10
**状态**: 整合完成

---

## 1. 问题框架

### 1.1 项目背景

**目标**: 构建面向Coding Agent的昇腾AscendC算子知识检索系统，帮助Agent在昇腾NPU上开发算子、排查bug、进行GPU→NPU跨平台适配。

**核心用户**: Coding Agent (Claude Code, CoPilot, Cursor, 通义灵码等)

### 1.2 当前进展

- ✅ 架构设计完成（双存储、置信度排序、三层知识图谱）
- ✅ API知识库设计完成（1786 API）
- ✅ GPU→NPU跨平台设计完成
- ✅ Bug/优化知识设计完成
- ✅ PR采样分析完成（6仓429 commits）
- ✅ 用户文档初步补充（README、快速入门、API参考）
- ❌ 核心代码未实现

---

## 2. 系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Coding Agent                                  │
│  (Claude Code / CoPilot / Cursor / 通义灵码)                      │
└─────────────────────────┬───────────────────────────────────────┘
                          │ MCP协议 / REST API
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    知识查询服务 (asc_ops)                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────────────┐      ┌───────────────────┐               │
│  │   ChromaDB        │      │   Redis           │               │
│  │   (向量存储)       │      │   (KV存储)        │               │
│  │                   │      │                   │               │
│  │  • API语义向量     │      │  • 算子属性       │               │
│  │  • 算子知识向量    │      │  • PR元数据       │               │
│  │  • Bug知识向量     │      │  • 质量评分       │               │
│  └───────────────────┘      └───────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
                          ▲
                          │ 数据源
┌─────────────────────────────────────────────────────────────────┐
│  数据源                                                            │
│  • 昇腾官方API文档 (1786+ API)                                    │
│  • 6个昇腾算子仓 (HierarchicalKV, fbgemm, ops-*)                  │
│  • 规划中: CUDA算子仓 (cuBLAS, CUTLASS)                           │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 双存储架构

| 存储类型 | 技术 | 用途 |
|----------|------|------|
| 向量存储 | ChromaDB | 语义检索、相似度匹配 |
| KV存储 | Redis | 精确索引、元数据、关联查询 |

**设计决策**: ChromaDB (嵌入式、无服务、零运维) + Redis (高读写、丰富数据结构)

### 2.3 知识分类

| 知识类型 | 存储位置 | 说明 |
|----------|----------|------|
| AscendC API | ChromaDB + Redis | 函数签名、参数、示例 |
| NPU算子Bug修复 | ChromaDB + Redis | 根因、触发条件、修复方案 |
| NPU优化方案 | ChromaDB + Redis | 优化类型、量化指标 |
| GPU算子知识 | 规划中 | CUDA实现、跨平台映射 |
| 跨平台适配 | 规划中 | GPU→NPU映射关系 |

---

## 3. 功能需求

### 3.1 API知识库

- R1. **API采集**: 从昇腾官方文档持续采集API定义（当前1786+ API）
- R2. **API分类**: 支持按category/subcategory/hardware_domain多维度分类
- R3. **API检索**: 支持精确查询、语义搜索、类别过滤
- R4. **API详情**: 返回完整签名、参数说明、使用示例、注意事项

### 3.2 NPU算子知识

- R5. **Bug知识抽取**: 从PR/commit中抽取Bug修复知识（根因、触发条件、修复方案）
- R6. **优化知识抽取**: 从PR/commit中抽取优化知识（优化类型、量化指标）
- R7. **PR分类**: 自动区分bugfix/optimization/feature commits
- R8. **置信度评估**: 基于完整度/来源/时效性计算置信度

### 3.3 GPU→NPU跨平台（规划中）

- R9. **GPU知识采集**: 接入CUDA算子仓（cuBLAS, CUTLASS等）
- R10. **API映射**: 建立GPU API → NPU API对应关系
- R11. **适配辅助**: 提供GPU→AscendC的转换建议

### 3.4 Agent集成

- R12. **MCP接口**: 支持MCP协议的查询接口
- R13. **REST API**: 提供HTTP查询接口
- R14. **Python SDK**: 提供Python查询客户端
- R15. **主动查询**: Agent开发前查询参考知识
- R16. **被动查询**: Agent遇问题时搜索解决方案

---

## 4. 数据模型

### 4.1 AscendCAPIDefinition

| 字段 | 类型 | 说明 |
|------|------|------|
| api_id | str | 唯一标识 |
| canonical_name | str | 标准名称 |
| full_signature | str | 完整签名 |
| category | str | 主类别 |
| subcategory | str | 子类别 |
| description | str | 功能描述 |
| parameters | List[APIParameter] | 参数列表 |
| return_value | APIReturnValue | 返回值 |
| usage_examples | List[UsageExample] | 使用示例 |
| 注意事项 | List[str] | 注意事项 |
| confidence | float | 置信度 |

### 4.2 BugFixKnowledge

| 字段 | 类型 | 说明 |
|------|------|------|
| bug_id | str | 唯一标识 |
| operator_id | str | 关联算子 |
| bug_title | str | Bug描述 |
| symptom | str | 表现 |
| root_cause | str | 根因 |
| trigger_conditions | List[str] | 触发条件 |
| fix_pattern | str | 修复方案 |
| related_apis | List[str] | 涉及API |
| confidence | float | 置信度 |
| severity | enum | critical/major/minor |
| category | enum | correctness/performance/numerical/memory/sync |

### 4.3 OptimizationKnowledge

| 字段 | 类型 | 说明 |
|------|------|------|
| opt_id | str | 唯一标识 |
| operator_id | str | 关联算子 |
| opt_title | str | 优化标题 |
| optimization_type | List[str] | 优化类型 |
| optimization_description | str | 优化方案 |
| improvement_ratio | float | 提升比例（可选） |
| related_apis | List[str] | 涉及API |
| confidence | float | 置信度 |

---

## 5. 查询接口

### 5.1 主动查询（开发参考）

```python
# 查询指定算子的bug和优化知识
result = await service.query_for_development(
    operator_name="Matmul",
    query_type="all"  # "bug" | "optimization" | "all"
)
```

### 5.2 被动查询（问题排查）

```python
# 根据症状搜索相似bug
result = await service.query_for_troubleshooting(
    symptom="Matmul算子crash",
    operator_name="Matmul",
    error_message="address error"
)
```

### 5.3 API查询

```python
# 精确查询或语义搜索
result = await service.query_api(
    api_name="VecReduceMax",
    include_examples=True
)
```

---

## 6. 实施路径

### 6.1 阶段划分

| Phase | 内容 | 时间 | 人天 |
|-------|------|------|------|
| Phase 1 | 双存储架构搭建 | 14天 | 14 |
| Phase 2a | 原子化知识图谱 | 21天 | 21 |
| Phase 2b | 增量同步管道 | 21天 | 21 |
| Phase 3 | 置信度排序层 | 14天 | 14 |
| Phase 4 | 质量评分体系 | 14天 | 14 |
| Phase 5 | Bug/优化知识设计 | 18天 | 18 |
| **合计** | | **84天** | **102人天** |

### 6.2 里程碑

| 里程碑 | 日期 | 验收条件 |
|--------|------|----------|
| M1: 存储基础设施 | 2026-04-28 | ChromaDB + Redis 部署完成 |
| M2: MVP可用 | 2026-06-04 | 支持Agent查询 |
| M3: 全面上线 | 2026-06-18 | 增量同步正常运行 |
| M4: Bug/优化知识 | 2026-07-03 | Bug≥200条，优化≥100条 |
| M5: 知识库自洽 | 2026-09-01 | 知识≥500条，月活≥1000次 |

---

## 7. 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 向量库 | ChromaDB | 嵌入式、零运维、当前规模足够 |
| KV存储 | Redis | 高性能、丰富数据结构 |
| Embedding | sentence-transformers | 本地运行、成本可控 |
| LLM | Claude 3.5 Sonnet | 抽取准确率高 |

---

## 8. 成功标准

### 8.1 质量标准

- [ ] 向量检索延迟 < 200ms (P99)
- [ ] 单次查询返回Top-5相关知识
- [ ] Bug知识≥200条，优化知识≥100条
- [ ] API接口可用率≥99.9%
- [ ] 基础置信度排序生效

### 8.2 功能标准

- [ ] 支持开发参考查询（bug、优化）
- [ ] 支持问题排查查询（症状→根因）
- [ ] 支持API精确查询和语义搜索
- [ ] 支持MCP协议集成
- [ ] 支持增量知识同步

---

## 9. 已知限制

- GPU算子知识采集尚未开始（规划中）
- 跨平台API映射尚未实现（规划中）
- 核心代码未实现（当前只有骨架）
- 未进行实际部署验证

---

## 10. 下一步

所有设计文档已完备，下一步应进入 `/ce:plan` 进行结构化的实施规划。

---

**文档来源**:
- docs/design/2026-04-09-ascendc-api-knowledge-base-design.md
- docs/design/2026-04-09-gpu-npu-cross-platform-knowledge-base-design.md
- docs/design/2026-04-10-npu-bug-optimization-knowledge-design.md
- docs/roadmap/2026-04-09-ascendc-knowledge-base-implementation-roadmap.md
- docs/analysis/pr_sampling_report.md
