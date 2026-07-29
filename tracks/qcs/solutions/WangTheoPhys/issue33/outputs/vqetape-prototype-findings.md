# VQETape Oracle Prototype Findings

**Date:** 2026-07-28
**Backend:** JAX 0.11.0 CPU on macOS
**Precision:** `complex64`
**Task:** exact TFIM VQE energy and full reverse-mode gradient

## Verification

- Test suite: **40 passed**
- Full-suite wall time: **505.12 s**
- Every benchmark candidate executed in a fresh process.
- Every candidate in both experiments passed full-gradient correctness.
- CPU process peak RSS and JAX executable memory analysis are reported
  separately. Neither is interpreted as GPU peak memory.

## Experiment 1: 4 qubits, 4 layers

- Candidates: **16**
- Correct candidates: **16**
- Pareto candidates: **7**
- \(K\)-aware selection for \(K=100\):
  `scan-segmented-u2-s1`
- Selected gradient relative L2 error: \(3.58\times10^{-8}\)

Representative JAX compiler temporary-memory estimates:

| Program | Temporary bytes | Warm median |
|---|---:|---:|
| `scan-default-u1` | 9,704 | 0.159 ms |
| `scan-remat-u1` | 3,536 | 0.371 ms |
| `scan-segmented-u1-s1` | 3,648 | 0.216 ms |

Relative to default scan, compiler-reported temporary memory decreased by:

- rematerialization: **63.6%**
- segmented adjoint: **62.4%**

## Experiment 2: 5 qubits, 6 layers

- Candidates: **19**
- Correct candidates: **19**
- Pareto candidates: **6**
- \(K\)-aware selection for \(K=100\):
  `scan-segmented-u4-s1`
- Selected gradient relative L2 error: \(6.23\times10^{-8}\)

Representative JAX compiler temporary-memory estimates:

| Program | Temporary bytes | Warm median |
|---|---:|---:|
| `scan-default-u1` | 26,552 | 0.391 ms |
| `scan-remat-u1` | 8,544 | 0.596 ms |
| `scan-segmented-u1-s2` | 12,792 | 0.397 ms |

Relative to default scan, compiler-reported temporary memory decreased by:

- rematerialization: **67.8%**
- segmented adjoint with segment length 2: **51.8%**

## What the Evidence Supports

1. Reverse-mode schedule choices materially change compiler-reported temporary
   memory for the exact VQE full-gradient kernel.
2. Segmented custom-adjoint candidates appear on the measured compile/warm/RSS
   Pareto frontier at both tested sizes.
3. Full-gradient correctness is preserved across unrolled, scan,
   rematerialized, and segmented programs.
4. The prototype's first decision gates are satisfied, so implementing direct
   bra-Hamiltonian-ket tensor programs is justified.

## What the Evidence Does Not Support

1. It does **not** prove a GPU peak-memory reduction. These experiments ran on
   CPU and process RSS is dominated by runtime/library overhead.
2. It does **not** show that segmented scheduling is uniformly better than
   generic rematerialization. Generic rematerialization produced the smallest
   compiler temporary-memory estimate in both experiments.
3. Compile-time measurements show substantial fresh-process variance and host
   contention. A paper-quality result needs multiple independent cold trials.
4. Sub-millisecond warm calls are too short for stable performance claims.
   Future benchmarks must execute batches of repeated optimizer steps per
   timed sample.
5. The state-vector oracle does not change asymptotic complexity. VQETape's
   tensor-contraction claim still requires the next direct scalar-contraction
   phase.

## Decision

Proceed to phase 2 with a narrow target:

> Lower the same 1D TFIM VQE objective to an exact direct
> bra-Hamiltonian-ket tensor program, expose its contraction intermediates,
> derive its adjoint residual graph, and compare fixed-path rematerialization
> with joint block/path/tape choices.
