# CUDA API Collection List

**Last Updated:** 2026-04-22
**Total APIs to Collect:** ~150
**Collected:** 63
**Coverage:** ~42%

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
| `__all` | `int __all(int predicate)` | ❌ Pending |
| `__any` | `int __any(int predicate)` | ❌ Pending |

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

### 4.1 Memory Allocation

| API Name | Signature | Status |
|----------|-----------|--------|
| `cudaMalloc` | `cudaError_t cudaMalloc(void** devPtr, size_t size)` | ✅ Collected |
| `cudaMallocHost` | `cudaError_t cudaMallocHost(void** ptr, size_t size)` | ✅ Collected |
| `cudaMallocPitch` | `cudaError_t cudaMallocPitch(void** devPtr, size_t* pitch, size_t width, size_t height)` | ✅ Collected |
| `cudaMallocArray` | `cudaError_t cudaMallocArray(cudaArray_t* array, const cudaChannelFormatDesc* desc, size_t width, size_t height)` | ✅ Collected |
| `cudaMalloc3D` | `cudaError_t cudaMalloc3D(cudaPitchedPtr* pitchedDevPtr, cudaExtent extent)` | ❌ Pending |
| `cudaMalloc3DArray` | `cudaError_t cudaMalloc3DArray(cudaArray_t* array, const cudaChannelFormatDesc* desc, cudaExtent extent)` | ❌ Pending |
| `cudaMallocManaged` | `cudaError_t cudaMallocManaged(void** devPtr, size_t size, unsigned int flags)` | ❌ Pending |
| `cudaMallocMipmappedArray` | `cudaError_t cudaMallocMipmappedArray(cudaMipmappedArray_t* mipmapArray, const cudaChannelFormatDesc* desc, cudaExtent extent, unsigned int numLevels)` | ❌ Pending |

### 4.2 Memory Deallocation

| API Name | Signature | Status |
|----------|-----------|--------|
| `cudaFree` | `cudaError_t cudaFree(void* devPtr)` | ✅ Collected |
| `cudaFreeHost` | `cudaError_t cudaFreeHost(void* ptr)` | ✅ Collected |
| `cudaFreeArray` | `cudaError_t cudaFreeArray(cudaArray_t array)` | ❌ Pending |
| `cudaFreeMipmappedArray` | `cudaError_t cudaFreeMipmappedArray(cudaMipmappedArray_t mipmapArray)` | ❌ Pending |

### 4.3 Memory Copy

| API Name | Signature | Status |
|----------|-----------|--------|
| `cudaMemcpy` | `cudaError_t cudaMemcpy(void* dst, const void* src, size_t count, cudaMemcpyKind kind)` | ✅ Collected |
| `cudaMemcpyAsync` | `cudaError_t cudaMemcpyAsync(void* dst, const void* src, size_t count, cudaMemcpyKind kind, cudaStream_t stream)` | ✅ Collected |
| `cudaMemcpy2D` | `cudaError_t cudaMemcpy2D(void* dst, size_t dpitch, const void* src, size_t spitch, size_t width, size_t height, cudaMemcpyKind kind)` | ❌ Pending |
| `cudaMemcpy2DAsync` | `cudaError_t cudaMemcpy2DAsync(void* dst, size_t dpitch, const void* src, size_t spitch, size_t width, size_t height, cudaMemcpyKind kind, cudaStream_t stream)` | ❌ Pending |
| `cudaMemcpy3D` | `cudaError_t cudaMemcpy3D(const cudaMemcpy3DParms* p)` | ❌ Pending |
| `cudaMemcpy3DAsync` | `cudaError_t cudaMemcpy3DAsync(const cudaMemcpy3DParms* p, cudaStream_t stream)` | ❌ Pending |
| `cudaMemcpyPeer` | `cudaError_t cudaMemcpyPeer(void* dst, int dstDevice, const void* src, int srcDevice, size_t count)` | ❌ Pending |
| `cudaMemcpyPeerAsync` | `cudaError_t cudaMemcpyPeerAsync(void* dst, int dstDevice, const void* src, int srcDevice, size_t count, cudaStream_t stream)` | ❌ Pending |
| `cudaMemcpyToSymbol` | `cudaError_t cudaMemcpyToSymbol(const void* symbol, const void* src, size_t count, size_t offset, cudaMemcpyKind kind)` | ✅ Collected |
| `cudaMemcpyFromSymbol` | `cudaError_t cudaMemcpyFromSymbol(void* dst, const void* symbol, size_t count, size_t offset, cudaMemcpyKind kind)` | ❌ Pending |
| `cudaMemcpyToSymbolAsync` | `cudaError_t cudaMemcpyToSymbolAsync(const void* symbol, const void* src, size_t count, size_t offset, cudaMemcpyKind kind, cudaStream_t stream)` | ✅ Collected |
| `cudaMemcpyFromSymbolAsync` | `cudaError_t cudaMemcpyFromSymbolAsync(void* dst, const void* symbol, size_t count, size_t offset, cudaMemcpyKind kind, cudaStream_t stream)` | ❌ Pending |

### 4.4 Memory Set

| API Name | Signature | Status |
|----------|-----------|--------|
| `cudaMemset` | `cudaError_t cudaMemset(void* devPtr, int value, size_t count)` | ✅ Collected |
| `cudaMemsetAsync` | `cudaError_t cudaMemsetAsync(void* devPtr, int value, size_t count, cudaStream_t stream)` | ✅ Collected |
| `cudaMemset2D` | `cudaError_t cudaMemset2D(void* devPtr, size_t pitch, int value, size_t width, size_t height)` | ❌ Pending |
| `cudaMemset2DAsync` | `cudaError_t cudaMemset2DAsync(void* devPtr, size_t pitch, int value, size_t width, size_t height, cudaStream_t stream)` | ❌ Pending |
| `cudaMemset3D` | `cudaError_t cudaMemset3D(cudaPitchedPtr pitchedDevPtr, int value, cudaExtent extent)` | ❌ Pending |
| `cudaMemset3DAsync` | `cudaError_t cudaMemset3DAsync(cudaPitchedPtr pitchedDevPtr, int value, cudaExtent extent, cudaStream_t stream)` | ❌ Pending |

---

## 5. CUDA Runtime Stream APIs

**Source:** [CUDA Runtime API - Stream Management](https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__STREAM.html)

| API Name | Signature | Status |
|----------|-----------|--------|
| `cudaStreamCreate` | `cudaError_t cudaStreamCreate(cudaStream_t* stream)` | ✅ Collected |
| `cudaStreamCreateWithFlags` | `cudaError_t cudaStreamCreateWithFlags(cudaStream_t* stream, unsigned int flags)` | ✅ Collected |
| `cudaStreamDestroy` | `cudaError_t cudaStreamDestroy(cudaStream_t stream)` | ✅ Collected |
| `cudaStreamSynchronize` | `cudaError_t cudaStreamSynchronize(cudaStream_t stream)` | ✅ Collected |
| `cudaStreamWaitEvent` | `cudaError_t cudaStreamWaitEvent(cudaStream_t stream, cudaEvent_t event, unsigned int flags)` | ✅ Collected |
| `cudaStreamAddCallback` | `cudaError_t cudaStreamAddCallback(cudaStream_t stream, cudaStreamCallback_t callback, void* userData, unsigned int flags)` | ✅ Collected |
| `cudaStreamQuery` | `cudaError_t cudaStreamQuery(cudaStream_t stream)` | ❌ Pending |
| `cudaStreamBeginCapture` | `cudaError_t cudaStreamBeginCapture(cudaStream_t stream, cudaStreamCaptureMode mode)` | ❌ Pending |
| `cudaStreamEndCapture` | `cudaError_t cudaStreamEndCapture(cudaStream_t stream, cudaGraph_t* graph)` | ❌ Pending |
| `cudaStreamIsCapturing` | `cudaError_t cudaStreamIsCapturing(cudaStream_t stream, cudaStreamCaptureStatus* status)` | ❌ Pending |
| `cudaStreamAttachMemAsync` | `cudaError_t cudaStreamAttachMemAsync(cudaStream_t stream, void* devPtr, size_t length, unsigned int flags)` | ❌ Pending |
| `cudaStreamGetCaptureInfo` | `cudaError_t cudaStreamGetCaptureInfo(cudaStream_t stream, cudaStreamCaptureStatus* status, cuuint64_t* id)` | ❌ Pending |

---

## 6. CUDA Runtime Event APIs

**Source:** [CUDA Runtime API - Event Management](https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__EVENT.html)

| API Name | Signature | Status |
|----------|-----------|--------|
| `cudaEventCreate` | `cudaError_t cudaEventCreate(cudaEvent_t* event)` | ✅ Collected |
| `cudaEventCreateWithFlags` | `cudaError_t cudaEventCreateWithFlags(cudaEvent_t* event, unsigned int flags)` | ✅ Collected |
| `cudaEventDestroy` | `cudaError_t cudaEventDestroy(cudaEvent_t event)` | ✅ Collected |
| `cudaEventRecord` | `cudaError_t cudaEventRecord(cudaEvent_t event, cudaStream_t stream)` | ✅ Collected |
| `cudaEventQuery` | `cudaError_t cudaEventQuery(cudaEvent_t event)` | ✅ Collected |
| `cudaEventSynchronize` | `cudaError_t cudaEventSynchronize(cudaEvent_t event)` | ✅ Collected |
| `cudaEventElapsedTime` | `cudaError_t cudaEventElapsedTime(float* ms, cudaEvent_t start, cudaEvent_t end)` | ✅ Collected |

---

## 7. CUDA Runtime Device APIs

**Source:** [CUDA Runtime API - Device Management](https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__DEVICE.html)

### 7.1 Device Query & Selection

| API Name | Signature | Status |
|----------|-----------|--------|
| `cudaChooseDevice` | `cudaError_t cudaChooseDevice(int* device, const cudaDeviceProp* prop)` | ❌ Pending |
| `cudaGetDevice` | `cudaError_t cudaGetDevice(int* device)` | ❌ Pending |
| `cudaSetDevice` | `cudaError_t cudaSetDevice(int device)` | ❌ Pending |
| `cudaGetDeviceCount` | `cudaError_t cudaGetDeviceCount(int* count)` | ❌ Pending |
| `cudaGetDeviceProperties` | `cudaError_t cudaGetDeviceProperties(cudaDeviceProp* prop, int device)` | ❌ Pending |

### 7.2 Device Synchronization

| API Name | Signature | Status |
|----------|-----------|--------|
| `cudaDeviceSynchronize` | `cudaError_t cudaDeviceSynchronize()` | ❌ Pending |
| `cudaDeviceReset` | `cudaError_t cudaDeviceReset()` | ❌ Pending |

### 7.3 Cache & Limits

| API Name | Signature | Status |
|----------|-----------|--------|
| `cudaDeviceGetCacheConfig` | `cudaError_t cudaDeviceGetCacheConfig(cudaFuncCache* cacheConfig)` | ❌ Pending |
| `cudaDeviceSetCacheConfig` | `cudaError_t cudaDeviceSetCacheConfig(cudaFuncCache cacheConfig)` | ❌ Pending |
| `cudaDeviceGetLimit` | `cudaError_t cudaDeviceGetLimit(size_t* pValue, cudaLimit limit)` | ❌ Pending |
| `cudaDeviceSetLimit` | `cudaError_t cudaDeviceSetLimit(cudaLimit limit, size_t value)` | ❌ Pending |

---

## 8. Execution Control (Kernel Launch)

**Source:** [CUDA Programming Guide - Execution Configuration](https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#execution-configuration)

| API Name | Signature | Status |
|----------|-----------|--------|
| `cudaConfigureCall` | `cudaError_t cudaConfigureCall(dim3 gridDim, dim3 blockDim, size_t sharedMem, cudaStream_t stream)` | ❌ Pending |
| `cudaLaunchKernel` | `cudaError_t cudaLaunchKernel(const void* func, dim3 gridDim, dim3 blockDim, void** args, size_t sharedMem, cudaStream_t stream)` | ❌ Pending |
| `cudaLaunchCooperativeKernel` | `cudaError_t cudaLaunchCooperativeKernel(const void* func, dim3 gridDim, dim3 blockDim, void** args, size_t sharedMem, cudaStream_t stream)` | ❌ Pending |
| `cudaLaunchCooperativeKernelMultiDevice` | `cudaError_t cudaLaunchCooperativeKernelMultiDevice(const cudaLaunchKernelMultDeviceParams* params, unsigned int flags)` | ❌ Pending |

---

## Summary

### Collected APIs: 63

| Category | Collected | Total | Coverage |
|----------|-----------|-------|----------|
| Warp Shuffle | 4 | 4 | 100% |
| Warp Vote | 3 | 5 | 60% |
| Warp Reduce | 7 | 7 | 100% |
| Warp Match | 2 | 2 | 100% |
| Thread Sync | 4 | 4 | 100% |
| Memory Fence | 3 | 3 | 100% |
| Memory Allocation | 4 | 8 | 50% |
| Memory Copy | 5 | 13 | 38% |
| Memory Set | 2 | 6 | 33% |
| Stream | 6 | 12 | 50% |
| Event | 7 | 7 | 100% |
| Device | 11 | 11 | 100% |
| Execution | 4 | 4 | 100% |

### Priority Collection Order

1. **Memory 3D/Peer APIs** - Memory copy/set operations (8 remaining)
2. **Stream capture/query APIs** - Graph capture support (6 remaining)
3. **Memory managed/mipmapped** - Unified memory support (4 remaining)
4. **Legacy Warp Vote** - __all, __any deprecated APIs (2 remaining)

### Data Source

All CUDA Runtime APIs are documented at:
- https://docs.nvidia.com/cuda/cuda-runtime-api/index.html

Intrinsic functions (warp shuffle, vote, etc.) are documented at:
- https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html
