# VQETape RTX 3090 GPU findings

## Workload and environment

- Open-boundary TFIM, `n=10`, depth `L=4`, plus initial state,
  `complex64`, seed 33.
- RTX 3090 24 GB, NVIDIA driver 550.135, CUDA 12.2.
- Python 3.12.11, JAX/JAXlib 0.4.38, cuDNN 9.1.1.17.
- Five synchronized warm repetitions in fresh worker processes.
- `JAX_DEFAULT_MATMUL_PRECISION=highest`.

The fixed representatives are statevector unrolled/default, direct-TN
greedy/dense/MPO/no-rematerialization, and spatial-transfer greedy/block
width 2/default adjoint/unroll 1. This is a same-workload GPU validation of
the three exact representations, not a complete high-precision autotuner
sweep.

## Result

| Representation | Slurm job | Compile (s) | First execute (s) | Cold total (s) | Warm median (ms) | Warm MAD (ms) | Compile + 100 warm (s) | Host peak RSS (MiB) | NVML job peak (MiB) | Energy abs. error | Gradient rel. L2 error |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Statevector | 23015042 | 28.7213 | 0.4025 | 29.1238 | 3.3785 | 0.0231 | 29.4617 | 462.4 | 272 | 0 | 0 |
| Direct TN, dense MPO | 23015037 | 45.6544 | 0.1376 | 45.7920 | 5.0498 | 0.0669 | 46.2970 | 575.0 | 274 | 9.54e-7 | 4.18e-7 |
| Spatial transfer, block 2 | 23015038 | 15.5816 | 0.3636 | 15.9452 | 8.3281 | 0.0269 | 16.7781 | 473.9 | 274 | 3.81e-6 | 9.15e-7 |

All three jobs ended `COMPLETED/0:0`, reported `jax_backend=gpu` and
`jax_devices=["cuda:0"]`, passed the `complex64` energy/gradient tolerance,
and passed local and remote SHA256 audits.

At this small workload, statevector has the fastest steady-state kernel.
Spatial transfer instead cuts compilation by 45.7% and the declared
`compile + 100 warm` objective by 43.1% relative to statevector. Under this
single-workload model, the statevector/spatial break-even is about 2,663 VQE
calls. Direct TN is not selected at this size.

The nearly identical 272–274 MiB NVML peaks are job-level sampled device
allocations for a small workload. They do not demonstrate the asymptotic
memory advantage of spatial transfer; host RSS, compiler memory, logical
tape, and device allocation remain separately labeled.

## Precision A/B finding

The identical spatial candidate was also run with the platform-default
matmul precision:

| Matmul precision | Slurm job | Warm median (ms) | Energy abs. error | Gradient rel. L2 error | Correctness |
|---|---:|---:|---:|---:|---|
| Platform default | 23015032 | 8.4699 | 3.659e-2 | 3.634e-3 | fail |
| `highest` | 23015038 | 8.3281 | 3.815e-6 | 9.145e-7 | pass |

The default-precision candidate executed successfully, so this is not a
timeout or backend-availability failure. It is a numerical correctness
failure caused by reduced-precision GPU matrix products. VQETape now gives
fresh workers `JAX_DEFAULT_MATMUL_PRECISION=highest` unless the caller
explicitly overrides it. JAX documents both the environment variable and
the accuracy/performance tradeoff:
<https://docs.jax.dev/en/latest/config_options.html#default-matmul-precision>.

Slurm 23015271 is an integration check of that policy. Its parent environment
explicitly unsets `JAX_DEFAULT_MATMUL_PRECISION`; the updated VQETape
benchmark layer supplies `highest` only to the fresh worker. The same spatial
candidate then passes with energy error `3.815e-6` and gradient error
`9.145e-7`.

## Raw evidence

- [`vqetape-gpu-rtx3090-statevector-n10-d4.json`](vqetape-gpu-rtx3090-statevector-n10-d4.json)
  — SHA256 `07fc84c765d8f0d8d070c114e08cfe0886ae0a8ff2e8270905c915164a2ae93b`
- [`vqetape-gpu-rtx3090-direct-tn-n10-d4.json`](vqetape-gpu-rtx3090-direct-tn-n10-d4.json)
  — SHA256 `a7524d95258541ac8406f8a432801ffadb1f9a11b14b24f02aa603e7fa64d407`
- [`vqetape-gpu-rtx3090-spatial-n10-d4.json`](vqetape-gpu-rtx3090-spatial-n10-d4.json)
  — SHA256 `d16cb5e47ff73cc4d17f5cb6560da02615233be0eb103a29c948e261007b169a`
- [`vqetape-gpu-rtx3090-spatial-default-precision-control-n10-d4.json`](vqetape-gpu-rtx3090-spatial-default-precision-control-n10-d4.json)
  — SHA256 `72c569ba21949c441c7d56f0f951721ef98ae14caaaa320acf0f24af8db169ba`
- [`vqetape-gpu-rtx3090-worker-policy-check-n10-d4.json`](vqetape-gpu-rtx3090-worker-policy-check-n10-d4.json)
  — SHA256 `c1740840bbe70465347f33c4a97887007698482de71947782ea3c1e377d327f0`
