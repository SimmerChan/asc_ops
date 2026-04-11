---
date: 2026-04-11
topic: llm-extraction-pipeline
status: draft
---

# LLM 冷启动补充抽取管道

**文档版本**: v1.0
**创建日期**: 2026-04-11
**状态**: 需求已明确，待规划

---

## Problem Frame

当前知识库存在数据质量问题：1201条bug_fixes记录中，核心字段 `root_cause` 和 `fix_pattern` 为null或空值，导致查询结果无法提供有价值的调试信息。

MVP组件已完成，但数据质量未达标，无法真正服务于实际应用场景。

---

## Requirements

### R1: 优先级筛选引擎

**目标**: 对1201条记录按优先级排序，优先抽取高价值知识

**功能需求**:
- R1.1: 按引用频率筛选 - 优先抽取被高频引用的bug知识
- R1.2: 按算子重要性筛选 - 核心算子(Add/MatMul/Conv等)的bug优先
- R1.3: 按缺失程度筛选 - root_cause和fix_pattern都为空的优先
- R1.4: 输出优先级队列 - 生成待抽取记录的有序列表

**优先级评分公式**:
```
PriorityScore = w1 × CitationScore + w2 × OperatorScore + w3 × MissingFieldScore

其中:
- CitationScore: 引用次数归一化 (0-1)
- OperatorScore: 算子重要性 (核心算子=1.0, 其他=0.5)
- MissingFieldScore: 字段缺失程度 (两者都空=1.0, 部分空=0.5, 无缺失=0)
```

---

### R2: LLM 抽取管道

**目标**: 使用 Claude 3.5 Sonnet 对优先级队列中的bug知识记录进行重新抽取

**功能需求**:
- R2.1: 调用 Claude API 抽取 root_cause（根因分析）
- R2.2: 调用 Claude API 抽取 fix_pattern（修复模式）
- R2.3: 支持触发条件、影响范围、相关API等辅助字段抽取
- R2.4: 处理Claude返回null的情况（简单修复无深度信息）
- R2.5: 记录抽取置信度，支持后续过滤

**抽取Prompt设计**:
```
从以下Bug修复PR信息中抽取结构化知识：

PR标题: {pr_title}
PR描述: {pr_description}
代码变更: {code_diff}

请抽取:
1. root_cause: 根因分析（为什么会出现这个bug）
2. fix_pattern: 修复模式（如何修复的）
3. trigger_conditions: 触发条件
4. related_apis: 涉及的API列表

如果信息不足以抽取某字段，返回null。
以JSON格式输出。
```

---

### R3: 增量同步管道

**目标**: 新PR合并时实时触发LLM抽取，保证新数据质量

**功能需求**:
- R3.1: Webhook接收PR合并事件
- R3.2: 调用LLM抽取知识（异步，非阻塞）
- R3.3: 存储抽取结果到ChromaDB + Redis
- R3.4: 失败重试机制（最多3次）
- R3.5: 抽取结果质量评估（置信度 < 0.5 标记待审核）

---

### R4: 质量评估报告

**目标**: 生成抽取质量报告，量化管道效果

**功能需求**:
- R4.1: 统计抽取成功率（成功/失败/部分成功）
- R4.2: 计算字段填充率（root_cause填充率、fix_pattern填充率）
- R4.3: 生成问题记录列表（哪些bug仍无法抽取）
- R4.4: 输出质量趋势（随时间的变化）

---

## Success Criteria

- [ ] 优先级队列生成正确，高价值bug优先被处理
- [ ] Claude抽取后，top 100 bug记录的 root_cause 填充率 > 70%
- [ ] Claude抽取后，top 100 bug记录的 fix_pattern 填充率 > 50%
- [ ] 单条记录抽取延迟 < 5秒（95th percentile）
- [ ] 抽取管道可重复运行，不产生重复记录

---

## Scope Boundaries

**在范围内**:
- Bug知识的LLM抽取（root_cause, fix_pattern, trigger_conditions, related_apis）
- 优先级筛选引擎
- 增量同步管道
- 质量评估报告

**不在范围内**:
- API知识的LLM抽取（当前API数据来自官方文档，质量已较好）
- 优化知识的LLM抽取（待bug抽取验证后扩展）
- 自动修正流程（检测到低质量知识后自动重抽）

---

## Key Decisions

- **LLM提供商**: Claude 3.5 Sonnet（中文理解能力强，适合昇腾场景）
- **抽取策略**: 优先级筛选，非全量抽取（控制成本）
- **冷启动优先**: 先补充历史记录，上线增量同步后再保新增

---

## Dependencies / Assumptions

- Claude API Key 已配置在环境变量
- ChromaDB和Redis连接正常
- 当前1201条记录的结构已知（可通过Redis hgetall验证）

---

## Outstanding Questions

### Resolve Before Planning

1. **[R1] 优先级权重**: CitationScore / OperatorScore / MissingFieldScore 的权重比例？建议 (0.4, 0.3, 0.3)
2. **[R2] 抽取批次大小**: 每次并行调用Claude的批次大小？建议 10条/批

### Deferred to Planning

3. **[R3] Webhook安全**: PR事件Webhook的验证机制？
4. **[R4] 报告格式**: 质量报告输出格式（Markdown/JSON/HTML）？

---

## Next Steps

→ `/ce:plan` for structured implementation planning

