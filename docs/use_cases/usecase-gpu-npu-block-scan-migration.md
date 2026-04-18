# Use Case: CUB BlockScan 迁移到 AscendC

> **测试日期**: 2026-04-18
> **测试方式**: 实际调用 LLM API，对比有/无知识库时的回答差异

## 场景描述

**任务**: 将 CUDA CUB `BlockScan` 迁移到昇腾 NPU

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

## 实际测试配置

### Prompt (无知识库)

```
你是一个AscendC算子开发专家。将以下CUDA代码迁移到昇腾NPU...

只基于你自己的知识回答，不要搜索。
```

### Prompt (有知识库)

```
**重要**: 根据知识库查询结果，这个操作有已知的AscendC映射:
- GPU API: cub::DeviceScan
- NPU API: aclnnAsynchronousCompleteCumsum (置信度: 0.95, exact级别)

请基于上述知识库信息给出回答。
```

---

## 知识库查询结果

| 字段 | 值 |
|------|-----|
| GPU API | `cub::DeviceScan` |
| NPU API | `aclnnAsynchronousCompleteCumsum` |
| 置信度 | **0.95** |
| 等价级别 | **exact** |

---

## 效果对比

| 维度 | 无 MCP (实测) | 有 MCP (实测) |
|------|---------------|---------------|
| API 推荐 | 需猜测 | `aclnnAsynchronousCompleteCumsum` |
| 置信度 | 低 (不确定) | **0.95 (exact)** |
| 等价级别 | 未知 | **exact** |
| 语义对应 | 可能不准确 | Inclusive Sum 完全对应 |

---

## 核心价值

1. **消除猜测**: `cub::DeviceScan` 是 CUB 库的核心原语，直接对应 `aclnnAsynchronousCompleteCumsum`
2. **提高置信度**: 0.95 置信度，exact 级别映射，Agent 可直接使用
3. **避免试错**: 无知识库时可能需要尝试多个 API 才能找到正确的 NPU 实现
