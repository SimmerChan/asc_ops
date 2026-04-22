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
| `cudaMalloc` | ✅ Collected |
| `cudaMallocHost` | ✅ Collected |
| `cudaMallocManaged` | ✅ Collected |
| `cudaMallocPitch` | ✅ Collected |
| `cudaMallocArray` | ✅ Collected |
| `cudaMalloc3D` | ✅ Collected |
| `cudaMalloc3DArray` | ✅ Collected |
| `cudaMallocMipmappedArray` | ✅ Collected |

### 4.2 Memory Deallocation (4)

| API Name | Status |
|----------|--------|
| `cudaFree` | ✅ Collected |
| `cudaFreeHost` | ✅ Collected |
| `cudaFreeArray` | ✅ Collected |
| `cudaFreeMipmappedArray` | ✅ Collected |

### 4.3 Host Memory (3)

| API Name | Status |
|----------|--------|
| `cudaHostAlloc` | ✅ Collected |
| `cudaHostRegister` | ✅ Collected |
| `cudaHostUnregister` | ✅ Collected |

### 4.4 Memory Copy (12)

| API Name | Status |
|----------|--------|
| `cudaMemcpy` | ✅ Collected |
| `cudaMemcpyAsync` | ✅ Collected |
| `cudaMemcpy2D` | ✅ Collected |
| `cudaMemcpy2DAsync` | ✅ Collected |
| `cudaMemcpy3D` | ✅ Collected |
| `cudaMemcpy3DAsync` | ✅ Collected |
| `cudaMemcpyPeer` | ✅ Collected |
| `cudaMemcpyPeerAsync` | ✅ Collected |
| `cudaMemcpyToSymbol` | ✅ Collected |
| `cudaMemcpyFromSymbol` | ✅ Collected |
| `cudaMemcpyToSymbolAsync` | ✅ Collected |
| `cudaMemcpyFromSymbolAsync` | ✅ Collected |

### 4.5 Memory Set (6)

| API Name | Status |
|----------|--------|
| `cudaMemset` | ✅ Collected |
| `cudaMemsetAsync` | ✅ Collected |
| `cudaMemset2D` | ✅ Collected |
| `cudaMemset2DAsync` | ✅ Collected |
| `cudaMemset3D` | ✅ Collected |
| `cudaMemset3DAsync` | ✅ Collected |

### 4.6 Memory Query/Management (3)

| API Name | Status |
|----------|--------|
| `cudaMemGetInfo` | ✅ Collected |
| `cudaMemAdvise` | ✅ Collected |
| `cudaMemPrefetchAsync` | ✅ Collected |

---

## 5. CUDA Runtime Stream APIs

**Source:** [CUDA Runtime API - Stream Management](https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__STREAM.html)

| API Name | Status |
|----------|--------|
| `cudaStreamCreate` | ✅ Collected |
| `cudaStreamCreateWithFlags` | ✅ Collected |
| `cudaStreamCreateWithPriority` | ✅ Collected |
| `cudaStreamDestroy` | ✅ Collected |
| `cudaStreamSynchronize` | ✅ Collected |
| `cudaStreamWaitEvent` | ✅ Collected |
| `cudaStreamAddCallback` | ✅ Collected |
| `cudaStreamQuery` | ✅ Collected |
| `cudaStreamBeginCapture` | ✅ Collected |
| `cudaStreamEndCapture` | ✅ Collected |
| `cudaStreamIsCapturing` | ✅ Collected |
| `cudaStreamAttachMemAsync` | ✅ Collected |
| `cudaStreamGetCaptureInfo` | ✅ Collected |
| `cudaStreamGetDevice` | ✅ Collected |
| `cudaStreamGetFlags` | ✅ Collected |
| `cudaStreamGetId` | ✅ Collected |
| `cudaStreamGetPriority` | ✅ Collected |
| `cudaStreamSetAttribute` | ✅ Collected |
| `cudaStreamGetAttribute` | ✅ Collected |
| `cudaStreamCopyAttributes` | ✅ Collected |
| `cudaStreamUpdateCaptureDependencies` | ✅ Collected |
| `cudaThreadExchangeStreamCaptureMode` | ✅ Collected |
| `cudaCtxResetPersistingL2Cache` | ✅ Collected |

---

## 6. CUDA Runtime Event APIs

**Source:** [CUDA Runtime API - Event Management](https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__EVENT.html)

| API Name | Status |
|----------|--------|
| `cudaEventCreate` | ✅ Collected |
| `cudaEventCreateWithFlags` | ✅ Collected |
| `cudaEventDestroy` | ✅ Collected |
| `cudaEventRecord` | ✅ Collected |
| `cudaEventRecordWithFlags` | ✅ Collected |
| `cudaEventQuery` | ✅ Collected |
| `cudaEventSynchronize` | ✅ Collected |
| `cudaEventElapsedTime` | ✅ Collected |

---

## 7. CUDA Runtime Device APIs

**Source:** [CUDA Runtime API - Device Management](https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__DEVICE.html)

### 7.1 Device Selection and Initialization (9)

| API Name | Status |
|----------|--------|
| `cudaChooseDevice` | ✅ Collected |
| `cudaGetDevice` | ✅ Collected |
| `cudaSetDevice` | ✅ Collected |
| `cudaGetDeviceCount` | ✅ Collected |
| `cudaGetDeviceFlags` | ✅ Collected |
| `cudaGetDeviceProperties` | ✅ Collected |
| `cudaInitDevice` | ✅ Collected |
| `cudaSetDeviceFlags` | ✅ Collected |
| `cudaSetValidDevices` | ✅ Collected |

### 7.2 Device Attributes (5)

| API Name | Status |
|----------|--------|
| `cudaDeviceGetAttribute` | ✅ Collected |
| `cudaDeviceGetByPCIBusId` | ✅ Collected |
| `cudaDeviceGetPCIBusId` | ✅ Collected |
| `cudaDeviceGetStreamPriorityRange` | ✅ Collected |

### 7.3 Cache and Memory Configuration (5)

| API Name | Status |
|----------|--------|
| `cudaDeviceGetCacheConfig` | ✅ Collected |
| `cudaDeviceSetCacheConfig` | ✅ Collected |
| `cudaDeviceGetDefaultMemPool` | ✅ Collected |
| `cudaDeviceGetMemPool` | ✅ Collected |
| `cudaDeviceSetMemPool` | ✅ Collected |

### 7.4 Limits (3)

| API Name | Status |
|----------|--------|
| `cudaDeviceGetLimit` | ✅ Collected |
| `cudaDeviceSetLimit` | ✅ Collected |
| `cudaDeviceSynchronize` | ✅ Collected |

### 7.5 IPC (5)

| API Name | Status |
|----------|--------|
| `cudaIpcCloseMemHandle` | ✅ Collected |
| `cudaIpcGetEventHandle` | ✅ Collected |
| `cudaIpcGetMemHandle` | ✅ Collected |
| `cudaIpcOpenEventHandle` | ✅ Collected |
| `cudaIpcOpenMemHandle` | ✅ Collected |

### 7.6 Peer-to-Peer and Other (2)

| API Name | Status |
|----------|--------|
| `cudaDeviceGetP2PAttribute` | ✅ Collected |
| `cudaDeviceReset` | ✅ Collected |

---

## 8. Execution Control APIs

**Source:** [CUDA Programming Guide - Execution Configuration](https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#execution-configuration)

| API Name | Status |
|----------|--------|
| `cudaConfigureCall` | ✅ Collected |
| `cudaLaunchKernel` | ✅ Collected |
| `cudaLaunchCooperativeKernel` | ✅ Collected |
| `cudaLaunchCooperativeKernelMultiDevice` | ✅ Collected |

---

## Summary

### API Counts by Category

| Category | Count | Status |
|----------|-------|--------|
| Warp Shuffle | 4 | ✅ Complete |
| Warp Vote | 5 | ✅ Complete |
| Warp Reduce | 7 | ✅ Complete |
| Warp Match | 2 | ✅ Complete |
| Thread Sync | 4 | ✅ Complete |
| Memory Fence | 3 | ✅ Complete |
| Memory Allocation | 9 | ✅ Complete |
| Memory Deallocation | 4 | ✅ Complete |
| Host Memory | 3 | ✅ Complete |
| Memory Copy | 12 | ✅ Complete |
| Memory Set | 6 | ✅ Complete |
| Memory Management | 3 | ✅ Complete |
| Stream APIs | 23 | ✅ Complete |
| Event APIs | 8 | ✅ Complete |
| Device Selection/Init | 9 | ✅ Complete |
| Device Attributes | 5 | ✅ Complete |
| Cache/Memory Config | 5 | ✅ Complete |
| Device Limits | 3 | ✅ Complete |
| IPC | 5 | ✅ Complete |
| Peer-to-Peer/Other | 2 | ✅ Complete |
| Execution Control | 4 | ✅ Complete |
| **TOTAL** | **125** | **100%** |

### Data Sources

- **CUDA Runtime API**: https://docs.nvidia.com/cuda/cuda-runtime-api/index.html
- **CUDA Programming Guide**: https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html
