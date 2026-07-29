# VQETape Operator-Schmidt Representation Findings

**Date:** 2026-07-29
**Backend:** JAX 0.11.0 CPU on macOS
**Search:** 2 gate representations × 3 path strategies × 4 tape policies
**Correctness oracle:** exact state-vector energy and complete gradient

## Research Question

Does replacing each dense rank-4 RZZ tensor by its exact rank-2
operator-Schmidt factorization improve the contraction path, reverse-mode
residual tape, or lowered executable?

The two exact representations are:

\[
R_{ZZ}(\theta)_{o_1o_2i_1i_2}
\]

and

\[
R_{ZZ}(\theta)
=
\sum_{a=0}^{1}
L_{o_1i_1a}(\theta)R_{o_2i_2a},
\]

where

\[
L_0=\cos\frac{\theta}{2}I,\qquad
L_1=-i\sin\frac{\theta}{2}Z,
\qquad
R_0=I,\qquad R_1=Z.
\]

Every tape policy for one representation/path pair reused the same serialized
explicit path. Dense and Schmidt paths were searched independently with the
same path strategy because their network topologies differ.

## Workloads

| Workload | Qubits | Depth | Initial state | \(J\) | \(g\) | Candidates |
|---|---:|---:|---|---:|---:|---:|
| A | 3 | 2 | plus | 1.0 | 1.0 | 24 |
| B | 3 | 1 | zero | 0.7 | 0.3 | 24 |

All **48/48** candidates passed the `complex64` energy and full-gradient
tolerances.

Maximum observed errors:

| Workload | Energy absolute error | Gradient relative L2 error |
|---|---:|---:|
| A | \(7.15\times10^{-7}\) | \(2.59\times10^{-7}\) |
| B | \(2.38\times10^{-7}\) | \(7.79\times10^{-9}\) |

The unused final RZZ parameter in every layer retained exactly zero gradient.

## Workload A: 3 Qubits, Depth 2

The following rows use the default JAX reverse tape. Time is a single
fresh-process CPU measurement and is not treated as a hardware-independent
constant.

| Representation | Path | Tensors | Input elements | FLOPs | Largest intermediate | Logical residual bytes | `_diag` bytes | JAX temp | Compile | Warm |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | auto-hq | 29 | 200 | 1,080 | 16 | 21,540 | 6,080 | 8,708 B | 9.299 s | 0.333 ms |
| dense | greedy | 29 | 200 | 1,048 | 16 | 21,700 | 6,080 | 9,988 B | 8.564 s | 0.350 ms |
| dense | random-greedy | 29 | 200 | 1,120 | 16 | 22,020 | 6,080 | 9,216 B | 9.519 s | 0.198 ms |
| Schmidt | auto-hq | 37 | 200 | 1,184 | 16 | 18,660 | 0 | 9,668 B | 6.960 s | 0.425 ms |
| Schmidt | greedy | 37 | 200 | 1,456 | 32 | 19,940 | 0 | 9,476 B | 8.510 s | 0.351 ms |
| Schmidt | random-greedy | 37 | 200 | 1,200 | 16 | 18,660 | 0 | 9,476 B | 6.281 s | 0.624 ms |

The best default logical tape fell from 21,540 to 18,660 bytes:

\[
1-\frac{18{,}660}{21{,}540}\approx13.4\%.
\]

However:

- best estimated FLOPs increased from 1,048 to 1,184;
- best compiler temporary memory increased from 8,708 to 9,476 bytes;
- best warm time increased from 0.198 to 0.351 ms.

For \(K=100\), the horizon selector chose Schmidt random-greedy with the
default tape because its one measured compile time was lower. Its warm runtime
was not competitive, so this is a cold-start trade-off rather than a general
throughput improvement.

## Workload B: 3 Qubits, Depth 1

| Representation | Path | Tensors | Input elements | FLOPs | Largest intermediate | Logical residual bytes | `_diag` bytes | JAX temp | Compile | Warm |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | auto-hq | 19 | 112 | 400 | 8 | 8,780 | 3,040 | 4,164 B | 3.504 s | 0.202 ms |
| dense | greedy | 19 | 112 | 408 | 8 | 8,780 | 3,040 | 4,292 B | 3.464 s | 0.215 ms |
| dense | random-greedy | 19 | 112 | 400 | 8 | 8,780 | 3,040 | 4,164 B | 2.847 s | 0.229 ms |
| Schmidt | auto-hq | 23 | 112 | 432 | 8 | 7,420 | 0 | 4,640 B | 4.019 s | 0.237 ms |
| Schmidt | greedy | 23 | 112 | 440 | 8 | 7,260 | 0 | 4,740 B | 3.514 s | 0.307 ms |
| Schmidt | random-greedy | 23 | 112 | 440 | 8 | 7,420 | 0 | 4,612 B | 3.741 s | 0.253 ms |

The best default logical tape fell from 8,780 to 7,260 bytes:

\[
1-\frac{7{,}260}{8{,}780}\approx17.3\%.
\]

The executable trend again favored dense:

- best FLOPs: 400 dense versus 432 Schmidt;
- best JAX temp: 4,164 versus 4,612 bytes;
- best warm time: 0.202 versus 0.237 ms;
- best compile time: 2.847 versus 3.514 s.

The horizon selector chose dense random-greedy.

## Why Input Elements Did Not Fall

One dense RZZ slot stores:

\[
2^4=16
\]

elements. Two Schmidt factors store:

\[
2^3+2^3=16
\]

elements. The exact factorization exposes low-rank connectivity and removes
structural zeros, but it does not reduce the raw number of bound elements in
this uncompressed implementation.

It also adds one tensor and one contraction per factor pair. For these small
networks, the extra graph structure outweighed the lower-rank semantics in
path FLOPs and executable scheduling.

## Named Tape Behavior

Both representations retained exact named residual-budget control. In
workload A:

- dense default tape: 21.5–22.0 KB depending on path;
- Schmidt default tape: 18.7–19.9 KB;
- dense named-empty tape: 608 B;
- Schmidt named-empty tape: 3,168 B.

The higher Schmidt named-empty floor comes from additional factor-construction
values and constants that cannot be eliminated merely by excluding named
contraction outputs.

Logical tape bytes and compiler temporary bytes again moved differently. This
confirms that VQETape must measure both rather than using saved-residual totals
as a proxy for device peak memory.

## Decision-Gate Audit

| Gate | Result | Evidence |
|---|---|---|
| Energy and complete-gradient correctness | **PASS** | 48/48 candidates valid; oracle errors below tolerance |
| Eliminate dense `_diag` residuals | **PASS** | 6,080→0 B at depth 2; 3,040→0 B at depth 1 |
| Materially change path or logical tape | **PASS** | logical tape reduced 13.4% and 17.3%; path FLOPs also changed |
| Schmidt candidate nondominated in compiler temp and warm runtime | **FAIL** | every Schmidt candidate was dominated by at least one dense candidate in both workloads |
| Qualitative result holds on two workloads | **PASS** | lower logical tape but worse executable Pareto on both |

## Conclusion

The operator-Schmidt lowering is mathematically correct and improves the
logical AD representation, but this explicit two-factor network is not a
performance win for the tested workloads.

The supported result is:

> Exposing the exact operator-Schmidt rank of RZZ eliminates dense gate
> construction residuals and reduces JAX's default logical VJP tape, but the
> additional factor nodes increase contraction work and are dominated by the
> dense representation after compiler lowering on these CPU workloads.

This negative result rules out “factor every RZZ gate into two explicit
tensors” as the next default optimization.

The next promising representation should preserve the rank-2 algebra without
materializing two generic tensors—for example, a fused structured RZZ
contraction/custom primitive—or move to Hamiltonian-level MPO/spatial-transfer
sharing, where repeated Pauli-term contraction is the larger source of
redundancy.

CPU process RSS is not GPU peak memory. No accelerator-memory claim is made.

## Repository Validation

The final regression suite completed with:

```text
100 passed in 516.05s
```

This includes dense backward-compatibility, RZZ factor reconstruction at
boundary angles and `complex128`, closed-network topology, incompatible-path
rejection, fresh-process transport for both representations, structured
residual attribution, named tape budgets, and the multi-workload energy and
complete-gradient oracle matrix.
