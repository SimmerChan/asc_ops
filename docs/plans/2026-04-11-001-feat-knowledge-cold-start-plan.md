---
title: "Knowledge Cold Start Plan"
type: feat
status: active
date: 2026-04-11
origin: docs/brainstorms/2026-04-10-complete-design-requirements.md
---

# AscendC Operator Knowledge Base - 知识冷启动计划

## Overview

将 1786+ AscendC API 和 Bug/优化知识导入知识库，完成 MVP 知识冷启动。

**来源文档**: `docs/brainstorms/2026-04-10-complete-design-requirements.md`

---

## Problem Frame

MVP 代码已完成，但知识库为空。Agent 无法检索到有效知识。需要：
1. 从昇腾官方文档导入 1786+ API 定义
2. 从 6 个昇腾算子仓导入 Bug/优化知识

---

## Requirements Trace

- R1. API采集: 从昇腾官方文档持续采集 API 定义（1786+ API）
- R5. Bug知识抽取: 从 PR/commit 中抽取 Bug 修复知识
- R6. 优化知识抽取: 从 PR/commit 中抽取优化知识
- R7. PR分类: 自动区分 bugfix/optimization/feature commits

---

## Scope Boundaries

**包含**:
- AscendC API 文档导入
- Bug/优化知识从 6 仓导入
- 知识存储到 ChromaDB + Redis
- 基础质量验证

**不包含**:
- GPU 算子知识采集（Phase 6）
- 跨平台 API 映射（Phase 6）
- 增量同步管道验证（部署后）

---

## Data Sources

### 6 个昇腾算子仓

| 仓库 | 总Commits | Bugfix | Optimization | Feature |
|------|-----------|--------|--------------|---------|
| HierarchicalKV-ascend | 16 | 6 (37.5%) | 2 (12.5%) | 6 (37.5%) |
| fbgemm-ascend | 13 | 3 (23.1%) | 0 (0%) | 6 (46.2%) |
| ops-nn | 100 | 27 (27%) | 5 (5%) | 68 (68%) |
| ops-math | 100 | 26 (26%) | 5 (5%) | 69 (69%) |
| ops-transformer | 80 | ~20 | ~4 | ~56 |
| ops-cv | 80 | ~20 | ~4 | ~56 |

---

## Implementation Units

- [ ] **Unit 0: 前置准备（环境与数据）**

**Goal:** 搭建冷启动前置环境

**Approach:**
1. 确认 6 个昇腾仓已 clone 到 `/tmp/ascend_repos/`（参考 `scripts/analyze_repos.py` 的仓库列表）
2. 确认 ChromaDB 和 Redis 可用
3. 创建 `scripts/cold_start/` 目录

**Verification:**
- `ls /tmp/ascend_repos/` 显示 6 个仓库目录
- `scripts/cold_start/` 目录已创建

---

- [ ] **Unit 1: 验证 API 文档采集链路**

**Goal:** 验证昇腾官方 API 文档可正确解析和导入

**Requirements:** R1

**Files:**
- Modify: `src/asc_ops/collector/official_docs.py`
- Create: `scripts/cold_start/import_apis.py`

**Approach:**
1. 检查 `OfficialDocsClient` 的 base_url 配置
2. 确认 API 列表文件或采集逻辑
3. 运行小批量导入测试（10 个 API）

**Verification:**
- 10 个 API 成功导入 ChromaDB
- Redis 中元数据正确

---

- [ ] **Unit 2: 创建 Bug/优化知识导入脚本**

**Goal:** 从 6 个昇腾算子仓批量导入 Bug/优化知识

**Requirements:** R5, R6, R7

**Files:**
- Create: `scripts/cold_start/import_bug_opt_knowledge.py`
- Modify: `src/asc_ops/extractor/bug_extractor.py` (如需要)
- Modify: `src/asc_ops/extractor/opt_extractor.py` (如需要)

**Approach:**
1. 使用现有 `BugExtractor` 和 `OptExtractor`（纯规则匹配，**无 LLM**）
2. 从本地已 clone 的仓库 (`/tmp/ascend_repos/`) 读取 commit 详情
3. 对 bugfix/optimization commits，提取 commit message 作为 title
4. 调用规则抽取器 `extract(pr_title, pr_body=commit_message, ...)` 尝试提取
5. 规则抽取基于关键词匹配（ROOT_CAUSE_KEYWORDS, FIX_PATTERN_KEYWORDS 等）
6. 由于 commit message 极短（28-30 字符），大多数条目 `extraction_success=False`
7. **修改 `KnowledgeStorage.store_bugfix()` 和 `store_optimization()`**：移除 `extraction_success=False` 跳过逻辑，**所有条目都存储**
8. 存储到 ChromaDB (向量) + Redis (元数据)

**⚠️ 关键修改**: 现有 `store_bugfix()` 在 `extraction_success=False` 时跳过存储（见 `knowledge_storage.py:58-60`）。必须修改此逻辑，否则 ~90% 的低信号 commits 不会被存储。

**Patterns to follow:**
- `scripts/analyze_repos.py` - PR 分类逻辑（已有）
- `src/asc_ops/extractor/bug_extractor.py` - 规则抽取器（无 LLM）
- `src/asc_ops/extractor/knowledge_storage.py` - 存储逻辑需修改

**Test scenarios:**
- ops-nn 仓库 bugfix commits 全部处理
- 验证 extraction_success=True 的条目包含 root_cause 或 fix_pattern
- 验证 extraction_success=False 的条目仍被存储（已修改后的行为）

**Verification:**
- ops-nn 导入后 ChromaDB bug_fixes collection 记录数 > 0
- Redis 记录 extraction_success 分布（预期大多数为 False）

---

- [ ] **Unit 3: 批量导入所有仓库**

**Goal:** 完成 6 个仓的 Bug/优化知识导入

**Requirements:** R5, R6, R7

**Dependencies:** Unit 2 (脚本已创建并验证)

**Files:**
- Modify: `scripts/cold_start/import_bug_opt_knowledge.py` (扩展支持多仓库循环)

**Approach:**
1. 扩展 Unit 2 脚本，支持传入仓库名称批量处理
2. 对 6 个仓库依次运行导入
3. 记录导入统计（成功/失败/low_signal跳过）
4. 使用 source_repo + source_pr 作为去重 key，避免重复导入

**Verification:**
- 6 个仓库全部导入完成
- 无重复记录（验证 Redis key 数量）

---

- [ ] **Unit 4: 质量验证**

**Goal:** 验证导入知识的存储和检索可用性

**Requirements:** R5, R6, R7

**Files:**
- Create: `scripts/cold_start/verify_knowledge.py`

**Approach:**
1. 验证 ChromaDB 存储：查询 `bug_fixes` 和 `optimizations` collection 记录数 > 0
2. 验证 Redis 存储：查询 `bugfix:*` 和 `optimization:*` key 数量
3. 验证 extraction_success 分布：统计 True/False 比例
4. **检索可用性测试**：调用 `KnowledgeQueryService.query_for_development()` 查询已知算子，验证返回非空（不验证相关性，因为低信号数据相关性自然低）

**Verification:**
- ChromaDB bug_fixes collection 有记录
- Redis 有对应元数据
- 检索返回非空结果（证明管道可用）

**注**: 不验证检索相关性，因为低信号 commit 数据（无 root_cause/trigger_conditions）相关性自然差。验证目标是**管道可用性**，不是知识质量。

---

## High-Level Technical Design

```
┌─────────────────────────────────────────────────────────────┐
│                    Cold Start Pipeline                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  API Docs    │    │  6 Repos     │    │  Extraction  │  │
│  │  (1786+)     │    │  Commits     │    │  Validators  │  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘  │
│         │                   │                   │           │
│         ▼                   ▼                   │           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              ChromaDB + Redis                       │    │
│  │  • API向量    • Bug知识    • 优化知识               │    │
│  └─────────────────────────────────────────────────────┘    │
│                            │                                │
│                            ▼                                │
│                   ┌──────────────┐                          │
│                   │   Verify     │                          │
│                   │  Sampling    │                          │
│                   └──────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Open Questions

### Resolved During Planning

- **Q: Bug/优化知识存储到哪里？**
  A: ChromaDB (向量) + Redis (元数据 Hash)。Bug 知识使用 `bug:detail:{bug_id}` key，索引到 `bug:operator:{operator_id}` Set。

- **Q: 抽取使用 LLM 还是规则？**
  A: 当前使用规则抽取（BugExtractor 是纯规则匹配）。不依赖 LLM API。

- **Q: 短 commit message 如何处理？**
  A: 所有 commits 都存储，extraction_success 标记实际抽取结果。

### Deferred to Implementation

- **Q: API 文档是否有现成的数据文件（如 JSON/CSV）？**
  A: 如无，需要配置爬虫或确认文档访问方式

- **Q: 是否需要增强 LLM 抽取能力？**
  A: 冷启动后，如果低置信度条目过多，可考虑：1) 获取 PR body 而非仅 commit message；2) 构建 LLM 抽取客户端。

---

## Risks & Dependencies

- **风险**: 昇腾官方文档可能有访问限制或需要认证
- **缓解**: 先小批量测试，确认可用后再批量导入

- **风险**: commit message 极短（28-30 字符），规则抽取成功率 <10%
- **缓解**: 所有 commits 都存储为知识条目；未来可引入 PR body 获取或 LLM 抽取增强

---

## Documentation / Operational Notes

- 导入完成后更新 `docs/README.md` 数据规模表格
- 记录导入日志便于排查问题

---

## Success Metrics

| 指标 | 目标 | 验证方式 | 说明 |
|------|------|----------|------|
| API 导入数量 | 1786+ | ChromaDB collection count | 文档访问受限 |
| Bug 知识存储 | ~102条 | ChromaDB bug_fixes count | **依赖代码修改**：移除 extraction_success=False 跳过逻辑 |
| 优化知识存储 | ~20条 | ChromaDB optimizations count | 同上 |
| extraction_success=True | 10%+ | Redis key count | 规则抽取有实质内容的比例 |
| 检索管道可用 | True | query_for_development() 非空 | 管道通，不验证相关性 |

**关键依赖**: `knowledge_storage.py` 的 `store_bugfix()` 和 `store_optimization()` 必须修改，移除 `extraction_success=False` 跳过逻辑（line 58-60, 101-103）。否则 ~90% 低信号 commits 不会被存储。

---

## Sources & References

- Origin document: [docs/brainstorms/2026-04-10-complete-design-requirements.md](docs/brainstorms/2026-04-10-complete-design-requirements.md)
- PR Sampling: [docs/analysis/pr_sampling_report.md](docs/analysis/pr_sampling_report.md)
- Bug Extractor: `src/asc_ops/extractor/bug_extractor.py`
- Opt Extractor: `src/asc_ops/extractor/opt_extractor.py`
- API Storage: `src/asc_ops/collector/api_storage.py`
