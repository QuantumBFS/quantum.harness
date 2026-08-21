# SUSY/Cohomological Hodge-Resolved Geometric ETH Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, preregister, execute, and audit a charge-resolved $\mathcal N=2$ SYK benchmark that predicts a sealed four-channel response statistic from exact/coexact two-point Hodge data and compares it with the existing one-sided Laughlin response law.

**Architecture:** New task-local v7 modules construct cubic fermionic cochain complexes, solve their harmonic BPS fibers, decompose projector responses into orthogonal exact/coexact branches, and generate both collapsed and Hodge-resolved covariance-matched Gaussian nulls. A split-checkpoint runner keeps physical $R_4$ in outcome sidecars, a sequential analyzer seals the complete $N=14$ prediction before unsealing, and independent figure/report/delivery scripts consume only accepted hashed artifacts. Existing v1--v6 source and outcome files remain immutable.

**Tech Stack:** Python 3, NumPy, SciPy sparse/dense linear algebra, pytest, Matplotlib, JSON/NPZ/SHA-256 checkpointing, Bash/Slurm for $N=14$, and the existing task-local `lgeth.wick_channels` finite-size statistic.

## Global Constraints

- Work only inside `01_task_folder/task_05/` for executable code and task outputs; task scripts may not import another task folder.
- Create new v7 files; do not modify accepted v1--v6 numerical artifacts or hash-anchored implementation modules.
- Write tests before implementation and commit each independently reviewable task.
- Generate every numerical result, table, and figure by script; do not enter measured values by hand.
- Treat a complete disorder realization as the uncertainty unit; never resample tangent entries as independent observations.
- Keep safe Hodge covariates and physical four-point outcomes in different files; safe serialization must reject `R4`, `four_point`, and `connected` keys.
- Use $m=8$ channels, primary sparse and secondary isotropic coupling panels, $N=8,10,12$ sequential development, $N=14$ sealed validation, and $N=16$ only after an explicit separation gate.
- Preserve the registered result branches and claim boundaries from `docs/plans/2026-08-01-susy-cohomological-geometric-eth-design.md`.
- Keep task_05 and main-dashboard statuses synchronized at `🟡 Ongoing` until the human explicitly closes the task.

## File map

- Create `01_task_folder/task_05/script/lgeth/susy_cohomology.py`: charge bases, fermionic signs, cubic supercharge matrices, charge-sector Hamiltonians, BPS frames, and expected generic ranks.
- Create `01_task_folder/task_05/script/lgeth/hodge_response.py`: coupling-tangent projection, sparse/isotropic panels, exact/coexact response branches, covariance summaries, and Hodge signatures.
- Create `01_task_folder/task_05/script/lgeth/hodge_wick.py`: collapsed-versus-Hodge Gaussian samplers and complete-realization reference aggregation.
- Create `01_task_folder/task_05/script/run_susy_hodge_geometric_eth_v7.py`: source-hashed kernel/response checkpoints, split safe/outcome files, pilot aggregation, prediction seals, and CLI.
- Create `01_task_folder/task_05/script/analyze_susy_hodge_geometric_eth_v7.py`: sequential pilot summaries, sealed $N=14$ predictions, unseal scoring, and frozen branch selection.
- Create `01_task_folder/task_05/script/make_susy_hodge_figure_v7.py`: one publication figure and machine-readable manifest.
- Create `01_task_folder/task_05/script/verify_susy_hodge_delivery_v7.py`: full scientific, provenance, corruption, figure, and report audit.
- Create `01_task_folder/task_05/script/slurm/run_susy_hodge_N14_v7_array.sbatch` and `submit_susy_hodge_N14_v7.sh`: safe production and prediction-only dependency chain; no automatic unseal.
- Create focused tests named `test_susy_cohomology_v7.py`, `test_hodge_response_v7.py`, `test_hodge_wick_v7.py`, `test_susy_hodge_runner_v7.py`, `test_susy_hodge_analysis_v7.py`, and `test_susy_hodge_delivery_v7.py`.
- Generate outputs under `01_task_folder/task_05/script/output/susy_hodge_v7_*` and `susy_hodge_v7_checkpoints/`; do not commit bulk frames or response arrays.

---

### Task 1: Cubic charge-resolved cochain complex

**Files:**
- Create: `01_task_folder/task_05/script/lgeth/susy_cohomology.py`
- Test: `01_task_folder/task_05/script/tests/test_susy_cohomology_v7.py`

**Interfaces:**
- Produces: `charge_basis(N: int, charge: int) -> tuple[int, ...]`, `cubic_triples(N: int) -> tuple[tuple[int,int,int], ...]`, `cubic_supercharge(N: int, charge: int, couplings: np.ndarray) -> scipy.sparse.csr_matrix`, `charge_hamiltonian(...) -> csr_matrix`, `expected_generic_bps_rank(N: int, charge: int) -> int`, and `solve_bps_frame(...) -> BPSFrame`.
- `BPSFrame` fields: `basis`, `projector_frame`, `complement_frame`, `positive_energies`, `gap`, `kernel_residual`, `orthogonality_error`, `expected_rank`, `q_in`, and `q_out`.

- [ ] **Step 1: Write the failing algebra tests**

```python
def test_cubic_supercharge_is_nilpotent_and_has_registered_bps_rank():
    rng = np.random.default_rng(7)
    couplings = rng.normal(size=20) + 1j * rng.normal(size=20)
    q1 = cubic_supercharge(6, 1, couplings)
    q4 = cubic_supercharge(6, 4, couplings)
    assert np.linalg.norm((q4 @ q1).toarray()) < 1e-12
    frame = solve_bps_frame(6, 3, couplings, dense_cutoff=64)
    assert frame.projector_frame.shape == (20, 18)
    assert frame.gap > 0.0
    assert frame.kernel_residual < 1e-10
```

- [ ] **Step 2: Run the focused test and verify the missing-module failure**

Run: `PYTHONPATH=01_task_folder/task_05/script pytest -q 01_task_folder/task_05/script/tests/test_susy_cohomology_v7.py`

Expected: collection fails because `lgeth.susy_cohomology` does not exist.

- [ ] **Step 3: Implement fermionic creation signs and sparse supercharges**

Use sorted bit-string bases and apply the ordered operator product from right to left:

```python
def _create(state: int, mode: int) -> tuple[int, int] | None:
    bit = 1 << mode
    if state & bit:
        return None
    sign = -1 if (state & (bit - 1)).bit_count() % 2 else 1
    return state | bit, sign
```

Build `Q_r: H_r -> H_{r+3}` in COO form, convert to CSR, and define

```python
h_r = q_in @ q_in.getH() + q_out.getH() @ q_out
```

Solve the reduced dense cases with `scipy.linalg.eigh`; classify eigenvalues relative to `max(1.0, max_eigenvalue) * 1e-11`; verify the expected rank rather than inferring the scientific rank from a tolerance.

- [ ] **Step 4: Run the algebra tests**

Run: `PYTHONPATH=01_task_folder/task_05/script pytest -q 01_task_folder/task_05/script/tests/test_susy_cohomology_v7.py`

Expected: all tests pass for basis counts, Hermiticity, positivity, nilpotency, central/adjacent rank formulas, and deterministic frames.

- [ ] **Step 5: Commit the cochain backend**

```bash
git add 01_task_folder/task_05/script/lgeth/susy_cohomology.py 01_task_folder/task_05/script/tests/test_susy_cohomology_v7.py
git commit -m "feat: add charge-resolved SUSY cochain backend"
```

### Task 2: Exact/coexact Hodge response theorem

**Files:**
- Create: `01_task_folder/task_05/script/lgeth/hodge_response.py`
- Test: `01_task_folder/task_05/script/tests/test_hodge_response_v7.py`

**Interfaces:**
- Consumes: `BPSFrame`, `cubic_supercharge`, and an $m\times\binom N3$ tangent array.
- Produces: `HodgeResponse(minus: np.ndarray, plus: np.ndarray, total: np.ndarray, direct: np.ndarray, checks: dict[str,bool])` and `hodge_response(frame, couplings, tangents) -> HodgeResponse` with arrays shaped `(m, dim(H_r), D)`.

- [ ] **Step 1: Write failing response-identity tests**

```python
def test_hodge_branches_are_orthogonal_and_equal_direct_resolvent():
    frame, couplings, tangent = reduced_generic_case(N=6, charge=3, seed=11)
    result = hodge_response(frame, couplings, tangent[None, :])
    assert np.linalg.norm(result.minus[0].conj().T @ result.plus[0]) < 1e-10
    assert np.allclose(result.total, result.minus + result.plus, atol=1e-10)
    assert np.allclose(result.total, result.direct, atol=1e-10)
```

Add a centered finite-difference test for the projector derivative `dP = X P^† + P X^†` at step sizes `2e-5` and `1e-5`; require the error ratio to be compatible with second-order convergence and the smaller-step relative error below `2e-5`.

- [ ] **Step 2: Run the test to confirm failure**

Run: `PYTHONPATH=01_task_folder/task_05/script pytest -q 01_task_folder/task_05/script/tests/test_hodge_response_v7.py`

Expected: collection fails because `hodge_response` is undefined.

- [ ] **Step 3: Implement branch right-hand sides and pseudoinverse action**

For tangent supercharges `dq_in` and `dq_out`, compute

```python
rhs_minus = q_in @ dq_in.getH() @ P
rhs_plus = q_out.getH() @ dq_out @ P
solve = U @ ((U.conj().T @ rhs) / energies[:, None])
x_minus = -solve(rhs_minus)
x_plus = -solve(rhs_plus)
```

Compute the direct derivative from `dH = dq_in @ q_in.H + q_in @ dq_in.H + dq_out.H @ q_out + q_out.H @ dq_out` and require branch sum agreement. Do not project away a failed residual.

- [ ] **Step 4: Run response and cochain regressions**

Run: `PYTHONPATH=01_task_folder/task_05/script pytest -q 01_task_folder/task_05/script/tests/test_susy_cohomology_v7.py 01_task_folder/task_05/script/tests/test_hodge_response_v7.py`

Expected: all tests pass.

- [ ] **Step 5: Commit the response theorem**

```bash
git add 01_task_folder/task_05/script/lgeth/hodge_response.py 01_task_folder/task_05/script/tests/test_hodge_response_v7.py
git commit -m "feat: implement exact SUSY Hodge response"
```

### Task 3: Physical tangent panels and safe Hodge signature

**Files:**
- Modify: `01_task_folder/task_05/script/lgeth/hodge_response.py`
- Modify: `01_task_folder/task_05/script/tests/test_hodge_response_v7.py`

**Interfaces:**
- Produces: `project_moduli_tangents(couplings, candidates)`, `coupling_panels(couplings, panel_size, seed) -> dict[str,np.ndarray]`, `HodgeSignature`, and `hodge_signature(response) -> HodgeSignature`.
- `HodgeSignature` records full nonnegative branch target spectra, positive complement spectra, branch weights, Hodge balance, effective ranks, spectral entropies, and orthogonality residual.

- [ ] **Step 1: Add failing tangent and signature tests**

```python
def test_registered_panels_remove_radial_phase_and_have_full_support():
    couplings = normalized_couplings(8, seed=13)
    panels = coupling_panels(couplings, panel_size=8, seed=17)
    assert set(panels) == {"sparse", "isotropic"}
    for values in panels.values():
        assert values.shape == (8, 56)
        assert np.max(np.abs(values @ couplings.conj())) < 1e-12
        assert np.allclose(values @ values.conj().T, np.eye(8), atol=1e-12)
```

Test `eta_H=0` for a one-sided synthetic response, `eta_H=1` for equal branch weights, invariance under independent ambient and target unitary rotations, and rejection of a singular eight-channel panel.

- [ ] **Step 2: Run tests and observe the missing-interface failure**

Run: `PYTHONPATH=01_task_folder/task_05/script pytest -q 01_task_folder/task_05/script/tests/test_hodge_response_v7.py`

- [ ] **Step 3: Implement complex moduli projection and deterministic QR**

Use the complex projection

```python
projected = candidates - np.outer(candidates @ couplings.conj(), couplings)
q, r = np.linalg.qr(projected.T, mode="reduced")
phases = np.exp(-1j * np.angle(np.diag(r)))
tangents = (q * phases[None, :]).T
```

The one complex direction removed spans both real radial and phase directions. Select sparse coordinates from a deterministic permutation and generate isotropic candidates from an independent RNG stream.

- [ ] **Step 4: Run the focused response suite**

Run: `PYTHONPATH=01_task_folder/task_05/script pytest -q 01_task_folder/task_05/script/tests/test_hodge_response_v7.py`

- [ ] **Step 5: Commit the safe signature layer**

```bash
git add 01_task_folder/task_05/script/lgeth/hodge_response.py 01_task_folder/task_05/script/tests/test_hodge_response_v7.py
git commit -m "feat: add SUSY tangent panels and Hodge signatures"
```

### Task 4: Hodge-resolved covariance-matched Gaussian null

**Files:**
- Create: `01_task_folder/task_05/script/lgeth/hodge_wick.py`
- Test: `01_task_folder/task_05/script/tests/test_hodge_wick_v7.py`

**Interfaces:**
- Consumes: branch spectra/weights from `HodgeSignature` and `covariance_matched_wick` from the immutable `lgeth.wick_channels` module.
- Produces: `sample_hodge_gaussian_channels(signature, channel_count, rng) -> np.ndarray`, `hodge_gaussian_r4_reference(signature, channel_count, samples, seed) -> np.ndarray`, and `complete_realization_null(signatures, samples, seed) -> np.ndarray`.

- [ ] **Step 1: Write failing Gaussian-null tests**

```python
def test_one_sided_hodge_sampler_matches_existing_distribution():
    signature = synthetic_signature(minus_weight=1.0, plus_weight=0.0)
    first = hodge_gaussian_r4_reference(signature, 8, 512, 23)
    second = gaussian_r4_reference(
        signature.minus_target_positive,
        signature.minus_external_positive,
        8,
        512,
        23,
    )
    assert abs(np.median(first) - np.median(second)) < 0.015
```

Also test deterministic seeds, nonnegative spectra, branch-weight rescaling invariance after channel whitening, and direct-sum output shape.

- [ ] **Step 2: Run tests and confirm failure**

Run: `PYTHONPATH=01_task_folder/task_05/script pytest -q 01_task_folder/task_05/script/tests/test_hodge_wick_v7.py`

- [ ] **Step 3: Implement the signed two-branch sampler**

For each nonzero branch, normalize its target/external spectra, generate complex standard Gaussian entries, apply square-root spectra, rotate the target by a deterministic Haar unitary drawn from the null RNG, scale by the square root of the branch weight fraction, concatenate branches along the external axis, and call the unchanged `covariance_matched_wick` implementation. If exactly one branch has positive weight, dispatch directly to the existing one-sided sampler.

- [ ] **Step 4: Run null and immutable Wick regressions**

Run: `PYTHONPATH=01_task_folder/task_05/script pytest -q 01_task_folder/task_05/script/tests/test_hodge_wick_v7.py 01_task_folder/task_05/script/tests/test_wick_channels_v3.py`

- [ ] **Step 5: Commit the Hodge null**

```bash
git add 01_task_folder/task_05/script/lgeth/hodge_wick.py 01_task_folder/task_05/script/tests/test_hodge_wick_v7.py
git commit -m "feat: add Hodge-resolved Gaussian response null"
```

### Task 5: Split-checkpoint runner and information barrier

**Files:**
- Create: `01_task_folder/task_05/script/run_susy_hodge_geometric_eth_v7.py`
- Test: `01_task_folder/task_05/script/tests/test_susy_hodge_runner_v7.py`

**Interfaces:**
- Produces: `prepare_realization(N, sector, realization, ...)`, `run_panel(...)`, `write_safe_covariates(...)`, `seal_file_hash(...)`, `write_prediction(...)`, and `unseal_outcomes(...)`.
- Registered constants: `SIZES=(8,10,12,14)`, `SECTORS=("central","adjacent")`, `PANEL_KINDS=("sparse","isotropic")`, `PANEL_SIZE=8`, realization counts `{8:64,10:48,12:32,14:24}`, and `NULL_REPLICATES=2000`.

- [ ] **Step 1: Write the reduced split/seal test**

```python
def test_reduced_susy_runner_keeps_r4_out_of_safe_artifacts(tmp_path):
    prepare_realization(6, "central", 0, root=tmp_path, reduced=True, force=True)
    run_panel(6, "central", 0, "sparse", root=tmp_path, reduced=True, force=True)
    safe = (tmp_path / "N6_central_seed000_sparse_v7.json").read_text()
    outcome = (tmp_path / "N6_central_seed000_sparse_v7.outcome.json").read_text()
    assert "R4" not in safe and "four_point" not in safe and "connected" not in safe
    assert '"R4"' in outcome
```

Require `unseal_outcomes` to fail before a seal exists, after a one-byte prediction mutation, and after an outcome identity mutation.

- [ ] **Step 2: Run the runner test and verify failure**

Run: `PYTHONPATH=01_task_folder/task_05/script pytest -q 01_task_folder/task_05/script/tests/test_susy_hodge_runner_v7.py`

- [ ] **Step 3: Implement atomic, source-hashed checkpoints**

Follow the v6 continuum runner's `_atomic_json`, `_atomic_npz`, identity hash, array hash, and seal validation patterns in a new file. Serialize branch matrices only in NPZ; serialize derived safe scalars/spectra in JSON. Write the outcome sidecar only after all response identities pass, and never load it from a safe aggregation function.

- [ ] **Step 4: Run reduced runner plus Hodge suites**

Run: `PYTHONPATH=01_task_folder/task_05/script pytest -q 01_task_folder/task_05/script/tests/test_susy_hodge_runner_v7.py 01_task_folder/task_05/script/tests/test_susy_cohomology_v7.py 01_task_folder/task_05/script/tests/test_hodge_response_v7.py 01_task_folder/task_05/script/tests/test_hodge_wick_v7.py`

- [ ] **Step 5: Commit the information barrier**

```bash
git add 01_task_folder/task_05/script/run_susy_hodge_geometric_eth_v7.py 01_task_folder/task_05/script/tests/test_susy_hodge_runner_v7.py
git commit -m "feat: enforce sealed SUSY Hodge response outcomes"
```

### Task 6: Analytic decomposable-three-form control

**Files:**
- Modify: `01_task_folder/task_05/script/lgeth/susy_cohomology.py`
- Modify: `01_task_folder/task_05/script/lgeth/hodge_response.py`
- Modify: `01_task_folder/task_05/script/tests/test_susy_cohomology_v7.py`
- Modify: `01_task_folder/task_05/script/tests/test_hodge_response_v7.py`

**Interfaces:**
- Produces: `decomposable_couplings(N, alpha)`, `decomposable_tangent(N, family, site)`, and `analytic_decomposable_curvature_multiplicities(N, charge, kind)`.

- [ ] **Step 1: Add failing atomic-spectrum tests**

At $C_{123}=\alpha$ and all other couplings zero, compute diagonal tangent $(12k)$ and off-diagonal Hermitian combination $(12k),(13l)$. Assert every numerical curvature eigenvalue lies within `1e-10` of `{-1/alpha**2, 0, 1/alpha**2}` and the nonzero multiplicities match Appendix D.2 of the seed paper.

- [ ] **Step 2: Run the control tests and verify failure**

Run: `PYTHONPATH=01_task_folder/task_05/script pytest -q 01_task_folder/task_05/script/tests/test_susy_cohomology_v7.py 01_task_folder/task_05/script/tests/test_hodge_response_v7.py`

- [ ] **Step 3: Implement the exact control and multiplicity formulas**

Generate the decomposable coupling vector by the canonical triple lookup. Construct curvature from the response branches as the antisymmetrized Gram combination and compare it with the analytic $0,\pm1/\alpha^2$ support. Preserve zero eigenvalues rather than removing them in this structural test.

- [ ] **Step 4: Run all v7 unit tests**

Run: `PYTHONPATH=01_task_folder/task_05/script pytest -q $(rg --files 01_task_folder/task_05/script/tests | rg 'v7\.py$')`

- [ ] **Step 5: Commit the analytic negative control**

```bash
git add 01_task_folder/task_05/script/lgeth/susy_cohomology.py 01_task_folder/task_05/script/lgeth/hodge_response.py 01_task_folder/task_05/script/tests/test_susy_cohomology_v7.py 01_task_folder/task_05/script/tests/test_hodge_response_v7.py
git commit -m "test: certify decomposable SUSY curvature atoms"
```

### Task 7: Sequential $N=8,10,12$ pilot production

**Files:**
- Modify: `01_task_folder/task_05/script/run_susy_hodge_geometric_eth_v7.py`
- Create: `01_task_folder/task_05/script/tests/test_susy_hodge_pilot_v7.py`

**Interfaces:**
- Produces: `script/output/susy_hodge_v7_covariates_pilot.json`, `susy_hodge_v7_outcomes_pilot.{json,npz}`, and per-realization checkpoints.

- [ ] **Step 1: Add a reduced aggregation test**

Generate two reduced realizations in each sector and panel kind. Require complete case grids, finite physical and both-null $R_4$ arrays, full source identity, complete-realization grouping, and deterministic regeneration.

- [ ] **Step 2: Run the reduced pilot test**

Run: `PYTHONPATH=01_task_folder/task_05/script pytest -q 01_task_folder/task_05/script/tests/test_susy_hodge_pilot_v7.py`

- [ ] **Step 3: Implement resumable pilot aggregation**

Use independent seeds derived from `(VERSION, N, sector, realization, purpose)`. The safe aggregate must be written before any pilot outcome aggregate. Opening pilot outcomes is allowed only after every kernel, gap, Hodge, panel-support, gauge, and source-hash gate passes.

- [ ] **Step 4: Run the registered local sizes sequentially**

Run:

```bash
PYTHONPATH=01_task_folder/task_05/script python 01_task_folder/task_05/script/run_susy_hodge_geometric_eth_v7.py pilot --sizes 8 10 12
```

Expected: 64/48/32 complete disorder realizations per sector and both panel kinds, with safe artifacts written before the pilot outcome aggregate.

- [ ] **Step 5: Run v7 regressions and commit compact pilot code/metadata**

```bash
PYTHONPATH=01_task_folder/task_05/script pytest -q $(rg --files 01_task_folder/task_05/script/tests | rg 'v7\.py$')
git add 01_task_folder/task_05/script/run_susy_hodge_geometric_eth_v7.py 01_task_folder/task_05/script/tests/test_susy_hodge_pilot_v7.py
git commit -m "data: complete SUSY Hodge pilot sequence"
```

Do not stage bulk checkpoint NPZ files.

### Task 8: Sealed $N=14$ prediction and Slurm workflow

**Files:**
- Create: `01_task_folder/task_05/script/analyze_susy_hodge_geometric_eth_v7.py`
- Create: `01_task_folder/task_05/script/slurm/run_susy_hodge_N14_v7_array.sbatch`
- Create: `01_task_folder/task_05/script/slurm/submit_susy_hodge_N14_v7.sh`
- Test: `01_task_folder/task_05/script/tests/test_susy_hodge_analysis_v7.py`

**Interfaces:**
- Produces: `write_n14_prediction(covariates, ...)`, `score_unsealed_n14(...)`, `susy_hodge_v7_N14_prediction.json`, and `susy_hodge_v7_N14_prediction.sha256`.

- [ ] **Step 1: Write failing prediction-before-outcome tests**

Use synthetic safe covariates and hidden sidecars. Assert prediction creation succeeds when sidecars are unreadable, the serialized prediction contains no physical $R_4$, scoring fails without a valid SHA-256 seal, and the primary simultaneous pair is central/adjacent sparse panels only.

- [ ] **Step 2: Run analysis tests and verify failure**

Run: `PYTHONPATH=01_task_folder/task_05/script pytest -q 01_task_folder/task_05/script/tests/test_susy_hodge_analysis_v7.py`

- [ ] **Step 3: Implement complete-realization prediction intervals and frozen branch logic**

For each of 2000 reference replicates, draw one covariance-conditioned Gaussian tensor per disorder realization and take the realization median. Use per-case 97.5% intervals for the two-case primary pair. Score `strong_covariance_universality`, `hodge_resolved_geometric_eth`, `cohomological_non_gaussian_class`, `structured_cohomology`, or `feasibility_failure` exactly as frozen in the design.

- [ ] **Step 4: Implement the scheduler stop point**

The array maps 24 realizations × two sectors × two panel kinds. The dependent aggregate writes safe covariates and the two numerical null predictions, seals the JSON, prints the seal, and exits. The submission script must not invoke the unseal subcommand.

- [ ] **Step 5: Run tests, shell syntax checks, and submit when the remote allocation is live**

```bash
PYTHONPATH=01_task_folder/task_05/script pytest -q 01_task_folder/task_05/script/tests/test_susy_hodge_analysis_v7.py 01_task_folder/task_05/script/tests/test_susy_hodge_runner_v7.py
bash -n 01_task_folder/task_05/script/slurm/submit_susy_hodge_N14_v7.sh
```

After the prediction seal is independently visible, run the separate unseal command and commit only code, compact JSON summaries, and seals:

```bash
git add 01_task_folder/task_05/script/analyze_susy_hodge_geometric_eth_v7.py 01_task_folder/task_05/script/slurm/run_susy_hodge_N14_v7_array.sbatch 01_task_folder/task_05/script/slurm/submit_susy_hodge_N14_v7.sh 01_task_folder/task_05/script/tests/test_susy_hodge_analysis_v7.py
git commit -m "analysis: seal SUSY Hodge held-out prediction"
```

### Task 9: Inference figure and source-backed result report

**Files:**
- Create: `01_task_folder/task_05/script/make_susy_hodge_figure_v7.py`
- Create: `01_task_folder/task_05/script/tests/test_susy_hodge_figure_v7.py`
- Generate: `01_task_folder/task_05/script/output/figure_susy_hodge_geometric_eth_v7.{pdf,png,json}`
- Generate: `01_task_folder/task_05/script/output/susy_hodge_geometric_eth_report_v7.md`

**Interfaces:**
- Consumes only accepted pilot inference, sealed $N=14$ inference, decomposable-control audit, and immutable v6 cross-parent report.
- Produces a four-panel figure: response-complex schematic; Hodge balance/effective-rank flow; physical versus collapsed/Hodge null; and held-out branch/structured-control verdict.

- [ ] **Step 1: Write failing figure/report provenance tests**

Require every plotted scalar to be recoverable from hashed JSON/NPZ input, the selected branch to appear verbatim in figure JSON and report, the literature links to be clickable Markdown, and the report to contain established/not-established sections.

- [ ] **Step 2: Run figure tests and confirm missing outputs**

Run: `PYTHONPATH=01_task_folder/task_05/script pytest -q 01_task_folder/task_05/script/tests/test_susy_hodge_figure_v7.py`

- [ ] **Step 3: Implement generated assets**

Use uncertainty bands from complete realizations, distinguish pilot from held-out points visually, mark the prediction-seal boundary, and place the analytic decomposable control in a separate style. Do not draw an asymptotic fit unless the registered $N=16$ separation gate later passes.

- [ ] **Step 4: Generate and visually inspect both PDF and PNG**

```bash
PYTHONPATH=01_task_folder/task_05/script python 01_task_folder/task_05/script/make_susy_hodge_figure_v7.py
pdftoppm -png -r 180 -f 1 -singlefile 01_task_folder/task_05/script/output/figure_susy_hodge_geometric_eth_v7.pdf tmp/susy_hodge_v7_figure
```

Inspect `tmp/susy_hodge_v7_figure.png` at original resolution and correct clipping, overlaps, unreadable labels, or misleading axes before acceptance.

- [ ] **Step 5: Commit code and compact publication artifacts**

```bash
git add 01_task_folder/task_05/script/make_susy_hodge_figure_v7.py 01_task_folder/task_05/script/tests/test_susy_hodge_figure_v7.py 01_task_folder/task_05/script/output/figure_susy_hodge_geometric_eth_v7.pdf 01_task_folder/task_05/script/output/figure_susy_hodge_geometric_eth_v7.png 01_task_folder/task_05/script/output/figure_susy_hodge_geometric_eth_v7.json 01_task_folder/task_05/script/output/susy_hodge_geometric_eth_report_v7.md
git commit -m "docs: report Hodge-resolved geometric ETH verdict"
```

### Task 10: Fail-closed delivery audit and dashboard synchronization

**Files:**
- Create: `01_task_folder/task_05/script/verify_susy_hodge_delivery_v7.py`
- Create: `01_task_folder/task_05/script/tests/test_susy_hodge_delivery_v7.py`
- Modify: `01_task_folder/task_05/task_05_dashboard.md`
- Modify: `00_main/main_dashboard.md`

**Interfaces:**
- Produces: `script/output/susy_hodge_delivery_audit_v7.json` with individual checks and one top-level `passed` boolean.

- [ ] **Step 1: Write the failing delivery and corruption tests**

Require exact registered case grids, all source/array/seal hashes, no safe-outcome leakage, prediction timestamp before unseal timestamp, analytic curvature atoms, one-sided regression, selected branch consistency, figure/report provenance, and the complete v7 pytest command. Copy accepted metadata to a temporary directory, corrupt one seal and one safe JSON key, and require both audits to fail.

- [ ] **Step 2: Run the delivery test and confirm failure**

Run: `PYTHONPATH=01_task_folder/task_05/script pytest -q 01_task_folder/task_05/script/tests/test_susy_hodge_delivery_v7.py`

- [ ] **Step 3: Implement the audit and one-command verifier**

The verifier must recompute branch selection from arrays rather than trust the report, scan safe serialized data for forbidden keys, compare every referenced SHA-256, and include exact test counts and result provenance in its JSON.

- [ ] **Step 4: Run the complete v7 and immutable v6 regressions**

```bash
PYTHONPATH=01_task_folder/task_05/script pytest -q $(rg --files 01_task_folder/task_05/script/tests | rg '(v6|v7)\.py$')
PYTHONPATH=01_task_folder/task_05/script python 01_task_folder/task_05/script/verify_susy_hodge_delivery_v7.py
```

- [ ] **Step 5: Synchronize dashboards and commit the delivery**

Append a `[Codex]` version-log entry with the selected branch, main numerical intervals, source hashes, prediction seal, test count, report, and figure. Embed `![Hodge-resolved Geometric ETH](script/output/figure_susy_hodge_geometric_eth_v7.png)` in the task canvas and add the same status/result to the main session log. Keep both statuses `🟡 Ongoing` unless the human explicitly closes the task.

```bash
git add 01_task_folder/task_05/script/verify_susy_hodge_delivery_v7.py 01_task_folder/task_05/script/tests/test_susy_hodge_delivery_v7.py 01_task_folder/task_05/script/output/susy_hodge_delivery_audit_v7.json
git commit -m "science: deliver Hodge-resolved SUSY benchmark"
```

## Self-review result

- **Spec coverage:** The ten tasks cover the cubic cochain, expected BPS ranks, exact/coexact theorem, tangent panels, pre-outcome Hodge signature, two competing nulls, information barrier, decomposable control, sequential pilot, sealed $N=14$, branch inference, figure/report, corruption tests, and dashboard delivery. The conditional $N=16$ extension remains gated exactly as specified rather than being silently omitted.
- **Placeholder scan:** No red-flag placeholder or unspecified error-handling step remains. Every code task has a named failing test, exact command, implementation rule, passing command, and commit boundary.
- **Type consistency:** `BPSFrame` flows from `susy_cohomology` into `hodge_response`; `HodgeSignature` flows into `hodge_wick` and the safe runner; only the analyzer may validate a seal and open outcome sidecars; figure and delivery scripts consume the analyzer's accepted artifacts.

## Execution handoff

Plan saved at `docs/plans/2026-08-01-susy-cohomological-geometric-eth-implementation-plan.md`. Execution mode is **inline**: the human already authorized execution with “做吧,” and the active repository instructions prohibit unrequested subagent delegation. Work proceeds task by task with the commit and regression checkpoints above.
