---
title: LLM 冷启动补充抽取管道
type: feat
status: completed
date: 2026-04-11
origin: docs/brainstorms/2026-04-11-llm-extraction-pipeline-requirements.md
---

# LLM 冷启动补充抽取管道

## Overview

对1201条bug_fixes记录进行LLM重新抽取，补全 `root_cause` 和 `fix_pattern` 字段，提升知识库数据质量。

## Problem Frame

当前知识库存在数据质量问题：1201条bug_fixes记录中，核心字段 `root_cause` 和 `fix_pattern` 为null或空值。MVP组件已完成但数据质量未达标，无法真正服务于实际应用场景。

## Requirements Trace

- **R1**: 优先级筛选引擎 - 按引用频率/算子重要性/缺失程度排序
- **R2**: LLM 抽取管道 - 使用 Claude 3.5 Sonnet 批量抽取bug知识
- **R4**: 质量评估报告 - 生成抽取质量报告

> 注: R3 (增量同步) 已延期，优先完成冷启动补充

## Scope Boundaries

**在范围内:**
- Bug知识的LLM抽取（root_cause, fix_pattern, trigger_conditions, related_apis）
- 优先级筛选引擎
- 质量评估报告

**不在范围内:**
- 增量同步管道（R3，已延期）
- API知识/优化知识的LLM抽取
- 自动修正流程

## Key Decisions

- **LLM Provider**: Claude 3.5 Sonnet via `UnifiedLLMClient(provider="anthropic")`
- **抽取策略**: 优先级筛选 (CitationScore=0.4, OperatorScore=0.3, MissingFieldScore=0.3)
- **批次大小**: 10条/批，控制并发
- **已有模式复用**: 扩展现有 `BugExtractor._llm_extract()` 和 `LLMBasedRetry`

## Context & Research

### Relevant Code and Patterns

| 模式 | 文件 | 说明 |
|------|------|------|
| BugExtractor | `src/asc_ops/extractor/bug_extractor.py` | 已有 `_llm_extract()` 方法，可复用 |
| LLMBasedRetry | `src/asc_ops/extractor/retry.py` | 已有重试管道，可扩展 |
| KnowledgeStorage | `src/asc_ops/extractor/knowledge_storage.py` | 已有 `store_bugfix()` 和 Redis 存储 |
| UnifiedLLMClient | `src/asc_ops/llm/client.py` | 支持 anthropic provider |
| CitationTracker | `src/asc_ops/quality/citation_tracker.py` | 提供引用统计 |
| Redis Keys | `src/asc_ops/storage/keys.py` | 键名前缀规范 |

### Institutional Learnings

- 已有 `LLMBasedRetry` 模式，但只处理抽取失败的记录
- 冷启动导入时已调用过LLM，但21条记录仍全部失败，原因是PR本身无技术细节
- `BugExtractor` 的 `BUG_EXTRACTION_PROMPT` 已存在，可直接使用

## Open Questions

### Resolved During Planning

1. **优先级权重**: CitationScore=0.4, OperatorScore=0.3, MissingFieldScore=0.3
2. **抽取批次大小**: 10条/批
3. **R3延期**: 增量同步管道暂不实现，冷启动优先
4. **报告格式**: Markdown 格式输出到 `data/quality_report_{timestamp}.md`

### Deferred to Implementation

5. **Webhook安全**: R3实现时处理
6. **报告自动推送**: R3实现时考虑

## Implementation Units

- [x] **Unit 1: 优先级评分引擎 (PriorityScorer)**

**Goal:** 对bug记录按优先级排序，输出有序队列

**Requirements:** R1

**Dependencies:** None

**Files:**
- Create: `src/asc_ops/extractor/priority_scorer.py`
- Test: `tests/unit/extractor/test_priority_scorer.py`

**Approach:**
- 创建 `PriorityScorer` 类
- 实现三维度评分: CitationScore, OperatorScore, MissingFieldScore
- 从 Redis/CitationTracker 获取引用数据
- 输出 `List[BugPriorityItem]` 有序队列

**Patterns to follow:**
- `src/asc_ops/quality/citation_tracker.py` - Redis 读取模式
- `src/asc_ops/extractor/knowledge_storage.py` - Redis 交互封装

**Test scenarios:**
- 核心算子 (Matmul/Add/Conv) 的 OperatorScore = 1.0
- 两者都空的 MissingFieldScore = 1.0
- 引用次数归一化正确 (max_citation=100时，50次→0.5)

**Verification:**
- `pytest tests/unit/extractor/test_priority_scorer.py -v` 通过

---

- [x] **Unit 2: 批量抽取器 (BatchBugExtractor)**

**Goal:** 对优先级队列中的bug记录批量调用LLM抽取

**Requirements:** R2

**Dependencies:** Unit 1

**Files:**
- Create: `src/asc_ops/extractor/batch_extractor.py`
- Test: `tests/unit/extractor/test_batch_extractor.py`

**Approach:**
- 复用 `BugExtractor._llm_extract()` 和 `BUG_EXTRACTION_PROMPT`
- 新增 `BatchBugExtractor.extract_batch()` 方法
- 支持批次并发 (10条/批)
- 处理null返回情况，记录置信度
- 更新 Redis 中 `has_root_cause`, `has_fix_pattern` 标记

**Technical design:**
```
class BatchBugExtractor:
    async def extract_batch(
        self,
        bug_records: List[BugRecord],
        batch_size: int = 10,
    ) -> BatchResult:
        # 并发控制 semaphore
        # 对每条记录调用 LLM
        # 合并结果，更新存储
```

**Patterns to follow:**
- `src/asc_ops/extractor/retry.py` - LLM 调用模式
- `src/asc_ops/extractor/bug_extractor.py` - `_llm_extract()` 实现

**Test scenarios:**
- 10条记录批量抽取成功
- 单条LLM返回null时不影响其他记录
- 置信度 < 0.5 标记待审核

**Verification:**
- `pytest tests/unit/extractor/test_batch_extractor.py -v` 通过

---

- [x] **Unit 3: 质量评估报告 (ExtractionQualityReporter)**

**Goal:** 生成抽取质量报告，量化管道效果

**Requirements:** R4

**Dependencies:** Unit 2

**Files:**
- Create: `src/asc_ops/extractor/quality_reporter.py`
- Test: `tests/unit/extractor/test_quality_reporter.py`

**Approach:**
- 统计字段填充率 (root_cause, fix_pattern)
- 生成问题记录列表
- 输出 Markdown 格式报告
- 支持重复运行（幂等）

**Patterns to follow:**
- `src/asc_ops/quality/stats_api.py` - 统计 API 模式
- `scripts/cold_start/import_bug_opt_knowledge.py` - 报告输出模式

**Test scenarios:**
- 空知识库生成全0报告
- 部分填充时正确计算百分比

**Verification:**
- `pytest tests/unit/extractor/test_quality_reporter.py -v` 通过

---

- [x] **Unit 4: CLI 脚本 (llm_retry_batch)**

**Goal:** 提供命令行接口执行批量LLM抽取

**Requirements:** R1, R2, R4

**Dependencies:** Units 1, 2, 3

**Files:**
- Create: `scripts/llm_retry_batch.py`

**Approach:**
- CLI 参数: `--limit`, `--batch-size`, `--report-only`
- `--report-only` 仅生成质量报告，不执行抽取
- `--dry-run` 预览优先级队列，不执行抽取
- 整合 Units 1-3 的功能

**Patterns to follow:**
- `scripts/cold_start/import_bug_opt_knowledge.py` - CLI 模式
- `src/asc_ops/cli/operator_sync.py` - 参数解析模式

**Test scenarios:**
- `--help` 显示正确用法
- `--dry-run` 输出队列预览

**Verification:**
- `python scripts/llm_retry_batch.py --help` 正常输出

---

- [x] **Unit 5: 端到端验证**

**Goal:** 在真实数据上验证完整管道

**Requirements:** R1, R2, R4, Success Criteria

**Dependencies:** Units 1-4

**Files:**
- Test: `tests/e2e/test_llm_extraction_pipeline.py` (create if not exists)

**Approach:**
- 使用真实 ChromaDB/Redis 数据
- 执行完整抽取流程
- 验证字段填充率提升
- 生成最终质量报告

**Verification:**
- Top 100 bug 的 root_cause 填充率 > 70%
- Top 100 bug 的 fix_pattern 填充率 > 50%
- 单条抽取延迟 P95 < 5秒

## System-Wide Impact

- **Storage**: `KnowledgeStorage.store_bugfix()` 被调用更新已有记录
- **Redis Keys**: 新增 `bugfix:priority:queue` 用于优先级队列
- **ChromaDB Metadata**: 更新 `has_root_cause`, `has_fix_pattern` 标记

## Risks & Dependencies

| 风险 | 影响 | 缓解 |
|------|------|------|
| Claude API 限流 | 抽取中断 | 添加 rate limiter，控制并发 |
| 部分PR无技术细节 | 填充率不达标 | 接受上限，报告问题记录 |
| Redis/ChromaDB 连接失败 | 管道中断 | 添加重连逻辑 |

## Documentation / Operational Notes

- 使用前确保 `ANTHROPIC_API_KEY` 环境变量已配置
- 建议先 `--dry-run` 预览优先级队列
- 建议先 `--report-only` 查看当前质量基线

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-11-llm-extraction-pipeline-requirements.md](../brainstorms/2026-04-11-llm-extraction-pipeline-requirements.md)
- Related code: `src/asc_ops/extractor/bug_extractor.py`, `src/asc_ops/extractor/retry.py`
- Related tests: `tests/unit/extractor/test_bug_extractor.py`
