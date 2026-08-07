# Dynamic Atom-Reload Policies for Surface-Code Memory

Status: readable deadline report, `inconclusive_at_deadline`. Every numerical
result below is from a checksum-verified, atomically published public artifact.
The registered stopping rules did not finish by the deadline, so no reload
policy is claimed superior and no sealed holdout result is reported.

## Interim Result

The implementation and validation pipeline is complete enough to run the
registered experiment, but the scientific stopping rules have not yet
finished. Accepted discovery evidence through Phase 2 contains 89,600,000
cell-shots over all 2,240 cells. Only 27 cells reached the registered logical-
failure target, so all 280 paired physical groups continued. The resulting 436
`helpful` and 1,524 `no_significant_difference` classifications are explicitly
provisional.

The independent-seed headline confirmation is accepted through Phase 5, with
12,800,000 cell-shots and 320,000 shots per cell. All 32 policy-versus-none
comparisons meet the registered precision rule, but only 4 of 40 cells have
reached 1,000 logical failures. The other 36 cells and all eight lockstep
groups therefore continue. The defensible current conclusion is that the
benchmark machinery, exact replay and precision analysis work as registered;
the available evidence does not yet authorize a claim that active atom reload
improves logical error.

## Scope

This study benchmarks dynamic atom reload for rotated surface-code memory under
the frozen Challenge 66 model. It compares `none`, `immediate`, periodic, and
missing-fraction threshold policies with common exogenous random streams. The
reported distances are `d=3,5`; results are finite-size regime maps or
pseudo-threshold observations, never an asymptotic loss threshold.

## Model and Methods

- Circuit family: memory-X and memory-Z, `T=d,2d`.
- Noise: independent data Pauli, measurement flip, and per-round atom loss.
- State: `ACTIVE -> LOST_UNDETECTED -> LOST_DETECTED -> RELOADING -> ACTIVE`.
- Decoder: frozen erasure-aware graph decoder validated against an independent
  exhaustive small-slice oracle.
- Pairing: policies in a physical group share addressed random streams and
  exact `shot_id` ranges.
- Discovery stopping: at least 400 logical failures per cell or 2,000,000
  shots, doubling cumulative paired shots.
- Confirmation stopping: at least 1,000 logical failures per cell or
  20,000,000 shots, with 20,000 paired bootstrap resamples.
- Multiplicity: Benjamini-Hochberg FDR `q=0.05`.
- Helpful/harmful: a candidate-minus-none paired 95% interval is helpful only
  when its FDR-qualified upper bound is below zero, harmful only when its lower
  bound is above zero.

## Reproducibility and Validation

The locked environment, simulator, independent oracle, isolation controls,
negative controls, exact replay, and frozen reference score passed before the
large grid. The accepted candidate commit is
`0a73ba334a4b85403634e710f3d768ef8831d16d`; its normalized source-tree SHA-256
is `829ade4b3ab7408c9151a6a06222e6779df6c65096b8d2e2d947e26238140482`.

Development validator score: `185.979924557991` validated decoded shots/s
geometric mean. This is an implementation-selection metric and is not evidence
that reload improves logical error.

## Discovery Results

Accepted public artifact through Phase 2:
`results/discovery/analysis/phase-2/6771281` on SCNet.

- 280 physical groups, 2,240 cells and 1,960 paired comparisons accounted for;
- 89,600,000 cumulative cell-shots;
- 27 cells reached the registered failure target and 2,213 continue;
- every lockstep group continues into Phase 3;
- provisional FDR classifications: 436 `helpful`, 1,524
  `no_significant_difference`, and no authorized headline claim;
- matrix SHA-256:
  `75490cff0949dc128221bf9168138d4d813c07014f26c1c9cacac9b2ec6b9b18`;
- analysis-manifest SHA-256:
  `945f798bbfefe7e85c5730cebd65f3fe48501d39cb76602c56e1ff338cc292bd`;
- continuation-plan SHA-256:
  `c2183dcaa8aad272d7eb77050aedefb38ad24f85e78687ba965e943ebe753519`.

All seven elements of Phase-3 array `23019121` completed on xh5. The original
dependent analysis `23019135` failed closed because the transferred tree
lacked the Phase-1 continuation plan. After that plan was transferred and its
manifest passed, replacement analysis `23020995` reached its wall-time limit
without publishing a Phase-3 manifest. The Phase-3 data are archived but
excluded from accepted numerical results.

## Independent-Seed Confirmation

Initial artifact job `6769918` completed 800,000 exact-replayed shots and all
five v2 negative controls. Stopping-cycle job `6769978` atomically published
and verified Phases 1--5 before its wall-time limit interrupted an unpublished
Phase-6 staging directory. The accepted Phase-5 artifact is
`results/confirmation/analysis/phase-5/6769978`.

- 8 headline physical groups, 40 cells and 32 paired comparisons;
- 12,800,000 cumulative cell-shots, or 320,000 shots per cell;
- 4 cells reached 1,000 logical failures and 36 continue;
- 32/32 comparisons meet paired precision, for precision fraction `1.0`
  against the required `0.8`;
- result-manifest SHA-256:
  `3cf868e8d6602aecb8976244041906baf2ea4922cd41271fcd164a7cab1ef945`;
- analysis-manifest SHA-256:
  `67ab1aa9137cb1a1568617cf3979c5e60c92a2aa3e384e4955695401edd2444b`.

xh5 resume job `23018885` revalidated all transferred manifests and resumed
from Phase 5 with 120 CPUs. It reached its wall-time limit without atomically
publishing Phase 6, which is therefore excluded. The accepted precision result
is necessary but not sufficient: cell-level failure stopping still forces all
eight groups to continue.

## Reload-Cost Sensitivity and Pareto Results

Execution remained forbidden because discovery was not final. Executable snapshot
`bundle-sensitivity-cycle-7ea851b` passed 26/26 focused contracts on xh5 job
`23006968`. Prepared design:
48 physical/cost groups, 192 active-policy cells, three loss regions, two delay
costs, two reset-error costs, two reload-failure costs and two combined costs.

The final analysis reports the pre-result Cartesian grid
`lambda_r, lambda_t in {0, 1e-3, 1e-2}`
for
`J = p_L + lambda_r * reloads/(N_sites*T) + lambda_t * extra_rounds/T`, plus
the unweighted Pareto frontier. The fixed-horizon in-place model has
`extra_rounds_per_shot=0`; delay remains visible through logical error, missing
occupancy and reload site-round wait. No policy may be called globally best.

## Limitations

- Independent per-site loss is a baseline, not a correlated Rydberg loss model.
- Reload restores a carrier but not the unknown pre-loss quantum state.
- The graph decoder and timing semantics are frozen approximations to the
  registered Challenge 66 model, not a device-specific gate schedule.
- `d=3,5` cannot establish an asymptotic threshold.
- Non-significance is not equivalence; capped wide intervals remain explicitly
  inconclusive.

## Holdout and Final Status

Holdout query budget: `0 / 1`, unspent.

Final status: `inconclusive_at_deadline`.

The sealed holdout could be run once only after every public science gate and
this report were complete. The 2026-07-30 15:27 CST deadline arrived with
discovery, confirmation, and cost sensitivity incomplete, so no holdout query
was spent.
