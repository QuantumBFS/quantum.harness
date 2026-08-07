# Challenge #15 Route B Continuous Holomorphic NQS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and freeze a continuous-coordinate, fixed-degree holomorphic determinant-sum NQS with a shared generator and scalar/rank-2 sector heads.

**Architecture:** Every single-particle column is a degree-`2Q` monopole polynomial, and every many-body term is a determinant, so strict LLL closure and exchange antisymmetry are construction properties. A rank-64 shared determinant bank feeds an `L=0` scalar head and a five-component rank-2 head coupled with analytic Clebsch-Gordan tensors. Sphere-spinor Metropolis, analytic angular derivatives, and coordinate-space Coulomb estimators provide the common adapter surface.

**Tech Stack:** Python 3.11+, NumPy, SciPy, SymPy only for cached Clebsch-Gordan constants, pytest, JSON, Git worktrees.

---

## Immutable lane boundary

- Owner: `AroundPeking`.
- Route key: `continuous_holomorphic`.
- First branch/worktree: `challenge/qmc-chiral-graviton-scalable-v1-s02b-a01` and `D:/Playground/worktrees/quantum.harness/challenge-qmc-chiral-graviton-scalable-v1-s02b-a01`.
- Start from the exact post-admission SHA recorded in `s01-route-d-admission.md`; record it and the protocol hash in all five journals.
- Frozen capacity: `determinant_rank=64`, `generator_hidden_width=64`, under `max_trainable_parameters=262144`.
- Coordinate-dependent orbital coefficients, anti-holomorphic inputs to the wavefunction, degree-changing multiplicative correlators, full determinant-basis expansions, and exact many-body `L` projectors are forbidden.
- Each task consumes one Route B attempt and has at most 90 minutes active implementation time. A construction or SO(3) failure is recorded as evidence, never hidden by a low energy.

## File map

- `continuous_holomorphic/spinors.py`: normalized sphere spinors, fixed-degree monopole vector, SU(2) rotations, and chord distance.
- `continuous_holomorphic/determinants.py`: rank-64 holomorphic determinant bank and stable log amplitudes.
- `continuous_holomorphic/irreps.py`: cached CG constants and shared scalar/rank-2 coefficient heads.
- `continuous_holomorphic/sampler.py`: sphere-spinor Metropolis with independent chains.
- `continuous_holomorphic/estimators.py`: Coulomb and analytic `L^2` local estimators.
- `continuous_holomorphic/model.py`: parameters, analytic log derivatives, and parameter-count checks.
- `continuous_holomorphic/train.py`: state-averaged VMC and frozen Adam loop.
- `continuous_holomorphic/diagnostics.py`: degree, exchange, finite-rotation, and tower checks.
- `continuous_holomorphic/adapter.py`, `factory.py`: common interfaces and frozen-checkpoint binding.
- `train_continuous_holomorphic.py`: training/smoke/manifest CLI.

### Task 1 (`s02b-a01`): Fixed-degree holomorphic determinant bank

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/continuous_holomorphic/__init__.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/continuous_holomorphic/spinors.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/continuous_holomorphic/determinants.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/routes/test_holomorphic_determinants.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02b-a01.md`

- [ ] **Step 1: Create the worktree from the journaled admission SHA**

```powershell
$match = Get-Content tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s01-route-d-admission.md | Select-String '^comparison_base_sha: `([0-9a-f]{40})`$'
$routeBase = $match.Matches.Groups[1].Value
if ($routeBase.Length -ne 40) { throw 'missing comparison_base_sha' }
git worktree add D:/Playground/worktrees/quantum.harness/challenge-qmc-chiral-graviton-scalable-v1-s02b-a01 -b challenge/qmc-chiral-graviton-scalable-v1-s02b-a01 $routeBase
```

- [ ] **Step 2: Write RED tests for degree, gauge covariance, and exchange**

```python
def test_each_orbital_is_homogeneous_degree_two_q():
    z = normalized_spinors(seed=848, n_electrons=3)
    value = monopole_vector(z, two_q=6)
    scaled = monopole_vector(1.7 * z, two_q=6, normalize=False)
    assert scaled == pytest.approx((1.7**6) * value)

def test_every_determinant_term_is_antisymmetric():
    bank = DeterminantBank.initialize(n_electrons=3, two_q=6, rank=4, seed=848)
    z = normalized_spinors(seed=1848, n_electrons=3)
    swapped = z[[1, 0, 2]]
    assert bank.amplitudes(swapped) == pytest.approx(-bank.amplitudes(z), abs=1e-12)

def test_antiholomorphic_perturbation_is_detected():
    assert wirtinger_residual(lambda x: bank.amplitudes(x), z) < 1e-10
    assert wirtinger_residual(lambda x: bank.amplitudes(x) + 1e-3*x[0,0].conjugate(), z) > 1e-5
```

- [ ] **Step 3: Implement the fixed-degree basis and stable determinant sum**

```python
def monopole_vector(spinors: np.ndarray, two_q: int, *, normalize: bool = True) -> np.ndarray:
    z = normalize_rows(spinors) if normalize else np.asarray(spinors, dtype=np.complex128)
    u, v = z[:, 0], z[:, 1]
    columns = [math.sqrt(math.comb(two_q, k)) * u**k * v**(two_q-k) for k in range(two_q + 1)]
    return np.column_stack(columns)

@dataclass
class DeterminantBank:
    orbital_coefficients: np.ndarray  # [rank, 2Q+1, N], coordinate independent

    def amplitudes(self, spinors):
        basis = monopole_vector(spinors, self.two_q)
        return np.asarray([np.linalg.det(basis @ coeff) for coeff in self.orbital_coefficients])

    def combined(self, spinors, weights):
        terms = self.amplitudes(spinors)
        scale = np.max(np.abs(terms))
        return scale * np.dot(weights, terms / scale) if scale else 0.0j
```

Initialize coefficient columns by QR, never from coordinates. Validate shapes, `rank<=64`, exact degree, and finite amplitudes.

- [ ] **Step 4: Run GREEN and static closure audit**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/routes/test_holomorphic_determinants.py -q
rg -n "conj\(|conjugate\(|abs\(" tracks/qmc/solutions/BOTS-848/scalable_v1/routes/continuous_holomorphic/determinants.py
git diff --check
```

Expected: `conj/conjugate` has no wavefunction-construction match; `abs` appears only in stable scaling, not as an input feature.

- [ ] **Step 5: Commit and close a01**

Commit `feat(qmc): add fixed degree holomorphic bank`; journal exact degree/swap/Wirtinger residuals and close `slice-pass` only if all are finite and below thresholds.

```powershell
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/continuous_holomorphic tracks/qmc/solutions/BOTS-848/tests/routes/test_holomorphic_determinants.py
git commit -m "feat(qmc): add fixed degree holomorphic bank"
git add tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02b-a01.md
git commit -m "docs(qmc): record route B attempt a01"
```

### Task 2 (`s02b-a02`): Coordinate sampler, Coulomb energy, and analytic Casimir

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/continuous_holomorphic/sampler.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/continuous_holomorphic/estimators.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/routes/test_holomorphic_estimators.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02b-a02.md`

- [ ] **Step 1: Write RED tests for detailed balance and analytic generators**

```python
def test_metropolis_is_seeded_and_returns_normalized_spinors():
    a = sample_spinors(LOGPSI, n_samples=64, burn_in=32, seed=848)
    b = sample_spinors(LOGPSI, n_samples=64, burn_in=32, seed=848)
    assert np.array_equal(a, b)
    assert np.max(abs(np.sum(abs(a)**2, axis=-1) - 1.0)) < 1e-12

def test_l2_estimator_matches_known_scalar_and_rank2_polynomials():
    assert local_l2(SCALAR_MODEL, CONFIG) == pytest.approx(0.0, abs=1e-10)
    assert local_l2(RANK2_MODEL, CONFIG) == pytest.approx(6.0, abs=1e-9)
```

- [ ] **Step 2: Implement a reversible tangent-plane proposal**

```python
def propose_spinor(z, rng, scale):
    eta = rng.normal(size=2) + 1j * rng.normal(size=2)
    eta -= z * np.vdot(z, eta)
    proposal = z + scale * eta
    return proposal / np.linalg.norm(proposal)

log_acceptance = 2.0 * (logabs_new - logabs_old)
accept = math.log(rng.random()) < min(0.0, log_acceptance)
```

Update one uniformly chosen particle per step, retain chain state after burn-in, and reject nonfinite amplitudes with a counted diagnostic.

- [ ] **Step 3: Implement coordinate Coulomb and analytic angular derivatives**

```python
def coulomb_local(spinors, q):
    total = 0.0
    for i in range(len(spinors)):
        for j in range(i + 1, len(spinors)):
            chord = math.sqrt(2.0 * (1.0 - float(np.clip(abs(np.vdot(spinors[i], spinors[j]))**2, 0.0, 1.0))))
            total += 1.0 / (math.sqrt(q) * chord)
    return total

def local_l2(model, spinors):
    psi, lz, lp, lm, lm_lp = model.angular_jet(spinors)
    return (lm_lp + lz + lz * lz) / psi
```

`angular_jet` differentiates the degree-`2Q` monomial vector analytically, propagates derivatives through determinants with cofactor identities, and combines terms with the same head weights. Central differences appear only in tests.

- [ ] **Step 4: Run exact derivative tests, singularity guard, and commit**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/routes/test_holomorphic_estimators.py -q
git diff --check
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/continuous_holomorphic tracks/qmc/solutions/BOTS-848/tests/routes/test_holomorphic_estimators.py
git commit -m "feat(qmc): add holomorphic VMC estimators"
```

- [ ] **Step 5: Journal a02**

Record acceptance rate, maximum derivative-vs-finite-difference error, scalar/rank-2 Casimir errors, wall time, and `slice-pass`/failure.

```powershell
git add tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02b-a02.md
git commit -m "docs(qmc): record route B attempt a02"
```

### Task 3 (`s02b-a03`): Shared generator, scalar/rank-2 heads, and VMC

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/continuous_holomorphic/irreps.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/continuous_holomorphic/model.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/continuous_holomorphic/train.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/routes/test_holomorphic_training.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02b-a03.md`

- [ ] **Step 1: Write RED tests for one shared bank and a five-component head**

```python
def test_scalar_and_rank2_heads_share_exact_bank_storage():
    model = HolomorphicNQS.initialize(PROTOCOL, seed=848)
    assert model.scalar_head.bank is model.rank2_head.bank
    assert model.rank2_head.weights.shape == (5, 64)
    assert model.trainable_parameters <= 262_144

def test_rank2_head_rotates_by_wigner_d_on_tiny_coupled_fixture():
    left = fixture.rank2(rotated(CONFIG, ROTATION))
    right = wigner_d2(ROTATION) @ fixture.rank2(CONFIG)
    assert left == pytest.approx(right, abs=1e-10)
```

- [ ] **Step 2: Generate cached CG tensors and irrep heads**

```python
@functools.lru_cache(maxsize=None)
def clebsch_gordan(j1_2, m1_2, j2_2, m2_2, j_2, m_2):
    value = sympy.physics.wigner.clebsch_gordan(
        Rational(j1_2, 2), Rational(j2_2, 2), Rational(j_2, 2),
        Rational(m1_2, 2), Rational(m2_2, 2), Rational(m_2, 2),
    )
    return float(value)

class Rank2Head:
    def amplitudes(self, spinors):
        bank = self.bank.amplitudes(spinors)
        return self.weights @ bank
```

Initialize the five rows from the same CG-coupled parameter tensor and update a shared latent vector, rather than training five unrelated row arrays. Reject any checkpoint whose rows lack a common `generator_id`.

- [ ] **Step 3: Implement analytic scores and the exact frozen training schedule**

Use log-derivative VMC gradients for both heads, average the five excited energies, and use the same deterministic symmetry penalties as Route A:

```python
loss = e0 + np.mean(e2m) + 0.25*(l2_ground**2 + (l2_excited-6.0)**2) + 0.05*l2_variance
```

Run exactly 2048 Adam updates, batch 512 per sector, three independent seeds, final-update selection, complex128, gradient clip 10, checkpoint interval 128. The trainer must reject unknown capacity or budget overrides.

- [ ] **Step 4: Run analytic-gradient and 16-update smoke tests**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/routes/test_holomorphic_training.py -q
python tracks/qmc/solutions/BOTS-848/train_continuous_holomorphic.py --smoke-updates 16 --training-seed 848 --run-dir D:/Playground/tmp/bots848-route-b-smoke
```

Expected: finite scores/objective, exact update/sample count, deterministic artifact hash.

- [ ] **Step 5: Commit and journal a03**

Commit `feat(qmc): train shared holomorphic NQS`; record whether the rank-2 covariance fixture remains exact after optimizer updates.

```powershell
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/continuous_holomorphic/irreps.py tracks/qmc/solutions/BOTS-848/scalable_v1/routes/continuous_holomorphic/model.py tracks/qmc/solutions/BOTS-848/scalable_v1/routes/continuous_holomorphic/train.py tracks/qmc/solutions/BOTS-848/tests/routes/test_holomorphic_training.py tracks/qmc/solutions/BOTS-848/train_continuous_holomorphic.py
git commit -m "feat(qmc): train shared holomorphic NQS"
git add tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02b-a03.md
git commit -m "docs(qmc): record route B attempt a03"
```

### Task 4 (`s02b-a04`): Exchange, SO(3), degree, and tower diagnostics

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/continuous_holomorphic/diagnostics.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/routes/test_holomorphic_diagnostics.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02b-a04.md`

- [ ] **Step 1: Write RED numerical-certificate tests**

```python
def test_diagnostics_report_all_common_fields():
    values = HolomorphicDiagnostics(PROTOCOL).evaluate(FIXTURE, seed=3848, swap_probes=16, rotation_probes=8)
    assert set(values) == {"lll_residual", "particle_swap_residual", "finite_rotation_residual", "tower_ladder_residual"}
    assert max(values.values()) < 1e-9
```

- [ ] **Step 2: Implement measured residuals**

- `lll_residual`: maximum analytic anti-holomorphic derivative divided by amplitude scale, plus exact degree mismatch indicator.
- `particle_swap_residual`: maximum `|psi(Pij z)+psi(z)|/max(|psi|,tiny)` over ground and all five components.
- `finite_rotation_residual`: maximum norm of `psi_2(Rz)-D^2(R)psi_2(z)` and scalar residual.
- `tower_ladder_residual`: compare analytic total `L_±` action with `sqrt(6-M(M±1))*psi_{M±1}`.

Use seeded Haar SU(2) matrices and analytic Wigner `D^2`; do not estimate a many-body projection.

```python
def evaluate(self, candidate, *, seed, swap_probes, rotation_probes):
    rng = np.random.default_rng(seed)
    swaps = [swap_residual(candidate, random_spinors(rng), rng) for _ in range(swap_probes)]
    rotations = [rotation_residual(candidate, random_spinors(rng), haar_su2(rng)) for _ in range(rotation_probes)]
    return {
        "lll_residual": max(degree_residual(candidate), wirtinger_residual(candidate)),
        "particle_swap_residual": max(swaps),
        "finite_rotation_residual": max(rotations),
        "tower_ladder_residual": ladder_residual(candidate, rng),
    }
```

- [ ] **Step 3: Add adversarial tests**

Inject separately: a conjugated coordinate, degree-`2Q+1` term, symmetric determinant replacement, and one independently perturbed `M` row. Assert that each makes the intended residual exceed its protocol threshold.

```python
@pytest.mark.parametrize("mutation,field", [
    (inject_conjugate, "lll_residual"),
    (raise_degree, "lll_residual"),
    (remove_determinant_sign, "particle_swap_residual"),
    (perturb_one_m_row, "finite_rotation_residual"),
])
def test_adversarial_mutation_fails_its_certificate(mutation, field):
    values = DIAGNOSTICS.evaluate(mutation(FIXTURE), seed=3848, swap_probes=8, rotation_probes=4)
    assert values[field] > threshold_for(field, PROTOCOL)
```

- [ ] **Step 4: Run diagnostics and common tests**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/routes/test_holomorphic_diagnostics.py tracks/qmc/solutions/BOTS-848/tests/test_scalable_gates.py -q
git diff --check
```

- [ ] **Step 5: Commit and journal a04**

Commit `test(qmc): certify holomorphic route symmetries`; a finite rotation or ladder residual above threshold closes `failed` even when degree and exchange pass.

```powershell
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/continuous_holomorphic/diagnostics.py tracks/qmc/solutions/BOTS-848/tests/routes/test_holomorphic_diagnostics.py
git commit -m "test(qmc): certify holomorphic route symmetries"
git add tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02b-a04.md
git commit -m "docs(qmc): record route B attempt a04"
```

### Task 5 (`s02b-a05`): Adapter, N=8 smoke, and terminal freeze

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/continuous_holomorphic/adapter.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/continuous_holomorphic/factory.py`
- Create: `tracks/qmc/solutions/BOTS-848/train_continuous_holomorphic.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/routes/test_holomorphic_adapter.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02b-a05.md`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/freezes/route-b-receipt.json`

- [ ] **Step 1: Write RED common-interface and manifest-binding tests**

```python
def test_factory_returns_common_candidate_from_manifest_checkpoint(tmp_path, monkeypatch):
    run = train_fixture(tmp_path, route="continuous_holomorphic", seed=848)
    monkeypatch.setenv("BOTS848_SCALABLE_RUN_DIR", str(run))
    candidate, diagnostics = factory(load_protocol(), 848)
    assert isinstance(candidate, CandidateAdapter)
    assert isinstance(diagnostics, DiagnosticProvider)
    assert candidate.checkpoint_sha256 == manifest_artifact_sha(run, "checkpoint")
    assert candidate.construction_certificate().strict_lll is True
```

- [ ] **Step 2: Implement factory and state handles**

`factory(protocol, training_seed)` must require `BOTS848_SCALABLE_RUN_DIR`, verify checkpoint protocol/seed/capacity and manifest hash, and return six coordinate-state handles. Each handle returns `SampleBatch` with the protocol burn-in and one finite vector for `logpsi`, `local_energy`, and `local_l2`.

```python
def factory(protocol: ProtocolConfig, training_seed: int):
    run_dir = Path(os.environ["BOTS848_SCALABLE_RUN_DIR"]).resolve()
    checkpoint = HolomorphicCheckpoint.load(run_dir / "checkpoint.npz")
    checkpoint.require(protocol_sha256=protocol.sha256, training_seed=training_seed, capacity=dict(protocol.capacity["routes"]["continuous_holomorphic"]))
    candidate = HolomorphicCandidate(checkpoint, protocol, run_dir)
    return candidate, HolomorphicDiagnostics(protocol)
```

- [ ] **Step 3: Add CLI and manifest call**

```python
freeze_manifest(
    run_dir=run_dir, project_root=solution_root, route="continuous_holomorphic",
    attempt="s02b-a05", protocol=protocol,
    selected_update=protocol.training["optimizer_updates"], training_seed=seed,
    source_files=sorted(route_root.glob("*.py")),
    artifact_files={"checkpoint": checkpoint, "optimizer_state": optimizer, "training_log": training_log},
)
```

- [ ] **Step 4: Run full suite, frozen N=8 smoke, and forbidden-import audit**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests -q
python tracks/qmc/solutions/BOTS-848/train_continuous_holomorphic.py --n8-smoke --training-seed 848 --run-dir D:/Playground/tmp/bots848-route-b-n8-smoke
rg -n "benchmark_v0\.(ed_oracle|fock_ed|projected_nqs|nqs_benchmark)" tracks/qmc/solutions/BOTS-848/scalable_v1/routes/continuous_holomorphic tracks/qmc/solutions/BOTS-848/train_continuous_holomorphic.py
git diff --check
```

- [ ] **Step 5: Freeze three seeds and close Route B**

Train all frozen seeds, hash the three artifact bundles, and commit only source/tests/journal plus a receipt containing logical names, byte sizes, SHA-256 values, source commit, admission SHA, and protocol hash. Do not invoke the ED evaluator. Close `step-pass` only when all pre-reveal gates and resource ceilings pass; otherwise write `route-stopped` and do not create a sixth attempt.

```powershell
foreach ($seed in 848,1848,2848) {
  python tracks/qmc/solutions/BOTS-848/train_continuous_holomorphic.py --training-seed $seed --run-dir "D:/Playground/output/BOTS-848/scalable-v1/route-b/seed-$seed"
  if ($LASTEXITCODE -ne 0) { throw "Route B training failed for seed $seed" }
}
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/continuous_holomorphic tracks/qmc/solutions/BOTS-848/train_continuous_holomorphic.py tracks/qmc/solutions/BOTS-848/tests/routes/test_holomorphic_adapter.py tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02b-a05.md tracks/qmc/solutions/BOTS-848/logs/scalable-v1/freezes/route-b-receipt.json
git commit -m "feat(qmc): freeze continuous holomorphic route"
```

## Route B acceptance checklist

- [ ] Every coordinate polynomial is degree `2Q`; no anti-holomorphic or coordinate-dependent coefficient enters.
- [ ] Every term is a determinant and passes measured exchange tests.
- [ ] One shared rank-64 bank produces scalar and rank-2 heads; five independent networks are impossible in the checkpoint schema.
- [ ] Analytic `L^2`, finite rotations, and ladder relations pass both exact fixtures and random probes.
- [ ] Training and N=8 smoke remain within frozen parameter/resource budgets.
- [ ] Frozen coordinate amplitudes support the common post-reveal ED-fidelity estimator for the ground state and all five components.
- [ ] Three seed manifests and a pre-reveal freeze receipt exist with no ED access.
