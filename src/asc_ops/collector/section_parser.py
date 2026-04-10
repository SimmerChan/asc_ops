# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
Section 解析器

提供更细粒度的 HTML 页面 section 解析能力
"""

import logging
import re
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup, Tag

from .parsers import (
    APIParserError,
    ParsingResult,
    ParsingDegradedError,
    SELECTORS,
)

logger = logging.getLogger(__name__)


class SectionParser:
    """
    Section 级解析器

    用于解析页面中特定的 section，如参数表格、返回值区域等
    """

    def __init__(self, html: str):
        """
        初始化解析器

        Args:
            html: HTML 内容
        """
        self.soup = BeautifulSoup(html, "html.parser")
        self._cache: Dict[str, Any] = {}

    def parse_function_signature(self) -> Optional[str]:
        """解析函数签名"""
        # 先尝试预定义的选择器
        for selector in SELECTORS["signature"]:
            elem = self.soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if "(" in text or "{" in text:
                    return text

        # 尝试通用的代码块
        code_blocks = self.soup.select("pre code, pre, code")
        for block in code_blocks:
            text = block.get_text(strip=True)
            if "(" in text and ("API" in text or "acl" in text or "ge::" in text):
                return text

        return None

    def parse_parameters(self) -> Optional[List[Dict[str, str]]]:
        """解析参数表格"""
        for selector in SELECTORS["parameters_table"]:
            table = self.soup.select_one(selector)
            if table:
                params = self._parse_html_table(table)
                if params:
                    return params

        # 尝试 dl (definition list) 格式
        dl = self.soup.select("dl.param-list, dl.parameters")
        if dl:
            return self._parse_dl_list(dl[0])

        return None

    def _parse_html_table(self, table: Tag) -> Optional[List[Dict[str, str]]]:
        """解析 HTML 表格"""
        params = []
        rows = table.select("tr")

        for row in rows:
            cols = row.select("td, th")
            if len(cols) >= 2:
                param_name = cols[0].get_text(strip=True)
                param_type = cols[1].get_text(strip=True) if len(cols) > 1 else ""

                # 跳过表头
                if param_name.lower() in ["参数名", "parameter", "name"]:
                    continue

                param_desc = ""
                if len(cols) > 2:
                    param_desc = cols[2].get_text(strip=True)

                param_required = "可选" not in param_desc and "optional" not in param_desc.lower()

                if param_name:
                    params.append({
                        "name": param_name,
                        "type": param_type,
                        "description": param_desc,
                        "required": param_required,
                    })

        return params if params else None

    def _parse_dl_list(self, dl: Tag) -> List[Dict[str, str]]:
        """解析 definition list"""
        params = []
        dts = dl.select("dt")
        dds = dl.select("dd")

        for dt, dd in zip(dts, dds):
            name = dt.get_text(strip=True)
            desc = dd.get_text(strip=True)

            # 尝试从 desc 中分离类型
            type_match = re.match(r"([\w]+):?\s*(.*)", desc)
            if type_match:
                param_type, param_desc = type_match.groups()
            else:
                param_type = ""
                param_desc = desc

            params.append({
                "name": name,
                "type": param_type,
                "description": param_desc,
                "required": True,
            })

        return params

    def parse_return_value(self) -> Optional[Dict[str, str]]:
        """解析返回值"""
        for selector in SELECTORS["return_value"]:
            elem = self.soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if text:
                    return {
                        "type": self._infer_return_type(text),
                        "description": text,
                    }

        # 尝试从函数签名推断
        sig = self.parse_function_signature()
        if sig:
            # 匹配 "返回值" 或 "返回" 相关内容
            return_match = re.search(r"返回[值类型]?\s*[:：]?\s*(\w+)", text)
            if return_match:
                return {
                    "type": return_match.group(1),
                    "description": text,
                }

        return None

    def _infer_return_type(self, text: str) -> str:
        """推断返回类型"""
        type_patterns = [
            (r"\bint\b", "int"),
            (r"\bvoid\b", "void"),
            (r"\bbool\b", "bool"),
            (r"\bfloat\b", "float"),
            (r"\bdouble\b", "double"),
            (r"\bstring\b", "string"),
            (r"\bint32_t\b", "int32"),
            (r"\bint64_t\b", "int64"),
            (r"\buint32_t\b", "uint32"),
            (r"\buint64_t\b", "uint64"),
            (r"aclError", "aclError"),
            (r"::", "class/struct"),
        ]

        for pattern, type_name in type_patterns:
            if re.search(pattern, text):
                return type_name

        return "unknown"

    def parse_description(self) -> str:
        """解析描述文本"""
        # 尝试多个位置
        for selector in SELECTORS["description"]:
            elem = self.soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if len(text) > 50:  # 确保有实质内容
                    return text

        # 尝试第一个 <p> 标签
        first_p = self.soup.find("p")
        if first_p:
            text = first_p.get_text(strip=True)
            if len(text) > 30:
                return text

        return ""

    def parse_examples(self) -> List[Dict[str, str]]:
        """解析使用示例"""
        examples = []

        for selector in SELECTORS["examples"]:
            elems = self.soup.select(selector)
            for i, elem in enumerate(elems[:5]):  # 最多5个
                code = elem.get_text(strip=True)
                if len(code) > 20:  # 确保是真正的示例
                    # 提取语言标记（如果有）
                    lang = elem.get("class", [])
                    language = ""
                    for c in lang:
                        if c.startswith("language-"):
                            language = c.replace("language-", "")
                            break

                    examples.append({
                        "scenario": f"示例 {i+1}",
                        "code": code,
                        "language": language,
                    })

        return examples

    def parse_cautions(self) -> List[str]:
        """解析注意事项"""
        cautions = []

        for selector in SELECTORS["cautions"]:
            elems = self.soup.select(selector)
            for elem in elems:
                text = elem.get_text(strip=True)
                if len(text) > 5:
                    cautions.append(text)

        return cautions

    def find_section(self, section_name: str) -> Optional[Tag]:
        """
        查找特定 section

        Args:
            section_name: section 名称 (如 "参数", "返回值", "示例")

        Returns:
            找到的 section 标签，或 None
        """
        # 常见 section 标题模式
        patterns = [
            rf"<h[1-6][^>]*>\s*{section_name}\s*</h[1-6]>",
            rf"<div[^>]*class[^>]*\b{ section_name }\b[^>]*>",
            rf"<section[^>]*id[^>]*\b{ section_name }\b[^>]*>",
        ]

        for pattern in patterns:
            match = self.soup.search(pattern)
            if match:
                # 返回找到的标签
                start, end = match.start(), match.end()
                for tag in self.soup.find_all(True):
                    if str(tag) in str(self.soup)[start:end]:
                        return tag

        # 降级：模糊匹配
        for tag in self.soup.find_all(["h1", "h2", "h3", "h4"]):
            if section_name in tag.get_text():
                return tag

        return None

    def get_table_of_contents(self) -> Dict[str, str]:
        """提取目录结构"""
        toc = {}

        for tag in self.soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            text = tag.get_text(strip=True)
            if text and len(text) < 100:  # 过滤掉太长的标题
                toc[text] = str(tag.get("id", "") or text)

        return toc
