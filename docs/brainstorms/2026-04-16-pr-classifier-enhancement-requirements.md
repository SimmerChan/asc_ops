---
date: 2026-04-16
topic: pr-classifier-enhancement
---

# PR 分类器增强

## Problem Frame

当前 PR 分类器仅依赖 `pr_title` + `pr_body`，使用固定权重关键词匹配，存在：
1. 中文分词粒度过粗（"精度修复"未识别"修复"）
2. 无负向关键词过滤（"新增"压制"修复"）
3. `commit_message` 未传入
4. 无 fallback 机制，歧义 case 全部误判

**目标**：充分利用 PR 信息，对 bugfix / optimization / feature / unknown 四类实现准确分类。

## Requirements

- R1. **规则层改进**
  - 改进中文分词器：先提取单字关键词（修复、断、错等），再进行2-4字符切分
  - 添加负向关键词集合：feature 类词（新增、实现、支持）压制 bugfix 信号时降低 bugfix 置信度
  - 启用 `commit_message` 参数参与计算

- R2. **LLM Fallback 机制**
  - 当规则层置信度 < 0.5 时，触发 LLM 分类
  - LLM 输入：pr_title + pr_body + diff 摘要（前 500 字符）
  - 使用现有 `UnlimitedLLMClient`
  - 分类结果缓存到 Redis（key: `pr:classifier:{pr_id}`），有效期 7 天

- R3. **LLM 分类 Prompt 设计**
  - 支持中文输入输出
  - 返回结构化结果：{type: bugfix|optimization|feature|unknown, confidence: 0.0-1.0, reason: string}
  - 优先判断是否含 bug 修复（代码错误、异常行为），次级判断优化/新功能

- R4. **分类器集成**
  - `BugExtractor` 和 `OptimizationExtractor` 透明使用增强后的分类器
  - 分类结果记录到 extraction metadata（用于后续分析）

## Success Criteria

- BugFix 准召率：precision > 90%, recall > 80%（对比人工标注样本）
- Optimization/FEATURE 误判率降低 50%
- LLM 调用率控制在总处理量的 20-30% 以内
- 分类延迟：规则层 < 10ms，LLM fallback < 2s

## Scope Boundaries

**在范围内：**
- 规则层分词和关键词改进
- LLM fallback 机制
- 分类结果 Redis 缓存
- 集成到现有 Extractor

**不在范围内：**
- 独立部署分类服务
- 模型训练 / Fine-tuning
- 多语言支持（非中文 PR）

## Key Decisions

- **混合架构**：规则层处理 70-80% 高置信度 case，LLM 处理 20-30% 歧义 case
- **缓存策略**：Redis 缓存 LLM 结果 7 天，避免重复调用相同 PR
- **Diff 摘要**：LLM 输入包含 diff 前 500 字符，平衡信息量和 token 成本

## Dependencies / Assumptions

- 依赖 `UnifiedLLMClient`（已存在）
- 依赖 Redis（已存在）
- 需要人工标注样本集用于评估（50-100 条）

## Outstanding Questions

### Deferred to Planning
- **[Technical]** LLM prompt 的具体措辞和 few-shot examples 设计 ✅ 已完成
  - 系统提示词定义 4 种类型及判断标准
  - 用户输入格式：title + body + diff_summary (500字)
  - Few-shot examples: bugfix/optimization/feature/unknown 各类型示例
- **[Technical]** diff 摘要提取逻辑（取前 N 字符 vs 取特定文件）
- **[Needs validation]** 0.5 阈值是否合适，需在标注集上验证

## Next Steps

→ `/ce:plan` for structured implementation planning
