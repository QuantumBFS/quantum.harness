# Challenge #28 Symmetry-Preserving Local MPS VMCRG Implementation Plan

> **Archived optional comparison.** This MPS route and its existing evidence
> are preserved, but they do not contribute to any Issue #28 pure-neural Easy
> Goal success gate. The canonical plan is `../../../PLAN.md` and the detailed
> pure-neural implementation plan is
> `2026-07-28-issue28-pure-neural-vmcrg.md`.

> **Execution rule:** implement this plan in the current session with strict test-first cycles. Do not commit, push, switch branches, overwrite existing results, or modify files outside `tracks/mps/DMRG/` before user review.

**Goal:** Extend the verified two-dimensional Ising VMCRG baseline with a shared, local, symmetry-exact 3x3 patch MPS residual, a 512-state lookup table, exact local cache updates, and reproducible one- and two-level RG experiments for Challenge #28.

**Architecture:** Keep the existing `src/vmcrg_ref/` Ising, majority-rule RG, 13-operator registry, and traditional VMCRG implementation as the physical baseline. Add a direct physical-index open-boundary MPS for binary 3x3 patches, compile its D4 x Z2 symmetrized and uniform-target-centered output into a 512-entry table, and use that table in a new incremental Metropolis sampler and VMCRG optimizer. Reuse the existing result conventions and scripts while adding focused TOML configs, pytest coverage, Slurm wrappers, metrics, plots, and checkpoints for the MPS route.

**Tech stack:** Python 3.12, NumPy float64, SciPy, Numba, pytest, matplotlib, TOML via `tomllib`; no PyTorch dependency and no neural forward pass inside a spin proposal.

## Global Constraints

- Work only in `/home/asus/code/quantum.harness/tracks/mps/DMRG` and preserve all pre-existing files and results.
- The local checkout is currently on `main`; PR #154 has head `challenge/mps/neural-renormalized-hamiltonians`. Do not switch branches in the dirty shared worktree.
- Physical convention: `H(sigma) = -K sum_<ij> sigma_i sigma_j = K S_nn(sigma)` with `S_nn = -sum_<ij> sigma_i sigma_j` and acceptance `min(1, exp[-Delta(H+V)])`.
- Main paper-matched point: `L=45`, periodic square lattice, `K=0.436`, 3x3 non-overlapping majority blocks, uniform independent block-spin target.
- Provenance anchors: exact Ising critical coupling `K_c = 0.5 ln(1+sqrt(2)) = 0.44068679350977147`; paper flow bracket `0.4355-0.4365`; paper L=45 schedule `3000` variational steps, `20` sweeps/step, `16` walkers, `mu=5e-5`.
- Published traditional basis: the 7 two-spin and 6 four-spin coordinates listed on Supplement page 3 and already encoded as `EVEN_SHAPES`.
- Neural residual: `V(J,theta,alpha) = sum_a J_a S_a(mu) + alpha sum_r f_sym(P_r mu)` with a shared 9-site open MPS and exact D4, Z2, and translation symmetry.
- Patch order: row-major offsets `(-1,-1), (-1,0), (-1,1), (0,-1), (0,0), (0,1), (1,-1), (1,0), (1,1)` around every coarse-lattice center, with periodic indexing.
- Bit code: bit `k` corresponds to patch position `k`; `-1 -> 0`, `+1 -> 1`; pattern id is `sum_k bit_k * 2**k`.
- Formal bond dimensions: `chi in {2,4,8}`; `chi=16` is optional after the mandatory runs pass.
- MPS core shapes: `(1,2,chi)`, seven copies of `(chi,2,chi)`, and `(chi,2,1)`; direct slice selection by the binary spin state.
- Residual is exactly zero initially through `alpha=0`; patch outputs are centered by their exact mean over all 512 uniform patches.
- Monte Carlo proposals use only cached operator deltas and table differences; direct MPS contraction is forbidden inside proposal loops.
- Correctness tests use float64 and target absolute error `<=1e-10` unless a stricter exact integer comparison applies.
- Large raw chains and checkpoints remain ignored; only small summaries, configs, logs, CSV/JSON, and final figures are candidates for version control.
- Scientific claims are conditional on measured multi-seed evidence; a null or negative neural result is reported without threshold changes or seed selection.

---

## Scientific Questions and Decision Rules

1. **Representation:** Does the MPS residual lower a held-out VMCRG objective estimate and reduce 3x3 patch-distribution error relative to the same trained 13-operator baseline?
2. **Physics:** Does it reduce residual two-point and held-out multi-spin correlations without violating exact Ising symmetries?
3. **Sampling:** Does it reduce integrated autocorrelation time and improve ESS/s relative to both unbiased and traditional-bias Metropolis under matched proposal and sweep budgets?
4. **Computation:** Does the 512-state lookup plus local cache materially outperform direct MPS evaluation and full residual recomputation?
5. **Repeated RG:** At RG level 2, does warm-starting the level-1 MPS reduce optimization steps, sweeps, or wall time to a matched target error?

Primary success requires repeatable improvement across at least three predeclared seeds. Failure to improve is a valid result if symmetry, cache consistency, and fair-budget checks pass.

## Mathematical Definitions

- The VMCRG functional follows Wu and Car:

  `Omega[V] = log(Z_V / Z_0) + E_target[V]`.

- Its parameter gradient is:

  `d Omega / d lambda = E_target[dV/dlambda] - E_biased[dV/dlambda]`.

- For the uniform independent target, every 3x3 patch has probability `1/512`; the centered table and its parameter derivative therefore have exact target mean zero.
- Each outer optimizer iteration compiles current MPS parameters into a centered table. A coarse-spin flip affects exactly nine patch centers and toggles one known bit in each cached pattern id.
- Sequential objective logging uses free-energy perturbation between adjacent parameter states:

  `Delta Omega_t = log mean_biased_t exp[-(V_{t+1}-V_t)] + E_target[V_{t+1}-V_t]`,

  evaluated stably with log-sum-exp and accumulated from the traditional baseline anchor.
- Level-2 RG uses the composite map `mu^(1)=tau_3(sigma)` and `mu^(2)=tau_3(mu^(1))`; a microscopic proposal propagates at most one changed site through each cached level.

## File Map

Existing files to preserve and extend:

- `src/vmcrg_ref/ising.py`: nearest-neighbor Ising energy and local delta.
- `src/vmcrg_ref/blockspin.py`: current full 3x3 majority transform.
- `src/vmcrg_ref/operators.py`: published operator registry and local deltas.
- `src/vmcrg_ref/multi_optimizer.py`: traditional VMCRG Stage A.
- `src/vmcrg_ref/paper_observables.py`: existing correlation-time primitives.
- `src/vmcrg_ref/__init__.py`: export new public classes without breaking existing imports.
- `README.md`: replace the old reproduction-first front page with a Challenge #28 reproduction guide while retaining links to historical evidence.
- `reproduce.py`: retain existing commands; add only a non-breaking MPS challenge command if integration remains small.

New focused modules:

- `src/vmcrg_ref/symmetries.py`: patch coordinates, D4 permutations, transforms, orbit checks.
- `src/vmcrg_ref/mps_patch.py`: direct patch MPS, contractions, analytic gradients, canonicalization, diagnostics, serialization.
- `src/vmcrg_ref/patch_table.py`: 9-bit codec, 512 enumeration, centered lookup, periodic patch geometry, incremental cache.
- `src/vmcrg_ref/rg.py`: incremental one- and two-level majority-rule state with composite proposal/commit.
- `src/vmcrg_ref/mps_bias.py`: traditional plus MPS bias value/delta abstraction.
- `src/vmcrg_ref/mps_sampler.py`: Python reference and Numba lookup-table Metropolis samplers.
- `src/vmcrg_ref/mps_vmcrg.py`: Stage B residual training, optional Stage C joint tuning, exact target terms, logging, gradient clipping.
- `src/vmcrg_ref/autocorrelation.py`: documented automatic-window IAT, ESS, ESS/s.
- `src/vmcrg_ref/observables.py`: correlations, high-order probes, patch histogram distances, timing/resource summaries.
- `src/vmcrg_ref/checkpoint.py`: atomic small checkpoint metadata plus compressed model arrays.
- `src/vmcrg_ref/config.py`: validated TOML experiment configuration.

New tests:

- `tests/test_ising_pytest.py`
- `tests/test_rg_mps.py`
- `tests/test_local_operators_pytest.py`
- `tests/test_mps_patch.py`
- `tests/test_symmetries.py`
- `tests/test_patch_table.py`
- `tests/test_incremental_mps.py`
- `tests/test_mps_sampler.py`
- `tests/test_mps_vmcrg.py`
- `tests/test_checkpoint_mps.py`

New experiment files:

- `scripts/run_exact_checks.py`
- `scripts/run_smoke.py`
- `scripts/run_baseline.py`
- `scripts/run_neural_vmcrg.py`
- `scripts/run_rg_warm_start.py`
- `scripts/benchmark_updates.py`
- `scripts/analyze_results.py`
- `scripts/plot_results.py`
- `config/mps_smoke.toml`
- `config/mps_baseline_9x9.toml`
- `config/mps_baseline_45x45.toml`
- `config/mps_chi2.toml`
- `config/mps_chi4.toml`
- `config/mps_chi8.toml`
- `config/mps_warm_start.toml`
- `jobs/mps_smoke.slurm`
- `jobs/mps_scan.slurm`
- `jobs/mps_warm_start.slurm`
- `results/mps_challenge/README.md`
- `pyproject.toml`

---

## Task 1: Lock the Plan and Baseline

**Produces:** an auditable starting point and no changes outside the solution directory.

- [ ] Record branch, PR head, dirty paths, challenge metadata, paper SHA-256 values, Python/package versions, and the pre-change 94-test result in `results/mps_challenge/environment.json`.
- [ ] Add a `pyproject.toml` that declares the existing runtime dependencies and pytest discovery without installing or upgrading packages.
- [ ] Run the existing suite again with `.venv/bin/python reproduce.py test`; expected result: 94 tests pass before new test files are introduced.

## Task 2: Ising and Periodic-Lattice Contract

**Tests first:** `test_periodic_neighbors`, `test_ising_energy_against_bruteforce`, `test_delta_energy_matches_full_recompute`.

- [ ] Add failing pytest cases for periodic neighbors on 2x2, 3x3, and 4x4 arrays, exact bond counting, and every-site local energy deltas.
- [ ] Extend `ising.py` only where the desired API is missing: `periodic_neighbors`, `ising_hamiltonian`, and explicit `delta_hamiltonian` wrappers using the established sign convention.
- [ ] Run the focused tests, then the complete legacy suite.

## Task 3: Incremental Composite Majority RG

**Tests first:** `test_block_spin_majority_rule`, `test_block_spin_incremental_update`, plus a two-level composite-map test.

- [ ] Specify block origin `(0,0)`, row-major block order, non-overlapping slices, and periodic coarse lattices in `rg.py` docstrings.
- [ ] Implement `MajorityRGState(spins, block_size=3, levels=1|2)` with cached sums/spins, a side-effect-free proposal, and commit.
- [ ] Verify a random sequence of microscopic flips against full recomputation of both 15x15 and 5x5 levels.
- [ ] Keep `blockspin.py` behavior unchanged and use it as the full-recompute oracle.

## Task 4: Published Operator Registry Audit

**Tests first:** `test_local_operator_delta_matches_full_recompute`, parametrized independently over all 13 published operators.

- [ ] Assert every `EVEN_SHAPES` coordinate tuple against Supplement page 3.
- [ ] Assert periodic D4 instance counts, global Z2 parity, and one-spin incremental deltas for each operator separately.
- [ ] Add target-expectation checks showing every nonconstant published even operator has exact zero mean under independent uniform spins.
- [ ] Do not reconstruct or relabel the unpublished initial 26-operator set.

## Task 5: Patch Symmetry Maps

**Tests first:** `test_patch_d4_transformations`, `test_z2_symmetry_exact`, `test_d4_symmetry_exact`.

- [ ] Implement the eight D4 index maps from the documented row-major coordinates.
- [ ] Test identity, four rotations, four reflections, uniqueness, closure, and inverse mappings.
- [ ] Generate at least 100 deterministic random patches and require symmetry errors at or below `5e-14` for the final symmetrized MPS.
- [ ] Provide an explicit `symmetrize=False` ablation flag; default remains exact D4 x Z2.

## Task 6: Direct 9-Site Patch MPS

**Tests first:** `test_mps_output_scalar`, core-shape/parameter-count tests, explicit enumeration comparison, and `test_mps_gradient_finite_difference`.

- [ ] Implement physical-state mapping `-1 -> 0`, `+1 -> 1` and open-boundary contraction over nine cores.
- [ ] Implement batch contraction for all 512 patches and analytic weighted gradients using left/right environments.
- [ ] Implement exact D4 x Z2 averaging and exact uniform-target centering.
- [ ] Implement deterministic left-canonicalization with rank padding that preserves all declared core shapes and the contracted function to `1e-12`.
- [ ] Initialize finite random cores and `alpha=0`; report core norms, total parameter norm, output range, and parameter count.
- [ ] Reject NaN/Inf cores and non-finite contractions immediately.

## Task 7: 512-State Lookup and Patch Cache

**Tests first:** `test_patch_bit_encoding_roundtrip`, `test_lookup_table_matches_direct_mps`, `test_uniform_target_patch_histogram`, `test_bias_constant_gauge`.

- [ ] Enumerate ids `0..511`, decode all patches, re-encode, and assert exact round trips.
- [ ] Build `PatchLookupTable` from direct symmetrized MPS outputs; center by the exact arithmetic mean and assert table mean below `1e-14`.
- [ ] Build periodic patch-site and reverse site-to-patch tables for arbitrary coarse lengths `>=3`; each site must affect exactly nine centers.
- [ ] Cache per-center ids, values, histogram, and total residual; a flip must update ids by XOR with the precomputed local bit mask.
- [ ] Add full-recompute drift checks that emit seed, site, old/new ids, and maximum discrepancy before raising.

## Task 8: Traditional Plus MPS Bias and Incremental Sampler

**Tests first:** `test_neural_delta_matches_full_recompute`, `test_cache_consistency_after_random_flips`, and compiled/reference trajectory equivalence.

- [ ] Implement `MPSResidualBias` with `J`, `alpha`, operator registry, centered lookup, and explicit full value.
- [ ] Implement a Python reference sampler using `MajorityRGState`, operator deltas, and the nine-patch cache delta.
- [ ] Implement a Numba kernel that consumes the frozen 512 table and cache arrays; it must never call MPS contraction.
- [ ] Support unbiased (`J=alpha=0`), traditional (`alpha=0`), and traditional+MPS modes through one configuration.
- [ ] Use the overflow-safe decision `delta<=0 or log(u)<-delta` and record attempted/accepted proposals.
- [ ] Check caches every configured number of sweeps and stop immediately on drift.

## Task 9: Traditional VMCRG Stage A Wrapper

**Tests first:** exact identity-RG gradient direction and small-system objective descent.

- [ ] Reuse `MultiOperatorOptimizer` and the 13 published operators rather than duplicate the paper baseline.
- [ ] Add a wrapper that saves the final running-average `J`, paper settings, acceptance rates, operator moments, convergence trace, and checkpoint metadata.
- [ ] For uniform targets use exact zero operator expectations, excluding any constant operator.
- [ ] Validate on a small identity-RG case where `J*=-K`, then on 9x9 -> 3x3 smoke settings.

## Task 10: MPS VMCRG Stages B and C

**Tests first:** exact-gradient finite difference on a tiny fixed sample, zero-alpha behavior, clipping, deterministic seed reproduction, and objective-increment sign on a controlled problem.

- [ ] Freeze Stage A `J` and optimize `alpha` plus MPS cores using the exact target-zero gradient and biased patch histograms.
- [ ] Use separate learning rates and Adam moments for `alpha` and cores, global gradient clipping, finite diagnostics, and early stopping on a predeclared patience window.
- [ ] Recompile the table once after each outer parameter update; refresh every walker cache from its current coarse spins.
- [ ] Log step, RG level, seed, cumulative objective estimate/change, gradient norms, `J`, `alpha`, MPS norm/range, acceptance, correlations, patch distances, IAT estimate, sweep time, total time, and checkpoint flag.
- [ ] Enable joint Stage C only after Stage B stability checks pass; maintain separate `J`, `alpha`, and core learning rates.
- [ ] On Stage C instability, restore the best Stage B checkpoint and mark joint tuning as failed rather than modifying thresholds.

## Task 11: Checkpoints and Configuration

**Tests first:** `test_checkpoint_roundtrip`, `test_reproducibility_same_seed`, invalid-config tests.

- [ ] Save model arrays to compressed NPZ and human-readable metadata/config hashes to JSON; write through a temporary file then rename.
- [ ] Restore MPS cores, `alpha`, `J`, optimizer counters, RNG states, RG level, and best-objective metadata.
- [ ] Validate all TOML fields, especially divisibility by `3**rg_levels`, bond dimension, seed list uniqueness, sweep counts, cache-check interval, and output path non-overwrite.

## Task 12: Observables and Statistical Efficiency

**Tests first:** known synthetic autocorrelation series, exact uniform histogram, and hand-computed TV/JS/KL examples.

- [ ] Measure microscopic energy, microscopic magnetization, coarse magnetization, multiple displacement correlations, four-spin, six-spin, long-range products, and 3x3 parity.
- [ ] Compute patch TV, Jensen-Shannon divergence, and KL with documented Jeffreys pseudocount `1/2` for empirical zero cells while retaining the unsmoothed TV.
- [ ] Implement FFT autocorrelation and a self-consistent Sokal window `M >= 5 tau(M)`, with initial-positive-sequence fallback.
- [ ] Report `tau_int`, `ESS=N/(2 tau_int)`, wall time, and `ESS/s` for every arm and seed.

## Task 13: Stage 0 and Stage 1 Local Validation

- [ ] Run all mandatory unit tests under pytest.
- [ ] Compare 4x4 unbiased Metropolis energy/magnetization moments against exact enumeration with a deterministic chain and predeclared statistical tolerance.
- [ ] Verify a multi-block 6x3 or 9x6 majority mapping against explicit block enumeration.
- [ ] Verify traditional and MPS gradient directions on fixed exact/sample distributions.
- [ ] Save a compact exact-check JSON report.

## Task 14: Stage 2 9x9 -> 3x3 Smoke Workflow

- [ ] Run traditional Stage A with a few walkers and short sweeps.
- [ ] Run Stage B at `chi=2`, starting from `alpha=0`.
- [ ] Exercise logging, checkpoints, cache checks, analysis, and plotting end to end in a few minutes.
- [ ] Mark smoke results as connectivity-only and scientifically insufficient.

## Task 15: Performance Benchmarks

- [ ] Benchmark direct MPS contraction, 512 table evaluation, full lattice residual recomputation, local cache proposal, one sweep, and one optimizer iteration.
- [ ] Warm Numba before timing and report median plus dispersion across repeated timings.
- [ ] Record parameter counts, table/Jacobian memory estimates, measured RSS where available, and forward time for `chi=2,4,8` and optional `16`.
- [ ] Require direct/full and lookup/increment paths to agree numerically before reporting speedups.

## Task 16: Stage 3 Medium-Scale Runs

- [ ] Run 18x18 -> 6x6 or 27x27 -> 9x9 at `chi=2,4` for seeds `20260801, 20260802, 20260803`.
- [ ] Compare traditional and MPS arms with identical walkers, thermalization, measurement sweeps, thinning, and proposal schedules.
- [ ] Use these timings to estimate Stage 4 wall time and memory before cluster submission.

## Task 17: Slurm Preparation and Safety Check

- [ ] Read the active cluster profile and use `scripts/harness_slurm.sh` for precheck, queue probing, feasibility test, submit, monitor, fetch, and classification.
- [ ] Ship only `tracks/mps/DMRG/` plus the minimal runner through an explicitly scoped rsync path; do not commit or push the dirty shared tree.
- [ ] First remote job: one node, 1-4 CPUs, small memory, at most 10 minutes, smoke config only.
- [ ] Every job sets stdout/stderr, deterministic seed/cell id, `set -euo pipefail`, writable cache directories, and incremental result writes.

## Task 18: Stage 4 45x45 Easy Goal

- [ ] Train or load one common traditional baseline per seed and reuse it fairly for `chi=2,4,8` Stage B runs.
- [ ] Use at least seeds `20260801, 20260802, 20260803`; retain every run regardless of outcome.
- [ ] Compare unbiased, traditional, and traditional+MPS samplers with matched measurement budgets.
- [ ] Collect objective, patch distances, correlations, held-out high-order errors, IAT, ESS/s, acceptance, runtime, memory, parameter count, and symmetry errors.
- [ ] Keep raw chains/checkpoints remote or ignored; fetch summaries and compact diagnostics.

## Task 19: Stage 5 Level-2 RG and Warm Start

- [ ] Validate 45x45 -> 15x15 -> 5x5 composite incremental state against full recomputation.
- [ ] Compare random initialization and level-1 MPS warm start under identical seed sets, walkers, sweeps, optimizer, thresholds, and wall limits.
- [ ] Report steps, sweeps, time to matched error, final error, physical metrics, and sampling efficiency; do not report loss alone.
- [ ] If Stage 4 does not pass correctness/stability gates, keep the code/tests but mark Stage 5 compute as not run.

## Task 20: Analysis, Figures, README, and Final Verification

- [ ] Generate all requested plots from saved summary CSV/JSON with labeled axes, error bars, seed count, lattice, K, RG level, and chi.
- [ ] Store the exact data used by every panel next to the figure.
- [ ] Rewrite `README.md` around Issue #28, the MPS residual contribution, verified conventions, commands, reproducibility, metrics, limitations, and interpretation rules.
- [ ] Run focused pytest, complete pytest, legacy unittest entry, formatting/static checks available in the repository, and root `make test` if it does not mutate unrelated files.
- [ ] Run `superpowers:verification-before-completion`, inspect `git status` and `git diff -- tracks/mps/DMRG`, and report unrun/failed experiments explicitly.
- [ ] Stop before `git add`, commit, push, PR edits, or Ready-for-review changes.

---

## Required Test Name Mapping

The final pytest collection must include these exact behaviors, whether some reuse existing legacy assertions:

1. `test_periodic_neighbors`
2. `test_ising_energy_against_bruteforce`
3. `test_delta_energy_matches_full_recompute`
4. `test_block_spin_majority_rule`
5. `test_block_spin_incremental_update`
6. `test_patch_bit_encoding_roundtrip`
7. `test_patch_d4_transformations`
8. `test_z2_symmetry_exact`
9. `test_d4_symmetry_exact`
10. `test_mps_output_scalar`
11. `test_mps_gradient_finite_difference`
12. `test_lookup_table_matches_direct_mps`
13. `test_neural_delta_matches_full_recompute`
14. `test_local_operator_delta_matches_full_recompute`
15. `test_cache_consistency_after_random_flips`
16. `test_uniform_target_patch_histogram`
17. `test_bias_constant_gauge`
18. `test_metropolis_small_lattice_against_exact`
19. `test_checkpoint_roundtrip`
20. `test_reproducibility_same_seed`

## Experiment Gate Table

| Gate | Required evidence | On failure |
|---|---|---|
| Stage 0 | all deterministic deltas/symmetries/lookups within tolerance | debug before any sampling experiment |
| Stage 1 | exact-enumeration and gradient-direction checks pass | do not run 9x9 smoke |
| Stage 2 | end-to-end logs/checkpoints/figures and cache checks pass | fix locally; no Slurm submission |
| Stage 3 | three seeds stable, measured cost feasible, no cache drift | reduce learning rate/sweeps only through a new documented config |
| Stage 4 | all chi/seeds complete with fair budgets and finite diagnostics | report incomplete/null result; do not select seeds |
| Stage 5 | Stage 4 correct and stable; composite RG tests pass | omit level-2 claims and keep warm-start as future work |

## Risk Register and Degradation Paths

- **MPS gauge instability:** left-canonicalize after updates, clip global gradients, monitor final-core/output norms, lower core learning rate through a new config if needed.
- **Zero-alpha training stall:** alpha receives the first nonzero gradient while core gradients are gated by alpha; if alpha remains statistically zero, report no residual signal rather than forcing nonzero initialization.
- **Noisy VMCRG gradients:** increase independent walkers or gradient accumulation within the declared compute budget; retain exact target expectations and do not add target MC noise.
- **Traditional baseline mismatch:** use the published 13 operators and existing verified implementation; if the full paper schedule is too costly, label reduced schedules provisional and never call them the paper-complete baseline.
- **Lookup/cache drift:** immediate abort with reproducible state; no tolerance relaxation above `1e-10` for float64 correctness paths.
- **Autocorrelation uncertainty:** lengthen measurement chains or report one-sided lower bounds; never compare sweep time without IAT and ESS/s.
- **Cluster queue/resource issues:** use the profile and queue probe to switch only among real compatible partitions; do not expand nodes/memory silently.
- **Stage C divergence:** restore and report Stage B checkpoint as the final neural result.
- **No MPS improvement:** preserve the null result, analyze chi/seed sensitivity and overhead, and state that the hypotheses were not supported under the tested budget.
- **Level-2 cost too high:** deliver verified composite mapping and warm-start code/tests, but mark the physical Stage 5 experiment unexecuted.

## Planned Reproduction Commands

```bash
MPLCONFIGDIR=/tmp/matplotlib .venv/bin/python -m pytest -q tracks/mps/DMRG/tests
MPLCONFIGDIR=/tmp/matplotlib .venv/bin/python tracks/mps/DMRG/scripts/run_smoke.py --config tracks/mps/DMRG/config/mps_smoke.toml
MPLCONFIGDIR=/tmp/matplotlib .venv/bin/python tracks/mps/DMRG/scripts/run_baseline.py --config tracks/mps/DMRG/config/mps_baseline_45x45.toml
MPLCONFIGDIR=/tmp/matplotlib .venv/bin/python tracks/mps/DMRG/scripts/run_neural_vmcrg.py --config tracks/mps/DMRG/config/mps_chi4.toml
MPLCONFIGDIR=/tmp/matplotlib .venv/bin/python tracks/mps/DMRG/scripts/benchmark_updates.py --output tracks/mps/DMRG/results/mps_challenge/benchmarks
MPLCONFIGDIR=/tmp/matplotlib .venv/bin/python tracks/mps/DMRG/scripts/analyze_results.py --root tracks/mps/DMRG/results/mps_challenge
MPLCONFIGDIR=/tmp/matplotlib .venv/bin/python tracks/mps/DMRG/scripts/plot_results.py --root tracks/mps/DMRG/results/mps_challenge
```

Cluster commands will be filled with the active profile's real partition and remote path after local Stage 2-3 timings and `harness_slurm.sh probe-partitions`; no partition is invented in this plan.
