# CUDA API Collection List

**Last Updated:** 2026-04-22
**Total APIs Defined:** 125
**Collected:** 125
**Coverage:** 100%

> **数据来源**: NVIDIA CUDA Runtime API 官方文档
> - Memory Management: https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html
> - Device Management: https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__DEVICE.html
> - Stream Management: https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__STREAM.html
> - Event Management: https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__EVENT.html
> - Warp-level Intrinsics: https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html

---

## Summary

| Category | Count | Status |
|----------|-------|--------|
| Warp Shuffle | 4 | ✅ Complete |
| Warp Vote | 5 | ✅ Complete |
| Warp Reduce | 7 | ✅ Complete |
| Warp Match | 2 | ✅ Complete |
| Thread Sync | 4 | ✅ Complete |
| Memory Fence | 3 | ✅ Complete |
| Memory Management | 37 | ✅ Complete |
| Stream Management | 23 | ✅ Complete |
| Event Management | 8 | ✅ Complete |
| Device Management | 29 | ✅ Complete |
| Execution Control | 4 | ✅ Complete |
| **TOTAL** | **125** | **100%** |

---

## 1. Warp-Level Intrinsics (SIMD-like Operations)

### 1.1 Warp Shuffle Functions
**Source:** [CUDA Programming Guide - Warp Shuffle Functions](https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#warp-shuffle-functions)

| API Name | Signature | Status |
|----------|-----------|--------|
| `__shfl_sync` | `T __shfl_sync(unsigned mask, T var, int delta)` | ✅ Collected |
| `__shfl_up_sync` | `T __shfl_up_sync(unsigned mask, T var, int delta)` | ✅ Collected |
| `__shfl_down_sync` | `T __shfl_down_sync(unsigned mask, T var, int delta)` | ✅ Collected |
| `__shfl_xor_sync` | `T __shfl_xor_sync(unsigned mask, T var, int laneMask)` | ✅ Collected |

### 1.2 Warp Vote Functions
**Source:** [CUDA Programming Guide - Warp Vote Functions](https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#warp-vote-functions)

| API Name | Signature | Status |
|----------|-----------|--------|
| `__all_sync` | `int __all_sync(unsigned mask, int predicate)` | ✅ Collected |
| `__any_sync` | `int __any_sync(unsigned mask, int predicate)` | ✅ Collected |
| `__uni_sync` | `int __uni_sync(unsigned mask)` | ✅ Collected |
| `__all` | `int __all(int predicate)` | ✅ Collected (deprecated) |
| `__any` | `int __any(int predicate)` | ✅ Collected (deprecated) |

### 1.3 Warp Reduce Functions
**Source:** [CUDA Programming Guide - Warp Reduce Functions](https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#warp-reduce-functions)

| API Name | Signature | Status |
|----------|-----------|--------|
| `__reduce_add_sync` | `T __reduce_add_sync(unsigned mask, T var)` | ✅ Collected |
| `__reduce_mul_sync` | `T __reduce_mul_sync(unsigned mask, T var)` | ✅ Collected |
| `__reduce_min_sync` | `T __reduce_min_sync(unsigned mask, T var)` | ✅ Collected |
| `__reduce_max_sync` | `T __reduce_max_sync(unsigned mask, T var)` | ✅ Collected |
| `__reduce_and_sync` | `T __reduce_and_sync(unsigned mask, T var)` | ✅ Collected |
| `__reduce_or_sync` | `T __reduce_or_sync(unsigned mask, T var)` | ✅ Collected |
| `__reduce_xor_sync` | `T __reduce_xor_sync(unsigned mask, T var)` | ✅ Collected |

### 1.4 Warp Match Functions
**Source:** [CUDA Programming Guide - Warp Match Functions](https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#warp-match-functions)

| API Name | Signature | Status |
|----------|-----------|--------|
| `__match_any_sync` | `unsigned __match_any_sync(unsigned mask, T var)` | ✅ Collected |
| `__match_all_sync` | `unsigned __match_all_sync(unsigned mask, T var)` | ✅ Collected |

---

## 2. Thread Synchronization Functions

**Source:** [CUDA Programming Guide - Synchronization Functions](https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#synchronization-functions)

| API Name | Signature | Status |
|----------|-----------|--------|
| `__syncthreads` | `void __syncthreads()` | ✅ Collected |
| `__syncthreads_count` | `int __syncthreads_count(int predicate)` | ✅ Collected |
| `__syncthreads_and` | `int __syncthreads_and(int predicate)` | ✅ Collected |
| `__syncthreads_or` | `int __syncthreads_or(int predicate)` | ✅ Collected |

---

## 3. Memory Fence Functions

**Source:** [CUDA Programming Guide - Memory Fence Functions](https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#memory-fence-functions)

| API Name | Signature | Status |
|----------|-----------|--------|
| `__threadfence` | `void __threadfence()` | ✅ Collected |
| `__threadfence_block` | `void __threadfence_block()` | ✅ Collected |
| `__threadfence_system` | `void __threadfence_system()` | ✅ Collected |

---

## 4. CUDA Runtime Memory APIs

**Source:** [CUDA Runtime API - Memory Management](https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html)

### 4.1 Memory Allocation (9)

| API Name | Status |
|----------|--------|
| `cudaMalloc` | ✅ |
| `cudaMallocHost` | ✅ |
| `cudaMallocManaged` | ✅ |
| `cudaMallocPitch` | ✅ |
| `cudaMallocArray` | ✅ |
| `cudaMalloc3D` | ✅ |
| `cudaMalloc3DArray` | ✅ |
| `cudaMallocMipmappedArray` | ✅ |

### 4.2 Memory Deallocation (4)

| API Name | Status |
|----------|--------|
| `cudaFree` | ✅ |
| `cudaFreeHost` | ✅ |
| `cudaFreeArray` | ✅ |
| `cudaFreeMipmappedArray` | ✅ |

### 4.3 Host Memory (3)

| API Name | Status |
|----------|--------|
| `cudaHostAlloc` | ✅ |
| `cudaHostRegister` | ✅ |
| `cudaHostUnregister` | ✅ |

### 4.4 Memory Copy (12)

| API Name | Status |
|----------|--------|
| `cudaMemcpy` | ✅ |
| `cudaMemcpyAsync` | ✅ |
| `cudaMemcpy2D` | ✅ |
| `cudaMemcpy2DAsync` | ✅ |
| `cudaMemcpy3D` | ✅ |
| `cudaMemcpy3DAsync` | ✅ |
| `cudaMemcpyPeer` | ✅ |
| `cudaMemcpyPeerAsync` | ✅ |
| `cudaMemcpyToSymbol` | ✅ |
| `cudaMemcpyFromSymbol` | ✅ |
| `cudaMemcpyToSymbolAsync` | ✅ |
| `cudaMemcpyFromSymbolAsync` | ✅ |

### 4.5 Memory Set (6)

| API Name | Status |
|----------|--------|
| `cudaMemset` | ✅ |
| `cudaMemsetAsync` | ✅ |
| `cudaMemset2D` | ✅ |
| `cudaMemset2DAsync` | ✅ |
| `cudaMemset3D` | ✅ |
| `cudaMemset3DAsync` | ✅ |

### 4.6 Memory Query/Management (3)

| API Name | Status |
|----------|--------|
| `cudaMemGetInfo` | ✅ |
| `cudaMemAdvise` | ✅ |
| `cudaMemPrefetchAsync` | ✅ |

---

## 5. CUDA Runtime Stream APIs

**Source:** [CUDA Runtime API - Stream Management](https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__STREAM.html)

| API Name | Status |
|----------|--------|
| `cudaStreamCreate` | ✅ |
| `cudaStreamCreateWithFlags` | ✅ |
| `cudaStreamCreateWithPriority` | ✅ |
| `cudaStreamDestroy` | ✅ |
| `cudaStreamSynchronize` | ✅ |
| `cudaStreamWaitEvent` | ✅ |
| `cudaStreamAddCallback` | ✅ |
| `cudaStreamQuery` | ✅ |
| `cudaStreamBeginCapture` | ✅ |
| `cudaStreamEndCapture` | ✅ |
| `cudaStreamIsCapturing` | ✅ |
| `cudaStreamAttachMemAsync` | ✅ |
| `cudaStreamGetCaptureInfo` | ✅ |
| `cudaStreamGetDevice` | ✅ |
| `cudaStreamGetFlags` | ✅ |
| `cudaStreamGetId` | ✅ |
| `cudaStreamGetPriority` | ✅ |
| `cudaStreamSetAttribute` | ✅ |
| `cudaStreamGetAttribute` | ✅ |
| `cudaStreamCopyAttributes` | ✅ |
| `cudaStreamUpdateCaptureDependencies` | ✅ |
| `cudaThreadExchangeStreamCaptureMode` | ✅ |
| `cudaCtxResetPersistingL2Cache` | ✅ |

---

## 6. CUDA Runtime Event APIs

**Source:** [CUDA Runtime API - Event Management](https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__EVENT.html)

| API Name | Status |
|----------|--------|
| `cudaEventCreate` | ✅ |
| `cudaEventCreateWithFlags` | ✅ |
| `cudaEventDestroy` | ✅ |
| `cudaEventRecord` | ✅ |
| `cudaEventRecordWithFlags` | ✅ |
| `cudaEventQuery` | ✅ |
| `cudaEventSynchronize` | ✅ |
| `cudaEventElapsedTime` | ✅ |

---

## 7. CUDA Runtime Device APIs

**Source:** [CUDA Runtime API - Device Management](https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__DEVICE.html)

### 7.1 Device Selection and Initialization (9)

| API Name | Status |
|----------|--------|
| `cudaChooseDevice` | ✅ |
| `cudaGetDevice` | ✅ |
| `cudaSetDevice` | ✅ |
| `cudaGetDeviceCount` | ✅ |
| `cudaGetDeviceFlags` | ✅ |
| `cudaGetDeviceProperties` | ✅ |
| `cudaInitDevice` | ✅ |
| `cudaSetDeviceFlags` | ✅ |
| `cudaSetValidDevices` | ✅ |

### 7.2 Device Attributes (4)

| API Name | Status |
|----------|--------|
| `cudaDeviceGetAttribute` | ✅ |
| `cudaDeviceGetByPCIBusId` | ✅ |
| `cudaDeviceGetPCIBusId` | ✅ |
| `cudaDeviceGetStreamPriorityRange` | ✅ |

### 7.3 Cache and Memory Configuration (5)

| API Name | Status |
|----------|--------|
| `cudaDeviceGetCacheConfig` | ✅ |
| `cudaDeviceSetCacheConfig` | ✅ |
| `cudaDeviceGetDefaultMemPool` | ✅ |
| `cudaDeviceGetMemPool` | ✅ |
| `cudaDeviceSetMemPool` | ✅ |

### 7.4 Limits and Synchronization (3)

| API Name | Status |
|----------|--------|
| `cudaDeviceGetLimit` | ✅ |
| `cudaDeviceSetLimit` | ✅ |
| `cudaDeviceSynchronize` | ✅ |

### 7.5 IPC (5)

| API Name | Status |
|----------|--------|
| `cudaIpcCloseMemHandle` | ✅ |
| `cudaIpcGetEventHandle` | ✅ |
| `cudaIpcGetMemHandle` | ✅ |
| `cudaIpcOpenEventHandle` | ✅ |
| `cudaIpcOpenMemHandle` | ✅ |

### 7.6 Peer-to-Peer and Other (3)

| API Name | Status |
|----------|--------|
| `cudaDeviceGetP2PAttribute` | ✅ |
| `cudaDeviceFlushGPUDirectRDMAWrites` | ✅ |
| `cudaDeviceReset` | ✅ |

---

## 8. Execution Control APIs

**Source:** [CUDA Programming Guide - Execution Configuration](https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#execution-configuration)

| API Name | Status |
|----------|--------|
| `cudaConfigureCall` | ✅ |
| `cudaLaunchKernel` | ✅ |
| `cudaLaunchCooperativeKernel` | ✅ |
| `cudaLaunchCooperativeKernelMultiDevice` | ✅ |

---

## Data Sources

- **CUDA Runtime API**: https://docs.nvidia.com/cuda/cuda-runtime-api/index.html
- **CUDA Programming Guide**: https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html
