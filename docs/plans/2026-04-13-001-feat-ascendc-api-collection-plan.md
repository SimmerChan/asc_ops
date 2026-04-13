---
title: AscendC API 采集与入库
type: feat
status: completed
date: 2026-04-13
origin: docs/design/2026-04-09-ascendc-api-knowledge-base-design.md
---

# AscendC API 采集与入库

## Overview

将昇腾官方 CANN 9.0.0-beta.2 的 1786 个 AscendC API 采集入库，建立完整的 API 知识库，为 Coding Agent 提供 API 参考查询能力。

## Problem Frame

当前状态：
- `ascend_apis` collection 已在 ChromaDB/Redis 中定义
- 采集组件骨架代码已实现
- **占位符 URL 和 CSS 选择器需要替换为实际值**

目标：
- 从昇腾官方文档采集 1786 个 API 的完整信息
- 支持后续增量同步

## Requirements Trace

- 设计文档: `docs/design/2026-04-09-ascendc-api-knowledge-base-design.md`
- Phase A1: API 数据模型 + 存储结构 ✓ (已完成)
- Phase A2: API 文档采集 Pipeline ← 本次实施

## Scope Boundaries

**在范围内:**
- 修正 `official_docs.py` 中的 base_url
- 修正 `link_discovery.py` 中的列表页 URL
- 适配 `parsers.py` 中的 CSS 选择器以匹配实际页面结构
- 实现采集调度器 (APICollector)
- 创建 CLI 命令触发采集

**不在范围内:**
- API 使用案例采集 (Phase A3)
- 增量同步调度 (后续迭代)
- 跨库关联 (Phase A5)

## Key Technical Decisions

### URL 结构 (实测数据)
```
Base URL: https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/API/ascendcopapi/

列表页: atlasascendc_api_07_0003.html
详情页: atlasascendc_api_07_XXXX.html (XXXX = 4位序号, 0001-1786)
```

### 页面结构特征 (来自记忆文件)
- 面包屑导航包含分类信息
- 函数原型在 `<pre>` 或 `<code>` 标签中
- 参数表格包含 "参数名" / "类型" / "描述" 列
- 产品支持情况表格

### 采集策略
- 两阶段：链接发现 → 详情提取
- 断点续采：基于 Redis 记录进度
- 限速控制：0.5 秒/请求

## Implementation Units

### Unit 1: 修正 URL 配置

**Goal:** 将占位符 URL 替换为实际昇腾文档 URL

**Files:**
- `src/asc_ops/collector/official_docs.py` (line 31)
- `src/asc_ops/collector/link_discovery.py` (line 57)

**Approach:**
- `official_docs.py`: `base_url = "https://www.hiascend.com"`
- `link_discovery.py`: `DEFAULT_API_LIST_URL = "https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/API/ascendcopapi/atlasascendc_api_07_0003.html"`

**Verification:**
```bash
grep "www.hiascend.com" src/asc_ops/collector/official_docs.py
grep "atlasascendc_api_07_0003" src/asc_ops/collector/link_discovery.py
```

---

### Unit 2: 适配页面解析选择器

**Goal:** 更新 `parsers.py` 中的 CSS 选择器以匹配 CANN API 页面实际结构

**Files:**
- `src/asc_ops/collector/parsers.py` (lines 50-60)

**Approach:**
根据实测页面结构，更新 SELECTORS:

```python
SELECTORS = {
    "api_name": ["h1", ".article-title", "[class*='title']"],
    "breadcrumb": ["[class*='breadcrumb']", ".nav-path", "section[class*='article-bread']"],
    "signature": ["pre", "code", "[class*='signature']"],
    "hardware_support": ["table:has(th:contains('产品'))"],
    "parameters_table": ["table:has(th:contains('参数名'))"],
    "return_value": ["h2:contains('返回值'), p:contains('返回')"],
    "examples": ["pre:has(code)", "[class*='example']"],
    "cautions": ["[class*='caution']", "[class*='warning']"],
    "description": ["section[class*='content']", ".article-content"],
}
```

**Key insight:**
- CANN API 页面使用 `<pre>` 标签包含函数原型
- 表格标题包含 "参数名" / "类型" / "描述"
- 面包屑在 `<section class="article-bread">` 中

**Verification:**
- 单元测试验证解析器能正确提取 LocalTensor 页面

---

### Unit 3: 实现 APICollector 调度器

**Goal:** 将链接发现和详情提取编排为完整采集流程

**Files:**
- Create: `src/asc_ops/collector/api_collector.py`

**Approach:**
```python
class APICollector:
    """API 采集调度器"""

    def __init__(
        self,
        docs_client: OfficialDocsClient,
        storage: APIStorage,
        checkpoint: CheckpointManager,
    ):
        ...

    async def run_full_collection(self, limit: Optional[int] = None):
        """执行全量或限量采集"""
        # 1. 发现所有 API 链接
        links = await self._discover_links()

        # 2. 获取已采集进度
        completed = self._checkpoint.get_completed_ids()

        # 3. 过滤未采集的
        pending = [l for l in links if l.api_id not in completed]

        # 4. 限流采集详情
        for link in tqdm(pending[:limit]):
            await self._collect_api_detail(link)
            self._checkpoint.mark_completed(link.api_id)

        return {"total": len(links), "collected": len(pending[:limit])}
```

**Dependencies:**
- Unit 1 (URL 配置)
- Unit 2 (选择器适配)

**Verification:**
- `python -c "from asc_ops.collector.api_collector import APICollector; print('OK')"`

---

### Unit 4: 创建 CLI 采集命令

**Goal:** 提供命令行接口触发采集任务

**Files:**
- `src/asc_ops/cli/collect.py`

**Approach:**
使用 Click 创建 CLI:

```python
@click.group()
def cli():
    """AscendC 知识采集工具"""
    pass

@cli.command()
@click.option("--limit", "-l", default=None, type=int, help="限制采集数量")
@click.option("--resume/--no-resume", default=True, help="是否从断点继续")
async def apicollect(limit, resume):
    """采集 AscendC API 文档"""
    collector = APICollector()
    result = await collector.run_full_collection(limit=limit)
    click.echo(f"采集完成: {result}")
```

**Verification:**
```bash
python -m asc_ops.cli collect --help
```

---

### Unit 5: 验证采集结果

**Goal:** 验证 API 数据正确入库

**Approach:**
1. 运行采集脚本 (限定前 10 条)
2. 检查 ChromaDB 中的文档数量
3. 检查 Redis 中的元数据
4. 抽样验证数据完整性

**Verification:**
```bash
# 采集前 10 个 API
python -m asc_ops.cli collect --limit 10

# 验证
python -c "
from asc_ops.storage.chroma_client import ChromaDBClient
from asc_ops.storage.collections import CollectionType
chroma = ChromaDBClient()
print(f'API count: {chroma.count(CollectionType.ASCEND_APIS.value)}')"
```

**Success Criteria:**
- 采集 10 个 API，10 个正确入库
- ChromaDB 计数增加 10
- Redis 包含 API 元数据

## Verification

**目标:** 验证 1786 个 API 采集功能正常

| 步骤 | 操作 | 验证 |
|------|------|------|
| 1 | 修正 URL 配置 | `grep` 确认无占位符 |
| 2 | 适配选择器 | 解析 LocalTensor 页面成功 |
| 3 | 运行采集 (10 条) | 10/10 入库 |
| 4 | 运行采集 (100 条) | 100/100 入库 |

## Open Questions

### Deferred to Implementation
- **CSS 选择器适配**: 需要实际抓取页面验证选择器是否正确
- **采集进度持久化**: CheckpointManager 已实现，需验证断点续采

## System-Wide Impact

- **ChromaDB**: 新增 `ascend_apis` collection 数据
- **Redis**: 新增 `api:*` keys
- **MCP 工具**: `query_ascendc_api` 等工具将可返回真实 API 数据

## Risks & Dependencies

| 风险 | 影响 | 缓解 |
|------|------|------|
| 昇腾文档结构变更 | 解析失败 | 预留降级解析模式 |
| 限流触发 | 采集中断 | 指数退避重试 |
| 页面编码问题 | 中文乱码 | 指定 UTF-8 编码 |

## Dependencies

- `OfficialDocsClient` (已有)
- `APILinkDiscovery` (已有,需修正 URL)
- `APIParser` (已有,需适配选择器)
- `APIStorage` (已有)
- `CheckpointManager` (已有)

## Next Steps

1. 实施 Unit 1-5
2. 运行全量采集 (1786 APIs)
3. 生成采集质量报告
