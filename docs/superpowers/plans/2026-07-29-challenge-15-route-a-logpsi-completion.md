# Challenge #15 Route A Log-Psi Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rescue A02 with a production log-wavefunction estimator, then complete and freeze the occupation-space autoregressive Route A through A03, A04, and A05 without ED reveal.

**Architecture:** Fixed-`N`, fixed-`M` dynamic programming supplies exact support masks and samplers.  A shared two-layer autoregressive network returns `log(psi)` and analytic scores; sparse Coulomb and ladder actions consume log amplitudes through a bounded complex row reducer.  A single reduced `M=0`, `L=2` state generates the five-component tower, and the common adapter binds the final three-seed checkpoints to frozen manifests.

**Tech Stack:** Python 3.11+, NumPy, SciPy, pytest, JSON/JSONL, Git worktrees, optional Slurm through the live SCNet profile.

---

## Immutable controls

- Comparison base SHA: `5aa9219f4cd24bc2274f0514b621c2f9b47cead7`.
- Protocol SHA-256: `2435cd2e72ffae88117ee194f45b15451c8653dafa755b732005b6a199251d38`.
- Physics: Haldane sphere, `N=6`, `2Q=15`, fully polarized fermions, LLL chord-distance Coulomb, `L=0` ground state and `L=2` neutral excitation.
- Seeds: `848, 1848, 2848`; hidden width `128`; hidden layers `2`.
- Production must not import `benchmark_v0.ed_oracle`, `benchmark_v0.fock_ed`, `benchmark_v0.projected_nqs`, or `benchmark_v0.nqs_benchmark`.
- No production full-basis enumeration, dense Hamiltonian, dense `L^2`, projector, Ritz solve, or ED-based checkpoint selection.
- A03's 16-update smoke trains only the two reduced `M=0` sectors.  After A04 supplies the tower and its score propagation, A05's full frozen training averages the five excited components exactly as required.
- Every implementation attempt uses a separate worktree, writes a journal, and has at most 90 minutes of active implementation.  A blocked problem gets at most five root-cause-driven attempts.  Attempt five failing closes the active goal as blocked.
- Acceptance amendment (2026-07-29): numerical correctness remains a hard gate, while the N=6 timing ratio is a reported resource metric and optimization backlog item rather than a blocking threshold.  This amendment is recorded in `2026-07-29-challenge-15-route-a-acceptance-amendment.md`.
- Each slice closes only after implementer self-review, external specification review, external code-quality review, and fresh main-agent verification.  No push is authorized.
- Slurm-first amendment (2026-07-29): after the reviewed A02 terminal, all A03-A05 pytest, RED/GREEN, smoke, performance, training, and final executable verification run only in SCNet compute-node Slurm allocations.  The controlling evidence and command substitutions are defined in `2026-07-29-challenge-15-route-a-slurm-first-amendment.md`; where this original plan shows a local Python command or permits optional Slurm, the amendment supersedes it.  Login nodes remain limited to staging, scheduler queries, submission, log tailing, and fetch.  The common scalable evaluator remains forbidden until the four-route barrier.

## File map

- Modify: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/operators.py` — sparse actions and log-domain row reduction.
- Modify: `tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_operators.py` — exact/log-shift/error/performance gates.
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/model.py` — shared autoregressive log-wavefunction and analytic scores.
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/train.py` — sampling, VMC covariances, Adam, checkpoints, and progress records.
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/tower.py` — log-domain ladder tower and fixed-`M` Metropolis sampler.
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/diagnostics.py` — construction, ladder, and finite-rotation residuals.
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/adapter.py` — common state/candidate contracts and resource metrics.
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/factory.py` — strict run-directory binding.
- Create: `tracks/qmc/solutions/BOTS-848/train_occupation_autoregressive.py` — smoke/full/N=8 CLI and manifest writer.
- Create/modify: `tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_training.py`, `test_occupation_tower.py`, and `test_occupation_adapter.py`.
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02a-a02-logpsi-rescue.md`, `s02a-a03.md`, `s02a-a04.md`, `s02a-a05.md`, and `freezes/route-a-receipt.json`.

### Task 1: A02 RED contract for log amplitudes

**Files:**
- Modify: `tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_operators.py`
- Test: `tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_operators.py`

- [ ] **Step 1: Add a test-only exact-vector log callback**

```python
def _logpsi_from_basis(basis, values):
    table = dict(zip(basis, values, strict=True))

    def logpsi(state):
        value = complex(table[state])
        if value == 0.0:
            return complex(-np.inf, 0.0)
        return complex(math.log(abs(value)), math.atan2(value.imag, value.real))

    return logpsi
```

- [ ] **Step 2: Add exact-matrix and global-shift tests for the wished-for API**

```python
@pytest.mark.parametrize("shift", [-1000.0, 0.0, 1000.0])
def test_log_local_energy_matches_direct_matrix_and_global_shift(shift):
    basis = fixed_m_basis(3, 6, 0.0)
    values = np.array([complex(i + 1, 0.25 * (-1) ** i) for i in range(len(basis))])
    base = _logpsi_from_basis(basis, values)
    shifted = lambda state: base(state) + complex(shift, 0.375)
    expected = hamiltonian_matrix(basis, PAIRS, V) @ values
    for index, state in enumerate(basis):
        assert local_energy(state, OPERATOR, shifted) == pytest.approx(
            expected[index] / values[index], abs=1.0e-12
        )
```

Add the corresponding negative/half-integer-`M` `local_l2` comparison using the existing exact fixture.

- [ ] **Step 3: Add zero, historical-regression, and coefficient-boundary tests**

```python
def test_log_row_skips_exact_zero_neighbor_but_rejects_zero_source():
    values = {1: 0.0j, 2: 1.0 + 0.0j}
    logpsi = _logpsi_from_basis((1, 2), (values[1], values[2]))
    assert local_from_log_neighbors(2, {1: 7.0}, logpsi) == 0.0j
    with pytest.raises(ValueError, match="sampled logpsi"):
        local_from_log_neighbors(1, {2: 1.0}, logpsi)


def test_log_row_rejects_unrepresentable_coefficient_components():
    bad = complex(1.0e308, math.ldexp(1.0, -1074))
    with pytest.raises(ValueError, match="coefficient component dynamic range"):
        local_from_log_neighbors(1, {2: bad}, lambda state: 0.0j)
```

Also encode the prior multiply-first and divide-first examples using finite log differences; both must return their finite mathematical values.

- [ ] **Step 4: Run RED and record the exact failure**

Run:

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_operators.py -q
```

Expected: collection or assertion failure because `local_from_log_neighbors` and the new `logpsi` signatures do not exist.  Save the command, exit code, failing test names, start time, and elapsed time for the rescue journal.

- [ ] **Step 5: Commit only the RED tests**

```powershell
git add tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_operators.py
git commit -m "test(qmc): specify logpsi occupation estimators"
```

### Task 2: A02 GREEN log-domain sparse estimator

**Files:**
- Modify: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/operators.py`
- Modify: `tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_operators.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02a-a02-logpsi-rescue.md`

- [ ] **Step 1: Replace the raw-amplitude public boundary**

Define:

```python
LogAmplitude = Callable[[int], complex]


def _validated_logpsi(logpsi, state, *, sampled):
    raw = complex(np.asarray(logpsi(state)).item())
    if sampled and (not math.isfinite(raw.real) or not math.isfinite(raw.imag)):
        raise ValueError("sampled logpsi must be finite")
    if not sampled and raw.real == -math.inf and math.isfinite(raw.imag):
        return None
    if not math.isfinite(raw.real) or not math.isfinite(raw.imag):
        raise ValueError("neighbor logpsi must be finite or exact zero")
    return raw
```

Delete the production `Amplitude` alias, `_amplitude_value`, `local_from_neighbors`, and the Fraction-based accumulator.  Do not add a compatibility overload.

- [ ] **Step 2: Validate coefficients without discarding rectangular components**

```python
def _coefficient_log_polar(value):
    coefficient = complex(np.asarray(value).item())
    if not math.isfinite(coefficient.real) or not math.isfinite(coefficient.imag):
        raise ValueError("neighbor coefficient must be finite")
    if coefficient == 0.0:
        return None
    scale = max(abs(coefficient.real), abs(coefficient.imag))
    _, exponent = math.frexp(scale)
    scaled_real = math.ldexp(coefficient.real, -exponent)
    scaled_imag = math.ldexp(coefficient.imag, -exponent)
    if (coefficient.real != 0.0 and scaled_real == 0.0) or (
        coefficient.imag != 0.0 and scaled_imag == 0.0
    ):
        raise ValueError("coefficient component dynamic range is unsupported")
    scaled = complex(scaled_real, scaled_imag)
    return math.log(abs(scaled)) + exponent * math.log(2.0), math.atan2(
        scaled.imag, scaled.real
    )
```

Use the same check during `PreparedPairOperator.build`, before caching nonzero columns.

- [ ] **Step 3: Implement the bounded complex row reducer**

```python
def local_from_log_neighbors(state, neighbors, logpsi):
    source = _validated_nonnegative_state(state)
    source_log = _validated_logpsi(logpsi, source, sampled=True)
    terms = []
    for target_raw, coefficient_raw in neighbors.items():
        target = _validated_nonnegative_state(target_raw)
        coefficient = _coefficient_log_polar(coefficient_raw)
        if coefficient is None:
            continue
        target_log = _validated_logpsi(logpsi, target, sampled=False)
        if target_log is None:
            continue
        coefficient_log_abs, coefficient_phase = coefficient
        delta = target_log - source_log
        terms.append((coefficient_log_abs + delta.real, coefficient_phase + delta.imag))
    if not terms:
        return 0.0j
    shift = max(log_abs for log_abs, _ in terms)
    real = math.fsum(math.exp(log_abs - shift) * math.cos(phase) for log_abs, phase in terms)
    imag = math.fsum(math.exp(log_abs - shift) * math.sin(phase) for log_abs, phase in terms)
    scaled = complex(real, imag)
    if scaled == 0.0:
        return 0.0j
    final_log_abs = shift + math.log(abs(scaled))
    if final_log_abs > math.log(np.finfo(np.float64).max):
        raise OverflowError("local estimator result is outside complex128 range")
    magnitude = math.exp(final_log_abs)
    result = magnitude * scaled / abs(scaled)
    if not math.isfinite(result.real) or not math.isfinite(result.imag):
        raise OverflowError("local estimator result is outside complex128 range")
    return complex(result)
```

Refactor `local_energy` and `local_l2` to call this function with `logpsi`.

- [ ] **Step 4: Run targeted GREEN and all regression gates**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_operators.py -q
python -m pytest tracks/qmc/solutions/BOTS-848/tests -q
python -m compileall -q tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive
rg -n "benchmark_v0\.(fock_ed|ed_oracle|projected_nqs|nqs_benchmark)|full_basis|hamiltonian_matrix|l_squared_matrix" tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive
git diff --check
```

Expected: both pytest commands pass; compilation is silent; `rg` exits `1` with no output; diff check is silent.

- [ ] **Step 5: Measure the actual coefficient range and N=6 hot path**

Use the public LLL Coulomb integral builder once outside the production module, prepare the `N=6, 2Q=15` operator, and report minimum/maximum nonzero magnitudes and median wall time over at least 200 local-energy evaluations.  Compare with parent commit `3145bfd`.  The ratio is a resource metric and optimization backlog item; it does not override a passing numerical-correctness certificate or block A02 solely for exceeding `2x`.

- [ ] **Step 6: Commit implementation and rescue journal**

```powershell
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/operators.py tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_operators.py
git commit -m "fix(qmc): move occupation estimators to logpsi"
git add tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02a-a02-logpsi-rescue.md
git commit -m "docs(qmc): record logpsi estimator rescue"
```

The journal records why raw amplitudes failed, RED/GREEN evidence, hashes, elapsed active time, coefficient range, timing, reviews, and `slice-pass` or the exact failed gate.

### Task 3: A03 shared autoregressive log-wavefunction

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/model.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_training.py`

- [ ] **Step 1: Create the A03 worktree from the reviewed A02 terminal SHA**

Use branch `challenge/qmc-chiral-graviton-scalable-v1-s02a-a03-logpsi` and worktree `D:/Playground/worktrees/quantum.harness/challenge-qmc-chiral-graviton-scalable-v1-s02a-a03-logpsi`.  Verify the exact parent SHA and protocol hash, then run the complete BOTS-848 suite before editing.

- [ ] **Step 2: Write RED tests for normalization, shared trunk, reproducibility, and analytic scores**

```python
def test_model_log_probabilities_normalize_on_tiny_support():
    model = AutoregressiveNQS.initialize(
        n_electrons=3, two_q=6, target_m2=0, width=8, layers=2, seed=848,
        max_trainable_parameters=262144,
    )
    support = FeasibilityTable.build(3, 6, 0).enumerate_support()
    for sector in ("ground", "excited"):
        log_norm = scipy.special.logsumexp(
            [2.0 * model.logpsi(state, sector).real for state in support]
        )
        assert log_norm == pytest.approx(0.0, abs=1.0e-12)
    assert model.trunk_parameter_ids("ground") == model.trunk_parameter_ids("excited")


def test_analytic_log_derivative_matches_central_difference():
    analytic = model.log_derivative(CONFIG, "ground")
    numeric = central_difference_all_parameters(model, CONFIG, "ground", step=1.0e-6)
    np.testing.assert_allclose(analytic, numeric, rtol=2.0e-5, atol=2.0e-7)
```

Also test deterministic initialization/sampling for seed `848`, infeasible state rejection, and parameter-cap rejection.

- [ ] **Step 3: Run RED**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_training.py -q
```

Expected: import failure because `model.py` does not exist.

- [ ] **Step 4: Implement the two-layer conditional model**

Represent each prefix as a fixed-length vector with processed occupations `0/1`, unprocessed orbitals `-1`, and three context scalars: orbital fraction, remaining-particle fraction, and remaining-`M2` fraction.  Use shared trunk arrays `W1,b1,W2,b2` and sector-specific two-branch amplitude and phase heads.  Mask infeasible choices with the `FeasibilityTable`, normalize allowed branch logits with `logsumexp`, and define

```python
logpsi = 0.5 * sum(log_probability_of_selected_branch) + 1j * sum(selected_branch_phase)
```

Store parameters in a deterministic flat tree with stable names and slices.  Reverse the cached two-layer tanh calculation analytically so `log_derivative` returns one complex value per flat parameter.  `sample` uses the same conditional probabilities and never enumerates support.

- [ ] **Step 5: Run GREEN and commit**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_training.py -q
python -m pytest tracks/qmc/solutions/BOTS-848/tests -q
git diff --check
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/model.py tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_training.py
git commit -m "feat(qmc): add shared autoregressive logpsi model"
```

### Task 4: A03 VMC, Adam, checkpoints, and deterministic smoke

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/train.py`
- Create: `tracks/qmc/solutions/BOTS-848/train_occupation_autoregressive.py`
- Modify: `tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_training.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02a-a03.md`

- [ ] **Step 1: Add RED tests for covariance, Adam, exact budgets, and atomic checkpoints**

Test `score_covariance` against an explicit NumPy expression, gradient clipping against a known vector, one Adam step against a hand-computed fixture, exactly `batch_size_per_sector` samples for both reduced sectors per update, JSONL updates `1..16`, final-update selection, and byte-identical checkpoint hashes for two smoke runs with seed `848`.

- [ ] **Step 2: Implement reduced-state VMC**

For A03 smoke, sample ground and excited `M=0` sectors only.  Compute local Coulomb energy and local `L^2` through the reviewed log estimator.  The reduced objective is

```python
objective = (
    energy_ground
    + energy_excited_m0
    + 0.25 * mean_l2_ground**2
    + 0.25 * (mean_l2_excited - 6.0) ** 2
    + 0.05 * variance_l2_excited
)
```

Use the complex VMC score covariance, frozen Adam hyperparameters, global gradient-norm clipping, exactly one final selected update, JSONL progress every 16 updates, and atomic `.npz` replacement every 128 updates.  No early stopping and no oracle access.

- [ ] **Step 3: Implement the CLI modes**

`--smoke-updates 16 --training-seed 848 --run-dir PATH` runs the reduced deterministic smoke.  `--n8-smoke` and the full frozen schedule are accepted only after the later tasks install their required adapters/tower; until then they fail with a clear feature-state error rather than silently changing the objective.

- [ ] **Step 4: Run smoke twice and compare artifacts**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_training.py -q
python tracks/qmc/solutions/BOTS-848/train_occupation_autoregressive.py --smoke-updates 16 --training-seed 848 --run-dir D:/Playground/tmp/bots848-route-a-a03-smoke-1
python tracks/qmc/solutions/BOTS-848/train_occupation_autoregressive.py --smoke-updates 16 --training-seed 848 --run-dir D:/Playground/tmp/bots848-route-a-a03-smoke-2
```

Expected: finite objective/gradient/L2 records, exact updates and sample counts, no oracle path, and equal checkpoint SHA-256 values.

- [ ] **Step 5: Commit and journal**

Commit code/tests as `feat(qmc): train reduced occupation logpsi states`, then commit `s02a-a03.md` with RED/GREEN, smoke hashes, elapsed time, peak RSS, and `slice-pass` or exact failure.

### Task 5: A04 log-domain ladder tower and score propagation

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/tower.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_tower.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02a-a04.md`

- [ ] **Step 1: Create the A04 worktree from the reviewed A03 terminal SHA and run the full baseline**

Use branch/worktree suffix `s02a-a04-logpsi`; record parent/protocol hashes before editing.

- [ ] **Step 2: Write RED tests against a tiny exact `L=2` fixture**

The tests construct one exact `M=0` coefficient vector, convert it to log amplitudes, build `M=-2..2`, verify norm one in each tiny fixed-`M` basis, verify local `L^2=6` below `1e-12`, and compare derived analytic log scores with central differences of the base parameters.

- [ ] **Step 3: Implement stable ladder actions**

`LadderTower.from_m0` uses inverse sparse ladder neighbors and the reviewed bounded log sum to evaluate each derived component.  Divide by the analytic spin-2 coefficient `sqrt(L(L+1)-M(M+1))` or `sqrt(L(L+1)-M(M-1))` in log magnitude.  Propagate scores through a linear action with normalized complex term weights:

```python
derived_score = sum(weight * parent_score(source) for source, weight in weights)
```

where `weights` sum to one in the complex amplitude ratio for the derived state.  Exact zeros remain `-inf` log amplitudes.

- [ ] **Step 4: Run exact tower GREEN and commit**

Run the tower test, operator tests, and complete suite; commit `tower.py` and tests as `feat(qmc): derive logpsi spin two tower`.

### Task 6: A04 reversible fixed-M sampler and SO(3) diagnostics

**Files:**
- Modify: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/tower.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/diagnostics.py`
- Modify: `tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_tower.py`

- [ ] **Step 1: Add RED tests for detailed balance and diagnostics**

Use a tiny exact target distribution to verify the transition matrix satisfies detailed balance.  Test all five sampled sectors, frozen burn-in reporting, deterministic seeds, ladder residual below `1e-12` on the fixture, and finite-rotation residual below `1e-10` on eight seeded probes.

- [ ] **Step 2: Implement a symmetric two-pair proposal**

Precompute all unordered orbital pairs grouped by equal `m1+m2`.  At each proposal, choose a group and two distinct pairs independently of the state; if one pair is fully occupied and the other fully empty, swap them, otherwise self-loop.  Because proposal selection is state independent, the nontrivial move and its reverse have equal probability.  Accept with

```python
min(1.0, math.exp(min(0.0, 2.0 * (logpsi_new.real - logpsi_old.real))))
```

using the equivalent stable branch that returns `1` for nonnegative log ratio.

- [ ] **Step 3: Implement construction and numerical diagnostics**

Return exactly `lll_residual`, `particle_swap_residual`, `finite_rotation_residual`, and `tower_ladder_residual`.  The first two are construction zeros.  Ladder is measured from sparse actions.  Finite rotations use spin-`Q` one-body matrices and determinant minors; tiny fixtures may sum their tiny support, while production uses seeded importance samples and never enumerates a physical basis.

- [ ] **Step 4: Run GREEN, common contract tests, commit, and close A04 journal**

Run tower tests, `test_scalable_evaluator.py`, and the complete suite.  Commit code/tests, then record residuals, timings, hashes, and review results in `s02a-a04.md`.

### Task 7: A05 common adapter, strict factory, N=8 smoke, and manifests

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/adapter.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/factory.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_adapter.py`
- Modify: `tracks/qmc/solutions/BOTS-848/train_occupation_autoregressive.py`

- [ ] **Step 1: Create the A05 worktree from the reviewed A04 terminal SHA and write RED contract tests**

Test runtime conformance to `StateHandle`, `CandidateAdapter`, and `DiagnosticProvider`; five multiplet keys; checkpoint/protocol/seed/manifest binding; source-file hashes; no capacity override; and rejection of mismatched or modified artifacts.

- [ ] **Step 2: Implement frozen state and candidate adapters**

`OccupationState` exposes batch `sample`, `logpsi`, `local_energy`, and `local_l2`.  `OccupationCandidate` exposes the ground state, five tower components, the exact LLL/antisymmetry/scalability certificate, and measured resources.  The factory resolves only `BOTS848_SCALABLE_RUN_DIR`, verifies the manifest and artifacts, and rejects protocol or seed mismatch.

- [ ] **Step 3: Complete atomic artifacts and manifest writing**

The CLI writes `checkpoint.npz`, `optimizer-state.npz`, and `training.jsonl`, then calls `freeze_manifest` with route `occupation_autoregressive`, attempt `s02a-a05`, final selected update, seed, all route source files, and all three artifacts.  It has no oracle, early-stop, width, layer, batch, or checkpoint-selection override.

- [ ] **Step 4: Implement and run the frozen N=8 no-training smoke**

Use `N=8`, `2Q=21`, seed `4848`, batch `256`, two warmups, and five measured repetitions.  Exercise support sampling, model/logpsi, sparse local energy/L2, tower evaluation, and adapter batching without optimizer updates.  Record time/RSS ratios against the same N=6 device fingerprint.

- [ ] **Step 5: Run audits and commit the adapter slice**

Run adapter tests, full suite, N=8 smoke, forbidden-import search, compilation, and diff check.  Commit code/tests; do not write the terminal receipt until all three full training seeds exist.

### Task 8: A05 tower-aware full training and three-seed freeze

**Files:**
- Modify: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/train.py`
- Modify: `tracks/qmc/solutions/BOTS-848/train_occupation_autoregressive.py`
- Modify: `tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_adapter.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/freezes/route-a-receipt.json`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02a-a05.md`

- [ ] **Step 1: Add RED tests for the full objective and frozen schedule**

Test that each update uses exactly `512` samples for the ground sector and each of five derived excited components, that the excited energy is the arithmetic mean over `M=-2..2`, that analytic tower scores enter the gradient covariance, that exactly `2048` updates are selected at the final update, and that no ED path is imported or opened.

- [ ] **Step 2: Implement the full tower-aware objective**

Use

```python
objective = (
    energy_ground
    + sum(energy_l2_by_m.values()) / 5.0
    + 0.25 * mean_l2_ground**2
    + 0.25 * (mean_l2_excited - 6.0) ** 2
    + 0.05 * variance_l2_excited
)
```

with the frozen Adam schedule and final-update selection.  Do not reinterpret `batch_size_per_sector`, reduce seeds, or add early stopping.

- [ ] **Step 3: Estimate placement before the first full run**

Extrapolate the A03 16-update smoke and A04 five-state cost to 2048 updates.  If projected wall exceeds 600 seconds or RSS exceeds 16 GiB, use the live SCNet profile and `/using-slurm`; query `sinfo` immediately before submission and request no more than 32 CPUs or 64 GiB.  Record only nonsecret host/partition/module/job metadata.

- [ ] **Step 4: Run and monitor seeds `848`, `1848`, and `2848`**

Use output directories `D:/Playground/output/BOTS-848/scalable-v1/route-a/seed-<seed>` locally or the corresponding remote scratch directories.  Monitor through first progress output and job completion, fetch artifacts, verify every manifest and hash, and reject incomplete logs, wrong sample counts, NaN/Inf, budget overruns, or seed/protocol mismatch.

- [ ] **Step 5: Write the freeze receipt and terminal journal**

The receipt records owner, route, attempt, source commit, comparison base, protocol hash, three seed manifest hashes, artifact byte sizes, resource fingerprints, N=8 status, and `route-frozen`.  It contains no checkpoint bytes, ED values, credentials, or private paths.

- [ ] **Step 6: Commit terminal artifacts**

```powershell
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive tracks/qmc/solutions/BOTS-848/train_occupation_autoregressive.py tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_adapter.py tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02a-a05.md tracks/qmc/solutions/BOTS-848/logs/scalable-v1/freezes/route-a-receipt.json
git commit -m "feat(qmc): freeze occupation autoregressive route"
```

### Task 9: Final independent Route A audit

**Files:**
- Verify only; amend the A05 journal/receipt only if evidence is missing or inaccurate.

- [ ] **Step 1: Run the complete verification matrix fresh**

Run all route tests, complete BOTS-848 tests, compileall, forbidden-import and forbidden-path searches, `git diff --check`, clean status, protocol hash, manifest verification for all seeds, N=8 record validation, and `origin/master...HEAD` scope inspection.  Do not run the common ED evaluator before the four-route barrier.

- [ ] **Step 2: Perform final specification and quality reviews**

Review every acceptance item against code, tests, journals, and receipts.  Critical or Important findings return to the same step under the five-attempt/90-minute policy and must be re-reviewed after correction.

- [ ] **Step 3: Close the goal**

Mark the goal complete only when Route A is `step-pass`, the three seed freezes and N=8 smoke are verified, the branch is clean, and no required work remains.  If the same blocking problem reaches five failed attempts, write the final failure journal, preserve every worktree, mark the goal blocked, and report the exact evidence and required architectural decision.
