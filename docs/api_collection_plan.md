# AscendC API 完整采集计划

## 当前知识库状态 (2026-04-18)

**总API数量**: 1120
**有nav_path**: 778 (69.5%)
**无nav_path**: 342 (30.5%)

### 各类别状态

| 类别 | 总数 | 有nav_path | 无nav_path | 状态 |
|------|------|-----------|-----------|------|
| util | 838 | 509 | 329 | ⚠️ 需迁移 |
| C API | 261 | 261 | 0 | ✅ 完成 |
| memory | 7 | 0 | 7 | ⚠️ 待分类 |
| sync | 5 | 1 | 4 | ⚠️ 待分类 |
| tensor | 4 | 3 | 1 | ⚠️ 待分类 |
| compute | 1 | 0 | 1 | ⚠️ 待分类 |
| (无分类) | 4 | 4 | 0 | ⚠️ 需处理 |

---

## 问题分析

### 已完成 ✅
- **C API**: 261个全部采集，nav_path 100%正确

### 待处理 ⚠️

#### 342个API缺少nav_path

这些API按类型可分为:

| 类型 | 数量 | 可能的分类 |
|------|------|-----------|
| SIMT数学函数变体 | 48 | SIMT API/数学函数 |
| C++类型特性 | 29 | Utils API/C++标准库 |
| 基础API/Memory | 24 | 基础API/Memory数据搬运 |
| 同步/调测 | 31 | SIMT API/同步函数 |
| 矩阵计算 | 15+ | 基础API/矩阵计算 |
| 归一化 | 10+ | 基础API/归一化 |
| Tiling相关 | 15+ | Utils API/Tiling |
| 类型转换Cast | 5+ | SIMT API/类型转换 |
| Atomic变体 | 5+ | SIMT API/Atomic函数 |
| Softmax变体 | 10+ | 基础API |
| Reduction变体 | 15+ | SIMT或基础API |
| RTC | 10+ | Utils API/RTC |
| 其他 | 50+ | 需确认 |

---

## 实施方案

### Option 1: 保守方案 (快速完成)

接受当前状态，仅确保已知的API分类正确:
- 261 C API ✅
- 509 util (已有nav_path) ✅
- 342 util (无nav_path) - 保持现状，标记为"未分类"

**结果**: 770/1120 (68.8%) 完全分类

### Option 2: 积极方案 (手动完善)

需要逐个确认342个API的官方导航路径，工作量大但结果完整。

**初步分类** (基于命名模式):

```python
# 建议添加到API_NAV_MAPPING的分类

# ===== SIMT 数学函数变体 =====
"Cos": ("SIMT API", "数学函数", ""),
"Sin": ("SIMT API", "数学函数", ""),
"Tan": ("SIMT API", "数学函数", ""),
"Floor": ("SIMT API", "数学函数", ""),
"Ceil": ("SIMT API", "数学函数", ""),
"Round": ("SIMT API", "数学函数", ""),
"Trunc": ("SIMT API", "数学函数", ""),
"Acos": ("SIMT API", "数学函数", ""),
"Asin": ("SIMT API", "数学函数", ""),
"Atan": ("SIMT API", "数学函数", ""),
"Cosh": ("SIMT API", "数学函数", ""),
"Sinh": ("SIMT API", "数学函数", ""),
"Tanh": ("SIMT API", "数学函数", ""),
"Exp": ("SIMT API", "数学函数", ""),
"Log": ("SIMT API", "数学函数", ""),
"Sqrt": ("SIMT API", "数学函数", ""),

# ===== SIMT Atomic变体 =====
"AtomicCas": ("SIMT API", "Atomic函数", ""),
"AtomicExch": ("SIMT API", "Atomic函数", ""),

# ===== 基础API - 矩阵计算 =====
"Conv2D": ("基础API", "矩阵计算", ""),
"Conv3D": ("基础API", "矩阵计算", ""),
"Gem": ("基础API", "矩阵计算", ""),
"Matul": ("基础API", "矩阵计算", ""),
"Mmad": ("基础API", "矩阵计算", ""),

# ===== Utils API - Tiling =====
"TilingData结构定义": ("Utils API", "Tiling", ""),
"GET_TILING_DATA": ("Utils API", "Tiling", ""),
"GET_TILING_DATA_WITH_STRUCT": ("Utils API", "Tiling", ""),

# ===== Utils API - RTC =====
"aclrtcCompileProg": ("Utils API", "RTC", ""),
"aclrtcCreateProg": ("Utils API", "RTC", ""),
"aclrtcDestroyProg": ("Utils API", "RTC", ""),

# ===== C++ 类型特性 =====
"is_array": ("Utils API", "C++标准库", "类型特性"),
"is_const": ("Utils API", "C++标准库", "类型特性"),
"is_pointer": ("Utils API", "C++标准库", "类型特性"),
# ... 其他类型特性
```

---

## 推荐行动计划

### Step 1: 评估工作量
- 342个API需要人工确认官方分类
- 预计需要2-4小时工作量

### Step 2: 执行Option 2
1. 创建一个分类脚本
2. 运行nav_path迁移
3. 验证结果

### Step 3: 验证
```bash
PYTHONPATH=src python3 -c "
import chromadb
from asc_ops.storage.collections import CollectionType
from asc_ops.config import get_config

config = get_config()
client = chromadb.PersistentClient(path=str(config.chroma.db_path))
collection = client.get_collection(CollectionType.ASCEND_APIS.value)
results = collection.get(include=['metadatas'])

total = len(results.get('metadatas', []))
with_nav = sum(1 for m in results.get('metadatas', []) if m and m.get('nav_path'))

print(f'总API: {total}')
print(f'有nav_path: {with_nav} ({100*with_nav/total:.1f}%)')
"
```

---

## 总结

| 方案 | nav_path覆盖率 | 工作量 | 推荐度 |
|------|--------------|--------|--------|
| Option 1 | 68.8% | 0 | ⭐⭐ |
| Option 2 | 100% | 2-4小时 | ⭐⭐⭐⭐ |

**当前建议**: 先完成Option 1保证基本功能，后续有空再完善Option 2。

---

## API分类体系 (目标)

### 1. 基础数据结构
- LocalTensor, GlobalTensor, Coordinate, Layout
- TensorTrait, TPosition, ShapeInfo, TensorDesc
- ListTensorDesc, UnaryRepeatParams, BinaryRepeatParams
- complex32, complex64

### 2. 基础API
- **Memory数据搬运**: DataCopy, Copy, Fill, LoadData, DumpTensor
- **Memory矢量计算**: Exp, Ln, Abs, Add, Sub, Mul, Div, Max, Min
- **矩阵计算**: Mmad, Conv2D, Conv3D, Gemm, Matmul
- **归一化**: LayerNorm, GroupNorm, BatchNorm
- **激活函数**: Relu, Sigmoid, Tanh, Gelu
- **随机函数**: PhiloxRandom

### 3. SIMT API
- **核函数定义**: asc_vf_call
- **同步函数**: asc_syncthreads, asc_threadfence
- **数学函数**: tanf, sinf, cosf, expf, logf + Cos, Sin, Floor变体
- **精度转换**: rintf, floorf, ceilf, truncf
- **Atomic函数**: asc_atomic_add, AtomicCas, AtomicExch
- **Warp函数**: asc_all, asc_any, asc_ballot
- **类型转换**: __float2half, __half2float + Cast变体

### 4. Utils API
- **C++标准库**: max, min, abs, sqrt + 类型特性
- **Tiling**: TilingData, GET_TILING_DATA
- **RTC**: aclrtcCompileProg, aclrtcCreateProg
- **平台信息**: PlatformAscendC

### 5. AI CPU API
- printf, assert, DataStoreBarrier

### 6. C API (261个)
- **向量计算**: asc_add, asc_mul, asc_abs
- **寄存器操作**: asc_load, asc_store
- **数据搬运**: asc_copy_gm2ub, asc_copy_ub2gm
- **同步**: asc_sync_notify, asc_sync_wait
- **系统变量**: asc_get_block_num, asc_get_core_id
