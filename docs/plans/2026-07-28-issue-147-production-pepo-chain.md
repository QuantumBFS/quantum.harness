# Issue 147 Production PEPO Chain Implementation Plan

> **For agents:** Use task-by-task execution with checkpoints. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a resumable `h=3.0`, `D=4` production PEPO comparison with matched ordinary and thermodynamic chains, separate `chi=16/32` measurement, and auditable dense thermodynamics.

**Architecture:** A pickle-free checkpoint codec persists one accepted fixed-bond PEPO per `delta_beta=0.025`. A strict evolution state machine restores the newest hash-validated checkpoint, applies one complete second-order Trotter step, compresses under a fixed budget, and either atomically accepts the result or stops. A separate measurement pass contracts every checkpoint and differentiates the dense energy curve before selecting the ten public beta points.

**Tech Stack:** Python 3.11+, NumPy, SciPy, quimb, cotengra, JAX, psutil, pytest

---

## File Map

- Create `tracks/peps/solutions/avi7ii/qh147/checkpoint.py`: deterministic NPZ plus JSON checkpoint codec and resume discovery.
- Create `tracks/peps/solutions/avi7ii/qh147/evolve.py`: immutable production configuration, one-step evolution, acceptance rules, and resume loop.
- Create `tracks/peps/solutions/avi7ii/qh147/measure.py`: checkpoint contraction, local-polynomial derivative, dense/public CSV output.
- Create `tracks/peps/solutions/avi7ii/qh147/run.py`: `evolve`, `measure`, and `dry-run` CLI.
- Create `tracks/peps/solutions/avi7ii/configs/pepo-h3-d4.json`: ratified production settings.
- Create focused tests under `tracks/peps/solutions/avi7ii/tests/` matching each module.
- Modify `tracks/peps/solutions/avi7ii/README.md`: local verification and production commands.

### Task 1: Add the checkpoint codec

**Files:**
- Create: `tracks/peps/solutions/avi7ii/qh147/checkpoint.py`
- Create: `tracks/peps/solutions/avi7ii/tests/test_checkpoint.py`

- [ ] **Step 1: Write failing round-trip, corruption, and incomplete-checkpoint tests**

```python
import json

import numpy as np
import pytest

from qh147.checkpoint import latest_checkpoint, load_checkpoint, save_checkpoint
from qh147.pepo import FinitePEPO


def test_checkpoint_round_trip_preserves_dense_operator_and_metadata(tmp_path):
    pepo = FinitePEPO.identity(2, 2)
    path = tmp_path / "ordinary" / "checkpoints" / "beta-0.025000"
    save_checkpoint(path, pepo, beta=0.025, mode="ordinary", log_scale=1.5,
                    config_sha256="abc", diagnostics={"loss": 0.2})
    restored = load_checkpoint(path, expected_config_sha256="abc")
    assert np.array_equal(restored.pepo.to_dense(), pepo.to_dense())
    assert restored.beta == 0.025
    assert restored.mode == "ordinary"
    assert restored.log_scale == 1.5
    assert restored.diagnostics == {"loss": 0.2}


def test_checkpoint_rejects_tensor_corruption(tmp_path):
    path = tmp_path / "beta-0.025000"
    save_checkpoint(path, FinitePEPO.identity(1, 1), beta=0.025,
                    mode="ordinary", log_scale=0.0,
                    config_sha256="abc", diagnostics={})
    (path / "tensors.npz").write_bytes((path / "tensors.npz").read_bytes() + b"x")
    with pytest.raises(ValueError, match="tensor hash mismatch"):
        load_checkpoint(path, expected_config_sha256="abc")


def test_latest_checkpoint_ignores_directory_without_completion_marker(tmp_path):
    root = tmp_path / "checkpoints"
    complete = root / "beta-0.025000"
    save_checkpoint(complete, FinitePEPO.identity(1, 1), beta=0.025,
                    mode="ordinary", log_scale=0.0,
                    config_sha256="abc", diagnostics={})
    incomplete = root / "beta-0.050000"
    incomplete.mkdir(parents=True)
    (incomplete / "tensors.npz").write_bytes(b"partial")
    assert latest_checkpoint(root, expected_config_sha256="abc").beta == 0.025


def test_checkpoint_rejects_configuration_drift(tmp_path):
    path = tmp_path / "beta-0.025000"
    save_checkpoint(path, FinitePEPO.identity(1, 1), beta=0.025,
                    mode="ordinary", log_scale=0.0,
                    config_sha256="abc", diagnostics={})
    with pytest.raises(ValueError, match="configuration hash mismatch"):
        load_checkpoint(path, expected_config_sha256="different")
```

- [ ] **Step 2: Run the tests and verify the missing module failure**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tracks/peps/solutions/avi7ii/tests/test_checkpoint.py -q
```

Expected: collection fails because `qh147.checkpoint` does not exist.

- [ ] **Step 3: Implement deterministic pickle-free checkpoints**

Implement these public contracts in `checkpoint.py`:

```python
@dataclass(frozen=True)
class Checkpoint:
    pepo: FinitePEPO
    beta: float
    mode: str
    log_scale: float
    config_sha256: str
    diagnostics: dict[str, object]
    path: Path

```

Implement `save_checkpoint(path, pepo, *, beta, mode, log_scale,
config_sha256, diagnostics) -> Checkpoint`, `load_checkpoint(path, *,
expected_config_sha256) -> Checkpoint`, and `latest_checkpoint(root, *,
expected_config_sha256) -> Checkpoint | None` against that record.

Use lattice coordinate order to write arrays named `tensor_0000`,
`tensor_0001`, and so on. Store each tensor's exact indices and sorted tags in
`metadata.json`. Write `tensors.npz.tmp` through an open binary handle, replace
it with `tensors.npz`, compute SHA-256, then atomically replace
`metadata.json.tmp` with `metadata.json` last. Load with `allow_pickle=False`.
Rebuild `qtn.TensorNetwork` from the recorded arrays, indices, and tags.

- [ ] **Step 4: Run checkpoint tests**

Run the Step 2 command. Expected: `4 passed`.

- [ ] **Step 5: Commit the checkpoint codec**

```bash
git add tracks/peps/solutions/avi7ii/qh147/checkpoint.py tracks/peps/solutions/avi7ii/tests/test_checkpoint.py
git commit -m "feat(pepo): add atomic chain checkpoints"
```

### Task 2: Add the strict resumable evolution state machine

**Files:**
- Create: `tracks/peps/solutions/avi7ii/qh147/evolve.py`
- Create: `tracks/peps/solutions/avi7ii/tests/test_evolve.py`

- [ ] **Step 1: Write failing configuration, resume, immutability, and failure tests**

Create a deterministic fake compressor returning `CompressionResult`-compatible
records, then test these public contracts:

```python
cfg = ChainConfig(lx=2, ly=1, j=1.0, h=0.7, delta_beta=0.025,
                  beta_stop=0.075, max_bond=4, teacher_bond=16,
                  chi=16, cutoff=1e-10, max_iterations=50,
                  optimizer="L-BFGS-B", epsilon_z=1e-5,
                  epsilon_u=1e-4, contraction_noise=1e-7,
                  lambda_z=1.0, lambda_u=1.0, lambda_hermiticity=1.0,
                  hermiticity_tolerance=1e-6,
                  loss_acceptance_tolerance=1e-10)

first = run_chain(cfg, tmp_path, mode="ordinary", compressor_factory=factory,
                  stop_after_steps=2)
before = (first.latest.path / "tensors.npz").read_bytes()
second = run_chain(cfg, tmp_path, mode="ordinary", compressor_factory=factory)
assert second.accepted_betas == (0.025, 0.05, 0.075)
assert (first.latest.path / "tensors.npz").read_bytes() == before
```

Add cases proving invalid mode/configuration values fail, both modes produce the
same budget metadata, a non-finite or increasing final loss exits without a new
checkpoint, and the production compressor path retains `D<=4`.

- [ ] **Step 2: Run the focused tests and verify the missing module failure**

```powershell
.venv\Scripts\python.exe -m pytest tracks/peps/solutions/avi7ii/tests/test_evolve.py -q
```

Expected: collection fails because `qh147.evolve` does not exist.

- [ ] **Step 3: Implement immutable configuration and canonical hashing**

Implement `ChainConfig` with exactly the fields shown in Step 1. Validate
positive lattice sizes and couplings, exact integer `beta_stop/delta_beta`,
`teacher_bond>=max_bond`, positive `chi`, non-negative cutoff, positive
iteration/tolerance values, and thermodynamic tolerances above contraction
noise. Implement `config_sha256()` from `json.dumps(asdict(cfg), sort_keys=True,
separators=(",", ":"), allow_nan=False)` encoded as UTF-8.

- [ ] **Step 4: Implement the one-step and resume loop**

Expose:

```python
@dataclass(frozen=True)
class ChainResult:
    accepted_betas: tuple[float, ...]
    resumed_from: float
    latest: Checkpoint | None

```

Implement `run_chain(cfg, run_root, *, mode, compressor_factory=None,
stop_after_steps=None) -> ChainResult` against that record. The injected factory
accepts `(cfg, mode)` and returns an object exposing
`compress(teacher, max_bond, mode)`.

Production construction uses `BoundaryContractor(chi=cfg.chi,
cutoff=cfg.cutoff)`, the approved `CompressionObjective`, and
`VariationalCompressor`. Each step copies the accepted PEPO, applies every gate
from `second_order_gates` with `max_bond=cfg.teacher_bond`, compresses to
`cfg.max_bond`, renormalizes, and evaluates the partition and Hermiticity under
the same contractor. Accept only finite diagnostics, final total loss no more
than initial total plus `loss_acceptance_tolerance`, maximum bond within the
request, positive partition, and Hermiticity within tolerance. Save the
checkpoint only after every check passes. On failure atomically write
`failure.json`, print a flushed JSON failure line, and raise `RuntimeError`.

- [ ] **Step 5: Run evolution and regression tests**

```powershell
.venv\Scripts\python.exe -m pytest tracks/peps/solutions/avi7ii/tests/test_evolve.py tracks/peps/solutions/avi7ii/tests/test_compress.py tracks/peps/solutions/avi7ii/tests/test_thermo.py -q -W error
```

Expected: all focused tests pass without warnings.

- [ ] **Step 6: Commit the evolution state machine**

```bash
git add tracks/peps/solutions/avi7ii/qh147/evolve.py tracks/peps/solutions/avi7ii/tests/test_evolve.py
git commit -m "feat(pepo): add resumable beta evolution"
```

### Task 3: Add dense-grid measurement and specific heat

**Files:**
- Create: `tracks/peps/solutions/avi7ii/qh147/measure.py`
- Create: `tracks/peps/solutions/avi7ii/tests/test_measure.py`

- [ ] **Step 1: Write failing derivative and artifact tests**

```python
def test_local_polynomial_derivative_is_exact_for_cubic():
    beta = np.arange(0.025, 1.0001, 0.025)
    u = -3.0 + 2.0 * beta - beta**2 + 0.5 * beta**3
    expected = 2.0 - 2.0 * beta + 1.5 * beta**2
    assert np.allclose(local_polynomial_derivative(beta, u), expected,
                       rtol=1e-10, atol=1e-10)

def test_measurement_writes_dense_and_ten_point_public_tables(tmp_path):
    checkpoint_root = tmp_path / "ordinary" / "checkpoints"
    for beta in np.arange(0.025, 1.0001, 0.025):
        save_checkpoint(checkpoint_root / f"beta-{beta:.6f}",
                        FinitePEPO.identity(1, 1), beta=float(beta),
                        mode="ordinary", log_scale=0.0,
                        config_sha256="abc", diagnostics={})

    class FakeContractor:
        def thermodynamic_point(self, pepo, *, j, h, log_scale):
            return ThermodynamicPoint(z=1.0, u=-2.0)

        def hermiticity_residual(self, pepo):
            return 0.0

    factory = lambda chi, cutoff: FakeContractor()
    output = tmp_path / "measurements" / "ordinary" / "chi-16"
    result = measure_chain(checkpoint_root, output, expected_config_sha256="abc",
                           j=1.0, h=3.0, chi=16, cutoff=1e-10,
                           contractor_factory=factory)
    assert result.dense_count == 40
    assert result.public_count == 10
    assert len(list(csv.DictReader((output / "dense.csv").open()))) == 40
    assert [float(row["beta"]) for row in csv.DictReader(
        (output / "thermodynamics.csv").open())] == pytest.approx(
            np.arange(0.1, 1.0001, 0.1))
```

Add tests that measurement rejects a missing beta point and that `chi=16` and
`chi=32` use distinct output directories.

- [ ] **Step 2: Run tests and verify the missing module failure**

```powershell
.venv\Scripts\python.exe -m pytest tracks/peps/solutions/avi7ii/tests/test_measure.py -q
```

Expected: collection fails because `qh147.measure` does not exist.

- [ ] **Step 3: Implement stable local-polynomial differentiation**

Implement `local_polynomial_derivative(beta, values, degree=3, window=5)` by
fitting centered local coordinates with `np.polynomial.polynomial.polyfit`.
Use five points in the interior and the first/last five points at boundaries;
return coefficient one. Reject non-1D, unequal, non-finite, non-increasing, or
insufficient grids.

- [ ] **Step 4: Implement checkpoint measurement and atomic CSV artifacts**

Implement `measure_chain()` to require the complete 0.025 grid, contract each
checkpoint with `BoundaryContractor(chi=chi, cutoff=cutoff)`, convert
`ThermodynamicPoint.as_floats()`, calculate `f=-z/beta`, differentiate `u`, and
set `C=-beta**2*du_dbeta`. Write `dense.csv`, select every fourth row for
`thermodynamics.csv`, and write a hash-bearing `manifest.json` last. The output
path includes `mode` and `chi-<value>`.

- [ ] **Step 5: Run measurement and exact thermodynamic tests**

```powershell
.venv\Scripts\python.exe -m pytest tracks/peps/solutions/avi7ii/tests/test_measure.py tracks/peps/solutions/avi7ii/tests/test_exact.py tracks/peps/solutions/avi7ii/tests/test_thermo.py -q -W error
```

Expected: all tests pass without warnings.

- [ ] **Step 6: Commit measurement**

```bash
git add tracks/peps/solutions/avi7ii/qh147/measure.py tracks/peps/solutions/avi7ii/tests/test_measure.py
git commit -m "feat(pepo): measure resumable thermal chains"
```

### Task 4: Add production configuration and CLI

**Files:**
- Create: `tracks/peps/solutions/avi7ii/qh147/run.py`
- Create: `tracks/peps/solutions/avi7ii/configs/pepo-h3-d4.json`
- Create: `tracks/peps/solutions/avi7ii/tests/test_run_pepo.py`

- [ ] **Step 1: Write failing configuration and dry-run tests**

Test that loading `pepo-h3-d4.json` yields 10x10 OBC, Pauli convention, `J=1`,
`h=3`, `D=4`, teacher bond 16, `delta_beta=0.025`, beta stop 1, evolution
`chi=16`, measurement chis `[16,32]`, cutoff `1e-10`, L-BFGS-B, 50 iterations,
and the approved thermodynamic tolerances/weights. Test
`main(["dry-run", "--config", str(config), "--run-root", str(tmp_path)])`
returns zero and emits JSON with `steps=40`, `modes=["ordinary",
"thermodynamic"]`, `checkpoint_count=80`, and positive byte estimates. Test
`evolve` dispatches exactly one requested mode and `measure` requires an explicit
measurement `chi` from the configuration.

- [ ] **Step 2: Run tests and verify the missing CLI failure**

```powershell
.venv\Scripts\python.exe -m pytest tracks/peps/solutions/avi7ii/tests/test_run_pepo.py -q
```

Expected: collection fails because `qh147.run` does not exist.

- [ ] **Step 3: Add the exact JSON configuration**

The configuration contains explicit `model`, `evolution`, `compression`,
`measurement`, and `conventions` objects. Store no comments or non-finite JSON
values. `run.py` rejects unknown keys and converts the payload into `ChainConfig`.

- [ ] **Step 4: Implement `dry-run`, `evolve`, and `measure` dispatch**

Use subcommands with required `--config` and `--run-root`. `evolve` also requires
`--compression-mode ordinary|thermodynamic`; `measure` requires both
`--compression-mode` and `--chi`. `dry-run` performs no PEPO construction. The
memory estimate sums boundary and interior fixed-`D` tensor elements at eight
bytes each and reports both one-checkpoint and 80-checkpoint upper bounds.

- [ ] **Step 5: Run CLI tests and a real 2x2 dry run**

```powershell
.venv\Scripts\python.exe -m pytest tracks/peps/solutions/avi7ii/tests/test_run_pepo.py -q -W error
.venv\Scripts\python.exe -m qh147.run dry-run --config tracks/peps/solutions/avi7ii/configs/pepo-h3-d4.json --run-root tracks/peps/results/issue147-pepo
```

Expected: tests pass; the command emits one JSON object with the ratified setup,
40 steps, two modes, and storage estimates.

- [ ] **Step 6: Commit the production CLI**

```bash
git add tracks/peps/solutions/avi7ii/qh147/run.py tracks/peps/solutions/avi7ii/configs/pepo-h3-d4.json tracks/peps/solutions/avi7ii/tests/test_run_pepo.py
git commit -m "feat(pepo): add production chain CLI"
```

### Task 5: Document and verify the complete slice

**Files:**
- Modify: `tracks/peps/solutions/avi7ii/README.md`

- [ ] **Step 1: Add exact local and SCNet-ready commands**

Document the dry run, one-mode evolution, resume semantics, and independent
`chi=16/32` measurement commands. State that 10x10 evolution must first run as a
one-step SCNet timing probe and must not run locally.

- [ ] **Step 2: Run the complete package suite**

```powershell
.venv\Scripts\python.exe -m pytest tracks/peps/solutions/avi7ii/tests -q -W error
```

Expected: all existing 63 tests plus the new focused tests pass without warnings.

- [ ] **Step 3: Run the production dry run and inspect artifacts**

Run the Task 4 dry-run command. Confirm the JSON restates the exact Hamiltonian,
10x10 open boundary, Pauli convention, `h=3`, `D=4`, `chi=16`, measurement chis
16/32, 40 steps, and two modes.

- [ ] **Step 4: Commit documentation**

```bash
git add tracks/peps/solutions/avi7ii/README.md
git commit -m "docs(pepo): document production chain workflow"
```

## Post-Implementation Compute Gate

Do not submit either full 40-step chain as part of local implementation. After
all tasks pass, ship the committed branch to SCNet, run exactly one 10x10
`delta_beta=0.025` thermodynamic step, record wall time and peak memory, and
ratify the full Slurm request before submission. The queued ED job remains
independent.
