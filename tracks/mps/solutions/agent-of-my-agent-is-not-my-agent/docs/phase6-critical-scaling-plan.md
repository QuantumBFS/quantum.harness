# Phase 6 Critical-Scaling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the validated, resumable `sigma=1.75` R-xi crossing and
gap-scaling workflow without launching the production scaling grid.

**Architecture:** Add a rotated-basis, parity-resolved MPO/DMRG layer; pure
analysis modules for correlation lengths, crossings, and effective exponents;
and separate commands for per-sigma fit regeneration, scan planning, and
post-processing. Production execution remains a later cluster step and
consumes machine-readable run specifications created here.

**Tech Stack:** Python 3.11, NumPy, SciPy, TeNPy 1.1.0, matplotlib, pytest,
existing `mps` conda environment.

## Global constraints

- Hamiltonian:
  `H=-sum_(i<j) J_L(j-i;sigma) Z_phys,i Z_phys,j-Gamma sum_i X_phys,i`.
- Rotated basis: `X_phys=Sigmaz`, `Z_phys=Sigmax`, conserved physical
  `prod_i X_phys,i` parity.
- Full physical correlation only; no connected subtraction.
- Diagnostic size `L=32`; production window `L=64,128,256`.
- Fixed Gamma grids: coarse `1.540:0.005:1.580`, fine
  `1.552:0.001:1.570`; no adaptive refinement.
- Primary `Gamma_c` correction is `Gamma_x=Gamma_c+a/L`; logarithmic and
  leave-`(32,64)`-out results are sensitivity analyses.
- All gaps use the same extrapolated `Gamma_c` and its uncertainty bounds.
- Full scan uses `chi=128`; only crossing brackets and gaps use higher chi.
- Primary exponential fit:
  `K=24`, `alpha=0.5`, `r_fit=8*L_max=2048`, `L_max=256`.
- Do not start production calculations while executing this plan.

---

### Task 1: Rotated-basis MPO and parity-sector DMRG

**Files:**
- Modify: `src/lrtfim/mpo.py`
- Create: `src/lrtfim/parity_dmrg.py`
- Modify: `src/lrtfim/__init__.py`
- Create: `tests/test_rotated_basis.py`

**Interfaces:**
- Produce:
  `build_rotated_periodized_mpo(length, lambdas, coefficients, gamma) -> MPO`
- Produce: `build_rotated_nearest_neighbor_mpo(length, gamma) -> MPO`
- Produce:
  `run_parity_spectrum(model, dmrg_options) -> ParitySpectrumResult`
- `ParitySpectrumResult` contains even ground state, odd first excitation,
  gap, variance, discarded weight, chi, and sector labels.

- [ ] **Step 1: Write failing dense-MPO rotation tests**

  Add tests that contract both standard and rotated MPOs at `L=4` and require
  equality after the local Hadamard basis rotation:

  ```python
  hadamard = np.array([[1., 1.], [1., -1.]]) / np.sqrt(2.)
  rotation = reduce(np.kron, [hadamard] * length)
  np.testing.assert_allclose(
      dense_rotated,
      rotation @ dense_physical @ rotation.T,
      atol=2e-13,
  )
  ```

  Test both the periodic NN MPO and a two-pole periodized long-range MPO.

- [ ] **Step 2: Verify the tests fail for missing rotated builders**

  Run:

  ```bash
  PYTHONPATH=src conda run -n mps python -m pytest \
    tests/test_rotated_basis.py -q
  ```

  Expected: import failure for `build_rotated_periodized_mpo`.

- [ ] **Step 3: Implement rotated MPOGraph operators**

  Reuse the existing direct/wrapped graph construction but parameterize the
  physical operators:

  ```python
  def build_rotated_periodized_mpo(length, lambdas, coefficients, gamma):
      site = SpinHalfSite(conserve="parity")
      graph = build_periodized_mpo_graph(
          length, lambdas, coefficients, gamma,
          site=site,
          interaction_operator="Sigmax",
          field_operator="Sigmaz",
      ).build_MPO()
      return graph
  ```

  Extend `build_periodized_mpo_graph` and the NN graph builder with the three
  exact keyword arguments shown above: `site`, `interaction_operator`, and
  `field_operator`.

- [ ] **Step 4: Add failing even/odd sector tests**

  At `L=8,10,12`, compare the rotated parity-sector `E0`, `E1`, gap, and
  `Sigmax`-`Sigmax` correlations with the existing physical-basis dense ED
  fixtures. Require energy/gap error below `1e-9`, correlation error below
  `1e-8`, and explicit sector labels `even` and `odd`.

- [ ] **Step 5: Implement parity-sector targeting**

  Construct product MPS states with even/odd conserved charges and run the
  shared two-site options separately in each sector. Do not use
  `orthogonal_to` across sectors:

  ```python
  even = run_sector_state(model, initial_even, dmrg_options, sector="even")
  odd = run_sector_state(model, initial_odd, dmrg_options, sector="odd")
  return ParitySpectrumResult(even, odd, odd.energy - even.energy)
  ```

- [ ] **Step 6: Run the rotated validation gate**

  Run the focused tests and existing Phase 4/5 tests. Do not proceed unless
  NN and long-range `L=8,10,12` fixtures all pass.

---

### Task 2: Auditable physical correlations and R-xi

**Files:**
- Create: `src/lrtfim/correlation_ratio.py`
- Modify: `src/lrtfim/__init__.py`
- Create: `tests/test_correlation_ratio.py`

**Interfaces:**
- Produce:
  `physical_correlations_rotated(psi) -> ndarray` for all integer distances
  from zero through `L-1`
- Produce:
  `second_moment_ratio(correlations) -> CorrelationRatio`
- `CorrelationRatio` fields:
  `s_zero`, `s_k_min`, `xi`, `r_xi`, `k_min`.

- [ ] **Step 1: Write failing analytic correlation tests**

  Test a fully polarized state (`C(r)=1`) only for correlation reconstruction,
  and use a positive-definite synthetic periodic correlation
  `C(r)=exp[-min(r,L-r)/ell]` to verify:

  ```python
  s0 = np.sum(c)
  sk = np.sum(np.cos(2*np.pi*np.arange(L)/L) * c)
  xi = np.sqrt(s0/sk - 1) / (2*np.sin(np.pi/L))
  ```

  Require the returned raw values and `r_xi=xi/L`.

- [ ] **Step 2: Verify RED**

  Run the focused test and require failure because
  `lrtfim.correlation_ratio` is absent.

- [ ] **Step 3: Implement full periodic translation averaging**

  Evaluate physical `Z_phys` with TeNPy `Sigmax`:

  ```python
  for r in range(L):
      c[r] = np.mean([
          psi.expectation_value_term(
              [("Sigmax", i), ("Sigmax", (i+r) % L)]
          ) if r else 1.0
          for i in range(L)
      ])
  ```

  Reject nonpositive `S(k_min)`, `S(0)<S(k_min)`, or appreciable imaginary
  parts with explicit errors. Do not subtract one-point functions.

- [ ] **Step 4: Verify GREEN and ED agreement**

  Compare `C(r)`, `S(0)`, `S(k_min)`, `xi`, and `R_xi` from rotated MPS and
  dense ED at `L=8,10,12`.

---

### Task 3: Per-sigma fit regeneration and validation records

**Files:**
- Create: `src/lrtfim/fit_protocol.py`
- Create: `scripts/regenerate_sigma_fit.py`
- Create: `tests/test_fit_protocol.py`
- Create: `tests/test_regenerate_sigma_fit_cli.py`

**Interfaces:**
- Produce:
  `fit_grid(sigma, lengths, l_max) -> list[FitValidationRecord]`
- Produce:
  `select_primary_fit(records, K=24, alpha=0.5, r_fit=2048)`
- CLI writes `fit-summary.json` and distance-resolved CSV profiles.

- [ ] **Step 1: Write failing protocol-grid tests**

  Require the exact deterministic grid:

  ```python
  assert pole_counts == [16, 24, 32]
  assert tail_windows == [1024, 2048, 4096]
  assert alpha_values_at_k24 == [0.25, 0.5, 1.0]
  assert primary.r_fit == 8 * 256 == 2048
  ```

  Use a reduced `L_max=8` CLI fixture so tests remain fast.

- [ ] **Step 2: Verify RED**

  Run both focused tests and require missing module/command failures.

- [ ] **Step 3: Implement regeneration**

  Call `fit_power_law` independently for each sigma/grid cell; never copy a
  fit from another sigma. For every production length, record exact and
  periodized couplings, full lambda/rate/coefficient spectra,
  `min(a_k)*r_fit`, and distance-resolved absolute/relative errors.

- [ ] **Step 4: Add K-comparison schema**

  Define separate Hamiltonian and physics blocks:

  ```json
  {
    "K_comparison": {
      "hamiltonian": {"couplings": {}, "tail": {}},
      "physics": {"crossings": {}, "gaps": {}, "z_eff": {}}
    }
  }
  ```

  Physics fields remain explicitly `pending` until later tasks populate them;
  absence is not reported as convergence.

- [ ] **Step 5: Verify deterministic outputs**

  Run the reduced CLI twice and require byte-identical fit spectra and profile
  values.

---

### Task 4: Locked scan specification and resumable cell command

**Files:**
- Create: `src/lrtfim/phase6_protocol.py`
- Create: `scripts/plan_phase6_scan.py`
- Create: `scripts/run_phase6_cell.py`
- Create: `tests/test_phase6_protocol.py`
- Create: `tests/test_phase6_cell_cli.py`

**Interfaces:**
- Produce: `gamma_grid() -> ndarray` with 24 distinct locked values.
- Produce:
  `phase6_run_spec(sigma: float, fit_id: str, output_dir: Path) -> dict`
- Cell command consumes one `(L,Gamma,K,chi,sector)` payload and writes one
  atomic `manifest.json`, raw `C(r)`, and state diagnostics.

- [ ] **Step 1: Write failing locked-grid tests**

  Require:

  ```python
  coarse = np.arange(1.540, 1.580 + 0.0025, 0.005)
  fine = np.arange(1.552, 1.570 + 0.0005, 0.001)
  expected = np.unique(np.round(np.r_[coarse, fine], 12))
  np.testing.assert_array_equal(gamma_grid(), expected)
  assert len(expected) == 24
  ```

  Verify sizes `[32,64,128,256]`, full-grid `chi=128`, and no adaptive-grid
  field in the run spec.

- [ ] **Step 2: Verify RED**

  Run focused protocol and CLI tests; require missing interfaces.

- [ ] **Step 3: Implement scan planning**

  Emit a resumable run spec with immutable settings/provenance hashes,
  per-cell paths, fit identity, and explicit `status` fields. A symmetric
  extension function adds `0.010` to both ends while preserving `0.005` and
  `0.001` spacings; it must reject one-sided extension requests.

- [ ] **Step 4: Implement one-cell execution**

  The cell constructs its raw record directly from measured values:

  ```python
  record = {
      "energy": float(state.energy),
      "variance": float(state.variance),
      "discarded_weight": float(state.max_discarded_weight),
      "chi": int(state.max_chi),
      "sector": state.sector,
      "correlations": correlations.tolist(),
      "s_zero": float(ratio.s_zero),
      "s_k_min": float(ratio.s_k_min),
      "xi": float(ratio.xi),
      "r_xi": float(ratio.r_xi),
  }
  ```

  Tests use an `L=4` fixture, not production sizes.

- [ ] **Step 5: Verify resume and failure visibility**

  Ensure completed cells are skipped only when settings and provenance match;
  failed/missing cells remain in collection output.

---

### Task 5: Crossing interpolation, correction fits, and chi refinement

**Files:**
- Create: `src/lrtfim/crossing_analysis.py`
- Create: `scripts/analyze_phase6_crossings.py`
- Create: `tests/test_crossing_analysis.py`

**Interfaces:**
- Produce:
  `linear_crossing(gamma, r_small, r_large) -> Crossing`
- Produce:
  `fit_crossing_drift(crossings, form) -> DriftFit`
- Produce:
  `crossing_chi_status(values_by_chi) -> ConvergenceStatus`

- [ ] **Step 1: Write failing interpolation tests**

  Use two exactly linear curves with a known crossing and require interpolation
  only between neighboring fine-grid points. Reject absent or multiple sign
  changes and surface `window_extension_required`.

- [ ] **Step 2: Write failing correction and chi tests**

  Require the primary `1/L` intercept, logarithmic sensitivity intercept,
  leave-`(32,64)`-out records, unchanged high-chi bracket, final shift
  `<=2e-4`, and non-growing successive shifts. Require `chi=512` when the
  `384-256` test fails.

- [ ] **Step 3: Verify RED, then implement pure analysis**

  Keep interpolation and fits independent of TeNPy. Bootstrap supplied
  numerical uncertainties without silently dropping failed resamples.

- [ ] **Step 4: Implement analysis command**

  Read raw `R_xi` records, write crossings and refinement requests, and never
  submit jobs itself. Produce primary, log-sensitivity, and leave-smallest
  outputs without ranking correction forms.

- [ ] **Step 5: Verify plots and audit fields**

  Require the crossing table and plot to retain the two bracket points,
  interpolation fraction, `S(0)`, `S(k_min)`, `xi`, K, and chi.

---

### Task 6: Common-Gamma gaps, pairwise effective z, and uncertainty propagation

**Files:**
- Create: `src/lrtfim/gap_scaling.py`
- Create: `scripts/analyze_phase6_gaps.py`
- Create: `tests/test_gap_scaling.py`

**Interfaces:**
- Produce:
  `gap_chi_status(gaps_by_chi, discarded_by_state) -> ConvergenceStatus`
- Produce: `effective_z(delta_L, delta_2L) -> float`
- Produce:
  `analyze_z(gaps_at_central_lower_upper, k24, k32) -> ZAnalysis`

- [ ] **Step 1: Write failing gap-convergence tests**

  Require the `1e-3` relative `384-256` threshold, separate ground/excited
  discarded weights `<=1e-9`, automatic `chi=512` request, and unresolved
  status when the `512-384` test fails.

- [ ] **Step 2: Write failing z tests**

  Generate exact `Delta(L)=A*L**(-z)` data and require all pairwise
  `z_eff=z`. Add controlled K and Gamma-bound shifts and require separate
  uncertainty components for `K`, chi, Gamma propagation, and corrections.
  In report prose, call these quantities gap-based pairwise effective
  dynamical exponents; do not call them `z(L)` or identify them with a QMC
  aspect-ratio estimator.

- [ ] **Step 3: Verify RED, then implement**

  Use the same primary extrapolated `Gamma_c` for every L. Reject input records
  containing pair-specific Gamma values. Associate every gap-based pairwise
  exponent with `L_eff=sqrt(L1*L2)`. Fit `z_eff=z+a/L_eff` as the power
  sensitivity and `z_eff=z+a/log(L_eff)` as the logarithmic sensitivity,
  without model ranking.

- [ ] **Step 4: Implement gap analysis command**

  Write central/lower/upper Gamma gap tables, all `z_eff`, K=24-to-32 shifts,
  and leave-`L=32`-out results. Produce refinement requests but never launch
  production cells.

- [ ] **Step 5: Verify uncertainty language**

  Tests must require that `2e-4` and `1e-3` appear only under numerical
  chi-convergence fields, never as final `Gamma_c` or z uncertainty.

---

### Task 7: Documentation, dry-run package, and verification

**Files:**
- Modify: `README.md`
- Modify: `docs/methodology.md`
- Modify: `scripts/README.md`
- Modify: `tests/README.md`
- Create: `tests/test_phase6_dry_run.py`

- [ ] **Step 1: Add a failing dry-run test**

  Run the complete workflow with `L=4,8`, a three-point Gamma fixture,
  `K=2`, and small chi. Require fit records, manifests, raw correlations,
  `S(0)`, `S(k_min)`, `xi`, crossings, gap records, and separated uncertainty
  fields.

- [ ] **Step 2: Verify RED, then connect the commands**

  Add a `--dry-run-fixture` mode that uses only declared test parameters and
  cannot select production sizes accidentally.

- [ ] **Step 3: Update user documentation**

  Document the rotated physical-operator notation, parity sectors, fixed
  grids, common-Gamma gap convention, fit regeneration, numerical thresholds,
  K propagation, and the statement that no correction-form discrimination is
  claimed.

- [ ] **Step 4: Run full verification**

  ```bash
  PYTHONPATH=src conda run -n mps python -m pytest -q
  git diff --check -- \
    tracks/mps/solutions/agent-of-my-agent-is-not-my-agent
  ```

  Require zero failures. Inspect the generated run specification and confirm
  that no production result directory or cluster job was created.

- [ ] **Step 5: Stop before production**

  Report implementation readiness, local fixture evidence, expected cluster
  workload, and the exact future submission command. Do not execute the
  `L=32,64,128,256` Gamma grid in this implementation phase.
