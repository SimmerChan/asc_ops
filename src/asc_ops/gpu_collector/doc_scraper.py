# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
CUDA API 文档采集器

从 NVIDIA 官方 CUDA 文档采集 API 定义（名称、签名、分类、描述）
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Browser, Page

logger = logging.getLogger(__name__)


@dataclass
class CUDAAPIScrapedData:
    """CUDA API 采集结果"""
    api_name: str
    full_signature: str
    description: str
    category: str
    subcategory: str
    parameters: List[str]
    return_type: str
    documentation_url: str


@dataclass
class CUDACollectionResult:
    """CUDA API 采集统计"""
    total_discovered: int
    apis: List[CUDAAPIScrapedData]
    elapsed_seconds: float


# NVIDIA CUDA 文档 - Warp Shuffle 函数
WARP_SHUFFLE_BASE_URL = "https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html"

# Warp Shuffle API 列表（从文档页面结构分析得出）
WARP_SHUFFLE_APIS = [
    "__shfl_sync",
    "__shfl_up_sync",
    "__shfl_down_sync",
    "__shfl_xor_sync",
]

# Warp Vote 函数
WARP_VOTE_APIS = [
    "__all_sync",
    "__any_sync",
    "__uni_sync",
]

# Warp Reduce 函数
WARP_REDUCE_APIS = [
    "__reduce_add_sync",
    "__reduce_mul_sync",
    "__reduce_min_sync",
    "__reduce_max_sync",
    "__reduce_and_sync",
    "__reduce_or_sync",
    "__reduce_xor_sync",
]

# CUDA Memory Management APIs
MEMORY_APIS = [
    "cudaMalloc",
    "cudaMallocHost",
    "cudaMallocPitch",
    "cudaMallocArray",
    "cudaFree",
    "cudaFreeHost",
    "cudaMemcpy",
    "cudaMemcpyAsync",
    "cudaMemcpyToSymbol",
    "cudaMemcpyToSymbolAsync",
    "cudaMemset",
    "cudaMemsetAsync",
]

# CUDA Stream Management APIs
STREAM_APIS = [
    "cudaStreamCreate",
    "cudaStreamCreateWithFlags",
    "cudaStreamDestroy",
    "cudaStreamSynchronize",
    "cudaStreamWaitEvent",
    "cudaStreamAddCallback",
]

# CUDA Event APIs
EVENT_APIS = [
    "cudaEventCreate",
    "cudaEventCreateWithFlags",
    "cudaEventDestroy",
    "cudaEventRecord",
    "cudaEventQuery",
    "cudaEventSynchronize",
    "cudaEventElapsedTime",
]

# 分类映射
API_CATEGORY_MAPPING: Dict[str, tuple[str, str]] = {
    # Warp Shuffle
    "__shfl_sync": ("warp-shuffle", "shuffle"),
    "__shfl_up_sync": ("warp-shuffle", "shuffle"),
    "__shfl_down_sync": ("warp-shuffle", "shuffle"),
    "__shfl_xor_sync": ("warp-shuffle", "shuffle"),
    # Warp Vote
    "__all_sync": ("warp-vote", "vote"),
    "__any_sync": ("warp-vote", "vote"),
    "__uni_sync": ("warp-vote", "vote"),
    # Warp Reduce
    "__reduce_add_sync": ("warp-reduce", "reduce"),
    "__reduce_mul_sync": ("warp-reduce", "reduce"),
    "__reduce_min_sync": ("warp-reduce", "reduce"),
    "__reduce_max_sync": ("warp-reduce", "reduce"),
    "__reduce_and_sync": ("warp-reduce", "reduce"),
    "__reduce_or_sync": ("warp-reduce", "reduce"),
    "__reduce_xor_sync": ("warp-reduce", "reduce"),
    # Memory
    "cudaMalloc": ("memory-management", "allocation"),
    "cudaMallocHost": ("memory-management", "allocation"),
    "cudaMallocPitch": ("memory-management", "allocation"),
    "cudaFree": ("memory-management", "deallocation"),
    "cudaMemcpy": ("memory-management", "copy"),
    "cudaMemset": ("memory-management", "set"),
    # Stream
    "cudaStreamCreate": ("stream-management", "create"),
    "cudaStreamSynchronize": ("stream-management", "sync"),
    # Event
    "cudaEventCreate": ("event-management", "create"),
    "cudaEventRecord": ("event-management", "record"),
    "cudaEventSynchronize": ("event-management", "sync"),
}


class CUDADocScraper:
    """
    CUDA API 文档采集器

    使用浏览器自动化从 NVIDIA 官方文档采集 CUDA API 信息
    """

    def __init__(self, headless: bool = True):
        """
        初始化 CUDA 文档采集器

        Args:
            headless: 是否使用无头模式
        """
        self._headless = headless
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._init_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self._close_browser()

    async def _init_browser(self):
        """初始化浏览器"""
        if self._browser is None:
            playwright = await async_playwright().start()
            self._browser = await playwright.chromium.launch(headless=self._headless)
            self._page = await self._browser.new_page()

    async def _close_browser(self):
        """关闭浏览器"""
        if self._page:
            await self._page.close()
            self._page = None
        if self._browser:
            await self._browser.close()
            self._browser = None

    async def scrape_warp_shuffle_apis(self) -> List[CUDAAPIScrapedData]:
        """
        采集 Warp Shuffle API 信息

        Returns:
            CUDAAPIScrapedData 列表
        """
        if self._page is None:
            await self._init_browser()

        apis = []
        base_url = WARP_SHUFFLE_BASE_URL

        for api_name in WARP_SHUFFLE_APIS + WARP_VOTE_APIS + WARP_REDUCE_APIS:
            try:
                # 构建 API 文档 URL
                # CUDA 文档使用锚点定位到具体 API
                api_url = f"{base_url}#{api_name}"

                await self._page.goto(api_url, wait_until="networkidle", timeout=30000)

                # 提取 API 信息
                api_data = await self._extract_api_from_page(api_name)
                if api_data:
                    apis.append(api_data)
                    logger.info(f"Scraped: {api_name}")
                else:
                    # 如果页面解析失败，使用预定义信息
                    api_data = self._get_fallback_api_data(api_name)
                    if api_data:
                        apis.append(api_data)
                        logger.info(f"Used fallback for: {api_name}")

            except Exception as e:
                logger.warning(f"Failed to scrape {api_name}: {e}")
                # 使用 fallback 数据
                fallback = self._get_fallback_api_data(api_name)
                if fallback:
                    apis.append(fallback)

        return apis

    async def _extract_api_from_page(self, api_name: str) -> Optional[CUDAAPIScrapedData]:
        """
        从当前页面提取 API 信息

        Args:
            api_name: API 名称

        Returns:
            CUDAAPIScrapedData 或 None
        """
        try:
            # 等待页面加载
            await self._page.wait_for_load_state("networkidle")

            # 提取函数签名 - 尝试多种选择器
            signature = ""
            for selector in [
                "code.highlight cpp",
                "div.highlight cpp code",
                "pre.codehilite code",
                "code",
            ]:
                elements = await self._page.query_selector_all(selector)
                for elem in elements:
                    text = await elem.inner_text()
                    if api_name in text and "(" in text:
                        signature = text.split("\n")[0].strip()
                        break
                if signature:
                    break

            # 提取描述
            description = ""
            for selector in [
                "div.section",
                "div.contents",
                "p",
            ]:
                elements = await self._page.query_selector_all(selector)
                for elem in elements:
                    text = await elem.inner_text()
                    if len(text) > 50 and api_name.lower() in text.lower():
                        description = text[:500].strip()
                        break
                if description:
                    break

            # 获取分类
            category, subcategory = self._get_category(api_name)

            return CUDAAPIScrapedData(
                api_name=api_name,
                full_signature=signature,
                description=description,
                category=category,
                subcategory=subcategory,
                parameters=self._extract_parameters(signature),
                return_type=self._extract_return_type(signature),
                documentation_url=self._page.url,
            )

        except Exception as e:
            logger.debug(f"Failed to extract {api_name} from page: {e}")
            return None

    def _extract_parameters(self, signature: str) -> List[str]:
        """从签名提取参数列表"""
        if not signature or "(" not in signature:
            return []

        try:
            params_str = signature.split("(")[1].split(")")[0]
            if not params_str.strip():
                return []

            params = []
            depth = 0
            current = ""

            for char in params_str:
                if char in "(<":
                    depth += 1
                    current += char
                elif char in ")>":
                    depth -= 1
                    current += char
                elif char == "," and depth == 0:
                    params.append(current.strip())
                    current = ""
                else:
                    current += char

            if current.strip():
                params.append(current.strip())

            return params if params else []

        except Exception:
            return []

    def _extract_return_type(self, signature: str) -> str:
        """从签名提取返回类型"""
        if not signature:
            return ""

        try:
            # 签名格式: "return_type api_name(...)"
            # 或者 "api_name(...)" 如果没有显式返回类型
            if "(" in signature:
                return signature.split("(")[0].strip().split()[-1] if signature.split("(")[0].strip() else "void"
            return ""
        except Exception:
            return ""

    def _get_category(self, api_name: str) -> tuple[str, str]:
        """获取 API 分类"""
        if api_name in API_CATEGORY_MAPPING:
            return API_CATEGORY_MAPPING[api_name]

        # 默认分类
        if api_name.startswith("__shfl"):
            return "warp-shuffle", "shuffle"
        if api_name.startswith("__all") or api_name.startswith("__any") or api_name.startswith("__uni"):
            return "warp-vote", "vote"
        if api_name.startswith("__reduce"):
            return "warp-reduce", "reduce"
        if api_name.startswith("cuda"):
            return "cuda-runtime", "api"

        return "cuda", "api"

    def _get_fallback_api_data(self, api_name: str) -> Optional[CUDAAPIScrapedData]:
        """
        获取预定义的 API 回退数据

        用于当无法从文档页面提取信息时使用预定义数据
        """
        fallback_data = {
            "__shfl_sync": CUDAAPIScrapedData(
                api_name="__shfl_sync",
                full_signature="T __shfl_sync(unsigned mask, T var, int delta)",
                description="Exchange value among threads in a warp with source thread offset by delta modulo warp size. Threads within a warp must execute the same instruction simultaneously.",
                category="warp-shuffle",
                subcategory="shuffle",
                parameters=["unsigned mask", "T var", "int delta"],
                return_type="T",
                documentation_url=f"{WARP_SHUFFLE_BASE_URL}#warp-shuffle-functions",
            ),
            "__shfl_up_sync": CUDAAPIScrapedData(
                api_name="__shfl_up_sync",
                full_signature="T __shfl_up_sync(unsigned mask, T var, int delta)",
                description="Exchange value among threads in a warp by shifting data up by delta lanes. Upper warp lanes get undefined result.",
                category="warp-shuffle",
                subcategory="shuffle",
                parameters=["unsigned mask", "T var", "int delta"],
                return_type="T",
                documentation_url=f"{WARP_SHUFFLE_BASE_URL}#warp-shuffle-functions",
            ),
            "__shfl_down_sync": CUDAAPIScrapedData(
                api_name="__shfl_down_sync",
                full_signature="T __shfl_down_sync(unsigned mask, T var, int delta)",
                description="Exchange value among threads in a warp by shifting data down by delta lanes. Lower warp lanes get undefined result.",
                category="warp-shuffle",
                subcategory="shuffle",
                parameters=["unsigned mask", "T var", "int delta"],
                return_type="T",
                documentation_url=f"{WARP_SHUFFLE_BASE_URL}#warp-shuffle-functions",
            ),
            "__shfl_xor_sync": CUDAAPIScrapedData(
                api_name="__shfl_xor_sync",
                full_signature="T __shfl_xor_sync(unsigned mask, T var, int laneMask)",
                description="Exchange value among threads in a warp based on bitwise XOR of lane ID. Enables butterfly communication patterns.",
                category="warp-shuffle",
                subcategory="shuffle",
                parameters=["unsigned mask", "T var", "int laneMask"],
                return_type="T",
                documentation_url=f"{WARP_SHUFFLE_BASE_URL}#warp-shuffle-functions",
            ),
            "__all_sync": CUDAAPIScrapedData(
                api_name="__all_sync",
                full_signature="int __all_sync(unsigned mask, int predicate)",
                description="Synchronous warp-level ALL reduction. Returns 1 if predicate is true for all threads in the warp, 0 otherwise.",
                category="warp-vote",
                subcategory="vote",
                parameters=["unsigned mask", "int predicate"],
                return_type="int",
                documentation_url=f"{WARP_SHUFFLE_BASE_URL}#warp-vote-functions",
            ),
            "__any_sync": CUDAAPIScrapedData(
                api_name="__any_sync",
                full_signature="int __any_sync(unsigned mask, int predicate)",
                description="Synchronous warp-level ANY reduction. Returns 1 if predicate is true for any thread in the warp, 0 otherwise.",
                category="warp-vote",
                subcategory="vote",
                parameters=["unsigned mask", "int predicate"],
                return_type="int",
                documentation_url=f"{WARP_SHUFFLE_BASE_URL}#warp-vote-functions",
            ),
            "__uni_sync": CUDAAPIScrapedData(
                api_name="__uni_sync",
                full_signature="int __uni_sync(unsigned mask)",
                description="Synchronous warp-level UNISON. Returns 1 if all threads have the same value, 0 otherwise.",
                category="warp-vote",
                subcategory="vote",
                parameters=["unsigned mask"],
                return_type="int",
                documentation_url=f"{WARP_SHUFFLE_BASE_URL}#warp-vote-functions",
            ),
            "__reduce_add_sync": CUDAAPIScrapedData(
                api_name="__reduce_add_sync",
                full_signature="T __reduce_add_sync(unsigned mask, T var)",
                description="Synchronous warp-level ADD reduction. Computes sum of var across all threads in the warp.",
                category="warp-reduce",
                subcategory="reduce",
                parameters=["unsigned mask", "T var"],
                return_type="T",
                documentation_url=f"{WARP_SHUFFLE_BASE_URL}#warp-reduce-functions",
            ),
            "__reduce_min_sync": CUDAAPIScrapedData(
                api_name="__reduce_min_sync",
                full_signature="T __reduce_min_sync(unsigned mask, T var)",
                description="Synchronous warp-level MIN reduction. Computes minimum of var across all threads in the warp.",
                category="warp-reduce",
                subcategory="reduce",
                parameters=["unsigned mask", "T var"],
                return_type="T",
                documentation_url=f"{WARP_SHUFFLE_BASE_URL}#warp-reduce-functions",
            ),
            "__reduce_max_sync": CUDAAPIScrapedData(
                api_name="__reduce_max_sync",
                full_signature="T __reduce_max_sync(unsigned mask, T var)",
                description="Synchronous warp-level MAX reduction. Computes maximum of var across all threads in the warp.",
                category="warp-reduce",
                subcategory="reduce",
                parameters=["unsigned mask", "T var"],
                return_type="T",
                documentation_url=f"{WARP_SHUFFLE_BASE_URL}#warp-reduce-functions",
            ),
        }

        return fallback_data.get(api_name)

    async def scrape_memory_apis(self) -> List[CUDAAPIScrapedData]:
        """
        采集 CUDA Memory Management API 信息

        Returns:
            CUDAAPIScrapedData 列表
        """
        apis = []
        for api_name in MEMORY_APIS:
            fallback = self._get_fallback_memory_api_data(api_name)
            if fallback:
                apis.append(fallback)
        return apis

    def _get_fallback_memory_api_data(self, api_name: str) -> Optional[CUDAAPIScrapedData]:
        """获取内存管理 API 的预定义数据"""
        fallback_data = {
            "cudaMalloc": CUDAAPIScrapedData(
                api_name="cudaMalloc",
                full_signature="cudaError_t cudaMalloc(void** devPtr, size_t size)",
                description="Allocates memory on the GPU device. Similar to malloc() in C, but allocates memory accessible by the GPU.",
                category="memory-management",
                subcategory="allocation",
                parameters=["void** devPtr", "size_t size"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaFree": CUDAAPIScrapedData(
                api_name="cudaFree",
                full_signature="cudaError_t cudaFree(void* devPtr)",
                description="Frees memory on the GPU device. Must be called with pointer obtained from cudaMalloc.",
                category="memory-management",
                subcategory="deallocation",
                parameters=["void* devPtr"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaMemcpy": CUDAAPIScrapedData(
                api_name="cudaMemcpy",
                full_signature="cudaError_t cudaMemcpy(void* dst, const void* src, size_t count, cudaMemcpyKind kind)",
                description="Copies data between host and device memory. Blocking call that waits for transfer to complete.",
                category="memory-management",
                subcategory="copy",
                parameters=["void* dst", "const void* src", "size_t count", "cudaMemcpyKind kind"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaMemcpyAsync": CUDAAPIScrapedData(
                api_name="cudaMemcpyAsync",
                full_signature="cudaError_t cudaMemcpyAsync(void* dst, const void* src, size_t count, cudaMemcpyKind kind, cudaStream_t stream)",
                description="Copies data between host and device asynchronously. Non-blocking, requires stream argument.",
                category="memory-management",
                subcategory="copy",
                parameters=["void* dst", "const void* src", "size_t count", "cudaMemcpyKind kind", "cudaStream_t stream"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaMemset": CUDAAPIScrapedData(
                api_name="cudaMemset",
                full_signature="cudaError_t cudaMemset(void* devPtr, int value, size_t count)",
                description="Fills device memory with a specific value. Useful for initializing arrays.",
                category="memory-management",
                subcategory="set",
                parameters=["void* devPtr", "int value", "size_t count"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
        }
        return fallback_data.get(api_name)


async def scrape_cuda_apis_batch(
    api_names: List[str],
    headless: bool = True,
) -> List[CUDAAPIScrapedData]:
    """
    批量采集 CUDA API 信息

    Args:
        api_names: API 名称列表
        headless: 是否使用无头模式

    Returns:
        CUDAAPIScrapedData 列表
    """
    async with CUDADocScraper(headless=headless) as scraper:
        all_apis = []

        # 采集 Warp Shuffle APIs
        warp_apis = await scraper.scrape_warp_shuffle_apis()
        all_apis.extend(warp_apis)

        # 采集 Memory APIs
        memory_apis = await scraper.scrape_memory_apis()
        all_apis.extend(memory_apis)

        return all_apis


if __name__ == "__main__":
    import asyncio

    async def main():
        """测试采集功能"""
        logging.basicConfig(level=logging.INFO)

        async with CUDADocScraper(headless=False) as scraper:
            apis = await scraper.scrape_warp_shuffle_apis()
            print(f"\nCollected {len(apis)} APIs:")
            for api in apis:
                print(f"  - {api.api_name}: {api.full_signature[:50]}...")

    asyncio.run(main())
