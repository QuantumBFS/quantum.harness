# Final N3 Easy Goal Audit

The legacy directory contains three hash-linked published rounds. Round 4 is
hash-linked to Round 3 but is archived because all four used code whose raw
two-sample patch-TV statistic made the frozen 0.02 excess-TV gate unreachable,
and whose classifier ignored scientific gates. The implementation defect is
documented in `tracks/mps/DMRG/docs/progress/ISSUE28_N3_INVALID_GATE_20260730.md`.

The archived Round 4 did not intentionally change the registered physical
protocol, and it does reference the Round 3 manifest. A valid Round 3
checkpoint exists. Nevertheless, continuing that old chain cannot establish
formal success: the gate semantics and code hash changed, previous operator
bounds failed, and formal N3 requires five corrected gate-passing rounds in a
new immutable directory. Round 4 must not be forced into the valid chain.

The corrected run has one complete published round (`SCIENTIFIC_NEGATIVE`) and
an interrupted unpublished Round 2 staging directory. Round 2 completed 1,000
updates with `NOT_CONVERGED`; validation failed with operator-equivalence upper
bound 0.212841 and excess patch-TV upper bound 0.238629. A staging directory is
not a round and has no legal child checkpoint for formal continuation.

| Historical round | Operator bound | Patch-TV value | 0.02 distance | Status |
|---|---:|---:|---:|---|
| 1 | 0.258610 | 0.313538 | +0.238610 / +0.293538 | invalid-gate history |
| 2 | 0.212841 | 0.301902 | +0.192841 / +0.281902 | invalid-gate history |
| 3 | 0.077681 | 0.137724 | +0.057681 / +0.117724 | invalid-gate history |
| 4 archived | 0.026534 | 0.094025 | +0.006534 / +0.074025 | not countable |

The operator bound improved monotonically in the legacy chain, but patch-TV
did not approach 0.02 closely enough and its statistic was invalid for the
declared gate. This trend is descriptive only. Historical walltimes were about
0.9, 6.3, 6.8 and 16.9 h, with eight local/Slurm workers and sub-GiB memory.
No short, protocol-preserving continuation can complete all remaining gates
before the deadline. Do not launch N3/N4/N5 now.

Final classification: `PROTOCOL_INCOMPLETE`, with direct supporting evidence
of `OPTIMIZATION_NOT_CONVERGED` and frozen `VALIDATION_FAILED`.
