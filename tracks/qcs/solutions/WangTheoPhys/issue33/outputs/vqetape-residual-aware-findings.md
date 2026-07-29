# VQETape Residual-Aware Tape Findings

**Date:** 2026-07-28
**Backend:** JAX 0.11.0 CPU on macOS
**Workload:** 3 qubits, 2 RZZ–RX layers, exact TFIM energy and full gradient
**Controlled variable:** reverse tape only; every row uses the same explicit
greedy contraction path

## What Was Added

VQETape now traces the VJP chosen by JAX and byte-accounts every saved
residual. Gate tensors and contraction outputs can be assigned stable names.
A named checkpoint policy then saves only an explicit subset of those values
and exactly recomputes every other intermediate in the backward pass.

JAX 0.11 cannot directly retain a policy-named complex residual because its
checkpoint transform applies `reduce_precision` to the complex value.
VQETape handles this compatibility issue by naming the real and imaginary
parts separately and reconstructing the complex tensor exactly.

## Measured Tape Control

| Tape policy | Named units saved | VJP residual bytes | JAX temp | Compile | Warm median |
|---|---:|---:|---:|---:|---:|
| JAX default | automatic | 21,700 | 9,988 | 10.73 s | 0.293 ms |
| named, save none | 0 | 608 | 12,548 | 10.83 s | 0.338 ms |
| named, 50% static contraction budget | 18 | 5,088 | 12,036 | 11.03 s | 0.351 ms |
| named, save all contraction outputs | 56 | 8,928 | 11,588 | 12.23 s | 0.305 ms |

The logical reverse tape is therefore controllable and monotone across the
three named schedules:

\[
608 < 5{,}088 < 8{,}928 < 21{,}700\ \text{bytes}.
\]

Saving every named contraction output cuts JAX's logical saved-residual bytes
by about 58.9% relative to its default reverse program:

\[
1-\frac{8{,}928}{21{,}700}\approx 58.9\%.
\]

## Important Negative Result

The smaller logical tape did **not** reduce compiler-reported temporary memory
on this tiny CPU workload. The best JAX-default executable used 9,988 temporary
bytes, while named policies used 11,588–12,548 bytes. Recomputed operations,
real/imag reconstruction, buffer scheduling, and compiler fusion all affect
the final executable, so logical tape bytes are not the same quantity as peak
device memory.

This is precisely why VQETape must measure both layers:

1. the AD program's saved residuals;
2. the lowered executable's memory and runtime.

An optimizer that looks only at the contraction tree or only at JAX's saved
residual list can choose the wrong schedule.

## Current Research Claim

The supported claim is not yet “VQETape reduces GPU peak memory.” It is:

> VQETape exposes and controls the exact reverse-mode residual set of an exact
> differentiable VQE tensor contraction, while jointly measuring the resulting
> compiler memory and runtime.

The next decision gate is a larger accelerator workload where tensor
intermediates dominate compiler bookkeeping. The named tape should only become
a default optimization if at least one fixed-path candidate reduces measured
device peak memory at acceptable recomputation cost.

## Validation Matrix

The direct tensor-network value and full gradient were cross-checked against
the state-vector oracle for:

- 2 qubits, depth 1, zero initial state, \(J=0.7,\ g=0.3\);
- 3 qubits, depth 1, plus initial state, \(J=1.2,\ g=0.4\);
- 3 qubits, depth 2, plus initial state, \(J=0.8,\ g=1.1\).

The logical tape ordering

\[
\text{save none}<\text{save all named contractions}<\text{JAX default}
\]

was also verified at both 2-qubit/depth-1 and 3-qubit/depth-2 scales. The full
repository regression completed with **75 passing tests**.
