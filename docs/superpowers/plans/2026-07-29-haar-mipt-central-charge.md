# Haar-Circuit MIPT Central-Charge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reproduce the Born-weighted Haar-circuit MIPT effective central charge at `p = 0.168` from exact-state measurement-record entropy on `L = 8, 10, 12, 14, 16, 18`.

**Architecture:** Separate exact trajectory evolution, statistical analysis, and recoverable production scheduling into three Python modules. Every trajectory is an independent atomic record; pilot statistics choose total samples per width, and the same records feed a weighted double finite-size fit and whole-trajectory bootstrap. A short local benchmark precedes the 64-trajectory pilot so the repository's ten-minute local-compute limit is enforced before expensive work starts.

**Tech Stack:** Python 3, NumPy, Matplotlib, `concurrent.futures.ProcessPoolExecutor`, standard-library JSON/CSV/path handling, pytest.

## Global Constraints

- Periodic even-length qubit chain; independent Haar `U(4)` gates.
- Even layers: `(0,1), (2,3), ...`; odd layers: `(1,2), ..., (L-1,0)`.
- Every half-brick gate layer is followed by its own independent `Z`-measurement layer.
- Each site is attempted independently with `p = 0.168`; outcomes use sequential conditional Born sampling in ascending site order.
- Widths: exactly `L = 8, 10, 12, 14, 16, 18`.
- Discard `4*L` half-layers and record the next `24*L` half-layers.
- Simulate global-Haar and single-qubit-Haar product initial states separately and average them with exactly one-half weight each.
- Use normalized flat `complex128` vectors of length `2**L`; never form a production `2**L`-by-`2**L` operator.
- Keep at most the state plus two state-sized temporaries per worker; `moveaxis` views must not be copied before the single `tensordot` output is assigned back.
- Retain `F_s = -sum(log(q_m))`; analyze `tilde_f_{L,s} = F_s/(24*L**2)`.
- Pilot: `64` trajectories per width and initial-state family.
- Allocation: minimum `512`, multiples of `64`, target width error `2e-4`, cap `25000` per family and width.
- Fit: `L_min = 8, 10, 12, 14`, `alpha = 0.81`, `1000` whole-trajectory bootstrap replicates, plus an `L^-4` stability fit.
- Keep bootstrap, anisotropy `0.09`, fit-form shift, and unpropagated `p_c = 0.168(5)` uncertainty separate.
- Do not scan `p`, compute subleading Lyapunov exponents, introduce MPS truncation, or substitute a dual-unitary circuit in this stage.
- Local compute only below ten projected minutes and 16 GB; otherwise use the configured Slurm workflow after showing the projection to the user.
- Pilot collection must not start production; production requires an explicit `--approved` flag.
- Set numerical-library thread counts to one before importing NumPy in worker processes.
- Do not push, update PR #218, or launch a gated pilot/production job without explicit user authorization.

---

## File Structure

- Create `scripts/haar_mipt_transfer.py`: state initialization, Haar gates, local action, Born measurements, and one trajectory.
- Create `scripts/tests/test_haar_mipt_transfer.py`: dense oracles, Haar checks, measurement statistics, and trajectory invariants.
- Create `scripts/haar_mipt_analysis.py`: aggregation, double fit, stability fit, bootstrap, tables, and figures.
- Create `scripts/tests/test_haar_mipt_analysis.py`: weighting, synthetic recovery, bootstrap, and artifact tests.
- Create `scripts/haar_mipt_production.py`: seeds, atomic records, resume, pilot allocation, projection, workers, and CLI.
- Create `scripts/tests/test_haar_mipt_production.py`: allocation, seed, resume, deadline, gate, and projection tests.
- Write generated data only under `results/haar_mipt_ceff/`.
- Reuse `scripts/harness_slurm.sh` and `scripts/harness_array_sbatch.sh`; keep cluster-specific settings in the active profile.

### Task 1: Exact-state initialization and Haar gate layers

**Files:**
- Create: `scripts/haar_mipt_transfer.py`
- Create: `scripts/tests/test_haar_mipt_transfer.py`

**Interfaces:**
- Produces: `haar_unitary_4(rng) -> np.ndarray`.
- Produces: `global_haar_state(L, rng) -> np.ndarray`.
- Produces: `product_haar_state(L, rng) -> np.ndarray`.
- Produces: `layer_pairs(L, parity) -> tuple[tuple[int, int], ...]`.
- Produces: `apply_two_qubit_gate_inplace(state, gate, sites, L) -> None`.
- Produces: `apply_gate_layer(state, L, parity, rng) -> int`.
- Convention: `state.reshape((2,)*L)` axis `q` is qubit `q`; local gate order is `|00>, |01>, |10>, |11>` for `(q0,q1)`.

Start `test_haar_mipt_transfer.py` with an explicit script loader:

```python
_SCRIPT = Path(__file__).resolve().parents[1] / "haar_mipt_transfer.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("haar_mipt_transfer", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["haar_mipt_transfer"] = module
    spec.loader.exec_module(module)
    return module
```

- [ ] **Step 1: Write failing geometry and dense-oracle tests**

```python
def _dense_apply(state, gate, sites, L):
    q0, q1 = sites
    out = np.zeros_like(state)
    for source in range(1 << L):
        bits = [(source >> (L - 1 - q)) & 1 for q in range(L)]
        local_in = 2 * bits[q0] + bits[q1]
        for local_out in range(4):
            target_bits = bits.copy()
            target_bits[q0], target_bits[q1] = divmod(local_out, 2)
            target = sum(bit << (L - 1 - q) for q, bit in enumerate(target_bits))
            out[target] += gate[local_out, local_in] * state[source]
    return out


def test_layer_pairs_include_periodic_odd_gate():
    module = _load_module()
    assert module.layer_pairs(6, 0) == ((0, 1), (2, 3), (4, 5))
    assert module.layer_pairs(6, 1) == ((1, 2), (3, 4), (5, 0))


@pytest.mark.parametrize("sites", [(0, 1), (1, 2), (3, 0)])
def test_local_gate_matches_dense_oracle(sites):
    module = _load_module()
    rng = np.random.default_rng(17)
    state = module.global_haar_state(4, rng)
    gate = module.haar_unitary_4(rng)
    expected = _dense_apply(state, gate, sites, 4)
    module.apply_two_qubit_gate_inplace(state, gate, sites, 4)
    np.testing.assert_allclose(state, expected, rtol=2e-13, atol=2e-13)
```

- [ ] **Step 2: Write failing Haar and initialization tests**

```python
def test_haar_unitarity_and_low_moment():
    module = _load_module()
    rng = np.random.default_rng(41)
    values = []
    for _ in range(2000):
        gate = module.haar_unitary_4(rng)
        np.testing.assert_allclose(gate.conj().T @ gate, np.eye(4), atol=5e-13)
        values.append(abs(gate[0, 0]) ** 2)
    assert abs(np.mean(values) - 0.25) < 0.015


def test_haar_low_moments_are_left_unitary_invariant():
    module = _load_module()
    rng = np.random.default_rng(43)
    fixed = module.haar_unitary_4(np.random.default_rng(99))
    raw, rotated = [], []
    for _ in range(3000):
        gate = module.haar_unitary_4(rng)
        raw.append([abs(gate[0, 0])**2, abs(gate[0, 0])**4])
        transformed = fixed @ gate
        rotated.append([abs(transformed[0, 0])**2,
                        abs(transformed[0, 0])**4])
    np.testing.assert_allclose(np.mean(raw, axis=0), [.25, .1], atol=.015)
    np.testing.assert_allclose(np.mean(rotated, axis=0), [.25, .1], atol=.015)
    np.testing.assert_allclose(np.mean(raw, axis=0),
                               np.mean(rotated, axis=0), atol=.015)


@pytest.mark.parametrize("factory", ["global_haar_state", "product_haar_state"])
def test_initial_states_are_normalized_complex128(factory):
    module = _load_module()
    state = getattr(module, factory)(5, np.random.default_rng(7))
    assert state.shape == (32,)
    assert state.dtype == np.complex128
    np.testing.assert_allclose(np.vdot(state, state).real, 1.0, atol=3e-14)
```

- [ ] **Step 3: Run the focused tests and verify RED**

```powershell
python -m pytest scripts/tests/test_haar_mipt_transfer.py -q
```

Expected: import or attribute failures because the transfer interfaces do not exist.

- [ ] **Step 4: Implement Haar sampling and initial states**

```python
def haar_unitary_4(rng):
    z = (rng.normal(size=(4, 4)) + 1j * rng.normal(size=(4, 4))) / np.sqrt(2.0)
    q, r = np.linalg.qr(z)
    diagonal = np.diag(r)
    phases = np.where(np.abs(diagonal) > 0.0, diagonal / np.abs(diagonal), 1.0)
    return np.asarray(q * phases[np.newaxis, :], dtype=np.complex128)


def _haar_vector(dimension, rng):
    state = rng.normal(size=dimension) + 1j * rng.normal(size=dimension)
    state = np.asarray(state, dtype=np.complex128)
    state /= np.linalg.norm(state)
    return state


def global_haar_state(L, rng):
    if int(L) < 2:
        raise ValueError("L must be at least two")
    return _haar_vector(1 << int(L), rng)


def product_haar_state(L, rng):
    if int(L) < 2:
        raise ValueError("L must be at least two")
    state = np.array([1.0 + 0.0j], dtype=np.complex128)
    for _ in range(int(L)):
        state = np.kron(state, _haar_vector(2, rng))
    return np.asarray(state, dtype=np.complex128)
```

- [ ] **Step 5: Implement the generic local-gate path**

```python
def layer_pairs(L, parity):
    L, parity = int(L), int(parity)
    if L < 2 or L % 2 or parity not in (0, 1):
        raise ValueError("L must be even and parity must be zero or one")
    return tuple(((parity + 2*j) % L, (parity + 2*j + 1) % L)
                 for j in range(L // 2))


def apply_two_qubit_gate_inplace(state, gate, sites, L):
    q0, q1 = map(int, sites)
    if state.dtype != np.complex128 or state.shape != (1 << int(L),):
        raise ValueError("state must be flat complex128 with length 2**L")
    if np.shape(gate) != (4, 4) or q0 == q1:
        raise ValueError("invalid gate or sites")
    tensor = state.reshape((2,) * int(L))
    moved = np.moveaxis(tensor, (q0, q1), (0, 1))
    acted = np.tensordot(np.asarray(gate).reshape(2, 2, 2, 2), moved,
                         axes=((2, 3), (0, 1)))
    state[:] = np.moveaxis(acted, (0, 1), (q0, q1)).reshape(-1)


def apply_gate_layer(state, L, parity, rng):
    pairs = layer_pairs(L, parity)
    for pair in pairs:
        apply_two_qubit_gate_inplace(state, haar_unitary_4(rng), pair, L)
    return len(pairs)
```

- [ ] **Step 6: Run Task 1 tests and commit**

```powershell
python -m pytest scripts/tests/test_haar_mipt_transfer.py -q
git add scripts/haar_mipt_transfer.py scripts/tests/test_haar_mipt_transfer.py
git commit -m "Add matrix-free Haar circuit gates"
```

Expected: all Task 1 tests pass before the commit.

### Task 2: Sequential Born measurements and complete trajectories

**Files:**
- Modify: `scripts/haar_mipt_transfer.py`
- Modify: `scripts/tests/test_haar_mipt_transfer.py`

**Interfaces:**
- Produces: `measure_z_inplace(state, site, L, rng) -> tuple[int, float]`.
- Produces: `apply_measurement_layer(state, L, p, rng, accumulate_cost) -> dict`.
- Produces: `run_trajectory(L, p, seed, initial_family, burn_in_steps=None, record_steps=None) -> dict`.
- Record keys: `schema_version`, `L`, `p`, `initial_family`, `seed`, `burn_in_steps`, `record_steps`, `record_cost`, `cumulative_record_cost`, `runtime_seconds`, `gate_count`, `attempted_measurements`, `outcome_counts`.

- [ ] **Step 1: Write failing probability and empirical-frequency tests**

```python
def test_measurement_probability_and_post_state():
    module = _load_module()
    state = np.array([np.sqrt(0.8), 0.0, np.sqrt(0.2), 0.0], dtype=np.complex128)
    outcome, probability = module.measure_z_inplace(
        state, site=0, L=2, rng=np.random.default_rng(3))
    assert probability == pytest.approx(0.8 if outcome == 0 else 0.2)
    assert np.vdot(state, state).real == pytest.approx(1.0, abs=2e-14)
    assert np.linalg.norm(state.reshape(2, 2)[1-outcome]) == pytest.approx(0.0)


def test_empirical_born_frequency():
    module = _load_module()
    outcomes = []
    for seed in range(3000):
        state = np.array([np.sqrt(0.7), np.sqrt(0.3)], dtype=np.complex128)
        outcomes.append(module.measure_z_inplace(
            state, 0, 1, np.random.default_rng(seed))[0])
    assert abs(np.mean(outcomes) - 0.3) < 0.025
```

- [ ] **Step 2: Write failing dense-period, zero-cost, and reproducibility tests**

```python
def test_even_odd_period_matches_dense_oracle(monkeypatch):
    module = _load_module()
    rng = np.random.default_rng(9)
    state = module.global_haar_state(4, rng)
    gates = [module.haar_unitary_4(rng) for _ in range(4)]
    expected = state.copy()
    for gate, pair in zip(gates, ((0,1), (2,3), (1,2), (3,0))):
        expected = _dense_apply(expected, gate, pair, 4)
    iterator = iter(gates)
    monkeypatch.setattr(module, "haar_unitary_4", lambda ignored: next(iterator))
    module.apply_gate_layer(state, 4, 0, rng)
    module.apply_gate_layer(state, 4, 1, rng)
    np.testing.assert_allclose(state, expected, atol=3e-13)


def test_measured_basis_state_has_zero_cost():
    module = _load_module()
    state = np.array([0, 0, 1, 0], dtype=np.complex128)
    result = module.apply_measurement_layer(
        state, L=2, p=1.0, rng=np.random.default_rng(5), accumulate_cost=True)
    assert result["attempted"] == 2
    assert result["cost"] == pytest.approx(0.0)
```

Also assert for both initial families that identical seeds reproduce every field except runtime, and that `p=0`, `burn_in_steps=3`, `record_steps=5` gives zero attempts, zero cost, and five zero cumulative values.

```python
@pytest.mark.parametrize("family", ["global_haar", "product"])
def test_trajectory_is_reproducible_and_p_zero_has_zero_cost(family):
    module = _load_module()
    kwargs = dict(L=4, p=0.0, seed=73, initial_family=family,
                  burn_in_steps=3, record_steps=5)
    first, second = module.run_trajectory(**kwargs), module.run_trajectory(**kwargs)
    assert first["record_cost"] == 0.0
    assert first["attempted_measurements"] == 0
    assert first["cumulative_record_cost"] == [0.0] * 5
    for key in first.keys() - {"runtime_seconds"}:
        assert first[key] == second[key]
```

- [ ] **Step 3: Run the focused tests and verify RED**

```powershell
python -m pytest scripts/tests/test_haar_mipt_transfer.py -q
```

Expected: new tests fail on missing measurement and trajectory interfaces.

- [ ] **Step 4: Implement audited projective measurement**

```python
def measure_z_inplace(state, site, L, rng):
    tensor = state.reshape((2,) * int(L))
    norm2 = float(np.vdot(state, state).real)
    q0_raw = float(np.sum(np.abs(np.take(tensor, 0, axis=int(site))) ** 2))
    tolerance = 128.0 * np.finfo(np.float64).eps * max(1.0, norm2)
    if q0_raw < -tolerance or q0_raw > norm2 + tolerance:
        raise FloatingPointError("Born probability outside numerical tolerance")
    q0 = float(np.clip(q0_raw / norm2, 0.0, 1.0))
    outcome = int(rng.random() >= q0)
    probability = q0 if outcome == 0 else 1.0 - q0
    if probability <= np.finfo(np.float64).tiny:
        raise FloatingPointError("sampled outcome below positive threshold")
    index = [slice(None)] * int(L)
    index[int(site)] = 1 - outcome
    tensor[tuple(index)] = 0.0
    state /= np.sqrt(probability * norm2)
    return outcome, probability
```

- [ ] **Step 5: Implement measurement layers and trajectories**

```python
def apply_measurement_layer(state, L, p, rng, accumulate_cost):
    selected = np.flatnonzero(rng.random(int(L)) < float(p))
    cost, outcomes = 0.0, [0, 0]
    for site in selected:
        outcome, probability = measure_z_inplace(state, int(site), L, rng)
        outcomes[outcome] += 1
        if accumulate_cost:
            cost -= float(np.log(probability))
    return {"cost": cost, "attempted": int(selected.size), "outcomes": outcomes}


def run_trajectory(L, p, seed, initial_family,
                   burn_in_steps=None, record_steps=None):
    L, p, seed = int(L), float(p), int(seed)
    if L < 2 or L % 2 or not 0.0 <= p <= 1.0:
        raise ValueError("invalid even width or measurement probability")
    burn = 4*L if burn_in_steps is None else int(burn_in_steps)
    record = 24*L if record_steps is None else int(record_steps)
    if burn < 0 or record <= 0:
        raise ValueError("invalid trajectory lengths")
    rng = np.random.default_rng(seed)
    factories = {"global_haar": global_haar_state, "product": product_haar_state}
    if initial_family not in factories:
        raise ValueError("unknown initial-state family")
    state = factories[initial_family](L, rng)
    cumulative, total_cost = [], 0.0
    attempted, outcomes, gates = 0, [0, 0], 0
    started = time.perf_counter()
    for step in range(burn + record):
        gates += apply_gate_layer(state, L, step % 2, rng)
        result = apply_measurement_layer(state, L, p, rng, step >= burn)
        attempted += result["attempted"]
        outcomes = [outcomes[j] + result["outcomes"][j] for j in (0, 1)]
        if step >= burn:
            total_cost += result["cost"]
            cumulative.append(total_cost)
    return {"schema_version": 1, "L": L, "p": p,
            "initial_family": initial_family, "seed": seed,
            "burn_in_steps": burn, "record_steps": record,
            "record_cost": total_cost, "cumulative_record_cost": cumulative,
            "runtime_seconds": time.perf_counter() - started,
            "gate_count": gates, "attempted_measurements": attempted,
            "outcome_counts": outcomes}
```

- [ ] **Step 6: Run Task 2 tests and commit**

```powershell
python -m pytest scripts/tests/test_haar_mipt_transfer.py -q
git add scripts/haar_mipt_transfer.py scripts/tests/test_haar_mipt_transfer.py
git commit -m "Add Born-sampled Haar trajectories"
```

Expected: all transfer tests pass before the commit.

### Task 3: Equal-family aggregation and central-charge analysis

**Files:**
- Create: `scripts/haar_mipt_analysis.py`
- Create: `scripts/tests/test_haar_mipt_analysis.py`

**Interfaces:**
- Produces: `aggregate_trajectory_records(records) -> list[dict]`.
- Produces: `weighted_l2_fit(width_rows, lmin) -> dict`.
- Produces: `extrapolate_slopes(window_fits, alpha) -> dict`.
- Produces: `double_fit_central_charge(width_rows, alpha=0.81, lmins=(8,10,12,14)) -> dict`.
- Produces: `l4_stability_fit(width_rows, alpha=0.81) -> dict`.
- Produces: `bootstrap_central_charge(records, samples=1000, seed=0) -> np.ndarray`.
- Produces: `central_charge_summary(records, samples=1000, seed=0, alpha=0.81) -> tuple[list[dict], dict]`.
- Produces: `write_analysis_artifacts(records, width_rows, summary, output_dir) -> None`.

Start `test_haar_mipt_analysis.py` with an explicit loader and complete synthetic records:

```python
_SCRIPT = Path(__file__).resolve().parents[1] / "haar_mipt_analysis.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("haar_mipt_analysis", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["haar_mipt_analysis"] = module
    spec.loader.exec_module(module)
    return module


def _record(L, family, index, density, runtime=1.0):
    record_steps = 24*L
    return {"schema_version": 1, "L": L, "p": .168,
            "initial_family": family, "sample_index": index,
            "seed": 100000*L + 1000*(family == "product") + index,
            "burn_in_steps": 4*L, "record_steps": record_steps,
            "record_cost": density*L*record_steps,
            "cumulative_record_cost": [density*L*(j+1)
                                       for j in range(record_steps)],
            "runtime_seconds": runtime, "gate_count": 14*L**2,
            "attempted_measurements": 1, "outcome_counts": [1, 0]}


def _synthetic_records(seed, central_charge, per_family):
    rng = np.random.default_rng(seed)
    records = []
    for L in (8, 10, 12, 14, 16, 18):
        target = 1.7 - np.pi*.81*central_charge/(6*L**2)
        for family, shift in (("global_haar", .0005), ("product", -.0005)):
            for index in range(per_family):
                density = target + shift + 2e-5*rng.normal()
                records.append(_record(L, family, index, density))
    return records
```

- [ ] **Step 1: Write failing equal-weight aggregation tests**

```python
def test_aggregation_gives_families_equal_weight():
    module = _load_module()
    records = [_record(8, "global_haar", j, 1.0 + .01*j) for j in range(4)]
    records += [_record(8, "product", j, 3.0 + .02*j) for j in range(2)]
    row = module.aggregate_trajectory_records(records)[0]
    assert row["tilde_f"] == pytest.approx(
        .5 * (np.mean([1., 1.01, 1.02, 1.03]) + np.mean([3., 3.02])))
    expected_se = .5 * np.sqrt(np.var([1.,1.01,1.02,1.03], ddof=1)/4
                               + np.var([3.,3.02], ddof=1)/2)
    assert row["tilde_f_se"] == pytest.approx(expected_se)
```

Also reject duplicate `(L,family,sample_index)` keys and any width missing a family or having fewer than two trajectories in either family.

- [ ] **Step 2: Write failing fit, bootstrap, and artifact tests**

```python
def test_slope_extrapolation_recovers_known_central_charge():
    module = _load_module()
    alpha, expected_c = 0.81, 0.25
    m_inf = -np.pi * alpha * expected_c / 6.0
    fits = [{"lmin": lmin, "slope": m_inf + .7/lmin**2}
            for lmin in (8, 10, 12, 14)]
    result = module.extrapolate_slopes(fits, alpha)
    assert result["central_charge"] == pytest.approx(expected_c, abs=2e-13)


def test_bootstrap_and_artifacts_are_reproducible(tmp_path):
    module = _load_module()
    records = _synthetic_records(seed=7, central_charge=.25, per_family=20)
    widths, first = module.central_charge_summary(records, samples=40, seed=19)
    _, second = module.central_charge_summary(records, samples=40, seed=19)
    assert first["bootstrap_se"] == second["bootstrap_se"]
    assert abs(first["central_charge"] - .25) < .03
    module.write_analysis_artifacts(records, widths, first, tmp_path)
    names = {p.name for p in tmp_path.iterdir()}
    assert {"trajectory_summary.csv", "width_summary.csv", "fit_summary.json",
            "central_charge_fit.png", "record_entropy_growth.png"} <= names
```

- [ ] **Step 3: Run the analysis tests and verify RED**

```powershell
python -m pytest scripts/tests/test_haar_mipt_analysis.py -q
```

Expected: import failure because the analysis module does not exist.

- [ ] **Step 4: Implement trajectory-level aggregation**

```python
def aggregate_trajectory_records(records):
    rows = []
    for L in sorted({int(r["L"]) for r in records}):
        families = {}
        for family in ("global_haar", "product"):
            chosen = sorted((r for r in records if int(r["L"]) == L
                             and r["initial_family"] == family),
                            key=lambda r: int(r["sample_index"]))
            if len(chosen) < 2:
                raise ValueError(f"L={L} family={family} needs two trajectories")
            values = np.asarray([float(r["record_cost"])/(L*int(r["record_steps"]))
                                 for r in chosen])
            families[family] = {"count": len(chosen), "values": values,
                                "mean": float(values.mean()),
                                "se": float(values.std(ddof=1)/np.sqrt(len(values)))}
        mean = .5 * sum(item["mean"] for item in families.values())
        se = .5 * np.sqrt(sum(item["se"]**2 for item in families.values()))
        rows.append({"L": L, "tilde_f": mean, "tilde_f_se": se,
                     "families": families})
    return rows
```

- [ ] **Step 5: Implement primary and stability fits**

```python
def weighted_l2_fit(width_rows, lmin):
    selected = [row for row in width_rows if row["L"] >= int(lmin)]
    x = np.asarray([1.0/row["L"]**2 for row in selected])
    y = np.asarray([row["tilde_f"] for row in selected])
    sigma = np.asarray([row["tilde_f_se"] for row in selected])
    design = np.column_stack((np.ones_like(x), x))
    coef, _, _, _ = np.linalg.lstsq(design/sigma[:,None], y/sigma, rcond=None)
    return {"lmin": int(lmin), "intercept": float(coef[0]),
            "slope": float(coef[1]), "widths": [r["L"] for r in selected]}


def extrapolate_slopes(window_fits, alpha):
    x = np.asarray([1.0/fit["lmin"]**2 for fit in window_fits])
    y = np.asarray([fit["slope"] for fit in window_fits])
    correction, m_inf = np.polyfit(x, y, 1)
    return {"m0_inf": float(m_inf), "slope_correction": float(correction),
            "central_charge": float(-6*m_inf/(np.pi*float(alpha)))}


def double_fit_central_charge(width_rows, alpha=.81, lmins=(8,10,12,14)):
    windows = [weighted_l2_fit(width_rows, lmin) for lmin in lmins]
    return {"windows": windows, **extrapolate_slopes(windows, alpha)}


def l4_stability_fit(width_rows, alpha=.81):
    L = np.asarray([row["L"] for row in width_rows], dtype=float)
    y = np.asarray([row["tilde_f"] for row in width_rows])
    sigma = np.asarray([row["tilde_f_se"] for row in width_rows])
    design = np.column_stack((np.ones_like(L), L**-2, L**-4))
    coef, _, _, _ = np.linalg.lstsq(design/sigma[:,None], y/sigma, rcond=None)
    return {"intercept": float(coef[0]), "l2_coefficient": float(coef[1]),
            "l4_coefficient": float(coef[2]),
            "central_charge": float(-6*coef[1]/(np.pi*float(alpha)))}
```

Keep the four correlated slope extrapolations unweighted; the whole-trajectory bootstrap carries the statistical uncertainty.

- [ ] **Step 6: Implement bootstrap and artifacts**

Each bootstrap replicate resamples complete records independently within every `(L, initial_family)` group, recomputes the two family means and their equal-weight mean, and repeats the entire double fit using the original measured width standard errors as fixed weights. Reassign bootstrap `sample_index` values so duplicate draws remain valid independent entries:

```python
def bootstrap_central_charge(records, samples=1000, seed=0):
    rng = np.random.default_rng(seed)
    observed = aggregate_trajectory_records(records)
    fixed_errors = {row["L"]: row["tilde_f_se"] for row in observed}
    groups = {(L, family): [r for r in records if int(r["L"]) == L
                           and r["initial_family"] == family]
              for L in fixed_errors for family in ("global_haar", "product")}
    values = []
    for _ in range(int(samples)):
        resampled = []
        for group in groups.values():
            draws = rng.integers(0, len(group), size=len(group))
            for new_index, draw in enumerate(draws):
                item = dict(group[int(draw)])
                item["sample_index"] = new_index
                resampled.append(item)
        rows = aggregate_trajectory_records(resampled)
        for row in rows:
            row["tilde_f_se"] = fixed_errors[row["L"]]
        values.append(double_fit_central_charge(rows)["central_charge"])
    return np.asarray(values)
```

This avoids singular bootstrap weights while resampling the correct independent unit. The summary must contain:

```python
summary = {
    "central_charge": primary["central_charge"],
    "bootstrap_se": float(np.std(values, ddof=1)),
    "bootstrap_percentile_95": np.percentile(values, [2.5, 97.5]).tolist(),
    "alpha": .81, "alpha_se": .09,
    "anisotropy_error": abs(primary["central_charge"])*.09/.81,
    "stability_central_charge": stability["central_charge"],
    "fit_systematic": abs(primary["central_charge"]-stability["central_charge"]),
    "pc": .168, "pc_literature_error": .005, "pc_error_propagated": False,
    "literature_central_charge": .25, "literature_central_charge_error": .03,
}
```

Use the `Agg` backend. Plot `tilde_f_L` versus `1/L**2` with error bars and the asymptotic line. Plot equal-family mean cumulative record cost divided by `L*t` versus retained half-layer `t` as the linear-growth diagnostic.

- [ ] **Step 7: Run Task 3 tests and commit**

```powershell
python -m pytest scripts/tests/test_haar_mipt_analysis.py -q
git add scripts/haar_mipt_analysis.py scripts/tests/test_haar_mipt_analysis.py
git commit -m "Add Haar MIPT central-charge analysis"
```

Expected: all analysis tests pass before the commit.

### Task 4: Atomic resume, pilot allocation, and bounded scheduling

**Files:**
- Create: `scripts/haar_mipt_production.py`
- Create: `scripts/tests/test_haar_mipt_production.py`

**Interfaces:**
- Produces: `trajectory_seed(base_seed, L, family, sample_index) -> int`.
- Produces: `record_path(output_dir, L, family, sample_index) -> Path`.
- Produces: `write_trajectory_record_atomic(record, output_dir) -> Path`.
- Produces: `load_valid_records(output_dir, expected_config) -> tuple[list[dict], list[Path]]`.
- Produces: `build_tasks(sample_counts, completed) -> list[dict]`.
- Produces: `pilot_allocation(records, target_se=2e-4, minimum=512, batch=64, cap=25000) -> dict`.
- Produces: `project_runtime(records, requested_counts, workers) -> dict`.
- Produces: `run_ensemble(config, output_dir, approved=False, trajectory_runner=run_trajectory, executor_factory=ProcessPoolExecutor) -> dict`.
- `run_ensemble` returns a checkpoint dict with `actual_counts`, `requested_complete`, `deadline_reached`, `elapsed_seconds`, and `invalid_records`.

Start `test_haar_mipt_production.py` with the explicit loader and production-schema helpers:

```python
_SCRIPT = Path(__file__).resolve().parents[1] / "haar_mipt_production.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("haar_mipt_production", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["haar_mipt_production"] = module
    spec.loader.exec_module(module)
    return module


def _config(stage="pilot", sample_counts=None):
    sample_counts = {8: 2} if sample_counts is None else sample_counts
    return {"schema_version": 1, "stage": stage,
            "sizes": sorted(sample_counts), "sample_counts": sample_counts,
            "families": ["global_haar", "product"], "p": .168,
            "base_seed": 122168, "burn_in_multiplier": 4,
            "record_multiplier": 24, "workers": 2,
            "soft_deadline_seconds": 60.0}


def _production_record(L=8, family="global_haar", index=0,
                       density=1.0, runtime=1.0, seed=None):
    record_steps = 24*L
    family_code = {"global_haar": 0, "product": 1}[family]
    generated = np.random.SeedSequence([122168, L, family_code, index])
    seed = (int(generated.generate_state(1, dtype=np.uint64)[0])
            if seed is None else int(seed))
    return {"schema_version": 1, "L": L, "p": .168,
            "initial_family": family, "sample_index": index, "seed": seed,
            "burn_in_steps": 4*L, "record_steps": record_steps,
            "record_cost": density*L*record_steps,
            "cumulative_record_cost": [density*L*(j+1)
                                       for j in range(record_steps)],
            "runtime_seconds": runtime, "gate_count": 14*L**2,
            "attempted_measurements": 2, "outcome_counts": [1, 1]}


def _valid_record():
    return _production_record()


def _pilot_records_with_stdevs(L, haar_stdev, product_stdev, count):
    centered = np.arange(count, dtype=float) - .5*(count-1)
    centered /= centered.std(ddof=1)
    records = []
    for family, stdev in (("global_haar", haar_stdev),
                          ("product", product_stdev)):
        records.extend(_production_record(L, family, index, 1.0+stdev*z)
                       for index, z in enumerate(centered))
    return records


def _runtime_records(seconds, count):
    return [_production_record(8, family, index, runtime=seconds)
            for family in ("global_haar", "product")
            for index in range(count)]
```

- [ ] **Step 1: Write failing seed, allocation, and projection tests**

```python
def test_seeds_are_unique_across_family_width_and_index():
    module = _load_module()
    seeds = {module.trajectory_seed(122168, L, family, index)
             for L in (8, 10, 12)
             for family in ("global_haar", "product")
             for index in range(20)}
    assert len(seeds) == 120


def test_pilot_allocation_uses_equal_family_variance():
    module = _load_module()
    records = _pilot_records_with_stdevs(L=8, haar_stdev=.003,
                                         product_stdev=.004, count=64)
    allocation = module.pilot_allocation(records)
    effective = .5*np.sqrt(.003**2 + .004**2)
    expected = 64*math.ceil(max(512, (effective/2e-4)**2)/64)
    assert allocation[8]["requested_per_family"] == expected
    assert not allocation[8]["cap_limited"]


def test_projection_selects_remote_above_ten_minutes():
    module = _load_module()
    records = _runtime_records(seconds=10.0, count=64)
    projected = module.project_runtime(records, {8: 512}, workers=8)
    assert projected["projected_wall_seconds"] > 600
    assert projected["route"] == "remote"
```

- [ ] **Step 2: Write failing atomic-resume, deadline, and gate tests**

```python
def test_atomic_records_resume_and_reject_malformed_files(tmp_path):
    module = _load_module()
    config = _config(stage="pilot", sample_counts={8: 2})
    path = module.write_trajectory_record_atomic(_valid_record(), tmp_path)
    bad = path.with_name("trajectory_00001.json")
    bad.write_text("{broken", encoding="utf-8")
    records, invalid = module.load_valid_records(tmp_path, config)
    assert len(records) == 1
    assert invalid == [bad]
    assert not path.with_suffix(".json.tmp").exists()


def test_production_requires_explicit_approval(tmp_path):
    module = _load_module()
    with pytest.raises(PermissionError, match="--approved"):
        module.run_ensemble(_config(stage="production", sample_counts={8: 2}),
                            tmp_path, approved=False)
```

Use a two-worker `ThreadPoolExecutor` and this slow deterministic runner to verify that running futures drain while no replacement is submitted after the deadline:

```python
def _slow_fake_trajectory(**kwargs):
    time.sleep(.03)
    return _production_record(L=int(kwargs["L"]),
                              family=kwargs["initial_family"],
                              density=1.0, runtime=.03,
                              seed=int(kwargs["seed"]))


def test_deadline_drains_running_tasks_without_replacement(tmp_path):
    module = _load_module()
    config = _config(sample_counts={8: 3})
    config["soft_deadline_seconds"] = .01
    result = module.run_ensemble(config, tmp_path,
                                 trajectory_runner=_slow_fake_trajectory,
                                 executor_factory=ThreadPoolExecutor)
    assert sum(result["actual_counts"].values()) == 2
    assert result["deadline_reached"]
    assert not result["requested_complete"]
```

- [ ] **Step 3: Run production tests and verify RED**

```powershell
python -m pytest scripts/tests/test_haar_mipt_production.py -q
```

Expected: import failure because the production module does not exist.

- [ ] **Step 4: Implement task identity and atomic records**

```python
FAMILY_CODES = {"global_haar": 0, "product": 1}


def trajectory_seed(base_seed, L, family, sample_index):
    sequence = np.random.SeedSequence(
        [int(base_seed), int(L), FAMILY_CODES[str(family)], int(sample_index)])
    return int(sequence.generate_state(1, dtype=np.uint64)[0])


def record_path(output_dir, L, family, sample_index):
    return (Path(output_dir)/"records"/f"L{int(L)}"/str(family)
            /f"trajectory_{int(sample_index):05d}.json")


def write_trajectory_record_atomic(record, output_dir):
    path = record_path(output_dir, record["L"], record["initial_family"],
                       record["sample_index"])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(_jsonable(record), handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)
    return path
```

Validation requires exact `L`, `p`, family, sample-index range, deterministic seed, `4*L` burn-in, `24*L` record length, finite nonnegative cost/runtime, cumulative-cost length `24*L`, monotone cumulative cost, `gate_count = 14*L**2`, and outcome counts summing to attempted measurements. Malformed records are reported and never counted.

- [ ] **Step 5: Implement adaptive totals and runtime projection**

```python
def pilot_allocation(records, target_se=2e-4, minimum=512, batch=64, cap=25000):
    result = {}
    for L in sorted({int(record["L"]) for record in records}):
        stdevs = []
        for family in FAMILY_CODES:
            values = [float(r["record_cost"])/(L*int(r["record_steps"]))
                      for r in records if int(r["L"]) == L
                      and r["initial_family"] == family]
            if len(values) < 2:
                raise ValueError("pilot needs both family variances")
            stdevs.append(float(np.std(values, ddof=1)))
        effective = .5*np.hypot(*stdevs)
        uncapped = batch*math.ceil(max(minimum, (effective/target_se)**2)/batch)
        requested = min(int(cap), int(uncapped))
        result[L] = {"requested_per_family": requested,
                     "effective_stdev": effective,
                     "projected_se": effective/np.sqrt(requested),
                     "cap_limited": bool(uncapped > cap)}
    return result
```

`project_runtime` keeps separate mean runtimes for every `(L,family)`, counts only trajectories missing beyond the pilot, divides total CPU seconds by `workers`, and applies a `1.20` scheduling margin. It reports worker memory as `workers*12 MiB`; route is `local` only if wall time is at most `600` seconds and memory is below `16 GiB`.

- [ ] **Step 6: Implement bounded execution and progress**

`build_tasks` sorts missing `(L,family,sample_index)` by normalized completion fraction, descending `L`, then family. `run_ensemble` begins with:

```python
if config["stage"] == "production" and not approved:
    raise PermissionError("production requires --approved after projection review")
records, invalid = load_valid_records(output_dir, config)
completed = {(r["L"], r["initial_family"], r["sample_index"])
             for r in records}
tasks = build_tasks(config["sample_counts"], completed)
```

Normalize JSON string keys in `config["sample_counts"]` to integer widths before validation or task construction; all in-memory allocations use `dict[int, int]`.

Maintain at most `workers` futures. On completion, attach the sample index, validate, atomically write, and print with `flush=True`: elapsed time, total and per-width/family counts, current equal-family `tilde_f_L`, current standard error when defined, and projected remaining time. At the soft deadline stop submitting replacements, drain running futures, and write `run_checkpoint.json`.

- [ ] **Step 7: Run Task 4 tests and commit**

```powershell
python -m pytest scripts/tests/test_haar_mipt_production.py -q
git add scripts/haar_mipt_production.py scripts/tests/test_haar_mipt_production.py
git commit -m "Add resumable Haar MIPT scheduler"
```

Expected: all production tests pass before the commit.

### Task 5: CLI stages, benchmark gate, and cluster command generation

**Files:**
- Modify: `scripts/haar_mipt_production.py`
- Modify: `scripts/tests/test_haar_mipt_production.py`

**Interfaces:**
- `benchmark` writes `benchmark.json`, `pilot_config.json`, and `pilot_route.json`.
- `run --config PATH [--approved]` executes or resumes one config.
- `collect-pilot` writes `pilot_summary.json`, `production_config.json`, and `production_route.json`, then exits.
- `analyze` validates complete records and writes final analysis artifacts.
- Produces: `slurm_submit_command(config_path, walltime, workers) -> list[str]`.
- Produces: `benchmark_widths(sizes, families, p, base_seed) -> list[dict]`, one timing record per `(L,family)`.

Define the CLI-test helpers explicitly:

```python
def _fake_benchmark_widths(sizes, families, p, base_seed):
    return [{"L": L, "initial_family": family, "runtime_seconds": .01,
             "burn_in_steps": 2, "record_steps": 4}
            for L in sizes for family in families]


def _write_complete_fake_pilot(output_dir):
    module = _load_module()
    config = _config(stage="pilot", sample_counts={L: 64
                     for L in (8, 10, 12, 14, 16, 18)})
    (Path(output_dir)/"pilot_config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for L in config["sizes"]:
        for family in config["families"]:
            for index in range(64):
                density = 1.0 + (index-31.5)*1e-5
                module.write_trajectory_record_atomic(
                    _production_record(L, family, index, density), output_dir)
```

- [ ] **Step 1: Write failing CLI and gate-artifact tests**

```python
def test_benchmark_writes_fixed_pilot_config_only(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "benchmark_widths", _fake_benchmark_widths)
    assert module.main(["benchmark", "--output-dir", str(tmp_path),
                        "--workers", "4"]) == 0
    config = json.loads((tmp_path/"pilot_config.json").read_text())
    assert config["sizes"] == [8, 10, 12, 14, 16, 18]
    assert config["sample_counts"] == {str(L): 64 for L in config["sizes"]}
    assert config["p"] == .168
    assert not (tmp_path/"records").exists()


def test_collect_pilot_never_starts_production(tmp_path, monkeypatch):
    module = _load_module()
    _write_complete_fake_pilot(tmp_path)
    monkeypatch.setattr(module, "run_ensemble",
                        lambda *a, **k: pytest.fail("production auto-started"))
    assert module.main(["collect-pilot", "--output-dir", str(tmp_path)]) == 0
    config = json.loads((tmp_path/"production_config.json").read_text())
    assert config["stage"] == "production"
    assert (tmp_path/"production_route.json").is_file()
```

- [ ] **Step 2: Run CLI tests and verify RED**

```powershell
python -m pytest scripts/tests/test_haar_mipt_production.py -q
```

Expected: failures identify missing CLI subcommands and gate artifacts.

- [ ] **Step 3: Implement the bounded short benchmark**

For each width and both families, run one trajectory with `burn_in_steps=2` and `record_steps=4`. Estimate a full trajectory by multiplying runtime by `(28*L)/6`; estimate the full 64-per-family pilot with the same 20% margin. This benchmark is the only compute permitted before the pilot-route decision.

```python
pilot_config = {
    "schema_version": 1, "stage": "pilot",
    "sizes": [8, 10, 12, 14, 16, 18],
    "sample_counts": {str(L): 64 for L in (8,10,12,14,16,18)},
    "families": ["global_haar", "product"], "p": .168,
    "base_seed": 122168, "burn_in_multiplier": 4,
    "record_multiplier": 24, "workers": workers,
    "soft_deadline_seconds": soft_deadline_seconds,
}
```

- [ ] **Step 4: Implement pilot collection**

Require exactly 64 valid records in every `(L,family)` group. Run `pilot_allocation`, write requested total counts per family, and write the production route projection. Pilot indices `0..63` are retained; production schedules only `64..N_L-1`. If any group is incomplete or has nonfinite variance, exit nonzero without writing a production config.

- [ ] **Step 5: Generate a profile-neutral Slurm command**

```python
def slurm_submit_command(config_path, walltime, workers):
    command = (f"python3 -u scripts/haar_mipt_production.py run "
               f"--config {config_path}")
    if Path(config_path).name == "production_config.json":
        command += " --approved"
    return ["bash", "scripts/harness_slurm.sh", "submit", "--array", "1",
            "--run-spec", str(config_path), "--command", command,
            "--time", str(walltime), "--cpus", str(int(workers))]
```

Store this as a JSON argument list, not an unescaped shell string. Partition, memory class, account, modules, and Python path remain controlled by the active profile. Before submission, inspect the active profile and verify the remote checkout contains the implementation commit; pushing code is a separate approval.

- [ ] **Step 6: Implement analysis CLI, test, and commit**

`analyze` requires every requested record, calls `central_charge_summary(..., samples=1000, seed=base_seed+20000, alpha=.81)`, and writes all artifacts. An incomplete allocation writes a labelled checkpoint and returns nonzero.

```powershell
python -m pytest scripts/tests/test_haar_mipt_production.py scripts/tests/test_haar_mipt_analysis.py -q
git add scripts/haar_mipt_production.py scripts/tests/test_haar_mipt_production.py
git commit -m "Add Haar MIPT staged production CLI"
```

### Task 6: Full verification and performance gate

**Files:**
- Verify all files from Tasks 1--5.
- Write smoke outputs only under a test temporary directory.
- Write benchmark artifacts under `results/haar_mipt_ceff/` when execution reaches the authorized benchmark.

- [ ] **Step 1: Run all new tests**

```powershell
python -m pytest scripts/tests/test_haar_mipt_transfer.py scripts/tests/test_haar_mipt_analysis.py scripts/tests/test_haar_mipt_production.py -q
```

Expected: all new tests pass.

- [ ] **Step 2: Run existing clean-Ising and RBIM tests**

```powershell
python -m pytest scripts/tests/test_clean_ising_transfer.py scripts/tests/test_clean_ising_analysis.py scripts/tests/test_random_bond_ising_transfer.py scripts/tests/test_random_bond_ising_analysis.py scripts/tests/test_random_bond_ising_production.py -q
```

Expected: all listed tests pass.

- [ ] **Step 3: Run a tiny end-to-end smoke calculation**

In a temporary directory, run `L=4,6`, two trajectories per family, two burn-in and four record steps. Verify eight records, finite normalized costs, both family means, a reduced fit configuration supplied only to the smoke test, and all five analysis artifacts. Do not interpret reduced-width output as physics.

- [ ] **Step 4: Inspect source changes without touching unrelated symlinks**

```powershell
git diff --check -- scripts/haar_mipt_transfer.py scripts/haar_mipt_analysis.py scripts/haar_mipt_production.py scripts/tests/test_haar_mipt_transfer.py scripts/tests/test_haar_mipt_analysis.py scripts/tests/test_haar_mipt_production.py
git status --short
```

Expected: no source whitespace errors; `.agents/skills` and `.claude/skills` remain unstaged and untouched.

- [ ] **Step 5: Run the short benchmark and stop at the pilot route gate**

```powershell
python -u scripts/haar_mipt_production.py benchmark --output-dir results/haar_mipt_ceff --workers 8 --soft-deadline-seconds 600
```

Report per-width timing, projected CPU and wall time, memory, and route from `benchmark.json` and `pilot_route.json`. Do not launch the 64-trajectory pilot until the user approves the route.

### Task 7: Run and collect the pilot after compute approval

**Files:**
- Write: `results/haar_mipt_ceff/records/`
- Write: `results/haar_mipt_ceff/run_checkpoint.json`
- Write: `results/haar_mipt_ceff/pilot_summary.json`
- Write: `results/haar_mipt_ceff/production_config.json`
- Write: `results/haar_mipt_ceff/production_route.json`

- [ ] **Step 1: Launch the approved route**

Local command:

```powershell
python -u scripts/haar_mipt_production.py run --config results/haar_mipt_ceff/pilot_config.json
```

For remote execution, inspect `skills/using-slurm/profiles/active.toml`, run the harness precheck, verify the remote implementation commit, then submit the JSON argument list from `pilot_route.json`. Select a partition only after checking the active profile and current queue.

- [ ] **Step 2: Verify initial settlement**

Wait for at least one valid record from each family. Confirm parseable JSON, finite cost, exact metadata, task replacement, and a plausible remaining-time estimate. A submitted or running job is not a completed pilot.

- [ ] **Step 3: Resume to pilot completion**

On interruption, rerun the identical command; valid indices must be skipped. Continue until all `12*64 = 768` records validate or the approved deadline expires.

- [ ] **Step 4: Collect and stop at the production gate**

```powershell
python -u scripts/haar_mipt_production.py collect-pilot --output-dir results/haar_mipt_ceff
```

Report every `N_L`, cap status, projected standard error, additional trajectory count, CPU time, wall time, and route. Do not run `production_config.json` until the user approves this projection.

### Task 8: Run approved production and extract `c_eff`

**Files:**
- Complete: `results/haar_mipt_ceff/records/`
- Write: `results/haar_mipt_ceff/trajectory_summary.csv`
- Write: `results/haar_mipt_ceff/width_summary.csv`
- Write: `results/haar_mipt_ceff/fit_summary.json`
- Write: `results/haar_mipt_ceff/central_charge_fit.png`
- Write: `results/haar_mipt_ceff/record_entropy_growth.png`

- [ ] **Step 1: Launch only after production approval**

```powershell
python -u scripts/haar_mipt_production.py run --config results/haar_mipt_ceff/production_config.json --approved
```

For remote execution, repeat the profile, queue, remote-commit, guardrail, and submission checks using `production_route.json`.

- [ ] **Step 2: Monitor and preserve resumability**

Verify the first production record, then monitor often enough to see 10--50 updates. At deadline, preserve all completed records and report the missing allocation; never delete or replace pilot records.

- [ ] **Step 3: Analyze a complete allocation**

```powershell
python -u scripts/haar_mipt_production.py analyze --config results/haar_mipt_ceff/production_config.json
```

Expected: primary `c_eff`, bootstrap error, anisotropy error, fit-form shift, literature comparison, and two plots. If incomplete, retain a checkpoint and resume rather than labelling the estimate final.

- [ ] **Step 4: Verify artifacts and report**

Check all per-width/family counts equal `N_L`, cumulative entropy is linear across the record window, the finite-size coefficient has the sign required for positive `c_eff`, bootstrap samples are finite, and all artifacts parse or render. Report:

```text
c_eff = value +/- bootstrap (stat), +/- anisotropy, fit-form shift = value;
p fixed at 0.168 with literature uncertainty 0.005 not propagated;
literature target c_eff = 0.25 +/- 0.03.
```

Trajectory records remain local unless the user explicitly requests selected summaries to be committed or PR #218 to be updated.
