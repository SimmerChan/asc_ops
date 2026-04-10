# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
自适应限速模块

根据响应时间动态调整请求间隔
"""

import asyncio
import time
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """限速配置"""
    initial_interval: float = 0.5  # 初始间隔 (秒)
    min_interval: float = 0.1  # 最小间隔 (秒)
    max_interval: float = 10.0  # 最大间隔 (秒)
    rate_limit_backoff_multiplier: float = 3.0  # 触发限流时的退避乘数
    slow_response_threshold: float = 2.0  # 慢响应阈值 (秒)
    fast_response_threshold: float = 0.3  # 快响应阈值 (秒)


class AdaptiveRateLimiter:
    """
    自适应限速器

    根据服务器响应时间动态调整请求间隔
    """

    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        初始化限速器

        Args:
            config: 限速配置
        """
        self.config = config or RateLimitConfig()
        self._interval = self.config.initial_interval
        self._last_request_time: float = 0
        self._rate_limit_triggered: bool = False
        self._consecutive_slow: int = 0
        self._consecutive_fast: int = 0

        logger.info(
            f"AdaptiveRateLimiter initialized: "
            f"initial_interval={self._interval}s"
        )

    async def acquire(self) -> None:
        """
        获取请求许可 (等待直到可以发送请求)
        """
        now = time.time()
        elapsed = now - self._last_request_time

        if elapsed < self._interval:
            wait_time = self._interval - elapsed
            logger.debug(f"Rate limiting: waiting {wait_time:.3f}s")
            await asyncio.sleep(wait_time)

        self._last_request_time = time.time()

    def record_response_time(self, response_time: float) -> None:
        """
        记录响应时间并调整间隔

        Args:
            response_time: 响应时间 (秒)
        """
        if response_time > self.config.slow_response_threshold:
            # 响应太慢，增加间隔
            self._interval = min(
                self._interval * 1.2,
                self.config.max_interval
            )
            self._consecutive_slow += 1
            self._consecutive_fast = 0

            if self._consecutive_slow >= 3:
                logger.warning(
                    f"Slow responses detected ({response_time:.3f}s), "
                    f"increasing interval to {self._interval:.3f}s"
                )
                self._consecutive_slow = 0

        elif response_time < self.config.fast_response_threshold:
            # 响应快，可以加速
            self._interval = max(
                self._interval * 0.9,
                self.config.min_interval
            )
            self._consecutive_fast += 1
            self._consecutive_slow = 0

        else:
            # 正常范围，保持不变
            self._consecutive_slow = 0
            self._consecutive_fast = 0

    def trigger_rate_limit(self) -> None:
        """
        触发限流，立即增加间隔
        """
        self._interval = min(
            self._interval * self.config.rate_limit_backoff_multiplier,
            self.config.max_interval
        )
        self._rate_limit_triggered = True
        logger.warning(
            f"Rate limit triggered, increasing interval to {self._interval:.3f}s"
        )

    def reset_rate_limit_state(self) -> None:
        """
        重置限流状态
        """
        self._rate_limit_triggered = False
        self._consecutive_slow = 0
        self._consecutive_fast = 0
        logger.debug("Rate limit state reset")

    @property
    def interval(self) -> float:
        """当前间隔"""
        return self._interval

    @property
    def is_rate_limited(self) -> bool:
        """是否处于限流状态"""
        return self._rate_limit_triggered

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "current_interval": self._interval,
            "is_rate_limited": self._rate_limit_triggered,
            "consecutive_slow": self._consecutive_slow,
            "consecutive_fast": self._consecutive_fast,
        }


class ConcurrencyLimiter:
    """
    并发限制器

    使用信号量控制并发数量
    """

    def __init__(self, max_concurrent: int = 10, max_queue_size: int = 1000):
        """
        初始化并发限制器

        Args:
            max_concurrent: 最大并发数
            max_queue_size: 最大队列大小
        """
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_concurrent = max_concurrent
        self._max_queue_size = max_queue_size
        self._active_count: int = 0
        self._queue_size: int = 0

        logger.info(
            f"ConcurrencyLimiter initialized: max_concurrent={max_concurrent}"
        )

    async def acquire(self) -> None:
        """
        获取执行许可

        等待直到有可用的并发 slot
        """
        if self._queue_size >= self._max_queue_size:
            raise QueueFullError(
                f"Queue is full (max: {self._max_queue_size})"
            )

        self._queue_size += 1
        try:
            await self._semaphore.acquire()
            self._active_count += 1
            self._queue_size -= 1
        except Exception:
            self._queue_size -= 1
            raise

    def release(self) -> None:
        """
        释放执行许可
        """
        self._active_count = max(0, self._active_count - 1)
        self._semaphore.release()

    async def __aenter__(self):
        """上下文管理器入口"""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.release()
        return False

    @property
    def active_count(self) -> int:
        """当前活跃的并发数"""
        return self._active_count

    @property
    def available_count(self) -> int:
        """可用的并发数"""
        return self._max_concurrent - self._active_count

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "max_concurrent": self._max_concurrent,
            "active_count": self._active_count,
            "available_count": self.available_count,
            "queue_size": self._queue_size,
        }


class QueueFullError(Exception):
    """队列已满"""
    pass
