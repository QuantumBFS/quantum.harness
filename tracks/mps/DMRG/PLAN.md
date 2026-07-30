# Issue #28 Pure-Neural VMCRG Easy Goal Plan

> **Canonical challenge plan.** The previous MPS-residual plan is preserved at
> [`docs/superpowers/plans/2026-07-28-mps-vmcrg-optional-comparison.md`](docs/superpowers/plans/2026-07-28-mps-vmcrg-optional-comparison.md)
> as an optional comparison and does not contribute to Issue #28 success.

## Durable Documents

- Design: [`docs/superpowers/specs/2026-07-28-issue28-pure-neural-vmcrg-design.md`](docs/superpowers/specs/2026-07-28-issue28-pure-neural-vmcrg-design.md)
- Detailed TDD implementation plan: [`docs/superpowers/plans/2026-07-28-issue28-pure-neural-vmcrg.md`](docs/superpowers/plans/2026-07-28-issue28-pure-neural-vmcrg.md)
- Local N3/N4 deviation design: [`docs/superpowers/specs/2026-07-28-issue28-local-execution-deviation-design.md`](docs/superpowers/specs/2026-07-28-issue28-local-execution-deviation-design.md)
- Local N3/N4 implementation plan: [`docs/superpowers/plans/2026-07-28-issue28-local-execution.md`](docs/superpowers/plans/2026-07-28-issue28-local-execution.md)
- Invalid N3 gate incident and preserved evidence: [`docs/progress/ISSUE28_N3_INVALID_GATE_20260730.md`](docs/progress/ISSUE28_N3_INVALID_GATE_20260730.md)
- Official challenge: QuantumBFS/quantum.harness Issue #28

## Goal

Strictly complete the two-dimensional Easy Goal using a pure neural network
to represent renormalized Hamiltonians in VMCRG:

- periodic 45 x 45 Ising model;
- `K = 0.436`;
- non-overlapping 3 x 3 majority blocking;
- radius-3, hidden-32, multiscale D4/Z2/translation-symmetric MLP;
- exact all-zero 13-operator branch in every pure-neural run;
- five preregistered formal seed bundles;
- at least five consecutive neural-to-neural RG rounds per successful seed;
- paired comparison with unbiased and traditional 13-operator VMCRG;
- formal large compute through the user-authorized, fail-closed local execution
  deviation with bounded workers and `2 + 2 + 1` seed-bundle waves; Slurm is
  retained only as a fallback;
- Simplified-Chinese CLI, progress, plots, and final HTML report.

The 45 x 45 x 45 three-dimensional spin-glass Hard Goal is deferred until
the full two-dimensional workflow and evidence are complete.

## Current Verified Baseline

- Existing test suite before this implementation: `142 passed`.
- Traditional Ising/VMCRG, 13 even operators, local deltas, Table-I workflow,
  and autocorrelation diagnostics exist.
- Pure neural D4/Z2/translation-symmetric MLP, analytic gradients, local
  cache, validation, projection, ablation, and Robbins-Monro stability pilot
  exist.
- Existing one-round pure-neural formal attempts flatten the distribution but
  miss the frozen 13-projection diagnostic; they are baseline evidence, not
  Easy Goal success.
- Neural-to-neural microscopic Hamiltonians, exact N0 oracle, locked BAR
  objectives, paired five-round orchestration, and fail-closed neural resume
  remain to be implemented.

## Non-Negotiable Contracts

1. `V_theta = sum_r f_theta(P_r mu)` is a total energy.
2. Training/reporting objectives are normalized once per applicable site.
3. Every handoff is `U_next = -V_frozen`.
4. All model comparisons use one hashed independent gauge-reference set.
5. Formal objective differences use a common zero-bias anchor and frozen BAR
   bridges with explicit overlap gates.
6. Formal training uses literal `eta_t = eta_0 (t + t_0)^(-p)`, gradient
   clipping, Polyak averaging, and multi-condition stopping.
7. Neural/traditional arms share paired initial configurations and budgets,
   not mutable RNG state.
8. Formal seed count remains five after formal execution begins.
9. Correctness and protocol failures block dependent compute; scientific
   negatives continue to N5 reporting.
10. MPS code/results remain optional evidence and never enter success gates.

## Stage Dependency Graph

```text
B0 Traditional VMCRG baseline certification
  -> N0 exact blocking/objective/gradient oracle
  -> N1 random-initialization identity certification
  -> N2 one-round 45 x 45 pure-neural RG
  -> N3 neural-to-neural five-round pilot + variance/resource estimate
  -> freeze immutable formal protocol
  -> N4 five paired seeds x five dependent rounds
  -> N5 paired analysis, classification, figures, and report
```

## Stage Gates

### B0 Traditional Baseline

- [ ] Canonical 13-operator basis hash, signs, coordinates, D4 instances, and
      normalization pass.
- [ ] Traditional local deltas match full recomputation.
- [ ] Variational convergence and all frozen target moments pass.
- [ ] Principal couplings agree with verified paper-baseline evidence.
- [ ] `U_next = -V_frozen` handoff passes the common gauge check.
- [ ] Traditional bias improves autocorrelation versus unbiased Metropolis.

### N0 Exact Oracle

- [ ] Periodic 3 x 6, b=3 exact enumeration covers all `2^18` states.
- [ ] Exact coarse distribution, target distances, objective, and sign checks
      pass.
- [ ] Small square identity oracle agrees across JAX, analytic, finite-
      difference, exact, and Monte Carlo gradients.
- [ ] Every local delta agrees with direct total-energy recomputation.

### N1 Identity Certification

- [ ] Random initialization only; no supervised formal checkpoint.
- [ ] Explicit Robbins-Monro and monitoring protocol passes three formal
      identity seeds.
- [ ] Frozen distribution, exact relation, projection, and gradient-oracle
      diagnostics pass.

### N2 One Round

- [ ] L=45, K=0.436, b=3 pure-neural training passes correctness and frozen
      distribution gates.
- [ ] Held-out objective is identifiable and improves over zero bias.
- [ ] Candidate-26 and 13 projections are reported as diagnostics.
- [ ] Frozen model produces a verified neural microscopic checkpoint.

### N3 Five-Round Pilot

- [ ] One disjoint pilot bundle completes five neural-to-neural rounds.
- [ ] Hash-linked manifests and resume behavior pass.
- [ ] Wall, memory, output, variance, and fixed-five-seed power estimates are
      recorded.
- [ ] BAR ladders, training thresholds, resources, and seed bundles freeze
      byte-stably into `config/issue28_formal_v1.json`.

### N4 Formal Experiment

- [ ] Exactly five paired formal bundles run or receive explicit failure
      classifications.
- [ ] Each successful bundle completes five dependent rounds.
- [ ] Neural, linear, and unbiased arms use matched budgets/hardware.
- [ ] No seed replacement, threshold change, or result-dependent extension.

### N5 Analysis and Report

- [ ] Five-round paired representation endpoint and BAR overlap are reported.
- [ ] Neural tau is significantly better than unbiased and non-inferior to
      linear with upper ratio bound 1.10.
- [ ] Neural ESS/s is better than unbiased and non-inferior to linear with
      lower ratio bound 0.90.
- [ ] At least four of five seed effects point in every claimed direction.
- [ ] Every figure has exact source CSV/JSON.
- [ ] Final classification is one of `CORRECTNESS_FAILURE`,
      `PROTOCOL_FAILURE`, `SCIENTIFIC_NEGATIVE`, or `EASY_GOAL_SUCCESS`.
- [ ] Consolidated runnable script and self-contained HTML report exist.

## Implementation Work Packages

- [ ] 1. Shared atomic artifacts and hashes.
- [ ] 2. Immutable protocol, operator hash, gauge set, and paired seed bundles.
- [ ] 3. B0 traditional certification.
- [ ] 4. N0 exact 3 x 6 blocking oracle.
- [ ] 5. N0 JAX automatic-differentiation oracle.
- [ ] 6. Frozen BAR held-out objective estimator.
- [ ] 7. Literal Robbins-Monro schedule and multi-gate stopping.
- [ ] 8. Pure-neural fail-closed checkpoints.
- [ ] 9. Neural microscopic Hamiltonian and dual-cache sampler.
- [ ] 10. Stage manifests, dependencies, and terminal classifications.
- [ ] 11. N1 identity certification runner.
- [ ] 12. N2 one-round runner.
- [ ] 13. N3 five-round/resource/power pilot.
- [ ] 14. Immutable formal-protocol freezer.
- [ ] 15. N4 paired formal orchestration.
- [ ] 16. Unified `reproduce.py issue28-easy` entry.
- [ ] 17. Profile-driven Slurm jobs and monitoring.
- [ ] 18. N5 paired analysis, figures, and report.
- [ ] 19. Documentation, generated-cache cleanup, and final verification.

Each work package follows the exact tests, interfaces, commands, and commit
boundaries in the detailed implementation plan.

## Compute Policy

- The user explicitly authorized a local deviation for N3 and N4 after the
  qdeshell pilot remained pending. This changes execution location only; no
  physical, neural, statistical, seed, or success-gate setting changes.
- N3 runs alone with eight Issue #28 workers. Large local execution requires
  `--backend local --allow-large-local --workers 8`.
- N4 runs the immutable five bundles in `2 + 2 + 1` waves, with at most two
  bundle subprocesses and eight Issue #28 workers per subprocess. When
  available memory is below 12 GiB, concurrency falls to one.
- BLAS, OpenMP, and Numba nested thread pools are capped to the same per-bundle
  budget. Every local manifest records `LOCAL_COMPUTE_DEVIATION` and measured
  host provenance.
- Slurm remains a fallback only. Pending job `5311997` is cancelled after the
  full test suite and small-lattice local preflight pass, immediately before
  launching N3, so the disjoint pilot seed cannot execute twice.
- Final acceptance still depends on verified manifests and classifications,
  never on a local process exit code alone.

## Cleanup Boundary

Preserve all historical paper, neural, MPS, LTRG, protocol, and compact result
evidence. Remove only generated `__pycache__`, `.pytest_cache`, Numba caches,
duplicated generated HTML, and obsolete duplicate plan text after the
canonical replacements verify. Never delete historical outputs merely because
they did not pass a scientific gate.

## Completion Rule

Implementation completion and scientific Easy Goal success are distinct.
Code is complete when all local tests, fresh-checkout entry smoke, fail-closed
contracts, and Slurm workflow are verified. `EASY_GOAL_SUCCESS` additionally
requires the complete five-seed/five-round formal evidence to pass every
frozen representation and sampling gate. Otherwise the final report states
the exact correctness, protocol, or scientific-negative result.
