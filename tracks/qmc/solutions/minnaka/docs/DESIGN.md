# Submission design: practical ergodicity breaking in CP-AFQMC

## Objective

Turn the completed 2x2 exhaustive audit and 4x4 PQMC-to-CP path study into a
reviewable challenge submission.  The submission must make two contributions
clear:

1. it gives configuration-level evidence for practical ergodicity breaking in
   a sign-problem-free CP-AFQMC calculation; and
2. it proposes a way to remove this failure mode by constructing trial states
   with no nodes, or a large positive overlap margin, on the dynamically
   reachable walker set, including a rigorous special-GHF example.

The public report intentionally omits Green-function stability diagnostics and
the earlier 0.01 precision target.  They are implementation-level checks and do
not change the physical conclusion; the achieved direct-reweighting uncertainty
already resolves the UHF-CP bias.

## Scientific claim boundary

The numerical claim is **practical**, not topological: every replayed path has
positive physical weight and nonzero CP proposal probability, yet some
physically important paths are suppressed so strongly that a finite walker
population is effectively unable to visit them.  The evidence does not by
itself prove that the full positive-overlap Slater manifold has disconnected
components.

The mechanism is a product of many conditional probabilities.  If a path
requires choices with probabilities `q_1,...,q_K`, then

```text
Q_CP(X) = product_k q_k .
```

Repeated near-node encounters therefore produce an exponentially small path
probability even when no individual step reaches an exact node.

The strict constructive result is restricted to the half-filled bipartite
Hubbard model and its symmetry-paired reachable sector.  After a partial
particle-hole transformation, the spin-HS walker becomes a paired walker with
the same orbital matrix in the two spin sectors.  The special transverse GHF
trial becomes a number-projected singlet BCS state with a real positive-definite
pair matrix `F`.  Its overlap is

```text
<Psi_GHF|phi> = det(Phi^T F Phi) > 0
```

for every full-rank reachable `Phi`.  This proves the absence of trial-overlap
nodes on that reachable sector.  It does not assert a globally node-free real
state on the complete oriented Slater manifold.

## Evidence chain

1. **2x2 exhaustive enumeration.**  Compare physical path weight with CP
   under-sampling over all paths for RHF/UHF trials.  Important paths with
   under-sampling scores of many orders of magnitude establish that the
   mismatch is not confined to negligible-weight tails.
2. **4x4 PQMC path audit.**  Use sign-free PQMC to draw paths from the physical
   distribution, then replay each path under the UHF/spin-HS CP proposal.
   Eight of the ten worst-efficiency paths have physical weights above the
   sample median.
3. **Long-path mechanism.**  The centered log sampling efficiency is strongly
   anticorrelated with the prefix barrier (Spearman rho = -0.933).  Detailed
   heat-bath traces show many more low-probability choices, rather than one
   dominant zero-probability event.
4. **Observable consequence.**  Direct UHF-CP gives an energy near -13.47,
   while direct reweighting of 96,000 PQMC paths gives
   `-13.6155 +/- 0.0140`, consistent with the exact `-13.62192` and clearly
   separated from the UHF-CP result.

## Public artifacts

```text
tracks/qmc/solutions/minnaka/
|-- README.md                 concise reviewer entry point
|-- REPORT.md                 paper-style scientific narrative
|-- REPRODUCE.md              exact local and cluster commands
|-- EXECUTION_REPORT.md       run inventory and measured outputs
|-- figures/                  three curated PDF/PNG figure pairs
|-- data/                     compact machine-readable evidence
|-- docs/                     design and implementation plan
|-- scripts/                  report-figure generation and checks
`-- test/                     tracked source snapshot of the completed workflow
```

Large Markov-chain archives, build trees, and raw cluster logs are excluded.
The compact CSV/JSON evidence and source code needed to verify the published
numbers are included.

## Report structure

1. Abstract
2. Challenge and significance
3. From Slater-space visualization to path-space diagnostics
4. Mathematical mechanism of cumulative near-node suppression
5. 2x2 exhaustive evidence
6. 4x4 PQMC-to-CP evidence
7. Direct-reweighting energy test
8. Proposed resolution and the strict GHF construction
9. Scope, limitations, and next steps
10. Reproducibility and references

The three figures are used as a sequential argument: exhaustive mismatch,
important 4x4 paths with low CP efficiency, and the prefix-barrier mechanism.
