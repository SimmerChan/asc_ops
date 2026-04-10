# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
GPU 知识提取器

从 GPU 代码和文档中提取结构化知识
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from .models import (
    GPUKernelKnowledge,
    GPUAPIInfo,
    GPUPlatform,
    GPUKernelArchitecture,
    GPUKernelPerformance,
)

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """提取结果"""
    success: bool
    items: List[Any]
    errors: List[str]


class GPUKernelExtractor:
    """GPU Kernel 知识提取器"""

    # CUTLASS kernel 名称模式
    KERNEL_NAME_PATTERNS = [
        r"(cutlass_\w+_\w+x\d+x\d+)",
        r"(cutlass_gemm_\w+)",
        r"(cutlass_conv2d_\w+)",
    ]

    # 模板参数模式
    TEMPLATE_PARAM_PATTERNS = [
        r"template\s*<\s*([^>]+)>",
        r"using\s+(\w+)\s*=\s*\w+;",  # type aliases
    ]

    def extract_from_source(
        self,
        source_code: str,
        platform: GPUPlatform,
        source_file: str = "",
    ) -> List[GPUKernelKnowledge]:
        """
        从源代码中提取 Kernel 知识

        Args:
            source_code: 源代码
            platform: GPU 平台
            source_file: 源文件路径

        Returns:
            GPUKernelKnowledge 列表
        """
        results = []

        # 提取 kernel 名称
        kernel_names = self._extract_kernel_names(source_code)

        # 提取模板参数
        template_params = self._extract_template_params(source_code)

        for name in kernel_names:
            kernel = GPUKernelKnowledge(
                kernel_id=self._generate_kernel_id(name, source_file),
                kernel_name=name,
                platform=platform,
                source_file=source_file,
                template_parameters=template_params,
                description=self._extract_description(source_code, name),
            )
            results.append(kernel)

        return results

    def _extract_kernel_names(self, source_code: str) -> List[str]:
        """提取 kernel 名称"""
        names = set()
        for pattern in self.KERNEL_NAME_PATTERNS:
            matches = re.finditer(pattern, source_code, re.IGNORECASE)
            for match in matches:
                name = match.group(1)
                if len(name) > 5:  # 过滤太短的名称
                    names.add(name)
        return list(names)

    def _extract_template_params(self, source_code: str) -> List[str]:
        """提取模板参数"""
        params = set()
        for pattern in self.TEMPLATE_PARAM_PATTERNS:
            matches = re.finditer(pattern, source_code)
            for match in matches:
                param = match.group(1).strip()
                if param:
                    # 分割逗号分隔的参数
                    for p in param.split(","):
                        p = p.strip()
                        if p and len(p) < 50:  # 过滤太长
                            params.add(p)
        return list(params)[:10]  # 限制数量

    def _extract_description(self, source_code: str, kernel_name: str) -> str:
        """提取 kernel 描述"""
        # 查找 kernel 名称附近的注释
        lines = source_code.split("\n")
        for i, line in enumerate(lines):
            if kernel_name in line:
                # 向前查找注释
                for j in range(max(0, i - 3), i):
                    if "//" in lines[j] or "/*" in lines[j]:
                        comment = lines[j].split("//")[-1].split("/*")[-1].strip()
                        if len(comment) > 10:
                            return comment
        return ""

    def _generate_kernel_id(self, name: str, source_file: str) -> str:
        """生成唯一 kernel ID"""
        file_tag = ""
        if source_file:
            # 从路径提取简短的标识
            parts = source_file.replace("\\", "/").split("/")
            if parts:
                file_tag = parts[-1].replace(".cu", "").replace(".h", "")
        return f"{file_tag}_{name}" if file_tag else name


class GPUAPIExtractor:
    """GPU API 信息提取器"""

    # API 签名模式
    SIGNATURE_PATTERNS = [
        r"(\w+(?:::\w+)*)\s*\(([^)]*)\)\s*;",  # namespace::func(args);
        r"void\s+(\w+)\s*\(([^)]*)\)\s*;",  # void func(args);
    ]

    def extract_from_source(
        self,
        source_code: str,
        platform: GPUPlatform,
    ) -> List[GPUAPIInfo]:
        """
        从源代码中提取 API 信息

        Args:
            source_code: 源代码
            platform: GPU 平台

        Returns:
            GPUAPIInfo 列表
        """
        results = []
        seen_apis = set()

        for pattern in self.SIGNATURE_PATTERNS:
            matches = re.finditer(pattern, source_code)
            for match in matches:
                api_name = match.group(1).strip()
                params_str = match.group(2).strip()

                if api_name and api_name not in seen_apis:
                    seen_apis.add(api_name)

                    params = self._parse_parameters(params_str)

                    api = GPUAPIInfo(
                        api_id=self._generate_api_id(api_name, platform),
                        api_name=api_name,
                        platform=platform,
                        full_signature=f"{api_name}({params_str})",
                        parameters=params,
                        return_type=self._extract_return_type(source_code, api_name),
                    )
                    results.append(api)

        return results

    def _parse_parameters(self, params_str: str) -> List[str]:
        """解析参数列表"""
        if not params_str.strip():
            return []

        params = []
        # 简单解析：按逗号分割
        for param in params_str.split(","):
            param = param.strip()
            if param:
                # 提取参数类型/名称
                parts = param.split()
                if parts:
                    params.append(parts[-1])  # 参数名
        return params

    def _extract_return_type(self, source_code: str, api_name: str) -> str:
        """提取返回类型"""
        # 查找 api_name 声明前的类型
        pattern = rf"(\w+(?:::\w+)*)\s+{re.escape(api_name)}\s*\("
        matches = re.finditer(pattern, source_code)
        for match in matches:
            return match.group(1)
        return "void"

    def _generate_api_id(self, name: str, platform: GPUPlatform) -> str:
        """生成唯一 API ID"""
        return f"{platform.value}_{name}"


class CrossPlatformMappingExtractor:
    """跨平台映射提取器"""

    def __init__(self):
        self._mappings: Dict[str, Any] = {}

    def add_predefined_mapping(
        self,
        gpu_api: str,
        npu_api: str,
        platform: GPUPlatform,
        equivalence_level: str,
        notes: str = "",
    ):
        """添加预定义映射"""
        from .models import MappingEquivalenceLevel, CrossPlatformMapping
        import uuid

        level = MappingEquivalenceLevel(equivalence_level)
        mapping = CrossPlatformMapping(
            mapping_id=str(uuid.uuid4())[:8],
            gpu_api=gpu_api,
            npu_api=npu_api,
            platform=platform,
            equivalence_level=level,
            adaptation_notes=notes,
            source="manual",
        )
        self._mappings[gpu_api.lower()] = mapping

    def find_mapping(self, gpu_api: str) -> Optional["CrossPlatformMapping"]:
        """查找映射"""
        return self._mappings.get(gpu_api.lower())

    def get_all_mappings(self) -> List["CrossPlatformMapping"]:
        """获取所有映射"""
        return list(self._mappings.values())
