# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
API 解析器单元测试
"""

import pytest

from asc_ops.collector.parsers import (
    ParsingResult,
    parse_api_page,
    APIParserError,
    ParsingDegradedError,
    _extract_signature,
    _extract_parameters,
    _extract_return_value,
    _extract_description,
    _extract_examples,
    _extract_cautions,
    is_markdown_page,
)
from bs4 import BeautifulSoup


class TestExtractSignature:
    """函数签名提取测试"""

    def test_extract_from_pre_code(self):
        """从 pre/code 标签提取"""
        html = '<html><body><pre class="signature">aclMalloc(void **addr, size_t size)</pre></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        sig = _extract_signature(soup)
        assert sig == "aclMalloc(void **addr, size_t size)"

    def test_extract_from_code(self):
        """从 code 标签提取"""
        html = '<html><body><code class="signature">ge::Operator::Operator()</code></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        sig = _extract_signature(soup)
        assert sig == "ge::Operator::Operator()"

    def test_no_signature(self):
        """未找到签名"""
        html = '<html><body><p>No signature here</p></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        sig = _extract_signature(soup)
        assert sig is None


class TestExtractParameters:
    """参数提取测试"""

    def test_extract_from_table(self):
        """从表格提取参数"""
        html = '''
        <html><body>
        <table class="params">
            <thead>
                <tr><th>参数名</th><th>类型</th><th>描述</th></tr>
            </thead>
            <tbody>
                <tr><td>addr</td><td>void **</td><td>内存地址</td></tr>
                <tr><td>size</td><td>size_t</td><td>内存大小</td></tr>
            </tbody>
        </table>
        </body></html>
        '''
        soup = BeautifulSoup(html, "html.parser")
        params = _extract_parameters(soup)
        assert params is not None
        assert len(params) == 2
        assert params[0].name == "addr"
        assert params[0].type == "void **"
        assert params[1].name == "size"
        assert params[1].type == "size_t"


class TestExtractReturnValue:
    """返回值提取测试"""

    def test_extract_return_value(self):
        """提取返回值"""
        html = '<html><body><div class="return-value">返回: aclError</div></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        rv = _extract_return_value(soup)
        assert rv is not None


class TestExtractDescription:
    """描述提取测试"""

    def test_extract_description(self):
        """提取描述"""
        html = '<html><body><div class="description">This is a detailed description of the API function.</div></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        desc = _extract_description(soup)
        assert "description" in desc.lower()


class TestExtractExamples:
    """示例提取测试"""

    def test_extract_examples(self):
        """提取使用示例"""
        html = '''
        <html><body>
        <pre class="example">aclMalloc(&addr, 1024);</pre>
        <pre class="example">void *ptr; aclMalloc(&ptr, 2048);</pre>
        </body></html>
        '''
        soup = BeautifulSoup(html, "html.parser")
        examples = _extract_examples(soup)
        assert len(examples) == 2
        assert "aclMalloc" in examples[0].code


class TestExtractCautions:
    """注意事项提取测试"""

    def test_extract_cautions(self):
        """提取注意事项"""
        html = '''
        <html><body>
        <div class="caution">注意：请在设备初始化后调用</div>
        <div class="warning">警告：不要重复释放内存</div>
        </body></html>
        '''
        soup = BeautifulSoup(html, "html.parser")
        cautions = _extract_cautions(soup)
        assert len(cautions) == 2


class TestIsMarkdownPage:
    """Markdown 页面检测测试"""

    def test_detects_markdown(self):
        """检测 Markdown 页面"""
        html = "<html><body><pre><code>code block</code></pre><h1>Header</h1></body></html>"
        assert is_markdown_page(html) is True

    def test_detects_non_markdown(self):
        """检测非 Markdown 页面"""
        html = "<html><body><div>Plain text</div></body></html>"
        assert is_markdown_page(html) is False


class TestParseApiPage:
    """完整 API 页面解析测试"""

    def test_parse_full_page(self):
        """完整解析 API 页面"""
        html = '''
        <html>
        <head><title>aclMalloc</title></head>
        <body>
            <h1>aclMalloc</h1>
            <pre class="signature">aclError aclMalloc(void **addr, size_t size)</pre>
            <table class="params">
                <thead>
                    <tr><th>参数名</th><th>类型</th><th>描述</th></tr>
                </thead>
                <tbody>
                    <tr><td>addr</td><td>void **</td><td>内存地址指针</td></tr>
                    <tr><td>size</td><td>size_t</td><td>分配大小</td></tr>
                </tbody>
            </table>
            <div class="return-value">返回: aclError</div>
            <div class="description">该函数用于在ACL设备上分配内存。这是一个重要的函数。</div>
            <pre class="example">aclMalloc(&ptr, 1024);</pre>
            <div class="caution">注意：分配失败返回错误码</div>
        </body>
        </html>
        '''
        result = parse_api_page(
            html=html,
            api_id="test123",
            name="aclMalloc",
            url="https://example.com/api/aclMalloc",
            category="memory",
        )

        assert result.success is True
        assert result.api_definition is not None
        assert result.api_definition.api_id == "test123"
        assert result.api_definition.canonical_name == "aclMalloc"
        assert result.api_definition.category == "memory"
        assert len(result.api_definition.parameters) == 2
        assert result.degraded is False

    def test_parse_degraded(self):
        """降级解析失败的页面"""
        html = '<html><body><p>Not a proper API page</p></body></html>'
        result = parse_api_page(
            html=html,
            api_id="test456",
            name="unknownApi",
            url="https://example.com/api/unknown",
            category="unknown",
        )

        # 降级解析也应该返回成功，但包含警告
        assert result.success is True
        assert result.api_definition is not None
        assert result.degraded is True
        assert result.api_definition.confidence < 1.0

    def test_parse_critical_failure(self):
        """严重解析失败"""
        result = parse_api_page(
            html=None,
            api_id="test789",
            name="brokenApi",
            url="https://example.com/api/broken",
        )

        assert result.success is False
        assert len(result.parse_errors) > 0


class TestParsingResult:
    """ParsingResult 数据类测试"""

    def test_result_with_api_definition(self):
        """带 API 定义的结果"""
        from asc_ops.models import AscendCAPIDefinition, APISourceInfo, APIReturnValue

        api_def = AscendCAPIDefinition(
            api_id="test",
            canonical_name="testApi",
            full_signature="testApi()",
            category="test",
            subcategory="",
            description="Test API",
            parameters=[],
            return_value=APIReturnValue(type="void", description=""),
            source=APISourceInfo(source_type="official", source_url=""),
        )

        result = ParsingResult(success=True, api_definition=api_def)
        assert result.success is True
        assert result.api_definition.api_id == "test"
        assert result.degraded is False

    def test_result_with_errors(self):
        """带错误的结果"""
        result = ParsingResult(
            success=False,
            parse_errors=["Error 1", "Error 2"],
        )
        assert result.success is False
        assert len(result.parse_errors) == 2
