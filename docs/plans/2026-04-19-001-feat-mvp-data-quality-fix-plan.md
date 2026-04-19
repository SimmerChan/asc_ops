# MVP 数据质量修复计划

**文档版本**: v2.0
**创建日期**: 2026-04-19
**最后更新**: 2026-04-19
**状态**: completed
**类型**: feat
**优先级**: P0

---

## Overview

修复 asc_ops MVP 知识库的数据质量问题，使系统达到真正可用状态。

## 执行结果 (2026-04-19)

| 任务 | 状态 | 说明 |
|------|------|------|
| URL字段验证 | ✅ **已完成** | 1120/1120 有URL，无需修复 |
| 降级解析验证 | ✅ **已完成** | 0个降级解析，无需修复 |
| 重复记录去重 | ✅ **已完成** | 删除18条重复，保留1102条唯一 |
| 低置信度标记 | ✅ **已完成** | 4个API已标记到Redis待重新采集 |

---

## 问题分析

### 实际数据质量状态 (验证后)

| 问题 | Session记录 | 实际状态 | 处理 |
|------|------------|----------|------|
| URL字段为空 | 全部为空 | ✅ 已解决 | 无需操作 |
| 降级解析 | 6个 | ✅ 已解决 | 无需操作 |
| 重复记录 | 18条额外 | ✅ 已清理 | `deduplicate_apis.py --execute` |
| 低置信度 | 6个 | ⚠️ 已标记 | `mark_pending_recollection.py` |

### 根因分析

**URL字段**：代码链路完整（parsers.py → api_storage.py → knowledge_query.py），session记录可能有误。

**重复记录**：ChromaDB upsert基于api_id，但多个采集源使用不同ID生成方式导致重复。

---

## Implementation Units

### Unit 1: 重复API去重 ✅

**Goal:** 删除18条重复API记录

**执行时间**: 2026-04-19

**操作**:
```bash
python scripts/deduplicate_apis.py --execute
```

**结果**:
- 保留 15 条（每组重复保留置信度最高的1条）
- 删除 18 条
- 总API数量: 1120 → 1102

**删除的记录**:
- DataCopy(3条): 删除2条(conf=0.3)
- printf(3条): 删除2条(conf=1.0)
- assert(3条): 删除2条(conf=1.0)
- 其他12个2次重复: 各删除1条

**Files**:
- Create: `scripts/deduplicate_apis.py`

---

### Unit 2: 低置信度API标记 ✅

**Goal:** 标记4个低置信度API待重新采集

**执行时间**: 2026-04-19

**操作**:
```bash
python scripts/mark_pending_recollection.py --execute
```

**结果**: 4个API已标记到Redis `ascendc:apis:pending_recollection`

**标记的API**:
| API | ID | 置信度 |
|-----|-----|--------|
| TPipe | 331a92a5c1cedfa0 | 0.3 |
| TBufPool | 8012946116b5b370 | 0.3 |
| TBuf | e18d9b52bfc4c250 | 0.3 |
| OpMC2Def | e3d85f753ee47431 | 0.3 |

**Files**:
- Create: `scripts/mark_pending_recollection.py`

---

### Unit 3: ChromaDB数据优化 (待处理)

**Goal:** 优化数据文件，支持GitHub存储

**Status**: 待处理

**问题**: ChromaDB数据文件约54MB，超过GitHub单文件50MB限制

**建议方案**:
1. 启用Git LFS跟踪 `data/chroma_db/` 目录
2. 或压缩数据文件后上传

---

## 最终数据质量

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 总API数量 | 1120 | **1102** |
| 唯一名称 | 1105 | **1102** |
| URL完整率 | 100% | **100%** |
| 降级解析 | 0 | **0** |
| 重复名称 | 15 | **0** |
| 低置信度(<0.5) | 6 | **4** |

---

## 待处理项

1. **ChromaDB 54MB问题** - 启用Git LFS
2. **4个低置信度API重新采集** - TPipe, TBufPool, TBuf, OpMC2Def

---

## Verification Commands

```bash
# 检查数据质量
PYTHONPATH=src python3 -c "
from src.asc_ops.storage import ChromaDBClient
from src.asc_ops.config import get_config
from collections import Counter

config = get_config()
client = ChromaDBClient(persist_directory=str(config.chroma.db_path))
col = client.get_collection('ascend_apis')
results = col.get(include=['metadatas'])
metadatas = results['metadatas']

print(f'总API数量: {len(metadatas)}')
names = [m.get('name', '') for m in metadatas if m.get('name')]
dupes = {k: v for k, v in Counter(names).items() if v > 1}
print(f'重复名称: {len(dupes)}')
low_conf = sum(1 for m in metadatas if float(m.get(\"confidence\", 1)) < 0.5)
print(f'低置信度: {low_conf}')
"

# 检查待采集标记
PYTHONPATH=src python3 scripts/mark_pending_recollection.py --list
```

---

## Commit History

| Commit | 日期 | 说明 |
|--------|------|------|
| 31f700d | 2026-04-19 | docs: 更新README数据规模至1120 API |
| 8ff0f14 | 2026-04-19 | feat: 完成342个API的nav_path补充 |

**本次变更** (待提交):
- `scripts/deduplicate_apis.py` - 去重脚本
- `scripts/mark_pending_recollection.py` - 待采集标记脚本
- `docs/plans/2026-04-19-001-feat-mvp-data-quality-fix-plan.md` - 计划文档更新
