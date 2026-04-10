# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
API 链接发现器单元测试
"""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from asc_ops.collector.link_discovery import (
    APILink,
    LinkDiscoveryResult,
    LinkDiscoveryError,
    RateLimitError,
    _generate_api_id,
    _infer_category,
    discover_api_links,
)


class TestAPILink:
    """APILink 数据类测试"""

    def test_api_link_creation(self):
        """测试 APILink 创建"""
        link = APILink(
            api_id="abc123",
            name="test_api",
            url="https://example.com/api/test",
            category="memory",
        )
        assert link.api_id == "abc123"
        assert link.name == "test_api"
        assert link.url == "https://example.com/api/test"
        assert link.category == "memory"
        assert link.subcategory == ""

    def test_api_link_with_subcategory(self):
        """测试带子分类的 APILink"""
        link = APILink(
            api_id="def456",
            name="tensor_alloc",
            url="https://example.com/tensor/alloc",
            category="memory",
            subcategory="tensor",
        )
        assert link.subcategory == "tensor"


class TestLinkDiscoveryResult:
    """LinkDiscoveryResult 测试"""

    def test_result_creation(self):
        """测试结果创建"""
        result = LinkDiscoveryResult(
            total=100,
            new_links=[],
            removed_links=[],
            cached_links=[],
            discovery_time=1.5,
        )
        assert result.total == 100
        assert result.discovery_time == 1.5


class TestGenerateApiId:
    """API ID 生成测试"""

    def test_same_url_name_produces_same_id(self):
        """相同 URL 和名称产生相同 ID"""
        id1 = _generate_api_id("https://example.com/api/test", "test_api")
        id2 = _generate_api_id("https://example.com/api/test", "test_api")
        assert id1 == id2

    def test_different_url_produces_different_id(self):
        """不同 URL 产生不同 ID"""
        id1 = _generate_api_id("https://example.com/api/test1", "test_api")
        id2 = _generate_api_id("https://example.com/api/test2", "test_api")
        assert id1 != id2

    def test_id_is_16_chars(self):
        """生成的 ID 长度为 16"""
        api_id = _generate_api_id("https://example.com/api/test", "test_api")
        assert len(api_id) == 16


class TestInferCategory:
    """分类推断测试"""

    def test_memory_category(self):
        """内存分类推断"""
        category, subcategory = _infer_category("/memory/alloc", "test")
        assert category == "memory"

    def test_compute_category(self):
        """计算分类推断"""
        category, subcategory = _infer_category("/compute/operator", "test")
        assert category == "compute"

    def test_sync_category(self):
        """同步分类推断"""
        category, subcategory = _infer_category("/sync/event", "test")
        assert category == "sync"

    def test_tensor_category(self):
        """张量分类推断"""
        category, subcategory = _infer_category("/tensor/ndarray", "test")
        assert category == "tensor"

    def test_default_category(self):
        """默认分类"""
        category, subcategory = _infer_category("/unknown/path", "test")
        assert category == "util"


class TestDiscoverApiLinks:
    """discover_api_links 函数测试"""

    @pytest.fixture
    def sample_html(self):
        """示例 HTML 页面"""
        return """
        <html>
            <body>
                <a href="/api/memory/alloc.html">aclMalloc</a>
                <a href="/api/compute/operator.html">ge::Operator</a>
                <a href="/api/sync/event.html">aclEvent</a>
            </body>
        </html>
        """

    @pytest.mark.asyncio
    async def test_discovers_all_links(self, sample_html):
        """测试发现所有链接"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.text = sample_html
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await discover_api_links("https://example.com/api-list.html")

            assert result.total == 3
            assert len(result.new_links) == 3
            assert len(result.removed_links) == 0

    @pytest.mark.asyncio
    async def test_incremental_discovery(self, sample_html):
        """测试增量发现"""
        cached_ids = {"already_cached_id"}  # 假设一个已缓存的 ID

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.text = sample_html
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock _generate_api_id to return predictable IDs
            # Sample HTML has 3 links, return different IDs for each
            call_count = [0]
            def generate_id(url, name):
                ids = ["id1", "id2", "id3"]
                result = ids[call_count[0] % 3]
                call_count[0] += 1
                return result

            with patch("asc_ops.collector.link_discovery._generate_api_id", side_effect=generate_id):
                result = await discover_api_links(
                    "https://example.com/api-list.html",
                    cached_api_ids=cached_ids,
                )

                # 3 links discovered, none match cached_ids
                assert result.total == 3
                assert len(result.cached_links) == 0
                assert len(result.new_links) == 3

    @pytest.mark.asyncio
    async def test_detects_removed_links(self, sample_html):
        """测试检测移除的链接"""
        cached_ids = {"cached_id_1", "cached_id_2"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.text = sample_html
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock to return IDs that don't match cached
            with patch("asc_ops.collector.link_discovery._generate_api_id", return_value="new_id"):
                result = await discover_api_links(
                    "https://example.com/api-list.html",
                    cached_api_ids=cached_ids,
                )

                assert len(result.removed_links) == 2

    @pytest.mark.asyncio
    async def test_rate_limit_error(self):
        """测试限流错误"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.headers = {}
            mock_client.get.return_value = mock_response

            def raise_for_status():
                raise httpx.HTTPStatusError(
                    "Rate limited",
                    request=MagicMock(),
                    response=mock_response,
                )
            mock_response.raise_for_status = raise_for_status
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(RateLimitError):
                await discover_api_links("https://example.com/api-list.html")

    @pytest.mark.asyncio
    async def test_http_error(self):
        """测试 HTTP 错误"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_client.get.return_value = mock_response

            def raise_for_status():
                raise httpx.HTTPStatusError(
                    "Server error",
                    request=MagicMock(),
                    response=mock_response,
                )
            mock_response.raise_for_status = raise_for_status
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(LinkDiscoveryError):
                await discover_api_links("https://example.com/api-list.html")


class TestParseApiListPage:
    """页面解析测试"""

    def test_parses_api_links(self):
        """测试解析 API 链接"""
        from asc_ops.collector.link_discovery import _parse_api_list_page

        html = """
        <html>
            <body>
                <a href="/api/memory/alloc.html">aclMalloc</a>
                <a href="/api/compute/operator.html">ge::Operator</a>
            </body>
        </html>
        """
        links = _parse_api_list_page(html, "https://example.com")
        assert len(links) == 2
        assert links[0].name == "aclMalloc"
        assert links[1].name == "ge::Operator"

    def test_skips_anchor_links(self):
        """测试跳过锚点链接"""
        from asc_ops.collector.link_discovery import _parse_api_list_page

        html = """
        <html>
            <body>
                <a href="#section">Skip this</a>
                <a href="/api/test.html">Valid API</a>
            </body>
        </html>
        """
        links = _parse_api_list_page(html, "https://example.com")
        assert len(links) == 1
        assert links[0].name == "Valid API"

    def test_handles_relative_urls(self):
        """测试处理相对 URL"""
        from asc_ops.collector.link_discovery import _parse_api_list_page

        html = """
        <html>
            <body>
                <a href="/api/test.html">Relative Link</a>
            </body>
        </html>
        """
        links = _parse_api_list_page(html, "https://example.com/docs/")
        assert len(links) == 1
        assert links[0].url == "https://example.com/api/test.html"
