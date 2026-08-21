# Moore--Read Geometric ETH v9 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and audit a continuum-LLL coherent-state-factorized three-body Moore--Read parent with growing quasihole zero-mode spaces, then apply the established protected-response and covariance-complete Geometric-ETH tests.

**Architecture:** A new task-local factor (C_3) evaluates normalized three-boson annihilation over the complete (n_\phi^2) magnetic-translation orbit of a continuum-LLL coherent state, so (H=C_3^\dagger C_3) is positive and frustration free. This replacement is required by the opened small-size gate: the minimal high-flux-density Kapit--Mueller lattice had insufficient independent constraints and produced extra zero modes, whereas the coherent-state factor matches cyclic ((2,2)) counts. Kernel frames are solved with the existing factor-only eigensolver; parent-preserving one-body transports give exact response matrices through the existing intertwiner theorem.

**Tech Stack:** Python 3, NumPy, SciPy sparse matrices and LOBPCG, pytest, existing `lgeth` response/Wick modules, Slurm.

## Global Constraints

- The implementation remains inside task_05 and does not import task_04's clustered-root code.
- The normalized local constraint is (C_x=b_x^3/\sqrt{3!}), including exact occupation and multinomial factors.
- Registered base families use even particle number and even flux with (n_\phi\ge N); quasihole sequences are selected by script-computed cyclic ((2,2)) root counts.
- A numerical kernel is accepted only when observed nullity equals the cyclic ((2,2)) count, the internal bandwidth and residual pass tolerance, and the external gap is positive.
- The pilot is opened data. A later largest-size case is prospective and may not be opened before the smaller-size inference file and seal exist.
- Existing `lgeth` v4--v8 functions are reused without semantic changes.

---

### Task 1: Exact ((2,2)) root count in task_05

**Files:**
- Modify: `01_task_folder/task_05/script/lgeth/combinatorics.py`
- Create: `01_task_folder/task_05/script/tests/test_moore_read_parent_v9.py`

**Interfaces:**
- Produces: `clustered_zero_mode_count(n_particles: int, n_flux: int, k: int = 2, r: int = 2) -> int`.
- Consumes: `occupation_states` and `cyclic_kr_admissible` from the same module.

- [ ] **Step 1: Write the failing count and validation tests**

```python
def test_clustered_zero_mode_count_matches_direct_enumeration() -> None:
    expected = sum(
        cyclic_kr_admissible(state, k=2, r=2)
        for state in occupation_states(4, 6)
    )
    assert clustered_zero_mode_count(4, 6) == expected

def test_clustered_zero_mode_count_rejects_overfilled_torus() -> None:
    with pytest.raises(ValueError, match="n_flux"):
        clustered_zero_mode_count(7, 6)
```

- [ ] **Step 2: Run the tests and verify the missing symbol failure**

Run: `python3 -m pytest tests/test_moore_read_parent_v9.py -q`

Expected: collection fails because `clustered_zero_mode_count` is not defined.

- [ ] **Step 3: Implement the exact enumerator**

```python
def clustered_zero_mode_count(
    n_particles: int,
    n_flux: int,
    k: int = 2,
    r: int = 2,
) -> int:
    particles = int(n_particles)
    flux = int(n_flux)
    if particles <= 0 or flux <= 0 or flux * int(k) < particles * int(r):
        raise ValueError("n_flux is incompatible with the clustered filling")
    return sum(
        cyclic_kr_admissible(state, k=int(k), r=int(r))
        for state in occupation_states(particles, flux)
    )
```

- [ ] **Step 4: Run the focused tests and existing combinatorics tests**

Run: `python3 -m pytest tests/test_moore_read_parent_v9.py tests/test_independent_core.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add 01_task_folder/task_05/script/lgeth/combinatorics.py 01_task_folder/task_05/script/tests/test_moore_read_parent_v9.py
git commit -m "feat: add Moore-Read root counting"
```

### Task 2: Projected three-body parent factor

**Files:**
- Create: `01_task_folder/task_05/script/lgeth/moore_read_parent.py`
- Modify: `01_task_folder/task_05/script/tests/test_moore_read_parent_v9.py`

**Interfaces:**
- Produces: `ContinuumMooreReadParent`, `three_body_annihilation_constraints(basis, coefficient_frame, onsite_u=1.0, amplitude_cutoff=1e-14)`, `coherent_state_constraint_frame(n_flux)`, and `build_continuum_moore_read_parent(n_particles, n_flux)`.
- Consumes: `BosonBasis`, `guiding_center_coherent_state`, and task-local combinatorics.

- [ ] **Step 1: Add direct occupation-factor tests**

```python
def test_three_body_single_orbital_normalization() -> None:
    basis = BosonBasis(1, 3)
    constraints, intermediate = three_body_annihilation_constraints(
        basis, np.ones((1, 1), dtype=complex)
    )
    assert intermediate.n_particles == 0
    assert constraints.shape == (1, 1)
    assert np.allclose(constraints.toarray(), [[1.0]])

def test_three_body_constraint_matches_explicit_field_cube() -> None:
    basis = BosonBasis(3, 3)
    frame = np.asarray([[1.0, 2.0, -0.5]], dtype=complex)
    constraints, _ = three_body_annihilation_constraints(basis, frame)
    expected = explicit_normalized_field_cube_row(basis, frame[0])
    assert np.allclose(constraints.toarray()[0], expected)
```

- [ ] **Step 2: Verify the new tests fail because the module is absent**

Run: `python3 -m pytest tests/test_moore_read_parent_v9.py -q`

Expected: import failure for `lgeth.moore_read_parent`.

- [ ] **Step 3: Implement the sparse factor**

Implement the three disjoint occupation patterns with coefficients

```python
prefactor = np.sqrt(float(onsite_u) / 6.0)
aaa = prefactor * f_i**3 * np.sqrt(n_i * (n_i - 1) * (n_i - 2))
aab = 3.0 * prefactor * f_i**2 * f_j * np.sqrt(n_i * (n_i - 1) * n_j)
abc = 6.0 * prefactor * f_i * f_j * f_k * np.sqrt(n_i * n_j * n_k)
```

Stack physical-site rows as `site * intermediate.dimension + state_index`, sum duplicates, eliminate zeros, and return CSR.

- [ ] **Step 4: Implement the scalable builder**

```python
def build_continuum_moore_read_parent(
    n_particles: int,
    n_flux: int,
    *,
    image_cutoff: int = 8,
) -> ContinuumMooreReadParent:
    # Stack all magnetic translates of one periodic LLL coherent state,
    # apply C_3 at every row, and store only the factor.
```

The dataclass exposes `n_particles`, `n_flux`, `length`, `basis`, `intermediate_basis`, `orbitals`, and `constraints` so existing factorized solvers remain duck-type compatible.

- [ ] **Step 5: Run normalization, Hermiticity, and dimension tests**

Run: `python3 -m pytest tests/test_moore_read_parent_v9.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add 01_task_folder/task_05/script/lgeth/moore_read_parent.py 01_task_folder/task_05/script/tests/test_moore_read_parent_v9.py
git commit -m "feat: build factorized Moore-Read parent"
```

### Task 3: Kernel and transported-family audit

**Files:**
- Modify: `01_task_folder/task_05/script/tests/test_moore_read_parent_v9.py`
- Create: `01_task_folder/task_05/script/lgeth/moore_read_audit.py`

**Interfaces:**
- Produces: `MooreReadAudit` and `audit_moore_read_case(N, n_flux, seed=...) -> MooreReadAudit`.
- Consumes: `solve_kernel_frame_factored`, `transported_kernel_frame`, `projected_local_generator_pair`, and `analytic_protected_generator_response`.

- [ ] **Step 1: Write the failing exact-nullity test**

```python
def test_small_moore_read_parent_matches_clustered_count() -> None:
    audit = audit_moore_read_case(4, 6, 0.17, 0.29, seed=2026081601)
    assert audit.expected_rank == audit.observed_rank
    assert audit.internal_bandwidth < 1e-9
    assert audit.external_gap > 0.0
    assert audit.kernel_residual < 1e-7
```

- [ ] **Step 2: Write protected-motion tests**

```python
def test_moore_read_transport_moves_projector_without_splitting() -> None:
    audit = audit_moore_read_case(4, 6, 0.17, 0.29, seed=2026081601)
    assert audit.generator_commutator_norm > 1e-8
    assert audit.projector_distance > 1e-8
    assert audit.transported_constraint_residual < 1e-8
    assert audit.tangent_fiber_norm < 1e-8
```

- [ ] **Step 3: Implement the audit with script-generated tolerances and raw values**

Use `ManyBodyCase(expected_rank=clustered_zero_mode_count(...))`, solve the complete factor kernel, build two projected local generators, transport the frame at a fixed small parameter, rebuild `C_3` from the transformed coefficient frame, and measure every gate directly.

- [ ] **Step 4: Run focused tests**

Run: `python3 -m pytest tests/test_moore_read_parent_v9.py tests/test_protected_generator_response_v6.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add 01_task_folder/task_05/script/lgeth/moore_read_audit.py 01_task_folder/task_05/script/tests/test_moore_read_parent_v9.py
git commit -m "test: certify Moore-Read protected geometry"
```

### Task 4: Checkpointed pilot and production runner

**Files:**
- Create: `01_task_folder/task_05/script/run_moore_read_geometric_eth_v9.py`
- Create: `01_task_folder/task_05/script/tests/test_moore_read_runner_v9.py`
- Create: `01_task_folder/task_05/script/slurm/run_moore_read_geometric_eth_v9.sbatch`

**Interfaces:**
- Produces CLI modes `--audit`, `--prepare-kernel`, `--panel`, `--aggregate`, and `--preflight`; outputs versioned JSON/NPZ shards.
- Consumes the v9 parent/audit modules and existing local/Fourier panel, response, Wick, and complete-covariance functions.

- [ ] **Step 1: Write failing registration tests**

```python
def test_opened_pilot_and_prospective_cases_are_disjoint() -> None:
    assert set(OPENED_PILOT_CASES).isdisjoint(PROSPECTIVE_CASES)

def test_case_rank_is_generated_from_clustered_rule() -> None:
    case = case_for_particle_number(4, prospective=False)
    assert case.expected_rank == clustered_zero_mode_count(case.N, case.n_flux)
```

- [ ] **Step 2: Implement deterministic case registration**

Register the opened pilot sequence `(N,n_flux)=(4,6),(6,8)`; after measured preflight, register production `(4,6),(6,8),(8,10)` and keep `(10,12)` prospective. The code, not this document, records exact Hilbert and zero-mode dimensions.

- [ ] **Step 3: Implement atomic kernel and panel checkpoints**

Each JSON stores source hashes, case identity, basis dimension, constraint shape/nnz, expected and observed rank, residual, internal bandwidth, external gap, arrays hash, runtime, environment, and individual boolean checks. Each NPZ stores only the arrays needed to reproduce statistics.

- [ ] **Step 4: Implement panel statistics**

For every accepted kernel, evaluate 24 deterministic local panels and one structured Fourier panel with eight tangent labels. Save `WickResult` spectra and the response covariates required by the complete-covariance oracle; do not discard singular or failed panels.

- [ ] **Step 5: Implement runner tests using temporary output roots**

```python
def test_pilot_runner_is_reproducible(tmp_path: Path) -> None:
    first = run_pilot(tmp_path / "first")
    second = run_pilot(tmp_path / "second")
    assert scientific_projection(first) == scientific_projection(second)
    assert first["all_checks_pass"]
```

- [ ] **Step 6: Run focused tests and opened pilot**

Run: `python3 -m pytest tests/test_moore_read_parent_v9.py tests/test_moore_read_runner_v9.py -q`

Run: `python3 run_moore_read_geometric_eth_v9.py --preflight`

Expected: tests pass and preflight emits an audited JSON without opening prospective outcomes.

- [ ] **Step 7: Add Slurm submission envelope**

The sbatch script uses `--account=giggleliu`, the `shen` runtime root from `hpc_runtime_shen.env`, deterministic array indices, explicit memory/time, `PYTHONPATH=.`, and dependency-gated aggregation.

- [ ] **Step 8: Commit**

```bash
git add 01_task_folder/task_05/script/run_moore_read_geometric_eth_v9.py 01_task_folder/task_05/script/tests/test_moore_read_runner_v9.py 01_task_folder/task_05/script/slurm/run_moore_read_geometric_eth_v9.sbatch
git commit -m "feat: run Moore-Read Geometric ETH pilot"
```

### Task 5: Production inference and dashboard delivery

**Files:**
- Create: `01_task_folder/task_05/script/analyze_moore_read_geometric_eth_v9.py`
- Create: `01_task_folder/task_05/script/make_moore_read_geometric_eth_assets_v9.py`
- Create: `01_task_folder/task_05/script/verify_moore_read_geometric_eth_v9.py`
- Create: `01_task_folder/task_05/script/tests/test_moore_read_inference_v9.py`
- Modify: `01_task_folder/task_05/task_05_dashboard.md`
- Modify: `00_main/main_dashboard.md`

**Interfaces:**
- Produces: `output/moore_read_geometric_eth_v9.{json,npz}`, `output/figure_moore_read_geometric_eth_v9.{pdf,png}`, and `output/moore_read_geometric_eth_audit_v9.json`.
- Consumes: all registered v9 shards and existing Laughlin aggregate covariates without altering them.

- [ ] **Step 1: Write failing completeness and no-refit tests**

```python
def test_inference_rejects_missing_registered_panel(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="complete panel grid"):
        analyze(incomplete_fixture(tmp_path))

def test_result_branch_is_one_of_registered_labels() -> None:
    assert select_branch(fixture_summary()) in REGISTERED_BRANCHES
```

- [ ] **Step 2: Seal the smaller-size inference before opening the prospective case**

The seal contains source hashes, registered sizes/panels/seeds, complete-covariance prescription, confidence level, and branch rules. The prospective runner verifies this seal byte-for-byte.

- [ ] **Step 3: Run production and prospective jobs**

Execute locally when measured resources fit; otherwise synchronize the committed branch to the `shen` runtime and submit the registered Slurm chain. Wait for exact kernel/panel closure before aggregation.

- [ ] **Step 4: Generate inference, figure, and audit**

The figure contains zero-mode/gap scaling, local curvature statistics, complete-covariance connected residuals, and structured controls. The audit recomputes every displayed number from versioned JSON/NPZ inputs and fails closed on missing hashes or cases.

- [ ] **Step 5: Run delivery tests and full regression**

Run: `python3 -m pytest tests/test_moore_read_parent_v9.py tests/test_moore_read_runner_v9.py tests/test_moore_read_inference_v9.py -q`

Run: `python3 -m pytest tests -q`

Expected: all tests pass after required ignored LaTeX audit inputs are rebuilt.

- [ ] **Step 6: Synchronize dashboards**

Append a stamped v9 entry, embed the main PNG in task_05 `## Canvas`, link all artifacts, report the selected branch and limitations, update task_05's ledger date, and keep status `🟡 Ongoing`.

- [ ] **Step 7: Commit**

```bash
git add 01_task_folder/task_05/script/analyze_moore_read_geometric_eth_v9.py 01_task_folder/task_05/script/make_moore_read_geometric_eth_assets_v9.py 01_task_folder/task_05/script/verify_moore_read_geometric_eth_v9.py 01_task_folder/task_05/script/tests/test_moore_read_inference_v9.py 01_task_folder/task_05/task_05_dashboard.md 00_main/main_dashboard.md
git commit -m "feat: deliver Moore-Read Geometric ETH results"
```

## Self-Review

- Spec coverage: exact root count, physical three-body parent, growing quasihole kernel, protected noncommuting deformation, common statistics, production sealing, figures, audit, and dashboard delivery all have explicit tasks.
- Placeholder scan: every implementation and verification action is explicit and executable.
- Type consistency: every parent exposes the duck-typed fields used by `solve_kernel_frame_factored` and protected response functions; every response tensor has `(label, ambient, rank)`; every runner output is JSON metadata plus NPZ arrays.
