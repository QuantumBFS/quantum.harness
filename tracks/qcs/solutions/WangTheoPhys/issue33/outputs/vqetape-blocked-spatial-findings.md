# VQETape Blocked Spatial-Transfer Findings

## Experimental contract

This phase replaces the repeated one-site spatial transition with an exact
multi-site block:

\[
B_{q+1}
=
F^{(b)}
\left(
B_q;
\theta_{qb},\ldots,\theta_{qb+b-1}
\right).
\]

The incoming carry participates in the block contraction path, and the only
block output is the outgoing boundary. The exact boundary remains

\[
D=3\cdot4^L.
\]

The search compared block widths one through four. For each width and path
strategy, first, repeated block, optional tail, and last paths were searched
once, serialized, and reused across default and rematerialized adjoints and
all applicable unroll values. The already negative segmented schedule was
retained for width one; blocked segmented execution is implemented and tested
but was not multiplied across the default search.

Raw reports:

- [eight-qubit report](vqetape-blocked-spatial-report-n8-d2.json)
- [twelve-qubit report](vqetape-blocked-spatial-report-n12-d2.json)

Both experiments used `complex64`, a 2 GiB process-memory budget, five
synchronized warm calls, and a 100-call VQE horizon. Every candidate executed
in a fresh process.

## Correctness

All measured candidates were valid:

| Workload | Total candidates | Spatial candidates | Valid | Maximum energy error | Maximum relative gradient error |
|---|---:|---:|---:|---:|---:|
| \(n=8,L=2\) | 60 | 57 | 60 | \(8.58\times10^{-6}\) | \(1.68\times10^{-6}\) |
| \(n=12,L=2\) | 72 | 69 | 72 | \(7.63\times10^{-6}\) | \(4.46\times10^{-6}\) |

The errors remain within the configured complex64 tolerances. Unit tests also
cover every interior remainder, full energy and gradient equality with the
width-one program, rematerialized blocks, blocked segmented VJPs, rolled
control flow, and the unused padded RZZ gradient.

## Best measured envelope by block width

Different candidates may attain the compile, warm, and temporary-memory
columns. These tables describe the measured representation envelope rather
than one executable.

### \(n=8,L=2\)

| Block width | Spatial candidates | Best compile (s) | Best warm (µs) | Best compiler temp (B) | Best 100-call objective (s) |
|---:|---:|---:|---:|---:|---:|
| 1 | 21 | 1.873 | 596.17 | 11,656 | 1.949 |
| 2 | 18 | 2.415 | 562.96 | 14,480 | 2.472 |
| 3 | 12 | 3.341 | 642.00 | 19,160 | 3.432 |
| 4 | 6 | 2.681 | 565.42 | 27,224 | 2.737 |

Width two reduced the within-run best spatial warm time by 5.6% relative to
width one. Its extra compile cost prevented it from winning the 100-call
objective.

The horizon-selected candidate was width-one `auto-hq/default/u2`:

| Compile (s) | Warm (µs) | Compiler temp (B) | RSS (MiB) | Logical tape (B) | 100-call cost (s) |
|---:|---:|---:|---:|---:|---:|
| 1.874 | 753.79 | 32,800 | 282.08 | 22,880 | 1.949 |

The horizon-optimal global-MPO control cost 4.466 s, so the selected spatial
program retained a 2.29x compile-plus-100-call advantage in this run.

### \(n=12,L=2\)

| Block width | Spatial candidates | Best compile (s) | Best warm (µs) | Best compiler temp (B) | Best 100-call objective (s) |
|---:|---:|---:|---:|---:|---:|
| 1 | 21 | 1.702 | 816.50 | 12,872 | 1.784 |
| 2 | 18 | 2.580 | 780.79 | 15,568 | 2.694 |
| 3 | 18 | 2.327 | 674.96 | 20,440 | 2.433 |
| 4 | 12 | 7.301 | 1,187.00 | 27,808 | 7.501 |

Width three reduced the within-run best spatial warm time by 17.3% relative
to width one:

\[
\frac{816.50-674.96}{816.50}=17.3\%.
\]

The best width-three warm executable was `auto-hq/default/u3`. It compiled in
5.411 s, ran in 674.96 microseconds, used 40,472 compiler temporary bytes, and
retained a 38,432-byte logical tape. It is a throughput candidate, not the
100-call winner.

The horizon-selected candidate remained width-one `auto-hq/default/u1`:

| Compile (s) | Warm (µs) | Compiler temp (B) | RSS (MiB) | Logical tape (B) | 100-call cost (s) |
|---:|---:|---:|---:|---:|---:|
| 1.702 | 817.25 | 42,208 | 259.27 | 35,936 | 1.784 |

The horizon-optimal global-MPO control cost 19.652 s in the same run, so the
selected spatial program retained an 11.02x objective advantage. The absolute
global and spatial warm values differed noticeably from the earlier
three-repeat report; CPU scheduling and process noise therefore make
cross-run microsecond comparisons inappropriate. Block-width comparisons
above use candidates from the same fresh-process search.

## Decision-gate audit

| Gate | Result | Evidence |
|---|---|---|
| Exact multi-site energy and full gradient | Pass | 126/126 measured spatial candidates valid across both reports; structural tests also cover tails and complex program shapes |
| Rolled blocked execution | Pass | Width-two value-and-gradient StableHLO contains `while` |
| No full transfer-matrix output | Pass | Every block emits the \(D\)-element outgoing boundary; planner tests reject \(D^2\) output construction |
| Fair path comparison | Pass | Paths are serialized once per strategy and block width and reused across AD/unroll candidates |
| Warm improvement | Partial | 5.6% at \(n=8\), 17.3% at \(n=12\); the predeclared 20% target was not reached |
| 100-call default promotion | Reject | Width one remains the horizon-selected program on both workloads |
| Research-candidate retention | Pass | Width-two and width-three programs appear on measured Pareto fronts and provide lower warm time in the corresponding workload |

## Interpretation

The experiment supports three conclusions.

First, true multi-site contraction is not equivalent to merely increasing
`scan.unroll`. It changes the local tensor network and can reduce warm
value-and-gradient time, with the benefit increasing from 5.6% to 17.3%
between the two audited chain lengths.

Second, larger blocks expose a compile-versus-throughput trade-off. The path
that wins warm time is not the path that minimizes

\[
T_{\mathrm{compile}}+100T_{\mathrm{warm}}.
\]

Forward-only path quality and block width are therefore insufficient
selection features.

Third, width four is already beyond the useful CPU region for the tested
depth. Its local graph raises compile time and temporary memory without a
reliable throughput gain. Future searches should statically prune such
candidates rather than compile the full Cartesian product.

## Decision

Blocked execution is retained as an exact, user-selectable candidate axis, but
the default remains width one for the current 100-call CPU contract.

The next phase advances to differentiation-aware contraction analysis. Its
immediate goals are:

1. predict forward and reverse contraction work separately;
2. estimate saved residual liveness and tensor traffic;
3. rank block paths before fresh-process compilation;
4. search a separate explicit block VJP path;
5. determine whether the width-three throughput gain can be obtained with
   lower compile and residual cost.

## Regression evidence

Before the measured runs, the complete repository suite passed:

```text
246 passed, 6 skipped in 1279.25s (0:21:19)
```

The six skips are the parametrized cases where the requested block width is
larger than the number of interior sites.

## Limitations

The results use the local CPU JAX backend. Process RSS is noisy and is not a
GPU peak-memory measurement. The experiment covers one shallow, local,
one-dimensional TFIM ansatz. Exact boundary dimension remains exponential in
depth, and the results do not imply efficient generic VQE simulation.
