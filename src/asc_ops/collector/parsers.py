# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
API 详情页解析器

解析 API 详情页，提取结构化信息
支持两级降级策略：完整解析 → 降级解析 → 原始 HTML
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

from bs4 import BeautifulSoup

from ..models import (
    AscendCAPIDefinition,
    APIParameter,
    APIReturnValue,
    UsageExample,
    APISourceInfo,
)

logger = logging.getLogger(__name__)


@dataclass
class ParsingResult:
    """解析结果"""
    success: bool
    api_definition: Optional[AscendCAPIDefinition] = None
    parse_errors: List[str] = field(default_factory=list)
    degraded: bool = False  # 是否降级解析
    raw_html: Optional[str] = None  # 降级时保留原始 HTML


class APIParserError(Exception):
    """API 解析异常"""
    pass


class ParsingDegradedError(APIParserError):
    """解析降级 (降级到只提取核心字段)"""
    pass


# API 详情页 CSS 选择器 (CANN 9.0.0-beta.2 页面结构)
SELECTORS = {
    "api_name": ["h1", ".article-title", "[class*='title']"],
    "breadcrumb": ["[class*='breadcrumb']", ".nav-path", "section[class*='article-bread']"],
    "signature": ["pre", "code", "[class*='signature']"],
    "hardware_support": ["table"],
    "parameters_table": ["table"],
    "return_value": ["h2", "h3", "p"],
    "examples": ["pre", "[class*='example']"],
    "cautions": ["[class*='caution']", "[class*='warning']"],
    "description": ["section[class*='content']", ".article-content", "p"],
}


def parse_api_page(
    html: str,
    api_id: str,
    name: str,
    url: str,
    category: str = "",
    subcategory: str = "",
) -> ParsingResult:
    """
    解析 API 详情页

    Args:
        html: 页面 HTML 内容
        api_id: API 唯一 ID
        name: API 名称
        url: API 页面 URL
        category: 分类
        subcategory: 子分类

    Returns:
        ParsingResult: 解析结果
    """
    errors: List[str] = []

    try:
        soup = BeautifulSoup(html, "html.parser")

        # 尝试完整解析
        try:
            api_def = _parse_full(soup, api_id, name, url, category, subcategory)
            return ParsingResult(success=True, api_definition=api_def)
        except ParsingDegradedError as e:
            # 降级解析
            logger.warning(f"Falling back to degraded parsing for {name}: {e}")
            return _parse_degraded(soup, api_id, name, url, category, subcategory, str(e))
        except Exception as e:
            errors.append(str(e))
            # 尝试降级解析
            logger.warning(f"Full parsing failed for {name}, trying degraded: {e}")
            return _parse_degraded(soup, api_id, name, url, category, subcategory, str(e))

    except Exception as e:
        logger.error(f"Failed to parse API page {url}: {e}")
        return ParsingResult(
            success=False,
            parse_errors=[f"Critical parsing error: {e}"],
        )


def _parse_full(
    soup: BeautifulSoup,
    api_id: str,
    name: str,
    url: str,
    category: str,
    subcategory: str,
) -> AscendCAPIDefinition:
    """
    完整解析 API 详情页

    Raises:
        ParsingDegradedError: 解析失败，触发降级
    """
    # 提取函数签名
    signature = _extract_signature(soup)
    if not signature:
        raise ParsingDegradedError("Cannot find function signature")

    # 提取参数列表
    parameters = _extract_parameters(soup)
    if parameters is None:
        parameters = []  # 允许空参数

    # 提取返回值
    return_value = _extract_return_value(soup)
    if return_value is None:
        return_value = APIReturnValue(type="void", description="无返回值")

    # 提取描述
    description = _extract_description(soup)

    # 提取使用示例
    examples = _extract_examples(soup)

    # 提取注意事项
    cautions = _extract_cautions(soup)

    return AscendCAPIDefinition(
        api_id=api_id,
        canonical_name=name,
        full_signature=signature,
        category=category,
        subcategory=subcategory,
        description=description,
        parameters=parameters,
        return_value=return_value,
        version_info="",
        usage_examples=examples,
        注意事项=cautions,
        禁忌=[],
        source=APISourceInfo(source_type="official", source_url=url),
        confidence=1.0,
        last_updated=datetime.now(),
    )


def _parse_degraded(
    soup: BeautifulSoup,
    api_id: str,
    name: str,
    url: str,
    category: str,
    subcategory: str,
    error_msg: str,
) -> ParsingResult:
    """
    降级解析 - 只提取核心字段
    """
    # 尝试提取名称 (从页面标题)
    page_title = soup.find("title")
    extracted_name = page_title.get_text(strip=True) if page_title else name

    # 提取面包屑分类
    breadcrumbs = _extract_breadcrumbs(soup)
    if breadcrumbs and not category:
        category = breadcrumbs[0] if breadcrumbs else category

    # 生成最小签名
    signature = f"{name}()"  # 降级时使用简单签名

    api_def = AscendCAPIDefinition(
        api_id=api_id,
        canonical_name=name,
        full_signature=signature,
        category=category,
        subcategory=subcategory,
        description=f"[降级解析] {error_msg}",
        parameters=[],
        return_value=APIReturnValue(type="unknown", description="解析失败"),
        version_info="",
        usage_examples=[],
        注意事项=["[降级解析] 详细信息无法解析"],
        禁忌=[],
        source=APISourceInfo(source_type="official", source_url=url),
        confidence=0.3,  # 低置信度
        last_updated=datetime.now(),
    )

    return ParsingResult(
        success=True,
        api_definition=api_def,
        parse_errors=[f"Degraded parsing: {error_msg}"],
        degraded=True,
        raw_html=str(soup)[:5000] if soup else None,  # 保留部分原始 HTML
    )


def _extract_signature(soup: BeautifulSoup) -> Optional[str]:
    """提取函数签名"""
    for selector in SELECTORS["signature"]:
        elems = soup.select(selector)
        for elem in elems:
            text = elem.get_text(strip=True)
            # 跳过只有数字（行号）或太短的元素
            if not text or len(text) < 10:
                continue
            # 检查是否是行号（大部分是数字）
            if text.replace('\n', '').replace(' ', '').isdigit():
                continue
            # 检查是否包含函数签名特征
            if "(" in text or "{" in text:
                return text
    return None


def _extract_parameters(soup: BeautifulSoup) -> Optional[List[APIParameter]]:
    """提取参数列表"""
    for selector in SELECTORS["parameters_table"]:
        tables = soup.select(selector)
        for table in tables:
            params = _parse_parameters_table(table)
            if params is not None and len(params) > 0:
                return params
    return None


def _parse_parameters_table(table) -> Optional[List[APIParameter]]:
    """解析参数表格"""
    params = []

    # 查找表头行（可能在 thead 或 table 的第一行）
    header_row = table.select_one("thead tr")
    if not header_row:
        # 如果没有 thead，使用第一行作为表头
        rows = table.select("tr")
        if rows:
            header_row = rows[0]

    # 获取表头列名
    header_cols = []
    if header_row:
        for th in header_row.select("th"):
            header_cols.append(th.get_text(strip=True).lower())

    # 查找数据行（在 tbody 或 thead 之后）
    data_rows = []
    tbody = table.select_one("tbody")
    if tbody:
        data_rows = tbody.select("tr")
    else:
        # 没有 tbody，查找 thead 之后的 tr
        all_rows = table.select("tr")
        if len(all_rows) > 1:
            data_rows = all_rows[1:]  # 跳过表头

    if not data_rows:
        return None

    # 确定参数名和描述的列索引
    name_col_idx = 0
    desc_col_idx = 1

    for i, col_name in enumerate(header_cols):
        if "参数" in col_name or "名称" in col_name or "name" in col_name:
            name_col_idx = i
        if "描述" in col_name or "说明" in col_name or "desc" in col_name:
            desc_col_idx = i

    for row in data_rows:
        cols = row.select("td")
        if len(cols) >= max(name_col_idx, desc_col_idx) + 1:
            param_name = cols[name_col_idx].get_text(strip=True)
            param_desc = cols[desc_col_idx].get_text(strip=True)

            # 跳过表头行或无效行
            if not param_name or param_name in ["参数名", "参数说明"]:
                continue

            # 跳过纯数字的行号行
            if param_name.replace("\n", "").isdigit():
                continue

            params.append(APIParameter(
                name=param_name,
                type="",  # 参数表格通常只有名称和描述
                description=param_desc,
                required=True,
            ))

    return params if params else None


def _extract_return_value(soup: BeautifulSoup) -> Optional[APIReturnValue]:
    """提取返回值"""
    for selector in SELECTORS["return_value"]:
        elem = soup.select_one(selector)
        if elem:
            text = elem.get_text(strip=True)
            if text:
                # 简单解析: "返回值类型: 描述" 或 "返回: 类型"
                return APIReturnValue(type="inferred", description=text)
    return None


def _extract_description(soup: BeautifulSoup) -> str:
    """提取描述"""
    for selector in SELECTORS["description"]:
        elem = soup.select_one(selector)
        if elem:
            text = elem.get_text(strip=True)
            if len(text) > 20:  # 排除太短的
                return text
    return ""


def _extract_examples(soup: BeautifulSoup) -> List[UsageExample]:
    """提取使用示例"""
    examples = []
    seen_codes: set[str] = set()  # 避免重复

    for selector in SELECTORS["examples"]:
        elems = soup.select(selector)
        for elem in elems:
            code = elem.get_text(strip=True)
            if len(code) > 10 and code not in seen_codes:
                seen_codes.add(code)
                examples.append(UsageExample(
                    scenario=f"示例 {len(examples) + 1}",
                    code=code,
                ))
                if len(examples) >= 3:  # 最多3个示例
                    break
        if len(examples) >= 3:
            break

    return examples


def _extract_cautions(soup: BeautifulSoup) -> List[str]:
    """提取注意事项"""
    cautions = []
    for selector in SELECTORS["cautions"]:
        elems = soup.select(selector)
        for elem in elems:
            text = elem.get_text(strip=True)
            if text and len(text) > 5:
                cautions.append(text)
    return cautions


def _extract_breadcrumbs(soup: BeautifulSoup) -> List[str]:
    """提取面包屑导航"""
    breadcrumbs = []
    for selector in SELECTORS.get("breadcrumb", SELECTORS.get("category", [])):
        elem = soup.select_one(selector)
        if elem:
            # 分割面包屑文本
            text = elem.get_text(strip=True)
            parts = re.split(r"[>/\\]", text)
            breadcrumbs.extend([p.strip() for p in parts if p.strip()])
    return breadcrumbs


def is_markdown_page(html: str) -> bool:
    """检测是否为 Markdown 渲染页面"""
    # Markdown 页面通常有一些特征
    md_indicators = [
        "<code>",
        "<pre>",
        "<h1>",
        "<h2>",
        # 检查是否主要是 pre/code 标签
    ]
    return any(indicator in html for indicator in md_indicators)
