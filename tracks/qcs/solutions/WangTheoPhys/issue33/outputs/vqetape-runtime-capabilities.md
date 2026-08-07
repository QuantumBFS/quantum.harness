# VQETape runtime capabilities

- Backend: `cpu`.
- JAX devices: `1`.
- JAX x64 enabled in probe: `False`.
- GPU benchmark status: `skipped`.
- GPU skip reason: JAX reports no GPU device; CUDA/ROCm runtime and genuine GPU peak memory were not measured.
- Process peak RSS means host resident memory; it is never reported as GPU peak memory.
- Compiler memory analysis available: `True`.

## Devices

- `cpu:0` — cpu; device memory stats available: `False`.

No CUDA-specific performance or memory conclusion is made when the GPU status is skipped.
