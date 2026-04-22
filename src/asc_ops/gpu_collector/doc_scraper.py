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

# Thread Synchronization APIs
THREAD_SYNC_APIS = [
    "__syncthreads",
    "__syncthreads_count",
    "__syncthreads_and",
    "__syncthreads_or",
]

# Memory Fence APIs
MEMORY_FENCE_APIS = [
    "__threadfence",
    "__threadfence_block",
    "__threadfence_system",
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
            "__reduce_mul_sync": CUDAAPIScrapedData(
                api_name="__reduce_mul_sync",
                full_signature="T __reduce_mul_sync(unsigned mask, T var)",
                description="Synchronous warp-level MUL reduction. Computes product of var across all threads in the warp.",
                category="warp-reduce",
                subcategory="reduce",
                parameters=["unsigned mask", "T var"],
                return_type="T",
                documentation_url=f"{WARP_SHUFFLE_BASE_URL}#warp-reduce-functions",
            ),
            "__reduce_and_sync": CUDAAPIScrapedData(
                api_name="__reduce_and_sync",
                full_signature="T __reduce_and_sync(unsigned mask, T var)",
                description="Synchronous warp-level AND reduction. Computes bitwise AND of var across all threads in the warp.",
                category="warp-reduce",
                subcategory="reduce",
                parameters=["unsigned mask", "T var"],
                return_type="T",
                documentation_url=f"{WARP_SHUFFLE_BASE_URL}#warp-reduce-functions",
            ),
            "__reduce_or_sync": CUDAAPIScrapedData(
                api_name="__reduce_or_sync",
                full_signature="T __reduce_or_sync(unsigned mask, T var)",
                description="Synchronous warp-level OR reduction. Computes bitwise OR of var across all threads in the warp.",
                category="warp-reduce",
                subcategory="reduce",
                parameters=["unsigned mask", "T var"],
                return_type="T",
                documentation_url=f"{WARP_SHUFFLE_BASE_URL}#warp-reduce-functions",
            ),
            "__reduce_xor_sync": CUDAAPIScrapedData(
                api_name="__reduce_xor_sync",
                full_signature="T __reduce_xor_sync(unsigned mask, T var)",
                description="Synchronous warp-level XOR reduction. Computes bitwise XOR of var across all threads in the warp.",
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
                logger.info(f"Using fallback data for memory API: {api_name}")
            else:
                logger.warning(f"No fallback data for memory API: {api_name}")
        return apis

    async def scrape_thread_sync_apis(self) -> List[CUDAAPIScrapedData]:
        """
        采集 CUDA Thread Synchronization API 信息

        Returns:
            CUDAAPIScrapedData 列表
        """
        apis = []
        for api_name in THREAD_SYNC_APIS:
            fallback = self._get_fallback_thread_sync_api_data(api_name)
            if fallback:
                apis.append(fallback)
                logger.info(f"Using fallback data for thread sync API: {api_name}")
            else:
                logger.warning(f"No fallback data for thread sync API: {api_name}")
        return apis

    async def scrape_memory_fence_apis(self) -> List[CUDAAPIScrapedData]:
        """
        采集 CUDA Memory Fence API 信息

        Returns:
            CUDAAPIScrapedData 列表
        """
        apis = []
        for api_name in MEMORY_FENCE_APIS:
            fallback = self._get_fallback_memory_fence_api_data(api_name)
            if fallback:
                apis.append(fallback)
                logger.info(f"Using fallback data for memory fence API: {api_name}")
            else:
                logger.warning(f"No fallback data for memory fence API: {api_name}")
        return apis

    async def scrape_stream_apis(self) -> List[CUDAAPIScrapedData]:
        """
        采集 CUDA Stream Management API 信息

        Returns:
            CUDAAPIScrapedData 列表
        """
        apis = []
        for api_name in STREAM_APIS:
            fallback = self._get_fallback_memory_api_data(api_name)  # Same fallback dict for stream APIs
            if fallback:
                apis.append(fallback)
                logger.info(f"Using fallback data for stream API: {api_name}")
            else:
                logger.warning(f"No fallback data for stream API: {api_name}")
        return apis

    async def scrape_event_apis(self) -> List[CUDAAPIScrapedData]:
        """
        采集 CUDA Event Management API 信息

        Returns:
            CUDAAPIScrapedData 列表
        """
        apis = []
        for api_name in EVENT_APIS:
            fallback = self._get_fallback_memory_api_data(api_name)  # Same fallback dict
            if fallback:
                apis.append(fallback)
                logger.info(f"Using fallback data for event API: {api_name}")
            else:
                logger.warning(f"No fallback data for event API: {api_name}")
        return apis

    def _get_fallback_thread_sync_api_data(self, api_name: str) -> Optional[CUDAAPIScrapedData]:
        """获取线程同步 API 的预定义数据"""
        fallback_data = {
            "__syncthreads": CUDAAPIScrapedData(
                api_name="__syncthreads",
                full_signature="void __syncthreads()",
                description="Synchronizes all threads in a block. Used to ensure memory writes are visible between threads before proceeding.",
                category="thread-synchronization",
                subcategory="barrier",
                parameters=[],
                return_type="void",
                documentation_url="https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#synchronization-functions",
            ),
            "__syncthreads_count": CUDAAPIScrapedData(
                api_name="__syncthreads_count",
                full_signature="int __syncthreads_count(int predicate)",
                description="Synchronizes all threads and returns the number of threads for which predicate is non-zero.",
                category="thread-synchronization",
                subcategory="barrier",
                parameters=["int predicate"],
                return_type="int",
                documentation_url="https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#synchronization-functions",
            ),
            "__syncthreads_and": CUDAAPIScrapedData(
                api_name="__syncthreads_and",
                full_signature="int __syncthreads_and(int predicate)",
                description="Synchronizes and returns 1 if all threads in the block have non-zero predicate, 0 otherwise.",
                category="thread-synchronization",
                subcategory="barrier",
                parameters=["int predicate"],
                return_type="int",
                documentation_url="https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#synchronization-functions",
            ),
            "__syncthreads_or": CUDAAPIScrapedData(
                api_name="__syncthreads_or",
                full_signature="int __syncthreads_or(int predicate)",
                description="Synchronizes and returns 1 if any thread in the block has non-zero predicate, 0 otherwise.",
                category="thread-synchronization",
                subcategory="barrier",
                parameters=["int predicate"],
                return_type="int",
                documentation_url="https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#synchronization-functions",
            ),
        }
        return fallback_data.get(api_name)

    def _get_fallback_memory_fence_api_data(self, api_name: str) -> Optional[CUDAAPIScrapedData]:
        """获取内存屏障 API 的预定义数据"""
        fallback_data = {
            "__threadfence": CUDAAPIScrapedData(
                api_name="__threadfence",
                full_signature="void __threadfence()",
                description="Ensures that all global memory accesses by all threads in the block are visible to all threads in the device before any thread in the block proceeds.",
                category="memory-fence",
                subcategory="fence",
                parameters=[],
                return_type="void",
                documentation_url="https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#memory-fence-functions",
            ),
            "__threadfence_block": CUDAAPIScrapedData(
                api_name="__threadfence_block",
                full_signature="void __threadfence_block()",
                description="Ensures that all global memory accesses by all threads in the block are visible to all threads in the block before any thread proceeds.",
                category="memory-fence",
                subcategory="fence",
                parameters=[],
                return_type="void",
                documentation_url="https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#memory-fence-functions",
            ),
            "__threadfence_system": CUDAAPIScrapedData(
                api_name="__threadfence_system",
                full_signature="void __threadfence_system()",
                description="Ensures that all global memory accesses by all threads in the device are visible to all threads in the system before any thread proceeds.",
                category="memory-fence",
                subcategory="fence",
                parameters=[],
                return_type="void",
                documentation_url="https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#memory-fence-functions",
            ),
        }
        return fallback_data.get(api_name)

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
            "cudaMallocHost": CUDAAPIScrapedData(
                api_name="cudaMallocHost",
                full_signature="cudaError_t cudaMallocHost(void** ptr, size_t size)",
                description="Allocates page-locked host memory. Accessible by host and device, enables faster DMA transfers.",
                category="memory-management",
                subcategory="allocation",
                parameters=["void** ptr", "size_t size"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaMallocPitch": CUDAAPIScrapedData(
                api_name="cudaMallocPitch",
                full_signature="cudaError_t cudaMallocPitch(void** devPtr, size_t* pitch, size_t width, size_t height)",
                description="Allocates pitched device memory. pitch ensures memory access efficiency for 2D arrays.",
                category="memory-management",
                subcategory="allocation",
                parameters=["void** devPtr", "size_t* pitch", "size_t width", "size_t height"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaFreeHost": CUDAAPIScrapedData(
                api_name="cudaFreeHost",
                full_signature="cudaError_t cudaFreeHost(void* ptr)",
                description="Frees page-locked host memory allocated by cudaMallocHost.",
                category="memory-management",
                subcategory="deallocation",
                parameters=["void* ptr"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaMemcpyToSymbol": CUDAAPIScrapedData(
                api_name="cudaMemcpyToSymbol",
                full_signature="cudaError_t cudaMemcpyToSymbol(const void* symbol, const void* src, size_t count, size_t offset, cudaMemcpyKind kind)",
                description="Copies memory to a symbol (constant memory) on the device.",
                category="memory-management",
                subcategory="copy",
                parameters=["const void* symbol", "const void* src", "size_t count", "size_t offset", "cudaMemcpyKind kind"],
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
            "cudaMemsetAsync": CUDAAPIScrapedData(
                api_name="cudaMemsetAsync",
                full_signature="cudaError_t cudaMemsetAsync(void* devPtr, int value, size_t count, cudaStream_t stream)",
                description="Asynchronously fills device memory with a specific value.",
                category="memory-management",
                subcategory="set",
                parameters=["void* devPtr", "int value", "size_t count", "cudaStream_t stream"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            # Thread Synchronization
            "__syncthreads": CUDAAPIScrapedData(
                api_name="__syncthreads",
                full_signature="void __syncthreads()",
                description="Synchronizes all threads in a block. Used to ensure memory writes are visible between threads before proceeding.",
                category="thread-synchronization",
                subcategory="barrier",
                parameters=[],
                return_type="void",
                documentation_url="https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#synchronization-functions",
            ),
            "__syncthreads_count": CUDAAPIScrapedData(
                api_name="__syncthreads_count",
                full_signature="int __syncthreads_count(int predicate)",
                description="Synchronizes all threads and returns the number of threads for which predicate is non-zero.",
                category="thread-synchronization",
                subcategory="barrier",
                parameters=["int predicate"],
                return_type="int",
                documentation_url="https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#synchronization-functions",
            ),
            "__syncthreads_and": CUDAAPIScrapedData(
                api_name="__syncthreads_and",
                full_signature="int __syncthreads_and(int predicate)",
                description="Synchronizes and returns 1 if all threads in the block have non-zero predicate, 0 otherwise.",
                category="thread-synchronization",
                subcategory="barrier",
                parameters=["int predicate"],
                return_type="int",
                documentation_url="https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#synchronization-functions",
            ),
            "__syncthreads_or": CUDAAPIScrapedData(
                api_name="__syncthreads_or",
                full_signature="int __syncthreads_or(int predicate)",
                description="Synchronizes and returns 1 if any thread in the block has non-zero predicate, 0 otherwise.",
                category="thread-synchronization",
                subcategory="barrier",
                parameters=["int predicate"],
                return_type="int",
                documentation_url="https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#synchronization-functions",
            ),
            # Memory Fence
            "__threadfence": CUDAAPIScrapedData(
                api_name="__threadfence",
                full_signature="void __threadfence()",
                description="Ensures that all global memory accesses by all threads in the block are visible to all threads in the device before any thread in the block proceeds.",
                category="memory-fence",
                subcategory="fence",
                parameters=[],
                return_type="void",
                documentation_url="https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#memory-fence-functions",
            ),
            "__threadfence_block": CUDAAPIScrapedData(
                api_name="__threadfence_block",
                full_signature="void __threadfence_block()",
                description="Ensures that all global memory accesses by all threads in the block are visible to all threads in the block before any thread proceeds.",
                category="memory-fence",
                subcategory="fence",
                parameters=[],
                return_type="void",
                documentation_url="https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#memory-fence-functions",
            ),
            "__threadfence_system": CUDAAPIScrapedData(
                api_name="__threadfence_system",
                full_signature="void __threadfence_system()",
                description="Ensures that all global memory accesses by all threads in the device are visible to all threads in the system before any thread proceeds.",
                category="memory-fence",
                subcategory="fence",
                parameters=[],
                return_type="void",
                documentation_url="https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#memory-fence-functions",
            ),
            # Stream APIs
            "cudaStreamCreate": CUDAAPIScrapedData(
                api_name="cudaStreamCreate",
                full_signature="cudaError_t cudaStreamCreate(cudaStream_t* stream)",
                description="Creates a stream for asynchronous operations.",
                category="stream-management",
                subcategory="create",
                parameters=["cudaStream_t* stream"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__STREAM.html",
            ),
            "cudaStreamSynchronize": CUDAAPIScrapedData(
                api_name="cudaStreamSynchronize",
                full_signature="cudaError_t cudaStreamSynchronize(cudaStream_t stream)",
                description="Synchronizes all operations in the specified stream.",
                category="stream-management",
                subcategory="synchronize",
                parameters=["cudaStream_t stream"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__STREAM.html",
            ),
            "cudaStreamDestroy": CUDAAPIScrapedData(
                api_name="cudaStreamDestroy",
                full_signature="cudaError_t cudaStreamDestroy(cudaStream_t stream)",
                description="Destroys a stream created by cudaStreamCreate.",
                category="stream-management",
                subcategory="destroy",
                parameters=["cudaStream_t stream"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__STREAM.html",
            ),
            # Event APIs
            "cudaEventCreate": CUDAAPIScrapedData(
                api_name="cudaEventCreate",
                full_signature="cudaError_t cudaEventCreate(cudaEvent_t* event)",
                description="Creates an event for timing and synchronization.",
                category="event-management",
                subcategory="create",
                parameters=["cudaEvent_t* event"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__EVENT.html",
            ),
            "cudaEventSynchronize": CUDAAPIScrapedData(
                api_name="cudaEventSynchronize",
                full_signature="cudaError_t cudaEventSynchronize(cudaEvent_t event)",
                description="Waits for an event to complete.",
                category="event-management",
                subcategory="synchronize",
                parameters=["cudaEvent_t event"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__EVENT.html",
            ),
            "cudaEventRecord": CUDAAPIScrapedData(
                api_name="cudaEventRecord",
                full_signature="cudaError_t cudaEventRecord(cudaEvent_t event, cudaStream_t stream)",
                description="Records an event in a stream.",
                category="event-management",
                subcategory="record",
                parameters=["cudaEvent_t event", "cudaStream_t stream"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__EVENT.html",
            ),
            # Remaining Memory APIs
            "cudaMallocArray": CUDAAPIScrapedData(
                api_name="cudaMallocArray",
                full_signature="cudaError_t cudaMallocArray(cudaArray_t* array, const cudaChannelFormatDesc* desc, size_t width, size_t height)",
                description="Allocates an array on the GPU device.",
                category="memory-management",
                subcategory="allocation",
                parameters=["cudaArray_t* array", "const cudaChannelFormatDesc* desc", "size_t width", "size_t height"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaMalloc3D": CUDAAPIScrapedData(
                api_name="cudaMalloc3D",
                full_signature="cudaError_t cudaMalloc3D(cudaPitchedPtr* pitchedDevPtr, cudaExtent extent)",
                description="Allocates a pitched 3D array in device memory.",
                category="memory-management",
                subcategory="allocation",
                parameters=["cudaPitchedPtr* pitchedDevPtr", "cudaExtent extent"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaMalloc3DArray": CUDAAPIScrapedData(
                api_name="cudaMalloc3DArray",
                full_signature="cudaError_t cudaMalloc3DArray(cudaArray_t* array, const cudaChannelFormatDesc* desc, cudaExtent extent)",
                description="Allocates a 3D array in device memory.",
                category="memory-management",
                subcategory="allocation",
                parameters=["cudaArray_t* array", "const cudaChannelFormatDesc* desc", "cudaExtent extent"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaMallocManaged": CUDAAPIScrapedData(
                api_name="cudaMallocManaged",
                full_signature="cudaError_t cudaMallocManaged(void** devPtr, size_t size, unsigned int flags)",
                description="Allocates unified memory accessible from both host and device.",
                category="memory-management",
                subcategory="allocation",
                parameters=["void** devPtr", "size_t size", "unsigned int flags"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaFreeArray": CUDAAPIScrapedData(
                api_name="cudaFreeArray",
                full_signature="cudaError_t cudaFreeArray(cudaArray_t array)",
                description="Frees an array on the GPU device.",
                category="memory-management",
                subcategory="deallocation",
                parameters=["cudaArray_t array"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaMemcpy2D": CUDAAPIScrapedData(
                api_name="cudaMemcpy2D",
                full_signature="cudaError_t cudaMemcpy2D(void* dst, size_t dpitch, const void* src, size_t spitch, size_t width, size_t height, cudaMemcpyKind kind)",
                description="Copies a 2D array between host and device memory.",
                category="memory-management",
                subcategory="copy",
                parameters=["void* dst", "size_t dpitch", "const void* src", "size_t spitch", "size_t width", "size_t height", "cudaMemcpyKind kind"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaMemcpy2DAsync": CUDAAPIScrapedData(
                api_name="cudaMemcpy2DAsync",
                full_signature="cudaError_t cudaMemcpy2DAsync(void* dst, size_t dpitch, const void* src, size_t spitch, size_t width, size_t height, cudaMemcpyKind kind, cudaStream_t stream)",
                description="Asynchronously copies a 2D array between host and device memory.",
                category="memory-management",
                subcategory="copy",
                parameters=["void* dst", "size_t dpitch", "const void* src", "size_t spitch", "size_t width", "size_t height", "cudaMemcpyKind kind", "cudaStream_t stream"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaMemcpy3D": CUDAAPIScrapedData(
                api_name="cudaMemcpy3D",
                full_signature="cudaError_t cudaMemcpy3D(const cudaMemcpy3DParms* p)",
                description="Copies a 3D array between host and device memory.",
                category="memory-management",
                subcategory="copy",
                parameters=["const cudaMemcpy3DParms* p"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaMemcpy3DAsync": CUDAAPIScrapedData(
                api_name="cudaMemcpy3DAsync",
                full_signature="cudaError_t cudaMemcpy3DAsync(const cudaMemcpy3DParms* p, cudaStream_t stream)",
                description="Asynchronously copies a 3D array between host and device memory.",
                category="memory-management",
                subcategory="copy",
                parameters=["const cudaMemcpy3DParms* p", "cudaStream_t stream"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaMemcpyFromSymbol": CUDAAPIScrapedData(
                api_name="cudaMemcpyFromSymbol",
                full_signature="cudaError_t cudaMemcpyFromSymbol(void* dst, const void* symbol, size_t count, size_t offset, cudaMemcpyKind kind)",
                description="Copies from a symbol (constant memory) on the device to host memory.",
                category="memory-management",
                subcategory="copy",
                parameters=["void* dst", "const void* symbol", "size_t count", "size_t offset", "cudaMemcpyKind kind"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaMemcpyFromSymbolAsync": CUDAAPIScrapedData(
                api_name="cudaMemcpyFromSymbolAsync",
                full_signature="cudaError_t cudaMemcpyFromSymbolAsync(void* dst, const void* symbol, size_t count, size_t offset, cudaMemcpyKind kind, cudaStream_t stream)",
                description="Asynchronously copies from a device symbol to host memory.",
                category="memory-management",
                subcategory="copy",
                parameters=["void* dst", "const void* symbol", "size_t count", "size_t offset", "cudaMemcpyKind kind", "cudaStream_t stream"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaMemcpyToSymbolAsync": CUDAAPIScrapedData(
                api_name="cudaMemcpyToSymbolAsync",
                full_signature="cudaError_t cudaMemcpyToSymbolAsync(const void* symbol, const void* src, size_t count, size_t offset, cudaMemcpyKind kind, cudaStream_t stream)",
                description="Asynchronously copies to a symbol (constant memory) on the device.",
                category="memory-management",
                subcategory="copy",
                parameters=["const void* symbol", "const void* src", "size_t count", "size_t offset", "cudaMemcpyKind kind", "cudaStream_t stream"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaMemcpyPeer": CUDAAPIScrapedData(
                api_name="cudaMemcpyPeer",
                full_signature="cudaError_t cudaMemcpyPeer(void* dst, int dstDevice, const void* src, int srcDevice, size_t count)",
                description="Copies memory between two devices.",
                category="memory-management",
                subcategory="copy",
                parameters=["void* dst", "int dstDevice", "const void* src", "int srcDevice", "size_t count"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaMemcpyPeerAsync": CUDAAPIScrapedData(
                api_name="cudaMemcpyPeerAsync",
                full_signature="cudaError_t cudaMemcpyPeerAsync(void* dst, int dstDevice, const void* src, int srcDevice, size_t count, cudaStream_t stream)",
                description="Asynchronously copies memory between two devices.",
                category="memory-management",
                subcategory="copy",
                parameters=["void* dst", "int dstDevice", "const void* src", "int srcDevice", "size_t count", "cudaStream_t stream"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaMemset2D": CUDAAPIScrapedData(
                api_name="cudaMemset2D",
                full_signature="cudaError_t cudaMemset2D(void* devPtr, size_t pitch, int value, size_t width, size_t height)",
                description="Fills a 2D array with a specific value.",
                category="memory-management",
                subcategory="set",
                parameters=["void* devPtr", "size_t pitch", "int value", "size_t width", "size_t height"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaMemset2DAsync": CUDAAPIScrapedData(
                api_name="cudaMemset2DAsync",
                full_signature="cudaError_t cudaMemset2DAsync(void* devPtr, size_t pitch, int value, size_t width, size_t height, cudaStream_t stream)",
                description="Asynchronously fills a 2D array with a specific value.",
                category="memory-management",
                subcategory="set",
                parameters=["void* devPtr", "size_t pitch", "int value", "size_t width", "size_t height", "cudaStream_t stream"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaMemset3D": CUDAAPIScrapedData(
                api_name="cudaMemset3D",
                full_signature="cudaError_t cudaMemset3D(cudaPitchedPtr pitchedDevPtr, int value, cudaExtent extent)",
                description="Fills a 3D array with a specific value.",
                category="memory-management",
                subcategory="set",
                parameters=["cudaPitchedPtr pitchedDevPtr", "int value", "cudaExtent extent"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            "cudaMemset3DAsync": CUDAAPIScrapedData(
                api_name="cudaMemset3DAsync",
                full_signature="cudaError_t cudaMemset3DAsync(cudaPitchedPtr pitchedDevPtr, int value, cudaExtent extent, cudaStream_t stream)",
                description="Asynchronously fills a 3D array with a specific value.",
                category="memory-management",
                subcategory="set",
                parameters=["cudaPitchedPtr pitchedDevPtr", "int value", "cudaExtent extent", "cudaStream_t stream"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html",
            ),
            # Remaining Stream APIs
            "cudaStreamCreateWithFlags": CUDAAPIScrapedData(
                api_name="cudaStreamCreateWithFlags",
                full_signature="cudaError_t cudaStreamCreateWithFlags(cudaStream_t* stream, unsigned int flags)",
                description="Creates a stream with specified flags.",
                category="stream-management",
                subcategory="create",
                parameters=["cudaStream_t* stream", "unsigned int flags"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__STREAM.html",
            ),
            "cudaStreamWaitEvent": CUDAAPIScrapedData(
                api_name="cudaStreamWaitEvent",
                full_signature="cudaError_t cudaStreamWaitEvent(cudaStream_t stream, cudaEvent_t event, unsigned int flags)",
                description="Makes a stream wait for an event.",
                category="stream-management",
                subcategory="wait",
                parameters=["cudaStream_t stream", "cudaEvent_t event", "unsigned int flags"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__STREAM.html",
            ),
            "cudaStreamAddCallback": CUDAAPIScrapedData(
                api_name="cudaStreamAddCallback",
                full_signature="cudaError_t cudaStreamAddCallback(cudaStream_t stream, cudaStreamCallback_t callback, void* userData, unsigned int flags)",
                description="Adds a callback to a stream.",
                category="stream-management",
                subcategory="callback",
                parameters=["cudaStream_t stream", "cudaStreamCallback_t callback", "void* userData", "unsigned int flags"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__STREAM.html",
            ),
            "cudaStreamQuery": CUDAAPIScrapedData(
                api_name="cudaStreamQuery",
                full_signature="cudaError_t cudaStreamQuery(cudaStream_t stream)",
                description="Queries if a stream has completed all operations.",
                category="stream-management",
                subcategory="query",
                parameters=["cudaStream_t stream"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__STREAM.html",
            ),
            "cudaStreamBeginCapture": CUDAAPIScrapedData(
                api_name="cudaStreamBeginCapture",
                full_signature="cudaError_t cudaStreamBeginCapture(cudaStream_t stream, cudaStreamCaptureMode mode)",
                description="Begins capturing a stream.",
                category="stream-management",
                subcategory="capture",
                parameters=["cudaStream_t stream", "cudaStreamCaptureMode mode"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__STREAM.html",
            ),
            "cudaStreamEndCapture": CUDAAPIScrapedData(
                api_name="cudaStreamEndCapture",
                full_signature="cudaError_t cudaStreamEndCapture(cudaStream_t stream, cudaGraph_t* graph)",
                description="Ends capturing a stream and returns a graph.",
                category="stream-management",
                subcategory="capture",
                parameters=["cudaStream_t stream", "cudaGraph_t* graph"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__STREAM.html",
            ),
            "cudaStreamIsCapturing": CUDAAPIScrapedData(
                api_name="cudaStreamIsCapturing",
                full_signature="cudaError_t cudaStreamIsCapturing(cudaStream_t stream, cudaStreamCaptureStatus* status)",
                description="Checks if a stream is in capture mode.",
                category="stream-management",
                subcategory="capture",
                parameters=["cudaStream_t stream", "cudaStreamCaptureStatus* status"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__STREAM.html",
            ),
            "cudaStreamAttachMemAsync": CUDAAPIScrapedData(
                api_name="cudaStreamAttachMemAsync",
                full_signature="cudaError_t cudaStreamAttachMemAsync(cudaStream_t stream, void* devPtr, size_t length, unsigned int flags)",
                description="Attaches memory to a stream.",
                category="stream-management",
                subcategory="memory",
                parameters=["cudaStream_t stream", "void* devPtr", "size_t length", "unsigned int flags"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__STREAM.html",
            ),
            "cudaStreamGetCaptureInfo": CUDAAPIScrapedData(
                api_name="cudaStreamGetCaptureInfo",
                full_signature="cudaError_t cudaStreamGetCaptureInfo(cudaStream_t stream, cudaStreamCaptureStatus* status, cuuint64_t* id)",
                description="Gets capture information for a stream.",
                category="stream-management",
                subcategory="capture",
                parameters=["cudaStream_t stream", "cudaStreamCaptureStatus* status", "cuuint64_t* id"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__STREAM.html",
            ),
            # Remaining Event APIs
            "cudaEventCreateWithFlags": CUDAAPIScrapedData(
                api_name="cudaEventCreateWithFlags",
                full_signature="cudaError_t cudaEventCreateWithFlags(cudaEvent_t* event, unsigned int flags)",
                description="Creates an event with specified flags.",
                category="event-management",
                subcategory="create",
                parameters=["cudaEvent_t* event", "unsigned int flags"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__EVENT.html",
            ),
            "cudaEventDestroy": CUDAAPIScrapedData(
                api_name="cudaEventDestroy",
                full_signature="cudaError_t cudaEventDestroy(cudaEvent_t event)",
                description="Destroys an event.",
                category="event-management",
                subcategory="destroy",
                parameters=["cudaEvent_t event"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__EVENT.html",
            ),
            "cudaEventQuery": CUDAAPIScrapedData(
                api_name="cudaEventQuery",
                full_signature="cudaError_t cudaEventQuery(cudaEvent_t event)",
                description="Queries if an event has completed.",
                category="event-management",
                subcategory="query",
                parameters=["cudaEvent_t event"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__EVENT.html",
            ),
            "cudaEventElapsedTime": CUDAAPIScrapedData(
                api_name="cudaEventElapsedTime",
                full_signature="cudaError_t cudaEventElapsedTime(float* ms, cudaEvent_t start, cudaEvent_t end)",
                description="Calculates elapsed time between two events.",
                category="event-management",
                subcategory="timing",
                parameters=["float* ms", "cudaEvent_t start", "cudaEvent_t end"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__EVENT.html",
            ),
            # Device APIs
            "cudaChooseDevice": CUDAAPIScrapedData(
                api_name="cudaChooseDevice",
                full_signature="cudaError_t cudaChooseDevice(int* device, const cudaDeviceProp* prop)",
                description="Selects the device most closely matching the given properties.",
                category="device-management",
                subcategory="selection",
                parameters=["int* device", "const cudaDeviceProp* prop"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__DEVICE.html",
            ),
            "cudaGetDevice": CUDAAPIScrapedData(
                api_name="cudaGetDevice",
                full_signature="cudaError_t cudaGetDevice(int* device)",
                description="Returns the current device for the calling host thread.",
                category="device-management",
                subcategory="query",
                parameters=["int* device"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__DEVICE.html",
            ),
            "cudaSetDevice": CUDAAPIScrapedData(
                api_name="cudaSetDevice",
                full_signature="cudaError_t cudaSetDevice(int device)",
                description="Sets the current device for the calling host thread.",
                category="device-management",
                subcategory="selection",
                parameters=["int device"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__DEVICE.html",
            ),
            "cudaGetDeviceCount": CUDAAPIScrapedData(
                api_name="cudaGetDeviceCount",
                full_signature="cudaError_t cudaGetDeviceCount(int* count)",
                description="Returns the number of available devices.",
                category="device-management",
                subcategory="query",
                parameters=["int* count"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__DEVICE.html",
            ),
            "cudaGetDeviceProperties": CUDAAPIScrapedData(
                api_name="cudaGetDeviceProperties",
                full_signature="cudaError_t cudaGetDeviceProperties(cudaDeviceProp* prop, int device)",
                description="Returns information about the specified device.",
                category="device-management",
                subcategory="query",
                parameters=["cudaDeviceProp* prop", "int device"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__DEVICE.html",
            ),
            "cudaDeviceSynchronize": CUDAAPIScrapedData(
                api_name="cudaDeviceSynchronize",
                full_signature="cudaError_t cudaDeviceSynchronize()",
                description="Synchronizes all threads on the device.",
                category="device-management",
                subcategory="synchronization",
                parameters=[],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__DEVICE.html",
            ),
            "cudaDeviceReset": CUDAAPIScrapedData(
                api_name="cudaDeviceReset",
                full_signature="cudaError_t cudaDeviceReset()",
                description="Resets the device and clears all state.",
                category="device-management",
                subcategory="reset",
                parameters=[],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__DEVICE.html",
            ),
            "cudaDeviceGetCacheConfig": CUDAAPIScrapedData(
                api_name="cudaDeviceGetCacheConfig",
                full_signature="cudaError_t cudaDeviceGetCacheConfig(cudaFuncCache* cacheConfig)",
                description="Returns the current cache configuration.",
                category="device-management",
                subcategory="cache",
                parameters=["cudaFuncCache* cacheConfig"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__DEVICE.html",
            ),
            "cudaDeviceSetCacheConfig": CUDAAPIScrapedData(
                api_name="cudaDeviceSetCacheConfig",
                full_signature="cudaError_t cudaDeviceSetCacheConfig(cudaFuncCache cacheConfig)",
                description="Sets the cache configuration for the device.",
                category="device-management",
                subcategory="cache",
                parameters=["cudaFuncCache cacheConfig"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__DEVICE.html",
            ),
            "cudaDeviceGetLimit": CUDAAPIScrapedData(
                api_name="cudaDeviceGetLimit",
                full_signature="cudaError_t cudaDeviceGetLimit(size_t* pValue, cudaLimit limit)",
                description="Returns the current value of a device limit.",
                category="device-management",
                subcategory="limit",
                parameters=["size_t* pValue", "cudaLimit limit"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__DEVICE.html",
            ),
            "cudaDeviceSetLimit": CUDAAPIScrapedData(
                api_name="cudaDeviceSetLimit",
                full_signature="cudaError_t cudaDeviceSetLimit(cudaLimit limit, size_t value)",
                description="Sets a device limit.",
                category="device-management",
                subcategory="limit",
                parameters=["cudaLimit limit", "size_t value"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__DEVICE.html",
            ),
            # Execution Control APIs
            "cudaConfigureCall": CUDAAPIScrapedData(
                api_name="cudaConfigureCall",
                full_signature="cudaError_t cudaConfigureCall(dim3 gridDim, dim3 blockDim, size_t sharedMem, cudaStream_t stream)",
                description="Configures a kernel launch.",
                category="execution-control",
                subcategory="launch",
                parameters=["dim3 gridDim", "dim3 blockDim", "size_t sharedMem", "cudaStream_t stream"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#execution-configuration",
            ),
            "cudaLaunchKernel": CUDAAPIScrapedData(
                api_name="cudaLaunchKernel",
                full_signature="cudaError_t cudaLaunchKernel(const void* func, dim3 gridDim, dim3 blockDim, void** args, size_t sharedMem, cudaStream_t stream)",
                description="Launches a kernel on the device.",
                category="execution-control",
                subcategory="launch",
                parameters=["const void* func", "dim3 gridDim", "dim3 blockDim", "void** args", "size_t sharedMem", "cudaStream_t stream"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#execution-configuration",
            ),
            "cudaLaunchCooperativeKernel": CUDAAPIScrapedData(
                api_name="cudaLaunchCooperativeKernel",
                full_signature="cudaError_t cudaLaunchCooperativeKernel(const void* func, dim3 gridDim, dim3 blockDim, void** args, size_t sharedMem, cudaStream_t stream)",
                description="Launches a cooperative kernel on the device.",
                category="execution-control",
                subcategory="launch",
                parameters=["const void* func", "dim3 gridDim", "dim3 blockDim", "void** args", "size_t sharedMem", "cudaStream_t stream"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#execution-configuration",
            ),
            "cudaLaunchCooperativeKernelMultiDevice": CUDAAPIScrapedData(
                api_name="cudaLaunchCooperativeKernelMultiDevice",
                full_signature="cudaError_t cudaLaunchCooperativeKernelMultiDevice(const cudaLaunchKernelMultDeviceParams* params, unsigned int flags)",
                description="Launches a cooperative kernel on multiple devices.",
                category="execution-control",
                subcategory="launch",
                parameters=["const cudaLaunchKernelMultDeviceParams* params", "unsigned int flags"],
                return_type="cudaError_t",
                documentation_url="https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#execution-configuration",
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

        # 采集 Thread Synchronization APIs
        thread_sync_apis = await scraper.scrape_thread_sync_apis()
        all_apis.extend(thread_sync_apis)

        # 采集 Memory Fence APIs
        memory_fence_apis = await scraper.scrape_memory_fence_apis()
        all_apis.extend(memory_fence_apis)

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
