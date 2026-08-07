# Challenge #15 Route A Occupation Autoregressive NQS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and freeze a scalable fixed-occupation autoregressive NQS for the shared `L=0` ground state and ladder-derived `L=2` multiplet.

**Architecture:** A dynamic-programming mask samples only fixed-`N`, fixed-`M` Slater configurations. A shared autoregressive trunk with sector heads supplies amplitudes and phases; sparse two-body and angular-momentum neighborhoods supply local energy and local `L^2` without a full basis. The five excited components are derived from one frozen `M=0` state by analytic ladder actions and are judged by the common evaluator.

**Tech Stack:** Python 3.11+, NumPy, SciPy, pytest, JSON, Git worktrees.

---

## Immutable lane boundary

- Owner: `TensorSpicyJ`.
- Route key: `occupation_autoregressive`.
- First branch/worktree: `challenge/qmc-chiral-graviton-scalable-v1-s02a-a01` and `D:/Playground/worktrees/quantum.harness/challenge-qmc-chiral-graviton-scalable-v1-s02a-a01`.
- Start at the exact post-admission four-route SHA recorded by `s01-route-d-admission.md`; copy that SHA and the new protocol SHA into every journal.
- Use `N=6, 2Q=15`, training seeds `848,1848,2848`, width `128`, two hidden layers, and the frozen optimizer/sample budgets.
- Production code may import `benchmark_v0.lll_coulomb` for public LLL Coulomb integrals. It may not import any prefix frozen in `protocol.oracle.forbidden_module_prefixes`.
- Each task below consumes one Route A attempt, has at most 90 minutes active implementation time, closes with `slice-pass`, `step-pass`, `failed`, or `inconclusive`, and writes `logs/scalable-v1/s02a-a0N.md` before another attempt starts.

## File map

- `scalable_v1/routes/occupation_autoregressive/constraints.py`: exact fixed-`N`, fixed-`M` feasibility DP and masked draws.
- `scalable_v1/routes/occupation_autoregressive/operators.py`: fermion signs, sparse Coulomb neighbors, ladder actions, and local estimators.
- `scalable_v1/routes/occupation_autoregressive/model.py`: shared two-layer autoregressive amplitude/phase network and analytic parameter scores.
- `scalable_v1/routes/occupation_autoregressive/train.py`: state-averaged VMC, `L^2` penalties, Adam, checkpoints, and progress log.
- `scalable_v1/routes/occupation_autoregressive/tower.py`: derived `M=-2,...,2` amplitudes and Metropolis sampler.
- `scalable_v1/routes/occupation_autoregressive/diagnostics.py`: swap, ladder, finite-rotation, and LLL residuals.
- `scalable_v1/routes/occupation_autoregressive/adapter.py`: common `StateHandle`/`CandidateAdapter` surface and resource record.
- `scalable_v1/routes/occupation_autoregressive/factory.py`: `factory(protocol, training_seed)` bound to a frozen run directory.
- `train_occupation_autoregressive.py`: route CLI and manifest writer.
- `tests/routes/`: route-only RED/GREEN tests; tiny exact fixtures may import `benchmark_v0.fock_ed`, production files may not.

### Task 1 (`s02a-a01`): Exact constrained autoregressive support

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/__init__.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/__init__.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/constraints.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_constraints.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02a-a01.md`

- [ ] **Step 1: Create the isolated attempt from the admitted SHA**

```powershell
$match = Get-Content tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s01-route-d-admission.md | Select-String '^comparison_base_sha: `([0-9a-f]{40})`$'
$routeBase = $match.Matches.Groups[1].Value
if ($routeBase.Length -ne 40) { throw 'missing comparison_base_sha' }
git worktree add D:/Playground/worktrees/quantum.harness/challenge-qmc-chiral-graviton-scalable-v1-s02a-a01 `
  -b challenge/qmc-chiral-graviton-scalable-v1-s02a-a01 $routeBase
git rev-parse HEAD
python -c "import sys; sys.path.insert(0,r'tracks/qmc/solutions/BOTS-848'); from scalable_v1.protocol import load_protocol; print(load_protocol().sha256)"
```

Expected: the commit and protocol hashes equal the admission journal; never substitute a moving branch name.

- [ ] **Step 2: Write the failing support and reproducibility tests**

```python
def test_dp_support_equals_tiny_exact_fixed_m_basis():
    table = FeasibilityTable.build(n_electrons=3, two_q=6, target_m2=0)
    exact = set(fixed_m_basis(3, 6, 0.0))
    assert set(table.enumerate_support()) == exact

def test_masked_sampler_never_leaves_n_m_sector():
    table = FeasibilityTable.build(n_electrons=6, two_q=15, target_m2=0)
    draws = table.sample_uniform(256, seed=848)
    assert draws.tolist() == table.sample_uniform(256, seed=848).tolist()
    assert all(x.bit_count() == 6 and occupation_m2(x, 15) == 0 for x in draws)
```

Run:

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_constraints.py -q
```

Expected: FAIL because the route package does not exist.

- [ ] **Step 3: Implement the backward feasibility recurrence and masked draw**

```python
@dataclass(frozen=True)
class FeasibilityTable:
    n_electrons: int
    two_q: int
    target_m2: int
    counts: dict[tuple[int, int, int], int]

    @classmethod
    def build(cls, n_electrons: int, two_q: int, target_m2: int):
        counts = {(two_q + 1, 0, 0): 1}
        for orbital in range(two_q, -1, -1):
            m2 = -two_q + 2 * orbital
            for remaining in range(n_electrons + 1):
                for target in range(-n_electrons * two_q, n_electrons * two_q + 1):
                    counts[(orbital, remaining, target)] = (
                        counts.get((orbital + 1, remaining, target), 0)
                        + (counts.get((orbital + 1, remaining - 1, target - m2), 0) if remaining else 0)
                    )
        if counts.get((0, n_electrons, target_m2), 0) == 0:
            raise ValueError("empty fixed-N fixed-M sector")
        return cls(n_electrons, two_q, target_m2, counts)

    def allowed(self, orbital: int, remaining: int, target_m2: int) -> tuple[bool, bool]:
        m2 = -self.two_q + 2 * orbital
        zero = self.counts.get((orbital + 1, remaining, target_m2), 0) > 0
        one = remaining > 0 and self.counts.get((orbital + 1, remaining - 1, target_m2 - m2), 0) > 0
        return zero, one
```

`sample_uniform` must use the two completion counts as exact branch weights and `numpy.random.default_rng(seed)`; `enumerate_support` is test-only recursion over nonzero DP branches and must raise for `N>4` so production never enumerates a physical sector.

- [ ] **Step 4: Run GREEN, the no-enumeration guard, and commit**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_constraints.py -q
rg -n "combinations|full_basis|fixed_m_basis" tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive
git diff --check
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_constraints.py
git commit -m "feat(qmc): add constrained autoregressive support"
```

Expected: tests pass; `rg` has no production match; `git diff --check` is silent.

- [ ] **Step 5: Close the attempt journal**

Record hypothesis, base/protocol hashes, commands, elapsed active time, peak RSS, failing-test evidence, result `slice-pass`, and next risk “sparse estimator signs”. Commit it with `docs(qmc): record route A attempt a01`.

```powershell
git add tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02a-a01.md
git commit -m "docs(qmc): record route A attempt a01"
```

### Task 2 (`s02a-a02`): Sparse Coulomb and Casimir estimators

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/operators.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_operators.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02a-a02.md`

- [ ] **Step 1: Branch a new worktree from the terminal a01 commit and write RED tests**

```python
def test_sparse_local_energy_matches_tiny_direct_matrix():
    basis = fixed_m_basis(3, 6, 0.0)
    state = basis[2]
    amplitudes = {x: complex(i + 1) for i, x in enumerate(basis)}
    expected = (hamiltonian_matrix(basis, PAIRS, V) @ np.array(list(amplitudes.values())))[2] / amplitudes[state]
    assert local_energy(state, amplitudes.__getitem__, PAIRS, V) == pytest.approx(expected)

def test_sparse_local_l2_matches_tiny_direct_matrix():
    expected = (l_squared_matrix(BASIS, two_q=6, target_m=0.0) @ PSI)[INDEX] / PSI[INDEX]
    assert local_l2(BASIS[INDEX], AMP, two_q=6, target_m=0) == pytest.approx(expected)
```

Run the file and expect import failure.

- [ ] **Step 2: Implement route-local fermion algebra and polynomial neighborhoods**

```python
def apply_one_body(state: int, create: int, annihilate: int) -> tuple[int, int] | None:
    if not state & (1 << annihilate):
        return None
    sign = -1 if (state & ((1 << annihilate) - 1)).bit_count() % 2 else 1
    state ^= 1 << annihilate
    if state & (1 << create):
        return None
    sign *= -1 if (state & ((1 << create) - 1)).bit_count() % 2 else 1
    return state | (1 << create), sign

def ladder_neighbors(state: int, two_q: int, direction: int):
    for orbital in range(two_q + 1):
        target = orbital + direction
        if not 0 <= target <= two_q:
            continue
        applied = apply_one_body(state, target, orbital)
        if applied is not None:
            coefficient = math.sqrt((two_q - min(orbital, target)) * (min(orbital, target) + 1))
            yield applied[0], applied[1] * coefficient
```

Implement two-body signs locally, loop only over occupied source pairs and nonzero target pairs, and accumulate duplicate target bitsets before evaluating amplitude ratios.

- [ ] **Step 3: Implement local estimators from amplitude callbacks**

```python
def local_from_neighbors(state, amplitude, neighbors):
    denominator = amplitude(state)
    if abs(denominator) < 1e-300:
        raise FloatingPointError("sampled amplitude is numerically zero")
    return sum(matrix_element * amplitude(target) for target, matrix_element in neighbors) / denominator

def local_l2(state, amplitude, *, two_q, target_m):
    raised = ladder_neighbors(state, two_q, +1)
    chained = compose_ladders(raised, two_q, -1)
    return target_m * (target_m + 1) + local_from_neighbors(state, amplitude, chained)
```

`compose_ladders` must merge identical final bitsets and include the diagonal return path; its work is bounded by `O(N^2)` per sampled configuration.

- [ ] **Step 4: Run exact tests and production-import audit**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_operators.py -q
rg -n "benchmark_v0\.(fock_ed|ed_oracle|projected_nqs|nqs_benchmark)" tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive
git diff --check
```

Expected: tiny matrix agreement below `1e-12`; forbidden-import `rg` has no matches.

- [ ] **Step 5: Commit code and a02 journal**

Commit production/tests as `feat(qmc): add sparse occupation estimators`, then journal the RED/GREEN evidence and close `slice-pass`.

```powershell
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/operators.py tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_operators.py
git commit -m "feat(qmc): add sparse occupation estimators"
git add tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02a-a02.md
git commit -m "docs(qmc): record route A attempt a02"
```

### Task 3 (`s02a-a03`): Shared trunk, sector heads, and state-averaged VMC

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/model.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/train.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_training.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02a-a03.md`

- [ ] **Step 1: Write RED tests for normalization, sharing, gradients, and budget**

```python
def test_shared_model_normalizes_each_sector_on_tiny_support():
    model = AutoregressiveNQS.initialize(two_q=6, width=8, layers=2, seed=848)
    for sector, target_l in (("ground", 0), ("excited", 2)):
        probability = sum(abs(model.amplitude(x, sector, target_m=0)) ** 2 for x in SUPPORT)
        assert probability == pytest.approx(1.0, abs=1e-12)
    assert model.trunk_parameter_ids("ground") == model.trunk_parameter_ids("excited")

def test_score_matches_central_difference():
    analytic = model.log_derivative(CONFIG, "ground")[PARAMETER]
    assert analytic == pytest.approx(central_difference(model, PARAMETER, CONFIG), rel=2e-5)
```

- [ ] **Step 2: Implement the width-128 two-layer conditional network**

```python
@dataclass
class AutoregressiveNQS:
    trunk: tuple[tuple[np.ndarray, np.ndarray], ...]
    amplitude_heads: dict[str, tuple[np.ndarray, np.ndarray]]
    phase_heads: dict[str, tuple[np.ndarray, np.ndarray]]
    tables: dict[int, FeasibilityTable]

    def conditional(self, prefix, orbital, sector, remaining, remaining_m2):
        hidden = np.asarray(prefix, dtype=float)
        for weight, bias in self.trunk:
            hidden = np.tanh(weight @ hidden + bias)
        logits = self.amplitude_heads[sector][0] @ hidden + self.amplitude_heads[sector][1]
        allowed = self.tables[remaining_m2].allowed(orbital, remaining, remaining_m2)
        logits = np.where(np.asarray(allowed), logits, -np.inf)
        probabilities = np.exp(logits - scipy.special.logsumexp(logits))
        phase = float(self.phase_heads[sector][0] @ hidden + self.phase_heads[sector][1])
        return probabilities, phase
```

Store an explicit flat parameter tree and reverse-mode cache so `log_derivative` returns the analytic derivative of `log psi = 0.5*sum(log p) + 1j*sum(phase)`; reject any initialization above `max_trainable_parameters`.

- [ ] **Step 3: Implement the frozen Adam/VMC loop**

```python
objective = (
    energy_ground
    + sum(energy_l2_by_m.values()) / 5.0
    + 0.25 * (mean_l2_excited - 6.0) ** 2
    + 0.05 * variance_l2_excited
    + 0.25 * mean_l2_ground**2
)
gradient = score_covariance(local_objective, conjugate_scores)
parameters, adam_state = adam_update(
    parameters, gradient, learning_rate=protocol.training["learning_rate"],
    beta1=protocol.training["beta1"], beta2=protocol.training["beta2"],
    epsilon=protocol.training["epsilon"], clip_norm=protocol.training["gradient_clip_norm"],
)
```

Use exactly `batch_size_per_sector` samples per update, run exactly `optimizer_updates`, select only the final update, flush one JSON line every 16 updates, and atomically checkpoint every 128 updates. Do not add early stopping or ED-based selection.

- [ ] **Step 4: Run gradient/budget tests and a 16-update oracle-free smoke**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_training.py -q
python tracks/qmc/solutions/BOTS-848/train_occupation_autoregressive.py --smoke-updates 16 --training-seed 848 --run-dir D:/Playground/tmp/bots848-route-a-smoke
```

Expected: finite objective/gradients, monotonically increasing `update`, no oracle path in the log, and deterministic checkpoint hash on repeat.

- [ ] **Step 5: Commit and journal**

Commit as `feat(qmc): train shared occupation NQS`; journal whether the 16-update smoke is numerically stable. A NaN/Inf or failure to meet the exact sample budget closes `failed`, not `slice-pass`.

```powershell
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/model.py tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/train.py tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_training.py tracks/qmc/solutions/BOTS-848/train_occupation_autoregressive.py
git commit -m "feat(qmc): train shared occupation NQS"
git add tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02a-a03.md
git commit -m "docs(qmc): record route A attempt a03"
```

### Task 4 (`s02a-a04`): Ladder-derived five-component tower and SO(3) diagnostics

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/tower.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/diagnostics.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_tower.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02a-a04.md`

- [ ] **Step 1: Write RED tests against a tiny exact `L=2` vector**

```python
def test_ladder_tower_has_exact_normalization_and_casimir_on_fixture():
    tower = LadderTower.from_m0(FIXTURE_AMPLITUDE, two_q=6, l=2)
    assert set(tower) == {-2, -1, 0, 1, 2}
    for m, amplitude in tower.items():
        assert norm_on_basis(amplitude, FIXTURE_BASES[m]) == pytest.approx(1.0)
        assert max_local_l2_error(amplitude, m) < 1e-12

def test_finite_rotation_residual_is_small_for_fixture():
    assert finite_rotation_residual(FIXTURE_CANDIDATE, seed=3848, probes=8) < 1e-10
```

- [ ] **Step 2: Implement recursively normalized ladder amplitudes**

```python
def raised_amplitude(parent, state, *, two_q, l, m):
    coefficient = math.sqrt(l * (l + 1) - m * (m + 1))
    inverse = ladder_neighbors(state, two_q, -1)
    return sum(value * parent(source) for source, value in inverse) / coefficient

def lowered_amplitude(parent, state, *, two_q, l, m):
    coefficient = math.sqrt(l * (l + 1) - m * (m - 1))
    inverse = ladder_neighbors(state, two_q, +1)
    return sum(value * parent(source) for source, value in inverse) / coefficient
```

Build `M=±1,±2` from the single `M=0` checkpoint. The derived sampler uses reversible two-electron proposals that conserve `M`; acceptance is `min(1, abs(psi_new/psi_old)**2)` and returns the frozen burn-in value.

- [ ] **Step 3: Implement numerical diagnostics**

For a rotation `U` in the one-body spin-`Q` representation, compute each determinant matrix element as `det(U[np.ix_(occupied_out, occupied_in)])`. Estimate rotated amplitudes by importance sampling rather than summing a full basis. Return exactly:

```python
{
    "lll_residual": 0.0,
    "particle_swap_residual": 0.0,
    "finite_rotation_residual": maximum_relative_residual,
    "tower_ladder_residual": maximum_ladder_residual,
}
```

The two zero residuals are construction values: occupation Slater labels are already antisymmetric LLL states. Rotation and ladder residuals must be measured.

- [ ] **Step 4: Run tiny exact tests and the common diagnostic contract test**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_tower.py -q
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_scalable_evaluator.py -q
git diff --check
```

- [ ] **Step 5: Commit and journal**

Commit as `feat(qmc): derive occupation spin two tower`; record measured residuals and close `slice-pass` only if the fixture and stochastic estimator both meet their declared tolerances.

```powershell
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/tower.py tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/diagnostics.py tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_tower.py
git commit -m "feat(qmc): derive occupation spin two tower"
git add tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02a-a04.md
git commit -m "docs(qmc): record route A attempt a04"
```

### Task 5 (`s02a-a05`): Adapter, N=8 smoke, manifest, and terminal freeze

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/adapter.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/factory.py`
- Create: `tracks/qmc/solutions/BOTS-848/train_occupation_autoregressive.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_adapter.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02a-a05.md`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/freezes/route-a-receipt.json`

- [ ] **Step 1: Write the failing adapter/factory binding test**

```python
def test_factory_binds_protocol_seed_and_same_manifest_checkpoint(tmp_path, monkeypatch):
    run = train_fixture(tmp_path, route="occupation_autoregressive", seed=848)
    monkeypatch.setenv("BOTS848_SCALABLE_RUN_DIR", str(run))
    candidate, diagnostics = factory(load_protocol(), 848)
    assert candidate.name == "occupation-autoregressive-nqs"
    assert set(candidate.generate_multiplet()) == {-2, -1, 0, 1, 2}
    assert verify_manifest(run / "training-manifest.json", project_root=SOLUTION_ROOT, protocol=load_protocol(), expected_training_seed=848).valid
    assert candidate.checkpoint_sha256 == manifest_artifact_sha(run, "checkpoint")
```

- [ ] **Step 2: Implement the common interfaces and strict factory**

```python
def factory(protocol: ProtocolConfig, training_seed: int):
    run_dir = Path(os.environ["BOTS848_SCALABLE_RUN_DIR"]).resolve()
    checkpoint = load_checkpoint(run_dir / "checkpoint.npz")
    if checkpoint.protocol_sha256 != protocol.sha256 or checkpoint.training_seed != training_seed:
        raise ValueError("checkpoint protocol/seed mismatch")
    candidate = OccupationCandidate(checkpoint, protocol, run_dir)
    return candidate, OccupationDiagnostics(protocol)
```

`OccupationState.sample/logpsi/local_energy/local_l2`, `OccupationCandidate.ground_state/generate_multiplet/construction_certificate/resource_metrics`, and diagnostics must satisfy `runtime_checkable` common protocols. The construction statement must explicitly say “fixed-LLL Slater occupations; no full-basis allocation; ladder-derived tower”.

- [ ] **Step 3: Add training CLI, atomic artifacts, and frozen manifest**

The CLI must write `checkpoint.npz`, `optimizer-state.npz`, and `training.jsonl`, then call:

```python
freeze_manifest(
    run_dir=run_dir, project_root=solution_root,
    route="occupation_autoregressive", attempt="s02a-a05",
    protocol=protocol, selected_update=protocol.training["optimizer_updates"],
    training_seed=seed, source_files=sorted(route_root.glob("*.py")),
    artifact_files={"checkpoint": checkpoint, "optimizer_state": optimizer, "training_log": training_log},
)
```

The production CLI has no `--oracle`, `--early-stop`, or capacity override.

- [ ] **Step 4: Run full tests, N=8 no-training smoke, and audits**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests -q
python tracks/qmc/solutions/BOTS-848/train_occupation_autoregressive.py --n8-smoke --training-seed 848 --run-dir D:/Playground/tmp/bots848-route-a-n8-smoke
rg -n "benchmark_v0\.(ed_oracle|fock_ed|projected_nqs|nqs_benchmark)" tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive tracks/qmc/solutions/BOTS-848/train_occupation_autoregressive.py
git diff --check
```

Expected: all tests pass; smoke uses `N=8,2Q=21`, batch `256`, two warmups and five measured repetitions; forbidden-import `rg` has no match.

- [ ] **Step 5: Freeze all three seeds without ED reveal**

Run the full frozen training command once for each seed. Recompute artifact hashes, write the receipt with route key, attempt, source commit, protocol hash, base SHA, three manifest hashes, byte sizes, and status `route-frozen`; do not include checkpoints in Git and do not invoke `run_scalable_evaluator.py` before the four-route barrier.

```powershell
foreach ($seed in 848,1848,2848) {
  python tracks/qmc/solutions/BOTS-848/train_occupation_autoregressive.py --training-seed $seed --run-dir "D:/Playground/output/BOTS-848/scalable-v1/route-a/seed-$seed"
  if ($LASTEXITCODE -ne 0) { throw "Route A training failed for seed $seed" }
}
python -m pytest tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_adapter.py -q
```

- [ ] **Step 6: Close Route A**

Commit source/tests/receipt/journal as `feat(qmc): freeze occupation autoregressive route`. Classify `step-pass` only if all pre-reveal gates, resource ceilings, factory binding, and all three training seeds pass. Otherwise classify `route-stopped` at a05 and report the exact failed gates; do not create a sixth attempt.

```powershell
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive tracks/qmc/solutions/BOTS-848/train_occupation_autoregressive.py tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_adapter.py tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02a-a05.md tracks/qmc/solutions/BOTS-848/logs/scalable-v1/freezes/route-a-receipt.json
git commit -m "feat(qmc): freeze occupation autoregressive route"
```

## Route A acceptance checklist

- [ ] Fixed `N` and `M` are guaranteed by the DP support, not penalties.
- [ ] LLL membership and fermion antisymmetry are exact by occupation construction.
- [ ] No complete basis, Hamiltonian, `L^2` matrix, projector, or Ritz solve appears in production.
- [ ] One reduced checkpoint generates all five `M` components.
- [ ] `local_energy` and `local_l2` agree with independent `N<=4` matrices.
- [ ] Three frozen seeds, N=8 smoke, resource record, manifest hashes, and attempt journals exist.
- [ ] Frozen state handles expose amplitudes on sampled occupations so the common post-reveal ED-fidelity estimator can evaluate all six states.
- [ ] No ED artifact was read before freeze.
