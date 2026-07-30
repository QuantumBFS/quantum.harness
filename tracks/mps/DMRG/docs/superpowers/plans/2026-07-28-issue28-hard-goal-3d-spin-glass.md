# Issue #28 Hard Goal 3D Spin-Glass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, validate, run, and analyze a 45 x 45 x 45 iid +/-J
Edwards-Anderson spin-glass calculation whose neural VMCRG bias is an actual
trainable local disorder-conditioned MPS/Tensor Train and whose final Tc comes
from independent unbiased finite-size evidence.

**Architecture:** Add an isolated `spinglass3d` package rather than extending
the currently modified two-dimensional `vmcrg_ref` implementation in place.
The package has a NumPy reference path for exact correctness, an optional JAX
accelerator path vectorized over independent disorder/temperature/walker
states, shared immutable artifact schemas, and separate neural-RG and unbiased
FSS workflows. Existing `vmcrg_ref` code is reused only through stable public
helpers for atomic artifacts, autocorrelation, and the Stage 4 2D regression.

**Tech Stack:** Python 3.12, NumPy float64/int8, SciPy, Numba, optional JAX for
A800 acceleration, pytest, matplotlib, TOML via `tomllib`, and the repository's
profile-driven Slurm harness.

## Global Constraints

- The confirmed model is `H_J(s)=-sum_bonds J_ij s_i s_j`, iid
  `P(J_ij=+1)=P(J_ij=-1)=1/2`, cubic periodic boundary conditions, zero field,
  `|J|=k_B=1`, and beta=1/T.
- Every physical overlap uses two independently evolved unbiased real replicas
  with the same quenched J. A biased VMCRG pair is jointly distributed and
  must not be described as independent.
- First RG is 3 x 3 x 3 majority blocking. Second RG is disabled until the
  first-RG Stage 5 and Stage 6 gates pass.
- The global 45^3 or 15^3 lattice must never be represented by one MPS. The TT
  is a trainable local shared density summed over coarse sites.
- Route C is primary: a gauge-invariant disorder-conditioned finite linear
  baseline plus a disorder-conditioned TT residual. Route B is the scientific
  fallback. Route A is an ablation and cannot close the Hard Goal.
- Raw bond signs are forbidden as scalar disorder features. Conditioned models
  use tested spanning-tree gauge fixing or independent loop/plaquette fluxes.
- Exact q -> -q and cubic spatial symmetry must be structural. Data augmentation
  is never labeled exact.
- Unbiased FSS and biased neural VMCRG use disjoint random streams and result
  namespaces. Neural loss is not a Tc estimator.
- Temperatures in one PT ladder are never split into independent Slurm cells.
- Quenched J is the bootstrap/jackknife unit. Measurements within one J are not
  independent disorder samples.
- Any sample failing equilibration is extended under the same J and seed or
  reported failed; it is not replaced.
- Production outputs are immutable and hash-linked. A scheduler exit status is
  operational evidence only.
- Long loops print and flush 10-50 progress estimates and checkpoint within the
  24-hour cluster wall limit.
- Work remains on `challenge/issue28-pure-neural`. Preserve all pre-existing
  dirty files and unrelated LTRG/XY/Easy Goal results.
- Do not commit, push, switch branches, submit production, or change PR state
  until the user authorizes the corresponding later-stage action. Every task
  ends with a diff review instead of a commit.
- Before Stage 7 submission, show exact CPU, accelerator, memory, walltime,
  array count, output estimate, source/config hashes, and recovery strategy,
  then wait for user confirmation.

---

## Stage Milestones

| Milestone | Deliverable | Go condition | No-go consequence |
|---|---|---|---|
| Stage 4 / M4 | Re-run the existing 2D local-MPS regression and a fresh 45 x 45 connectivity cell | Existing MPS tests pass; gradients, canonicalization, local deltas, checkpoint, and frozen target metrics meet the fixed tolerances | Fix the shared MPS/statistics path before creating 3D production kernels |
| Stage 5 / M5 | Exact 2^8 L=2 checks, L=3 transfer check, and small 3D PT/VMCRG validation | Energies, overlap observables, swap detailed balance, 3D RG cache, TT gradients, symmetries, and reference/accelerated trajectories pass | Remain on small systems; second RG stays disabled |
| Stage 6 / M6 | Medium-size performance/equilibration/power pilot and frozen production candidate | Temperature travel, stationarity, ESS, MPS-vs-linear comparison, throughput, memory, and power projection all pass | Adjust the same pilot; do not reduce scientific gates silently |
| Stage 7 / M7 | Approved multi-size production including equilibrated L=45 | User approves exact request; every accepted J manifest passes frozen gates; completion fraction >=0.95 | Extend same cells or report no-go; generated scripts do not count |
| Stage 8 / M8 | Whole-J bootstrap FSS and independent RG-flow analysis | xi_L/L and Binder Tc intervals overlap; neural RG interval is compatible; fit-window systematics are reported | Report inconsistency or underpower without selecting a favorable fit |
| Stage 9 / M9 | Self-contained report, consolidated runner, tests, CI, and review diff | All success clauses are classified and the user approves repository actions | Leave files uncommitted and report the exact remaining failure |

## File and Ownership Map

### New package

| File | Single responsibility |
|---|---|
| `src/spinglass3d/__init__.py` | Narrow public exports and package version |
| `src/spinglass3d/config.py` | Typed TOML loading and cross-field validation |
| `src/spinglass3d/model.py` | Cubic iid +/-J bonds, energy, exact local deltas, color maps |
| `src/spinglass3d/exact.py` | L=2 enumeration and L=3 transfer partition/energy oracle |
| `src/spinglass3d/overlap.py` | Replica pairs, q field, global/spectral overlap measurements |
| `src/spinglass3d/rg.py` | Incremental one- and two-level 3D majority caches |
| `src/spinglass3d/gauge.py` | Local gauge transforms, spanning-tree canonicalization, loop fluxes |
| `src/spinglass3d/templates.py` | Cross, face/edge, cube, and factorized 3^3 token geometry/order |
| `src/spinglass3d/symmetry.py` | O_h permutations, q inversion, explicit group averaging |
| `src/spinglass3d/tensor_train.py` | Variable-length binary TT, gradients, canonicalization, I/O |
| `src/spinglass3d/linear_bias.py` | Even q and flux-conditioned finite operator baseline |
| `src/spinglass3d/bias.py` | Route A/B/C composition and incremental local bias cache |
| `src/spinglass3d/tempering.py` | Unbiased two-ladder and biased paired PT reference kernels |
| `src/spinglass3d/backend.py` | Reference/accelerator backend protocol and resource telemetry |
| `src/spinglass3d/jax_backend.py` | Optional JAX-equivalent batched updates and TT contractions |
| `src/spinglass3d/equilibration.py` | Round trips, log bins, Rhat, IAT/ESS, fail-closed gates |
| `src/spinglass3d/vmcrg.py` | Target/biased gradients, Route C stages, frozen evaluation |
| `src/spinglass3d/checkpoint.py` | Atomic complete optimizer/sampler checkpoints |
| `src/spinglass3d/workflow.py` | Stage/cell execution, manifests, immutable promotion, resume |
| `src/spinglass3d/statistics.py` | Whole-J bootstrap, crossings, correction-aware FSS |
| `src/spinglass3d/rg_flow.py` | Common-gauge effective summaries and flow-change intervals |
| `src/spinglass3d/report.py` | Tables, figures, failure classification, self-contained HTML |

### New scripts and scheduler files

| File | Responsibility |
|---|---|
| `scripts/hard_goal.py` | Consolidated `stage4`, `validate`, `pilot`, `cell`, `analyze`, `report` CLI |
| `scripts/hard_goal_benchmark.py` | Reference/JAX throughput and memory benchmark |
| `scripts/hard_goal_freeze_protocol.py` | Promote a passing pilot into a hash-locked production candidate |
| `jobs/hard_goal_array.slurm` | Profile-neutral array wrapper around one full-ladder cell |

### New configuration and documentation

| File | Responsibility |
|---|---|
| `config/hard_goal/design_v1.toml` | Confirmed physical/model/RG/evidence contract |
| `config/hard_goal/success_contract_v1.json` | Machine-readable gates and allowed classifications |
| `config/hard_goal/stage4_regression_v1.toml` | Fresh 2D regression settings |
| `config/hard_goal/stage5_validation_v1.toml` | Exact and small-3D validation settings |
| `config/hard_goal/stage6_pilot_v1.toml` | Medium pilot grid and provisional thresholds |
| `HARD_GOAL_README.md` | Reproduction commands, artifacts, and scope separation |
| `results/hard_goal/README.md` | Immutable result layout and retention policy |
| `results/hard_goal/.gitignore` | Ignore raw cells/checkpoints while allowing compact reviewed evidence |

### New tests

Tests are named with the `tests/test_hg3d_*.py` prefix to avoid collision with current
Easy Goal files. Each source file above has a same-purpose test module; workflow,
CLI, Slurm, FSS, and reporting receive separate integration tests.

### Existing code reused without modification

- `vmcrg_ref.artifacts`: canonical JSON, SHA-256, atomic JSON/NPZ, verified
  directory promotion.
- `vmcrg_ref.autocorrelation`: FFT ACF, Sokal window, IAT, ESS.
- `vmcrg_ref.mps_patch`, `mps_sampler`, `mps_vmcrg`, `checkpoint`: Stage 4 2D
  regression reference only.
- `scripts/parameter_scan.py`: generic run-spec generation/collection.
- `scripts/harness_slurm.sh`: precheck, partition probe, test-only submission,
  submit, monitor, fetch, classify, and resume.
- `skills/using-slurm/profiles/{qdeshell,scnet}.toml`: cluster limits and
  connection facts; no cluster fact is copied into scientific code.

## Task 1: Freeze the Confirmed Contract and Package Boundary

**Files:**
- Create: `src/spinglass3d/__init__.py`
- Create: `src/spinglass3d/config.py`
- Create: `config/hard_goal/design_v1.toml`
- Create: `config/hard_goal/success_contract_v1.json`
- Create: `tests/test_hg3d_config.py`

**Interfaces:**
- Produces: `ModelSpec`, `RGSpec`, `EvidenceSpec`, `HardGoalDesign`, and
  `load_design(path: str | Path) -> HardGoalDesign`.
- Produces: `HardGoalDesign.sha256` computed from canonical parsed content.
- Consumed by every later task; later modules receive a validated dataclass,
  never an unvalidated dictionary.

- [x] **Step 1: Write the model-contract tests**

```python
def test_confirmed_design_is_iid_pm1() -> None:
    design = load_design("config/hard_goal/design_v1.toml")
    assert design.model.distribution == "iid_pm1"
    assert design.model.hamiltonian_sign == -1
    assert design.model.periodic is True
    assert design.rg.block_shape == (3, 3, 3)
    assert design.sizes == (6, 9, 12, 15, 18, 24, 27, 45)

def test_exact_half_is_rejected_for_l45(tmp_path: Path) -> None:
    path = write_design(tmp_path, distribution="exact_half_pm1")
    with pytest.raises(ValueError, match="odd bond count"):
        load_design(path)
```

- [x] **Step 2: Run the tests and verify the missing-package failure**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_config.py`

Expected: collection fails with `ModuleNotFoundError: spinglass3d`.

- [x] **Step 3: Implement immutable typed configuration**

```python
@dataclass(frozen=True)
class ModelSpec:
    distribution: str
    coupling_scale: float
    periodic: bool
    external_field: float
    hamiltonian_sign: int

    def validate_length(self, length: int) -> None:
        if length < 2:
            raise ValueError("length must be at least two")
        if self.distribution == "exact_half_pm1" and 3 * length**3 % 2:
            raise ValueError("exact-half disorder is impossible for an odd bond count")
```

Parse TOML with `tomllib`, reject unknown distribution names, nonzero field,
nonperiodic boundaries, duplicate sizes, sizes not divisible by three, routes
outside `{A,B,C}`, ranks outside `{2,4,8,16}`, and a missing L=45. Hash the
canonical dataclass projection using `vmcrg_ref.artifacts.canonical_json_bytes`.

- [x] **Step 4: Encode the accepted decisions and success contract**

`design_v1.toml` records iid +/-J, route C/B/A roles, ranks 2/4/8 with 16 as
extension, sizes, one-RG default, uniform target, unbiased FSS, and the exact
observable names. `success_contract_v1.json` records the ten success clauses,
allowed terminal classes `PASS`, `SCIENTIFIC_NEGATIVE`, `EQUILIBRATION_FAILURE`,
`REPRESENTATION_FAILURE`, `RESOURCE_NO_GO`, and `CORRECTNESS_FAILURE`, plus a
rule that second RG requires an explicit first-RG pass manifest.

- [x] **Step 5: Verify and review only these files**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_config.py`

Run: `git diff --check -- src/spinglass3d config/hard_goal tests/test_hg3d_config.py`

Expected: tests pass; no existing `vmcrg_ref` file changes.

## Task 2: Stage 4 Two-Dimensional MPS Regression Gate

**Files:**
- Create: `config/hard_goal/stage4_regression_v1.toml`
- Create: `src/spinglass3d/workflow.py`
- Create: `scripts/hard_goal.py`
- Create: `tests/test_hg3d_stage4.py`
- Read only: `results/mps_challenge/exact_checks.json`
- Read only: `src/vmcrg_ref/{mps_patch,mps_sampler,mps_vmcrg,checkpoint}.py`

**Interfaces:**
- Produces: immutable `StageManifest(stage,classification,failed_gates,artifacts,hashes)`.
- Produces: `run_stage4(config: Path, output: Path) -> StageManifest`.
- Produces: `results/hard_goal/stage4-b2/manifest.json` with source hashes,
  fresh test results, numerical tolerances, and `classification`.
- Consumes the existing 2D classes without modifying their API.

- [x] **Step 1: Write a fail-closed Stage 4 manifest test**

```python
def test_stage4_refuses_a_failed_mps_gate(tmp_path: Path) -> None:
    result = classify_stage4(
        gradient_error=3e-5,
        canonical_error=1e-13,
        delta_error=1e-13,
        checkpoint_equal=True,
    )
    assert result["classification"] == "CORRECTNESS_FAILURE"
    assert "gradient_error" in result["failed_gates"]
```

- [x] **Step 2: Run the test and observe the missing interface**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_stage4.py`

Expected: import fails for `classify_stage4`.

- [x] **Step 3: Implement the Stage 4 adapter and CLI subcommand**

The adapter executes all `tests/*mps*.py`, recomputes one analytic-vs-finite TT
gradient, one canonicalization round trip, 100 incremental local deltas, and a
checkpoint save/load. It then runs a fresh L=45, b=3, chi=2 connectivity cell
with 4 walkers, 8 optimizer steps, 2 sweeps per step, 8 thermal sweeps, and 16
frozen measurement sweeps. The cell is explicitly labeled regression-only.

```python
def classify_stage4(*, gradient_error: float, canonical_error: float,
                    delta_error: float, checkpoint_equal: bool) -> dict[str, object]:
    failed = []
    if gradient_error > 2e-6:
        failed.append("gradient_error")
    if canonical_error > 1e-12:
        failed.append("canonicalization")
    if delta_error > 1e-10:
        failed.append("incremental_delta")
    if not checkpoint_equal:
        failed.append("checkpoint")
    return {"classification": "PASS" if not failed else "CORRECTNESS_FAILURE",
            "failed_gates": failed}
```

- [x] **Step 4: Run Stage 4 locally and inspect its fresh manifest**

Run: `../../../.venv/bin/python scripts/hard_goal.py stage4 --config config/hard_goal/stage4_regression_v1.toml --output results/hard_goal/stage4-b2`

Expected: `classification=PASS`, flushed progress, and a manifest stating that
the 2D result is not 3D Hard Goal evidence.

- [x] **Step 5: Enforce the M4 go/no gate**

Run: `../../../.venv/bin/python -m pytest -q tests/*mps*.py tests/test_hg3d_stage4.py`

Proceed to Task 3 only if the new manifest passes. Otherwise fix the reused 2D
contract in isolated new code or stop for user review; do not edit unrelated
dirty Easy Goal files implicitly.

## Task 3: Implement the Cubic +/-J Model and Exact Oracles

**Files:**
- Create: `src/spinglass3d/model.py`
- Create: `src/spinglass3d/exact.py`
- Create: `tests/test_hg3d_model.py`
- Create: `tests/test_hg3d_exact.py`

**Interfaces:**
- Produces: `EABonds(values: np.ndarray)` with shape `(L,L,L,3)` and int8 +/-1.
- Produces: `EABonds.sample(length: int, rng: Generator) -> EABonds`.
- Produces: `energy(spins, bonds) -> int`, `delta_energy(spins,bonds,site)->int`,
  `three_color_sites(length) -> tuple[np.ndarray,np.ndarray,np.ndarray]`.
- Produces: `enumerate_l2(beta,bonds) -> ExactThermalRecord` and
  `transfer_l3(beta,bonds) -> ExactPartitionRecord`.

- [x] **Step 1: Write brute-force energy and disorder tests**

```python
def test_local_delta_matches_total_energy() -> None:
    rng = np.random.default_rng(11)
    bonds = EABonds.sample(6, rng)
    spins = rng.choice(np.array([-1, 1], dtype=np.int8), size=(6, 6, 6))
    for site in np.ndindex(spins.shape):
        before = energy(spins, bonds)
        delta = delta_energy(spins, bonds, site)
        flipped = spins.copy()
        flipped[site] *= -1
        assert energy(flipped, bonds) - before == delta

def test_iid_generator_does_not_force_exact_half() -> None:
    bonds = EABonds.sample(45, np.random.default_rng(17))
    assert bonds.values.size == 273_375
    assert set(np.unique(bonds.values)) == {-1, 1}
```

- [x] **Step 2: Run the tests and verify missing implementations**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_model.py tests/test_hg3d_exact.py`

- [x] **Step 3: Implement energy, delta, and odd-periodic coloring**

```python
def energy(spins: np.ndarray, bonds: EABonds) -> int:
    total = 0
    for axis in range(3):
        shifted = np.roll(spins, -1, axis=axis)
        total -= int(np.sum(bonds.values[..., axis] * spins * shifted,
                            dtype=np.int64))
    return total

def delta_energy(spins: np.ndarray, bonds: EABonds,
                 site: tuple[int, int, int]) -> int:
    x, y, z = site
    local = 0
    for axis in range(3):
        plus = [x, y, z]
        minus = [x, y, z]
        plus[axis] = (plus[axis] + 1) % spins.shape[axis]
        minus[axis] = (minus[axis] - 1) % spins.shape[axis]
        local += int(bonds.values[x, y, z, axis] * spins[tuple(plus)])
        local += int(bonds.values[tuple(minus) + (axis,)] * spins[tuple(minus)])
    return 2 * int(spins[x, y, z]) * local
```

Build color arrays from `(x+y+z)%3`; assert every nearest-neighbor edge joins
different colors for each configured L.

- [x] **Step 4: Implement exact L=2 and transfer L=3 records**

Enumerate all 256 L=2 states, normalize with log-sum-exp, and expose exact
energy, heat capacity, two-point functions, and two-copy q^2/q^4 moments. For
L=3, construct 512 x 512 adjacent-layer transfer matrices and their beta
derivatives; evaluate `Z=trace(T0 T1 T2)` and `E=-d log Z/d beta`. Compare the
L=3 transfer result to direct enumeration on an L=2 compatibility case.

- [x] **Step 5: Verify exactness and review**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_model.py tests/test_hg3d_exact.py`

Expected tolerances: integer energy/deltas exact; L=2 probabilities within
`2e-14`; transfer partition and derivative within `2e-11` of its reference.

## Task 4: Implement Replica Overlap and Spin-Glass Observables

**Files:**
- Create: `src/spinglass3d/overlap.py`
- Create: `src/spinglass3d/observables.py`
- Create: `tests/test_hg3d_overlap.py`
- Create: `tests/test_hg3d_observables.py`

**Interfaces:**
- Produces: `ReplicaPair(a: np.ndarray, b: np.ndarray)` and
  `overlap_field(pair) -> np.ndarray[int8]`.
- Produces: `measure_sample(pair) -> OverlapMeasurement` containing q, q2, q4,
  and `abs_qk2` for the three axial minimum wavevectors.
- Produces: `ThermalOverlapAccumulator.update(measurement)` and
  `finalize(j_id,temperature) -> DisorderRecord`; one record represents one J.
- Produces: `aggregate_disorder(records) -> DisorderObservables` containing
  Binder, chi_SG(0), chi_SG(k_min), xi_L, and xi_L/L.

- [x] **Step 1: Write exact overlap-estimator tests**

```python
def test_overlap_symmetries() -> None:
    pair = fixed_pair()
    q = overlap_field(pair)
    np.testing.assert_array_equal(overlap_field(pair.swapped()), q)
    np.testing.assert_array_equal(overlap_field(pair.flip_both()), q)
    np.testing.assert_array_equal(overlap_field(pair.flip_a()), -q)

def test_disorder_average_precedes_binder_ratio() -> None:
    records = [sample_record(q2=0.2, q4=0.08),
               sample_record(q2=0.6, q4=0.40)]
    result = aggregate_disorder(records)
    expected = 0.5 * (3.0 - 0.24 / 0.4**2)
    assert result.binder == pytest.approx(expected)
```

- [x] **Step 2: Run the tests and observe missing overlap interfaces**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_overlap.py tests/test_hg3d_observables.py`

- [x] **Step 3: Implement Fourier overlap and moment records**

Use `np.fft.fftn(q)/q.size`; record `|q(k)|^2` for k=0 and the first nonzero
index on each axis. Average the three axial values only after retaining them in
the per-measurement object. `ThermalOverlapAccumulator` performs the thermal
average and emits exactly one record per `(J,T)`. Reject mismatched shapes,
nonbinary spins, and a/b arrays that share memory in unbiased workflow
construction.

- [x] **Step 4: Implement disorder aggregation with the fixed convention**

```python
mean_q2 = float(np.mean([record.q2 for record in records]))
mean_q4 = float(np.mean([record.q4 for record in records]))
chi0 = n_sites * mean_q2
chik = n_sites * float(np.mean([record.qk2_mean for record in records]))
xi = np.sqrt(chi0 / chik - 1.0) / (2.0 * np.sin(np.pi / length))
binder = 0.5 * (3.0 - mean_q4 / mean_q2**2)
```

Reject nonpositive `chik`, negative radicands beyond roundoff, and fewer than
two disorder records for an uncertainty-bearing aggregate.

- [x] **Step 5: Compare L=2 observables with Task 3 exact values**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_exact.py tests/test_hg3d_overlap.py tests/test_hg3d_observables.py`

Expected: q^2/q^4/chi agree within `2e-13`; symmetry comparisons are exact.

## Task 5: Implement Incremental 3D Majority RG

**Files:**
- Create: `src/spinglass3d/rg.py`
- Create: `tests/test_hg3d_rg.py`

**Interfaces:**
- Produces: `block_majority_3d(q, origin=(0,0,0)) -> np.ndarray[int8]`.
- Produces: `MajorityRG3D(q, block_size=3, levels=1, origin=(0,0,0))`.
- Produces: immutable `RGProposal3D` with `level_changes`, `final_site`, and
  `final_changed`; methods `proposal(site)`, `commit(proposal)`, and
  `assert_consistent()`.

- [x] **Step 1: Write one- and two-level cache tests**

```python
@pytest.mark.parametrize("length,levels", [(9, 1), (18, 2), (45, 2)])
def test_incremental_rg_matches_full_recompute(length: int, levels: int) -> None:
    rng = np.random.default_rng(length + levels)
    q = rng.choice(np.array([-1, 1], dtype=np.int8), size=(length,)*3)
    state = MajorityRG3D(q.copy(), levels=levels)
    for _ in range(200):
        site = tuple(int(rng.integers(length)) for _ in range(3))
        proposal = state.proposal(site)
        state.commit(proposal)
        state.assert_consistent()
```

- [x] **Step 2: Run the test and verify the missing 3D state**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_rg.py`

- [x] **Step 3: Port the proven 2D proposal/commit pattern to three axes**

Store int16 block sums because their range is [-27,27]. For each level, map a
site to `(x//3,y//3,z//3)`, subtract twice the changed input spin, determine
the nonzero majority, and stop propagation when the coarse spin is unchanged.
The proposal is side-effect free and commit checks stale old values.

- [x] **Step 4: Add all 27 block-origin sensitivity maps**

Implement origin by rolling q into a canonical partition and rolling coarse
coordinates back through a recorded mapping. Test that origins are deterministic
and that their outputs are not treated as independent samples.

- [x] **Step 5: Verify M5 RG prerequisites**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_rg.py`

Expected: exact cache agreement for 200 proposals per case; second-level tests
do not authorize second-level production.

## Task 6: Implement Gauge-Canonical Local Templates and Cubic Symmetry

**Files:**
- Create: `src/spinglass3d/gauge.py`
- Create: `src/spinglass3d/templates.py`
- Create: `src/spinglass3d/symmetry.py`
- Create: `tests/test_hg3d_gauge.py`
- Create: `tests/test_hg3d_templates.py`
- Create: `tests/test_hg3d_symmetry.py`

**Interfaces:**
- Produces: `gauge_transform(bonds, epsilon) -> EABonds`.
- Produces: `canonical_chords(edge_signs, tree_edges) -> np.ndarray[int8]`.
- Produces: `TemplateKind` values `cross`, `face_edge`, `cube`, `factorized_3x3x3`.
- Produces: `TemplateEncoder(kind, rg_level).encode(q_coarse,bonds,center)` and
  `reverse_q_incidence(length)`.
- Produces: 48 `CubicTransform` objects and `symmetry_images(tokens,encoder)`.

- [x] **Step 1: Write gauge invariance and token-count tests**

```python
@pytest.mark.parametrize("kind,nq,ncond", [
    ("cross", 7, 19),
    ("face_edge", 19, 31),
    ("cube", 8, 13),
    ("factorized_3x3x3", 27, 55),
])
def test_conditioned_template_counts(kind: str, nq: int, ncond: int) -> None:
    encoder = TemplateEncoder(kind=kind, conditioned=True, rg_level=1)
    assert encoder.q_token_count == nq
    assert encoder.token_count == ncond

def test_cube_encoding_is_gauge_invariant() -> None:
    q, bonds, epsilon = random_local_case(seed=41)
    transformed = gauge_transform(bonds, epsilon)
    left = TemplateEncoder("cube", True, 1).encode(q, bonds, (0, 0, 0))
    right = TemplateEncoder("cube", True, 1).encode(q, transformed, (0, 0, 0))
    np.testing.assert_array_equal(left, right)
```

- [x] **Step 2: Run tests and confirm the new encoders are absent**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_gauge.py tests/test_hg3d_templates.py tests/test_hg3d_symmetry.py`

- [x] **Step 3: Implement deterministic spanning-tree gauge fixing**

Choose a root and ordered spanning tree in each local graph. Propagate epsilon
from the root so every tree edge becomes +1, then emit chord signs in a fixed
edge-endpoint order. Assert `E-V+1` chord count: 5 for the cube and 28 for the
full 3^3 internal graph. Cross and face/edge emit the design's selected
plaquette flux products.

- [x] **Step 4: Implement template sequences and reverse incidence**

Use the documented center-shell order for cross/face-edge, a Gray path for the
cube, and a 3D serpentine path for 3^3. Interleave each flux/chord after its
spatial anchor. At RG level 2, derive disorder features from the full 9^3
microscopic preimage rather than assigning synthetic coarse bonds.

- [x] **Step 5: Implement and test all 48 O_h actions**

Generate signed permutation matrices with one nonzero +/-1 entry per row and
determinant +/-1. Transform q coordinates and raw local bonds together, then
gauge-canonicalize again. Test uniqueness, closure, inverse, and exact
joint-transform invariance. Treat q inversion as a separate two-element action.

- [x] **Step 6: Verify no raw-J leakage**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_gauge.py tests/test_hg3d_templates.py tests/test_hg3d_symmetry.py`

Inspect serialized encoder metadata; it must name only q tokens and
gauge-canonical flux/chord tokens.

## Task 7: Implement the Variable-Length Symmetry-Exact Tensor Train

**Files:**
- Create: `src/spinglass3d/tensor_train.py`
- Create: `tests/test_hg3d_tensor_train.py`

**Interfaces:**
- Produces: `TTGradient(cores: tuple[np.ndarray,...])` with norm/add/scale.
- Produces: `LocalTensorTrain.random(token_count,chi,seed)`, `value`, `values`,
  `gradient`, `left_canonicalize`, `parameter_count`, `parameter_norm`,
  `save_arrays`, and `from_arrays`.
- Produces: `SymmetricLocalTT(model, encoder, mode="group_average")` with exact
  O_h x Z2 values and uniform-target means.

- [x] **Step 1: Write rank/count, finite-difference, and canonical tests**

```python
@pytest.mark.parametrize("tokens,chi,count", [
    (13, 2, 96), (13, 4, 368), (13, 8, 1440),
    (19, 2, 144), (31, 4, 944), (55, 8, 6816),
])
def test_declared_parameter_counts(tokens: int, chi: int, count: int) -> None:
    model = LocalTensorTrain.random(tokens, chi, seed=3)
    assert model.parameter_count == count

def test_tt_gradient_matches_finite_difference() -> None:
    model, tokens, weights = fixed_tt_gradient_case()
    analytic = model.gradient(tokens, weights)
    numeric = central_difference(model, core=4, index=(1, 0, 1), epsilon=1e-6)
    assert analytic.cores[4][1, 0, 1] == pytest.approx(numeric, abs=2e-6)
```

- [x] **Step 2: Run tests and verify the generic TT is absent**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_tensor_train.py`

- [x] **Step 3: Generalize the proven forward/backward contraction**

Use physical index mapping -1 -> 0 and +1 -> 1. Core shapes are
`(1,2,chi)`, `n-2` copies of `(chi,2,chi)`, and `(chi,2,1)`. Validate every
core shape and finite value. Compute analytic weighted gradients with batched
left/right environments and reject nonfinite contractions.

- [x] **Step 4: Implement left-canonical gauge and target centering**

QR-canonicalize all but the final core with deterministic diagonal signs and
rank padding. For explicit group averaging, compute the uniform-q target mean
by replacing every q-token slice with `(G[:,0,:]+G[:,1,:])/2` for each symmetry
image while fixing disorder tokens. Small cube/cross lookup modes also verify
the mean by complete q enumeration.

- [x] **Step 5: Implement exact structural symmetry**

```python
def value(self, tokens: np.ndarray) -> float:
    total = 0.0
    for transformed in self.encoder.symmetry_images(tokens):
        total += self.model.value(transformed)
        total += self.model.value(self.encoder.flip_q_tokens(transformed))
    return total / (2.0 * self.encoder.cubic_group_size)
```

An optional orbit-canonical model is a separately labeled invariant
parameterization; it is benchmarked against group averaging for cost and held-out
error, not asserted numerically equal for identical raw cores.

- [x] **Step 6: Run chi=2/4/8 tests and review diagnostics**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_tensor_train.py`

Expected: canonical value error <=1e-12, symmetry error <=5e-14, centered mean
<=1e-13, finite gradients, and exact declared parameter counts.

## Task 8: Implement the Fair Linear Baseline, Route Composition, and Bias Cache

**Files:**
- Create: `src/spinglass3d/linear_bias.py`
- Create: `src/spinglass3d/bias.py`
- Create: `tests/test_hg3d_linear_bias.py`
- Create: `tests/test_hg3d_bias.py`

**Interfaces:**
- Produces: `LinearFeatureBasis.cube_v1()` with named orbit-summed even q and
  flux-conditioned features, full values, and exact local deltas.
- Produces: `BiasRoute` values `A_Q_ONLY`, `B_CONDITIONED_TT`, and
  `C_LINEAR_PLUS_TT`.
- Produces: `OverlapBias(route,basis,coefficients,tt)` and
  `LocalBiasCache(q,bonds,encoder,bias)` with `proposal`, `commit`, and
  `assert_consistent`.

- [x] **Step 1: Write fair-baseline and local-delta tests**

```python
def test_primary_linear_baseline_uses_only_gauge_invariants() -> None:
    basis = LinearFeatureBasis.cube_v1()
    assert basis.names == (
        "q_pair_nn", "q_pair_face", "q_plaquette",
        "flux_q_pair_nn", "flux_q_plaquette",
    )
    assert all(feature.q_parity % 2 == 0 for feature in basis.features)
    assert all(feature.gauge_invariant for feature in basis.features)

def test_cached_route_c_delta_matches_full_recompute() -> None:
    case = random_bias_case(length=9, route="C", seed=53)
    for site in np.ndindex(case.q.shape):
        proposal = case.cache.proposal(site)
        assert proposal.delta == pytest.approx(case.full_delta(site), abs=1e-10)
```

- [x] **Step 2: Run tests and verify missing baseline/cache types**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_linear_bias.py tests/test_hg3d_bias.py`

- [x] **Step 3: Implement the preregistered conditioned finite basis**

Orbit-sum nearest and face-diagonal q pairs plus a four-q face plaquette under
O_h. Add two products with the corresponding gauge-invariant plaquette flux.
Center every feature under uniform q for fixed local disorder. Expose the q-only
three-feature subset as an ablation, not the primary comparator.

- [x] **Step 4: Implement Route A/B/C composition and identifiability controls**

Route C energy is `coefficients @ features + tt_value`. Remove the TT uniform
target mean and report its least-squares projection onto the linear feature
matrix on held-out target samples. Stage B training freezes coefficients;
optional joint tuning starts only from a passing frozen residual checkpoint.

- [x] **Step 5: Implement cache strategies by template size**

Cube uses an 8,192-entry frozen token lookup; cross may use a 524,288-entry
lookup if rebuild time passes the pilot. Face/edge and full 3^3 contract directly.
A coarse q flip updates exactly the translated densities returned by reverse
incidence. Rebuild lookup only after a parameter update, never inside a spin
proposal.

- [x] **Step 6: Stress cache consistency**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_linear_bias.py tests/test_hg3d_bias.py`

Expected: 1,000 accepted/rejected random proposals without drift; route A has
no disorder tokens; B/C remain exactly gauge and q-inversion invariant.

## Task 9: Implement Detailed-Balance-Correct Parallel Tempering

**Files:**
- Create: `src/spinglass3d/tempering.py`
- Create: `tests/test_hg3d_tempering.py`

**Interfaces:**
- Produces: `TemperatureGrid(values: np.ndarray)` with strictly increasing beta
  storage and temperature labels.
- Produces: `SingleReplicaLadder` and `UnbiasedOverlapPT(ladder_a,ladder_b)`.
- Produces: `BiasedPairLadder` whose state at every temperature is a paired
  `(s^a,s^b)` plus one shared target-beta bias.
- Produces: `swap_delta(beta_m,beta_n,energy_m,energy_n,bias_m_xm,bias_m_xn,bias_n_xm,bias_n_xn)`, `attempt_local`, `attempt_swaps(parity)`,
  `attempt_global_q_flip`, and `run_sweeps`.

- [x] **Step 1: Write local and exchange detailed-balance tests**

```python
def test_general_biased_swap_delta() -> None:
    delta = swap_delta(
        beta_m=0.7, beta_n=1.1,
        energy_m=-12.0, energy_n=-4.0,
        bias_m_xm=2.0, bias_m_xn=3.5,
        bias_n_xm=-1.0, bias_n_xn=0.25,
    )
    expected = 1.1 * -12.0 + 0.7 * -4.0 - 0.7 * -12.0 - 1.1 * -4.0
    expected += -1.0 + 3.5 - 2.0 - 0.25
    assert delta == pytest.approx(expected)

def test_l2_transition_matrix_obeys_detailed_balance() -> None:
    transition, stationary = enumerate_l2_pt_transition(fixed_l2_case())
    flux = stationary[:, None] * transition
    np.testing.assert_allclose(flux, flux.T, atol=2e-13, rtol=2e-13)
```

- [x] **Step 2: Run the tests and observe the missing tempering module**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_tempering.py`

- [x] **Step 3: Implement unbiased two-ladder PT**

Each ladder has independent spins, RNG streams, local sweeps, and odd/even swap
streams for the same J. Use exact three-color updates only for the unbiased
nearest-neighbor Hamiltonian. Pair configurations occupying the same temperature
only at measurement time; preserve replica identity and temperature histories.

- [x] **Step 4: Implement biased paired PT with the full action**

```python
def swap_delta(*, beta_m: float, beta_n: float,
               energy_m: float, energy_n: float,
               bias_m_xm: float, bias_m_xn: float,
               bias_n_xm: float, bias_n_xn: float) -> float:
    before = beta_m * energy_m + bias_m_xm + beta_n * energy_n + bias_n_xn
    after = beta_m * energy_n + bias_m_xn + beta_n * energy_m + bias_n_xm
    return after - before
```

The correctness-first configuration supplies one identical bias to all ladder
positions, making cross-bias terms cancel. Keep the general formula and test it
because a beta-conditioned extension may use different biases.

- [x] **Step 5: Implement safe biased local updates and symmetry moves**

Use random-sequential within-state updates; vectorization occurs over independent
J/temperature/walker states. Do not use bare three-color simultaneous updates
with V. A global flip of one complete real replica has unit acceptance under the
zero-field, q-even action and is attempted from an independent stream.

- [x] **Step 6: Verify trajectories and balance**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_tempering.py`

Expected: enumerated detailed balance <=2e-13, shared-bias swap reduction exact,
global q flip exact, and two unbiased ladders share no array memory or RNG state.

## Task 10: Add the Optional Accelerator Backend and Benchmarks

**Files:**
- Create: `src/spinglass3d/backend.py`
- Create: `src/spinglass3d/jax_backend.py`
- Create: `scripts/hard_goal_benchmark.py`
- Create: `tests/test_hg3d_backend.py`
- Modify: `pyproject.toml:16-18`

**Interfaces:**
- Produces: `SamplerBackend` protocol with `sweeps`, `measure`, `checkpoint_state`,
  and `resource_snapshot`.
- Produces: `NumpyReferenceBackend` and optional `JaxBatchedBackend`.
- Produces: `BenchmarkRecord` with spin proposals/s, accepted changes/s, peak
  host/device memory, compile time, checkpoint bytes, and backend provenance.

- [x] **Step 1: Write cross-backend trajectory tests**

```python
def test_backend_proposal_deltas_match() -> None:
    case = fixed_backend_case(length=6, temperatures=4, disorder_samples=3)
    reference = NumpyReferenceBackend(case)
    candidate = JaxBatchedBackend(case)
    np.testing.assert_allclose(candidate.all_proposal_deltas(),
                               reference.all_proposal_deltas(),
                               atol=1e-10, rtol=1e-12)
```

Mark JAX tests with `pytest.importorskip("jax")`; absence of JAX skips only the
accelerator comparison, never the reference correctness suite.

- [x] **Step 2: Run the reference tests before adding JAX code**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_backend.py`

- [x] **Step 3: Define the backend protocol and reference adapter**

The protocol accepts already validated model/PT/bias states. It does not parse
configs or write artifacts. Resource snapshots use `resource.getrusage` for host
RSS and backend-native device memory when available.

- [x] **Step 4: Implement JAX vectorization only over independent states**

Use `jax.vmap` over disorder batches, temperatures, and walkers. Use
`jax.lax.scan` for random-sequential sites within one biased state. Transfer TT
cores as a PyTree and verify float64 is enabled. The implementation must not
simultaneously accept proposals whose bias neighborhoods overlap.

- [x] **Step 5: Add the optional accelerator dependency and smoke command**

Add `accelerator = ["jax>=0.4"]` without changing mandatory dependencies.
Document that CUDA/ROCm wheels are environment-specific and installed through
`make install jax EXTRA=cuda12` only for the approved qdeshell CUDA environment during Stage 6 environment
setup. CPU-only tests remain sufficient for source correctness.

- [x] **Step 6: Run deterministic equivalence and benchmark smoke**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_backend.py`

Run: `../../../.venv/bin/python scripts/hard_goal_benchmark.py --length 6 --temperatures 8 --samples 4 --sweeps 4 --backend reference --output /tmp/hg3d-reference-benchmark.json`

Expected: proposal deltas within tolerance, identical accept/reject decisions
when supplied the same uniforms, and a complete resource record.

## Task 11: Implement Equilibration Diagnostics and Fail-Closed Gates

**Files:**
- Create: `src/spinglass3d/equilibration.py`
- Create: `tests/test_hg3d_equilibration.py`

**Interfaces:**
- Produces: `RoundTripTracker`, `log_bin_estimates`, `split_rhat`, and
  `observable_iat_ess`.
- Produces: `EquilibrationThresholds` and
  `assess_equilibration(record, thresholds) -> EquilibrationReport`.
- Consumes: `vmcrg_ref.autocorrelation.autocorrelation_summary`.

- [x] **Step 1: Write synthetic pass/fail diagnostic tests**

```python
def test_swap_bottleneck_fails() -> None:
    report = assess_equilibration(
        synthetic_stationary_record(edge_acceptance=[0.3, 0.08, 0.31]),
        provisional_thresholds(),
    )
    assert report.passed is False
    assert "swap_bottleneck" in report.failed_gates

def test_measurement_duplication_does_not_change_disorder_count() -> None:
    record = synthetic_stationary_record(measurement_repeat=20)
    assert assess_equilibration(record, provisional_thresholds()).disorder_count == 1
```

- [x] **Step 2: Run the tests and verify missing diagnostics**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_equilibration.py`

- [x] **Step 3: Implement travel and stationarity diagnostics**

Track each physical replica's low -> high -> low events and time since last
endpoint. Form doubling bins for energy, q^2, q^4, chi_SG(0), and each axial
chi_SG(k_min). Compare the last three bins and first/second halves with combined
autocorrelation-aware standard errors. Store every component, not one Boolean.

- [x] **Step 4: Implement multi-chain and ESS gates**

Compute split-Rhat across at least four independent chain pairs. Reuse the Sokal
IAT estimator, storing its selected window and fallback. Provisional thresholds
are swap bottleneck 0.15, target band 0.20-0.50, round trips 10, Rhat 1.05,
ESS 200, two-standard-error bin agreement, and thermal-error fraction 0.25.

- [x] **Step 5: Add completion/censoring policy**

An aggregate fit-eligibility function requires >=95% of preregistered J IDs to
pass and tests failed-vs-passed pilot hardness metrics. It never substitutes a
new J ID. Reports preserve failed IDs and checkpoint extension counts.

- [x] **Step 6: Verify diagnostics**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_equilibration.py`

Expected: stationary synthetic AR(1) chains pass at adequate length; drift,
swap bottlenecks, missing round trips, low ESS, and inconsistent chains fail.

## Task 12: Implement Route C/B VMCRG Training and Frozen Evaluation

**Files:**
- Create: `src/spinglass3d/vmcrg.py`
- Create: `src/spinglass3d/checkpoint.py`
- Create: `tests/test_hg3d_vmcrg.py`
- Create: `tests/test_hg3d_checkpoint.py`

**Interfaces:**
- Produces: `VMCRGGradient(target, biased, difference)` and
  `estimate_gradient(model,target_batch,biased_batch)`.
- Produces: `VMCRGTrainer(protocol,basis,tt,backend)` with `step`, `run`,
  `freeze`, and `restore`.
- Produces: `FrozenEvaluation` with objective estimate, small-marginal TV/JS,
  held-out standardized moments, MMD, acceptance, IAT/ESS, and projection.
- Produces: atomic `TrainingCheckpoint` including cores, coefficients, optimizer,
  RNG/PT states, hashes, step, beta, J split, and RG level.

- [x] **Step 1: Write the sign and exact-gradient tests**

```python
def test_vmcrg_gradient_sign() -> None:
    target = np.array([0.25, -0.10, 0.40])
    biased = np.array([0.50, -0.30, 0.35])
    gradient = vmcrg_gradient(target, biased)
    np.testing.assert_allclose(gradient, target - biased)

def test_uniform_optimum_recovers_negative_bias() -> None:
    exact = exact_two_state_vmcrg()
    np.testing.assert_allclose(exact.recovered_hamiltonian,
                               -exact.optimal_bias_centered,
                               atol=2e-12)
```

- [x] **Step 2: Run the tests and verify missing trainer/checkpoint**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_vmcrg.py tests/test_hg3d_checkpoint.py`

- [x] **Step 3: Implement target and biased gradient blocks**

For each fixed J, draw independent uniform q' target configurations or use an
exact small-template target contraction. Compute
`gradient=E_target[dV]-E_biased[dV]`, then average over whole J records with
equal J weight. Do not weight a slow J more because it produced more retained
measurements.

- [x] **Step 4: Implement staged Route C optimization**

Stage C1 fits the finite basis with TT disabled. Stage C2 freezes coefficients,
initializes a centered TT residual, and optimizes cores with global gradient
clipping. Stage C3 joint tuning is allowed only when the frozen residual has
finite diagnostics and improved a held-out primary metric. Route B starts from
the same TT initialization and omits the linear branch.

- [x] **Step 5: Implement numerical controls and checkpoints**

Canonicalize at the configured interval, reset transformed optimizer moments,
log clipped/unclipped norms, core norms, output range, and finite status. On any
NaN/Inf, atomically save the last finite checkpoint and classify the run. Save
all sampler and optimizer RNG states so resume is trajectory-equivalent.

- [x] **Step 6: Implement frozen held-out comparison**

Use disorder-level train/validation/test splits. Compare the primary conditioned
linear baseline, Route C, Route B fallback, and Route A ablation under both
matched proposal count and matched wall time. A TT improvement requires a
whole-J bootstrap interval excluding zero for a preregistered primary metric
without a material regression on the other primary metrics.

- [x] **Step 7: Verify optimizer, serialization, and negative outcomes**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_vmcrg.py tests/test_hg3d_checkpoint.py`

Expected: exact finite differences <=2e-6, checkpoint resume reproduces the next
32 uniforms/decisions exactly, clipping is bounded, and a non-improving TT is
classified `SCIENTIFIC_NEGATIVE` rather than selected by seed.

## Task 13: Execute Stage 5 Exact and Small-3D Validation

**Files:**
- Create: `config/hard_goal/stage5_validation_v1.toml`
- Extend: `src/spinglass3d/workflow.py`
- Extend: `scripts/hard_goal.py`
- Create: `tests/test_hg3d_stage5_workflow.py`

**Interfaces:**
- Produces: `run_stage5(config,output) -> StageManifest`.
- Produces: immutable `exact.json`, `pt.json`, `rg.json`, `vmcrg.json`,
  `resources.json`, and `manifest.json` under one Stage 5 run.
- Consumes all Task 3-12 components through their public interfaces.

- [x] **Step 1: Write workflow completeness and fail-closed tests**

```python
def test_stage5_manifest_requires_every_evidence_file(tmp_path: Path) -> None:
    run = make_stage5_fixture(tmp_path, omit="pt.json")
    with pytest.raises(FileNotFoundError, match="pt.json"):
        validate_stage5_manifest(run / "manifest.json")
```

- [x] **Step 2: Run the test before implementing the workflow**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_stage5_workflow.py`

- [x] **Step 3: Encode the fixed validation matrix**

The config runs: four fixed L=2 J samples at beta values 0.4, 0.8, 0.9, and
1.2; two L=3 transfer samples; L=6 and L=9 PT reference runs; one-RG cube/cross
Route C/B at chi 2/4/8; four independent paired chains; and both reference and
available accelerator backends. Second RG remains false in this config.

- [x] **Step 4: Run deterministic and exact validation**

Run: `../../../.venv/bin/python scripts/hard_goal.py validate --config config/hard_goal/stage5_validation_v1.toml --output results/hard_goal/stage5-b2`

Monitor flushed per-case energy, q moments, swap acceptance, round trips,
gradient norm, and cache error. Do not continue after a correctness failure.

- [x] **Step 5: Enforce the M5 gate**

Pass only if L=2 observables agree within 5 combined standard errors and exact
absolute tolerance 2e-3 for MC estimates, L=3 energy agrees within 5e-4 per
site, swap detailed balance and cache tests pass exact tolerances, all symmetries
pass, and frozen TT gradients improve or cleanly classify the small test. A
scientific-negative representation result permits code correctness but blocks
Route C production until the model/stencil decision is reviewed.

- [x] **Step 6: Review Stage 5 artifacts and diff**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_*.py`

Run: `git diff --check -- src/spinglass3d scripts/hard_goal.py config/hard_goal tests/test_hg3d_*.py`

Proceed only from a passing `results/hard_goal/stage5-b2/manifest.json`.

## Task 14: Execute Stage 6 Pilot and Freeze a Production Candidate

**Files:**
- Create: `config/hard_goal/stage6_pilot_v1.toml`
- Create: `scripts/hard_goal_freeze_protocol.py`
- Extend: `src/spinglass3d/workflow.py`
- Create: `tests/test_hg3d_pilot.py`
- Create: `tests/test_hg3d_protocol_freeze.py`

**Interfaces:**
- Produces: `run_pilot(config,output) -> PilotReport`.
- Produces: `freeze_production_candidate(pilot_manifest,output) -> dict`.
- The frozen candidate includes temperature arrays by L, sweeps, chain counts,
  selected route/template/chi, J counts from power analysis, backend, resource
  request, output estimate, thresholds, seeds, and every source/config hash.

- [ ] **Step 1: Write pilot-resource and freeze refusal tests**

```python
def test_freeze_rejects_failed_round_trips(tmp_path: Path) -> None:
    manifest = passing_pilot_fixture(tmp_path)
    manifest["equilibration"]["round_trips_min"] = 2
    write_manifest(tmp_path, manifest)
    with pytest.raises(ValueError, match="round trips"):
        freeze_production_candidate(tmp_path / "manifest.json",
                                    tmp_path / "production-candidate.json")
```

- [ ] **Step 2: Run tests and verify freeze is unavailable**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_pilot.py tests/test_hg3d_protocol_freeze.py`

- [ ] **Step 3: Encode the medium pilot**

Use L=`12,18,24,27` with unique J counts `64,32,16,8`; initial T range
`[0.80,2.00]`; 48 temperatures; four chain pairs; cube and cross; routes C/B
and conditioned-linear control; chi 2/4/8. Ladder calibration uses 4,096 sweeps,
then doubling equilibration up to 1,048,576 sweeps, and an initial 8,192
measurement sweeps. Extensions retain the same IDs and checkpoints.

- [ ] **Step 4: Run local/reference preflight and cluster compatibility smokes**

Run the reference backend locally first. Through `/using-slurm`, precheck and
probe qdeshell and SCNet, then run only approved compute-node backend smokes.
Record whether JAX sees an A800 and whether the reference/CPU backend runs on
SCNet; do not assume DCU JAX compatibility. Fetch and verify smoke manifests.

- [ ] **Step 5: Run and monitor the pilot**

Run: `../../../.venv/bin/python scripts/hard_goal.py pilot --config config/hard_goal/stage6_pilot_v1.toml --output results/hard_goal/stage6-b3 --backend auto --backend-evidence results/hard_goal/stage6-backend-smoke/manifest.json`

For a remote pilot, generate a full-ladder run spec and use
`scripts/harness_slurm.sh` after test-only feasibility. Monitor pending ->
running, first progress output, periodic pulses, completion, fetch, and per-cell
classification. Resume only failed/incomplete cells after review.

- [ ] **Step 6: Select route/template/rank before production**

Apply the predeclared held-out comparison. Route C is selected only if it beats
the conditioned linear baseline; otherwise switch to passing Route B. Select
cube versus cross and chi from the lowest-cost statistically adequate model,
not the largest or best single seed. Face/edge requires a new pilot cell if both
small stencils underfit.

- [ ] **Step 7: Freeze the production candidate from measured evidence**

Run: `../../../.venv/bin/python scripts/hard_goal_freeze_protocol.py --pilot results/hard_goal/stage6-b3/manifest.json --output results/hard_goal/stage6-b3/production-candidate.json`

The freeze fails unless all provisional thresholds are replaced by measured,
explicit values; the projected L=45 runtime fits checkpointed 24-hour cells;
output and memory have 1.5x margins; and the power calculation supports the
accepted sample schedule or explicitly increases it.

- [ ] **Step 8: Enforce M6 and review**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_pilot.py tests/test_hg3d_protocol_freeze.py`

Do not create a Stage 7 run spec unless the candidate hash validates and its
manifest classification is `PASS`.

## Task 15: Build, Preview, Approve, and Execute Stage 7 Production

**Files:**
- Create: `jobs/hard_goal_array.slurm`
- Extend: `src/spinglass3d/workflow.py`
- Extend: `scripts/hard_goal.py`
- Create: `tests/test_hg3d_workflow.py`
- Create: `tests/test_hg3d_slurm.py`
- Generated for approval preview: `results/hard_goal/hg3d-production-v1/run_spec.json`

**Interfaces:**
- Produces: `build_production_run_spec(candidate,run_id) -> dict`.
- Produces: `run_cell(run_spec,cell_id) -> CellManifest`.
- Produces: `preview_slurm(candidate,run_spec,script) -> SlurmPreview`; it reads
  the frozen profile/resources and performs precheck, probe, and test-only only.
- Every cell key is `(L, disorder_batch, evidence_arm, model_chi, seed)` and
  embeds one complete temperature ladder from the frozen candidate.

- [ ] **Step 1: Write run-spec and array-contract tests**

```python
def test_temperature_is_not_a_cell_axis() -> None:
    spec = build_production_run_spec(frozen_candidate_fixture(), "hg-prod")
    assert "temperature" not in spec["axes"]
    assert all(len(cell["params"]["temperatures"]) >= 2
               for cell in spec["cells"])

def test_array_limit_is_enforced() -> None:
    with pytest.raises(ValueError, match="array limit 200"):
        build_oversized_qdeshell_spec(cell_count=201)
```

- [ ] **Step 2: Implement deterministic batches and immutable cells**

Derive every J seed from `(design_hash,L,global_sample_index)` and every chain
seed from `(J_seed,arm,chain_index)`. Cells write to staging, hash every summary,
checkpoint, and diagnostic, then use verified directory promotion. Existing
successful cells are read-only; resume starts from the last complete checkpoint.

- [ ] **Step 3: Implement the profile-neutral Slurm wrapper**

The wrapper contains no partition, GPU model, memory, or hardcoded repo path. It
requires `HARNESS_RUN_SPEC` and a Slurm cell index, invokes
`scripts/hard_goal.py cell`, uses unbuffered output, and propagates nonzero
classification exits. Profile limits and required GRES come from
`harness_slurm.sh`.

- [ ] **Step 4: Generate and display the exact pre-submission record**

Generate the run spec from the frozen candidate, then print a table containing
cluster/profile, partition candidates and live load, cell/array count, complete
temperature counts, J counts per L, CPUs, accelerator, memory, walltime,
estimated total accelerator-hours, output/storage, source/config hashes, and
resume strategy.

- [ ] **Step 5: Run precheck, queue probe, and test-only feasibility**

Run the profile-driven prechecks, then let the CLI read exact array/time/CPU
values from the hash-locked candidate and invoke test-only submission:

```bash
../../../.venv/bin/python scripts/hard_goal.py preview-slurm --candidate results/hard_goal/stage6-b3/production-candidate.json --run-spec results/hard_goal/hg3d-production-v1/run_spec.json --script jobs/hard_goal_array.slurm --profile-from-candidate
```

The preview command prints the resolved `harness_slurm.sh submit --test-only`
call and scheduler response after invoking the candidate profile's precheck and
partition probe; the operator does not invent or edit resources.

- [ ] **Step 6: Stop and obtain explicit Stage 7 submission approval**

Present the exact record and test-only scheduler response. Wait for a direct
user approval before shipping the dirty tree or leaving a real job queued. Use
an explicitly approved, path-scoped rsync strategy because commit/push remains
forbidden before Stage 9.

- [ ] **Step 7: Submit, monitor, fetch, and classify every cell**

After approval, submit through `harness_slurm.sh`, capture the job ID, monitor
pending/running/startup logs and 30-60 minute pulses, fetch outputs, and combine
Slurm `sacct` with scientific manifests. Re-run only reviewed incomplete cells.

- [ ] **Step 8: Enforce the L=45 M7 gate**

M7 passes only when actual L=45 data exist, all included J records pass the
frozen equilibration gates, preregistered completion is >=95%, and failed IDs
remain visible. A generated script, queued job, or Slurm COMPLETED state cannot
pass M7.

## Task 16: Implement Whole-Disorder Bootstrap and Correction-Aware FSS

**Files:**
- Create: `src/spinglass3d/statistics.py`
- Create: `tests/test_hg3d_statistics.py`
- Extend: `scripts/hard_goal.py`

**Interfaces:**
- Produces: `resample_disorder(records,indices)`, `pair_crossings`,
  `fit_dimensionless_fss`, and `bootstrap_fss`.
- Produces: `FSSFitResult` with Tc, nu, omega, coefficients, covariance,
  chi2/dof, failed resamples, L_min, T window, parity model, and source hashes.
- Consumes only immutable per-J Stage 7 summaries.

- [ ] **Step 1: Write bootstrap-unit and synthetic-recovery tests**

```python
def test_bootstrap_resamples_whole_j_records() -> None:
    records = correlated_temperature_records(disorder_samples=12)
    sample = resample_disorder(records, np.array([1, 1, 5, 9]))
    assert sample[0].j_id == sample[1].j_id == records[1].j_id
    np.testing.assert_array_equal(sample[0].temperatures, records[1].temperatures)

def test_corrected_fss_recovers_synthetic_tc() -> None:
    data = synthetic_fss(tc=1.11, nu=2.45, omega=1.0, seed=71)
    fit = fit_dimensionless_fss(data, observable="xi_over_l",
                                l_min=9, temperature_window=(1.0, 1.2),
                                polynomial_order=3, parity=True)
    assert fit.tc == pytest.approx(1.11, abs=0.015)
```

- [ ] **Step 2: Run tests before implementing the fitter**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_statistics.py`

- [ ] **Step 3: Implement pair crossings without two-size claims**

Interpolate each bootstrap size curve only inside observed temperature support,
find all sign changes of size-pair differences, and retain crossing distributions
for diagnostic plots. Require at least three fitted sizes for any Tc result.

- [ ] **Step 4: Implement correction-aware nonlinear fits**

Fit `R=F0(x)+L^-omega F1(x)+p(L)L^-omega_p Fp(x)` with
`x=(T-Tc)L^(1/nu)` and low-order polynomial Fs. The parity term is enabled only
according to the frozen Stage 6 protocol. Fit xi_L/L and Binder separately,
then jointly with shared Tc/nu and distinct coefficients. Record all failed
optimizations and bound hits.

- [ ] **Step 5: Implement whole-J bootstrap and window systematic**

Use saved bootstrap seeds and indices. Repeat the frozen set of L_min,
temperature-window, polynomial-order, and omega treatments. Statistical
intervals come from bootstrap quantiles; the accepted-fit spread is a separate
finite-size systematic. Do not select one fit after comparing Tc values.

- [ ] **Step 6: Verify and run Stage 8 FSS**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_statistics.py`

Run: `../../../.venv/bin/python scripts/hard_goal.py analyze --production results/hard_goal/hg3d-production-v1 --output results/hard_goal/hg3d-production-v1/analysis`

Expected: complete fit table for xi_L/L and Binder, failed fits visible, and no
measurement-level resampling path.

## Task 17: Implement Neural RG-Flow Evidence and Cross-Arm Classification

**Files:**
- Create: `src/spinglass3d/rg_flow.py`
- Create: `tests/test_hg3d_rg_flow.py`
- Create: `src/spinglass3d/report.py`
- Extend: `scripts/hard_goal.py`

**Interfaces:**
- Produces: `EffectiveSummary` in a centered common gauge.
- Produces: `estimate_flow_interval(level1_records, level2_records=None)`.
- Produces: `classify_cross_evidence(fss,rg,mps_comparison) -> FinalClassification`.

- [ ] **Step 1: Write common-gauge and interval-compatibility tests**

```python
def test_additive_bias_constant_does_not_change_flow() -> None:
    left = effective_summary(fixed_bias_values())
    right = effective_summary(fixed_bias_values() + 37.0)
    assert left == right

def test_incompatible_rg_and_fss_cannot_pass() -> None:
    result = classify_cross_evidence(
        fss=interval(1.08, 1.13),
        rg=interval(1.18, 1.24),
        mps_comparison=passing_mps_comparison(),
    )
    assert result.status == "SCIENTIFIC_NEGATIVE"
```

- [ ] **Step 2: Run tests before implementing RG analysis**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_rg_flow.py`

- [ ] **Step 3: Implement preregistered effective summaries**

Center each bias under the uniform target; project onto the fixed conditioned
linear basis; add held-out even q correlations, loop-conditioned summaries,
small-marginal distances, and MMD. The Stage 6 flow coordinate and its sign are
read from the frozen protocol, never inferred from Stage 7 outcomes.

- [ ] **Step 4: Estimate one-step RG flow and conditionally enable two-step RG**

Bootstrap whole J records to find the temperature where the flow changes basin
or approaches its fixed-point coordinate. If the first-RG pass hash is present,
run the preregistered `{9,18,27,45}` two-step cells and compare direct composite
training with iterated effective models. Otherwise report second RG as blocked.

- [ ] **Step 5: Quantify TT improvement and error accumulation**

Compare conditioned linear, Route C, and Route B with paired J bootstraps.
Report objective, TV/JS, held-out moment residuals, MMD, one-to-two-step drift,
walltime, memory, IAT, and ESS/s. At least one preregistered primary improvement
must exclude zero without hidden regressions.

- [ ] **Step 6: Enforce M8 cross-evidence gate**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_rg_flow.py`

Pass only when correction-aware xi_L/L and Binder intervals overlap and the RG
interval is compatible. Preserve a valid negative classification when the TT
or intervals fail.

## Task 18: Generate the Stage 9 Report, Consolidated Runner, and Review Diff

**Files:**
- Extend: `src/spinglass3d/report.py`
- Create: `HARD_GOAL_README.md`
- Create: `results/hard_goal/README.md`
- Create: `results/hard_goal/.gitignore`
- Extend: `scripts/hard_goal.py`
- Create: `tests/test_hg3d_report.py`
- Create: `tests/test_hg3d_cli.py`

**Interfaces:**
- Produces: `build_report(production,analysis,output) -> Path`.
- Produces: one consolidated command surface through `scripts/hard_goal.py`.
- Produces: self-contained HTML, source CSV/JSON for every figure, protocol and
  environment hashes, success table, and failure analysis.

- [ ] **Step 1: Write report provenance and CLI tests**

```python
def test_every_figure_has_exact_source_data(tmp_path: Path) -> None:
    report = build_report(report_fixture(tmp_path), tmp_path / "report")
    manifest = json.loads((report.parent / "report_manifest.json").read_text())
    assert manifest["figures"]
    assert all(Path(item["source_data"]).is_file() for item in manifest["figures"])

def test_cli_dry_run_never_submits() -> None:
    result = run_cli(["cell", "--dry-run", "--run-spec", "fixture.json"])
    assert "sbatch" not in result.executed_commands
```

- [ ] **Step 2: Run tests before implementing the report**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_report.py tests/test_hg3d_cli.py`

- [ ] **Step 3: Generate required scientific figures and tables**

Include energy/q time series, swap acceptance and round trips, IAT/ESS,
xi_L/L and Binder crossings, correction fits, chi_SG, TT rank/stencil curves,
linear-vs-TT target errors, one/two-step RG flow, resource scaling, failed-J
counts, and a four-part error budget. Every plot reads a saved table and records
its SHA-256.

- [ ] **Step 4: Write the interpretation and failure ledger**

Lead with Tc and whether all gates passed. State explicitly that H'_q is an
overlap-field effective Hamiltonian. Include model, sample counts, completion,
equilibration, route/rank/template, statistical and systematic errors, negative
runs, initialization dispersion, and outstanding risks. Compare the final
result to literature only after the independent estimate is fixed.

- [ ] **Step 5: Finish the consolidated reproducible commands**

Document fresh-checkout commands for dependency smoke, Stage 4, Stage 5,
pilot, protocol freeze, test-only Slurm preview, cell resume, analysis, and
report. Commands consume explicit configs and refuse overwrite. No command
automatically commits, pushes, or submits without the required gate.

- [ ] **Step 6: Run focused and full verification**

Run: `../../../.venv/bin/python -m pytest -q tests/test_hg3d_*.py`

Run: `../../../.venv/bin/python -m pytest -q`

Run: `make -C ../../.. test`

Expected: the root `.github/workflows/test.yml` equivalent passes its
`scripts/tests/` pytest/coverage suite.
Record skipped optional-backend tests separately from failures.

- [ ] **Step 7: Generate final report and inspect artifacts**

Run: `../../../.venv/bin/python scripts/hard_goal.py report --production results/hard_goal/hg3d-production-v1 --analysis results/hard_goal/hg3d-production-v1/analysis --output results/hard_goal/hg3d-production-v1/report`

Open the HTML and verify every figure, table, local link, and long label. Confirm
no raw chains or secret cluster credentials are included.

- [ ] **Step 8: Show the complete review diff and wait**

Run: `git status --short`

Run: `git diff --check`

Run focused `git diff --` commands for the Hard Goal files and list untracked
Hard Goal artifacts. Present scientific classification, tests, generated paths,
and the exact proposed staged-file list. Do not commit, push, or mark PR #154
ready until the user explicitly approves those actions.

## Plan Self-Review Checklist

- [x] Map every section of `HARD_GOAL_DESIGN.md` to at least one task above.
- [x] Confirm Stage 4 precedes all 3D compute and Stage 5 precedes the pilot.
- [x] Confirm second RG is guarded by a first-RG pass hash.
- [x] Confirm Route A cannot produce a passing final classification.
- [x] Confirm the primary linear baseline sees gauge-invariant disorder features.
- [x] Confirm biased PT uses the general cross-bias swap action.
- [x] Confirm unbiased FSS uses two independent ladders and whole-J resampling.
- [x] Confirm no temperature is a Slurm cell axis.
- [x] Confirm the production protocol is derived only from a passing pilot.
- [x] Confirm Stage 7 has a separate explicit submission approval stop.
- [x] Confirm every long run flushes progress and checkpoints within 24 hours.
- [x] Confirm tests reject NaN/Inf, stale caches, overwrite, seed replacement,
  failed-sample omission, and measurement-level disorder bootstrap.
- [x] Scan this plan for ambiguous placeholders and replace them with a source,
  generated-value rule, test fixture, or exact command.
- [x] Cross-check every public type/function name against the task that first
  defines it.

## Execution Handoff

Plan implementation starts in a fresh B2/Stage 4 thread. Because the repository
is dirty and the user requested one thread per stage, the recommended execution
mode is inline `superpowers:executing-plans` with an M4 review checkpoint before
any 3D work. Subagent-driven execution remains available only if the user
explicitly selects it. No plan step itself authorizes a commit or cluster job.
