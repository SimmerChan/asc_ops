# 快速入门

本文档帮助你5分钟内快速体验AscendC算子知识库。

---

## 前置条件

- Python 3.10+ 已安装
- asc_ops 已安装（见 [安装指南](installation.md)）

---

## 5分钟快速体验

### Step 1: 启动服务

```bash
# 在项目根目录启动服务
python -m asc_ops.server
```

你应该看到类似输出：

```
INFO:     Started server process on http://0.0.0.0:8000
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 2: 打开API文档

浏览器访问: http://localhost:8000/docs

这将打开自动生成的API交互界面。

---

## 使用Python SDK查询

### 基本查询示例

```python
import asyncio
from asc_ops import KnowledgeQueryService

async def main():
    # 初始化服务（会自动连接本地ChromaDB）
    service = KnowledgeQueryService()

    # === 场景1: 开发新算子前查询 ===
    print("=== 开发参考查询 ===")

    dev_results = await service.query_for_development(
        operator_name="Matmul",
        query_type="all"  # "bug" | "optimization" | "all"
    )

    print(f"找到 {len(dev_results.related_knowledge)} 条相关知识")
    for item in dev_results.related_knowledge[:3]:
        print(f"  - [{item.source_repo}] {item.title}")

    # === 场景2: 遇到问题时排查 ===
    print("\n=== 问题排查查询 ===")

    bug_results = await service.query_for_troubleshooting(
        symptom="Matmul算子在处理非对齐数据时crash",
        operator_name="Matmul",
        error_message="address error"
    )

    print(f"找到 {len(bug_results.possible_causes)} 个可能原因")
    for cause in bug_results.possible_causes[:3]:
        print(f"  - [置信度:{cause.confidence:.2f}] {cause.description}")

    # === 场景3: 查询API用法 ===
    print("\n=== API查询 ===")

    api_results = await service.query_api(
        api_name="VecMatmul",
        limit=5
    )

    print(f"找到 {len(api_results)} 个相关API")
    for api in api_results:
        print(f"  - {api.canonical_name}: {api.description[:50]}...")

asyncio.run(main())
```

### 预期输出

```
=== 开发参考查询 ===
找到 5 条相关知识
  - [ops-nn] Matmul算子分块优化经验
  - [ops-nn] Matmul内存泄漏修复
  - [HierarchicalKV] Matmul精度问题排查

=== 问题排查查询 ===
找到 3 个可能原因
  - [置信度:0.85] 非对齐地址访问导致地址越界
  - [置信度:0.72] 矩阵维度不是16倍数导致tile边界问题
  - [置信度:0.65] 输入数据stride与预期不符

=== API查询 ===
找到 2 个相关API
  - VecMatmul: 向量与矩阵乘法接口
  - Matmul: 矩阵乘法核心接口
```

---

## 使用MCP接口

### Claude Code配置

在Claude Code的MCP设置中添加：

```json
{
  "mcpServers": {
    "asc-ops": {
      "command": "python",
      "args": ["-m", "asc_ops.mcp"],
      "env": {
        "CHROMA_DB_PATH": "./data/chroma_db"
      }
    }
  }
}
```

### 使用示例

在Claude Code中：

```
/asc-query Matmul算子的常用优化方案有哪些？
```

---

## 使用REST API

### 查询端点

```bash
# 开发参考查询
curl -X POST "http://localhost:8000/api/v1/query/development" \
  -H "Content-Type: application/json" \
  -d '{"operator_name": "Matmul", "query_type": "all"}'

# 问题排查查询
curl -X POST "http://localhost:8000/api/v1/query/troubleshooting" \
  -H "Content-Type: application/json" \
  -d '{"symptom": "crash", "operator_name": "Matmul"}'

# API查询
curl -X GET "http://localhost:8000/api/v1/api/VecMatmul"
```

---

## 知识库状态检查

```python
from asc_ops import KnowledgeStats

stats = await KnowledgeStats.get()
print(f"API知识: {stats.api_count} 条")
print(f"算子知识: {stats.operator_count} 条")
print(f"Bug修复: {stats.bug_fix_count} 条")
print(f"优化方案: {stats.optimization_count} 条")
```

---

## 下一步

- [首次查询详解](first-query.md) - 更多查询示例
- [API参考](../api/reference.md) - 完整接口文档
- [部署指南](../deployment/docker.md) - 生产环境部署
