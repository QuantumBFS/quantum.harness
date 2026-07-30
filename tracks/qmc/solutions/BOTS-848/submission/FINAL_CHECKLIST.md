# BOTS:848 Challenge #15 final submission checklist

This checklist separates repository preparation from the external GitHub
submission action. Do not create a new pull request.

## Repository package

- [x] Solution is under `tracks/qmc/solutions/BOTS-848/`.
- [x] `SUBMISSION.md` maps every issue #15 deliverable to evidence.
- [x] Benchmark v0 has a clean-checkout command and pinned minimal dependencies.
- [x] The GPU Slurm runner records revision, clean status, device, tests,
  machine-readable output, and SHA-256 hashes.
- [x] Route D+ passing certificates and its non-passing optimization diagnosis
  are clearly separated from the Benchmark v0 acceptance claim.
- [x] Generated bulk results remain under `tracks/qmc/results/` or the remote
  run directory and are not committed.
- [x] The portable result summary and small immutable evidence certificates are
  committed under `submission/`.
- [x] `/challenge-report` material is rendered as a standalone offline page at
  `tracks/qmc/results/BOTS-848-benchmark-v0-final/report.html` with SHA-256
  `cb97ce0b030d79d7a696a9e200b2e20d08166355ad518c445bd34001416d5501`.

## Official competition handoff

- [ ] Update the existing registration PR
  [`QuantumBFS/quantum.harness#226`](https://github.com/QuantumBFS/quantum.harness/pull/226);
  do not open a third Challenge #15 PR.
- [ ] Move the final solution commits from the bhjia fork branch into PR #226's
  head branch, `TensorSpicyJ:challenge/qmc-chiral-graviton`.
- [ ] Replace the registration-only PR body with `submission/PR_BODY.md`.
- [ ] Confirm the PR diff contains the complete
  `tracks/qmc/solutions/BOTS-848/` package rather than only the registration
  README.
- [ ] Surface the already rendered challenge report in the final PR review
  handoff without committing the gitignored bulk result directory.
- [ ] Confirm PR #226 is ready for review, mergeable, and no longer changing.
- [ ] Treat the earlier duplicate PR #179 as non-canonical; do not split final
  commits between #179 and #226.

## Claim boundary

- Benchmark v0 is the minimum-acceptance result.
- Route D+ is a documented scalable research implementation with certified
  algebra/backend stages and an optimization-failure diagnosis.
- Do not claim a passing scalable D+0 result, thermodynamic extrapolation,
  chirality decomposition, or beyond-ED production result.
