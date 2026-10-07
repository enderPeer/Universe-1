/* Minimal single-threaded CUDA emulation so u1_cuda.cu can be compiled with gcc for
 * logic checks on machines without a GPU:  g++ -O2 -x c++ -include gpu/cuda_shim.h gpu/u1_cuda.cu
 * Kernel launches are rewritten by the LAUNCH macro below (see gpu/Makefile target u1_cuda_emu). */
#pragma once
#include <cstdint>
#include <cstring>
#include <cstdlib>
#define __global__
#define __device__
#define __constant__
#define __forceinline__ inline
struct dim3 { unsigned x, y, z; };
static dim3 blockIdx, blockDim, threadIdx;
typedef int cudaError_t; enum { cudaSuccess = 0 }; enum cudaMemcpyKind { cudaMemcpyHostToDevice, cudaMemcpyDeviceToHost };
struct cudaDeviceProp { char name[64]; };
static inline cudaError_t cudaSetDevice(int) { return 0; }
static inline cudaError_t cudaGetDeviceProperties(cudaDeviceProp *p, int) { strcpy(p->name, "cpu-emulation"); return 0; }
static inline cudaError_t cudaMalloc(void *p, size_t n) { *(void **)p = malloc(n); return 0; }
template <class T> static inline cudaError_t cudaMalloc(T **p, size_t n) { *p = (T *)malloc(n); return 0; }
static inline cudaError_t cudaMemset(void *p, int v, size_t n) { memset(p, v, n); return 0; }
static inline cudaError_t cudaMemcpy(void *d, const void *s, size_t n, cudaMemcpyKind) { memcpy(d, s, n); return 0; }
template <class T> static inline cudaError_t cudaMemcpyToSymbol(T &sym, const void *src, size_t n) { memcpy(&sym, src, n); return 0; }
static inline cudaError_t cudaDeviceSynchronize() { return 0; }
static inline const char *cudaGetErrorString(cudaError_t) { return "ok"; }
static inline unsigned long long atomicCAS(unsigned long long *p, unsigned long long cmp, unsigned long long v) { unsigned long long o = *p; if (o == cmp) *p = v; return o; }
static inline unsigned atomicMin(unsigned *p, unsigned v) { unsigned o = *p; if (v < o) *p = v; return o; }
static inline unsigned atomicAdd(unsigned *p, unsigned v) { unsigned o = *p; *p += v; return o; }
#define EMU_LAUNCH(kernel, grid, block, ...) do { blockDim.x = (block); for (unsigned b_ = 0; b_ < (unsigned)(grid); b_++) { blockIdx.x = b_; for (unsigned t_ = 0; t_ < (unsigned)(block); t_++) { threadIdx.x = t_; kernel(__VA_ARGS__); } } } while (0)
