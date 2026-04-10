# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
cuBLAS GPU API 采集器

从 NVIDIA cuBLAS 官方文档采集 BLAS API 知识
"""

import logging
from typing import List, Optional, Dict, Any

from ..models import GPUAPIInfo, GPUPlatform, GPURepository
from ..extractors import GPUAPIExtractor

logger = logging.getLogger(__name__)


class cuBLASCollector:
    """
    cuBLAS API 采集器

    采集 cuBLAS 官方文档中的 API 定义和签名
    """

    # cuBLAS 核心 API 列表 (基于官方文档)
    CORE_APIS = [
        "cublasCreate",
        "cublasDestroy",
        "cublasSetVector",
        "cublasGetVector",
        "cublasSgemm",
        "cublasDgemm",
        "cublasHgemm",
        "cublasGemmEx",
        "cublasSaxpy",
        "cublasDaxpy",
        "cublasScopy",
        "cublasDcopy",
        "cublasSdot",
        "cublasDdot",
        "cublasSnrm2",
        "cublasDnrm2",
        "cublasIsamax",
        "cublasIdamax",
        "cublasSscal",
        "cublasDscal",
        "cublasSswap",
        "cublasDswap",
        "cublasSgeam",
        "cublasDgeam",
        "cublasSdgmm",
        "cublasDdgmm",
    ]

    def __init__(self):
        """初始化 cuBLAS 采集器"""
        self.extractor = GPUAPIExtractor()

    def collect_from_documentation(self, docs_content: str) -> List[GPUAPIInfo]:
        """
        从文档内容中采集 cuBLAS API

        Args:
            docs_content: 文档内容 (HTML/Markdown)

        Returns:
            GPUAPIInfo 列表
        """
        apis = []

        for api_name in self.CORE_APIS:
            api = self._create_api_info(api_name)
            if api:
                apis.append(api)

        logger.info(f"Collected {len(apis)} cuBLAS APIs")
        return apis

    def collect_from_source(self, source_code: str) -> List[GPUAPIInfo]:
        """
        从源代码中采集 cuBLAS API

        Args:
            source_code: 源代码内容

        Returns:
            GPUAPIInfo 列表
        """
        return self.extractor.extract_from_source(
            source_code=source_code,
            platform=GPUPlatform.CUBLAS,
        )

    def _create_api_info(self, api_name: str) -> Optional[GPUAPIInfo]:
        """创建 API 信息"""
        try:
            signature = self._get_api_signature(api_name)
            category, subcategory = self._categorize_api(api_name)

            return GPUAPIInfo(
                api_id=f"cublas_{api_name}",
                api_name=api_name,
                platform=GPUPlatform.CUBLAS,
                full_signature=signature,
                description=self._get_api_description(api_name),
                category=category,
                subcategory=subcategory,
                documentation_url=f"https://docs.nvidia.com/cuda/cublas/",
            )
        except Exception as e:
            logger.error(f"Failed to create API info for {api_name}: {e}")
            return None

    def _get_api_signature(self, api_name: str) -> str:
        """获取 API 签名"""
        # cuBLAS 签名模板
        signatures = {
            "cublasCreate": "cublasHandle_t cublasCreate(void)",
            "cublasDestroy": "cublasStatus_t cublasDestroy(cublasHandle_t handle)",
            "cublasSetVector": "cublasStatus_t cublasSetVector(int n, int elemSize, const void *x, int incx, void *y, int incy)",
            "cublasGetVector": "cublasStatus_t cublasGetVector(int n, int elemSize, const void *x, int incx, void *y, int incy)",
            "cublasSgemm": "cublasStatus_t cublasSgemm(cublasHandle_t handle, cublasOperation_t transa, cublasOperation_t transb, int m, int n, int k, const float *alpha, const float *A, int lda, const float *B, int ldb, const float *beta, float *C, int ldc)",
            "cublasDgemm": "cublasStatus_t cublasDgemm(cublasHandle_t handle, cublasOperation_t transa, cublasOperation_t transb, int m, int n, int k, const double *alpha, const double *A, int lda, const double *B, int ldb, const double *beta, double *C, int ldc)",
            "cublasHgemm": "cublasStatus_t cublasHgemm(cublasHandle_t handle, cublasOperation_t transa, cublasOperation_t transb, int m, int n, int k, const __half *alpha, const __half *A, int lda, const __half *B, int ldb, const __half *beta, __half *C, int ldc)",
            "cublasGemmEx": "cublasStatus_t cublasGemmEx(cublasHandle_t handle, cublasOperation_t transa, cublasOperation_t transb, int m, int n, int k, const void *alpha, const void *A, cudaDataType_t Atype, int lda, const void *B, cudaDataType_t Btype, int ldb, const void *beta, void *C, cudaDataType_t Ctype, int ldc, cudaDataType_t computeType, cublasGemmAlgo_t algo)",
            "cublasSaxpy": "cublasStatus_t cublasSaxpy(cublasHandle_t handle, int n, const float *alpha, const float *x, int incx, float *y, int incy)",
            "cublasDaxpy": "cublasStatus_t cublasDaxpy(cublasHandle_t handle, int n, const double *alpha, const double *x, int incx, double *y, int incy)",
            "cublasScopy": "cublasStatus_t cublasScopy(cublasHandle_t handle, int n, const float *x, int incx, float *y, int incy)",
            "cublasDcopy": "cublasStatus_t cublasDcopy(cublasHandle_t handle, int n, const double *x, int incx, double *y, int incy)",
            "cublasSdot": "cublasStatus_t cublasSdot(cublasHandle_t handle, int n, const float *x, int incx, const float *y, int incy, float *result)",
            "cublasDdot": "cublasStatus_t cublasDdot(cublasHandle_t handle, int n, const double *x, int incx, const double *y, int incy, double *result)",
            "cublasSnrm2": "cublasStatus_t cublasSnrm2(cublasHandle_t handle, int n, const float *x, int incx, float *result)",
            "cublasDnrm2": "cublasStatus_t cublasDnrm2(cublasHandle_t handle, int n, const double *x, int incx, double *result)",
            "cublasIsamax": "cublasStatus_t cublasIsamax(cublasHandle_t handle, int n, const float *x, int incx, int *result)",
            "cublasIdamax": "cublasStatus_t cublasIdamax(cublasHandle_t handle, int n, const double *x, int incx, int *result)",
            "cublasSscal": "cublasStatus_t cublasSscal(cublasHandle_t handle, int n, const float *alpha, float *x, int incx)",
            "cublasDscal": "cublasStatus_t cublasDscal(cublasHandle_t handle, int n, const double *alpha, double *x, int incx)",
            "cublasSswap": "cublasStatus_t cublasSswap(cublasHandle_t handle, int n, float *x, int incx, float *y, int incy)",
            "cublasDswap": "cublasStatus_t cublasDswap(cublasHandle_t handle, int n, double *x, int incx, double *y, int incy)",
            "cublasSgeam": "cublasStatus_t cublasSgeam(cublasHandle_t handle, cublasOperation_t transa, cublasOperation_t transb, int m, int n, const float *alpha, const float *A, int lda, const float *beta, const float *B, int ldb, float *C, int ldc)",
            "cublasDgeam": "cublasStatus_t cublasDgeam(cublasHandle_t handle, cublasOperation_t transa, cublasOperation_t transb, int m, int n, const double *alpha, const double *A, int lda, const double *beta, const double *B, int ldb, double *C, int ldc)",
            "cublasSdgmm": "cublasStatus_t cublasSdgmm(cublasHandle_t handle, cublasSideMode_t side, int m, int n, const float *A, int lda, const float *x, int incx, float *C, int ldc)",
            "cublasDdgmm": "cublasStatus_t cublasDdgmm(cublasHandle_t handle, cublasSideMode_t side, int m, int n, const double *A, int lda, const double *x, int incx, double *C, int ldc)",
        }

        return signatures.get(api_name, f"{api_name}(void)")

    def _categorize_api(self, api_name: str) -> tuple:
        """分类 API"""
        name_lower = api_name.lower()

        if "gemm" in name_lower:
            return "compute", "matrix_multiply"
        elif "axpy" in name_lower or "dot" in name_lower or "nrm2" in name_lower:
            return "compute", "vector"
        elif "copy" in name_lower or "swap" in name_lower:
            return "compute", "data_move"
        elif "amax" in name_lower or "amin" in name_lower:
            return "compute", "search"
        elif "setvector" in name_lower or "getvector" in name_lower:
            return "memory", "data_transfer"
        elif "scal" in name_lower:
            return "compute", "scale"
        elif "create" in name_lower or "destroy" in name_lower:
            return "util", "handle"
        else:
            return "util", "other"

    def _get_api_description(self, api_name: str) -> str:
        """获取 API 描述"""
        descriptions = {
            "cublasSgemm": "单精度矩阵乘法 C = alpha * A * B + beta * C",
            "cublasDgemm": "双精度矩阵乘法 C = alpha * A * B + beta * C",
            "cublasHgemm": "半精度矩阵乘法 (FP16)",
            "cublasGemmEx": "混合精度矩阵乘法支持多种数据格式",
            "cublasSaxpy": "单精度向量缩放加法 y = alpha * x + y",
            "cublasDaxpy": "双精度向量缩放加法 y = alpha * x + y",
            "cublasScopy": "单精度向量拷贝 y = x",
            "cublasDcopy": "双精度向量拷贝 y = x",
            "cublasSdot": "单精度向量点积",
            "cublasDdot": "双精度向量点积",
        }
        return descriptions.get(api_name, f"cuBLAS {api_name} API")

    def create_repository_info(self) -> GPURepository:
        """创建 cuBLAS 仓库信息"""
        return GPURepository(
            repo_id="nvidia_cublas",
            repo_name="NVIDIA cuBLAS",
            platform=GPUPlatform.CUBLAS,
            documentation_url="https://docs.nvidia.com/cuda/cublas/",
            api_surface=self.CORE_APIS,
        )
