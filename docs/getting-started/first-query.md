# 首次查询

本文档提供更详细的使用示例，帮助你理解如何高效查询知识库。

---

## 1. 初始化知识库服务

### 基本初始化

```python
from asc_ops import KnowledgeQueryService

# 使用默认配置（ChromaDB嵌入式）
service = KnowledgeQueryService()
```

### 自定义配置初始化

```python
from asc_ops import KnowledgeQueryService, ChromaDBConfig, RedisConfig

# 自定义配置
service = KnowledgeQueryService(
    chromadb=ChromaDBConfig(
        path="./my_kb_data",
        collection_name="custom_collection"
    ),
    redis=RedisConfig(
        host="localhost",
        port=6379,
        db=0
    )
)
```

---

## 2. 开发参考查询

适用场景：Agent在开发新算子前，查询该算子的常见问题和优化经验。

### 2.1 查询特定算子的所有知识

```python
# 查询Matmul算子的bug和优化知识
result = await service.query_for_development(
    operator_name="Matmul",
    query_type="all"
)

print(f"=== Matmul算子知识 ===")
print(f"Bug修复: {len(result.bug_fixes)} 条")
print(f"优化方案: {len(result.optimizations)} 条")

for bug in result.bug_fixes:
    print(f"\n[Bug] {bug.bug_title}")
    print(f"  严重程度: {bug.severity}")
    print(f"  根因: {bug.root_cause}")
    print(f"  修复: {bug.fix_pattern}")
```

### 2.2 只查询Bug修复

```python
# 只查Bug，不查优化
result = await service.query_for_development(
    operator_name="Conv2d",
    query_type="bug"
)

for bug in result.bug_fixes:
    print(f"[{bug.severity}] {bug.bug_title}")
```

### 2.3 只查询优化方案

```python
# 只查优化
result = await service.query_for_development(
    operator_name="Matmul",
    query_type="optimization"
)

for opt in result.optimizations:
    print(f"[{opt.optimization_type}] {opt.opt_title}")
    if opt.improvement_ratio:
        print(f"  性能提升: {opt.improvement_ratio:.1%}")
```

### 2.4 按API过滤

```python
# 查询涉及特定API的算子知识
result = await service.query_for_development(
    operator_name="Matmul",
    api_filter=["Mmad", "TensorDesc"],  # 只返回使用这些API的知识
    query_type="all"
)
```

---

## 3. 问题排查查询

适用场景：Agent遇到昇腾算子bug需要定位根因和解决方案。

### 3.1 描述症状查询

```python
# 输入问题现象，搜索相似bug
result = await service.query_for_troubleshooting(
    symptom="Matmul算子在处理非对齐数据时crash",
    operator_name="Matmul"
)

for cause in result.possible_causes:
    print(f"\n=== 可能原因 (置信度: {cause.confidence:.0%}) ===")
    print(f"描述: {cause.description}")
    print(f"根因: {cause.root_cause}")
    print(f"触发条件: {cause.trigger_conditions}")
    print(f"修复建议: {cause.suggested_fix}")
```

### 3.2 提供错误信息

```python
# 提供错误信息辅助判断
result = await service.query_for_troubleshooting(
    symptom="推理结果错误",
    operator_name="LayerNorm",
    error_message="精度误差超过阈值",
    used_apis=["ReduceSum", "Div", "Mul"]
)
```

### 3.3 获取所有关联知识

```python
# 问题排查时同时获取相关算子知识和API信息
result = await service.query_for_troubleshooting(
    symptom="性能异常",
    operator_name="Attention",
    include_related=True,  # 包含关联知识
    include_api_details=True  # 包含API详情
)

print("=== 相关知识 ===")
for item in result.related_knowledge:
    print(f"  - [{item.type}] {item.title}")

print("=== 涉及API ===")
for api in result.related_apis:
    print(f"  - {api.canonical_name}: {api.description}")
```

---

## 4. API查询

适用场景：查询AscendC API的使用方法、参数说明、示例代码。

### 4.1 按API名称查询

```python
# 精确查询API
result = await service.query_api(
    api_name="VecReduceMax"
)

for api in result:
    print(f"=== {api.canonical_name} ===")
    print(f"签名: {api.full_signature}")
    print(f"描述: {api.description}")
    print(f"参数:")
    for param in api.parameters:
        print(f"  - {param.name}: {param.type} = {param.default}")
        print(f"    {param.description}")
```

### 4.2 按功能搜索API

```python
# 语义搜索：查找矩阵相关的所有API
result = await service.query_api(
    semantic_query="矩阵运算 乘法 计算",
    limit=10
)

for api in result:
    print(f"  - {api.canonical_name}")
```

### 4.3 按类别查询

```python
# 查询某个类别的所有API
result = await service.query_api(
    category="memory",
    subcategory="copy"
)

for api in result:
    print(f"  - {api.canonical_name}")
```

### 4.4 查询API使用示例

```python
# 获取API的使用案例
result = await service.query_api(
    api_name="DataCopy",
    include_examples=True
)

for api in result:
    print("=== 使用示例 ===")
    for example in api.usage_examples:
        print(f"场景: {example.scenario}")
        print(f"代码:\n{example.code}")
        print()
```

---

## 5. 知识库管理

### 5.1 查看知识库统计

```python
from asc_ops import KnowledgeStats

stats = await KnowledgeStats.get()

print("=== 知识库统计 ===")
print(f"API知识:      {stats.api_count:>6} 条")
print(f"算子知识:     {stats.operator_count:>6} 条")
print(f"  - Bug修复:  {stats.bug_fix_count:>6} 条")
print(f"  - 优化方案: {stats.optimization_count:>6} 条")
print(f"知识库容量:   {stats.storage_size_mb:.1f} MB")
```

### 5.2 知识质量查询

```python
# 查询高质量知识
high_quality = await service.query_high_quality(
    min_confidence=0.8,
    limit=20
)

for item in high_quality:
    print(f"[{item.confidence:.0%}] {item.title}")
```

### 5.3 知识来源追溯

```python
# 追溯特定知识的来源
source_info = await service追溯_source(
    knowledge_id="bug_ops_nn_abc123"
)

print(f"来源: {source_info.repo}")
print(f"PR: {source_info.pr_number}")
print(f"作者: {source_info.author}")
print(f"更新时间: {source_info.updated_at}")
```

---

## 6. 高级用法

### 6.1 批量查询

```python
# 一次查询多个算子
operators = ["Matmul", "Conv2d", "LayerNorm", "Attention"]

results = {}
for op in operators:
    results[op] = await service.query_for_development(
        operator_name=op,
        query_type="all"
    )

# 汇总结果
total_bugs = sum(len(r.bug_fixes) for r in results.values())
total_opts = sum(len(r.optimizations) for r in results.values())
print(f"共查询 {len(operators)} 个算子")
print(f"发现Bug: {total_bugs}, 优化: {total_opts}")
```

### 6.2 自定义排序

```python
# 按不同时效性权重排序
result = await service.query_for_development(
    operator_name="Matmul",
    ranking_strategy="recency_first",  # "relevance" | "recency" | "confidence"
    query_type="all"
)
```

### 6.3 结果过滤

```python
from asc_ops import BugSeverity

# 只返回严重问题
result = await service.query_for_development(
    operator_name="Matmul",
    severity_filter=[BugSeverity.CRITICAL, BugSeverity.MAJOR],
    query_type="bug"
)
```

---

## 下一步

- [API参考](../api/reference.md) - 完整接口定义
- [部署指南](../deployment/docker.md) - 生产环境部署
- [设计文档](../design/) - 架构设计详情
