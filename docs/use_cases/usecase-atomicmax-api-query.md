# Use Case: AscendC AtomicMax API 查询

> **测试日期**: 2026-04-19
> **测试方式**: 知识库实测 + Claude Code 对话模拟

## 场景描述

**任务**: 用户在开发 GPU 到 NPU 迁移代码时，询问 AscendC 是否有与 GPU `AtomicMax` 等价的接口

---

## 实测问题

```
用户提问: AscendC 有不有和GPU等价的AtomicMax接口?
```

---

## 无知识库时的回答（Claude Code 模拟 LLM）

```
关于 AscendC 的原子操作，我了解的情况如下：

AscendC 主要提供以下原子操作：
- 原子加 (AtomicAdd): 用于实现计数、累加等操作
- 原子交换 (AtomicExch): 用于实现锁等同步机制
- 原子比较交换 (AtomicCAS): 用于实现更复杂的原子操作

对于 AtomicMax（原子取最大值）操作，AscendC 的支持情况：
- 在 SIMT（单指令多线程）编程模型中，可能需要通过 AtomicCAS 来实现
- 在 Vector 计算中，可能需要查看具体的产品规格

AscendC 的原子操作主要通过 GM（Global Memory）的原子写来实现，
具体接口形式可能是：
- __genius_atomic_add()
- __genius_atomic_max()

建议查阅华为昇腾官方 CANN 文档获取最新支持情况。
```

### 问题分析

| 问题 | 说明 |
|-----|------|
| ❌ API 名称臆造 | `__genius_atomic_max` 不是真实的 AscendC API |
| ⚠️ 不确定 | 无法确认 `asc_atomic_max` 是否存在 |
| ⚠️ 建议查文档 | 无法直接给出准确答案 |
| ❌ 产品支持矩阵缺失 | 无法区分不同 Atlas 型号的支持情况 |

---

## 有知识库时的回答（ChromaDB 实测）

### 知识库查询结果

```python
# 查询 1: asc_atomic_max
results = await service.query_api(api_name='asc_atomic_max')
# 返回: asc_atomic_max (util/) - Atlas 350 ✓, A3 ✓, A2 ✗

# 查询 2: AtomicMax
results = await service.query_api(api_name='AtomicMax')
# 返回: AtomicMax (util/ISASI), SetAtomicMax (util/ISASI)

# 查询 3: asc_set_atomic_max
results = await service.query_api(api_name='asc_set_atomic_max')
# 返回: asc_set_atomic_max_bfloat/float/float16/int (C API/simd_atomic)
```

### 精确回答

```
AscendC **有** 与 GPU AtomicMax 等价的接口。

**SIMT API (util/ 分类)**:
| API | Atlas 350 | Atlas A3 | Atlas A2 |
|-----|-----------|----------|----------|
| `asc_atomic_max` | ✓ | ✓ | ✗ |
| `AtomicMax` (ISASI) | ✓ | ✗ | ✗ |
| `SetAtomicMax` (ISASI) | ✓ | ✓ | ✓ |

**C API (simd_atomic 分类)**:
| API | 支持类型 |
|-----|---------|
| `asc_set_atomic_max_bfloat` | bfloat16 |
| `asc_set_atomic_max_float` | float32 |
| `asc_set_atomic_max_float16` | float16 |
| `asc_set_atomic_max_int` | int32 |
```

---

## 效果对比

| 维度 | 无知识库 (Claude Code 模拟) | 有知识库 (实测) |
|------|---------------------------|----------------|
| API 名称准确性 | ❌ 臆造 `__genius_atomic_max` | ✅ 精确 `asc_atomic_max` / `AtomicMax` |
| API 分类 | ❌ 未区分 | ✅ SIMT API vs C API |
| 产品支持矩阵 | ❌ 无法提供 | ✅ Atlas 350/A3/A2 详细支持情况 |
| 数据类型 | ❌ 遗漏 | ✅ bfloat/float/float16/int 完整覆盖 |
| 来源依据 | ⚠️ 推测，有幻觉风险 | ✅ 昇腾官方文档 |
| 直接可用性 | ⚠️ 需查阅文档 | ✅ 直接给出准确答案 |

---

## 核心价值

1. **消除幻觉**: LLM 可能臆造 API 名称（如 `__genius_atomic_max`），知识库提供真实准确的 API
2. **精确分类**: 区分 SIMT API (util/) 和 C API (simd_atomic) 的适用场景
3. **产品支持信息**: 包含 Atlas 350/A3/A2 各产品的支持矩阵，避免在不支持的硬件上踩坑
4. **类型安全**: C API 提供类型化版本，帮助开发者选择正确的 API

---

## 扩展：GPU 到 NPU 原子操作映射表（实测）

```cuda
// GPU 原子操作
__device__ int atomicAdd(int* address, int val);
__device__ int atomicMax(int* address, int val);
__device__ int atomicMin(int* address, int val);
__device__ int atomicCAS(int* address, int compare, int val);

// AscendC SIMT API (实测)
asc_atomic_max(dest, val);     // 通用原子最大，Atlas 350/A3 支持
AtomicMax(dest, val);          // ISASI 指令，Atlas 350 支持
SetAtomicMax(dest, val);       // ISASI 设置，Atlas 350/A3/A2 全支持
AtomicMin(dest, val);
AtomicCas(dest, compare, val);

// AscendC C API (simd_atomic, 实测)
asc_set_atomic_max_bfloat(dest, val);  // Atlas 350/A3/A2 全支持
asc_set_atomic_max_float(dest, val);
asc_set_atomic_max_float16(dest, val);
asc_set_atomic_max_int(dest, val);
```
