---
date: 2026-04-10
topic: ascendc-api-collection-stability
---

# AscendC API采集稳定性需求

## Problem Frame

当前设计的API采集方案（两阶段采集：链接发现→详情提取）存在严重的稳定性问题。1786个API详情页的批量采集过程中，任何网络抖动、限流、解析失败都会导致数据丢失或采集中断。需要确保采集过程的**可靠性**、**容错性**和**可持续性**。

## Requirements

### R1. 错误重试与指数退避

当HTTP请求失败时，自动重试并采用指数退避策略：

| 错误类型 | 重试次数 | 退避策略 |
|----------|----------|----------|
| Timeout (5s) | 3次 | 1s → 2s → 4s |
| RateLimit (429) | 5次 | 10s → 20s → 40s → 80s → 160s |
| ServerError (5xx) | 3次 | 2s → 4s → 8s |

**关键要求：**
- RateLimit触发时必须完整执行退避周期，不能跳过
- 连续触发RateLimit超过阈值（如3次），发送告警通知管理员
- 重试期间其他API采集不受影响（并行处理）

### R2. 解析容错与自动降级

解析失败时采用**自动降级策略**，保证核心数据不丢失：

```
解析流程：
原始HTML → 完整解析器 → 结构化数据
                ↓ 解析成功
              存储到Redis
                ↓ 解析失败
         自动降级解析器
                ↓
    只提取: api_id, name, url, category
    + 原始HTML存入"raw_html:{api_id}"
    + 标记api_status = "parse_incomplete"
    + 记录解析异常到"parse_errors:{api_id}"
```

**降级解析器只提取：**
- API名称（从页面标题）
- API URL
- 面包屑分类（最粗粒度的一级分类）
- 更新时间（如果能提取）

**完整解析失败的触发条件：**
- 找不到函数原型section
- 参数表格解析失败（表格结构不匹配）
- 抛出未捕获异常

### R3. 自适应请求限速

根据服务器响应时间动态调整请求间隔：

```
初始间隔: 0.5秒
响应时间 > 2000ms → 间隔 = min(间隔 × 1.2, 10s)  // 减速
响应时间 < 300ms → 间隔 = max(间隔 × 0.9, 0.1s)   // 加速
响应时间正常 → 间隔不变

触发429 RateLimit → 立即暂停，间隔 × 3，等待完整退避周期后重试
```

**限速参数可配置：**
- `initial_interval`: 初始间隔（默认0.5s）
- `min_interval`: 最小间隔（默认0.1s）
- `max_interval`: 最大间隔（默认10s）
- `rate_limit_backoff_multiplier`: 退避乘数（默认3x）

### R4. 并发控制

限制同时进行的HTTP连接数，避免耗尽资源或触发服务器限流：

```
最大并发数: 10个连接（可配置）
超过并发限制的任务进入等待队列
等待队列可以堆积1000个任务
队列满时记录日志，暂停新任务加入
```

**并发控制策略：**
- 使用asyncio.Semaphore控制并发
- 每个并发slot独立处理一个API
- slot完成后自动调度下一个任务

### R5. 断点续采

记录采集进度，支持中断后从断点恢复：

```
Redis存储:
  progress:api_collection = {
    total: 1786,
    completed: [api_id, api_id, ...],
    failed: [{api_id, error, attempts}, ...],
    last_batch_id: 35,
    started_at: timestamp,
    updated_at: timestamp
  }

恢复逻辑:
  1. 读取progress记录
  2. 从last_batch_id + 1继续
  3. 跳过completed中的api_id
  4. 重试failed中的api_id（最多3次）
```

**断点记录时机：**
- 每完成一个API详情提取
- 每完成一个批次（50个）
- 每分钟定期保存checkpoint

### R6. 采集状态监控

实时监控采集过程，异常时及时告警：

```
监控指标:
- 每分钟采集速率 (apis/min)
- 成功率 (completed / total)
- 失败率按错误类型分布
- 当前队列深度
- 并发连接数

告警触发条件:
- 成功率 < 95% 持续5分钟
- 连续3次RateLimit触发
- 队列堆积超过500
- 采集速率 < 5 apis/min 持续10分钟
```

## Success Criteria

1. **可靠性**: 1786个API的完整采集成功率 ≥ 99%（允许1%因文档本身问题失败）
2. **容错性**: 单次网络抖动不导致数据丢失，自动重试恢复
3. **可持续性**: 不会被服务器限流封禁，长期稳定运行
4. **可观测性**: 实时掌握采集进度、成功率、失败原因
5. **可恢复性**: 中断后能准确从断点恢复，不重复采集已成功的API

## Scope Boundaries

**在范围内：**
- 采集稳定性增强
- 监控与告警
- 断点续采

**不在范围内：**
- 解析器的具体实现（属于Planning阶段）
- 采集任务的调度UI
- 告警的接收渠道配置（钉钉/飞书等）
- 采集数据的后续处理

## Key Decisions

- **D1. 自动降级优于保留原始HTML**: 简化处理逻辑，确保核心数据可用；完整原始数据可后续补充采集
- **D2. 并发控制而非串行**: 平衡采集速度与稳定性，10并发是经验值
- **D3. 指数退避而非固定间隔**: 更好地适配不同服务器的限流策略

## Dependencies / Assumptions

- Redis可用（用于进度记录、限速状态）
- 网络环境稳定（允许抖动但不允许完全不可达）
- 昇腾文档结构在单个版本周期内稳定

## Outstanding Questions

### Resolve Before Planning
- **Q1**: 1786个API如果按10并发、0.5s间隔，需要多长时间？
  - 计算: 1786 / 10 = 179批 × (0.5s + 解析时间约1s) ≈ 4.5分钟不含解析
  - **需要确认**: 实际解析时间估计？

### Deferred to Planning
- **Q2**: [Technical] 解析器的具体实现细节（SectionParser的HTML选择器、表格解析逻辑）
- **Q3**: [Technical] 监控告警的具体实现（用什么存储监控数据？Prometheus? Redis?）
- **Q4**: [Needs research] 昇腾文档是否有访问频率限制？如有，单IP限制是多少？

---

## Embedding Design Requirements

### Problem Frame

API知识的语义检索依赖Embedding向量。当前设计缺失：
1. Embedding什么内容？
2. 使用什么模型？
3. 何时生成向量？
4. 如何用于检索？

### Requirements

#### R10. Embedding内容策略

**完整描述embedding**：
- 函数签名（完整的C++模板声明）
- 功能描述（中英文）
- 参数类型列表
- 返回值类型
- 使用约束

```
示例 - Exp API的embedding内容：
"""
API: Exp
功能: 按元素取自然指数
签名: template <typename T, const ExpConfig& config = DEFAULT_EXP_CONFIG>
      __aicore__ inline void Exp(const LocalTensor<T>& dst,
                                 const LocalTensor<T>& src,
                                 const int32_t& count)
参数: T(数据类型), dst(输出), src(输入), count(元素个数)
约束: LocalTensor起始地址需32字节对齐
"""
```

#### R11. Embedding模型

**使用Qwen3-Embedding-4B**（用户指定）：
- 本地部署，避免API调用费用
- 预估输出维度：1024维或1536维
- 需要确认具体模型变体的输出维度

#### R12. 异步批量生成

```
生成策略：
采集时 → 只存储原始文本 → 标记embedding_status="pending"
异步任务 → 批量调用embedding模型 → 更新向量 → 标记"ready"
```

**批量生成参数**：
- 批大小: 100个API/批
- 生成间隔: 每小时触发
- 或支持手动触发全量重生成

#### R13. 意图路由检索

根据查询类型自动选择匹配策略：

```
查询类型识别 → 匹配策略 → 结果融合

策略路由：
├─ "Exp是什么" / "Exp怎么用" → 向量检索（语义相似）
├─ "Exp的参数是什么" → 关键词精确匹配
├─ "类似xxx的API" → 向量检索（跨类别）
└─ "数据类型转换的API" → 分类过滤 + 向量检索
```

**结果融合**：
- 向量相似度 × 0.6
- BM25关键词得分 × 0.3
- 权威性/使用频率 × 0.1

## Incremental Sync Requirements

### Problem Frame

当前增量同步方案依赖"列表页ETag变化"来判断是否有API更新。但昇腾更新单个API详情页时，列表页ETag通常不变，导致增量更新失效。

### Requirements

#### R15. 手动触发同步

采用**人工手动触发**策略，通过CLI命令触发：

```bash
# 触发API知识同步
python -m ascend_kb sync --api

# 触发算子知识同步
python -m ascend_kb sync --operator

# 触发全量同步（所有知识库）
python -m ascend_kb sync --all

# 查看同步状态
python -m ascend_kb sync --status
```

**触发流程：**
1. 管理员手动运行CLI命令
2. 重新发现API链接（检测新增API）
3. 比对已有数据，发现变更
4. 执行增量更新

#### R16. 同步状态跟踪

```bash
# 同步状态存储在Redis
sync:status = {
  last_sync: timestamp,
  synced_apis: [api_id, ...],
  new_apis: [api_id, ...],
  changed_apis: [{api_id, change_type}, ...],
  deleted_apis: [api_id, ...]
}
```

### Key Decisions (Incremental Sync)

- **D13. 同步触发**: 人工手动触发（简化，不依赖自动检测）
- **D14. CLI接口**: `python -m ascend_kb sync --api`
- **D15. 状态跟踪**: Redis记录同步状态，支持查看

---

#### R14. 向量存储规格

| 参数 | 值 |
|------|-----|
| 模型 | Qwen3-Embedding-4B |
| 预估维度 | 1024维 / 1536维 |
| 1786个API存储 | ~7MB / ~11MB (Float32) |
| ChromaDB索引开销 | 极低（嵌入式） |

## Key Decisions (Embedding)

- **D8. Embedding内容**: 完整描述（签名+描述+参数+约束）
- **D9. Embedding模型**: Qwen3-Embedding-4B（本地部署）
- **D10. 生成时机**: 异步批量生成（采集时只存文本）
- **D11. 查询策略**: 意图路由（向量+关键词+权威性融合）
- **D12. 向量维度**: 待确认Qwen3-Embedding-4B具体变体

---

## Tri-Relation Integration Requirements

### Problem Frame

算子知识(OperatorKB)、API知识(APIKB)、GPU知识(GPUKB)三大知识库当前是割裂的。需要建立关联，使Agent能够：
1. 查到"某算子用了哪些API"
2. 查到"某API被哪些算子使用"
3. 跨平台参考GPU实现

### Requirements

#### R7. 算子→API关联（优先级1）

通过**代码静态分析**从算子代码中抽取API调用关系：

```
抽取流程：
算子代码 → AST解析 → 识别API调用 → 关联记录

关联记录格式：
{
  "usage_id": "matmul_mmad_001",
  "operator_id": "matmul",
  "api_id": "Mmad",
  "code_location": "kernel_ops/matmul.cpp:56",
  "call_context": "矩阵乘法核心计算",
  "confidence": 0.95
}
```

**关联来源：**
- 主要：代码静态分析（识别AscendC API调用）
- 次要：算子仓的README/注释（作为补充）

**更新机制：**
- 新PR合并时自动触发关联更新
- 每日全量扫描

#### R8. GPU→NPU API映射（优先级2）

通过**自动推断**建立CUDA→AscendC的API映射：

```
推断方法：
1. 分析FBGEMM仓中同一算子的GPU实现 vs NPU实现
2. 识别API对应关系（如wmma::mma_sync → Mmad）
3. 记录映射置信度

映射记录格式：
{
  "mapping_id": "wmma_mmad_001",
  "gpu_api": "wmma::mma_sync",
  "npu_api": "Mmad",
  "equivalence": "功能等价",
  "parameter_mapping": {...},
  "confidence": 0.92
}
```

**自动推断的局限性：**
- 只能推断功能明显对应的API
- 需要人工验证和校正
- 复杂映射需手动补充

#### R9. 跨库联合查询（优先级3）

采用**查询路由**方案，不引入图数据库：

```
查询路由设计：

Agent查询 → 意图识别 → 路由到对应知识库 → 合并返回

意图类型：
├─ "某API怎么用" → APIKB
├─ "某算子用了哪些API" → APIKB + 关联索引
├─ "实现某算子需要什么" → 算子KB + APIKB + API映射
└─ "GPU的X对应NPU什么" → GPUKB + API映射
```

**查询合并策略：**
- 各库独立查询
- 按关联权重排序
- 返回格式统一

## Key Decisions (Tri-Relation)

- **D4. 算子→API关联来源**: 代码静态分析为主，文档为辅
- **D5. GPU→NPU映射**: 自动推断，但需人工验证
- **D6. 跨库查询方案**: 查询路由，不引入图数据库
- **D7. 优先级**: 算子→API (P1) → GPU→NPU映射 (P2) → 跨库查询 (P3)

## Next Steps

→ `/ce:plan` for structured implementation planning
