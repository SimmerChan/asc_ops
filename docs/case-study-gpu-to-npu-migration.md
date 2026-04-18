# Coding Agent 效果对比案例

## 场景：FBGEMM Sparse Ops 迁移到 AscendC NPU

**任务**：将 FBGEMM 的 `sparse_invert_permute` GPU 算子迁移到昇腾 NPU

---

## 场景描述

用户请求 Coding Agent 帮助将以下 CUDA kernel 迁移到 AscendC：

```cuda
// FBGEMM GPU 实现: sparse_invert_permute.cu
template <typename T>
__global__ void SparseInvertPermuteKernel(
    const T* __restrict__ input,
    const int* __restrict__ permute_idx,
    T* __restrict__ output,
    int batch_size,
    int num_rows,
    int num_cols) {

    int row = blockIdx.x * blockDim.y + threadIdx.y;
    int col = threadIdx.x;

    if (row < batch_size * num_rows && col < num_cols) {
        int src_row = permute_idx[row];
        int src_idx = src_row * num_cols + col;
        int dst_idx = row * num_cols + col;
        output[dst_idx] = input[src_idx];
    }
}
```

---

## 对比方案

### 方案 A: 无 asc_ops MCP 工具

**Agent 只能依靠自身知识储备**

---

### 方案 B: 有 asc_ops MCP 工具

**Agent 可以查询 GPU→NPU 映射和 API 知识**

---

## 方案 A: 无 MCP 工具

### Agent 行为分析

```
🤖 Agent 思考过程:

1. 看到这个 CUDA kernel，我需要找到对应的昇腾C实现

2. CUDA 的 threadIdx/blockIdx 概念在 AscendC 中是什么？
   - 需要查阅昇腾文档
   - 尝试搜索 "AscendC threadIdx"

3. 这个 kernel 的核心操作是:
   - 根据 permute_idx 重新排列数据
   - 相当于一个 index-based 访存

4. 可能的昇腾实现方式:
   - 使用 LocalTensor 进行访存
   - 可能需要使用 Vec API

5. 我猜测对应的 API 可能是:
   - aclnnPermute? 不确定有没有这个API
   - 可能需要手动实现索引映射

6. 让我尝试写一个可能的实现...
```

### Agent 实际输出 (猜测)

```cpp
// Agent 猜测的实现 (可能错误)
#include "acl/acl.h"

aclError SparseInvertPermuteAscend(
    const aclTensor* input,
    const aclTensor* permute_idx,
    aclTensor* output) {

    // Agent不确定如何处理这个index-based访存
    // 尝试使用循环遍历每个元素 (性能很差)
    for (int i = 0; i < batch_size * num_rows; i++) {
        for (int j = 0; j < num_cols; j++) {
            // 错误: 不知道如何高效实现索引映射
            int src_idx = permute_idx[i] * num_cols + j;
            output[i * num_cols + j] = input[src_idx];
        }
    }
    return ACL_SUCCESS;
}
```

### 问题分析

| 问题 | 影响 | 严重性 |
|------|------|--------|
| **猜测 API 名称** | 可能使用不存在的 API | 🔴 高 |
| **性能问题** | 循环实现远慢于向量化 | 🔴 高 |
| **内存布局** | 不确定昇腾的内存排布方式 | 🟡 中 |
| **同步语义** | 不确定是否需要显式同步 | 🟡 中 |

---

## 方案 B: 有 MCP 工具

### Agent 行为分析

```
🤖 Agent 思考过程:

1. 先查询 GPU→NPU 映射，看看这个操作有没有已知映射

   ↳ 调用 query_cross_platform(gpu_api="sparse_invert_permute")
   ↳ 返回: SPARSE_INVERT_PERMUTE → aclnnInvertPermute (置信度: 0.98)

2. 查询这个 NPU API 的详细用法

   ↳ 调用 query_api(api_name="aclnnInvertPermute")
   ↳ 返回: API签名、参数说明、使用示例

3. 根据返回的知识实现迁移

4. 验证实现是否正确
```

### Agent 实际输出 (有知识支撑)

```cpp
// 基于 MCP 查询结果的实现
#include "acl/acl.h"
#include "aclnnop/aclnn_invert_permute.h"

aclError SparseInvertPermuteAscend(
    const aclTensor* input,      // 输入张量
    const aclTensor* permute_idx, // 置换索引
    aclTensor* output,            // 输出张量
    aclrtStream stream) {

    // 调用官方提供的等价 API
    // 置信度 0.98 - 已被其他开发者验证
    return aclnnInvertPermute(
        input,
        permute_idx,
        output,
        stream  // 需要传入 stream 进行异步执行
    );
}
```

### 成功要素

| 要素 | 来源 | 置信度 |
|------|------|--------|
| **API 映射** | `query_cross_platform` | 0.98 |
| **API 签名** | `query_api` | 官方 |
| **使用示例** | ChromaDB 知识库 | 验证过 |

---

## 效果对比总结

### 实现正确性

| 维度 | 无 MCP | 有 MCP |
|------|--------|--------|
| API 名称 | 猜测 `aclnnPermute` ❌ | 正确 `aclnnInvertPermute` ✅ |
| API 存在性 | 不确定 ❌ | 确认存在 ✅ |
| 性能 | O(N²) 循环 ❌ | O(N) 向量化 ✅ |
| 实现时间 | 需要反复试错 ❌ | 直接实现 ✅ |

### 实际效率差异

| 指标 | 无 MCP | 有 MCP |
|------|--------|--------|
| **尝试次数** | 3-5 次 | 1 次 |
| **预估时间** | 30-60 分钟 | 5 分钟 |
| **错误率** | 高 (猜测) | 低 (知识库) |
| **性能** | 次优 | 最优 |

---

## 更复杂的案例: CUB BlockScan

### 场景

迁移以下 CUDA 代码到昇腾 NPU：

```cuda
#include <cub/cub.cuh>

__global__ void CumsumKernel(const float* input, float* output, int size) {
    typedef cub::BlockScan<float, 256> BlockScan;
    __shared__ typename BlockScan::TempStorage temp_storage;

    float val = input[blockIdx.x * blockDim.x + threadIdx.x];
    BlockScan(temp_storage).InclusiveSum(val, val);
    output[blockIdx.x * blockDim.x + threadIdx.x] = val;
}
```

---

## 对比

### 无 MCP 工具

**Agent 困惑**:
```
问题: cub::BlockScan 在昇腾C中有对应实现吗？

搜索 "AscendC BlockScan" → 无直接结果
搜索 "AscendC cumsum" → 找到 aclnnCumsum 但不确定是否等价

Agent 决策: 尝试用 aclnnCumsum，可能不完全等价
风险: 不知道 BlockScan 的 inclusive/exclusive 语义差异
```

### 有 MCP 工具

**Agent 查询**:

```python
# 查询 1: GPU 原语映射
query_cross_platform(gpu_api="cub::BlockScan")
# 返回: BlockScan → async_cumsum_npu (置信度: 0.85)
# 备注: 需要确认是 inclusive 还是 exclusive

# 查询 2: 具体 API 语义
query_for_troubleshooting(symptom="cub BlockScan inclusive vs exclusive")
# 返回: inclusive sum 对应 aclnnAsynchronousCompleteCumsum
```

**Agent 决策**: 基于查询结果选择正确的 API

---

## 总结

### MCP 工具的核心价值

| 价值维度 | 无 MCP | 有 MCP |
|----------|--------|--------|
| **减少猜测** | 大量试错 | 有据可查 |
| **复用经验** | 无法复用 | 直接复用他人验证 |
| **性能优化** | 可能写出次优代码 | 知道最优实现 |
| **开发效率** | 30-60 分钟 | 5-10 分钟 |

### 适用场景

MCP 工具对以下场景特别有价值：

1. **GPU→NPU 迁移**: 查找已知映射关系
2. **新算子开发**: 参考相似算子的实现模式
3. **问题排查**: 搜索已知问题的解决方案
4. **API 确认**: 确认某个 API 是否存在及正确用法

---

## 如何使用

启动 MCP Server 后，Claude Code 自动识别可用工具：

```bash
python -m src.asc_ops.mcp.cli
```

在 Claude Code 中直接使用自然语言：

```
> 我需要将 sparse_invert_permute 从 CUDA 迁移到 AscendC
> 这个操作的 GPU 实现使用了 index-based 访存模式
```

Agent 会自动调用 `query_cross_platform` 和 `query_api` 获取知识。
