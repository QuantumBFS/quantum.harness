# VQETape Direct Tensor-Network Findings

**Date:** 2026-07-28
**Backend:** JAX 0.11.0 CPU on macOS
**Workload:** 3 qubits, 2 RZZ–RX layers, exact TFIM energy and full gradient
**Candidates:** 3 paths × 3 reverse-tape policies = 9

## Methodological Correction

The first attempted run re-searched stochastic paths independently for every
tape policy. That made path and rematerialization effects inseparable and the
run was rejected.

The retained report serializes one explicit contraction list per path strategy
and reuses it for `none`, `all`, and threshold rematerialization policies.
Within each strategy, path FLOPs and largest-intermediate size are therefore
identical across tape policies.

## Correctness

- Valid candidates: **9/9**
- Maximum energy absolute error: below the `complex64` tolerance
- Maximum gradient relative L2 error: below the `complex64` tolerance
- Every candidate computes the full padded parameter gradient.

## Path Results

| Path | FLOPs | Largest intermediate | No-remat JAX temp |
|---|---:|---:|---:|
| `greedy` | 1,048 | 16 elements | 9,988 bytes |
| `auto-hq` | 1,008 | 16 elements | 8,128 bytes |
| `random-greedy` | 1,008 | 16 elements | 8,128 bytes |

The better path reduced compiler-reported temporary memory by:

\[
1-\frac{8128}{9988}\approx 18.6\%.
\]

This supports path-sensitive AD memory behavior even when the largest forward
intermediate is unchanged.

## Fixed-Path Tape Results

| Path | Policy | Remat steps | JAX temp |
|---|---|---:|---:|
| `auto-hq` | none | 0 | 8,128 bytes |
| `auto-hq` | all | 28 | 8,192 bytes |
| `auto-hq` | threshold 64 | 21 | 8,256 bytes |
| `greedy` | none | 0 | 9,988 bytes |
| `greedy` | all | 28 | 9,988 bytes |
| `greedy` | threshold 64 | 19 | 9,924 bytes |

Checkpointing individual pairwise contractions did not produce a meaningful
memory improvement. On the better path it increased compiler temporary memory.
The 64-byte decrease on the greedy threshold candidate is too small to support
a substantive claim.

## Pareto Selection

For \(K=100\), the selected candidate was:

```text
random-greedy + no rematerialization
```

The selected path used 1,008 estimated FLOPs, a largest intermediate of 16
elements, and 8,128 compiler temporary bytes. No joint path-plus-remat
candidate beat the best no-remat path.

## Decision-Gate Audit

| Gate | Result | Evidence |
|---|---|---|
| At least two path metrics | PASS | 1,048 vs 1,008 FLOPs |
| Path changes measured/compiler behavior | PASS | 18.6% JAX temp difference |
| Fixed-path step remat changes memory materially | FAIL | none/all equal or worse; threshold change negligible |
| Joint path/remat gives a new strong Pareto point | FAIL | selected candidate uses no remat |

## Interpretation

The failure is informative. A contraction output is the input of its parent.
Checkpointing only the individual contraction does not necessarily let reverse
mode discard the surrounding subtree state: the checkpointed function still
needs its operands, and those operands may themselves be expensive
intermediates retained by the outer graph.

The next rematerialization unit should therefore be a contraction subtree or
block:

\[
\text{saved subtree boundary}
\longrightarrow
\text{recompute internal contraction sequence during backward}.
\]

The next phase should compare:

1. fixed path with no rematerialization;
2. fixed path with whole-subtree rematerialization;
3. path partitioned into multiple blocks;
4. joint path and block-boundary selection.

CPU process RSS remains dominated by JAX/runtime overhead and is not evidence
of GPU peak-memory behavior.

## Additional Block-Remat Diagnostics

Two coarser exact policies were tested on the fixed greedy path:

| Policy | Remat unit | JAX temp | Compile | Warm median |
|---|---|---:|---:|---:|
| none | none | 9,988 bytes | 16.03 s | 0.365 ms |
| term | one complete Pauli-term contraction | 10,888 bytes | 21.09 s | 0.434 ms |
| objective | complete scalar TFIM objective | 11,332 bytes | 16.76 s | 0.562 ms |

They preserve full-gradient correctness but also fail to reduce
compiler-reported temporary memory at this size. They remain available as
diagnostic policies but are excluded from the default candidate enumeration.

## Contraction-Subtree Checkpoint Diagnostics

The explicit opt_einsum path was reconstructed as a contraction tree. Nodes at
one root-relative depth form an antichain, so each selected node can be treated
as one checkpointed function whose inputs are the original leaf tensors of
that subtree. This is materially coarser than checkpointing one pairwise
contraction.

All three subtree depths preserved the exact energy and full gradient. On the
same fixed greedy path:

| Policy | Checkpointed subtrees | JAX temp | Compile | Warm median |
|---|---:|---:|---:|---:|
| none | 0 | 9,988 bytes | 33.63 s | 0.525 ms |
| subtree depth 0 | 1 | 11,652 bytes | 35.32 s | 0.479 ms |
| subtree depth 1 | 2 | 11,588 bytes | 44.90 s | 0.505 ms |
| subtree depth 2 | 3 | 11,460 bytes | 49.42 s | 0.827 ms |

Whole-subtree rematerialization therefore also fails the decision gate on this
workload. It increases compiler temporary memory by 14.7–16.7% and increases
compilation cost. The depth-0 warm-time change is below the level at which a
single small CPU benchmark can support a speed claim.

The negative result narrows the design: checkpoint granularity cannot be
chosen from the forward contraction tree alone. VQETape needs to inspect the
actual residuals selected by JAX's reverse-mode transform and associate their
bytes with the operations that produce them. Only then can it target the
dominant saved values instead of assuming that forward-tree substructures are
the tape bottleneck.
