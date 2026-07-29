# Issue 86 Track B partial58 evidence

This directory contains the compact, sanitized public evidence for the
finite-size preliminary closeout. The complete raw manifests and scheduler
logs remain in the separately checksummed handback.

## Scope and status

- Scientific label: `pipeline validation / finite-size preliminary result`.
- Merged rows: 172 from Stage 1, Stage 2 first pass, the L16 correction, and
  the follow-up run.
- Follow-up completion: 58/69 manifests, split as A 54/65 and B 4/4.
- Strict `chi=64` retries: 38/38 pass the residual gate and 0/38 pass the
  normalized-variance gate.
- Adaptive `chi=128` points: 4/4 pass both quality gates.
- Remaining work: nine strict retries and two `L=8` adaptive cells.

Both published critical-field intervals are covered by the current
finite-size estimates. The largest crossing brackets retain width `0.005`,
above the formal `0.001` gate, and their movement from the preceding analysis
round is also above `1e-4`. The status therefore remains preliminary.

## Key outputs

- [`report.html`](report.html): self-contained offline challenge report.
- [`validation_summary.json`](validation_summary.json): numerical gates,
  scientific scope, and execution evidence.
- [`formal_summary.json`](formal_summary.json): crossing fits, uncertainty
  components, NN audit, and all convergence failures.
- [`deferred_quality.csv`](deferred_quality.csv): 55 finite-`chi` quality
  limitations that already pass the residual gate.
- [`next-recommendations.json`](next-recommendations.json): four largest-pair
  midpoint candidates and eight manual `chi=128` endpoint checks.

Every recommendation has `automatic_submission=false`. The `L=128` and
`chi=256` specifications are intentionally empty for this closeout.

## Provenance and verification

- Compute commit:
  `486b2673baa11d44a1048fbf9fd36751189889d7`.
- Analysis-tool commit:
  `3e31a89a85ec0f8ba729d840b8677f182d59228e`.
- Canonical analyzer SHA-256:
  `966a151cdb09483f656f91ca087044a4c5830c29c0bef42b2f5f6c210c7828e7`.
- Julia Issue 86 suite: 136/136 passed.
- Quality-first analyzer selection: 8/8 passed.
- Follow-up generator: 33/33 passed.
- Finalizer: 41/41 passed.
- Python Slurm tests: 8/8 passed, including twenty consecutive failed-cell
  concurrency stress rounds.

The full Track B universality boundary still requires long-range `z`,
`gamma/nu`, and the `sigma=1.6` and `sigma=1.8` rows.
