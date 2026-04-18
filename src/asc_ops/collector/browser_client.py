# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
Playwright 浏览器渲染采集器

用于采集需要 JS 渲染才能获取完整内容的昇腾文档页面
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional, Set
from datetime import datetime
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)


@dataclass
class BrowserAPILink:
    """API 链接信息"""
    api_id: str
    name: str
    url: str
    category: str = "util"
    subcategory: str = ""
    # 完整导航路径，如 ["SIMT API", "精度转换", "rintf"]
    nav_path: tuple[str, ...] = ()


@dataclass
class BrowserCollectionResult:
    """浏览器采集结果"""
    total_discovered: int
    new_links: List[BrowserAPILink]
    elapsed_seconds: float


# 昇腾官方 CANN API 文档列表页
LIST_PAGE_URL = "https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/API/ascendcopapi/atlasascendc_api_07_0003.html"

# 基于官方导航结构的API分类映射
# 格式: API名称 -> (顶级分类, 二级分类, 三级分类)
# 根据 CANN 9.0.0-beta.2 官方文档导航结构
API_NAV_MAPPING: dict[str, tuple[str, str, str]] = {
    # ===== 基础数据结构 =====
    "LocalTensor": ("基础数据结构", "LocalTensor", ""),
    "GlobalTensor": ("基础数据结构", "GlobalTensor", ""),
    "Coordinate": ("基础数据结构", "Coordinate", ""),
    "Layout": ("基础数据结构", "Layout", ""),
    "TensorTrait": ("基础数据结构", "TensorTrait", ""),
    "TPosition": ("基础数据结构", "TPosition", ""),
    "ShapeInfo": ("基础数据结构", "ShapeInfo", ""),
    "ListTensorDesc": ("基础数据结构", "ListTensorDesc", ""),
    "TensorDesc": ("基础数据结构", "TensorDesc", ""),
    "UnaryRepeatParams": ("基础数据结构", "UnaryRepeatParams", ""),
    "BinaryRepeatParams": ("基础数据结构", "BinaryRepeatParams", ""),
    "complex32": ("基础数据结构", "内置数据类型", ""),
    "complex64": ("基础数据结构", "内置数据类型", ""),

    # ===== 基础API - Memory数据搬运 =====
    "DataCopy": ("基础API", "Memory数据搬运", "DataCopy"),
    "Copy": ("基础API", "Memory数据搬运", "Copy"),
    "SetPadValue": ("基础API", "Memory数据搬运", "SetPadValue"),
    "SetLoopModePara": ("基础API", "Memory数据搬运", "SetLoopModePara"),
    "ResetLoopModePara": ("基础API", "Memory数据搬运", "ResetLoopModePara"),
    "BroadCastVecToMM": ("基础API", "Memory数据搬运", "BroadCastVecToMM"),

    # ===== 基础API - Memory矢量计算 - 基础算术 =====
    "Exp": ("基础API", "Memory矢量计算", "基础算术"),
    "Ln": ("基础API", "Memory矢量计算", "基础算术"),
    "Abs": ("基础API", "Memory矢量计算", "基础算术"),
    "Reciprocal": ("基础API", "Memory矢量计算", "基础算术"),
    "Sqrt": ("基础API", "Memory矢量计算", "基础算术"),
    "Rsqrt": ("基础API", "Memory矢量计算", "基础算术"),
    "Relu": ("基础API", "Memory矢量计算", "基础算术"),
    "Neg": ("基础API", "Memory矢量计算", "基础算术"),
    "Add": ("基础API", "Memory矢量计算", "基础算术"),
    "Sub": ("基础API", "Memory矢量计算", "基础算术"),
    "Mul": ("基础API", "Memory矢量计算", "基础算术"),
    "Div": ("基础API", "Memory矢量计算", "基础算术"),
    "Max": ("基础API", "Memory矢量计算", "基础算术"),
    "Min": ("基础API", "Memory矢量计算", "基础算术"),
    "Adds": ("基础API", "Memory矢量计算", "基础算术"),
    "Muls": ("基础API", "Memory矢量计算", "基础算术"),
    "Maxs": ("基础API", "Memory矢量计算", "基础算术"),
    "Mins": ("基础API", "Memory矢量计算", "基础算术"),
    "Subs": ("基础API", "Memory矢量计算", "基础算术"),
    "Divs": ("基础API", "Memory矢量计算", "基础算术"),
    "LeakyRelu": ("基础API", "Memory矢量计算", "基础算术"),

    # ===== 基础API - Memory矢量计算 - 逻辑计算 =====
    "Not": ("基础API", "Memory矢量计算", "逻辑计算"),
    "And": ("基础API", "Memory矢量计算", "逻辑计算"),
    "Or": ("基础API", "Memory矢量计算", "逻辑计算"),
    "Ands": ("基础API", "Memory矢量计算", "逻辑计算"),
    "Ors": ("基础API", "Memory矢量计算", "逻辑计算"),
    "ShiftLeft": ("基础API", "Memory矢量计算", "逻辑计算"),
    "ShiftRight": ("基础API", "Memory矢量计算", "逻辑计算"),

    # ===== 基础API - Memory矢量计算 - 复合计算 =====
    "Axpy": ("基础API", "Memory矢量计算", "复合计算"),
    "CastDequant": ("基础API", "Memory矢量计算", "复合计算"),
    "AddRelu": ("基础API", "Memory矢量计算", "复合计算"),
    "AddReluCast": ("基础API", "Memory矢量计算", "复合计算"),
    "AddDeqRelu": ("基础API", "Memory矢量计算", "复合计算"),
    "MulRelu": ("基础API", "Memory矢量计算", "复合计算"),

    # ===== 基础API - Memory矢量计算 - 归约 =====
    "ReduceSum": ("基础API", "Memory矢量计算", "归约"),
    "ReduceMax": ("基础API", "Memory矢量计算", "归约"),
    "ReduceMin": ("基础API", "Memory矢量计算", "归约"),

    # ===== 基础API - Memory矢量计算 - 类型转换 =====
    "Cast": ("基础API", "Memory矢量计算", "类型转换"),
    "Quant": ("基础API", "Memory矢量计算", "类型转换"),
    "Dequant": ("基础API", "Memory矢量计算", "类型转换"),

    # ===== SIMT API =====
    "asc_vf_call": ("SIMT API", "核函数定义", ""),
    "asc_syncthreads": ("SIMT API", "同步函数", ""),
    "asc_threadfence": ("SIMT API", "同步函数", ""),
    "asc_threadfence_block": ("SIMT API", "同步函数", ""),

    # SIMT 数学函数
    "tanf": ("SIMT API", "数学函数", ""),
    "tanhf": ("SIMT API", "数学函数", ""),
    "htanh": ("SIMT API", "数学函数", ""),
    "h2tanh": ("SIMT API", "数学函数", ""),
    "tanpif": ("SIMT API", "数学函数", ""),
    "atanf": ("SIMT API", "数学函数", ""),
    "atan2f": ("SIMT API", "数学函数", ""),
    "atanhf": ("SIMT API", "数学函数", ""),
    "expf": ("SIMT API", "数学函数", ""),
    "hexp": ("SIMT API", "数学函数", ""),
    "h2exp": ("SIMT API", "数学函数", ""),
    "exp2f": ("SIMT API", "数学函数", ""),
    "hexp2": ("SIMT API", "数学函数", ""),
    "h2exp2": ("SIMT API", "数学函数", ""),
    "exp10f": ("SIMT API", "数学函数", ""),
    "hexp10": ("SIMT API", "数学函数", ""),
    "h2exp10": ("SIMT API", "数学函数", ""),
    "expm1f": ("SIMT API", "数学函数", ""),
    "logf": ("SIMT API", "数学函数", ""),
    "hlog": ("SIMT API", "数学函数", ""),
    "h2log": ("SIMT API", "数学函数", ""),
    "log2f": ("SIMT API", "数学函数", ""),
    "hlog2": ("SIMT API", "数学函数", ""),
    "h2log2": ("SIMT API", "数学函数", ""),
    "log10f": ("SIMT API", "数学函数", ""),
    "hlog10": ("SIMT API", "数学函数", ""),
    "h2log10": ("SIMT API", "数学函数", ""),
    "log1pf": ("SIMT API", "数学函数", ""),
    "logbf": ("SIMT API", "数学函数", ""),
    "ilogbf": ("SIMT API", "数学函数", ""),
    "cosf": ("SIMT API", "数学函数", ""),
    "hcos": ("SIMT API", "数学函数", ""),
    "h2cos": ("SIMT API", "数学函数", ""),
    "coshf": ("SIMT API", "数学函数", ""),
    "cospif": ("SIMT API", "数学函数", ""),
    "acosf": ("SIMT API", "数学函数", ""),
    "acoshf": ("SIMT API", "数学函数", ""),
    "sinf": ("SIMT API", "数学函数", ""),
    "hsin": ("SIMT API", "数学函数", ""),
    "h2sin": ("SIMT API", "数学函数", ""),
    "sinhf": ("SIMT API", "数学函数", ""),
    "sinpif": ("SIMT API", "数学函数", ""),
    "asinf": ("SIMT API", "数学函数", ""),
    "asinhf": ("SIMT API", "数学函数", ""),
    "sincosf": ("SIMT API", "数学函数", ""),
    "sincospif": ("SIMT API", "数学函数", ""),
    "frexpf": ("SIMT API", "数学函数", ""),
    "ldexpf": ("SIMT API", "数学函数", ""),
    "sqrtf": ("SIMT API", "数学函数", ""),
    "hsqrt": ("SIMT API", "数学函数", ""),
    "h2sqrt": ("SIMT API", "数学函数", ""),
    "rsqrtf": ("SIMT API", "数学函数", ""),
    "hrsqrt": ("SIMT API", "数学函数", ""),
    "h2rsqrt": ("SIMT API", "数学函数", ""),
    "hrcp": ("SIMT API", "数学函数", ""),
    "h2rcp": ("SIMT API", "数学函数", ""),
    "hypotf": ("SIMT API", "数学函数", ""),
    "rhypotf": ("SIMT API", "数学函数", ""),
    "powf": ("SIMT API", "数学函数", ""),
    "norm3df": ("SIMT API", "数学函数", ""),
    "rnorm3df": ("SIMT API", "数学函数", ""),
    "norm4df": ("SIMT API", "数学函数", ""),
    "rnorm4df": ("SIMT API", "数学函数", ""),
    "normf": ("SIMT API", "数学函数", ""),
    "rnormf": ("SIMT API", "数学函数", ""),
    "cbrtf": ("SIMT API", "数学函数", ""),
    "rcbrtf": ("SIMT API", "数学函数", ""),
    "erff": ("SIMT API", "数学函数", ""),
    "erfcf": ("SIMT API", "数学函数", ""),
    "erfinvf": ("SIMT API", "数学函数", ""),
    "erfcinvf": ("SIMT API", "数学函数", ""),
    "erfcxf": ("SIMT API", "数学函数", ""),
    "tgammaf": ("SIMT API", "数学函数", ""),
    "lgammaf": ("SIMT API", "数学函数", ""),
    "cyl_bessel_i0f": ("SIMT API", "数学函数", ""),
    "cyl_bessel_i1f": ("SIMT API", "数学函数", ""),
    "normcdff": ("SIMT API", "数学函数", ""),
    "normcdfinvf": ("SIMT API", "数学函数", ""),
    "j0f": ("SIMT API", "数学函数", ""),
    "j1f": ("SIMT API", "数学函数", ""),
    "jnf": ("SIMT API", "数学函数", ""),
    "y0f": ("SIMT API", "数学函数", ""),
    "y1f": ("SIMT API", "数学函数", ""),
    "ynf": ("SIMT API", "数学函数", ""),
    "fabsf": ("SIMT API", "数学函数", ""),
    "__habs": ("SIMT API", "数学函数", ""),
    "fmaf": ("SIMT API", "数学函数", ""),
    "__hfma": ("SIMT API", "数学函数", ""),
    "fmaxf": ("SIMT API", "数学函数", ""),
    "__hmax": ("SIMT API", "数学函数", ""),
    "fminf": ("SIMT API", "数学函数", ""),
    "__hmin": ("SIMT API", "数学函数", ""),
    "fdimf": ("SIMT API", "数学函数", ""),
    "remquof": ("SIMT API", "数学函数", ""),
    "fmodf": ("SIMT API", "数学函数", ""),
    "remainderf": ("SIMT API", "数学函数", ""),
    "copysignf": ("SIMT API", "数学函数", ""),
    "nearbyintf": ("SIMT API", "数学函数", ""),
    "nextafterf": ("SIMT API", "数学函数", ""),
    "scalbnf": ("SIMT API", "数学函数", ""),
    "scalblnf": ("SIMT API", "数学函数", ""),
    "modff": ("SIMT API", "数学函数", ""),
    "labs": ("SIMT API", "数学函数", ""),
    "llabs": ("SIMT API", "数学函数", ""),
    "llmax": ("SIMT API", "数学函数", ""),
    "ullmax": ("SIMT API", "数学函数", ""),
    "umax": ("SIMT API", "数学函数", ""),
    "llmin": ("SIMT API", "数学函数", ""),
    "ullmin": ("SIMT API", "数学函数", ""),
    "umin": ("SIMT API", "数学函数", ""),
    "fdividef": ("SIMT API", "数学函数", ""),
    "signbit": ("SIMT API", "数学函数", ""),

    # SIMT 精度转换
    "rintf": ("SIMT API", "精度转换", ""),
    "hrint": ("SIMT API", "精度转换", ""),
    "h2rint": ("SIMT API", "精度转换", ""),
    "lrintf": ("SIMT API", "精度转换", ""),
    "llrintf": ("SIMT API", "精度转换", ""),
    "roundf": ("SIMT API", "精度转换", ""),
    "lroundf": ("SIMT API", "精度转换", ""),
    "llroundf": ("SIMT API", "精度转换", ""),
    "floorf": ("SIMT API", "精度转换", ""),
    "hfloor": ("SIMT API", "精度转换", ""),
    "h2floor": ("SIMT API", "精度转换", ""),
    "ceilf": ("SIMT API", "精度转换", ""),
    "hceil": ("SIMT API", "精度转换", ""),
    "h2ceil": ("SIMT API", "精度转换", ""),
    "truncf": ("SIMT API", "精度转换", ""),
    "htrunc": ("SIMT API", "精度转换", ""),
    "h2trunc": ("SIMT API", "精度转换", ""),

    # SIMT 比较函数
    "isfinite": ("SIMT API", "比较函数", ""),
    "isnan": ("SIMT API", "比较函数", ""),
    "__hisnan": ("SIMT API", "比较函数", ""),
    "isinf": ("SIMT API", "比较函数", ""),
    "__hisinf": ("SIMT API", "比较函数", ""),

    # SIMT Atomic函数
    "asc_atomic_add": ("SIMT API", "Atomic函数", ""),
    "asc_atomic_sub": ("SIMT API", "Atomic函数", ""),
    "asc_atomic_exch": ("SIMT API", "Atomic函数", ""),
    "asc_atomic_max": ("SIMT API", "Atomic函数", ""),
    "asc_atomic_min": ("SIMT API", "Atomic函数", ""),
    "asc_atomic_inc": ("SIMT API", "Atomic函数", ""),
    "asc_atomic_dec": ("SIMT API", "Atomic函数", ""),
    "asc_atomic_cas": ("SIMT API", "Atomic函数", ""),
    "asc_atomic_and": ("SIMT API", "Atomic函数", ""),
    "asc_atomic_or": ("SIMT API", "Atomic函数", ""),
    "asc_atomic_xor": ("SIMT API", "Atomic函数", ""),

    # SIMT Warp函数
    "asc_all": ("SIMT API", "Warp函数", ""),
    "asc_any": ("SIMT API", "Warp函数", ""),
    "asc_ballot": ("SIMT API", "Warp函数", ""),
    "asc_activemask": ("SIMT API", "Warp函数", ""),
    "asc_shfl": ("SIMT API", "Warp函数", ""),
    "asc_shfl_up": ("SIMT API", "Warp函数", ""),
    "asc_shfl_down": ("SIMT API", "Warp函数", ""),
    "asc_shfl_xor": ("SIMT API", "Warp函数", ""),
    "asc_reduce_add": ("SIMT API", "Warp函数", ""),
    "asc_reduce_max": ("SIMT API", "Warp函数", ""),
    "asc_reduce_min": ("SIMT API", "Warp函数", ""),

    # SIMT 类型转换
    "__float2float_rn": ("SIMT API", "类型转换", ""),
    "__float2float_rz": ("SIMT API", "类型转换", ""),
    "__float2float_rd": ("SIMT API", "类型转换", ""),
    "__float2float_ru": ("SIMT API", "类型转换", ""),
    "__float2float_rna": ("SIMT API", "类型转换", ""),
    "__float2half": ("SIMT API", "类型转换", ""),
    "__float2half_rn": ("SIMT API", "类型转换", ""),
    "__float2half_rn_sat": ("SIMT API", "类型转换", ""),
    "__float22half2_rn_sat": ("SIMT API", "类型转换", ""),
    "__float2half_rz": ("SIMT API", "类型转换", ""),
    "__float2half_rz_sat": ("SIMT API", "类型转换", ""),
    "__float22half2_rz": ("SIMT API", "类型转换", ""),
    "__float22half2_rz_sat": ("SIMT API", "类型转换", ""),
    "__float2half_rd": ("SIMT API", "类型转换", ""),
    "__float2half_rd_sat": ("SIMT API", "类型转换", ""),
    "__float22half2_rd": ("SIMT API", "类型转换", ""),
    "__float22half2_rd_sat": ("SIMT API", "类型转换", ""),
    "__float2half_ru": ("SIMT API", "类型转换", ""),
    "__float2half_ru_sat": ("SIMT API", "类型转换", ""),
    "__float22half2_ru": ("SIMT API", "类型转换", ""),
    "__float22half2_ru_sat": ("SIMT API", "类型转换", ""),
    "__float2half_rna": ("SIMT API", "类型转换", ""),
    "__float2half_rna_sat": ("SIMT API", "类型转换", ""),
    "__float22half2_rna": ("SIMT API", "类型转换", ""),
    "__float22half2_rna_sat": ("SIMT API", "类型转换", ""),
    "__float2half_ro": ("SIMT API", "类型转换", ""),
    "__float2half_ro_sat": ("SIMT API", "类型转换", ""),
    "__float22half2_ro": ("SIMT API", "类型转换", ""),
    "__float22half2_ro_sat": ("SIMT API", "类型转换", ""),
    "__float2bfloat16": ("SIMT API", "类型转换", ""),
    "__float2bfloat16_rn": ("SIMT API", "类型转换", ""),
    "__float2bfloat16_rn_sat": ("SIMT API", "类型转换", ""),
    "__float22bfloat162_rn_sat": ("SIMT API", "类型转换", ""),
    "__float2bfloat16_rz": ("SIMT API", "类型转换", ""),
    "__float2bfloat16_rz_sat": ("SIMT API", "类型转换", ""),
    "__float22bfloat162_rz": ("SIMT API", "类型转换", ""),
    "__float22bfloat162_rz_sat": ("SIMT API", "类型转换", ""),
    "__float2bfloat16_rd": ("SIMT API", "类型转换", ""),
    "__float2bfloat16_rd_sat": ("SIMT API", "类型转换", ""),
    "__float22bfloat162_rd": ("SIMT API", "类型转换", ""),
    "__float22bfloat162_rd_sat": ("SIMT API", "类型转换", ""),
    "__float2bfloat16_ru": ("SIMT API", "类型转换", ""),
    "__float2bfloat16_ru_sat": ("SIMT API", "类型转换", ""),
    "__float22bfloat162_ru": ("SIMT API", "类型转换", ""),
    "__float22bfloat162_ru_sat": ("SIMT API", "类型转换", ""),
    "__float2bfloat16_rna": ("SIMT API", "类型转换", ""),
    "__float2bfloat16_rna_sat": ("SIMT API", "类型转换", ""),
    "__float22bfloat162_rna": ("SIMT API", "类型转换", ""),
    "__float22bfloat162_rna_sat": ("SIMT API", "类型转换", ""),
    "__float2uint_rn": ("SIMT API", "类型转换", ""),
    "__float2uint_rz": ("SIMT API", "类型转换", ""),
    "__float2uint_rd": ("SIMT API", "类型转换", ""),
    "__float2uint_ru": ("SIMT API", "类型转换", ""),
    "__float2uint_rna": ("SIMT API", "类型转换", ""),
    "__float2int_rn": ("SIMT API", "类型转换", ""),
    "__float2int_rz": ("SIMT API", "类型转换", ""),
    "__float2int_rd": ("SIMT API", "类型转换", ""),
    "__float2int_ru": ("SIMT API", "类型转换", ""),
    "__float2int_rna": ("SIMT API", "类型转换", ""),
    "__float2ull_rn": ("SIMT API", "类型转换", ""),
    "__float2ull_rz": ("SIMT API", "类型转换", ""),
    "__float2ull_rd": ("SIMT API", "类型转换", ""),
    "__float2ull_ru": ("SIMT API", "类型转换", ""),
    "__float2ull_rna": ("SIMT API", "类型转换", ""),
    "__float2ll_rn": ("SIMT API", "类型转换", ""),
    "__float2ll_rz": ("SIMT API", "类型转换", ""),
    "__float2ll_rd": ("SIMT API", "类型转换", ""),
    "__float2ll_ru": ("SIMT API", "类型转换", ""),
    "__float2ll_rna": ("SIMT API", "类型转换", ""),
    "__float22hif82_rna": ("SIMT API", "类型转换", ""),
    "__float22hif82_rna_sat": ("SIMT API", "类型转换", ""),
    "__float22hif82_rh": ("SIMT API", "类型转换", ""),
    "__float22hif82_rh_sat": ("SIMT API", "类型转换", ""),
    "__asc_cvt_float2_to_fp8x2": ("SIMT API", "类型转换", ""),
    "__half2float": ("SIMT API", "类型转换", ""),
    "__half2half_rn": ("SIMT API", "类型转换", ""),
    "__half2half_rz": ("SIMT API", "类型转换", ""),
    "__half2half_rd": ("SIMT API", "类型转换", ""),
    "__half2half_ru": ("SIMT API", "类型转换", ""),
    "__half2half_rna": ("SIMT API", "类型转换", ""),
    "__half2bfloat16_rn": ("SIMT API", "类型转换", ""),
    "__half2bfloat16_rz": ("SIMT API", "类型转换", ""),
    "__half2bfloat16_rd": ("SIMT API", "类型转换", ""),
    "__half2bfloat16_ru": ("SIMT API", "类型转换", ""),
    "__half2bfloat16_rna": ("SIMT API", "类型转换", ""),
    "__half2uint_rn": ("SIMT API", "类型转换", ""),
    "__half2uint_rz": ("SIMT API", "类型转换", ""),
    "__half2uint_rd": ("SIMT API", "类型转换", ""),
    "__half2uint_ru": ("SIMT API", "类型转换", ""),
    "__half2uint_rna": ("SIMT API", "类型转换", ""),
    "__half2int_rn": ("SIMT API", "类型转换", ""),
    "__half2int_rz": ("SIMT API", "类型转换", ""),
    "__half2int_rd": ("SIMT API", "类型转换", ""),
    "__half2int_ru": ("SIMT API", "类型转换", ""),
    "__half2int_rna": ("SIMT API", "类型转换", ""),
    "__half2ull_rn": ("SIMT API", "类型转换", ""),
    "__half2ull_rz": ("SIMT API", "类型转换", ""),
    "__half2ull_rd": ("SIMT API", "类型转换", ""),
    "__half2ull_ru": ("SIMT API", "类型转换", ""),
    "__half2ull_rna": ("SIMT API", "类型转换", ""),
    "__half2ll_rn": ("SIMT API", "类型转换", ""),
    "__half2ll_rz": ("SIMT API", "类型转换", ""),
    "__half2ll_rd": ("SIMT API", "类型转换", ""),
    "__half2ll_ru": ("SIMT API", "类型转换", ""),
    "__half2ll_rna": ("SIMT API", "类型转换", ""),
    "__half22hif82_rna": ("SIMT API", "类型转换", ""),
    "__half22hif82_rna_sat": ("SIMT API", "类型转换", ""),
    "__half22hif82_rh": ("SIMT API", "类型转换", ""),
    "__half22hif82_rh_sat": ("SIMT API", "类型转换", ""),
    "__bfloat162half_rn": ("SIMT API", "类型转换", ""),
    "__bfloat162half_rn_sat": ("SIMT API", "类型转换", ""),
    "__bfloat162half_rz": ("SIMT API", "类型转换", ""),
    "__bfloat162half_rz_sat": ("SIMT API", "类型转换", ""),
    "__bfloat162half_rd": ("SIMT API", "类型转换", ""),
    "__bfloat162half_rd_sat": ("SIMT API", "类型转换", ""),
    "__bfloat162half_ru": ("SIMT API", "类型转换", ""),
    "__bfloat162half_ru_sat": ("SIMT API", "类型转换", ""),
    "__bfloat162half_rna": ("SIMT API", "类型转换", ""),
    "__bfloat162half_rna_sat": ("SIMT API", "类型转换", ""),
    "__bfloat162float": ("SIMT API", "类型转换", ""),
    "__bfloat162bfloat16_rn": ("SIMT API", "类型转换", ""),
    "__bfloat162bfloat16_rz": ("SIMT API", "类型转换", ""),
    "__bfloat162bfloat16_rd": ("SIMT API", "类型转换", ""),
    "__bfloat162bfloat16_ru": ("SIMT API", "类型转换", ""),
    "__bfloat162bfloat16_rna": ("SIMT API", "类型转换", ""),
    "__bfloat162uint_rn": ("SIMT API", "类型转换", ""),
    "__bfloat162uint_rz": ("SIMT API", "类型转换", ""),
    "__bfloat162uint_rd": ("SIMT API", "类型转换", ""),
    "__bfloat162uint_ru": ("SIMT API", "类型转换", ""),
    "__bfloat162uint_rna": ("SIMT API", "类型转换", ""),
    "__bfloat162int_rn": ("SIMT API", "类型转换", ""),
    "__bfloat162int_rz": ("SIMT API", "类型转换", ""),
    "__bfloat162int_rd": ("SIMT API", "类型转换", ""),
    "__bfloat162int_ru": ("SIMT API", "类型转换", ""),
    "__bfloat162int_rna": ("SIMT API", "类型转换", ""),
    "__bfloat162ull_rn": ("SIMT API", "类型转换", ""),
    "__bfloat162ull_rz": ("SIMT API", "类型转换", ""),
    "__bfloat162ull_rd": ("SIMT API", "类型转换", ""),
    "__bfloat162ull_ru": ("SIMT API", "类型转换", ""),
    "__bfloat162ull_rna": ("SIMT API", "类型转换", ""),
    "__bfloat162ll_rn": ("SIMT API", "类型转换", ""),
    "__bfloat162ll_rz": ("SIMT API", "类型转换", ""),
    "__bfloat162ll_rd": ("SIMT API", "类型转换", ""),
    "__bfloat162ll_ru": ("SIMT API", "类型转换", ""),
    "__bfloat162ll_rna": ("SIMT API", "类型转换", ""),
    "__uint2float_rn": ("SIMT API", "类型转换", ""),
    "__uint2float_rz": ("SIMT API", "类型转换", ""),
    "__uint2float_rd": ("SIMT API", "类型转换", ""),
    "__uint2float_ru": ("SIMT API", "类型转换", ""),
    "__uint2float_rna": ("SIMT API", "类型转换", ""),
    "__uint2half_rn": ("SIMT API", "类型转换", ""),
    "__uint2half_rn_sat": ("SIMT API", "类型转换", ""),
    "__uint2half_rz": ("SIMT API", "类型转换", ""),
    "__uint2half_rz_sat": ("SIMT API", "类型转换", ""),
    "__uint2half_rd": ("SIMT API", "类型转换", ""),
    "__uint2half_rd_sat": ("SIMT API", "类型转换", ""),
    "__uint2half_ru": ("SIMT API", "类型转换", ""),
    "__uint2half_ru_sat": ("SIMT API", "类型转换", ""),
    "__uint2half_rna": ("SIMT API", "类型转换", ""),
    "__uint2half_rna_sat": ("SIMT API", "类型转换", ""),
    "__uint2bfloat16_rn": ("SIMT API", "类型转换", ""),
    "__uint2bfloat16_rz": ("SIMT API", "类型转换", ""),
    "__uint2bfloat16_rd": ("SIMT API", "类型转换", ""),
    "__uint2bfloat16_ru": ("SIMT API", "类型转换", ""),
    "__uint2bfloat16_rna": ("SIMT API", "类型转换", ""),
    "__int2float_rn": ("SIMT API", "类型转换", ""),
    "__int2float_rz": ("SIMT API", "类型转换", ""),
    "__int2float_rd": ("SIMT API", "类型转换", ""),
    "__int2float_ru": ("SIMT API", "类型转换", ""),
    "__int2float_rna": ("SIMT API", "类型转换", ""),
    "__int2half_rn": ("SIMT API", "类型转换", ""),
    "__int2half_rn_sat": ("SIMT API", "类型转换", ""),
    "__int2half_rz": ("SIMT API", "类型转换", ""),
    "__int2half_rz_sat": ("SIMT API", "类型转换", ""),
    "__int2half_rd": ("SIMT API", "类型转换", ""),
    "__int2half_rd_sat": ("SIMT API", "类型转换", ""),
    "__int2half_ru": ("SIMT API", "类型转换", ""),
    "__int2half_ru_sat": ("SIMT API", "类型转换", ""),
    "__int2half_rna": ("SIMT API", "类型转换", ""),
    "__int2half_rna_sat": ("SIMT API", "类型转换", ""),
    "__int2bfloat16_rn": ("SIMT API", "类型转换", ""),
    "__int2bfloat16_rz": ("SIMT API", "类型转换", ""),
    "__int2bfloat16_rd": ("SIMT API", "类型转换", ""),
    "__int2bfloat16_ru": ("SIMT API", "类型转换", ""),
    "__int2bfloat16_rna": ("SIMT API", "类型转换", ""),
    "__ull2float_rn": ("SIMT API", "类型转换", ""),
    "__ull2float_rz": ("SIMT API", "类型转换", ""),
    "__ull2float_rd": ("SIMT API", "类型转换", ""),
    "__ull2float_ru": ("SIMT API", "类型转换", ""),
    "__ull2float_rna": ("SIMT API", "类型转换", ""),
    "__ull2half_rn": ("SIMT API", "类型转换", ""),
    "__ull2half_rz": ("SIMT API", "类型转换", ""),
    "__ull2half_rd": ("SIMT API", "类型转换", ""),
    "__ull2half_ru": ("SIMT API", "类型转换", ""),
    "__ull2half_rna": ("SIMT API", "类型转换", ""),
    "__ull2bfloat16_rn": ("SIMT API", "类型转换", ""),
    "__ull2bfloat16_rz": ("SIMT API", "类型转换", ""),
    "__ull2bfloat16_rd": ("SIMT API", "类型转换", ""),
    "__ull2bfloat16_ru": ("SIMT API", "类型转换", ""),
    "__ull2bfloat16_rna": ("SIMT API", "类型转换", ""),
    "__ll2float_rn": ("SIMT API", "类型转换", ""),
    "__ll2float_rz": ("SIMT API", "类型转换", ""),
    "__ll2float_rd": ("SIMT API", "类型转换", ""),
    "__ll2float_ru": ("SIMT API", "类型转换", ""),
    "__ll2float_rna": ("SIMT API", "类型转换", ""),
    "__ll2half_rn": ("SIMT API", "类型转换", ""),
    "__ll2half_rz": ("SIMT API", "类型转换", ""),
    "__ll2half_rd": ("SIMT API", "类型转换", ""),
    "__ll2half_ru": ("SIMT API", "类型转换", ""),
    "__ll2half_rna": ("SIMT API", "类型转换", ""),
    "__ll2bfloat16_rn": ("SIMT API", "类型转换", ""),
    "__ll2bfloat16_rz": ("SIMT API", "类型转换", ""),
    "__ll2bfloat16_rd": ("SIMT API", "类型转换", ""),
    "__ll2bfloat16_ru": ("SIMT API", "类型转换", ""),
    "__ll2bfloat16_rna": ("SIMT API", "类型转换", ""),
    "__hif822float2": ("SIMT API", "类型转换", ""),
    "__hif822half2": ("SIMT API", "类型转换", ""),
    "__e4m3x22float2": ("SIMT API", "类型转换", ""),
    "__e5m2x22float2": ("SIMT API", "类型转换", ""),
    "__float2bfloat162_rn": ("SIMT API", "类型转换", ""),
    "__floats2bfloat162_rn": ("SIMT API", "类型转换", ""),
    "__float22bfloat162_rn": ("SIMT API", "类型转换", ""),
    "__bfloat162bfloat162": ("SIMT API", "类型转换", ""),
    "__halves2bfloat162": ("SIMT API", "类型转换", ""),
    "__high2bfloat16": ("SIMT API", "类型转换", ""),
    "__high2bfloat162": ("SIMT API", "类型转换", ""),
    "__high2float": ("SIMT API", "类型转换", ""),
    "__highs2bfloat162": ("SIMT API", "类型转换", ""),
    "__low2bfloat16": ("SIMT API", "类型转换", ""),
    "__low2bfloat162": ("SIMT API", "类型转换", ""),
    "__low2float": ("SIMT API", "类型转换", ""),
    "__lowhigh2highlow": ("SIMT API", "类型转换", ""),
    "__lows2bfloat162": ("SIMT API", "类型转换", ""),
    "__bfloat1622float2": ("SIMT API", "类型转换", ""),
    "__floats2half2_rn": ("SIMT API", "类型转换", ""),
    "__float22half2_rn": ("SIMT API", "类型转换", ""),
    "__low2half": ("SIMT API", "类型转换", ""),
    "__low2half2": ("SIMT API", "类型转换", ""),
    "__high2half": ("SIMT API", "类型转换", ""),
    "__high2half2": ("SIMT API", "类型转换", ""),
    "__highs2half2": ("SIMT API", "类型转换", ""),
    "__lows2half2": ("SIMT API", "类型转换", ""),
    "__halves2half2": ("SIMT API", "类型转换", ""),
    "__half22float2": ("SIMT API", "类型转换", ""),
    "__int_as_float": ("SIMT API", "类型转换", ""),
    "__uint_as_float": ("SIMT API", "类型转换", ""),
    "__float_as_int": ("SIMT API", "类型转换", ""),
    "__float_as_uint": ("SIMT API", "类型转换", ""),
    "__ushort_as_half": ("SIMT API", "类型转换", ""),
    "__ushort_as_bfloat16": ("SIMT API", "类型转换", ""),

    # SIMT 向量类型构造函数
    "make_int2": ("SIMT API", "向量类型构造函数", ""),
    "make_int3": ("SIMT API", "向量类型构造函数", ""),
    "make_int4": ("SIMT API", "向量类型构造函数", ""),
    "make_uint2": ("SIMT API", "向量类型构造函数", ""),
    "make_uint3": ("SIMT API", "向量类型构造函数", ""),
    "make_uint4": ("SIMT API", "向量类型构造函数", ""),
    "make_ulonglong2": ("SIMT API", "向量类型构造函数", ""),
    "make_ulonglong3": ("SIMT API", "向量类型构造函数", ""),
    "make_ulonglong4": ("SIMT API", "向量类型构造函数", ""),
    "make_longlong2": ("SIMT API", "向量类型构造函数", ""),
    "make_longlong3": ("SIMT API", "向量类型构造函数", ""),
    "make_longlong4": ("SIMT API", "向量类型构造函数", ""),
    "make_ulong2": ("SIMT API", "向量类型构造函数", ""),
    "make_ulong3": ("SIMT API", "向量类型构造函数", ""),
    "make_ulong4": ("SIMT API", "向量类型构造函数", ""),
    "make_long2": ("SIMT API", "向量类型构造函数", ""),
    "make_long3": ("SIMT API", "向量类型构造函数", ""),
    "make_long4": ("SIMT API", "向量类型构造函数", ""),
    "make_float2": ("SIMT API", "向量类型构造函数", ""),
    "make_float3": ("SIMT API", "向量类型构造函数", ""),
    "make_float4": ("SIMT API", "向量类型构造函数", ""),
    "make_short2": ("SIMT API", "向量类型构造函数", ""),
    "make_short3": ("SIMT API", "向量类型构造函数", ""),
    "make_short4": ("SIMT API", "向量类型构造函数", ""),
    "make_ushort2": ("SIMT API", "向量类型构造函数", ""),
    "make_ushort3": ("SIMT API", "向量类型构造函数", ""),
    "make_ushort4": ("SIMT API", "向量类型构造函数", ""),
    "make_uchar2": ("SIMT API", "向量类型构造函数", ""),
    "make_uchar3": ("SIMT API", "向量类型构造函数", ""),
    "make_uchar4": ("SIMT API", "向量类型构造函数", ""),
    "make_char2": ("SIMT API", "向量类型构造函数", ""),
    "make_char3": ("SIMT API", "向量类型构造函数", ""),
    "make_char4": ("SIMT API", "向量类型构造函数", ""),
    "make_half2": ("SIMT API", "向量类型构造函数", ""),
    "make_bfloat162": ("SIMT API", "向量类型构造函数", ""),

    # SIMT 使能Cache Hints的Load/Store函数
    "asc_ldcg": ("SIMT API", "使能Cache Hints的Load/Store函数", ""),
    "asc_ldca": ("SIMT API", "使能Cache Hints的Load/Store函数", ""),
    "asc_stcg": ("SIMT API", "使能Cache Hints的Load/Store函数", ""),
    "asc_stwt": ("SIMT API", "使能Cache Hints的Load/Store函数", ""),

    # ===== Utils API =====
    # C++标准库
    "max": ("Utils API", "C++标准库", "算法"),
    "min": ("Utils API", "C++标准库", "算法"),
    "abs": ("Utils API", "C++标准库", "数学函数"),
    "sqrt": ("Utils API", "C++标准库", "数学函数"),
    "tuple": ("Utils API", "C++标准库", "容器函数"),
    "get": ("Utils API", "C++标准库", "容器函数"),
    "make_tuple": ("Utils API", "C++标准库", "容器函数"),
    # 类型特性略...

    # 平台信息获取
    "PlatformAscendC": ("Utils API", "平台信息获取", ""),
    "PlatformAscendCManager": ("Utils API", "平台信息获取", ""),

    # ===== AI CPU API =====
    "printf": ("AI CPU API", "", ""),
    "assert": ("AI CPU API", "", ""),
    "DataStoreBarrier": ("AI CPU API", "", ""),

    # ===== C API - 数据结构 =====
    "asc_fill_value_config": ("C API", "数据结构", ""),
    "asc_l13d_fmatrix_config": ("C API", "数据结构", ""),
    "asc_load3d_v2_config": ("C API", "数据结构", ""),
    "asc_ndim_pad_count_config": ("C API", "数据结构", ""),
    "asc_store_atomic_config": ("C API", "数据结构", ""),

    # ===== C API - Cube数据搬运 =====
    "asc_fill_l0a": ("C API", "Cube数据搬运", ""),
    "asc_fill_l0b": ("C API", "Cube数据搬运", ""),
    "asc_fill_l1": ("C API", "Cube数据搬运", ""),
    "asc_copy_l0c2gm": ("C API", "Cube数据搬运", ""),
    "asc_copy_l0c2l1": ("C API", "Cube数据搬运", ""),
    "asc_copy_l12l0a": ("C API", "Cube数据搬运", ""),
    "asc_copy_l12l0b": ("C API", "Cube数据搬运", ""),
    "asc_copy_l12bt": ("C API", "Cube数据搬运", ""),
    "asc_copy_l12fb": ("C API", "Cube数据搬运", ""),
    "asc_load_image_to_cbuf": ("C API", "Cube数据搬运", ""),
    "asc_set_l13d_padding": ("C API", "Cube数据搬运", ""),
    "asc_set_l13d_rpt": ("C API", "Cube数据搬运", ""),
    "asc_set_l13d_size": ("C API", "Cube数据搬运", ""),
    "asc_set_l0c_copy_params": ("C API", "Cube数据搬运", ""),
    "asc_set_l0c_copy_prequant": ("C API", "Cube数据搬运", ""),

    # ===== C API - 向量数据搬运 =====
    "asc_copy_gm2ub": ("C API", "向量数据搬运", ""),
    "asc_copy_gm2ub_align": ("C API", "向量数据搬运", ""),
    "asc_copy_ub2gm": ("C API", "向量数据搬运", ""),
    "asc_copy_ub2gm_align": ("C API", "向量数据搬运", ""),
    "asc_copy_ub2ub": ("C API", "向量数据搬运", ""),
    "asc_ndim_copy_gm2ub": ("C API", "向量数据搬运", ""),

    # ===== C API - 向量计算 =====
    "asc_abs": ("C API", "向量计算", ""),
    "asc_add": ("C API", "向量计算", ""),
    "asc_add_relu": ("C API", "向量计算", ""),
    "asc_add_scalar": ("C API", "向量计算", ""),
    "asc_and": ("C API", "向量计算", ""),
    "asc_axpy": ("C API", "向量计算", ""),
    "asc_bfloat162float": ("C API", "向量计算", ""),
    "asc_bfloat162int32": ("C API", "向量计算", ""),
    "asc_bitsort": ("C API", "向量计算", ""),
    "asc_brcb": ("C API", "向量计算", ""),
    "asc_copy": ("C API", "向量计算", ""),
    "asc_datablock_reduce_max": ("C API", "向量计算", ""),
    "asc_datablock_reduce_min": ("C API", "向量计算", ""),
    "asc_datablock_reduce_sum": ("C API", "向量计算", ""),
    "asc_deq_int162b8": ("C API", "向量计算", ""),
    "asc_deq_int322half": ("C API", "向量计算", ""),
    "asc_div": ("C API", "向量计算", ""),
    "asc_duplicate": ("C API", "向量计算", ""),
    "asc_eq": ("C API", "向量计算", ""),
    "asc_eq_scalar": ("C API", "向量计算", ""),
    "asc_exp": ("C API", "向量计算", ""),
    "asc_float2bf16": ("C API", "向量计算", ""),
    "asc_float2float": ("C API", "向量计算", ""),
    "asc_float2half": ("C API", "向量计算", ""),
    "asc_float2int16": ("C API", "向量计算", ""),
    "asc_float2int32": ("C API", "向量计算", ""),
    "asc_float2int64": ("C API", "向量计算", ""),
    "asc_fma": ("C API", "向量计算", ""),
    "asc_gather": ("C API", "向量计算", ""),
    "asc_gather_datablock": ("C API", "向量计算", ""),
    "asc_ge": ("C API", "向量计算", ""),
    "asc_ge_scalar": ("C API", "向量计算", ""),
    "asc_get_cmp_mask": ("C API", "向量计算", ""),
    "asc_get_reduce_max_cnt": ("C API", "向量计算", ""),
    "asc_get_reduce_min_cnt": ("C API", "向量计算", ""),
    "asc_get_rsvd_count": ("C API", "向量计算", ""),
    "asc_get_vms4_sr": ("C API", "向量计算", ""),
    "asc_gt": ("C API", "向量计算", ""),
    "asc_gt_scalar": ("C API", "向量计算", ""),
    "asc_half2float": ("C API", "向量计算", ""),
    "asc_half2int16": ("C API", "向量计算", ""),
    "asc_half2int32": ("C API", "向量计算", ""),
    "asc_half2int4": ("C API", "向量计算", ""),
    "asc_half2int8": ("C API", "向量计算", ""),
    "asc_half2uint8": ("C API", "向量计算", ""),
    "asc_int162float": ("C API", "向量计算", ""),
    "asc_int162half": ("C API", "向量计算", ""),
    "asc_int322float": ("C API", "向量计算", ""),
    "asc_int322int16": ("C API", "向量计算", ""),
    "asc_int322int64": ("C API", "向量计算", ""),
    "asc_int42half": ("C API", "向量计算", ""),
    "asc_int642float": ("C API", "向量计算", ""),
    "asc_int642int32": ("C API", "向量计算", ""),
    "asc_int82half": ("C API", "向量计算", ""),
    "asc_int82int16": ("C API", "向量计算", ""),
    "asc_int922half": ("C API", "向量计算", ""),
    "asc_le": ("C API", "向量计算", ""),
    "asc_leakyrelu": ("C API", "向量计算", ""),
    "asc_le_scalar": ("C API", "向量计算", ""),
    "asc_log": ("C API", "向量计算", ""),
    "asc_lt": ("C API", "向量计算", ""),
    "asc_lt_scalar": ("C API", "向量计算", ""),
    "asc_max": ("C API", "向量计算", ""),
    "asc_max_scalar": ("C API", "向量计算", ""),
    "asc_min": ("C API", "向量计算", ""),
    "asc_min_scalar": ("C API", "向量计算", ""),
    "asc_mrgsort4": ("C API", "向量计算", ""),
    "asc_mul": ("C API", "向量计算", ""),
    "asc_mul_add": ("C API", "向量计算", ""),
    "asc_mul_add_relu": ("C API", "向量计算", ""),
    "asc_mul_cast_half2int8": ("C API", "向量计算", ""),
    "asc_mul_cast_half2uint8": ("C API", "向量计算", ""),
    "asc_mul_scalar": ("C API", "向量计算", ""),
    "asc_ne": ("C API", "向量计算", ""),
    "asc_ne_scalar": ("C API", "向量计算", ""),
    "asc_not": ("C API", "向量计算", ""),
    "asc_or": ("C API", "向量计算", ""),
    "asc_pair_reduce_sum": ("C API", "向量计算", ""),
    "asc_rcp": ("C API", "向量计算", ""),
    "asc_reduce": ("C API", "向量计算", ""),
    "asc_repeat_reduce_max": ("C API", "向量计算", ""),
    "asc_repeat_reduce_min": ("C API", "向量计算", ""),
    "asc_repeat_reduce_sum": ("C API", "向量计算", ""),
    "asc_relu": ("C API", "向量计算", ""),
    "asc_rsqrt": ("C API", "向量计算", ""),
    "asc_select": ("C API", "向量计算", ""),
    "asc_set_cmp_mask": ("C API", "向量计算", ""),
    "asc_set_deq_scale": ("C API", "向量计算", ""),
    "asc_set_mask_count": ("C API", "向量计算", ""),
    "asc_set_mask_norm": ("C API", "向量计算", ""),
    "asc_set_vector_mask": ("C API", "向量计算", ""),
    "asc_set_va_reg": ("C API", "向量计算", ""),
    "asc_shiftleft": ("C API", "向量计算", ""),
    "asc_shiftright": ("C API", "向量计算", ""),
    "asc_sqrt": ("C API", "向量计算", ""),
    "asc_sub": ("C API", "向量计算", ""),
    "asc_sub_relu": ("C API", "向量计算", ""),
    "asc_sub_scalar": ("C API", "向量计算", ""),
    "asc_transto5hd": ("C API", "向量计算", ""),
    "asc_transpose": ("C API", "向量计算", ""),
    "asc_uint82half": ("C API", "向量计算", ""),
    "asc_vaxpy": ("C API", "向量计算", ""),
    "asc_vdeq_int162b8": ("C API", "向量计算", ""),

    # ===== C API - 标量计算 =====
    "asc_clz": ("C API", "标量计算", ""),
    "asc_ffs": ("C API", "标量计算", ""),
    "asc_ffz": ("C API", "标量计算", ""),
    "asc_popc": ("C API", "标量计算", ""),
    "asc_sflbits": ("C API", "标量计算", ""),
    "asc_clear_nthbit": ("C API", "标量计算", ""),
    "asc_set_nthbit": ("C API", "标量计算", ""),
    "asc_zero_bits_cnt": ("C API", "标量计算", ""),

    # ===== C API - Cube计算 =====
    "asc_enable_hf32": ("C API", "Cube计算", ""),
    "asc_enable_hf32_trans": ("C API", "Cube计算", ""),
    "asc_mmad": ("C API", "Cube计算", ""),
    "asc_mmad_sparse": ("C API", "Cube计算", ""),
    "asc_set_fp32_mode": ("C API", "Cube计算", ""),
    "asc_set_l0c2gm_config": ("C API", "Cube计算", ""),
    "asc_set_mmad_direction_m": ("C API", "Cube计算", ""),
    "asc_set_mmad_direction_n": ("C API", "Cube计算", ""),

    # ===== C API - 同步 =====
    "asc_sync": ("C API", "同步", ""),
    "asc_sync_block_arrive": ("C API", "同步", ""),
    "asc_sync_block_wait": ("C API", "同步", ""),
    "asc_sync_data_barrier": ("C API", "同步", ""),
    "asc_sync_mte2": ("C API", "同步", ""),
    "asc_sync_mte3": ("C API", "同步", ""),
    "asc_sync_notify": ("C API", "同步", ""),
    "asc_sync_pipe": ("C API", "同步", ""),
    "asc_sync_vec": ("C API", "同步", ""),
    "asc_sync_wait": ("C API", "同步", ""),

    # ===== C API - 系统变量 =====
    "asc_get_arch_ver": ("C API", "系统变量", ""),
    "asc_get_block_idx": ("C API", "系统变量", ""),
    "asc_get_block_num": ("C API", "系统变量", ""),
    "asc_get_core_id": ("C API", "系统变量", ""),
    "asc_get_ctrl": ("C API", "系统变量", ""),
    "asc_get_ffts_base_addr": ("C API", "系统变量", ""),
    "asc_get_phy_buf_addr": ("C API", "系统变量", ""),
    "asc_get_program_counter": ("C API", "系统变量", ""),
    "asc_get_sub_block_id": ("C API", "系统变量", ""),
    "asc_get_sub_block_num": ("C API", "系统变量", ""),
    "asc_get_system_cycle": ("C API", "系统变量", ""),
    "asc_set_ctrl": ("C API", "系统变量", ""),
    "asc_set_ffts_base_addr": ("C API", "系统变量", ""),

    # ===== C API - 缓存控制 =====
    "asc_dcci": ("C API", "缓存控制", ""),
    "asc_datacache_preload": ("C API", "缓存控制", ""),
    "asc_get_icache_preload_status": ("C API", "缓存控制", ""),
    "asc_icache_preload": ("C API", "缓存控制", ""),

    # ===== C API - SIMD Atomic =====
    "asc_set_atomic_add": ("C API", "SIMD Atomic", ""),
    "asc_set_atomic_max": ("C API", "SIMD Atomic", ""),
    "asc_set_atomic_min": ("C API", "SIMD Atomic", ""),
    "asc_set_atomic_none": ("C API", "SIMD Atomic", ""),
    "asc_set_store_atomic_config_v1": ("C API", "SIMD Atomic", ""),
    "asc_set_store_atomic_config_v2": ("C API", "SIMD Atomic", ""),
    "asc_get_store_atomic_config": ("C API", "SIMD Atomic", ""),

    # ===== C API - 寄存器操作 =====
    "asc_abs_sub": ("C API", "寄存器操作", ""),
    "asc_addc": ("C API", "寄存器操作", ""),
    "asc_arange": ("C API", "寄存器操作", ""),
    "asc_bfloat162e1m2x2": ("C API", "寄存器操作", ""),
    "asc_bfloat162e2m1x2": ("C API", "寄存器操作", ""),
    "asc_bfloat162half": ("C API", "寄存器操作", ""),
    "asc_clear_ar_spr": ("C API", "寄存器操作", ""),
    "asc_cumulative_histogram": ("C API", "寄存器操作", ""),
    "asc_create_iter_reg": ("C API", "寄存器操作", ""),
    "asc_create_mask": ("C API", "寄存器操作", ""),
    "asc_deintlv": ("C API", "寄存器操作", ""),
    "asc_duplicate_scalar": ("C API", "寄存器操作", ""),
    "asc_e1m2x22bfloat16": ("C API", "寄存器操作", ""),
    "asc_e2m1x22bfloat16": ("C API", "寄存器操作", ""),
    "asc_e4m32float": ("C API", "寄存器操作", ""),
    "asc_e5m22float": ("C API", "寄存器操作", ""),
    "asc_exp_sub": ("C API", "寄存器操作", ""),
    "asc_float2e4m3": ("C API", "寄存器操作", ""),
    "asc_float2e5m2": ("C API", "寄存器操作", ""),
    "asc_float2hif8": ("C API", "寄存器操作", ""),
    "asc_frequency_histogram": ("C API", "寄存器操作", ""),
    "asc_half2bf16": ("C API", "寄存器操作", ""),
    "asc_half2hif8": ("C API", "寄存器操作", ""),
    "asc_half2int4x2": ("C API", "寄存器操作", ""),
    "asc_hif82half": ("C API", "寄存器操作", ""),
    "asc_int162int32": ("C API", "寄存器操作", ""),
    "asc_int162uint32": ("C API", "寄存器操作", ""),
    "asc_int162uint8": ("C API", "寄存器操作", ""),
    "asc_int322uint16": ("C API", "寄存器操作", ""),
    "asc_int322uint8": ("C API", "寄存器操作", ""),
    "asc_int4x22bfloat16": ("C API", "寄存器操作", ""),
    "asc_int4x22half": ("C API", "寄存器操作", ""),
    "asc_int4x22int16": ("C API", "寄存器操作", ""),
    "asc_int82int16": ("C API", "寄存器操作", ""),
    "asc_int82int32": ("C API", "寄存器操作", ""),
    "asc_intlv": ("C API", "寄存器操作", ""),
    "asc_load": ("C API", "寄存器操作", ""),
    "asc_loadalign": ("C API", "寄存器操作", ""),
    "asc_loadunalign": ("C API", "寄存器操作", ""),
    "asc_loadunalign_pre": ("C API", "寄存器操作", ""),
    "asc_ln": ("C API", "寄存器操作", ""),
    "asc_madd": ("C API", "寄存器操作", ""),
    "asc_mask_spr": ("C API", "寄存器操作", ""),
    "asc_mem_bar": ("C API", "寄存器操作", ""),
    "asc_mull": ("C API", "寄存器操作", ""),
    "asc_muls": ("C API", "寄存器操作", ""),
    "asc_neg": ("C API", "寄存器操作", ""),
    "asc_pack": ("C API", "寄存器操作", ""),
    "asc_prelu": ("C API", "寄存器操作", ""),
    "asc_set_mask_spr": ("C API", "寄存器操作", ""),
    "asc_shiftleft_scalar": ("C API", "寄存器操作", ""),
    "asc_shiftright_scalar": ("C API", "寄存器操作", ""),
    "asc_squeeze": ("C API", "寄存器操作", ""),
    "asc_store": ("C API", "寄存器操作", ""),
    "asc_storealign": ("C API", "寄存器操作", ""),
    "asc_storeunalign": ("C API", "寄存器操作", ""),
    "asc_storeunalign_postupdate": ("C API", "寄存器操作", ""),
    "asc_subc": ("C API", "寄存器操作", ""),
    "asc_truncate": ("C API", "寄存器操作", ""),
    "asc_uint162uint32": ("C API", "寄存器操作", ""),
    "asc_uint162uint8": ("C API", "寄存器操作", ""),
    "asc_uint322int16": ("C API", "寄存器操作", ""),
    "asc_uint322uint16": ("C API", "寄存器操作", ""),
    "asc_uint322uint8": ("C API", "寄存器操作", ""),
    "asc_uint82uint16": ("C API", "寄存器操作", ""),
    "asc_uint82uint32": ("C API", "寄存器操作", ""),
    "asc_unpack": ("C API", "寄存器操作", ""),
    "asc_unsqueeze": ("C API", "寄存器操作", ""),
    "asc_update_mask": ("C API", "寄存器操作", ""),
    "asc_xor": ("C API", "寄存器操作", ""),

    # ===== C API - 杂项 =====
    "asc_init": ("C API", "杂项", ""),

    # ===== 推断的导航路径 (基于命名模式, 2026-04-18) =====

    # ===== SIMT API - Atomic函数 =====
    "AtomicCas": ("SIMT API", "Atomic函数", ""),
    "AtomicExch": ("SIMT API", "Atomic函数", ""),
    "AtomicMax": ("SIMT API", "Atomic函数", ""),
    "AtomicMin": ("SIMT API", "Atomic函数", ""),
    "GetStoreAtomicConfig": ("SIMT API", "Atomic函数", ""),
    "SetAtomicAdd": ("SIMT API", "Atomic函数", ""),
    "SetAtomicMax": ("SIMT API", "Atomic函数", ""),
    "SetAtomicMin": ("SIMT API", "Atomic函数", ""),
    "SetAtomicType": ("SIMT API", "Atomic函数", ""),
    "SetStoreAtomicConfig": ("SIMT API", "Atomic函数", ""),

    # ===== SIMT API - 同步函数 =====
    "GetCmpMask": ("SIMT API", "同步函数", ""),
    "GetCtrlSpr": ("SIMT API", "同步函数", ""),
    "GetReduceRepeatMaxMinSpr": ("SIMT API", "同步函数", ""),
    "GetReduceRepeatSumSpr": ("SIMT API", "同步函数", ""),
    "GetSFFValue": ("SIMT API", "同步函数", ""),
    "ResetCtrlSpr": ("SIMT API", "同步函数", ""),
    "ResetMask": ("SIMT API", "同步函数", ""),
    "SetCmpMask": ("SIMT API", "同步函数", ""),
    "SetCtrlSpr": ("SIMT API", "同步函数", ""),
    "SetMaskCount": ("SIMT API", "同步函数", ""),
    "SetMaskNorm": ("SIMT API", "同步函数", ""),
    "SetVectorMask": ("SIMT API", "同步函数", ""),

    # ===== SIMT API - 数学函数 =====
    "AbsSub": ("SIMT API", "数学函数", ""),
    "Acos": ("SIMT API", "数学函数", ""),
    "Asin": ("SIMT API", "数学函数", ""),
    "Atan": ("SIMT API", "数学函数", ""),
    "Ceil": ("SIMT API", "数学函数", ""),
    "Cos": ("SIMT API", "数学函数", ""),
    "Cosh": ("SIMT API", "数学函数", ""),
    "Digamma": ("SIMT API", "数学函数", ""),
    "Erf": ("SIMT API", "数学函数", ""),
    "Erfc": ("SIMT API", "数学函数", ""),
    "ExpSub": ("SIMT API", "数学函数", ""),
    "Floor": ("SIMT API", "数学函数", ""),
    "Fma": ("SIMT API", "数学函数", ""),
    "Fmod": ("SIMT API", "数学函数", ""),
    "Frac": ("SIMT API", "数学函数", ""),
    "Hypot": ("SIMT API", "数学函数", ""),
    "Lgamma": ("SIMT API", "数学函数", ""),
    "Log": ("SIMT API", "数学函数", ""),
    "Round": ("SIMT API", "数学函数", ""),
    "Sign": ("SIMT API", "数学函数", ""),
    "Sin": ("SIMT API", "数学函数", ""),
    "Sinh": ("SIMT API", "数学函数", ""),
    "Tan": ("SIMT API", "数学函数", ""),
    "Tanh": ("SIMT API", "数学函数", ""),
    "Trunc": ("SIMT API", "数学函数", ""),

    # ===== SIMT API - 比较函数 =====
    "BitwiseAnd": ("SIMT API", "比较函数", ""),
    "BitwiseNot": ("SIMT API", "比较函数", ""),
    "BitwiseOr": ("SIMT API", "比较函数", ""),
    "BitwiseXor": ("SIMT API", "比较函数", ""),
    "Compare": ("SIMT API", "比较函数", ""),
    "Compares": ("SIMT API", "比较函数", ""),
    "Compare（结果存入寄存器）": ("SIMT API", "比较函数", ""),
    "Compare（结果存放入寄存器）": ("SIMT API", "比较函数", ""),
    "LogicalAnd": ("SIMT API", "比较函数", ""),
    "LogicalAnds": ("SIMT API", "比较函数", ""),
    "LogicalNot": ("SIMT API", "比较函数", ""),
    "LogicalOr": ("SIMT API", "比较函数", ""),
    "LogicalOrs": ("SIMT API", "比较函数", ""),
    "LogicalXor": ("SIMT API", "比较函数", ""),
    "Not": ("SIMT API", "比较函数", ""),
    "Or": ("SIMT API", "比较函数", ""),
    "Select": ("SIMT API", "比较函数", ""),
    "Xor": ("SIMT API", "比较函数", ""),

    # ===== SIMT API - 精度转换 =====
    "Rint": ("SIMT API", "精度转换", ""),
    "fdivdef": ("SIMT API", "精度转换", ""),
    "nearbyIntf": ("SIMT API", "精度转换", ""),

    # ===== 基础API - HCCL通信 =====
    "HCCL通信类": ("基础API", "HCCL通信", ""),
    "MetricsProfStart": ("基础API", "HCCL通信", ""),
    "MetricsProfStop": ("基础API", "HCCL通信", ""),

    # ===== 基础API - Memory数据搬运 =====
    "Broadcast": ("基础API", "Memory数据搬运", ""),
    "Concat": ("基础API", "Memory数据搬运", ""),
    "DataCopyPad": ("基础API", "Memory数据搬运", ""),
    "DeInterleave": ("基础API", "Memory数据搬运", ""),
    "DumpTensor": ("基础API", "Memory数据搬运", ""),
    "Duplicate": ("基础API", "Memory数据搬运", ""),
    "Extract": ("基础API", "Memory数据搬运", ""),
    "Fill": ("基础API", "Memory数据搬运", ""),
    "Interleave": ("基础API", "Memory数据搬运", ""),
    "Load3D": ("基础API", "Memory数据搬运", ""),
    "Load3Dv1/Load3Dv2": ("基础API", "Memory数据搬运", ""),
    "LoadData": ("基础API", "Memory数据搬运", ""),
    "LoadDataUnzip": ("基础API", "Memory数据搬运", ""),
    "LoadDataWithSparse": ("基础API", "Memory数据搬运", ""),
    "LoadDataWithTranspose": ("基础API", "Memory数据搬运", ""),
    "LoadImageToLocal": ("基础API", "Memory数据搬运", ""),
    "LoadUnZipIndex": ("基础API", "Memory数据搬运", ""),
    "Pad": ("基础API", "Memory数据搬运", ""),
    "TransData": ("基础API", "Memory数据搬运", ""),
    "TransDataTo5HD": ("基础API", "Memory数据搬运", ""),
    "Transpose": ("基础API", "Memory数据搬运", ""),
    "UnPad": ("基础API", "Memory数据搬运", ""),
    "VectorPadding": ("基础API", "Memory数据搬运", ""),

    # ===== 基础API - Memory矢量计算 =====
    "BlockReduceMax": ("基础API", "Memory矢量计算", ""),
    "BlockReduceMin": ("基础API", "Memory矢量计算", ""),
    "BlockReduceSum": ("基础API", "Memory矢量计算", ""),
    "Brcb": ("基础API", "Memory矢量计算", ""),
    "ClampMax": ("基础API", "Memory矢量计算", ""),
    "ClampMin": ("基础API", "Memory矢量计算", ""),
    "CountBitsCntSameAsSignBit": ("基础API", "Memory矢量计算", ""),
    "CountLeadingZero": ("基础API", "Memory矢量计算", ""),
    "CumSum": ("基础API", "Memory矢量计算", ""),
    "Gather": ("基础API", "Memory矢量计算", ""),
    "GatherMask": ("基础API", "Memory矢量计算", ""),
    "Gatherb": ("基础API", "Memory矢量计算", ""),
    "GetBitCount": ("基础API", "Memory矢量计算", ""),
    "Mean": ("基础API", "Memory矢量计算", ""),
    "PairReduceSum": ("基础API", "Memory矢量计算", ""),
    "ReduceAll": ("基础API", "Memory矢量计算", ""),
    "ReduceAny": ("基础API", "Memory矢量计算", ""),
    "ReduceMean": ("基础API", "Memory矢量计算", ""),
    "ReduceProd": ("基础API", "Memory矢量计算", ""),
    "ReduceXorSum": ("基础API", "Memory矢量计算", ""),
    "RepeatReduceSum": ("基础API", "Memory矢量计算", ""),
    "Scatter": ("基础API", "Memory矢量计算", ""),
    "Sum": ("基础API", "Memory矢量计算", ""),
    "Where": ("基础API", "Memory矢量计算", ""),
    "WholeReduceMax": ("基础API", "Memory矢量计算", ""),
    "WholeReduceMin": ("基础API", "Memory矢量计算", ""),
    "WholeReduceSum": ("基础API", "Memory矢量计算", ""),

    # ===== 基础API - 矩阵计算 =====
    "BilinearInterpolation": ("基础API", "矩阵计算", ""),
    "Conv2D": ("基础API", "矩阵计算", ""),
    "Conv3D": ("基础API", "矩阵计算", ""),
    "Conv3DBackpropFilter": ("基础API", "矩阵计算", ""),
    "Conv3DBackpropInput": ("基础API", "矩阵计算", ""),
    "Gemm": ("基础API", "矩阵计算", ""),
    "Matmul": ("基础API", "矩阵计算", ""),
    "Mmad": ("基础API", "矩阵计算", ""),
    "MmadWithSparse": ("基础API", "矩阵计算", ""),

    # ===== 基础API - 归一化 =====
    "BatchNorm": ("基础API", "归一化", ""),
    "DeepNorm": ("基础API", "归一化", ""),
    "GroupNorm": ("基础API", "归一化", ""),
    "LayerNorm": ("基础API", "归一化", ""),
    "LayerNormGrad": ("基础API", "归一化", ""),
    "LayerNormGradBeta": ("基础API", "归一化", ""),
    "Normalize": ("基础API", "归一化", ""),
    "RmsNorm": ("基础API", "归一化", ""),
    "WelfordFinalize": ("基础API", "归一化", ""),
    "WelfordUpdate": ("基础API", "归一化", ""),

    # ===== 基础API - 激活函数 =====
    "AdjustSoftMaxRes": ("基础API", "激活函数", ""),
    "FasterGelu": ("基础API", "激活函数", ""),
    "FasterGeluV2": ("基础API", "激活函数", ""),
    "FusedMulAdd": ("基础API", "激活函数", ""),
    "GeGLU": ("基础API", "激活函数", ""),
    "Gelu": ("基础API", "激活函数", ""),
    "LogSoftMax": ("基础API", "激活函数", ""),
    "MulAddDst": ("基础API", "激活函数", ""),
    "MulAddRelu": ("基础API", "激活函数", ""),
    "MulCast": ("基础API", "激活函数", ""),
    "MulAdd": ("基础API", "激活函数", ""),
    "MulsCast": ("基础API", "激活函数", ""),
    "Prelu": ("基础API", "激活函数", ""),
    "ReGlu": ("基础API", "激活函数", ""),
    "Relu": ("基础API", "激活函数", ""),
    "Sigmoid": ("基础API", "激活函数", ""),
    "Silu": ("基础API", "激活函数", ""),
    "SimpleSoftMax": ("基础API", "激活函数", ""),
    "SoftmaxFlash": ("基础API", "激活函数", ""),
    "SoftmaxFlashV2": ("基础API", "激活函数", ""),
    "SoftmaxFlashV3": ("基础API", "激活函数", ""),
    "SoftmaxGrad": ("基础API", "激活函数", ""),
    "SoftmaxGradFront": ("基础API", "激活函数", ""),
    "SoftMax": ("基础API", "激活函数", ""),
    "SubRelu": ("基础API", "激活函数", ""),
    "SubReluCast": ("基础API", "激活函数", ""),
    "Swish": ("基础API", "激活函数", ""),
    "SwiGLU": ("基础API", "激活函数", ""),

    # ===== 基础API - 排序 =====
    "CreateVecIndex": ("基础API", "排序", ""),
    "GetMrgSortResult": ("基础API", "排序", ""),
    "MrgSort": ("基础API", "排序", ""),
    "MrgSort4": ("基础API", "排序", ""),
    "RpSort16": ("基础API", "排序", ""),
    "Sort": ("基础API", "排序", ""),
    "Sort32": ("基础API", "排序", ""),
    "TopK": ("基础API", "排序", ""),

    # ===== 基础API - 量化 =====
    "AntiQuantize": ("基础API", "量化", ""),
    "AscendAntiQuant": ("基础API", "量化", ""),
    "AscendDequant": ("基础API", "量化", ""),
    "AscendQuant": ("基础API", "量化", ""),
    "Dequantize": ("基础API", "量化", ""),
    "Quantize": ("基础API", "量化", ""),

    # ===== 基础API - 随机函数 =====
    "PhiloxRandom": ("基础API", "随机函数", ""),

    # ===== 基础API - 同步 =====
    "AllocMutexID": ("基础API", "同步", ""),
    "AllocMutexID/ReleaseMutexID": ("基础API", "同步", ""),
    "Async": ("基础API", "同步", ""),
    "CrossCoreSetFlag": ("基础API", "同步", ""),
    "CrossCoreWaitFlag": ("基础API", "同步", ""),
    "DataSyncBarrier": ("基础API", "同步", ""),
    "DisableDmaAtomic": ("基础API", "同步", ""),
    "GroupBarrier": ("基础API", "同步", ""),
    "IBSet": ("基础API", "同步", ""),
    "IBWait": ("基础API", "同步", ""),
    "Mutex": ("基础API", "同步", ""),
    "NotifyNextBlock": ("基础API", "同步", ""),
    "PipeBarrier": ("基础API", "同步", ""),
    "ReleaseMutexID": ("基础API", "同步", ""),
    "SyncAll": ("基础API", "同步", ""),
    "WaitPreBlock": ("基础API", "同步", ""),
    "WaitPreTaskEnd": ("基础API", "同步", ""),

    # ===== 基础API - 初始化与配置 =====
    "ContextBuilder": ("基础API", "初始化与配置", ""),
    "DEVICE_IMPL_OP_OPTILING": ("基础API", "初始化与配置", ""),
    "GET_TILING_DATA": ("基础API", "初始化与配置", ""),
    "GET_TILING_DATA_MEMBER": ("基础API", "初始化与配置", ""),
    "GET_TILING_DATA_PTR_WITH_STRUCT": ("基础API", "初始化与配置", ""),
    "GET_TILING_DATA_WITH_STRUCT": ("基础API", "初始化与配置", ""),
    "GET_TPL_TILING_KEY": ("基础API", "初始化与配置", ""),
    "GmAlloc": ("基础API", "初始化与配置", ""),
    "GmFree": ("基础API", "初始化与配置", ""),
    "ICPU_RUN_KF": ("基础API", "初始化与配置", ""),
    "ICPU_SET_TILING_KEY": ("基础API", "初始化与配置", ""),
    "KERNEL_TASK_TYPE": ("基础API", "初始化与配置", ""),
    "KERNEL_TASK_TYPE_DEFAULT": ("基础API", "初始化与配置", ""),
    "OpAICoreConfig": ("基础API", "初始化与配置", ""),
    "OpAICoreDef": ("基础API", "初始化与配置", ""),
    "OpAttrDef": ("基础API", "初始化与配置", ""),
    "OpDef": ("基础API", "初始化与配置", ""),
    "OpMC2Def": ("基础API", "初始化与配置", ""),
    "OpParamDef": ("基础API", "初始化与配置", ""),
    "OpTilingRegistry": ("基础API", "初始化与配置", ""),
    "REGISTER_NONE_TILING": ("基础API", "初始化与配置", ""),
    "REGISTER_TILING_DEFAULT": ("基础API", "初始化与配置", ""),
    "REGISTER_TILING_FOR_TILINGKEY": ("基础API", "初始化与配置", ""),
    "SetKernelMode": ("基础API", "初始化与配置", ""),
    "TBuf": ("基础API", "初始化与配置", ""),
    "TBufPool": ("基础API", "初始化与配置", ""),
    "TILING_KEY_IS": ("基础API", "初始化与配置", ""),
    "TPipe": ("基础API", "初始化与配置", ""),
    "TQue": ("基础API", "初始化与配置", ""),
    "TQueBind": ("基础API", "初始化与配置", ""),
    "TQueSync": ("基础API", "初始化与配置", ""),
    "InitDetermineComputeWorkspace": ("基础API", "初始化与配置", ""),
    "InitSocState": ("基础API", "初始化与配置", ""),
    "InitSpmBuffer": ("基础API", "初始化与配置", ""),
    "ReadSpmBuffer": ("基础API", "初始化与配置", ""),
    "WriteSpmBuffer": ("基础API", "初始化与配置", ""),

    # ===== 基础API - 数据同步与缓存 =====
    "DataCacheCleanAndInvalid": ("基础API", "数据同步与缓存", ""),
    "DataCachePreload": ("基础API", "数据同步与缓存", ""),
    "Fixpipe": ("基础API", "数据同步与缓存", ""),
    "GetDataBlockSizeInBytes": ("基础API", "数据同步与缓存", ""),
    "GetICachePreloadStatus": ("基础API", "数据同步与缓存", ""),
    "GetRuntimeUBSize": ("基础API", "数据同步与缓存", ""),
    "GetUBSizeInBytes": ("基础API", "数据同步与缓存", ""),
    "ICachePreLoad": ("基础API", "数据同步与缓存", ""),
    "ReadGmByPassDCache": ("基础API", "数据同步与缓存", ""),
    "SetFixPipeAddr": ("基础API", "数据同步与缓存", ""),
    "SetFixPipeClipRelu": ("基础API", "数据同步与缓存", ""),
    "SetFixPipeConfig": ("基础API", "数据同步与缓存", ""),
    "SetFixpipeNz2ndFlag": ("基础API", "数据同步与缓存", ""),
    "SetFixpipePreQuantFlag": ("基础API", "数据同步与缓存", ""),
    "SetFmatrix": ("基础API", "数据同步与缓存", ""),
    "SetHF32Mode": ("基础API", "数据同步与缓存", ""),
    "SetHF32TransMode": ("基础API", "数据同步与缓存", ""),
    "SetLoadDataBoundary": ("基础API", "数据同步与缓存", ""),
    "SetLoadDataPaddingValue": ("基础API", "数据同步与缓存", ""),
    "SetLoadDataRepeat": ("基础API", "数据同步与缓存", ""),
    "SetMMColumnMajor": ("基础API", "数据同步与缓存", ""),
    "SetMMRowMajor": ("基础API", "数据同步与缓存", ""),
    "WriteGmByPassDCache": ("基础API", "数据同步与缓存", ""),

    # ===== 基础API - 其他 =====
    "ASC_CPU_LOG": ("基础API", "其他", ""),
    "DropOut": ("基础API", "其他", ""),
    "KfcWorkspace": ("基础API", "其他", ""),
    "NumericLimits": ("基础API", "其他", ""),
    "ProposalConcat": ("基础API", "其他", ""),
    "ProposalExtract": ("基础API", "其他", ""),

    # ===== Utils API - C++标准库 =====
    "Trap": ("Utils API", "C++标准库", ""),
    "__trap": ("Utils API", "C++标准库", ""),
    "add_const": ("Utils API", "C++标准库", ""),
    "add_cv": ("Utils API", "C++标准库", ""),
    "add_lvalue_reference": ("Utils API", "C++标准库", ""),
    "add_pointer": ("Utils API", "C++标准库", ""),
    "add_rvalue_reference": ("Utils API", "C++标准库", ""),
    "add_volatile": ("Utils API", "C++标准库", ""),
    "ascendc_assert": ("Utils API", "C++标准库", ""),
    "clock": ("Utils API", "C++标准库", ""),
    "conditional": ("Utils API", "C++标准库", ""),
    "enable_if": ("Utils API", "C++标准库", ""),
    "fdivdef": ("Utils API", "C++标准库", ""),
    "integer_sequence": ("Utils API", "C++标准库", ""),
    "integral_constant": ("Utils API", "C++标准库", ""),
    "is_array": ("Utils API", "C++标准库", ""),
    "is_base_of": ("Utils API", "C++标准库", ""),
    "is_const": ("Utils API", "C++标准库", ""),
    "is_convertible": ("Utils API", "C++标准库", ""),
    "is_floating_point": ("Utils API", "C++标准库", ""),
    "is_integral": ("Utils API", "C++标准库", ""),
    "is_pointer": ("Utils API", "C++标准库", ""),
    "is_reference": ("Utils API", "C++标准库", ""),
    "is_same": ("Utils API", "C++标准库", ""),
    "is_void": ("Utils API", "C++标准库", ""),
    "remove_const": ("Utils API", "C++标准库", ""),
    "remove_cv": ("Utils API", "C++标准库", ""),
    "remove_pointer": ("Utils API", "C++标准库", ""),
    "remove_volatile": ("Utils API", "C++标准库", ""),

    # ===== Utils API - RTC =====
    "aclrtcCompileProg": ("Utils API", "RTC", ""),
    "aclrtcCreateProg": ("Utils API", "RTC", ""),
    "aclrtcDestroyProg": ("Utils API", "RTC", ""),
    "aclrtcGetBinData": ("Utils API", "RTC", ""),
    "aclrtcGetBinDataSize": ("Utils API", "RTC", ""),
    "aclrtcGetCompileLog": ("Utils API", "RTC", ""),
    "aclrtcGetCompileLogSize": ("Utils API", "RTC", ""),

    # ===== Utils API - Tiling =====
    "TilingData结构定义": ("Utils API", "Tiling", ""),
    "TilingData结构注册": ("Utils API", "Tiling", ""),
    "SetTilingData": ("Utils API", "Tiling", ""),
    "TilingData": ("Utils API", "Tiling", ""),

    # ===== Utils API - 原型注册与管理 =====
    "ASCENDC_TPL_SEL_PARAM": ("Utils API", "原型注册与管理", ""),
    "SetAippFunctions": ("Utils API", "原型注册与管理", ""),
    "SetDeqScale": ("Utils API", "原型注册与管理", ""),
    "SetFlag/WaitFlag": ("Utils API", "原型注册与管理", ""),
    "SetNextTaskStart": ("Utils API", "原型注册与管理", ""),
    "原型注册接口（OP_ADD）": ("Utils API", "原型注册与管理", ""),
    "模板参数定义": ("Utils API", "原型注册与管理", ""),

    # ===== Utils API - 平台信息获取 =====
    "GetArchVersion": ("Utils API", "平台信息获取", ""),
    "GetArchVer": ("Utils API", "平台信息获取", ""),
    "GetBlockIdx": ("Utils API", "平台信息获取", ""),
    "GetBlockNum": ("Utils API", "平台信息获取", ""),
    "GetCoreId": ("Utils API", "平台信息获取", ""),
    "GetProgramCounter": ("Utils API", "平台信息获取", ""),
    "GetSubBlockIdx": ("Utils API", "平台信息获取", ""),
    "GetSubBlockNum": ("Utils API", "平台信息获取", ""),
    "GetSysWorkSpacePtr": ("Utils API", "平台信息获取", ""),
    "GetSystemCycle": ("Utils API", "平台信息获取", ""),
    "GetTaskRatio": ("Utils API", "平台信息获取", ""),
    "GetTPipePtr": ("Utils API", "平台信息获取", ""),
    "GetUserWorkspace": ("Utils API", "平台信息获取", ""),
    "SetSysWorkSpace": ("Utils API", "平台信息获取", ""),

    # ===== Utils API - 调测接口 =====
    "CheckLocalMemoryIA": ("Utils API", "调测接口", ""),
    "DumpAccChkPoint": ("Utils API", "调测接口", ""),
    "PrintTimeStamp": ("Utils API", "调测接口", ""),
    "TRACE_START": ("Utils API", "调测接口", ""),
    "TRACE_STOP": ("Utils API", "调测接口", ""),

    # ===== 补充缺失的API (推断) =====
    # SIMT 数学函数
    "Acosh": ("SIMT API", "数学函数", ""),
    "Asinh": ("SIMT API", "数学函数", ""),
    "Atanh": ("SIMT API", "数学函数", ""),
    "Power": ("SIMT API", "数学函数", ""),
    "SinCos": ("SIMT API", "数学函数", ""),
    "Truncate": ("SIMT API", "数学函数", ""),
    # SIMT 比较函数
    "IsFinite": ("SIMT API", "比较函数", ""),
    "IsInf": ("SIMT API", "比较函数", ""),
    "IsNan": ("SIMT API", "比较函数", ""),
    # 类型转换
    "Cast（float转bfloat16_t）": ("SIMT API", "类型转换", ""),
    "Cast（float转half、int32_t）": ("SIMT API", "类型转换", ""),
    "Cast（多类型转float）": ("SIMT API", "类型转换", ""),
    # C++ 标准库
    "remove_reference": ("Utils API", "C++标准库", ""),
    # 基础API
    "Arange": ("基础API", "Memory矢量计算", ""),
    "Mull": ("基础API", "Memory矢量计算", ""),
    "CubeResGroupHandle": ("基础API", "其他", ""),
}


def _get_nav_path(name: str) -> tuple[str, ...]:
    """
    根据API名称获取官方导航路径

    Args:
        name: API名称

    Returns:
        导航路径元组，如 ("SIMT API", "精度转换", "rintf")
    """
    if name in API_NAV_MAPPING:
        return API_NAV_MAPPING[name]
    return ()


def _infer_category(name: str, url: str = "") -> str:
    """从名称推断分类 (兼容旧接口)"""
    nav_path = _get_nav_path(name)
    if nav_path:
        return nav_path[0]  # 返回顶级分类
    return "util"


class BrowserClient:
    """
    Playwright 浏览器采集客户端

    使用无头浏览器渲染页面，提取动态加载的 API 链接
    """

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 60000,
        wait_selector: str = "a[href*='ascendc']",
    ):
        """
        初始化浏览器客户端

        Args:
            headless: 是否使用无头模式
            timeout: 页面加载超时 (毫秒)
            wait_selector: 等待元素出现的选择器
        """
        self.headless = headless
        self.timeout = timeout
        self.wait_selector = wait_selector
        self._browser: Optional[Browser] = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def connect(self):
        """连接浏览器"""
        if self._browser is None:
            p = await async_playwright().__aenter__()
            self._browser = await p.chromium.launch(headless=self.headless)
        return self

    async def close(self):
        """关闭浏览器"""
        if self._browser:
            await self._browser.close()
            self._browser = None

    async def discover_api_links(
        self,
        cached_ids: Optional[Set[str]] = None,
    ) -> BrowserCollectionResult:
        """
        发现 API 链接

        使用 Playwright 加载页面，等待 JS 渲染完成后提取所有 API 链接

        Args:
            cached_ids: 已缓存的 API ID 集合

        Returns:
            BrowserCollectionResult: 发现的链接结果
        """
        import hashlib
        from bs4 import BeautifulSoup

        start_time = datetime.now()
        cached_ids = cached_ids or set()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()

            logger.info(f"Loading API list page: {LIST_PAGE_URL}")
            await page.goto(LIST_PAGE_URL, timeout=self.timeout)

            # 等待页面加载完成
            try:
                await page.wait_for_load_state("networkidle", timeout=self.timeout)
                # 额外等待确保 JS 执行完成
                await asyncio.sleep(2)
            except PlaywrightTimeout:
                logger.warning("Page load timeout, continuing anyway")

            # 获取页面内容
            content = await page.content()
            await browser.close()

        # 解析 HTML
        soup = BeautifulSoup(content, "html.parser")

        # 提取所有 API 链接
        links: List[BrowserAPILink] = []
        found_ids: Set[str] = set()

        # 查找所有包含 ascendc_api 的链接
        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "")
            name = a_tag.get_text(strip=True)

            # 只选择包含 atlasascendc_api_07_XXXX.html 的链接
            if "atlasascendc_api_07_" not in href:
                continue
            if ".xml" in href:  # 排除 XML 链接
                continue
            if not name:  # 需要名称
                continue

            # 构建完整 URL
            full_url = urljoin(LIST_PAGE_URL, href)

            # 生成 ID
            content_hash = f"{full_url}:{name}".encode("utf-8")
            api_id = hashlib.sha256(content_hash).hexdigest()[:16]

            # 避免重复
            if api_id in found_ids:
                continue
            found_ids.add(api_id)

            # 获取导航路径
            nav_path = _get_nav_path(name)
            category = nav_path[0] if nav_path else "util"

            links.append(BrowserAPILink(
                api_id=api_id,
                name=name,
                url=full_url,
                category=category,
                subcategory=nav_path[1] if len(nav_path) > 1 else "",
                nav_path=nav_path,
            ))

        elapsed = (datetime.now() - start_time).total_seconds()

        # 分离新增和已缓存的链接
        new_links = [l for l in links if l.api_id not in cached_ids]

        logger.info(
            f"Discovered {len(links)} API links via browser rendering "
            f"({len(new_links)} new, {len(links) - len(new_links)} cached) "
            f"in {elapsed:.1f}s"
        )

        return BrowserCollectionResult(
            total_discovered=len(links),
            new_links=new_links,
            elapsed_seconds=elapsed,
        )


async def discover_with_browser(
    cached_api_ids: Optional[Set[str]] = None,
    headless: bool = True,
) -> BrowserCollectionResult:
    """
    便捷函数：使用浏览器发现 API 链接

    Args:
        cached_api_ids: 已缓存的 API ID 集合
        headless: 是否使用无头模式

    Returns:
        BrowserCollectionResult: 发现的链接结果
    """
    async with BrowserClient(headless=headless) as client:
        return await client.discover_api_links(cached_api_ids)


if __name__ == "__main__":
    # 测试采集
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    async def main():
        print("=" * 50)
        print("  Playwright API 链接发现测试")
        print("=" * 50)

        result = await discover_with_browser()

        print(f"\n发现结果:")
        print(f"  - 总数: {result.total_discovered}")
        print(f"  - 新增: {len(result.new_links)}")
        print(f"  - 耗时: {result.elapsed_seconds:.1f}s")

        print(f"\n前 10 个 API:")
        for link in result.new_links[:10]:
            print(f"  [{link.category}] {link.name}")

        return 0

    sys.exit(asyncio.run(main()))
