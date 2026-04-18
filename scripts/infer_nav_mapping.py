#!/usr/bin/env python3
# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
基于命名模式推断API导航路径

用于为342个缺失nav_path的API推断官方导航路径
"""

import chromadb
from asc_ops.storage.collections import CollectionType
from asc_ops.config import get_config


# 基于CANN官方文档结构和API命名模式的分类推断
def infer_nav_path(name: str) -> tuple:
    """
    根据API名称推断导航路径

    Returns:
        (category, subcategory, api_name) 或 None
    """

    # ===== SIMT 数学函数变体 =====
    if name in ['Cos', 'Sin', 'Tan', 'Floor', 'Ceil', 'Round', 'Trunc', 'Frac',
                'Acos', 'Asin', 'Atan', 'Cosh', 'Sinh', 'Tanh',
                'Exp', 'ExpSub', 'Log', 'Log10', 'Lgamma', 'Digamma',
                'Sqrt', 'Rsqrt', 'Pow', 'Norm', 'Norm3df', 'Norm4df',
                'Abs', 'AbsSub', 'Sign', 'Fma', 'Fmod', 'Hypot',
                'Erf', 'Erfc']:
        return ("SIMT API", "数学函数", "")

    # ===== SIMT 精度转换/舍入 =====
    if name in ['Rint', 'nearbyIntf', 'fdivdef']:
        return ("SIMT API", "精度转换", "")

    # ===== SIMT 比较/逻辑函数 =====
    if name in ['Compare', 'Compares', 'Compare（结果存入寄存器）', 'Compare（结果存放入寄存器）',
                'And', 'Or', 'Not', 'Xor', 'BitwiseAnd', 'BitwiseOr', 'BitwiseNot', 'BitwiseXor',
                'LogicalAnd', 'LogicalOr', 'LogicalNot', 'LogicalXor', 'LogicalAnds', 'LogicalOrs',
                'Select', 'Select']:
        return ("SIMT API", "比较函数", "")

    # ===== SIMT Atomic函数 =====
    if name in ['AtomicCas', 'AtomicExch', 'AtomicMax', 'AtomicMin',
                'SetAtomicAdd', 'SetAtomicMax', 'SetAtomicMin', 'SetAtomicType',
                'GetStoreAtomicConfig', 'SetStoreAtomicConfig']:
        return ("SIMT API", "Atomic函数", "")

    # ===== SIMT 向量/内存同步 =====
    if name in ['SetCmpMask', 'GetCmpMask', 'SetVectorMask', 'SetMaskCount', 'SetMaskNorm',
                'ResetMask', 'GetCtrlSpr', 'SetCtrlSpr', 'ResetCtrlSpr',
                'GetReduceRepeatMaxMinSpr', 'GetReduceRepeatSumSpr', 'GetSFFValue']:
        return ("SIMT API", "同步函数", "")

    # ===== 基础API - Memory数据搬运 =====
    if name in ['Fill', 'LoadData', 'Load3D', 'Load3Dv1/Load3Dv2', 'LoadImageToLocal',
                'DumpTensor', 'Duplicate', 'Broadcast', 'Concat', 'Extract',
                'Transpose', 'TransData', 'TransDataTo5HD', 'DataCopyPad',
                'Interleave', 'DeInterleave', 'VectorPadding',
                'LoadUnZipIndex', 'LoadDataUnzip', 'LoadDataWithSparse', 'LoadDataWithTranspose',
                'Pad', 'UnPad']:
        return ("基础API", "Memory数据搬运", "")

    # ===== 基础API - Memory矢量计算 =====
    if name in ['Gather', 'Scatter', 'GatherMask', 'Gatherb', 'Where',
                'ReduceAll', 'ReduceAny', 'ReduceMean', 'ReduceProd', 'ReduceXorSum',
                'Sum', 'Mean', 'PairReduceSum', 'RepeatReduceSum', 'PairReduceSum',
                'BlockReduceMax', 'BlockReduceMin', 'BlockReduceSum',
                'WholeReduceMax', 'WholeReduceMin', 'WholeReduceSum',
                'ClampMax', 'ClampMin', 'CumSum', 'CountLeadingZero',
                'CountBitsCntSameAsSignBit', 'GetBitCount', 'Brcb']:
        return ("基础API", "Memory矢量计算", "")

    # ===== 基础API - 矩阵计算 =====
    if name in ['Conv2D', 'Conv3D', 'Conv3DBackpropFilter', 'Conv3DBackpropInput',
                'Gemm', 'Matmul', 'Mmad', 'MmadWithSparse', 'BilinearInterpolation']:
        return ("基础API", "矩阵计算", "")

    # ===== 基础API - 归一化 =====
    if name in ['LayerNorm', 'LayerNormGrad', 'LayerNormGradBeta', 'GroupNorm', 'BatchNorm',
                'Normalize', 'WelfordUpdate', 'WelfordFinalize', 'DeepNorm', 'RmsNorm']:
        return ("基础API", "归一化", "")

    # ===== 基础API - 激活函数 =====
    if name in ['Relu', 'Prelu', 'Gelu', 'FasterGelu', 'FasterGeluV2', 'Silu', 'Swish',
                'Sigmoid', 'SoftMax', 'LogSoftMax', 'SimpleSoftMax',
                'SoftmaxFlash', 'SoftmaxFlashV2', 'SoftmaxFlashV3',
                'SoftmaxGrad', 'SoftmaxGradFront', 'AdjustSoftMaxRes',
                'GeGLU', 'SwiGLU', 'ReGlu', 'SubRelu', 'SubReluCast', 'MulAddDst', 'MulAddRelu', 'MulCast', 'MulsCast', 'FusedMulAdd', 'MulAdd']:
        return ("基础API", "激活函数", "")

    # ===== 基础API - 排序 =====
    if name in ['Sort', 'Sort32', 'TopK', 'MrgSort', 'MrgSort4', 'RpSort16',
                'CreateVecIndex', 'GetMrgSortResult']:
        return ("基础API", "排序", "")

    # ===== 基础API - 量化 =====
    if name in ['Quantize', 'Dequantize', 'AscendQuant', 'AscendAntiQuant', 'AntiQuantize',
                'Quant', 'Dequantize', 'AscendDequant']:
        return ("基础API", "量化", "")

    # ===== 基础API - 随机函数 =====
    if name in ['PhiloxRandom']:
        return ("基础API", "随机函数", "")

    # ===== 基础API - 同步/通信 =====
    if name in ['SyncAll', 'Async', 'PipeBarrier', 'NotifyNextBlock', 'WaitPreBlock', 'WaitPreTaskEnd',
                'GroupBarrier', 'CrossCoreSetFlag', 'CrossCoreWaitFlag', 'DataSyncBarrier',
                'DisableDmaAtomic', 'Mutex', 'AllocMutexID', 'ReleaseMutexID', 'AllocMutexID/ReleaseMutexID',
                'IBSet', 'IBWait']:
        return ("基础API", "同步", "")

    # ===== 基础API - 初始化/配置 =====
    if name in ['InitDetermineComputeWorkspace', 'InitSocState', 'InitSpmBuffer', 'ReadSpmBuffer', 'WriteSpmBuffer',
                'GmAlloc', 'GmFree', 'TBuf', 'TBufPool', 'TPipe', 'TQue', 'TQueBind', 'TQueSync',
                'ContextBuilder', 'OpAICoreConfig', 'OpAICoreDef', 'OpAttrDef', 'OpDef',
                'OpMC2Def', 'OpParamDef', 'OpTilingRegistry',
                'DEVICE_IMPL_OP_OPTILING', 'ICPU_RUN_KF', 'ICPU_SET_TILING_KEY',
                'KERNEL_TASK_TYPE', 'KERNEL_TASK_TYPE_DEFAULT', 'TILING_KEY_IS',
                'REGISTER_NONE_TILING', 'REGISTER_TILING_DEFAULT', 'REGISTER_TILING_FOR_TILINGKEY',
                'GET_TILING_DATA', 'GET_TILING_DATA_WITH_STRUCT', 'GET_TILING_DATA_MEMBER',
                'GET_TILING_DATA_PTR_WITH_STRUCT', 'GET_TPL_TILING_KEY',
                'SetKernelMode']:
        return ("基础API", "初始化与配置", "")

    # ===== 基础API - 数据同步/缓存 =====
    if name in ['DataCacheCleanAndInvalid', 'DataCachePreload', 'ReadGmByPassDCache', 'WriteGmByPassDCache',
                'ICachePreLoad', 'GetICachePreloadStatus',
                'SetFixPipeAddr', 'SetFixPipeClipRelu', 'SetFixPipeConfig',
                'SetFixpipeNz2ndFlag', 'SetFixpipePreQuantFlag', 'Fixpipe',
                'SetFmatrix', 'SetMMColumnMajor', 'SetMMRowMajor',
                'SetHF32Mode', 'SetHF32TransMode',
                'SetLoadDataBoundary', 'SetLoadDataPaddingValue', 'SetLoadDataRepeat',
                'GetUBSizeInBytes', 'GetRuntimeUBSize', 'GetDataBlockSizeInBytes']:
        return ("基础API", "数据同步与缓存", "")

    # ===== 基础API - 通信/HCCL =====
    if name in ['HCCL通信类', 'MetricsProfStart', 'MetricsProfStop']:
        return ("基础API", "HCCL通信", "")

    # ===== Utils API - Tiling =====
    if name in ['TilingData结构定义', 'TilingData结构注册', 'SetTilingData', 'TilingData']:
        return ("Utils API", "Tiling", "")

    # ===== Utils API - RTC =====
    if name.startswith('aclrtc'):
        return ("Utils API", "RTC", "")

    # ===== Utils API - C++标准库 =====
    if name in ['is_array', 'is_const', 'is_pointer', 'is_reference', 'is_void',
                'is_integral', 'is_floating_point', 'is_convertible', 'is_base_of', 'is_same',
                'add_const', 'remove_const', 'add_pointer', 'remove_pointer',
                'add_volatile', 'remove_volatile', 'add_cv', 'remove_cv',
                'add_lvalue_reference', 'add_rvalue_reference', 'add_reference',
                'conditional', 'enable_if', 'integer_sequence', 'integral_constant',
                'ascendc_assert', 'clock', 'fdivdef', '__trap', 'Trap']:
        return ("Utils API", "C++标准库", "")

    # ===== Utils API - 平台信息 =====
    if name in ['GetArchVersion', 'GetBlockNum', 'GetBlockIdx', 'GetSubBlockNum', 'GetSubBlockIdx',
                'GetCoreId', 'GetSystemCycle', 'GetProgramCounter', 'GetTPipePtr',
                'GetSysWorkSpacePtr', 'GetUserWorkspace', 'SetSysWorkSpace',
                'GetTaskRatio', 'GetArchVer']:
        return ("Utils API", "平台信息获取", "")

    # ===== 调测接口 =====
    if name in ['PrintTimeStamp', 'TRACE_START', 'TRACE_STOP', 'DumpAccChkPoint',
                'CheckLocalMemoryIA']:
        return ("Utils API", "调测接口", "")

    # ===== 原型注册/模板 =====
    if name in ['原型注册接口（OP_ADD）', '模板参数定义', 'ASCENDC_TPL_SEL_PARAM',
                'SetAippFunctions', 'SetDeqScale', 'SetFlag/WaitFlag', 'SetNextTaskStart']:
        return ("Utils API", "原型注册与管理", "")

    # ===== 其他/杂项 =====
    if name in ['ASC_CPU_LOG', 'KfcWorkspace', 'NumericLimits', 'DropOut',
                'ProposalConcat', 'ProposalExtract', 'AscendAntiQuant', 'AscendDequant']:
        return ("基础API", "其他", "")

    return None


def main():
    config = get_config()
    client = chromadb.PersistentClient(path=str(config.chroma.db_path))
    collection = client.get_collection(CollectionType.ASCEND_APIS.value)

    results = collection.get(include=['metadatas'])

    # 获取无nav_path的API
    missing = []
    for meta in results.get('metadatas', []):
        if not meta:
            continue
        nav = meta.get('nav_path', '')
        if not nav or nav == '[]' or nav == 'null' or nav == '':
            missing.append(meta.get('name', ''))

    print(f"缺失nav_path的API数量: {len(missing)}")
    print()

    # 分类统计
    categorized = {}
    uncategorized = []

    for name in sorted(missing):
        nav = infer_nav_path(name)
        if nav:
            key = f"{nav[0]}/{nav[1]}"
            if key not in categorized:
                categorized[key] = []
            categorized[key].append(name)
        else:
            uncategorized.append(name)

    print("=" * 60)
    print("  分类结果")
    print("=" * 60)

    for key, names in sorted(categorized.items()):
        print(f"\n{key}: {len(names)}个")
        for n in names[:10]:
            print(f"  - {n}")
        if len(names) > 10:
            print(f"  ... 还有{len(names) - 10}个")

    print(f"\n未分类: {len(uncategorized)}个")
    for n in uncategorized:
        print(f"  - {n}")

    # 生成映射代码
    print("\n" + "=" * 60)
    print("  生成的映射代码")
    print("=" * 60)

    code_lines = []
    for key, names in sorted(categorized.items()):
        cat, subcat = key.split("/")
        for name in sorted(names):
            code_lines.append(f'    "{name}": ("{cat}", "{subcat}", ""),')

    print("\n添加以下代码到API_NAV_MAPPING:")
    print("# ===== 推断的导航路径 =====")
    for line in code_lines[:50]:
        print(line)
    if len(code_lines) > 50:
        print(f"  ... 还有{len(code_lines) - 50}行")


if __name__ == "__main__":
    main()
