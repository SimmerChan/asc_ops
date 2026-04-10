# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
CUTLASS GPU Kernel 采集器

从 NVIDIA CUTLASS 仓库采集 GPU Kernel 知识
"""

import logging
import re
from pathlib import Path
from typing import List, Optional, Generator

from ..models import GPUKernelKnowledge, GPUPlatform, GPURepository
from ..extractors import GPUKernelExtractor

logger = logging.getLogger(__name__)


class CUTLASSCollector:
    """
    CUTLASS Kernel 采集器

    解析 CUTLASS 仓库中的 kernel 定义和模板参数
    """

    # CUTLASS kernel 文件模式
    KERNEL_FILE_EXTENSIONS = [".h", ".cu", ".cuh"]

    # CUTLASS kernel 目录模式
    KERNEL_DIR_PATTERNS = [
        "include/cutlass",
        "examples",
    ]

    def __init__(self, repo_path: str = ""):
        """
        初始化 CUTLASS 采集器

        Args:
            repo_path: CUTLASS 仓库本地路径
        """
        self.repo_path = Path(repo_path) if repo_path else None
        self.extractor = GPUKernelExtractor()

    def collect_from_repository(self) -> List[GPUKernelKnowledge]:
        """
        从本地仓库采集所有 CUTLASS kernels

        Returns:
            GPUKernelKnowledge 列表
        """
        if self.repo_path is None or not self.repo_path.exists():
            logger.warning("CUTLASS repository path not set or not found")
            return []

        kernels = []

        # 遍历 CUTLASS 头文件
        for file_path in self._iterate_kernel_files():
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                kernels.extend(
                    self.extractor.extract_from_source(
                        source_code=content,
                        platform=GPUPlatform.CUTLASS,
                        source_file=str(file_path),
                    )
                )
            except Exception as e:
                logger.error(f"Failed to parse {file_path}: {e}")

        logger.info(f"Collected {len(kernels)} CUTLASS kernels")
        return kernels

    def collect_from_content(
        self,
        content: str,
        source_file: str = "",
    ) -> List[GPUKernelKnowledge]:
        """
        从给定内容中采集 CUTLASS kernels

        Args:
            content: 源代码内容
            source_file: 源文件路径

        Returns:
            GPUKernelKnowledge 列表
        """
        return self.extractor.extract_from_source(
            source_code=content,
            platform=GPUPlatform.CUTLASS,
            source_file=source_file,
        )

    def _iterate_kernel_files(self) -> Generator[Path, None, None]:
        """遍历仓库中的 kernel 文件"""
        if self.repo_path is None:
            return

        for pattern in self.KERNEL_DIR_PATTERNS:
            dir_path = self.repo_path / pattern
            if dir_path.exists():
                yield from self._find_kernel_files(dir_path)

    def _find_kernel_files(self, directory: Path) -> Generator[Path, None, None]:
        """递归查找 kernel 文件"""
        for item in directory.rglob("*"):
            if item.is_file() and item.suffix in self.KERNEL_FILE_EXTENSIONS:
                # 过滤非 kernel 文件
                if self._is_kernel_file(item):
                    yield item

    def _is_kernel_file(self, file_path: Path) -> bool:
        """判断是否为 kernel 源文件"""
        # CUTLASS kernel 文件通常包含特定模式
        name = file_path.name.lower()
        content_patterns = ["kernel", "gemm", "conv", "epilogue", " prologue"]

        # 文件名模式
        name_patterns = ["kernel", "gemm", "conv", "warp", "mma"]
        if any(p in name for p in name_patterns):
            return True

        # 内容检查 (只读前 1KB)
        try:
            content = file_path.read_bytes()[:1024].decode("utf-8", errors="ignore").lower()
            if any(p in content for p in content_patterns):
                return True
        except Exception:
            pass

        return False

    def extract_kernel_signature(self, content: str, kernel_name: str) -> Optional[str]:
        """
        提取特定 kernel 的签名

        Args:
            content: 源代码内容
            kernel_name: kernel 名称

        Returns:
            函数签名
        """
        # 查找 kernel 定义
        pattern = rf"(template\s*<[^>]*>\s*)?(\w+(?:::\w+)*)\s+{re.escape(kernel_name)}\s*\([^)]*\)"
        match = re.search(pattern, content, re.MULTILINE)
        if match:
            return match.group(0)
        return None

    def create_repository_info(self) -> GPURepository:
        """创建 CUTLASS 仓库信息"""
        return GPURepository(
            repo_id="nvidia_cutlass",
            repo_name="NVIDIA CUTLASS",
            platform=GPUPlatform.CUTLASS,
            clone_url="https://github.com/NVIDIA/cutlass.git",
            local_path=str(self.repo_path) if self.repo_path else "",
            api_surface=self._get_main_apis(),
        )

    def _get_main_apis(self) -> List[str]:
        """获取 CUTLASS 主要 API 列表"""
        return [
            "cutlass::gemm::device::Gemm",
            "cutlass::conv::device::Conv2d",
            "cutlass::warp::WarpMma",
            "cutlass::mma::device::Mma",
        ]
