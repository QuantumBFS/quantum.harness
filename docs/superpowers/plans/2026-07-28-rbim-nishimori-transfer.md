# RBIM Nishimori Random Transfer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compute the leading random-transfer Lyapunov exponent for the square-lattice bimodal RBIM at `p = 0.1092212`, then fit its cylinder free energies at `L = 8, 10, 12, 16, 20` for the Nishimori-point effective central charge.

**Architecture:** A reusable matrix-free row operator applies one fixed random bond realization to a `2**L` spin-basis vector using local butterfly contractions. A streaming strip driver normalizes after every row and records block means of log norms. A separate analysis module estimates errors, performs weighted finite-size fits and block bootstrap, writes artifacts, and stops after the pilot if the measured production cost exceeds the local ten-minute budget.

**Tech Stack:** Python 3, NumPy, Matplotlib, standard-library `unittest`, CSV/JSON artifacts.

## Global Constraints

- Use the bimodal convention `Pr(J=-1)=0.1092212` and `Pr(J=+1)=1-p` on both horizontal and vertical bonds.
- Use `K_N = 0.5*log((1-p)/p)`, periodic transverse boundaries, and widths `8, 10, 12, 16, 20`.
- Do not materialize the `2**L` transfer matrix in production and do not use Gaussian-QR or multi-vector QR.
- Discard `50*L` rows, use block length `100*L`, and target free-energy-density standard error `1e-4`.
- Do not silently run locally beyond the measured approximately ten-minute budget.
- Save scripts under `scripts/` and artifacts under `results/random_bond_ising_nishimori/`.
- Flush one progress line after every completed block.

---

### Task 1: Fixed-bond matrix-free row action

**Files:**
- Create: `scripts/random_bond_ising_transfer.py`
- Create: `scripts/tests/test_random_bond_ising_transfer.py`

**Interfaces:**
- Produces: `nishimori_coupling(p: float) -> float`
- Produces: `periodic_spin_products(L: int) -> numpy.ndarray`
- Produces: `RandomBondRowTransfer(L: int, coupling: float)` with `apply(vector, horizontal_bonds, vertical_bonds) -> numpy.ndarray`
- Consumes: NumPy only.

- [ ] **Step 1: Write the failing dense-oracle and convention tests**

```python
def _dense_row_transfer(L, coupling, horizontal, vertical):
    states = np.arange(1 << L, dtype=np.uint64)
    bits = ((states[:, None] >> np.arange(L, dtype=np.uint64)) & 1).astype(float)
    spins = 2.0 * bits - 1.0
    horizontal_energy = np.sum(
        horizontal[None, :] * spins * np.roll(spins, -1, axis=1), axis=1
    )
    vertical_energy = (spins * vertical[None, :]) @ spins.T
    return np.exp(
        coupling * horizontal_energy[:, None] + coupling * vertical_energy
    )


def test_nishimori_coupling_satisfies_probability_identity(self):
    module = _load_module()
    p = 0.1092212
    coupling = module.nishimori_coupling(p)
    self.assertAlmostEqual(math.exp(-2.0 * coupling), p / (1.0 - p), places=14)


def test_matrix_free_fixed_row_matches_dense_oracle(self):
    module = _load_module()
    L = 4
    coupling = 0.73
    horizontal = np.array([1, -1, 1, -1], dtype=np.int8)
    vertical = np.array([-1, 1, 1, -1], dtype=np.int8)
    vector = np.arange(1, (1 << L) + 1, dtype=float) / 17.0
    expected = _dense_row_transfer(L, coupling, horizontal, vertical) @ vector
    actual = module.RandomBondRowTransfer(L, coupling).apply(
        vector, horizontal, vertical
    )
    np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python3 -m unittest scripts.tests.test_random_bond_ising_transfer -v`

Expected: FAIL because `scripts/random_bond_ising_transfer.py` does not exist.

- [ ] **Step 3: Implement the coupling, spin products, and butterfly action**

```python
def nishimori_coupling(p):
    p = float(p)
    if not 0.0 < p < 0.5:
        raise ValueError("p must satisfy 0 < p < 0.5")
    return 0.5 * math.log((1.0 - p) / p)


def periodic_spin_products(L):
    if L < 2:
        raise ValueError("L must be at least 2")
    states = np.arange(1 << L, dtype=np.uint64)
    products = np.empty((L, states.size), dtype=np.int8)
    for site in range(L):
        neighbor = (site + 1) % L
        different = ((states >> site) ^ (states >> neighbor)) & 1
        products[site] = 1 - 2 * different.astype(np.int8)
    return products


class RandomBondRowTransfer:
    def __init__(self, L, coupling):
        self.L = int(L)
        self.dimension = 1 << self.L
        self.coupling = float(coupling)
        self.spin_products = periodic_spin_products(self.L)

    def apply(self, vector, horizontal_bonds, vertical_bonds):
        vector = np.asarray(vector, dtype=np.float64)
        horizontal_bonds = np.asarray(horizontal_bonds, dtype=np.int8)
        vertical_bonds = np.asarray(vertical_bonds, dtype=np.int8)
        if vector.shape != (self.dimension,):
            raise ValueError("vector has the wrong dimension")
        if horizontal_bonds.shape != (self.L,) or vertical_bonds.shape != (self.L,):
            raise ValueError("bond arrays must have shape (L,)")
        if not np.all(np.isin(horizontal_bonds, (-1, 1))) or not np.all(
            np.isin(vertical_bonds, (-1, 1))
        ):
            raise ValueError("bond signs must be +/-1")

        source = vector.copy()
        target = np.empty_like(source)
        for site, sign in enumerate(vertical_bonds):
            parallel = math.exp(self.coupling * int(sign))
            antiparallel = math.exp(-self.coupling * int(sign))
            stride = 1 << site
            source_blocks = source.reshape(-1, 2, stride)
            target_blocks = target.reshape(-1, 2, stride)
            lower = source_blocks[:, 0, :]
            upper = source_blocks[:, 1, :]
            target_blocks[:, 0, :] = parallel * lower + antiparallel * upper
            target_blocks[:, 1, :] = antiparallel * lower + parallel * upper
            source, target = target, source

        horizontal_energy = horizontal_bonds @ self.spin_products
        source *= np.exp(self.coupling * horizontal_energy)
        return source
```

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `python3 -m unittest scripts.tests.test_random_bond_ising_transfer -v`

Expected: all Task 1 tests PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add scripts/random_bond_ising_transfer.py scripts/tests/test_random_bond_ising_transfer.py
git commit -m "Add matrix-free random Ising row transfer"
```

### Task 2: Streaming leading Lyapunov exponent and block statistics

**Files:**
- Modify: `scripts/random_bond_ising_transfer.py`
- Modify: `scripts/tests/test_random_bond_ising_transfer.py`

**Interfaces:**
- Consumes: `RandomBondRowTransfer.apply(...)` from Task 1.
- Produces: `sample_bond_signs(rng, L, p) -> numpy.ndarray`
- Produces: `run_random_strip(L, p, seed, burn_in, retained_rows, block_length, progress=True) -> dict`
- The result contains `block_log_norm_means`, `lyapunov`, `lyapunov_se`, `free_energy`, `free_energy_se`, `runtime_seconds`, and `rows_per_second`.

- [ ] **Step 1: Add failing reproducibility, blocking, and validation tests**

```python
def test_random_strip_is_seed_reproducible_and_blocked(self):
    module = _load_module()
    arguments = dict(
        L=3,
        p=0.1092212,
        seed=122,
        burn_in=6,
        retained_rows=24,
        block_length=8,
        progress=False,
    )
    first = module.run_random_strip(**arguments)
    second = module.run_random_strip(**arguments)
    np.testing.assert_array_equal(
        first["block_log_norm_means"], second["block_log_norm_means"]
    )
    self.assertEqual(len(first["block_log_norm_means"]), 3)
    self.assertTrue(math.isfinite(first["free_energy"]))
    self.assertGreaterEqual(first["free_energy_se"], 0.0)


def test_random_strip_rejects_incomplete_blocks(self):
    module = _load_module()
    with self.assertRaises(ValueError):
        module.run_random_strip(3, 0.1, 1, 2, 10, 6, progress=False)
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python3 -m unittest scripts.tests.test_random_bond_ising_transfer -v`

Expected: FAIL because `run_random_strip` is missing.

- [ ] **Step 3: Implement streaming disorder, scalar normalization, and blocks**

```python
def sample_bond_signs(rng, L, p):
    return np.where(rng.random(L) < p, -1, 1).astype(np.int8)


def run_random_strip(L, p, seed, burn_in, retained_rows, block_length, progress=True):
    if burn_in < 0 or retained_rows <= 0 or block_length <= 0:
        raise ValueError("row counts must be positive and burn_in nonnegative")
    if retained_rows % block_length:
        raise ValueError("retained_rows must be a multiple of block_length")
    coupling = nishimori_coupling(p)
    operator = RandomBondRowTransfer(L, coupling)
    rng = np.random.default_rng(seed)
    vector = np.ones(operator.dimension, dtype=np.float64)
    vector /= np.linalg.norm(vector)
    block_means = []
    block_sum = 0.0
    retained = 0
    started = time.perf_counter()

    for row in range(burn_in + retained_rows):
        horizontal = sample_bond_signs(rng, L, p)
        vertical = sample_bond_signs(rng, L, p)
        vector = operator.apply(vector, horizontal, vertical)
        norm = float(np.linalg.norm(vector))
        if not math.isfinite(norm) or norm <= 0.0:
            raise RuntimeError(f"invalid norm at row {row}")
        vector /= norm
        if row < burn_in:
            continue
        block_sum += math.log(norm)
        retained += 1
        if retained % block_length == 0:
            block_means.append(block_sum / block_length)
            block_sum = 0.0
            if progress:
                print(
                    f"L={L}: block={len(block_means)}, "
                    f"Lambda0={np.mean(block_means):.10f}",
                    flush=True,
                )

    runtime = time.perf_counter() - started
    blocks = np.asarray(block_means, dtype=float)
    lyapunov = float(np.mean(blocks))
    lyapunov_se = float(np.std(blocks, ddof=1) / math.sqrt(len(blocks))) if len(blocks) > 1 else math.nan
    return {
        "L": int(L), "p": float(p), "coupling": coupling, "seed": int(seed),
        "burn_in": int(burn_in), "retained_rows": int(retained_rows),
        "block_length": int(block_length), "block_log_norm_means": blocks,
        "lyapunov": lyapunov, "lyapunov_se": lyapunov_se,
        "free_energy": -lyapunov / L, "free_energy_se": lyapunov_se / L,
        "runtime_seconds": runtime,
        "rows_per_second": (burn_in + retained_rows) / runtime,
    }
```

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `python3 -m unittest scripts.tests.test_random_bond_ising_transfer -v`

Expected: all transfer and strip tests PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add scripts/random_bond_ising_transfer.py scripts/tests/test_random_bond_ising_transfer.py
git commit -m "Estimate leading random-transfer Lyapunov exponent"
```

### Task 3: Weighted central-charge fits and uncertainty propagation

**Files:**
- Create: `scripts/random_bond_ising_analysis.py`
- Create: `scripts/tests/test_random_bond_ising_analysis.py`

**Interfaces:**
- Consumes: dictionaries returned by `run_random_strip`.
- Produces: `fit_central_charge(sizes, free_energies, errors, include_l4=True, lmin=8) -> dict`
- Produces: `estimate_required_rows(strip_result, target_free_energy_se) -> dict`
- Produces: `central_charge_summary(strip_results, bootstrap_samples, seed) -> dict`

- [ ] **Step 1: Write failing synthetic-fit and runtime-projection tests**

```python
def test_weighted_fit_recovers_synthetic_central_charge(self):
    module = _load_module()
    sizes = np.array([8, 10, 12, 16, 20], dtype=float)
    expected_c = 0.464
    energies = -1.27 - math.pi * expected_c / (6.0 * sizes**2) + 0.8 / sizes**4
    errors = np.full(sizes.shape, 1e-5)
    result = module.fit_central_charge(sizes, energies, errors, include_l4=True)
    self.assertAlmostEqual(result["central_charge"], expected_c, places=10)


def test_required_rows_scales_as_inverse_error_squared(self):
    module = _load_module()
    result = {"retained_rows": 1000, "block_length": 100, "free_energy_se": 4e-4,
              "runtime_seconds": 5.0, "burn_in": 100}
    projection = module.estimate_required_rows(result, 1e-4)
    self.assertEqual(projection["required_retained_rows"], 16000)
    self.assertGreater(projection["projected_runtime_seconds"], 5.0)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python3 -m unittest scripts.tests.test_random_bond_ising_analysis -v`

Expected: FAIL because `scripts/random_bond_ising_analysis.py` does not exist.

- [ ] **Step 3: Implement weighted fits, projections, and block bootstrap**

```python
def fit_central_charge(sizes, free_energies, errors, include_l4=True, lmin=8):
    sizes = np.asarray(sizes, dtype=float)
    values = np.asarray(free_energies, dtype=float)
    errors = np.asarray(errors, dtype=float)
    if sizes.ndim != 1 or values.shape != sizes.shape or errors.shape != sizes.shape:
        raise ValueError("sizes, free_energies, and errors must have equal 1D shapes")
    if not np.all(np.isfinite(errors)) or np.any(errors <= 0.0):
        raise ValueError("errors must be finite and positive")
    mask = sizes >= lmin
    selected = sizes[mask]
    columns = [np.ones_like(selected), selected ** -2]
    if include_l4:
        columns.append(selected ** -4)
    design = np.column_stack(columns)
    weighted_design = design / errors[mask, None]
    weighted_values = values[mask] / errors[mask]
    coefficients, _, rank, _ = np.linalg.lstsq(weighted_design, weighted_values, rcond=None)
    if rank != design.shape[1]:
        raise RuntimeError("rank-deficient central-charge fit")
    covariance = np.linalg.inv(weighted_design.T @ weighted_design)
    charge = -6.0 * coefficients[1] / math.pi
    charge_se = 6.0 * math.sqrt(covariance[1, 1]) / math.pi
    return {
        "sizes": selected.astype(int).tolist(),
        "include_l4": bool(include_l4), "coefficients": coefficients.tolist(),
        "central_charge": float(charge), "central_charge_linear_se": float(charge_se),
    }


def estimate_required_rows(strip_result, target_free_energy_se):
    if not math.isfinite(target_free_energy_se) or target_free_energy_se <= 0.0:
        raise ValueError("target_free_energy_se must be finite and positive")
    ratio = strip_result["free_energy_se"] / target_free_energy_se
    raw_rows = strip_result["retained_rows"] * max(1.0, ratio * ratio)
    block = strip_result["block_length"]
    required = int(math.ceil(raw_rows / block) * block)
    measured_rows = strip_result["burn_in"] + strip_result["retained_rows"]
    projected_rows = strip_result["burn_in"] + required
    return {
        "required_retained_rows": required,
        "projected_runtime_seconds": strip_result["runtime_seconds"] * projected_rows / measured_rows,
    }


def central_charge_summary(strip_results, bootstrap_samples, seed):
    sizes = np.asarray([item["L"] for item in strip_results], dtype=float)
    values = np.asarray([item["free_energy"] for item in strip_results], dtype=float)
    errors = np.asarray([item["free_energy_se"] for item in strip_results], dtype=float)
    fits = {
        "primary_L8_l24": fit_central_charge(sizes, values, errors, True, 8),
        "all_L_l2": fit_central_charge(sizes, values, errors, False, 8),
        "drop_L8_l24": fit_central_charge(sizes, values, errors, True, 10),
    }
    rng = np.random.default_rng(seed)
    bootstrap_charges = []
    for _ in range(bootstrap_samples):
        sampled_values = []
        for item in strip_results:
            blocks = np.asarray(item["block_log_norm_means"], dtype=float)
            sampled = rng.choice(blocks, size=len(blocks), replace=True)
            sampled_values.append(-float(np.mean(sampled)) / item["L"])
        bootstrap_charges.append(
            fit_central_charge(sizes, sampled_values, errors, True, 8)["central_charge"]
        )
    deterministic = [fit["central_charge"] for fit in fits.values()]
    fits["reported"] = {
        "central_charge": fits["primary_L8_l24"]["central_charge"],
        "bootstrap_se": float(np.std(bootstrap_charges, ddof=1)),
        "fit_envelope_lower": float(min(deterministic)),
        "fit_envelope_upper": float(max(deterministic)),
        "bootstrap_samples": int(bootstrap_samples),
    }
    return fits
```

The bootstrap standard deviation and deterministic fit envelope remain
separate fields; neither is silently substituted for the other.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `python3 -m unittest scripts.tests.test_random_bond_ising_analysis -v`

Expected: all Task 3 tests PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add scripts/random_bond_ising_analysis.py scripts/tests/test_random_bond_ising_analysis.py
git commit -m "Fit Nishimori central charge from random strips"
```

### Task 4: Artifacts, progress, and pilot cost gate

**Files:**
- Modify: `scripts/random_bond_ising_analysis.py`
- Modify: `scripts/tests/test_random_bond_ising_analysis.py`

**Interfaces:**
- Produces: `write_analysis_artifacts(strip_results, summary, projections, runtime, output_dir) -> None`
- Produces: `run_workflow(sizes, p, seed, pilot_blocks, target_se, max_local_seconds, bootstrap_samples, output_dir) -> tuple`
- Produces CLI with explicit flags for every sampling and stopping parameter.

- [ ] **Step 1: Add failing artifact and small-workflow tests**

```python
def test_artifacts_include_blocks_widths_fit_projection_and_plot(self):
    module = _load_module()
    sizes = np.array([8, 10, 12, 16, 20], dtype=float)
    expected_c = 0.464
    results = []
    for L in sizes:
        free_energy = -1.27 - math.pi * expected_c / (6.0 * L**2) + 0.8 / L**4
        lyapunov = -L * free_energy
        blocks = lyapunov + np.array([-0.004, -0.002, 0.002, 0.004])
        lyapunov_se = np.std(blocks, ddof=1) / math.sqrt(len(blocks))
        results.append({
            "L": int(L), "p": 0.1092212, "coupling": 1.0, "seed": int(L),
            "burn_in": 50 * int(L), "retained_rows": 400 * int(L),
            "block_length": 100 * int(L), "block_log_norm_means": blocks,
            "lyapunov": float(np.mean(blocks)), "lyapunov_se": float(lyapunov_se),
            "free_energy": float(-np.mean(blocks) / L),
            "free_energy_se": float(lyapunov_se / L),
            "runtime_seconds": 1.0, "rows_per_second": 1000.0,
        })
    summary = module.central_charge_summary(results, bootstrap_samples=20, seed=7)
    projections = [module.estimate_required_rows(item, 1e-4) for item in results]
    runtime = {"production_launched": False, "projected_total_seconds": 1000.0,
               "target_free_energy_se": 1e-4}
    with tempfile.TemporaryDirectory() as temporary:
        module.write_analysis_artifacts(
            results, summary, projections, runtime, Path(temporary)
        )
        for name in (
            "blocks.csv", "width_summary.csv", "central_charge_fit.json",
            "runtime_projection.json", "central_charge_fit.png",
        ):
            path = Path(temporary) / name
            self.assertTrue(path.exists(), name)
            self.assertGreater(path.stat().st_size, 0)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python3 -m unittest scripts.tests.test_random_bond_ising_analysis -v`

Expected: FAIL because `write_analysis_artifacts` is missing.

- [ ] **Step 3: Implement artifact writers and pilot gate**

Write one CSV row per block with `L`, block index, and block mean; one CSV row
per width with the leading exponent, free energy, standard error, rows, seed,
and runtime; JSON documents for the fits and projections; and a plot of
`f_L` versus `1/L**2` with statistical error bars and the primary fitted curve.

Use the following orchestration shape so the cost decision is persisted and
testable independently of the command-line wrapper:

```python
def run_workflow(sizes, p, seed, pilot_blocks, target_se, max_local_seconds,
                 bootstrap_samples, output_dir):
    pilots = []
    for L in sizes:
        block_length = 100 * L
        pilots.append(run_random_strip(
            L=L, p=p, seed=seed + L, burn_in=50 * L,
            retained_rows=pilot_blocks * block_length,
            block_length=block_length, progress=True,
        ))
    projections = [estimate_required_rows(item, target_se) for item in pilots]
    projected_total = sum(item["projected_runtime_seconds"] for item in projections)
    production_launched = projected_total <= max_local_seconds
    if production_launched:
        selected = []
        for pilot, projection in zip(pilots, projections):
            L = pilot["L"]
            selected.append(run_random_strip(
                L=L, p=p, seed=seed + 10000 + L, burn_in=50 * L,
                retained_rows=projection["required_retained_rows"],
                block_length=100 * L, progress=True,
            ))
    else:
        selected = pilots
    summary = central_charge_summary(selected, bootstrap_samples, seed + 20000)
    runtime = {
        "production_launched": production_launched,
        "projected_total_seconds": projected_total,
        "target_free_energy_se": target_se,
    }
    write_analysis_artifacts(selected, summary, projections, runtime, output_dir)
    return selected, summary, runtime
```

`run_workflow` must:

1. use `burn_in=50*L` and `block_length=100*L`;
2. run `pilot_blocks` blocks for each requested width with seed `seed+L`;
3. estimate required rows and total production time from the pilot;
4. rerun all widths with the projected rows and seeds `seed+10000+L` only if
   total projected runtime is at most `max_local_seconds`;
5. otherwise analyze and save the pilot, recording `production_launched=false`;
6. call `central_charge_summary`, write artifacts, and print the achieved
   central charge and uncertainty without calling it converged when the target
   error was not reached.

Add argparse defaults:

```python
parser.add_argument("--sizes", nargs="+", type=int, default=[8, 10, 12, 16, 20])
parser.add_argument("--p", type=float, default=0.1092212)
parser.add_argument("--seed", type=int, default=1221092212)
parser.add_argument("--pilot-blocks", type=int, default=2)
parser.add_argument("--target-se", type=float, default=1e-4)
parser.add_argument("--max-local-seconds", type=float, default=600.0)
parser.add_argument("--bootstrap-samples", type=int, default=2000)
parser.add_argument("--output-dir", type=Path,
                    default=Path("results/random_bond_ising_nishimori"))
```

- [ ] **Step 4: Run both new test modules and verify GREEN**

Run: `python3 -m unittest scripts.tests.test_random_bond_ising_transfer scripts.tests.test_random_bond_ising_analysis -v`

Expected: all new tests PASS with no warnings.

- [ ] **Step 5: Commit Task 4**

```bash
git add scripts/random_bond_ising_analysis.py scripts/tests/test_random_bond_ising_analysis.py
git commit -m "Add Nishimori pilot and analysis artifacts"
```

### Task 5: Regression verification and requested production pilot

**Files:**
- Create or update: `results/random_bond_ising_nishimori/blocks.csv`
- Create or update: `results/random_bond_ising_nishimori/width_summary.csv`
- Create or update: `results/random_bond_ising_nishimori/central_charge_fit.json`
- Create or update: `results/random_bond_ising_nishimori/runtime_projection.json`
- Create or update: `results/random_bond_ising_nishimori/central_charge_fit.png`

**Interfaces:**
- Consumes the CLI from Task 4.
- Produces the requested five-width central-charge measurement or a quantified pilot precision/cost result when the direct method exceeds the local budget.

- [ ] **Step 1: Run all affected unit tests**

Run: `python3 -m unittest scripts.tests.test_clean_ising_transfer scripts.tests.test_clean_ising_analysis scripts.tests.test_random_bond_ising_transfer scripts.tests.test_random_bond_ising_analysis -v`

Expected: all tests PASS; the clean Ising `c=1/2` synthetic and operator oracles remain unchanged.

- [ ] **Step 2: Run formatting-independent syntax checks**

Run: `python3 -m py_compile scripts/random_bond_ising_transfer.py scripts/random_bond_ising_analysis.py`

Expected: exit code 0 with no output.

- [ ] **Step 3: Launch the requested cost-gated calculation**

Run:

```bash
python3 -u scripts/random_bond_ising_analysis.py \
  --sizes 8 10 12 16 20 \
  --p 0.1092212 \
  --seed 1221092212 \
  --pilot-blocks 2 \
  --target-se 1e-4 \
  --max-local-seconds 600 \
  --bootstrap-samples 2000 \
  --output-dir results/random_bond_ising_nishimori
```

Expected: progress after every block; all five widths produce finite block
statistics; either production is launched within budget or
`production_launched=false` is saved with a finite projected cost.

- [ ] **Step 4: Inspect the actual result before making a physics claim**

Run:

```bash
python3 -c "import json; p='results/random_bond_ising_nishimori/central_charge_fit.json'; d=json.load(open(p)); print(json.dumps(d, indent=2))"
```

Check that the reported central charge is finite, its statistical uncertainty
is finite, and the fit envelope is not presented as a statistical error. If
the pilot misses the target standard error, label the number preliminary and
report the projected raw-spin cost.

- [ ] **Step 5: Commit reproducible scripts and generated result artifacts**

```bash
git add scripts/random_bond_ising_transfer.py scripts/random_bond_ising_analysis.py \
  scripts/tests/test_random_bond_ising_transfer.py scripts/tests/test_random_bond_ising_analysis.py
git add -f results/random_bond_ising_nishimori
git commit -m "Measure Nishimori random-bond Ising central charge"
```

- [ ] **Step 6: Hand off the result**

Report in Chinese: the achieved `c_eff`, statistical uncertainty, finite-size
fit envelope, whether the `1e-4` width errors were reached, runtime status, the
plot path, and the exact rerun command. State explicitly that the subleading
Lyapunov spectrum remains deferred.
