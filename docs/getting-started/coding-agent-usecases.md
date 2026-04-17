# Coding Agent 使用案例

本文档展示 Coding Agent 如何使用 AscendC 算子知识库进行算子开发和调试。

---

## 场景一：开发新 Matmul 算子

**背景**: Agent 需要为昇腾 NPU 开发一个新的 Matmul 算子，希望在开发前了解常见问题和最佳实践。

### Agent 执行流程

```python
# 1. 开发前：查询该算子的历史问题和优化经验
result = await service.query_for_development(
    operator_name="Matmul",
    query_type="all",      # 查询 bug 和优化知识
    min_confidence=0.6,    # 只看高置信度知识
    limit=10
)

print(f"共找到 {result.total_count} 条知识")
for bug in result.bug_fixes:
    print(f"[Bug] {bug.bug_title}")
    print(f"  严重程度: {bug.severity.value}")
    print(f"  触发条件: {bug.trigger_conditions}")
    print(f"  修复方案: {bug.fix_pattern}")
```

**Agent 思考输出**:

```
在开发 Matmul 算子前，我需要了解历史踩坑经验：

发现 3 个高置信度 Bug:
1. [CRITICAL] 矩阵维度不是 16 的倍数导致 tile 边界问题
   - 触发条件: 输入 M/N/K 不是 16 的倍数
   - 修复: 填充 + mask 方案

2. [MAJOR] 非对齐地址访问导致地址越界
   - 触发条件: 数据起始地址 % 32 != 0
   - 修复: 使用 VecCopy 替代 DataCopy

3. [MINOR] stride 与描述符不匹配导致精度问题
   - 触发条件: transposed 矩阵输入
   - 修复: 检查 stride 的一致性

发现 2 个优化经验:
1. [性能] 分块 tiling 策略，提升 40% 性能
2. [内存] 原地操作优化，节省 30% 内存
```

---

## 场景二：排查 Matmul 算子 crash

**背景**: 部署的 Matmul 算子在处理特定输入时 crash，Agent 需要定位问题。

### Agent 执行流程

```python
# 1. 描述症状，搜索可能原因
result = await service.query_for_troubleshooting(
    symptom="Matmul算子在处理非对齐数据时crash",
    operator_name="Matmul",
    error_message="address error - out of bounds",
    used_apis=["DataCopy", "Mmad"],
    limit=5
)

print(f"找到 {len(result.possible_causes)} 个可能原因")
for cause in result.possible_causes:
    print(f"\n=== 原因 (置信度: {cause.confidence:.0%}) ===")
    print(f"根因: {cause.root_cause}")
    print(f"触发条件: {cause.trigger_conditions}")
    print(f"建议修复: {cause.suggested_fix}")
    print(f"建议检查: {cause.suggested_checks}")
```

**Agent 思考输出**:

```
根据错误 "address error - out of bounds" 和症状描述，
知识库匹配到以下可能原因：

可能原因 1 (置信度 85%):
- 根因: 非对齐地址访问导致地址越界
- 触发条件: 数据起始地址 % 32 != 0
- 建议修复: 使用 VecCopy 替代 DataCopy 进行非对齐数据搬移
- 建议检查:
  1. 检查输入数据的内存地址对齐情况
  2. 检查 DataCopy 的 dst/src 地址是否满足 32 字节对齐

可能原因 2 (置信度 72%):
- 根因: 矩阵维度不是 16 的倍数导致 tile 边界越界
- 触发条件: M/N/K 不是 16 的倍数
- 建议修复: 填充输入矩阵到 16 的倍数，并用 mask 处理有效区域
- 建议检查: 检查输入矩阵的 shape 是否满足 16 对齐
```

---

## 场景三：GPU CUDA 算子迁移到 NPU

**背景**: Agent 需要将一个 CUDA GEMM 算子迁移到昇腾 NPU，需要找到等效的 AscendC API。

### Agent 执行流程

```python
# 1. 查询 GPU API 的 NPU 等效映射
result = await service.query_cross_platform(
    gpu_api="__sync_threads",
    gpu_platform="cuda"
)

print(f"NPU 等效 API: {result.npu_api}")
print(f"等价级别: {result.equivalence_level.value}")
print(f"适配注意: {result.adaptation_notes}")

# 2. 批量查询多个 GPU API
gpu_apis = [
    ("wmma::load_matrix_sync", "cuda"),
    ("wmma::store_matrix_sync", "cuda"),
    ("__shfl_xor_sync", "cuda"),
]

for gpu_api, platform in gpu_apis:
    result = await service.query_cross_platform(gpu_api, platform)
    print(f"{gpu_api} -> {result.npu_api if result else '未找到'}")
```

**Agent 思考输出**:

```
GPU -> NPU 跨平台映射查询结果：

__sync_threads -> gm_sync
  等价级别: 功能等价
  适配注意: NPU 使用 gm_sync 进行全局内存同步，需在 block 内所有线程调用

wmma::load_matrix_sync -> mmad::load_matrix_a/b
  等价级别: 部分等价
  适配注意: NPU 的 mmad API 仅支持 16x16x16 tile 块，
           需将 CUDA 的 16x16 tile 映射到 NPU 的 16x16x16

__shfl_xor_sync -> ai_core::shuffle_xor
  等价级别: 功能等价
  适配注意: NPU 使用 warp-level shuffle 替代 thread-level，
           需要确保线程在同一个 warp 内
```

---

## 场景四：查询特定 API 用法

**背景**: Agent 需要了解某个 AscendC API 的具体用法和参数说明。

### Agent 执行流程

```python
# 1. 查询 API 定义和签名
apis = await service.query_api(
    api_name="VecMatmul",
    include_examples=True
)

for api in apis:
    print(f"=== {api.canonical_name} ===")
    print(f"签名: {api.full_signature}")
    print(f"描述: {api.description}")
    print(f"参数:")
    for param in api.parameters:
        required = "(必填)" if param.required else "(可选)"
        print(f"  - {param.name}: {param.type} {required}")
        print(f"    {param.description}")

    if api.usage_examples:
        print("使用示例:")
        for ex in api.usage_examples:
            print(f"\n场景: {ex.scenario}")
            print(f"代码:\n{ex.code}")
```

---

## 场景五：批量开发多个相关算子

**背景**: Agent 需要开发一整套 Vision Transformer 相关的算子（Attention、LayerNorm、Softmax 等）。

### Agent 执行流程

```python
# 1. 定义需要开发的算子列表
operators = ["Attention", "LayerNorm", "Softmax", "Gelu", "Transpose"]

# 2. 批量查询每个算子的知识
results = {}
for op in operators:
    results[op] = await service.query_for_development(
        operator_name=op,
        query_type="all",
        min_confidence=0.5,
        limit=5
    )

# 3. 汇总输出
print("=== Vision Transformer 算子开发参考 ===\n")
for op, result in results.items():
    print(f"\n## {op}")
    print(f"Bug: {len(result.bug_fixes)} 条, 优化: {len(result.optimizations)} 条")

    if result.bug_fixes:
        critical = [b for b in result.bug_fixes if b.severity.value == "CRITICAL"]
        if critical:
            print(f"  严重问题: {len(critical)} 个")

    if result.optimizations:
        best = max(result.optimizations, key=lambda x: x.improvement_ratio or 0)
        if best.improvement_ratio:
            print(f"  最高优化: {best.improvement_ratio:.0%} 性能提升")
```

---

## 场景六：通过 MCP 协议集成

**背景**: 在 Claude Code 中直接调用知识库工具。

### Claude Code 配置

在 `settings.json` 中配置 MCP 服务器：

```json
{
  "mcpServers": {
    "asc-ops": {
      "command": "python",
      "args": ["-m", "asc_ops.mcp.cli"],
      "env": {
        "ASC_OPS_CHROMA_PATH": "./data/chroma_db",
        "ASC_OPS_REDIS_HOST": "localhost"
      }
    }
  }
}
```

### Claude Code 对话示例

```
用户: 我需要开发一个新的 Conv2d 算子，有什么需要注意的吗？

Agent: (调用 query_for_development 工具)

根据知识库，历史 Conv2d 算子的常见问题包括：

1. [CRITICAL] 步长不为 1 时的工作区计算错误
   - 根因: Conv2d stride>1 时需要更大的工作区
   - 修复: pre_allocate 工作区，参考 ops-nn PR#456

2. [MAJOR] group>1 时 channel 分组边界问题
   - 触发条件: depthwise conv 使用 group=channels
   - 修复: 分组检查 + 边界 mask

3. [优化] Im2Col + GEMM 融合策略
   - 效果: 40% 性能提升

需要我进一步查询某个具体方面的详细信息吗？
```

---

## MCP 工具清单

| 工具名称 | 用途 | 主要参数 |
|---------|------|---------|
| `query_for_development` | 开发前查询 bug 和优化知识 | `operator_name`, `query_type`, `min_confidence` |
| `query_for_troubleshooting` | 问题排查 | `symptom`, `operator_name`, `error_message` |
| `query_api` | 查询 AscendC API | `api_name`, `semantic_query`, `category` |
| `query_cross_platform` | GPU→NPU 映射 | `gpu_api`, `gpu_platform` |

---

## 最佳实践

### 1. 开发前必查
在开始新算子开发前，务必调用 `query_for_development` 获取历史踩坑经验。

### 2. 问题排查优先描述症状
使用 `query_for_troubleshooting` 时，尽量描述清晰的问题现象，而非直接猜测根因。

### 3. 结合 API 查询
开发或调试时，可同时查询相关 API 的用法示例。

### 4. 关注置信度
返回结果按置信度排序，低置信度知识需人工验证。

---

## 下一步

- [首次查询详解](first-query.md) - 更多查询示例
- [API参考](../api/reference.md) - 完整接口文档
- [MCP集成](../deployment/docker.md) - MCP 服务器部署
