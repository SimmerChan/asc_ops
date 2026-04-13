# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
API 链接发现器

从昇腾官方文档列表页发现所有 API 链接，支持增量发现
"""

import logging
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional, Set
from datetime import datetime
from urllib.parse import urljoin

import httpx

from ..config import get_config

logger = logging.getLogger(__name__)


@dataclass
class APILink:
    """API 链接信息"""
    api_id: str  # 基于 URL 生成的唯一 ID
    name: str  # API 名称
    url: str  # 详情页 URL
    category: str  # 分类 (memory/compute/sync/tensor/util)
    subcategory: str = ""  # 子分类
    discovered_at: datetime = field(default_factory=datetime.now)


@dataclass
class LinkDiscoveryResult:
    """链接发现结果"""
    total: int
    new_links: List[APILink]
    removed_links: List[str]  # api_ids that no longer exist
    cached_links: List[APILink]  # previously known links
    discovery_time: float  # seconds elapsed


class LinkDiscoveryError(Exception):
    """链接发现异常"""
    pass


class RateLimitError(LinkDiscoveryError):
    """触发限流"""
    pass


# 昇腾官方 CANN API 文档列表页
# CANN 9.0.0-beta.2 版本
DEFAULT_API_LIST_URL = "https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/API/ascendcopapi/atlasascendc_api_07_0003.html"

# 分类映射 (从 URL 或页面内容推断)
CATEGORY_PATTERNS = {
    "memory": ["内存", "memory", "buffer", "alloc"],
    "compute": ["计算", "compute", "operator", "算子"],
    "sync": ["同步", "sync", "event", "stream"],
    "tensor": ["张量", "tensor", "ndarray"],
    "util": ["工具", "util", "helper", "common"],
}


def _generate_api_id(url: str, name: str) -> str:
    """基于 URL 和名称生成唯一 API ID"""
    content = f"{url}:{name}".encode("utf-8")
    return hashlib.sha256(content).hexdigest()[:16]


def _infer_category(url: str, name: str = "") -> tuple[str, str]:
    """从 URL 或名称推断分类"""
    url_lower = (url + name).lower()

    for category, patterns in CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if pattern.lower() in url_lower:
                return category, ""
    return "util", ""


async def discover_api_links(
    list_page_url: str,
    cached_api_ids: Optional[Set[str]] = None,
    timeout: float = 30.0,
) -> LinkDiscoveryResult:
    """
    从 API 列表页发现所有 API 链接

    Args:
        list_page_url: API 列表页 URL
        cached_api_ids: 已知的 API ID 集合，用于增量发现
        timeout: 请求超时时间 (秒)

    Returns:
        LinkDiscoveryResult: 包含新增、移除和已缓存的链接

    Raises:
        LinkDiscoveryError: 发现失败
        RateLimitError: 触发限流
    """
    start_time = datetime.now()
    cached_api_ids = cached_api_ids or set()

    new_links: List[APILink] = []
    removed_links: List[str] = []
    cached_links: List[APILink] = []

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            logger.info(f"Fetching API list page: {list_page_url}")
            response = await client.get(list_page_url)
            response.raise_for_status()

            # 解析页面提取 API 链接
            discovered = _parse_api_list_page(response.text, list_page_url)

            # 分类新增和移除的链接
            for link in discovered:
                if link.api_id in cached_api_ids:
                    cached_links.append(link)
                else:
                    new_links.append(link)

            # 检测移除的链接 (之前存在但现在不在列表中)
            discovered_ids = {link.api_id for link in discovered}
            removed_links = list(cached_api_ids - discovered_ids)

            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"Link discovery completed: {len(new_links)} new, "
                f"{len(removed_links)} removed, {len(cached_links)} cached, "
                f"elapsed {elapsed:.2f}s"
            )

            return LinkDiscoveryResult(
                total=len(discovered),
                new_links=new_links,
                removed_links=removed_links,
                cached_links=cached_links,
                discovery_time=elapsed,
            )

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            logger.warning(f"Rate limit hit: {e}")
            raise RateLimitError(f"Rate limit exceeded: {e}") from e
        logger.error(f"HTTP error during link discovery: {e}")
        raise LinkDiscoveryError(f"HTTP error: {e}") from e
    except httpx.TimeoutException as e:
        logger.error(f"Timeout during link discovery: {e}")
        raise LinkDiscoveryError(f"Timeout: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error during link discovery: {e}")
        raise LinkDiscoveryError(f"Unexpected error: {e}") from e


def _parse_api_list_page(html: str, base_url: str) -> List[APILink]:
    """
    解析 API 列表页，提取所有 API 链接

    Args:
        html: 页面 HTML 内容
        base_url: 基础 URL，用于处理相对链接

    Returns:
        API 链接列表
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    links: List[APILink] = []

    # 查找 API 链接的模式
    # 只选择包含 atlasascendc_api_07_XXXX.html 的链接
    # 排除 .xml 链接（错误的）
    api_link_selectors = [
        "a[href*='/ascendc']",
        ".api-item a",
        ".api-link",
        "table a",
    ]

    found_links = set()
    for selector in api_link_selectors:
        for a_tag in soup.select(selector):
            href = a_tag.get("href", "")
            name = a_tag.get_text(strip=True)

            if not href or not name:
                continue

            # 跳过锚点链接和 JavaScript 链接
            if href.startswith("#") or href.startswith("javascript:"):
                continue

            # 只保留 .html 链接，排除 .xml 链接
            if ".html" not in href or ".xml" in href:
                continue

            # 构建完整 URL
            full_url = urljoin(base_url, href)

            # 生成 API ID
            api_id = _generate_api_id(full_url, name)

            # 避免重复
            if api_id in found_links:
                continue
            found_links.add(api_id)

            # 推断分类
            category, subcategory = _infer_category(full_url, name)

            links.append(APILink(
                api_id=api_id,
                name=name,
                url=full_url,
                category=category,
                subcategory=subcategory,
            ))

    logger.debug(f"Parsed {len(links)} API links from page")
    return links
