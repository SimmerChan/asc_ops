# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
重试模块

提供指数退避重试能力
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Callable, TypeVar, Optional, Any
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryStrategy(Enum):
    """重试策略"""
    TIMEOUT = "timeout"  # 网络超时
    RATE_LIMIT = "rate_limit"  # 限流
    SERVER_ERROR = "server_error"  # 服务器错误


@dataclass
class RetryConfig:
    """重试配置"""
    # Timeout 重试配置
    timeout_max_retries: int = 3
    timeout_base_delay: float = 1.0  # 1s, 2s, 4s

    # RateLimit 重试配置
    rate_limit_max_retries: int = 5
    rate_limit_base_delay: float = 10.0  # 10s, 20s, 40s, 80s, 160s

    # ServerError 重试配置
    server_error_max_retries: int = 3
    server_error_base_delay: float = 2.0  # 2s, 4s, 8s

    # 通用配置
    max_total_retries: int = 10


@dataclass
class RetryState:
    """重试状态"""
    attempt: int = 0
    strategy: RetryStrategy = RetryStrategy.TIMEOUT
    last_error: str = ""
    last_attempt_at: Optional[datetime] = None
    total_retries: int = 0


class RetryExhaustedError(Exception):
    """重试次数耗尽"""
    pass


class RetryContext:
    """重试上下文"""

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.state = RetryState()

    def should_retry(self, strategy: RetryStrategy) -> bool:
        """判断是否应该重试"""
        if self.state.total_retries >= self.config.max_total_retries:
            return False

        max_retries = self._get_max_retries(strategy)
        return self.state.attempt < max_retries

    def _get_max_retries(self, strategy: RetryStrategy) -> int:
        """获取策略对应的最大重试次数"""
        if strategy == RetryStrategy.TIMEOUT:
            return self.config.timeout_max_retries
        elif strategy == RetryStrategy.RATE_LIMIT:
            return self.config.rate_limit_max_retries
        elif strategy == RetryStrategy.SERVER_ERROR:
            return self.config.server_error_max_retries
        return 0

    def get_delay(self, strategy: RetryStrategy) -> float:
        """计算延迟时间"""
        base_delay = self._get_base_delay(strategy)
        return base_delay * (2 ** self.state.attempt)

    def _get_base_delay(self, strategy: RetryStrategy) -> float:
        """获取基础延迟"""
        if strategy == RetryStrategy.TIMEOUT:
            return self.config.timeout_base_delay
        elif strategy == RetryStrategy.RATE_LIMIT:
            return self.config.rate_limit_base_delay
        elif strategy == RetryStrategy.SERVER_ERROR:
            return self.config.server_error_base_delay
        return 1.0

    def record_attempt(self, strategy: RetryStrategy, error: str):
        """记录尝试"""
        self.state.attempt += 1
        self.state.strategy = strategy
        self.state.last_error = error
        self.state.last_attempt_at = datetime.now()
        self.state.total_retries += 1

    def reset(self):
        """重置状态"""
        self.state = RetryState()


async def retry_with_backoff(
    func: Callable[..., T],
    *args,
    strategy: RetryStrategy = RetryStrategy.TIMEOUT,
    context: Optional[RetryContext] = None,
    **kwargs,
) -> T:
    """
    带指数退避的重试

    Args:
        func: 要重试的函数
        *args: 函数参数
        strategy: 重试策略
        context: 重试上下文
        **kwargs: 函数关键字参数

    Returns:
        函数返回值

    Raises:
        RetryExhaustedError: 重试次数耗尽
    """
    context = context or RetryContext()
    context.reset()

    while True:
        try:
            # 如果是异步函数
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            return result

        except Exception as e:
            error_msg = str(e)

            # 判断错误类型
            detected_strategy = _detect_error_strategy(e)

            # 记录尝试
            context.record_attempt(detected_strategy, error_msg)

            # 检查是否应该重试
            if not context.should_retry(detected_strategy):
                logger.error(
                    f"Retry exhausted after {context.state.total_retries} attempts. "
                    f"Last error: {error_msg}"
                )
                raise RetryExhaustedError(
                    f"Retry exhausted: {error_msg}"
                ) from e

            # 计算延迟
            delay = context.get_delay(detected_strategy)

            logger.warning(
                f"Retry attempt {context.state.attempt}/{context._get_max_retries(detected_strategy)} "
                f"for {detected_strategy.value} after {delay}s. Error: {error_msg}"
            )

            # 等待
            await asyncio.sleep(delay)


def _detect_error_strategy(error: Exception) -> RetryStrategy:
    """
    检测错误类型并返回对应的重试策略

    Args:
        error: 异常

    Returns:
        重试策略
    """
    error_str = str(error).lower()

    # 检测限流
    if "429" in error_str or "rate limit" in error_str or "too many requests" in error_str:
        return RetryStrategy.RATE_LIMIT

    # 检测服务器错误
    if hasattr(error, "status_code"):
        status_code = getattr(error, "status_code", 0)
        if 500 <= status_code < 600:
            return RetryStrategy.SERVER_ERROR

    # 检测超时
    if "timeout" in error_str or "timed out" in error_str:
        return RetryStrategy.TIMEOUT

    # 默认使用 TIMEOUT 策略
    return RetryStrategy.TIMEOUT
