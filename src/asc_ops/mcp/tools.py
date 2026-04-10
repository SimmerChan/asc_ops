# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
MCP 工具定义
"""

import logging
from typing import List, Optional

from .models import (
    MCPTool,
    MCPToolResult,
    MCPContentBlock,
)

logger = logging.getLogger(__name__)


class MCPTools:
    """
    MCP 工具集

    提供四个核心工具供 Agent 调用
    """

    def __init__(self):
        """初始化 MCP 工具"""
        self._tools = self._register_tools()

    def _register_tools(self) -> List[MCPTool]:
        """注册所有工具"""
        return [
            MCPTool(
                name="query_for_development",
                description="查询算子的 Bug 注意事项和优化经验。在开发新算子前调用，获取常见问题和最佳实践。",
                input_schema={
                    "type": "object",
                    "properties": {
                        "operator_name": {
                            "type": "string",
                            "description": "算子名称，如 Matmul, VecReduce, Tensor 等"
                        },
                        "query_type": {
                            "type": "string",
                            "enum": ["bug", "optimization", "all"],
                            "default": "all",
                            "description": "查询类型：bug（仅 Bug 知识）、optimization（仅优化知识）、all（全部）"
                        },
                        "min_confidence": {
                            "type": "number",
                            "default": 0.5,
                            "description": "最低置信度阈值"
                        },
                        "limit": {
                            "type": "integer",
                            "default": 10,
                            "description": "返回结果数量限制"
                        }
                    },
                    "required": ["operator_name"]
                }
            ),
            MCPTool(
                name="query_for_troubleshooting",
                description="根据问题症状查询可能的原因和建议检查项。遇到问题时调用。",
                input_schema={
                    "type": "object",
                    "properties": {
                        "symptom": {
                            "type": "string",
                            "description": "问题症状描述，如 'Matmul crash', 'memory leak' 等"
                        },
                        "operator_name": {
                            "type": "string",
                            "description": "算子名称（可选）"
                        },
                        "error_message": {
                            "type": "string",
                            "description": "错误信息（可选）"
                        },
                        "used_apis": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "使用的 API 列表（可选）"
                        },
                        "limit": {
                            "type": "integer",
                            "default": 5,
                            "description": "返回结果数量限制"
                        }
                    },
                    "required": ["symptom"]
                }
            ),
            MCPTool(
                name="query_api",
                description="查询 AscendC API 定义。支持精确匹配和语义搜索。",
                input_schema={
                    "type": "object",
                    "properties": {
                        "api_name": {
                            "type": "string",
                            "description": "API 名称（精确匹配）"
                        },
                        "semantic_query": {
                            "type": "string",
                            "description": "语义搜索查询"
                        },
                        "category": {
                            "type": "string",
                            "enum": ["memory", "compute", "sync", "tensor", "util"],
                            "description": "API 类别：memory, compute, sync, tensor, util"
                        },
                        "subcategory": {
                            "type": "string",
                            "description": "API 子类别"
                        },
                        "include_examples": {
                            "type": "boolean",
                            "default": False,
                            "description": "是否包含使用示例"
                        },
                        "limit": {
                            "type": "integer",
                            "default": 10,
                            "description": "返回结果数量限制"
                        }
                    }
                }
            ),
            MCPTool(
                name="query_cross_platform",
                description="查询 GPU API 到 NPU API 的跨平台映射。用于将 GPU 算子迁移到 NPU 时获取等效 API。",
                input_schema={
                    "type": "object",
                    "properties": {
                        "gpu_api": {
                            "type": "string",
                            "description": "GPU API 名称，如 '__syncthreads', 'wmma::load_matrix_sync' 等"
                        },
                        "gpu_platform": {
                            "type": "string",
                            "enum": ["cuda", "cutlass", "cublas", "cudnn"],
                            "default": "cuda",
                            "description": "GPU 平台来源"
                        },
                        "include_adaptation_notes": {
                            "type": "boolean",
                            "default": True,
                            "description": "是否包含适配注意事项"
                        }
                    },
                    "required": ["gpu_api"]
                }
            ),
        ]

    def list_tools(self) -> List[MCPTool]:
        """列出所有可用工具"""
        return self._tools

    def get_tool(self, name: str) -> Optional[MCPTool]:
        """获取指定工具"""
        for tool in self._tools:
            if tool.name == name:
                return tool
        return None

    async def call_tool(
        self,
        name: str,
        arguments: dict,
        knowledge_query_service=None,
        mapper_engine=None,
    ) -> MCPToolResult:
        """
        调用工具

        Args:
            name: 工具名称
            arguments: 工具参数
            knowledge_query_service: 知识查询服务
            mapper_engine: 跨平台映射引擎

        Returns:
            MCPToolResult: 工具执行结果
        """
        logger.info(f"Calling MCP tool: {name} with args: {arguments}")

        try:
            if name == "query_for_development":
                return await self._query_for_development(arguments, knowledge_query_service)
            elif name == "query_for_troubleshooting":
                return await self._query_for_troubleshooting(arguments, knowledge_query_service)
            elif name == "query_api":
                return await self._query_api(arguments, knowledge_query_service)
            elif name == "query_cross_platform":
                return await self._query_cross_platform(arguments, mapper_engine)
            else:
                return MCPToolResult(
                    content=[MCPContentBlock(type="text", text=f"Unknown tool: {name}")],
                    is_error=True
                )

        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}")
            return MCPToolResult(
                content=[MCPContentBlock(type="text", text=f"Error: {str(e)}")],
                is_error=True
            )

    async def _query_for_development(
        self,
        args: dict,
        service,
    ) -> MCPToolResult:
        """query_for_development 工具实现"""
        if service is None:
            return MCPToolResult(
                content=[MCPContentBlock(type="text", text="Knowledge query service not available")],
                is_error=True
            )

        result = await service.query_for_development(
            operator_name=args["operator_name"],
            query_type=args.get("query_type", "all"),
            min_confidence=args.get("min_confidence", 0.5),
            limit=args.get("limit", 10),
        )

        # 格式化输出
        lines = [f"# {result.operator_name} 开发知识查询结果"]
        lines.append(f"\n共找到 {result.total_count} 条知识\n")

        if result.bug_fixes:
            lines.append("## Bug 修复知识")
            for bug in result.bug_fixes:
                lines.append(f"\n### {bug.bug_title}")
                lines.append(f"- 严重程度: {bug.severity.value}")
                lines.append(f"- 分类: {bug.category.value}")
                if bug.root_cause:
                    lines.append(f"- 根因: {bug.root_cause}")
                if bug.fix_pattern:
                    lines.append(f"- 修复方案: {bug.fix_pattern}")
                if bug.trigger_conditions:
                    lines.append(f"- 触发条件: {', '.join(bug.trigger_conditions)}")

        if result.optimizations:
            lines.append("\n## 优化知识")
            for opt in result.optimizations:
                lines.append(f"\n### {opt.opt_title}")
                lines.append(f"- 优化类型: {', '.join(opt.optimization_type)}")
                if opt.optimization_description:
                    lines.append(f"- 描述: {opt.optimization_description}")
                if opt.improvement_ratio:
                    lines.append(f"- 提升比例: {opt.improvement_ratio * 100:.1f}%")

        text = "\n".join(lines)
        return MCPToolResult(content=[MCPContentBlock(type="text", text=text)])

    async def _query_for_troubleshooting(
        self,
        args: dict,
        service,
    ) -> MCPToolResult:
        """query_for_troubleshooting 工具实现"""
        if service is None:
            return MCPToolResult(
                content=[MCPContentBlock(type="text", text="Knowledge query service not available")],
                is_error=True
            )

        result = await service.query_for_troubleshooting(
            symptom=args["symptom"],
            operator_name=args.get("operator_name"),
            error_message=args.get("error_message"),
            used_apis=args.get("used_apis"),
            limit=args.get("limit", 5),
        )

        lines = [f"# 问题排查: {result.symptom}"]
        lines.append(f"\n找到 {len(result.possible_causes)} 个可能原因\n")

        for i, cause in enumerate(result.possible_causes, 1):
            lines.append(f"\n## 原因 {i}")
            lines.append(f"- Bug ID: {cause.bug_id}")
            lines.append(f"- 置信度: {cause.confidence:.2f}")
            lines.append(f"- 根因: {cause.root_cause}")
            if cause.trigger_conditions:
                lines.append(f"- 触发条件: {', '.join(cause.trigger_conditions)}")
            if cause.suggested_fix:
                lines.append(f"- 建议修复: {cause.suggested_fix}")
            if cause.suggested_checks:
                lines.append(f"- 建议检查: {', '.join(cause.suggested_checks)}")

        text = "\n".join(lines)
        return MCPToolResult(content=[MCPContentBlock(type="text", text=text)])

    async def _query_api(
        self,
        args: dict,
        service,
    ) -> MCPToolResult:
        """query_api 工具实现"""
        if service is None:
            return MCPToolResult(
                content=[MCPContentBlock(type="text", text="Knowledge query service not available")],
                is_error=True
            )

        result = await service.query_api(
            api_name=args.get("api_name"),
            semantic_query=args.get("semantic_query"),
            category=args.get("category"),
            subcategory=args.get("subcategory"),
            include_examples=args.get("include_examples", False),
            limit=args.get("limit", 10),
        )

        lines = [f"# API 查询结果"]
        lines.append(f"\n找到 {len(result)} 个 API\n")

        for api in result:
            lines.append(f"\n## {api.canonical_name}")
            lines.append(f"- 签名: {api.full_signature}")
            lines.append(f"- 类别: {api.category} / {api.subcategory}")
            lines.append(f"- 描述: {api.description}")
            if api.usage_examples and args.get("include_examples"):
                lines.append("\n### 使用示例:")
                for ex in api.usage_examples:
                    lines.append(f"\n{ex.scenario}:\n```\n{ex.code}\n```")

        text = "\n".join(lines)
        return MCPToolResult(content=[MCPContentBlock(type="text", text=text)])

    async def _query_cross_platform(
        self,
        args: dict,
        mapper_engine,
    ) -> MCPToolResult:
        """query_cross_platform 工具实现"""
        if mapper_engine is None:
            # 如果映射引擎未初始化，返回提示
            return MCPToolResult(
                content=[MCPContentBlock(
                    type="text",
                    text="跨平台映射引擎未初始化。请先配置 GPU 知识库。"
                )]
            )

        result = mapper_engine.find_mapping(
            gpu_api=args["gpu_api"],
            platform=args.get("gpu_platform", "cuda"),
            include_notes=args.get("include_adaptation_notes", True),
        )

        lines = [f"# GPU → NPU 跨平台映射: {args['gpu_api']}"]
        lines.append(f"\n平台: {args.get('gpu_platform', 'cuda')}")

        if result:
            lines.append(f"\n## 映射结果")
            lines.append(f"- NPU API: **{result.npu_api}**")
            lines.append(f"- 等价级别: {result.equivalence_level.value}")
            if result.adaptation_notes and args.get("include_adaptation_notes", True):
                lines.append(f"\n### 适配注意事项")
                lines.append(result.adaptation_notes)
        else:
            lines.append("\n未找到精确映射。尝试搜索相似 API...")

            # 搜索相似映射
            similar = mapper_engine.find_similar(args["gpu_api"])
            if similar:
                lines.append("\n### 相似映射")
                for sim in similar[:3]:
                    lines.append(f"- {sim.gpu_api} → {sim.npu_api} ({sim.equivalence_level.value})")
            else:
                lines.append("\n未找到相似映射。建议查阅昇腾官方文档。")

        text = "\n".join(lines)
        return MCPToolResult(content=[MCPContentBlock(type="text", text=text)])
