# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
LLM Exception Types

Provider 异常映射到统一异常类型
"""


class LLMException(Exception):
    """LLM 操作基础异常"""

    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        details: dict = None,
    ):
        self.provider = provider
        self.details = details or {}
        super().__init__(message)


class LLMConfigurationError(LLMException):
    """配置错误：缺少 API key 或无效配置"""

    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        details: dict = None,
    ):
        super().__init__(message, provider, details)


class LLMResponseError(LLMException):
    """API 返回错误（4xx，非限流）"""

    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        status_code: int = None,
        details: dict = None,
    ):
        self.status_code = status_code
        super().__init__(message, provider, details)


class LLMRateLimitError(LLMException):
    """限流（429）"""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        provider: str = "unknown",
        retry_after: int = None,
        details: dict = None,
    ):
        self.retry_after = retry_after  # 秒
        super().__init__(message, provider, details)


class LLMTimeoutError(LLMException):
    """请求超时"""

    def __init__(
        self,
        message: str = "Request timeout",
        provider: str = "unknown",
        timeout: float = None,
        details: dict = None,
    ):
        self.timeout = timeout
        super().__init__(message, provider, details)


class LLMUnsupportedError(LLMException):
    """Provider 不支持该功能"""

    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        details: dict = None,
    ):
        super().__init__(message, provider, details)
