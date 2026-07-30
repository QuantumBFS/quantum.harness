# Diagnosing and removing practical ergodicity breaking in CP-AFQMC

**Result.** In a half-filled Hubbard model with no sign problem, physically
important auxiliary-field paths can remain formally reachable but be suppressed
by more than a thousand natural-log units under a UHF-guided constrained-path
(CP) proposal.  The suppression is caused primarily by the product of many low
conditional probabilities along a long path, not by one absolute node.

This submission addresses [challenge #90](https://github.com/QuantumBFS/quantum.harness/issues/90)
with three contributions:

1. an exhaustive 2x2 path-space audit and a 4x4 PQMC-to-CP replay that expose
   important paths missed in practice by CP;
2. a trajectory-level **prefix barrier** diagnostic that identifies repeated
   near-node encounters as the dominant mechanism; and
3. a proposed resolution: optimize the trial state to have a positive overlap
   margin on the dynamically reachable walker set.  We rigorously prove that a
   special transverse GHF trial is one such construction for the half-filled
   bipartite model.

## Main evidence

| Quantity | Result |
|---|---:|
| Exact 2x2 paths enumerated per trial | 16,777,216 |
| UHF worst-efficiency paths with physical weight at least the mean | 799 |
| 4x4 worst-efficiency paths above the median physical weight | 8 of 10 |
| Efficiency–prefix-barrier Spearman correlation | −0.933 |
| Direct UHF-CP energy | −13.4683(31) |
| Directly reweighted PQMC-path energy | −13.6155(140) |
| Exact 4x4 energy | −13.62192 |

The 96,000-path direct ratio-of-sums estimate is consistent with the exact
energy and differs clearly from direct UHF-CP.  All reweighting factors are
positive, with effective sample size 95,727.

## Read the submission

- [Scientific report](REPORT.md)
- [Execution report](EXECUTION_REPORT.md)
- [Reproduction instructions](REPRODUCE.md)
- [Compact machine-readable evidence](data/README.md)
- [Implementation source and tests](test/)

The report uses three figures in sequence: exhaustive 2x2 mismatch, important
4x4 PQMC paths with vanishingly small CP efficiency, and the cumulative prefix
barrier responsible for that suppression.

## Team

| | |
|---|---|
| Team | `minnaka` |
| Member | Mingzhong Lu |
| Track | Quantum Monte Carlo |
| Challenge lead | Mingpu Qin |
