## Team

| | |
|---|---|
| **Team name** | Do you like Tadej Pogacar? |
| **Members** | Jiansen Zhang, Zimiao Zhang, Jize Xu |

## Challenge

| Row | |
|---|---|
| **Challenge** | Reproduce the Track B validation floor for published long-range transverse-field Ising critical fields using finite-system DMRG, exact anchors, and explicit finite-size, bond-dimension, and MPO error audits. |
| **Catalog issue** | Addresses #86 — “Where does long-range universality end? Three adversarial tests of the σ*=7/4 vs 2 dispute,” released by Kun Chen, Institute of Theoretical Physics, Chinese Academy of Sciences. |
| **Track** | `tracks/mps/` — Track B, DMRG critical-point validation with sparse ED and the nearest-neighbour chain as anchors. |

## Scientific status

This submission is a **pipeline validation / finite-size preliminary result** for the two published Track B validation-floor anchors.

| σ | finite-size estimate | published Γc | largest bracket | preceding-round movement |
|---:|---:|---:|---:|---:|
| 1.75 | 1.5621218 ± 0.0041452 | 1.5609 ± 0.0003 | 0.005 | 1.52e-4 |
| 2.0 | 1.4220052 ± 0.0038822 | 1.4208 ± 0.0002 | 0.005 | 1.48e-4 |

Both conservative intervals cover the published anchors. The bracket-width gate of 1e-3, adjacent-round movement gate of 1e-4, and the normalized-variance audit remain open, so this PR does not claim a formal reproduction or the complete universality boundary.

## What changed

- Implements the periodic Hurwitz-ζ image-summed long-range TFIM and audited SOE-MPO construction.
- Adds sparse ED, nearest-neighbour, MPO-pole, bond-dimension, finite-size, and convergence diagnostics.
- Adds recoverable per-cell Slurm execution with atomic manifests and bounded packed workers.
- Makes quality-first analysis prefer results that pass both variance and residual gates.
- Restricts same-parameter strict retries to residual failures; variance-only failures are recorded in `deferred_quality.csv`.
- Emits small manual crossing recommendations with `automatic_submission=false`; no L=128 or χ=256 expansion is scheduled in this closeout.
- Publishes compact sanitized partial58 evidence and a self-contained offline report.

## Execution evidence

- Follow-up: 58/69 successful manifests, split as A 54/65 and B 4/4.
- Strict χ=64 retries: residual 38/38 pass; normalized variance 0/38 pass.
- Adaptive χ=128 points: 4/4 pass both quality gates.
- Three jobs reached TIMEOUT and one wrapper launch failed because `HARNESS_RUN_SPEC` was missing; no OOM or independent Julia error was observed.

## Verification

- Julia Issue 86 suite: 136/136 passed.
- Quality-first analyzer selection: 8/8 passed.
- Follow-up generator: 33/33 passed.
- Finalizer: 41/41 passed.
- Python Slurm tests: 8/8 passed, including twenty consecutive failed-cell concurrency stress rounds.
- JSON/report integrity, SHA-256, sensitive-information, and `git diff --check` audits passed.

## Report and data

- [Offline Challenge Report](report.html)
- [Evidence README](README.md)
- [Validation summary](validation_summary.json)
- [Formal summary](formal_summary.json)

The public evidence contains the compact merged rows, summaries, crossings, figures, recommendation specs, and report. Full manifests and scheduler logs remain in a separately checksummed handback and are excluded from Git.

Long-range z, γ/ν, σ=1.6, and σ=1.8 remain future work.
