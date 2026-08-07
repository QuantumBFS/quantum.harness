# Challenge #15 Route C CF-Flow L=2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and freeze an `L=2` composite-fermion exciton with a shared SO(3)-equivariant flow, while measuring rather than assuming lowest-Landau-level closure.

**Architecture:** The ground seed is the filled `Q*=(N-1)/2` composite-fermion shell times two Jastrow factors. The excited seed replaces one hole by one quasiparticle in the next effective shell and couples the particle-hole pair to `L=2,M` with Clebsch-Gordan coefficients. A permutation-equivariant tangent flow dresses both sectors; an independent covariant anti-holomorphic leakage diagnostic decides whether the route is strict LLL or a hard-gate-failing prototype.

**Tech Stack:** Python 3.11+, NumPy, SciPy, SymPy for cached Wigner/CG numbers, pytest, JSON, Git worktrees.

---

## Immutable lane boundary

- Owner: `bhjia-phys`.
- Route key: `cf_flow_l2`.
- First branch/worktree: `challenge/qmc-chiral-graviton-scalable-v1-s02c-a01` and `D:/Playground/worktrees/quantum.harness/challenge-qmc-chiral-graviton-scalable-v1-s02c-a01`.
- Start at the post-admission comparison SHA; all journals record it and the protocol hash.
- Frozen capacity: `flow_layers=4`, `hidden_width=64`, with no capacity/budget override.
- The target is the challenge's long-wavelength `L=2` exciton, not the paper's maximally separated `L=N` transport excitation.
- No exact many-body LLL projector is allowed. If leakage exceeds `1e-10`, `ConstructionCertificate.strict_lll` must be `False`, `lll_valid` must fail, and the terminal result is a useful `prototype` obstruction rather than a pass.
- Each task consumes one Route C attempt and has at most 90 minutes active implementation time.

## File map

- `cf_flow_l2/cg.py`: exact cached CG and Wigner constants.
- `cf_flow_l2/seeds.py`: Laughlin ground and CG-coupled CF particle-hole seeds.
- `cf_flow_l2/flow.py`: four-layer permutation/SO(3)-equivariant tangent backflow.
- `cf_flow_l2/leakage.py`: gauge-covariant Wirtinger/cyclotron leakage and fixed-degree tests.
- `cf_flow_l2/sampler.py`, `estimators.py`: continuous Metropolis, Coulomb, and angular estimators.
- `cf_flow_l2/model.py`, `train.py`: shared flow parameters and state-averaged Adam VMC.
- `cf_flow_l2/diagnostics.py`: exchange, rotation, ladder, and leakage records.
- `cf_flow_l2/adapter.py`, `factory.py`: common interfaces, strict/prototype certificate, manifest binding.
- `train_cf_flow_l2.py`: route CLI and freeze writer.

### Task 1 (`s02c-a01`): Analytic `L=0` and CG-coupled `L=2` CF seeds

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_flow_l2/__init__.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_flow_l2/cg.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_flow_l2/seeds.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/routes/test_cf_flow_seeds.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02c-a01.md`

- [ ] **Step 1: Create the lane from the literal admission journal SHA**

```powershell
$match = Get-Content tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s01-route-d-admission.md | Select-String '^comparison_base_sha: `([0-9a-f]{40})`$'
$routeBase = $match.Matches.Groups[1].Value
if ($routeBase.Length -ne 40) { throw 'missing comparison_base_sha' }
git worktree add D:/Playground/worktrees/quantum.harness/challenge-qmc-chiral-graviton-scalable-v1-s02c-a01 -b challenge/qmc-chiral-graviton-scalable-v1-s02c-a01 $routeBase
```

- [ ] **Step 2: Write RED tests for the effective flux and exciton coupling**

```python
def test_cf_effective_flux_and_ground_seed_equal_laughlin():
    seed = CFSeeds(n_electrons=4)
    assert seed.two_q == 9 and seed.two_q_star == 3
    z = normalized_spinors(seed=848, n_electrons=4)
    reference = normalized_spinors(seed=1848, n_electrons=4)
    normalization = seed.ground(reference) / laughlin(reference, power=3)
    assert seed.ground(z) == pytest.approx(normalization * laughlin(z, power=3), rel=1e-11)

def test_one_cg_object_generates_exactly_five_l2_components():
    seed = CFSeeds(n_electrons=4)
    tower = seed.exciton_tower(CONFIG)
    assert set(tower) == {-2, -1, 0, 1, 2}
    assert seed.coupling_terms(0) == [
        (mp, mh, phase * cg(seed.qp_l2, 2*mp, seed.hole_l2, -2*mh, 4, 0))
        for mp, mh, phase in seed.allowed_particle_hole_pairs(0)
    ]
```

The reference fixture is checked once to have nonzero ground and Laughlin amplitudes before forming `normalization`.

- [ ] **Step 3: Implement Eq.-12-style particle-hole coupling**

```python
@dataclass(frozen=True)
class CFSeeds:
    n_electrons: int

    @property
    def two_q(self): return 3 * (self.n_electrons - 1)
    @property
    def two_q_star(self): return self.n_electrons - 1
    @property
    def hole_l2(self): return self.two_q_star
    @property
    def qp_l2(self): return self.two_q_star + 2

    def ground(self, z):
        return filled_shell_determinant(z, self.two_q_star) * jastrow(z, power=2)

    def excited(self, z, m):
        return sum(
            phase * cg(self.qp_l2, 2*mp, self.hole_l2, -2*mh, 4, 2*m)
            * particle_hole_determinant(z, self.two_q_star, mp, mh)
            * jastrow(z, power=2)
            for mp, mh, phase in self.allowed_particle_hole_pairs(m)
        )
```

Use the hole-conjugation phase `(-1)^(l_h-m_h)`. Cache exact rational CG values through SymPy then convert to complex128. Assert nonempty coupling terms and a single normalization convention for all `M`.

- [ ] **Step 4: Run seed tests and forbid `L=N` substitutions**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/routes/test_cf_flow_seeds.py -q
rg -n "transport|L=N|maximally" tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_flow_l2
git diff --check
```

Expected: `rg` appears only in an explanatory rejection message/test, never as the constructed target.

- [ ] **Step 5: Commit and journal a01**

Commit `feat(qmc): add CG coupled CF graviton seed`; record CG normalization, exchange residual, five component norms, and `slice-pass`/failure.

```powershell
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_flow_l2 tracks/qmc/solutions/BOTS-848/tests/routes/test_cf_flow_seeds.py
git commit -m "feat(qmc): add CG coupled CF graviton seed"
git add tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02c-a01.md
git commit -m "docs(qmc): record route C attempt a01"
```

### Task 2 (`s02c-a02`): Four-layer permutation- and SO(3)-equivariant flow

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_flow_l2/flow.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/routes/test_cf_flow_equivariance.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02c-a02.md`

- [ ] **Step 1: Write RED tests for permutation, rotation, and antipodal stability**

```python
def test_flow_commutes_with_particle_permutation_and_su2_rotation():
    flow = CFFlow.initialize(layers=4, width=64, seed=848)
    assert flow(CONFIG[PERM]) == pytest.approx(flow(CONFIG)[PERM], abs=1e-11)
    assert flow(rotate(CONFIG, U)) == pytest.approx(rotate(flow(CONFIG), U), abs=1e-10)

def test_zero_weights_are_identity():
    assert CFFlow.zeros(4, 64)(CONFIG) == pytest.approx(CONFIG, abs=1e-14)
```

- [ ] **Step 2: Implement invariant messages and tangent updates**

```python
def layer(z, weights):
    updated = np.empty_like(z)
    for i in range(len(z)):
        message = np.zeros(2, dtype=np.complex128)
        for j in range(len(z)):
            if i == j: continue
            overlap = np.vdot(z[i], z[j])
            chord2 = max(0.0, 1.0 - abs(overlap)**2)
            scalar = mlp(np.array([chord2, chord2**2]), weights)
            tangent = z[j] - z[i] * overlap
            message += scalar * tangent
        proposal = z[i] + message / max(1, len(z)-1)
        updated[i] = proposal / np.linalg.norm(proposal)
    return updated
```

The scalar MLP uses only rotation invariants and shared weights. Four residual layers share the same architecture but not weights. Validate `4`, `64`, complex128, and the global parameter ceiling.

- [ ] **Step 3: Compose the same flow with both seed sectors**

```python
def amplitude(self, spinors, sector, m=0):
    flowed = self.flow(spinors)
    return self.seeds.ground(flowed) if sector == "ground" else self.seeds.excited(flowed, m)
```

There is one flow object/checkpoint; sector-specific flows are rejected by checkpoint validation.

- [ ] **Step 4: Run equivariance tests plus exchange regression**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/routes/test_cf_flow_equivariance.py tracks/qmc/solutions/BOTS-848/tests/routes/test_cf_flow_seeds.py -q
git diff --check
```

- [ ] **Step 5: Commit and journal a02**

Commit `feat(qmc): add equivariant CF backflow`; record maximum permutation/rotation residual and close `slice-pass` only if both are below `1e-9`.

```powershell
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_flow_l2/flow.py tracks/qmc/solutions/BOTS-848/tests/routes/test_cf_flow_equivariance.py
git commit -m "feat(qmc): add equivariant CF backflow"
git add tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02c-a02.md
git commit -m "docs(qmc): record route C attempt a02"
```

### Task 3 (`s02c-a03`): Independent LLL/cyclotron leakage decision

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_flow_l2/leakage.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/routes/test_cf_flow_leakage.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02c-a03.md`

- [ ] **Step 1: Write RED calibration tests**

```python
def test_covariant_leakage_is_zero_for_laughlin_and_nonzero_for_conjugate_term():
    assert leakage_residual(LAUGHLIN, CONFIG, two_q=9) < 1e-10
    contaminated = lambda z: LAUGHLIN(z) * (1.0 + 1e-3 * z[0, 0].conjugate())
    assert leakage_residual(contaminated, CONFIG, two_q=9) > 1e-5

def test_generic_nonzero_backflow_cannot_self_certify_strict_lll():
    result = certify_lll(NONZERO_FLOW_MODEL, PROBES, threshold=1e-10)
    assert result.strict_lll is (result.maximum_residual <= 1e-10)
```

- [ ] **Step 2: Implement a gauge-covariant Wirtinger residual**

Strip the known monopole gauge factor chart-by-chart, differentiate only tangent anti-holomorphic directions, and normalize by the holomorphic gradient scale:

```python
residual_i = abs(covariant_dbar(amplitude, z, particle=i, step=2.0**-18)) / max(abs(amplitude(z)), holomorphic_scale, 1e-300)
```

Evaluate both north and south charts, halve the step once, and require second-order consistency. Report `max(residual_h, residual_h2, chart_mismatch)`; a nonconvergent derivative is `inf`, not zero.

- [ ] **Step 3: Add fixed-degree and seed/flow decomposition diagnostics**

Measure leakage for the raw ground seed, raw five-component exciton, identity flow, and trained/nonzero flow separately. This identifies whether the obstruction comes from the unprojected quasiparticle seed or the learned backflow.

```python
def decomposed_leakage(model, probes):
    return {
        "ground_seed": maximum_leakage(model.seeds.ground, probes),
        "exciton_seed": max(maximum_leakage(model.seeds.component(m), probes) for m in range(-2, 3)),
        "identity_flow": maximum_leakage(model.with_identity_flow().amplitude, probes),
        "trained_flow": maximum_leakage(model.amplitude, probes),
    }
```

- [ ] **Step 4: Run calibration and freeze the classification rule**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/routes/test_cf_flow_leakage.py -q
git diff --check
```

Expected: known holomorphic fixture passes; injected conjugate fails; `strict_lll` is exactly the numerical comparison, not a manually supplied boolean.

- [ ] **Step 5: Commit and journal a03**

Commit `test(qmc): measure CF flow LLL leakage`; record all four decomposed residuals. A finite nonzero result above threshold is a successful diagnostic `slice-pass`, even though it predicts final `lll_valid=false`.

```powershell
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_flow_l2/leakage.py tracks/qmc/solutions/BOTS-848/tests/routes/test_cf_flow_leakage.py
git commit -m "test(qmc): measure CF flow LLL leakage"
git add tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02c-a03.md
git commit -m "docs(qmc): record route C attempt a03"
```

### Task 4 (`s02c-a04`): Joint VMC for ground and five-component exciton

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_flow_l2/sampler.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_flow_l2/estimators.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_flow_l2/model.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_flow_l2/train.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/routes/test_cf_flow_training.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02c-a04.md`

- [ ] **Step 1: Write RED tests for shared parameters, gradients, and budget**

```python
def test_all_sectors_share_one_flow_and_gradient_is_analytic():
    model = CFModel.initialize(PROTOCOL, seed=848)
    assert len({id(model.flow_for("ground")), *(id(model.flow_for(m)) for m in range(-2,3))}) == 1
    assert model.score(CONFIG, "ground")[3] == pytest.approx(central_difference(model, 3, CONFIG), rel=3e-4)
    assert model.trainable_parameters <= 262_144
```

- [ ] **Step 2: Implement continuous sampling and estimators**

Reuse the route-local reversible tangent proposal. Coulomb local energy is the chord potential. `local_l2` uses analytic/complex-step total angular generators of the flowed amplitude and is independently checked against finite rotations.

```python
class CFState:
    def sample(self, n_samples, seed):
        configs = metropolis_spinors(self.log_amplitude_one, n_samples=n_samples, burn_in=self.protocol.sampling["burn_in_steps"], seed=seed)
        return SampleBatch(configs, n_samples, self.protocol.sampling["burn_in_steps"], seed)

    def local_energy(self, configs):
        return np.asarray([chord_coulomb(z, q=self.two_q/2) for z in configs], dtype=np.complex128)

    def local_l2(self, configs):
        return np.asarray([casimir_ratio(self.amplitude_one, z) for z in configs], dtype=np.complex128)
```

- [ ] **Step 3: Implement the exact frozen Adam schedule**

```python
loss = energy_ground + np.mean(energy_l2_by_m) + 0.25*(l2_ground**2 + (l2_excited-6.0)**2) + 0.05*l2_variance
```

Use protocol learning rate/betas/epsilon/clip, 2048 updates, 512 samples per sector, checkpoint 128, final update only, three seeds. Flush leakage and symmetry residual estimates with energy every 16 updates; they are diagnostics, not ED-informed checkpoint selectors.

- [ ] **Step 4: Run gradient tests and 16-update smoke**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/routes/test_cf_flow_training.py -q
python tracks/qmc/solutions/BOTS-848/train_cf_flow_l2.py --smoke-updates 16 --training-seed 848 --run-dir D:/Playground/tmp/bots848-route-c-smoke
```

- [ ] **Step 5: Commit and journal a04**

Commit `feat(qmc): train L2 CF flow`; journal energy, acceptance, leakage trajectory, NaN count, time, and whether optimization preserves exchange/SO(3).

```powershell
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_flow_l2 tracks/qmc/solutions/BOTS-848/tests/routes/test_cf_flow_training.py tracks/qmc/solutions/BOTS-848/train_cf_flow_l2.py
git commit -m "feat(qmc): train L2 CF flow"
git add tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02c-a04.md
git commit -m "docs(qmc): record route C attempt a04"
```

### Task 5 (`s02c-a05`): Adapter, explicit prototype gate, N=8 smoke, and freeze

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_flow_l2/diagnostics.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_flow_l2/adapter.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_flow_l2/factory.py`
- Create: `tracks/qmc/solutions/BOTS-848/train_cf_flow_l2.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/routes/test_cf_flow_adapter.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02c-a05.md`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/freezes/route-c-receipt.json`

- [ ] **Step 1: Write RED tests that prevent a false LLL pass**

```python
def test_certificate_is_derived_from_measured_leakage(tmp_path, monkeypatch):
    run = trained_fixture(tmp_path, leakage=2e-6)
    monkeypatch.setenv("BOTS848_SCALABLE_RUN_DIR", str(run))
    candidate, _ = factory(load_protocol(), 848)
    certificate = candidate.construction_certificate()
    assert certificate.strict_lll is False
    assert "prototype" in certificate.statement

def test_holomorphic_fixture_can_set_strict_lll_true(tmp_path, monkeypatch):
    run = trained_fixture(tmp_path, leakage=0.0, identity_flow=True)
    monkeypatch.setenv("BOTS848_SCALABLE_RUN_DIR", str(run))
    assert factory(load_protocol(), 848)[0].construction_certificate().strict_lll is True
```

- [ ] **Step 2: Implement common interfaces and measured diagnostics**

Return all six coordinate states, resource metrics, and exactly four common diagnostic fields. The certificate is:

```python
strict = measured_leakage <= protocol.symmetry["lll_residual_max"]
ConstructionCertificate(
    strict_lll=strict, antisymmetric=True, scalable=True,
    trainable_parameters=model.trainable_parameters,
    statement=("fixed-degree holomorphic CF flow" if strict else "prototype: measured higher-LL leakage"),
)
```

- [ ] **Step 3: Add strict factory/CLI and manifest**

The factory requires `BOTS848_SCALABLE_RUN_DIR`, verifies protocol/seed/capacity/artifact hash, and never recalculates leakage from a different checkpoint. The CLI freezes `checkpoint`, `optimizer_state`, and `training_log` under route `cf_flow_l2`, attempt `s02c-a05`.

```python
def factory(protocol: ProtocolConfig, training_seed: int):
    run_dir = Path(os.environ["BOTS848_SCALABLE_RUN_DIR"]).resolve()
    checkpoint = CFCheckpoint.load(run_dir / "checkpoint.npz")
    checkpoint.require(protocol_sha256=protocol.sha256, training_seed=training_seed, capacity=dict(protocol.capacity["routes"]["cf_flow_l2"]))
    candidate = CFCandidate(checkpoint, protocol, run_dir)
    return candidate, CFDiagnostics(protocol, checkpoint.leakage_record)

manifest = freeze_manifest(
    run_dir=run_dir, project_root=solution_root, route="cf_flow_l2", attempt="s02c-a05",
    protocol=protocol, selected_update=protocol.training["optimizer_updates"], training_seed=seed,
    source_files=sorted(route_root.glob("*.py")),
    artifact_files={"checkpoint": checkpoint_path, "optimizer_state": optimizer_path, "training_log": training_log_path},
)
```

- [ ] **Step 4: Run full tests, N=8 smoke, and oracle-import audit**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests -q
python tracks/qmc/solutions/BOTS-848/train_cf_flow_l2.py --n8-smoke --training-seed 848 --run-dir D:/Playground/tmp/bots848-route-c-n8-smoke
rg -n "benchmark_v0\.(ed_oracle|fock_ed|projected_nqs|nqs_benchmark)" tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_flow_l2 tracks/qmc/solutions/BOTS-848/train_cf_flow_l2.py
git diff --check
```

- [ ] **Step 5: Freeze three seeds and close honestly**

Write the receipt with three manifest hashes, source/base/protocol hashes, byte sizes, maximum leakage, and classification. If strict LLL and all other pre-reveal gates pass, close `step-pass`; otherwise close `route-stopped` with the exact failed gate and retain the prototype evidence. Do not add exact projection, change the threshold, or create a sixth attempt.

```powershell
foreach ($seed in 848,1848,2848) {
  python tracks/qmc/solutions/BOTS-848/train_cf_flow_l2.py --training-seed $seed --run-dir "D:/Playground/output/BOTS-848/scalable-v1/route-c/seed-$seed"
  if ($LASTEXITCODE -ne 0) { throw "Route C training failed for seed $seed" }
}
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_flow_l2 tracks/qmc/solutions/BOTS-848/train_cf_flow_l2.py tracks/qmc/solutions/BOTS-848/tests/routes/test_cf_flow_adapter.py tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02c-a05.md tracks/qmc/solutions/BOTS-848/logs/scalable-v1/freezes/route-c-receipt.json
git commit -m "feat(qmc): freeze CF flow L2 route"
```

## Route C acceptance checklist

- [ ] `Q*=(N-1)/2` and the CG-coupled target is `L=2`, not `L=N`.
- [ ] Ground and excited sectors use one four-layer width-64 equivariant flow.
- [ ] Exchange and SO(3) covariance are measured after the flow.
- [ ] LLL leakage is independently calibrated, decomposed by seed/flow, and controls the certificate.
- [ ] A prototype failure is preserved and cannot be relabeled as strict LLL.
- [ ] Frozen coordinate amplitudes support the same post-reveal ED-fidelity estimator as Routes B and D.
- [ ] Three seed artifacts, N=8 smoke, manifests, resource metrics, and no-ED receipt exist.
