# VQETape AD-Aware Contraction Findings

## Scope

This experiment evaluates exact differentiated spatial-transfer VQE
programs for the open-boundary TFIM RZZ–RX ansatz. It adds static
reconstruction of every forward and reverse einsum, differentiated cost
accounting, a recomputing custom VJP, and fixed-path comparisons of default,
rematerialized, segmented, and explicit adjoints.

Every timing candidate ran in a fresh process. Both audited workloads use
`complex64`, depth two, a 2 GiB selection budget, five synchronized warm
calls, and a 100-call selection horizon. Raw data are in
`vqetape-ad-aware-report-n8-d2.json` and
`vqetape-ad-aware-report-n12-d2.json`.

## Correctness and candidate coverage

At eight qubits, all 78 spatial candidates were valid, including all 21
explicit-VJP candidates.

At twelve qubits, 85 of 93 spatial candidates were valid. Eight candidates
sharing the same `random-greedy`, width-two path missed the `complex64`
energy tolerance by \(1.1444\times10^{-5}\), slightly above the configured
\(10^{-5}\) threshold. This affected default, remat, and explicit policies
equally, so it is a path-conditioning result rather than evidence of a
custom-VJP inconsistency. The remaining 22 explicit candidates were valid.

| workload | max explicit energy error | max explicit relative gradient error |
|---|---:|---:|
| \(n=8,L=2\) | \(7.15\times10^{-6}\) | \(1.57\times10^{-6}\) |
| \(n=12,L=2\) | \(9.54\times10^{-6}\) | \(4.43\times10^{-6}\) |

The explicit complex contraction VJP was independently checked against
`jax.vjp` for matrix, scalar, and multistep contractions. JAX's complex
cotangent convention uses the algebraic transpose for these holomorphic
einsums; inserting a Hermitian conjugation would be incorrect.

## Does the static AD score predict warm runtime?

Spearman correlations were calculated separately over valid spatial
candidates:

| workload | candidates | forward FLOPs vs warm | forward+backward FLOPs vs warm | AD score vs warm | role residual vs compiler temp |
|---|---:|---:|---:|---:|---:|
| \(n=8,L=2\) | 78 | -0.227 (p=0.045) | -0.227 (p=0.045) | -0.057 (p=0.620) | 0.479 (p=\(9.21\times10^{-6}\)) |
| \(n=12,L=2\) | 85 | -0.045 (p=0.686) | -0.045 (p=0.686) | -0.021 (p=0.845) | 0.551 (p=\(4.59\times10^{-8}\)) |

The first deterministic AD score did **not** improve warm-runtime ranking
over forward FLOPs. It therefore fails the pruning gate and remains
diagnostic only. Forward and total differentiated FLOPs have the same ranks
because generated reverse work is nearly proportional to forward work in
this family. Larger blocked programs can also have more FLOPs while reducing
scan overhead, explaining the weak or negative runtime correlation.

Residual size is a materially better signal for compiler temporary memory,
although 0.48–0.55 correlation is not accurate enough to replace
measurement.

## Explicit VJP versus identical default paths

Only pairs with identical strategy, block width, unroll, and serialized paths
were compared. A ratio below one favors explicit VJP.

| workload | pairs | median compile ratio | compile wins | median warm ratio | warm wins | median temp ratio | temp wins | median tape ratio | tape wins |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| \(n=8,L=2\) | 21 | 0.876 | 14 | 1.200 | 10 | 0.871 | 14 (+2 ties) | 0.290 | 21 |
| \(n=12,L=2\) | 22 | 1.129 | 8 | 1.430 | 7 | 0.610 | 18 | 0.280 | 22 |

The custom reverse program reduced logical tape in every valid pair.
Compiler temporary memory also improved in most pairs, especially at twelve
qubits. Warm runtime did not improve in the median because recomputing the
trace and emitting explicit reverse einsums often costs more than JAX's fused
transpose.

Nevertheless, explicit VJP strictly dominated its paired default in all
compile/warm/temp metrics for six eight-qubit structures and one
twelve-qubit structure. In the full three-objective spatial Pareto sets:

- 5 of 14 eight-qubit frontier candidates used explicit VJP;
- 3 of 14 twelve-qubit frontier candidates used explicit VJP.

Explicit VJP therefore passes the nondominance gate as a search candidate,
but not a universal-default gate.

## End-of-horizon selection

For \(T_{\mathrm{compile}}+100T_{\mathrm{warm}}\):

| workload | selected spatial program | compile | warm | objective | compiler temp | logical tape |
|---|---|---:|---:|---:|---:|---:|
| \(n=8,L=2\) | random-greedy, b1, remat, u1 | 1.604 s | 1.033 ms | 1.707 s | 12,296 B | 5,472 B |
| \(n=12,L=2\) | greedy, b1, explicit, u1 | 2.044 s | 1.559 ms | 2.200 s | 18,792 B | 11,056 B |

The best exact global-MPO controls required 6.254 s and 13.365 s for the same
objective. The selected spatial programs improved it by 3.66x and 6.08x.

The fastest warm spatial programs were:

| workload | fastest spatial program | compile | warm | MAD |
|---|---|---:|---:|---:|
| \(n=8,L=2\) | random-greedy, b2, explicit, u3 | 5.599 s | 0.390 ms | 0.018 ms |
| \(n=12,L=2\) | greedy, b4, explicit, u2 | 10.393 s | 0.704 ms | 0.008 ms |

At eight qubits, the fastest explicit spatial kernel was faster than the best
global-MPO warm kernel in this run (0.390 versus 0.534 ms). At twelve qubits
it remained about 7% slower (0.704 versus 0.655 ms). Cross-run comparisons
with earlier reports are not used as promotion evidence.

## Decision

1. Retain explicit VJP as a measured candidate: it is exact, greatly reduces
   logical tape, commonly reduces compiler temporary memory, appears on both
   Pareto fronts, and wins the twelve-qubit 100-call selection.
2. Do not make explicit VJP the universal default: median warm runtime is
   worse and benefit depends on path, block width, and unroll.
3. Do not use the first static AD score for pruning.
4. Retain differentiated residual and traffic analysis; residual size has a
   repeatable positive relationship with compiler temporary memory.
5. Proceed to exact symmetry compression of recurrent boundaries. Any later
   learned cost model needs more workloads and compiler features rather than
   refitting these two reports.
