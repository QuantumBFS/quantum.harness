# Attempt 44 protocol — search dimension versus black-box cost

Date frozen: 2026-07-29
Parent: `RESEARCH_CHARTER_05.md`
Status: frozen before Attempt-42 outcomes

## Question

What is the smallest model-informed search dimension `k` that reliably reaches
infidelity `1e-3`, and what scalar-query and shot cost does it require relative
to a 40-dimensional search?

## Development benchmark

- The 21 normalized Attempt-35 truth cells.
- Four nested measurement-noise replicates per truth cell.
- Paired seeds across every method/dimension.
- 32768 shots per gradient or validation scalar query.
- Two global-update cycles, central displacement 0.05, trust radius 0.25.
- Scalar black-box boundary and exact accounting from Charter 05.

No fresh truth is opened.

## Search geometries

Evaluate:

- principal-prefix `k = 5, 10, 15`;
- principal-plus-deterministic-complement `k = 20, 40`;
- raw-coordinate-global `k = 40`.

The nominal Hessian eigenvectors are ordered by descending positive curvature.
Their signs are fixed by making the largest-magnitude component positive. The
rank-15 basis is completed deterministically by projecting the ordered raw
coordinate vectors into its orthogonal complement, applying modified
Gram–Schmidt, discarding vectors below norm `1e-10`, and fixing signs by the
same rule. This completion is computed once from the nominal model and cannot
use truth information.

Every principal-family dimension uses:

```text
ridge = 0.1 * median(top-15 positive nominal curvatures).
```

Positive-direction curvatures retain their nominal values. Deterministic
complement directions use zero nominal curvature before adding the common
ridge. Thus changing `k` does not retune regularization.

Raw-coordinate-global is an explicit comparator, not the `k=40`
principal-completed point.

## Frozen caps

Each global run contains two 1024-shot sentinels. Each of two cycles contains
`2k` central-difference queries and two validation queries:

```text
query cap = 4k + 6
shot cap  = 2048 + (4k + 4) * 32768.
```

| k | Query cap | Shot cap |
|---:|---:|---:|
| 5 | 26 | 788480 |
| 10 | 46 | 1443840 |
| 15 | 66 | 2099200 |
| 20 | 86 | 2754560 |
| 40 | 166 | 5376000 |

All costs are checked against the black-box service ledger.

## Cost semantics

Three cost measures remain separate:

1. **full-cap online:** actual executable method cost when no online certificate
   is used;
2. **certified online:** cost at the first candidate passing the frozen
   Attempt-43 certificate;
3. **oracle-scored first hit:** post-hoc hidden-exact diagnostic.

The headline uses certified online cost only if Attempt 43 passes its gates.
Otherwise it uses full-cap online cost. Oracle-scored first-hit points may be
shown in a visibly separate supplementary panel.

Failed runs receive the applicable full cap. Warm successes cost zero only if
the warm state itself receives the same counted online certification required
of later candidates; otherwise warm success is post-hoc only.

## Independent unit and intervals

- Average nested replicates within each truth cell.
- Use a stratified truth-cell bootstrap with frozen seed 113044 and 20000
  draws.
- Plot 95% intervals for success, queries, and shots.
- Preserve per-family estimates; pooled estimates are stratified by family.

## Dimension-selection gate

Select the smallest `k` satisfying:

- absolute success at least 75%;
- `LCB95(success_k - success_40) > -0.10`;
- destructive accepted-step rate at most 5%; and
- for a resource-advantage claim,
  `UCB95(cost_k / cost_40) < 0.60`.

`k=20` or `k=40` replaces `k=15` only if its success is at least ten percentage
points higher or it passes a safety gate that `k=15` fails.

## Required outputs

- machine-readable per-run ledger and truth-level summary;
- search-dimension versus scalar-query headline with 95% error bars;
- search-dimension versus shot-cost headline with 95% error bars;
- success-versus-dimension panel;
- raw-coordinate comparator;
- selected-dimension gate decision;
- clear development and cost-semantics labels.

