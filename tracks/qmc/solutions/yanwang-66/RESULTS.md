# Challenge 66 result record

## Headline

Across the highest verified public artifacts, dynamic reload policies produce
**502 provisional helpful and zero harmful FDR classifications** among 1,960
paired policy-versus-none comparisons. An independent-seed confirmation reaches
the target confidence-interval precision in **32/32 comparisons**.

This is promising evidence for parameter-dependent benefit, not a claim that a
single policy wins everywhere. The registered cell-level stopping rule remains
incomplete, so the deadline disposition is `inconclusive_at_deadline`.

## Discovery Phase 3

| Quantity | Value |
|---|---:|
| Physical groups | 280 |
| Cells | 2,240 |
| Policy-versus-none comparisons | 1,960 |
| Cumulative cell-shots | 179,200,000 |
| Helpful, provisional | 502 |
| No significant difference, provisional | 1,458 |
| Harmful, provisional | 0 |
| Cells meeting the failure target | 81 |
| Lockstep groups completing the target | 4 |

The 20,000-resample paired intervals are corrected across all 1,960
comparisons with Benjamini-Hochberg `q=0.05`. Phase 3 was verified after the
deadline and is reported as a supplement; it does not rewrite the frozen
deadline decision.

## Independent-seed confirmation Phase 5

| Quantity | Value |
|---|---:|
| Headline groups | 8 |
| Cells | 40 |
| Comparisons | 32 |
| Cumulative cell-shots | 12,800,000 |
| Comparisons meeting precision | 32 / 32 |
| Precision fraction | 1.0 (required: 0.8) |
| Cells meeting the failure target | 4 / 40 |

The precision gate is a concrete success: every candidate-versus-none
comparison has reached its registered interval width. The remaining blocker is
the deliberately conservative count of observed logical failures, not unstable
confidence intervals.

## What the result supports

- Active reload deserves parameter-region optimization rather than a blanket
  always/never rule.
- Common-random-number pairing resolves policy differences efficiently.
- A round-level erasure-aware surface-code simulator can be made deterministic,
  causal, restartable and independently auditable on public HPC systems.
- The decoder-ready interface cleanly separates observation history from the
  final logical label.

## Claim boundary

- The study does not identify a universally best reload policy.
- `d=3,5` finite-size data do not establish an asymptotic loss threshold.
- Cost sensitivity was not run because its registered discovery prerequisite
  did not finish.
- The sealed holdout remains unused at `0 / 1`.

The machine-readable source for every number above is `results/summary.json`.
The two result subdirectories contain the verified aggregate Parquet tables,
their original analysis summaries and checksum manifests. The original
`analysis-checksums.sha256` files also name large cluster-only artifacts;
`included-checksums.sha256` provides a directly runnable check for the compact
files committed in this PR.
