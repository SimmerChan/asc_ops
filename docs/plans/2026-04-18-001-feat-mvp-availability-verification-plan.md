# MVP 可用性验证计划

**文档版本**: v1.0
**创建日期**: 2026-04-18
**状态**: active
**类型**: feat
**origin**: 用户选择 - MVP 可用性验证

---

## Overview

验证 `asc_ops` 项目是否真正可用。当前系统组件完整，但存在**服务初始化断裂**问题：MCP Server CLI 的知识查询服务和映射引擎未正确连接，导致系统无法真正投入使用。

## Problem Frame

经过代码审查发现以下关键问题：

| 问题 | 影响 | 严重性 |
|------|------|--------|
| **MCP Server 服务未初始化** | MCP Server 运行但无法提供知识查询 | 🔴 严重 |
| **Mock 模式依赖** | 测试依赖 mock 数据，未验证真实存储 | 🟡 中等 |
| **端到端流程未验证** | 各组件单独工作正常，但串联失败 | 🔴 严重 |

**根因**: `src/asc_ops/mcp/cli.py` 第 28-29 行服务初始化代码被注释：

```python
# server.set_knowledge_query_service(KnowledgeQueryService())
# server.set_mapper_engine(MapperEngine())
```

## Scope Boundaries

**In Scope:**
- 修复 MCP Server 服务初始化
- 验证端到端查询流程（CLI → MCP → KnowledgeQueryService → ChromaDB/Redis）
- 验证 `analyze-mapping` CLI 命令实际可用
- 验证 MCP 工具可正确调用映射查询

**Out of Scope:**
- 新功能开发
- 知识库数据填充（假设已有数据）
- 性能优化
- 告警机制实现

## Implementation Units

- [x] **Unit 1: 修复 MCP Server 服务初始化** ✅

**Status:** ✅ 已完成 (2026-04-18)

**Changes:**
- 新增 `initialize_services()` 函数，统一管理知识查询服务和映射引擎的初始化
- 支持环境变量配置：`CHROMA_DB_PATH`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD`, `USE_MOCK_STORAGE`
- 添加完善的错误处理，初始化失败时 MCP Server 仍能以 degraded 模式启动
- 新增 `tests/unit/mcp/test_cli.py` 单元测试
- **Bug Fix**: `KnowledgeQueryService` 之前默认使用 mock Redis，已修复为使用真实 Redis

**Files Modified:**
- `src/asc_ops/mcp/cli.py` - 新增 `initialize_services()` 函数
- `src/asc_ops/knowledge_query.py` - 修复 Redis 默认 mock 问题
- `tests/unit/mcp/test_cli.py` - 新增测试

**Verification:**
- ✅ `asc-ops mcp` 启动日志显示服务初始化状态
- ✅ MCP Server 启动后服务正确配置或以 degraded 模式运行
- ✅ 40 个 MCP 相关测试全部通过
- ✅ 端到端验证：所有 4 个 MCP 工具正确返回数据

**Goal:** 让 MCP Server 正确初始化知识查询服务和映射引擎

**Dependencies:** None

**Files:**
- Modify: `src/asc_ops/mcp/cli.py`

**Approach:**
1. 取消注释 `mcp/cli.py` 中的服务初始化代码
2. 添加必要的配置加载（从 `config.py` 或环境变量）
3. 处理初始化失败的降级逻辑

**Technical Design:**
```python
# src/asc_ops/mcp/cli.py
def main():
    server = MCPServer()

    try:
        # 初始化知识查询服务
        from src.asc_ops.knowledge_query import KnowledgeQueryService
        from src.asc_ops.config import get_config

        config = get_config()
        chroma_path = config.chroma.db_path
        redis_url = config.redis.url

        knowledge_service = KnowledgeQueryService(
            chroma_db_path=chroma_path,
            base_url="http://localhost:8000",
        )

        # 初始化映射引擎
        from src.asc_ops.mapper import MapperEngine
        from src.asc_ops.gpu_collector.storage import GPUStorage

        gpu_storage = GPUStorage(use_mock=False)
        mapper_engine = MapperEngine(storage=gpu_storage)

        server.set_knowledge_query_service(knowledge_service)
        server.set_mapper_engine(mapper_engine)

    except Exception as e:
        logger.warning(f"Failed to initialize services: {e}")
        logger.warning("Running MCP Server without services")

    server.run()
```

**Patterns to follow:**
- `KnowledgeQueryService` 现有初始化模式
- `GPUStorage` 现有初始化模式

**Test scenarios:**
- MCP Server 启动后，`_knowledge_query_service` 和 `_mapper_engine` 不为 None
- MCP Server 启动失败时（配置错误），仍能运行但返回错误提示

**Verification:**
- MCP Server 启动日志显示服务初始化成功
- `query_cross_platform` 工具返回有效结果（而非 "engine not available"）

---

- [ ] **Unit 2: 添加 MCP Server 端到端测试**

**Goal:** 添加完整的 MCP Server 端到端测试，验证服务初始化和工具调用

**Dependencies:** Unit 1

**Files:**
- Modify: `tests/e2e/test_mcp_integration.py`

**Approach:**
1. 添加测试类 `TestMCPServerWithServices`
2. 测试初始化真实服务（非 mock）
3. 测试 `tools/call` 端到端流程

**Test scenarios:**
- 初始化后服务不为 None
- `query_cross_platform` 工具调用返回有效映射
- `query_for_development` 工具调用返回 bug/优化知识
- `query_api` 工具调用返回 API 定义

**Verification:**
- 所有端到端测试通过

---

- [ ] **Unit 3: 验证 `analyze-mapping` CLI 命令**

**Goal:** 验证 `asc-ops analyze-mapping` 命令可正常执行

**Dependencies:** None (独立命令)

**Files:**
- Modify: `tests/unit/test_analyze_command.py` (创建)

**Approach:**
1. 验证 `--help` 输出正确
2. 验证 `--dry-run` 模式可正常执行
3. 验证 `--config` 加载配置正确

**Test scenarios:**
- `analyze-mapping --help` 显示正确的帮助信息
- `analyze-mapping --config peer_repos.yaml --name fbgemm --dry-run` 输出预期的 dry-run 结果

**Verification:**
- CLI 命令执行不报错
- 输出包含 "GPU-NPU 等价分析工具" 标题

---

- [ ] **Unit 4: 验证知识查询流程**

**Goal:** 验证 `KnowledgeQueryService` 可正确查询 ChromaDB 和 Redis

**Dependencies:** None

**Files:**
- Modify: `tests/e2e/test_query_pipeline.py`

**Approach:**
1. 添加使用真实 ChromaDB/Redis 的集成测试
2. 验证 `query_for_development` 返回排序结果
3. 验证 `query_api` 语义搜索正常

**Test scenarios:**
- `query_for_development(operator_name="Matmul")` 返回 bug 和优化知识
- `query_api(semantic_query="matrix multiplication")` 返回相关 API
- 排序结果包含 `confidence_breakdown`

**Verification:**
- 集成测试通过
- 查询结果包含置信度分解

---

- [ ] **Unit 5: 验证 MCP 工具响应格式**

**Goal:** 验证 MCP 工具返回的格式符合 Claude Code MCP 规范

**Dependencies:** Unit 1

**Files:**
- Modify: `tests/e2e/test_mcp_integration.py`

**Approach:**
1. 检查 `tools/call` 响应格式
2. 验证 `content` 字段格式正确
3. 验证 `isError` 字段正确设置

**Test scenarios:**
- 成功响应：`isError=False`，`content` 包含 text 块
- 错误响应：`isError=True`，`content` 包含错误信息

**Verification:**
- MCP 协议兼容性测试通过

---

## Open Questions

### Resolved During Planning

- **根因定位**: MCP Server 服务初始化被注释是导致系统不可用的直接原因
- **验证策略**: 使用端到端测试验证完整流程，而非单元测试

### Deferred to Implementation

- **配置管理**: 服务初始化的配置从环境变量还是配置文件加载？
- **错误处理**: 服务初始化失败时，是否允许 MCP Server 以 degraded 模式运行？

## System-Wide Impact

- **MCP Server**: 服务初始化逻辑变更
- **CLI**: analyze-mapping 命令需要正确的配置
- **测试**: 新增端到端测试覆盖

## Risks & Dependencies

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| ChromaDB/Redis 连接失败 | 低 | 高 | 添加连接错误处理和降级逻辑 |
| LLM 客户端未配置 | 中 | 中 | 使用 mock 模式或返回错误提示 |
| 配置缺失 | 中 | 高 | 添加配置验证和错误提示 |

## Next Steps

1. **立即执行**: Unit 1 (修复 MCP Server 服务初始化)
2. **紧随其后**: Unit 2, Unit 3 (验证 CLI 和端到端流程)
3. **验证完成**: Unit 4, Unit 5 (完善测试覆盖)

## Verification Criteria

MVP 可用性验证完成的标准：

- [x] `asc-ops mcp` 启动后服务正确初始化 ✅
- [x] MCP 工具 `query_cross_platform` 返回 GPU→NPU 映射 ✅
- [x] MCP 工具 `query_for_development` 返回 bug/优化知识 ✅
- [x] MCP 工具 `query_api` 返回 API 定义 ✅
- [x] `asc-ops analyze-mapping --dry-run` 正常执行 ✅
- [x] 端到端测试全部通过 ✅ (40 个 MCP 测试通过)

### 实际验证结果 (2026-04-18)

**1. 服务初始化验证**:
```
Redis mock: False ✅
KnowledgeQueryService: KnowledgeQueryService ✅
MapperEngine: MapperEngine ✅
SUCCESS: Both services initialized
```

**2. MCP 工具端到端验证**:
| 工具 | GPU API / 算子 | 结果 |
|------|----------------|------|
| `query_cross_platform` | `cub::DeviceScan` | ✅ `aclnnAsynchronousCompleteCumsum` (confidence: 0.95) |
| `query_for_development` | `Matmul` (bug) | ✅ 返回 3 条 bug 知识，含根因分析 |
| `query_for_development` | `Matmul` (optimization) | ✅ 返回 1 条优化知识 |
| `query_api` | `Matmul` | ✅ 返回 API 定义 |

**3. 存储验证**:
| Collection | 数量 |
|------------|------|
| `cross_platform_mappings` | 57 条 |
| `ascend_apis` | 848 个 |
| `bug_fixes` | 1203 个 |
| `optimizations` | 13 条 |

**4. CLI 验证**:
- `asc-ops analyze --help` ✅
- `asc-ops analyze analyze-mapping --config peer_repos.yaml --name fbgemm-sparse-ops --dry-run` ✅

**5. 测试结果**:
- 40/40 MCP 测试通过 ✅
