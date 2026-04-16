---
title: PR 分类器增强
type: feat
status: completed
date: 2026-04-16
origin: docs/brainstorms/2026-04-16-pr-classifier-enhancement-requirements.md
---

# PR 分类器增强

## Overview

增强 PR 分类器，实现规则层 + LLM 混合架构，提升 bugfix/optimization/feature/unknown 四类分类准确率。

## Problem Frame

当前分类器仅依赖 `pr_title` + `pr_body`，使用固定权重关键词匹配：
- 中文分词粒度过粗（"精度修复"未识别"修复"）
- 无负向关键词过滤（"新增"压制"修复"）
- 无 LLM fallback，歧义 case 全部误判

目标：规则层处理 70-80% 高置信度 case，LLM 处理 20-30% 歧义 case。

## Requirements Trace

- R1. 规则层改进：改进分词器 + 负向关键词过滤 + commit_message 传入
- R2. LLM Fallback：当置信度 < 0.5 时触发
- R3. LLM Prompt：定义 4 种类型判断标准和 few-shot examples
- R4. 分类器集成：BugExtractor/OptimizationExtractor 透明使用增强后的分类器

## Scope Boundaries

- 修改 `PRClassifier` 支持 enhanced classify 和 LLM fallback
- 添加 Redis 缓存（7 天 TTL）
- 更新 `BugExtractor` 和 `OptimizationExtractor` 调用方式
- 添加单元测试和标注样本验证

**不在范围内：**
- 独立部署分类服务
- 模型训练 / Fine-tuning

## Context & Research

### Relevant Code and Patterns

- `src/asc_ops/extractor/classifier.py` — `PRClassifier.classify(title, body, commit_message="")`
- `src/asc_ops/llm/client.py` — `UnifiedLLMClient.chat(messages)` async 接口
- `src/asc_ops/extractor/retry.py` — Redis 使用模式
- `src/asc_ops/storage/redis_client.py` — RedisClient
- `tests/unit/extractor/test_classifier.py` — 现有测试

### LLM Provider

使用 `UnifiedLLMClient`，provider 配置与 batch_extractor 保持一致。

## Key Technical Decisions

- **混合架构**：规则层置信度 ≥ 0.5 直接返回，< 0.5 触发 LLM
- **Diff 摘要**：取 diff 前 500 字符作为 LLM 输入
- **缓存策略**：Redis key = `pr:classifier:{pr_id}`，TTL = 7 天
- **Prompt 设计**：已在需求文档中定义

## Open Questions

### Resolved During Planning

- **Diff 摘要提取逻辑**：取 diff 前 500 字符，理由：平衡信息量和 token 成本

### Deferred to Implementation

- **0.5 阈值验证**：需在标注集上验证，可通过实验调整

## Implementation Units

- [x] **Unit 1: 增强 PRClassifier 分词器和关键词过滤** ✅

**Goal:** 改进规则层分类准确率，覆盖 70-80% case

**Requirements:** R1

**Dependencies:** None

**Files:**
- Modify: `src/asc_ops/extractor/classifier.py`

**Approach:**
1. 改进 `_tokenize` 方法：
   - 先提取单字关键词（从所有关键词集合中取长度为 1 的词）
   - 再进行 2-4 字符切分
2. 添加负向关键词集合：`FEATURE_NEGATIVE = {"新增", "实现", "支持", "添加"}`
3. 修改 `classify` 方法：
   - 当 feature 类关键词与 bugfix 类关键词同时出现时，降低 bugfix 置信度
4. 启用 `commit_message` 参数参与计算

**Patterns to follow:** 现有 `PRClassifier` 代码结构

**Test scenarios:**
- "精度修复" → 识别出"修复"，正确分类为 bugfix
- "新增xxx修复yyy" → 识别 bugfix 信号不被压制
- "优化GroupedMatmul" → 正确分类为 optimization

**Verification:**
- 规则层对 100 条样本的分类准确率 > 70%

---

- [x] **Unit 2: 添加 LLM Fallback 机制** ✅

**Goal:** 当规则层置信度 < 0.5 时，使用 LLM 分类

**Requirements:** R2, R3

**Dependencies:** Unit 1

**Files:**
- Modify: `src/asc_ops/extractor/classifier.py`
- Create: `src/asc_ops/extractor/llm_classifier.py` (可选，内联实现更简洁)

**Approach:**
1. 在 `PRClassifier` 中添加 `classify_with_llm` async 方法
2. LLM 输入构建：
   - system_prompt: 定义 4 种类型和判断标准
   - user_message: `{title}\n{body}\nDIFF_SUMMARY:\n{diff_summary[:500]}`
3. 解析 LLM 返回：提取 type, confidence, reason
4. 结果缓存到 Redis

**Patterns to follow:**
- `UnifiedLLMClient.chat()` 接口模式
- `src/asc_ops/extractor/retry.py` 的 Redis 使用模式

**Test scenarios:**
- 低置信度 case 触发 LLM 调用
- LLM 返回格式正确解析
- Redis 缓存命中时不调用 LLM

**Verification:**
- LLM fallback 响应延迟 < 2s
- 缓存命中率 > 50%（相同 PR 不重复调用 LLM）

---

- [x] **Unit 3: 更新 Extractor 集成** ✅

**Goal:** BugExtractor 和 OptimizationExtractor 透明使用增强后的分类器

**Requirements:** R4

**Dependencies:** Unit 1, Unit 2

**Files:**
- Modify: `src/asc_ops/extractor/bug_extractor.py`
- Modify: `src/asc_ops/extractor/opt_extractor.py`

**Approach:**
1. 修改 `BugExtractor.extract` 调用：
   - 传入 `commit_message` 参数
   - 当规则层置信度 < 0.5 时，使用 `classify_with_llm`
2. 修改 `OptimizationExtractor.extract` 同理
3. 分类结果记录到 extraction metadata

**Patterns to follow:** 现有 `extract` 方法签名

**Test scenarios:**
- BugExtractor 正确跳过非 bugfix PR
- OptimizationExtractor 正确跳过非 optimization PR
- LLM fallback 正常工作

**Verification:**
- 集成测试通过
- 分类 metadata 正确记录

---

- [x] **Unit 4: 评估和测试** ✅

**Goal:** 验证分类准确率提升

**Requirements:** Success Criteria

**Dependencies:** Unit 1, Unit 2, Unit 3

**Files:**
- Modify: `tests/unit/extractor/test_classifier.py`
- Create: `data/classifier_eval_samples.json` (标注样本集)

**Approach:**
1. 准备 50-100 条人工标注样本
2. 运行分类器评估：
   - 计算 precision/recall per type
   - 测量 LLM 调用率
3. 记录评估结果到 `data/classifier_eval_YYYYMMDD.json`

**Test scenarios:**
- BugFix precision > 90%, recall > 80%
- LLM 调用率 < 30%
- 规则层处理 70-80% case

**Verification:**
- 评估指标达到目标
- 测试覆盖所有 4 种类型

## System-Wide Impact

- **BugExtractor**: 跳过非 bugfix PR 的逻辑不变，但分类更准确
- **OptimizationExtractor**: 同上
- **LLM 调用量**: 预计增加 20-30% 的 LLM 流量（用于分类）

## Risks & Dependencies

| 风险 | 影响 | 缓解 |
|------|------|------|
| LLM API 成本增加 | 中 | 缓存 + 阈值控制 |
| LLM API 延迟 | 低 | 2s 内响应，可接受 |
| 缓存雪崩 | 低 | TTL 分散 + 随机化 |

## Documentation / Operational Notes

- 更新 `docs/` 记录分类器改进
- 标注样本集可复用于未来评估

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-16-pr-classifier-enhancement-requirements.md](../brainstorms/2026-04-16-pr-classifier-enhancement-requirements.md)
- **Existing classifier:** `src/asc_ops/extractor/classifier.py`
- **LLM client:** `src/asc_ops/llm/client.py`
