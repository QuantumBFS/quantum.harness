# VQETape Exact Spatial-Transfer Findings

## Experimental contract

This phase compares exact global bra–MPO–ket contractions with exact
spatial-transfer programs for the same open-boundary TFIM VQE energy and
complete gradient. Every measured candidate runs in a fresh process and is
validated against the state-vector oracle.

The spatial program is constructed from the already verified
operator-Schmidt RZZ and bond-dimension-3 TFIM MPO tensors. Each bulk
contraction receives the current boundary as operand zero and emits only the
next boundary.

The search contains three global dense-MPO controls and 15 spatial
candidates:

\[
\{\text{greedy},\text{random-greedy},\text{auto-hq}\}
\times
\{
\text{default-u1},
\text{default-u2},
\text{remat-u1},
\text{remat-u2},
\text{segmented}
\}.
\]

For each path strategy, first/bulk/last contraction paths are searched once,
serialized, and reused by all five spatial schedules. The audited reports
confirm identical forward FLOP counts within every such group. This prevents
stochastic path differences from being mistaken for AD-schedule effects.

Raw reports:

- [eight-qubit report](vqetape-spatial-transfer-report-n8-d2.json)
- [twelve-qubit report](vqetape-spatial-transfer-report-n12-d2.json)

## Correctness and structural invariants

The implemented spatial cuts retain:

- one ket RZZ Schmidt index per layer;
- one bra RZZ Schmidt index per layer;
- one Hamiltonian MPO index.

Therefore:

\[
\operatorname{shape}(B)
=
\underbrace{(2,\ldots,2)}_{2L\ \mathrm{entries}}
\mathbin{\|}(3,),
\qquad
\dim B=3\cdot4^L.
\]

Structural tests cover depths one, two, and three. For the tested greedy
paths, every bulk contraction output and intermediate is smaller than
\(D^2\); no full transfer matrix is emitted.

Sequential spatial energies match the global MPO for two through five
qubits, depths one and two, both supported product initial states, non-unit
couplings, and complex64/complex128 checks. Default, rematerialized, and
segmented scan adjoints match on complete gradients, including partial final
segments. The unused padded RZZ gradient remains exactly zero.

## Rolled control flow

At fixed depth one, value-and-gradient StableHLO contains rolled `while`
control flow for both six and ten qubits. In the audited run, the text sizes
were 107,194 and 107,215 characters respectively. This is evidence that the
bulk body is reused rather than Python-unrolled with chain length; it is not a
claim that every compiler IR component is perfectly constant.

## Global MPO versus spatial-transfer results

Both workloads used `complex64`, three synchronized warm repetitions, a
2 GiB process-memory budget, and a 100-call VQE horizon.

All 36 measured candidates were valid. The maximum errors over the
eight-qubit report were:

\[
\epsilon_E=6.20\times10^{-6},
\qquad
\epsilon_g=1.56\times10^{-6}.
\]

For twelve qubits:

\[
\epsilon_E=6.68\times10^{-6},
\qquad
\epsilon_g=1.27\times10^{-6}.
\]

Both are within the configured complex64 tolerances.

### Horizon-selected programs

The control in each comparison is the global-MPO candidate with the lowest
\(T_{\mathrm{compile}}+100T_{\mathrm{warm}}\), not a deliberately weak
global path.

| Workload | Program | Path/AD | Compile (s) | Warm (µs) | Compiler temp (B) | RSS (MiB) | Logical tape (B) | 100-step cost (s) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| \(n=8,L=2\) | Spatial | random-greedy/remat-u1 | 1.234 | 492.54 | 12,360 | 246.94 | 5,472 | 1.283 |
| \(n=8,L=2\) | Global MPO control | greedy/default | 5.496 | 391.17 | 29,512 | 270.30 | 28,880 | 5.535 |
| \(n=12,L=2\) | Spatial | greedy/remat-u1 | 1.609 | 762.63 | 13,496 | 242.84 | 7,504 | 1.686 |
| \(n=12,L=2\) | Global MPO control | random-greedy/default | 14.188 | 606.12 | 50,376 | 248.56 | 48,432 | 14.249 |

The selected spatial program therefore reduced the 100-step objective by:

- 4.31× at eight qubits;
- 8.45× at twelve qubits.

This does **not** come from a faster warm kernel. The selected spatial
program was about 1.26× slower per warm call in both workloads. It won because
the compiler reused a rolled bulk body:

- compile time was 4.45× and 8.82× shorter;
- compiler temporary bytes were 2.39× and 3.73× smaller;
- logical tape was 5.28× and 6.45× smaller.

### Best observed metric by representation

Different rows may attain each column; this table describes the measured
representation envelope rather than one candidate.

| Workload | Representation | Best compile (s) | Best warm (µs) | Best compiler temp (B) |
|---|---|---:|---:|---:|
| \(n=8,L=2\) | Global MPO | 5.496 | 300.83 | 28,168 |
| \(n=8,L=2\) | Spatial | 1.234 | 402.67 | 11,656 |
| \(n=12,L=2\) | Global MPO | 14.188 | 467.63 | 46,728 |
| \(n=12,L=2\) | Spatial | 1.609 | 594.33 | 13,112 |

Warm-only selection would still choose the global MPO on these CPU
workloads. Spatial transfer is the compile/memory/horizon winner, not yet the
single-call throughput winner.

## Default, remat, and segmented adjoints

The same auto-hq spatial path gives a fixed-path comparison:

| Workload | Adjoint | Compile (s) | Warm (µs) | Compiler temp (B) | Logical tape (B) | Modeled carry bytes |
|---|---|---:|---:|---:|---:|---:|
| \(n=8\) | default-u1 | 1.280 | 559.38 | 29,472 | 22,880 | 2,304 |
| \(n=8\) | remat-u1 | 1.288 | 541.58 | 11,656 | 5,328 | 2,304 |
| \(n=8\) | segmented-s2 | 1.674 | 679.46 | 19,752 | 3,862 | 1,920 |
| \(n=12\) | default-u1 | 2.452 | 713.83 | 42,208 | 35,936 | 3,840 |
| \(n=12\) | remat-u1 | 2.221 | 779.71 | 13,112 | 6,976 | 3,840 |
| \(n=12\) | segmented-s3 | 2.932 | 1,067.71 | 23,720 | 4,396 | 2,688 |

Segmented checkpointing behaved as predicted at the logical/model level and
reduced compiler temporary bytes relative to default AD. However, ordinary
bulk rematerialization produced still lower compiler temporary bytes and
faster warm execution on every fixed path. Segmented is therefore retained
as an exact research candidate but is not the default.

This result also confirms why logical residual bytes, modeled carry bytes,
compiler temporary bytes, and process RSS cannot be substituted for one
another.

## Fixed-depth scaling

The scaling comparison holds depth at \(L=2\), for which the exact boundary
dimension is:

\[
D=3\cdot4^2=48.
\]

Using the best observed value within each representation, increasing the
chain from eight to twelve qubits changed:

| Metric | Global MPO factor | Spatial factor |
|---|---:|---:|
| Best compile time | 2.58× | 1.30× |
| Best warm time | 1.55× | 1.48× |
| Best compiler temp | 1.66× | 1.12× |

Two points are not enough to fit an asymptotic law, but the direction matches
the structural IR evidence: the global graph continues to grow, whereas the
spatial program reuses one fixed-depth scan body and increases its iteration
count.

## Decision-gate audit

| Gate | Result | Evidence |
|---|---|---|
| Energy and complete-gradient correctness | Pass | 36/36 fresh candidates valid; structural matrix also covers small workloads and complex128 |
| Exact boundary dimension | Pass | Every spatial report row has shape `[2,2,2,2,3]` and dimension 48 |
| No \(D^2\) transfer tensor | Pass | Bulk outputs \(D\); audited step outputs remain below \(D^2\) |
| Rolled spatial control flow | Pass | StableHLO contains `while`; six- and ten-qubit IR text sizes remain nearly equal |
| Executable nondominance | Pass | Spatial remat has higher warm time but substantially lower compiler temporary memory than every global control |
| Two-length fixed-depth trend | Pass | Compile and compiler-temp growth are lower for the spatial envelope |
| Segmented memory trade-off | Pass with negative selection result | Beats default on temp/tape/model, but remat dominates it |

The exact spatial representation advances. The current default should be
selected empirically between global MPO and spatial remat according to the
VQE horizon and memory budget.

## Regression audit

The complete repository suite passed after the fair-path benchmark rerun and
documentation update:

```text
204 passed in 749.40s (0:12:29)
```

This covers the previous state-vector, direct-TN, residual-aware,
operator-Schmidt, and exact-MPO behavior as well as spatial configuration
serialization, cut planning, carry-fused execution, full gradients, rolled
control flow, partial segmented VJPs, fresh workers, candidate selection, and
CLI report generation.

## Interpretation and limitations

The result is specific to shallow, local, one-dimensional VQE circuits. Its
iteration count can be linear in qubit count at fixed depth, while the exact
boundary dimension remains exponential in depth. It does not establish
efficient exact simulation for generic deep or two-dimensional circuits.

The benchmarks used the local CPU JAX backend. Process RSS is allocator- and
process-sensitive, and none of these numbers is a GPU peak-memory claim. A
GPU study should preserve the same serialized paths and fresh-process
contract while adding device peak and HBM-traffic measurement.
