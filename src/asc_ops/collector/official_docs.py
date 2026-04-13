# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
昇腾官方文档 HTTP 客户端

封装对昇腾官方文档的 HTTP 请求，支持重试和限速
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)


class OfficialDocsClient:
    """
    昇腾官方文档 HTTP 客户端

    支持:
    - 自动重试 (指数退避)
    - 限速控制
    - 并发控制
    """

    def __init__(
        self,
        base_url: str = "https://www.hiascend.com",
        timeout: float = 30.0,
        max_retries: int = 3,
        initial_interval: float = 0.5,
    ):
        """
        初始化客户端

        Args:
            base_url: 文档基础 URL
            timeout: 请求超时时间
            max_retries: 最大重试次数
            initial_interval: 初始请求间隔
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.initial_interval = initial_interval

        self._client: Optional[httpx.AsyncClient] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._rate_interval = initial_interval
        self._last_request_time: float = 0

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def connect(self):
        """建立连接"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": "AscendC-Knowledge-Base/1.0 (Python/3.11)",
                },
            )
            self._semaphore = asyncio.Semaphore(10)  # 10 并发
        return self

    async def close(self):
        """关闭连接"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def fetch_page(
        self,
        path: str,
        retry_count: int = 0,
    ) -> str:
        """
        获取页面内容

        Args:
            path: 页面路径 (相对于 base_url) 或完整 URL
            retry_count: 当前重试次数

        Returns:
            页面 HTML 内容

        Raises:
            RateLimitError: 触发限流
            OfficialDocsError: 获取失败
        """
        if self._client is None:
            await self.connect()

        # 如果是完整 URL，直接使用；否则拼接 base_url
        if path.startswith("http://") or path.startswith("https://"):
            url = path
        else:
            url = f"{self.base_url}/{path.lstrip('/')}"

        try:
            # 限速控制
            await self._rate_limit()

            async with self._semaphore:
                response = await self._client.get(url)
                self._update_rate_interval(response.elapsed.total_seconds())

                if response.status_code == 429:
                    # 限流触发
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limit hit, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    return await self.fetch_page(path, retry_count)

                response.raise_for_status()
                return response.text

        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500 and retry_count < self.max_retries:
                # 服务器错误，重试
                wait_time = 2 ** retry_count
                logger.warning(f"Server error {e.response.status_code}, retrying in {wait_time}s")
                await asyncio.sleep(wait_time)
                return await self.fetch_page(path, retry_count + 1)

            logger.error(f"HTTP error fetching {url}: {e}")
            raise OfficialDocsError(f"HTTP error: {e}") from e

        except httpx.TimeoutException as e:
            if retry_count < self.max_retries:
                wait_time = 2 ** retry_count
                logger.warning(f"Timeout fetching {url}, retrying in {wait_time}s")
                await asyncio.sleep(wait_time)
                return await self.fetch_page(path, retry_count + 1)

            logger.error(f"Timeout fetching {url}: {e}")
            raise OfficialDocsError(f"Timeout: {e}") from e

        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            raise OfficialDocsError(f"Unexpected error: {e}") from e

    async def _rate_limit(self):
        """限速控制"""
        import time

        now = time.time()
        elapsed = now - self._last_request_time

        if elapsed < self._rate_interval:
            await asyncio.sleep(self._rate_interval - elapsed)

        self._last_request_time = time.time()

    def _update_rate_interval(self, response_time: float):
        """
        根据响应时间自适应调整请求间隔

        Args:
            response_time: 响应时间 (秒)
        """
        if response_time > 2.0:
            # 响应太慢，增加间隔
            self._rate_interval = min(self._rate_interval * 1.2, 10.0)
        elif response_time < 0.3:
            # 响应快，可以加速
            self._rate_interval = max(self._rate_interval * 0.9, 0.1)
        # 正常范围保持不变


class OfficialDocsError(Exception):
    """官方文档访问异常"""
    pass


class RateLimitError(OfficialDocsError):
    """触发限流"""
    pass
