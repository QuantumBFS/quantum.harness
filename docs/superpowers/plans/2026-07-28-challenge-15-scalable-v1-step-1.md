# Challenge #15 Scalable v1 Step 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze and verify the route-independent scalable-v1 protocol, candidate contract, statistics, oracle-isolation audit, hard-gate engine, resource record, and one-command evaluator before any NQS route is implemented.

**Architecture:** A pure-Python package under `tracks/qmc/solutions/BOTS-848/scalable_v1/` owns immutable protocol data and consumes route adapters through `Protocol` interfaces. Evaluation has two phases: collect and freeze candidate evidence, then load the N=6 ED oracle only after the manifest audit passes. Synthetic adapters test the boundary without importing the Benchmark v0 ED/projector implementation.

**Tech Stack:** Python 3.13 standard library, NumPy, pytest, JSON; no new dependency.

---

## Scope and attempt boundary

This plan implements research Step 1 only. Execute it in the worktree
`D:/Playground/worktrees/quantum.harness/challenge-qmc-chiral-graviton-scalable-v1-s01-a01`
on branch `challenge/qmc-chiral-graviton-scalable-v1-s01-a01`. The attempt label
is `scalable-v1-s01-a01`, with a 90-minute active-development limit.

Before editing, create the actual journal
`tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s01-a01.md`. Record the starting
commit returned by `git rev-parse HEAD`, actual timestamps, the exact physics
contract, cost estimate, and this verified baseline:

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests -q
```

Expected before Step 1 changes: `31 passed`.

Raw output belongs under the ignored directory
`tracks/qmc/results/BOTS-848-scalable-v1-s01-a01/`. Never record a key, token,
username, host endpoint, or secret-bearing environment value.

This plan does not implement any of the three NQS routes. New package code must
not import `benchmark_v0.ed_oracle`, `benchmark_v0.fock_ed`,
`benchmark_v0.projected_nqs`, or `benchmark_v0.nqs_benchmark`.

One evaluator invocation owns one frozen training seed. Route plans must create
three manifests and three `run.json` records for seeds `848`, `1848`, and
`2848`; the Step 4 comparison computes medians across those records. A manifest
for one seed cannot be reused under another seed.

## File map

| Path | Responsibility |
|---|---|
| `tracks/qmc/solutions/BOTS-848/scalable_v1/protocol.json` | Frozen physics, training, sampling, threshold, resource, and N=8-smoke values. |
| `tracks/qmc/solutions/BOTS-848/scalable_v1/protocol.py` | Load, hash, and validate the protocol. |
| `tracks/qmc/solutions/BOTS-848/scalable_v1/contracts.py` | Sample, state, candidate, diagnostics, construction, and resource interfaces. |
| `tracks/qmc/solutions/BOTS-848/scalable_v1/resources.py` | Portable peak-RSS and wall-time capture. |
| `tracks/qmc/solutions/BOTS-848/scalable_v1/statistics.py` | Blocking estimates, ESS, propagated errors, and residuals. |
| `tracks/qmc/solutions/BOTS-848/scalable_v1/audit.py` | Manifest hashing, AST import audit, and oracle-isolation decision. |
| `tracks/qmc/solutions/BOTS-848/scalable_v1/gates.py` | Pre-reveal gates and post-freeze ED comparison. |
| `tracks/qmc/solutions/BOTS-848/scalable_v1/evaluator.py` | Evidence collection, reveal ordering, and report assembly. |
| `tracks/qmc/solutions/BOTS-848/run_scalable_evaluator.py` | Generic `module:factory` CLI. |
| `tracks/qmc/solutions/BOTS-848/tests/test_scalable_*.py` | Focused TDD tests. |
| `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/` | Step/attempt index and actual journal. |

Spec routing is explicit: this plan implements the fixed physics/protocol,
scalable and oracle guards, common adapter, statistics, gates, resources,
schema, reveal order, and attempt logging. Sparse Hamiltonian/L2 identities,
route-specific LLL constructions, particle swaps, finite rotations, and actual
N=8 smoke kernels require a concrete wavefunction and therefore belong in the
Step 2, Step 3, and Step 4 route plans. Step 1 fixes their method signatures,
probe counts, result fields, and pass thresholds so later routes cannot redefine
the benchmark.

### Task 1: Freeze and validate the common protocol

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/__init__.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/protocol.json`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/protocol.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/test_scalable_protocol.py`

- [ ] **Step 1: Write the failing protocol tests**

```python
from scalable_v1.protocol import load_protocol


def test_protocol_freezes_physics_and_budget() -> None:
    p = load_protocol()
    assert p.schema_version == "challenge-15-scalable-v1.0"
    assert p.physics["n_electrons"] == 6
    assert p.physics["two_q"] == 15
    assert p.training["seeds"] == [848, 1848, 2848]
    assert p.training["optimizer_updates"] == 2048
    assert p.training["local_energy_evaluations_per_sector"] == (
        p.training["optimizer_updates"] * p.training["batch_size_per_sector"]
    )
    assert p.sampling["samples_per_chain"] % p.sampling["block_size"] == 0
    assert p.oracle["human_blind"] is False
    assert p.sha256 == load_protocol().sha256


def test_protocol_freezes_route_capacity_and_n8_smoke() -> None:
    p = load_protocol()
    assert p.capacity["max_trainable_parameters"] == 262_144
    assert set(p.capacity["routes"]) == {
        "occupation_autoregressive", "continuous_holomorphic", "cf_flow_l2"
    }
    assert p.smoke_n8["n_electrons"] == 8
    assert p.smoke_n8["two_q"] == 21
    assert p.smoke_n8["batch_size"] == 256
```

- [ ] **Step 2: Run the test and verify RED**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_scalable_protocol.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'scalable_v1'`.

- [ ] **Step 3: Create the exact committed protocol**

```json
{
  "schema_version": "challenge-15-scalable-v1.0",
  "physics": {"geometry": "Haldane sphere", "n_electrons": 6, "two_q": 15, "filling": 0.3333333333333333, "polarization": "fully polarized fermions", "interaction": "1/(sqrt(Q) * |Omega_i-Omega_j|)", "units": "e^2/(epsilon*l_B)", "ground_l": 0, "excited_l": 2},
  "training": {"seeds": [848, 1848, 2848], "optimizer": "adam", "learning_rate": 0.001, "beta1": 0.9, "beta2": 0.999, "epsilon": 1e-08, "gradient_clip_norm": 10.0, "optimizer_updates": 2048, "batch_size_per_sector": 512, "local_energy_evaluations_per_sector": 1048576, "checkpoint_interval": 128, "checkpoint_selection": "final_update", "dtype": "complex128"},
  "sampling": {"chains": 8, "burn_in_steps": 1024, "samples_per_chain": 8192, "block_size": 256, "minimum_ess_per_state": 4096, "maximum_gap_standard_error": 0.005, "maximum_local_energy_imaginary_part": 1e-08},
  "symmetry": {"seed": 3848, "swap_probes": 64, "rotation_probes": 32, "lll_residual_max": 1e-10, "swap_residual_max": 1e-10, "so3_residual_max": 1e-06, "ladder_residual_max": 1e-08, "l2_expectation_absolute_floor": 0.001, "l2_sigma_multiplier": 5.0, "l2_variance_max": 0.001, "multiplet_absolute_floor": 0.0001, "multiplet_sigma_multiplier": 2.0},
  "oracle": {"human_blind": false, "ed_sigma_multiplier": 5.0, "numerical_floor": 1e-12, "forbidden_module_prefixes": ["benchmark_v0.ed_oracle", "benchmark_v0.fock_ed", "benchmark_v0.projected_nqs", "benchmark_v0.nqs_benchmark"], "forbidden_path_fragments": ["BOTS-848-benchmark-v0-attempt-01", "BOTS-848-benchmark-v0-attempt-02"]},
  "capacity": {"max_trainable_parameters": 262144, "routes": {"occupation_autoregressive": {"hidden_width": 128, "hidden_layers": 2}, "continuous_holomorphic": {"determinant_rank": 64, "generator_hidden_width": 64}, "cf_flow_l2": {"flow_layers": 4, "hidden_width": 64}}},
  "resources": {"local_wall_seconds": 600.0, "local_peak_rss_bytes": 17179869184, "remote_wall_seconds": 7200.0, "remote_max_cpus": 32, "remote_peak_rss_bytes": 68719476736, "max_checkpoint_bytes": 536870912, "comparison_device_policy": "same_fingerprint_or_disable_resource_tiebreak"},
  "smoke_n8": {"n_electrons": 8, "two_q": 21, "seed": 4848, "batch_size": 256, "warmup_repetitions": 2, "measured_repetitions": 5}
}
```

- [ ] **Step 4: Implement the immutable loader**

```python
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

DEFAULT_PROTOCOL_PATH = Path(__file__).with_name("protocol.json")
SECTIONS = ("physics", "training", "sampling", "symmetry", "oracle", "capacity", "resources", "smoke_n8")


@dataclass(frozen=True)
class ProtocolConfig:
    schema_version: str
    sha256: str
    _data: Mapping[str, Any]

    def section(self, name: str) -> Mapping[str, Any]:
        return MappingProxyType(copy.deepcopy(self._data[name]))

    @property
    def physics(self): return self.section("physics")
    @property
    def training(self): return self.section("training")
    @property
    def sampling(self): return self.section("sampling")
    @property
    def symmetry(self): return self.section("symmetry")
    @property
    def oracle(self): return self.section("oracle")
    @property
    def capacity(self): return self.section("capacity")
    @property
    def resources(self): return self.section("resources")
    @property
    def smoke_n8(self): return self.section("smoke_n8")


def _validate(data: dict[str, Any]) -> None:
    missing = [name for name in SECTIONS if name not in data]
    if data.get("schema_version") != "challenge-15-scalable-v1.0" or missing:
        raise ValueError(f"invalid scalable-v1 protocol; missing={missing}")
    physics, training, sampling = data["physics"], data["training"], data["sampling"]
    if physics["two_q"] != 3 * (physics["n_electrons"] - 1):
        raise ValueError("two_q must equal 3*(N-1)")
    if training["local_energy_evaluations_per_sector"] != training["optimizer_updates"] * training["batch_size_per_sector"]:
        raise ValueError("inconsistent local-energy budget")
    if len(training["seeds"]) != 3 or len(set(training["seeds"])) != 3:
        raise ValueError("three unique comparison seeds are required")
    if sampling["samples_per_chain"] % sampling["block_size"]:
        raise ValueError("block_size must divide samples_per_chain")
    if data["oracle"]["human_blind"] is not False:
        raise ValueError("human_blind must remain false")
    smoke = data["smoke_n8"]
    if smoke["two_q"] != 3 * (smoke["n_electrons"] - 1):
        raise ValueError("invalid N=8 smoke flux")


def load_protocol(path: str | Path = DEFAULT_PROTOCOL_PATH) -> ProtocolConfig:
    payload = Path(path).read_bytes()
    data = json.loads(payload.decode("utf-8"))
    _validate(data)
    return ProtocolConfig(data["schema_version"], hashlib.sha256(payload).hexdigest(), MappingProxyType(data))
```

Export `ProtocolConfig` and `load_protocol` from `scalable_v1/__init__.py`.

- [ ] **Step 5: Run GREEN and commit**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_scalable_protocol.py -q
git add tracks/qmc/solutions/BOTS-848/scalable_v1 tracks/qmc/solutions/BOTS-848/tests/test_scalable_protocol.py
git commit -m "feat(qmc): freeze scalable v1 protocol"
```

Expected: two tests pass and no route implementation is present.

### Task 2: Define candidate contracts and portable resource records

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/contracts.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/resources.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/test_scalable_contracts.py`

- [ ] **Step 1: Write failing shape and record tests**

```python
import numpy as np
import pytest

from scalable_v1.contracts import ConstructionCertificate, ResourceMetrics, SampleBatch


def test_sample_batch_rejects_wrong_count() -> None:
    with pytest.raises(ValueError, match="n_samples"):
        SampleBatch(np.zeros((3, 4)), n_samples=4, burn_in_steps=1024, seed=848)


def test_resource_record_computes_ess_rate() -> None:
    certificate = ConstructionCertificate(
        strict_lll=True,
        antisymmetric=True,
        scalable=True,
        trainable_parameters=100,
        statement="fixed LLL configuration space; no full-basis allocation",
    )
    metrics = ResourceMetrics(
        placement="local", wall_seconds=2.0, peak_rss_bytes=1024,
        peak_vram_bytes=None, checkpoint_bytes=512,
        estimator_evaluations=100, effective_sample_size=50.0,
        n8_smoke_complete=True, n8_to_n6_time_ratio=1.5,
        n8_to_n6_memory_ratio=1.2, device_fingerprint="cpu:test",
    )
    assert certificate.strict_lll
    assert metrics.ess_per_second == 25.0
```

- [ ] **Step 2: Run the test and verify RED**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_scalable_contracts.py -q
```

Expected: import fails because `contracts.py` is absent.

- [ ] **Step 3: Implement the approved adapter boundary**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, runtime_checkable

import numpy as np


@dataclass(frozen=True)
class SampleBatch:
    configs: Any
    n_samples: int
    burn_in_steps: int
    seed: int

    def __post_init__(self) -> None:
        if len(self.configs) != self.n_samples:
            raise ValueError("n_samples does not match configuration batch")


@dataclass(frozen=True)
class ConstructionCertificate:
    strict_lll: bool
    antisymmetric: bool
    scalable: bool
    trainable_parameters: int
    statement: str

    def __post_init__(self) -> None:
        if self.trainable_parameters <= 0:
            raise ValueError("trainable_parameters must be positive")


@dataclass(frozen=True)
class ResourceMetrics:
    placement: str
    wall_seconds: float
    peak_rss_bytes: int
    peak_vram_bytes: int | None
    checkpoint_bytes: int
    estimator_evaluations: int
    effective_sample_size: float
    n8_smoke_complete: bool
    n8_to_n6_time_ratio: float
    n8_to_n6_memory_ratio: float
    device_fingerprint: str

    def __post_init__(self) -> None:
        if self.placement not in {"local", "remote"}:
            raise ValueError("placement must be local or remote")
        if self.wall_seconds <= 0.0:
            raise ValueError("wall_seconds must be positive")
        if self.n8_smoke_complete and (
            self.n8_to_n6_time_ratio <= 0.0 or self.n8_to_n6_memory_ratio <= 0.0
        ):
            raise ValueError("completed N=8 smoke ratios must be positive")

    @property
    def ess_per_second(self) -> float:
        return self.effective_sample_size / self.wall_seconds


@runtime_checkable
class StateHandle(Protocol):
    label: str
    l: int
    m: int

    def sample(self, n_samples: int, seed: int) -> SampleBatch: ...
    def logpsi(self, config_batch: Any) -> np.ndarray: ...
    def local_energy(self, config_batch: Any) -> np.ndarray: ...
    def local_l2(self, config_batch: Any) -> np.ndarray: ...


@runtime_checkable
class CandidateAdapter(Protocol):
    name: str
    family: str

    def ground_state(self) -> StateHandle: ...
    def generate_multiplet(self) -> Mapping[int, StateHandle]: ...
    def construction_certificate(self) -> ConstructionCertificate: ...
    def resource_metrics(self) -> ResourceMetrics: ...


@runtime_checkable
class DiagnosticProvider(Protocol):
    def evaluate(
        self,
        candidate: CandidateAdapter,
        *,
        seed: int,
        swap_probes: int,
        rotation_probes: int,
    ) -> Mapping[str, float]: ...
```

The state handles own the approved `sample`, `logpsi`, `local_energy`, and
`local_l2` methods. The candidate bundle owns `generate_multiplet` and
`resource_metrics`. A valid bundle returns exactly `M=-2,-1,0,1,2`.
Route implementations make `resource_metrics()` run the frozen N=8 smoke batch
before setting `n8_smoke_complete=True`; Step 1 tests only this common record
and does not manufacture an N-dependent model.

- [ ] **Step 4: Implement portable process metering**

```python
from __future__ import annotations

import ctypes
import os
import sys
import time
from dataclasses import dataclass, field


def peak_rss_bytes() -> int:
    if os.name == "nt":
        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        process = ctypes.windll.kernel32.GetCurrentProcess()
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb)
        if not ok:
            raise OSError("GetProcessMemoryInfo failed")
        return int(counters.PeakWorkingSetSize)
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


@dataclass
class RuntimeMeter:
    started: float = field(init=False, default=0.0)
    wall_seconds: float = field(init=False, default=0.0)
    peak_rss_bytes: int = field(init=False, default=0)

    def __enter__(self) -> "RuntimeMeter":
        self.started = time.perf_counter()
        return self

    def __exit__(self, *args: object) -> None:
        self.wall_seconds = time.perf_counter() - self.started
        self.peak_rss_bytes = peak_rss_bytes()
```

Add this exact process-meter test:

```python
from scalable_v1.resources import RuntimeMeter


def test_runtime_meter_reports_positive_process_usage() -> None:
    with RuntimeMeter() as meter:
        payload = np.ones(1024, dtype=float)
        assert payload.sum() == 1024.0
    assert meter.wall_seconds > 0.0
    assert meter.peak_rss_bytes > 0
```

- [ ] **Step 5: Run GREEN and commit**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_scalable_contracts.py -q
git add tracks/qmc/solutions/BOTS-848/scalable_v1/contracts.py tracks/qmc/solutions/BOTS-848/scalable_v1/resources.py tracks/qmc/solutions/BOTS-848/tests/test_scalable_contracts.py
git commit -m "feat(qmc): define scalable candidate contract"
```

Expected: contract and resource tests pass.

### Task 3: Implement blocking statistics and residual math

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/statistics.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/test_scalable_statistics.py`

- [ ] **Step 1: Write failing numerical tests**

```python
import math
import numpy as np
import pytest

from scalable_v1.statistics import blocking_estimate, combine_independent, normalized_residual


def test_blocking_estimate_uses_block_means() -> None:
    values = np.arange(16, dtype=float).reshape(2, 8)
    result = blocking_estimate(values, block_size=2)
    blocks = values.reshape(2, 4, 2).mean(axis=2).ravel()
    assert result.mean == np.mean(values)
    assert result.standard_error == np.std(blocks, ddof=1) / math.sqrt(8)
    assert 0.0 < result.effective_sample_size <= 16.0


def test_complex_input_tracks_imaginary_drift() -> None:
    result = blocking_estimate(np.ones((2, 8), dtype=complex) + 2e-9j, block_size=2)
    assert result.mean == 1.0
    assert result.maximum_imaginary_part == 2e-9


def test_error_propagation_and_residual() -> None:
    assert combine_independent(3.0, 0.3, 2.0, 0.4) == (1.0, 0.5)
    assert normalized_residual(np.array([1, 2]), np.array([1, 2])) == 0.0


def test_blocking_estimate_rejects_nonfinite_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        blocking_estimate(np.array([[1.0, np.nan]]), block_size=1)
```

- [ ] **Step 2: Run the test and verify RED**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_scalable_statistics.py -q
```

Expected: import fails because `statistics.py` is absent.

- [ ] **Step 3: Implement the complete helpers**

```python
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class ScalarEstimate:
    mean: float
    variance: float
    standard_error: float
    effective_sample_size: float
    maximum_imaginary_part: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def blocking_estimate(values: np.ndarray, *, block_size: int) -> ScalarEstimate:
    array = np.asarray(values)
    if array.ndim != 2 or array.shape[1] % block_size:
        raise ValueError("values must be [chains, samples] with divisible blocks")
    if not np.all(np.isfinite(array)):
        raise ValueError("estimator values must be finite")
    maximum_imaginary = float(np.max(np.abs(np.imag(array))))
    real = np.real(array).astype(float, copy=False)
    chains, samples = real.shape
    blocks = real.reshape(chains, samples // block_size, block_size).mean(axis=2).ravel()
    mean = float(np.mean(real))
    variance = float(np.var(real, ddof=1)) if real.size > 1 else 0.0
    standard_error = float(np.std(blocks, ddof=1) / math.sqrt(blocks.size)) if blocks.size > 1 else 0.0
    ess = float(real.size) if variance == 0.0 or standard_error == 0.0 else min(float(real.size), variance / standard_error**2)
    return ScalarEstimate(mean, variance, standard_error, ess, maximum_imaginary)


def combine_independent(left_mean: float, left_error: float, right_mean: float, right_error: float) -> tuple[float, float]:
    return left_mean - right_mean, math.hypot(left_error, right_error)


def normalized_residual(actual: np.ndarray, expected: np.ndarray) -> float:
    actual = np.asarray(actual, dtype=complex)
    expected = np.asarray(expected, dtype=complex)
    denominator = max(float(np.linalg.norm(expected)), np.finfo(float).eps)
    return float(np.linalg.norm(actual - expected) / denominator)
```

- [ ] **Step 4: Run GREEN and commit**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_scalable_statistics.py -q
git add tracks/qmc/solutions/BOTS-848/scalable_v1/statistics.py tracks/qmc/solutions/BOTS-848/tests/test_scalable_statistics.py
git commit -m "feat(qmc): add scalable blocking statistics"
```

Expected: all four statistics tests pass.

### Task 4: Freeze checkpoints and enforce oracle isolation

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/audit.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/test_scalable_audit.py`

- [ ] **Step 1: Write failing clean, forbidden-import, and tamper tests**

```python
import json
from pathlib import Path

from scalable_v1.audit import freeze_manifest, verify_manifest
from scalable_v1.protocol import DEFAULT_PROTOCOL_PATH, load_protocol


def make_files(tmp_path: Path, source_text: str):
    project, run = tmp_path / "project", tmp_path / "run"
    project.mkdir(); run.mkdir()
    source = project / "candidate.py"
    artifacts = {
        "checkpoint": run / "checkpoint.bin",
        "optimizer_state": run / "optimizer.bin",
        "training_log": run / "training.log",
    }
    source.write_text(source_text, encoding="utf-8")
    for role, path in artifacts.items():
        path.write_bytes(role.encode("utf-8"))
    return project, run, source, artifacts


def test_clean_manifest_passes(tmp_path: Path) -> None:
    project, run, source, artifacts = make_files(tmp_path, "VALUE = 1\n")
    protocol = load_protocol()
    manifest = freeze_manifest(
        run_dir=run, project_root=project, route="occupation_autoregressive",
        attempt="scalable-v1-s01-a01", protocol=protocol, selected_update=2048,
        training_seed=848,
        source_files=[source], artifact_files=artifacts,
    )
    assert verify_manifest(manifest, project_root=project, protocol=protocol).valid


def test_forbidden_import_and_tamper_fail(tmp_path: Path) -> None:
    project, run, source, artifacts = make_files(
        tmp_path, "from benchmark_v0.fock_ed import fixed_m_basis\n"
    )
    protocol = load_protocol()
    manifest = freeze_manifest(
        run_dir=run, project_root=project, route="occupation_autoregressive",
        attempt="scalable-v1-s01-a01", protocol=protocol, selected_update=2048,
        training_seed=848,
        source_files=[source], artifact_files=artifacts,
    )
    first = verify_manifest(manifest, project_root=project, protocol=protocol)
    artifacts["checkpoint"].write_bytes(b"changed")
    second = verify_manifest(manifest, project_root=project, protocol=protocol)
    assert not first.valid
    assert any("benchmark_v0.fock_ed" in issue for issue in first.issues)
    assert not second.valid
    assert any("artifact hash" in issue for issue in second.issues)
```

- [ ] **Step 2: Run the test and verify RED**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_scalable_audit.py -q
```

Expected: import fails because `audit.py` is absent.

- [ ] **Step 3: Implement manifest hashing and AST import inspection**

```python
from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .protocol import ProtocolConfig


@dataclass(frozen=True)
class AuditResult:
    valid: bool
    issues: tuple[str, ...]
    manifest_sha256: str
    artifact_bytes: int = 0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def imported_modules(source: str) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            found.add(module)
            found.update(f"{module}.{alias.name}" for alias in node.names)
    return found


def freeze_manifest(*, run_dir: Path, project_root: Path, route: str, attempt: str,
                    protocol: ProtocolConfig, selected_update: int,
                    training_seed: int,
                    source_files: list[Path], artifact_files: dict[str, Path]) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    required_artifacts = {"checkpoint", "optimizer_state", "training_log"}
    if set(artifact_files) != required_artifacts:
        raise ValueError(f"artifact roles must be {sorted(required_artifacts)}")
    payload = {
        "schema_version": "challenge-15-frozen-manifest-v1",
        "route": route, "attempt": attempt, "protocol_sha256": protocol.sha256,
        "training_seed": training_seed,
        "selected_capacity": dict(protocol.capacity["routes"][route]),
        "selected_update": selected_update, "checkpoint_policy": "final_update",
        "human_blind": False, "oracle_accesses": [],
        "source_files": [{"path": str(p.resolve().relative_to(project_root.resolve())), "sha256": sha256_file(p)} for p in source_files],
        "artifacts": {
            role: {"path": str(path.resolve().relative_to(run_dir.resolve())), "sha256": sha256_file(path)}
            for role, path in artifact_files.items()
        },
    }
    output = run_dir / "training-manifest.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def verify_manifest(manifest_path: Path, *, project_root: Path, protocol: ProtocolConfig,
                    expected_training_seed: int | None = None) -> AuditResult:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    issues: list[str] = []
    if payload.get("protocol_sha256") != protocol.sha256:
        issues.append("protocol hash mismatch")
    route = payload.get("route")
    if route not in protocol.capacity["routes"]:
        issues.append("route is outside the frozen comparison set")
    elif payload.get("selected_capacity") != protocol.capacity["routes"][route]:
        issues.append("selected capacity does not match the frozen route mapping")
    if payload.get("selected_update") != protocol.training["optimizer_updates"]:
        issues.append("selected checkpoint is not the frozen final update")
    if payload.get("training_seed") not in protocol.training["seeds"]:
        issues.append("training seed is outside the frozen comparison set")
    if expected_training_seed is not None and payload.get("training_seed") != expected_training_seed:
        issues.append("manifest training seed does not match requested run")
    if payload.get("checkpoint_policy") != "final_update":
        issues.append("checkpoint policy is not final_update")
    if payload.get("human_blind") is not False or payload.get("oracle_accesses") != []:
        issues.append("oracle isolation disclosure is invalid")
    if not payload.get("source_files") or set(payload.get("artifacts", {})) != {"checkpoint", "optimizer_state", "training_log"}:
        issues.append("manifest must hash source files and frozen artifacts")
    forbidden = tuple(protocol.oracle["forbidden_module_prefixes"])
    fragments = tuple(protocol.oracle["forbidden_path_fragments"])
    root = project_root.resolve()
    for item in payload.get("source_files", []):
        path = (root / item["path"]).resolve()
        if root not in path.parents or not path.is_file() or sha256_file(path) != item["sha256"]:
            issues.append(f"source hash mismatch or path escape: {path}")
            continue
        text = path.read_text(encoding="utf-8")
        for module in imported_modules(text):
            if any(module == prefix or module.startswith(prefix + ".") for prefix in forbidden):
                issues.append(f"forbidden candidate import: {module}")
        for prefix in forbidden:
            if prefix in text and not any(prefix in issue for issue in issues):
                issues.append(f"forbidden candidate module reference: {prefix}")
        for fragment in fragments:
            if fragment in text:
                issues.append(f"forbidden oracle path fragment: {fragment}")
    run_root = manifest_path.parent.resolve()
    artifact_bytes = 0
    for role, item in payload.get("artifacts", {}).items():
        path = (run_root / item["path"]).resolve()
        if run_root not in path.parents or not path.is_file() or sha256_file(path) != item["sha256"]:
            issues.append(f"artifact hash mismatch or path escape ({role}): {path}")
        else:
            artifact_bytes += path.stat().st_size
    return AuditResult(not issues, tuple(issues), sha256_file(manifest_path), artifact_bytes)
```

- [ ] **Step 4: Add a protocol-hash mismatch test and run GREEN**

Copy `protocol.json` to a temporary path, change `optimizer_updates` and
`local_energy_evaluations_per_sector` consistently, load it, and assert that the
old manifest fails with `protocol hash mismatch`.

```python
def test_manifest_rejects_a_different_valid_protocol(tmp_path: Path) -> None:
    project, run, source, artifacts = make_files(tmp_path, "VALUE = 1\n")
    original = load_protocol()
    manifest = freeze_manifest(
        run_dir=run, project_root=project, route="occupation_autoregressive",
        attempt="scalable-v1-s01-a01", protocol=original, selected_update=2048,
        training_seed=848,
        source_files=[source], artifact_files=artifacts,
    )
    data = json.loads(DEFAULT_PROTOCOL_PATH.read_text(encoding="utf-8"))
    data["training"]["optimizer_updates"] = 1024
    data["training"]["local_energy_evaluations_per_sector"] = 524288
    changed_path = tmp_path / "changed-protocol.json"
    changed_path.write_text(json.dumps(data), encoding="utf-8")
    changed = load_protocol(changed_path)
    result = verify_manifest(manifest, project_root=project, protocol=changed)
    assert not result.valid
    assert "protocol hash mismatch" in result.issues
```

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_scalable_audit.py -q
git add tracks/qmc/solutions/BOTS-848/scalable_v1/audit.py tracks/qmc/solutions/BOTS-848/tests/test_scalable_audit.py
git commit -m "feat(qmc): audit oracle-isolated checkpoints"
```

Expected: clean source passes; forbidden import, tamper, and protocol mismatch each fail with a named issue.

### Task 5: Implement hard gates and the post-freeze ED reveal

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/gates.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/test_scalable_gates.py`

- [ ] **Step 1: Write failing gate tests with synthetic non-oracle numbers**

```python
from scalable_v1.audit import AuditResult
from scalable_v1.gates import apply_ed_reveal, evaluate_pre_reveal
from scalable_v1.protocol import load_protocol


def estimate(mean: float, variance: float = 0.0, error: float = 1e-4):
    return {
        "mean": mean, "variance": variance, "standard_error": error,
        "effective_sample_size": 8192.0, "maximum_imaginary_part": 0.0,
    }


def passing_evidence():
    return {
        "construction": {"strict_lll": True, "antisymmetric": True, "scalable": True, "trainable_parameters": 100},
        "statistics": {
            "ground": {"energy": estimate(1.0), "l2": estimate(0.0)},
            "l2_by_m": {str(m): {"energy": estimate(1.1), "l2": estimate(6.0)} for m in range(-2, 3)},
            "gap": {"mean": 0.1, "standard_error": 2e-4},
        },
        "diagnostics": {
            "lll_residual": 0.0, "particle_swap_residual": 0.0,
            "finite_rotation_residual": 1e-8, "tower_ladder_residual": 1e-10,
        },
        "resources": {
            "placement": "local", "wall_seconds": 2.0, "peak_rss_bytes": 1024,
            "checkpoint_bytes": 512, "n8_smoke_complete": True,
        },
    }


def test_pre_reveal_passes_non_ed_gates_and_leaves_ed_pending() -> None:
    pre = evaluate_pre_reveal(passing_evidence(), load_protocol(), AuditResult(True, (), "manifest"))
    assert pre["gates"]["ed_crosscheck_valid"] == "pending"
    assert all(value is True for name, value in pre["gates"].items() if name != "ed_crosscheck_valid")


def test_reveal_adds_ed_errors_without_mutating_pre_reveal() -> None:
    protocol = load_protocol()
    pre = evaluate_pre_reveal(passing_evidence(), protocol, AuditResult(True, (), "manifest"))
    final = apply_ed_reveal(
        pre,
        {"ground_energy": 1.0, "l2_by_m": {str(m): 1.1 for m in range(-2, 3)}},
        protocol,
    )
    assert pre["gates"]["ed_crosscheck_valid"] == "pending"
    assert final["gates"]["ed_crosscheck_valid"] is True
    assert final["gates"]["scalable_v1_pass"] is True
    assert final["ed_comparison"]["gap_absolute_error"] < 1e-12
```

- [ ] **Step 2: Run the test and verify RED**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_scalable_gates.py -q
```

Expected: import fails because `gates.py` is absent.

- [ ] **Step 3: Implement pre-reveal gates**

```python
from __future__ import annotations

import copy
import math
from typing import Any, Mapping

from .audit import AuditResult
from .protocol import ProtocolConfig


def within(mean: float, target: float, error: float, floor: float, sigma: float) -> bool:
    return abs(mean - target) <= max(floor, sigma * error)


def evaluate_pre_reveal(evidence: Mapping[str, Any], protocol: ProtocolConfig, audit: AuditResult) -> dict[str, Any]:
    result = copy.deepcopy(dict(evidence))
    construction = result["construction"]
    stats = result["statistics"]
    diagnostics = result["diagnostics"]
    threshold = protocol.symmetry
    sampling = protocol.sampling
    resources = result["resources"]
    components = stats["l2_by_m"]
    if set(components) != {"-2", "-1", "0", "1", "2"}:
        raise ValueError("complete L=2 multiplet is required")

    all_states = [stats["ground"], *components.values()]
    mc_valid = (
        all(state[key]["effective_sample_size"] >= sampling["minimum_ess_per_state"]
            for state in all_states for key in ("energy", "l2"))
        and all(state["energy"]["maximum_imaginary_part"] <= sampling["maximum_local_energy_imaginary_part"]
                for state in all_states)
        and stats["gap"]["standard_error"] <= sampling["maximum_gap_standard_error"]
    )
    ground_l2 = stats["ground"]["l2"]
    l2_valid = (
        within(ground_l2["mean"], 0.0, ground_l2["standard_error"],
               threshold["l2_expectation_absolute_floor"], threshold["l2_sigma_multiplier"])
        and ground_l2["variance"] <= threshold["l2_variance_max"]
    )
    l2_valid = l2_valid and all(
        within(state["l2"]["mean"], 6.0, state["l2"]["standard_error"],
               threshold["l2_expectation_absolute_floor"], threshold["l2_sigma_multiplier"])
        and state["l2"]["variance"] <= threshold["l2_variance_max"]
        for state in components.values()
    )
    energies = [state["energy"] for state in components.values()]
    highest = max(energies, key=lambda value: value["mean"])
    lowest = min(energies, key=lambda value: value["mean"])
    splitting = highest["mean"] - lowest["mean"]
    splitting_limit = max(
        threshold["multiplet_absolute_floor"],
        threshold["multiplet_sigma_multiplier"] * math.hypot(
            highest["standard_error"], lowest["standard_error"]
        ),
    )
    limits = protocol.resources
    wall_limit = limits["local_wall_seconds"] if resources["placement"] == "local" else limits["remote_wall_seconds"]
    rss_limit = limits["local_peak_rss_bytes"] if resources["placement"] == "local" else limits["remote_peak_rss_bytes"]
    resource_valid = (
        resources["wall_seconds"] <= wall_limit
        and resources["peak_rss_bytes"] <= rss_limit
        and resources["checkpoint_bytes"] <= limits["max_checkpoint_bytes"]
    )
    gates: dict[str, bool | str] = {
        "lll_valid": bool(construction["strict_lll"] and diagnostics["lll_residual"] <= threshold["lll_residual_max"]),
        "antisymmetry_valid": bool(construction["antisymmetric"] and diagnostics["particle_swap_residual"] <= threshold["swap_residual_max"]),
        "so3_equivariance_valid": bool(diagnostics["finite_rotation_residual"] <= threshold["so3_residual_max"] and diagnostics["tower_ladder_residual"] <= threshold["ladder_residual_max"]),
        "l2_casimir_valid": bool(l2_valid),
        "fivefold_multiplet_valid": bool(splitting <= splitting_limit),
        "mc_error_valid": bool(mc_valid),
        "ed_crosscheck_valid": "pending",
        "reproducible_run_valid": bool(audit.valid),
        "scalable_path_valid": bool(
            construction["scalable"]
            and construction["trainable_parameters"] <= protocol.capacity["max_trainable_parameters"]
            and resources["n8_smoke_complete"]
        ),
        "oracle_isolated": bool(audit.valid),
        "blind_training_valid": bool(audit.valid and protocol.oracle["human_blind"] is False),
        "resource_budget_valid": bool(resource_valid),
    }
    result["gates"] = gates
    result["diagnostics"]["multiplet_splitting"] = splitting
    result["audit"] = {
        "valid": audit.valid, "issues": list(audit.issues),
        "manifest_sha256": audit.manifest_sha256,
    }
    return result
```

- [ ] **Step 4: Implement the immutable ED reveal**

```python
def apply_ed_reveal(pre_reveal: Mapping[str, Any], oracle: Mapping[str, float],
                    protocol: ProtocolConfig) -> dict[str, Any]:
    if pre_reveal["gates"]["oracle_isolated"] is not True:
        raise ValueError("ED oracle cannot be loaded before oracle isolation passes")
    result = copy.deepcopy(dict(pre_reveal))
    ground = result["statistics"]["ground"]["energy"]
    gap = result["statistics"]["gap"]
    oracle_components = oracle["l2_by_m"]
    if set(oracle_components) != {"-2", "-1", "0", "1", "2"}:
        raise ValueError("ED oracle must contain all five L=2 components")
    ed_combined = sum(oracle_components.values()) / 5.0
    ed_gap = ed_combined - oracle["ground_energy"]
    ground_error = abs(ground["mean"] - oracle["ground_energy"])
    gap_error = abs(gap["mean"] - ed_gap)
    sigma = protocol.oracle["ed_sigma_multiplier"]
    floor = protocol.oracle["numerical_floor"]
    excited_errors = {
        magnetic_number: abs(
            result["statistics"]["l2_by_m"][magnetic_number]["energy"]["mean"]
            - oracle_components[magnetic_number]
        )
        for magnetic_number in oracle_components
    }
    ed_valid = (
        ground_error <= max(floor, sigma * ground["standard_error"])
        and gap_error <= max(floor, sigma * gap["standard_error"])
        and all(
            excited_errors[m] <= max(
                floor,
                sigma * result["statistics"]["l2_by_m"][m]["energy"]["standard_error"],
            )
            for m in excited_errors
        )
    )
    result["ed_comparison"] = {
        "ground_absolute_error": ground_error,
        "excited_absolute_error_by_m": excited_errors,
        "gap_absolute_error": gap_error,
        "gap_z_score": gap_error / max(gap["standard_error"], floor),
    }
    result["gates"]["ed_crosscheck_valid"] = bool(ed_valid)
    result["gates"]["scalable_v1_pass"] = all(value is True for value in result["gates"].values())
    return result
```

- [ ] **Step 5: Add exact failure-isolation cases**

In the test file, use `copy.deepcopy(passing_evidence())` to make five cases:
`strict_lll=False` must fail `lll_valid`; L2 variance `0.01` must fail
`l2_casimir_valid`; ESS `100` must fail `mc_error_valid`; deleting key `"2"`
must raise `ValueError`; local wall `601.0` must fail
`resource_budget_valid`. Assert the named gate in each case.

```python
import copy
import pytest


@pytest.mark.parametrize(
    ("mutation", "gate"),
    [
        (lambda value: value["construction"].__setitem__("strict_lll", False), "lll_valid"),
        (lambda value: value["statistics"]["l2_by_m"]["0"]["l2"].__setitem__("variance", 0.01), "l2_casimir_valid"),
        (lambda value: value["statistics"]["ground"]["energy"].__setitem__("effective_sample_size", 100.0), "mc_error_valid"),
        (lambda value: value["resources"].__setitem__("wall_seconds", 601.0), "resource_budget_valid"),
        (lambda value: value["construction"].__setitem__("trainable_parameters", 262145), "scalable_path_valid"),
    ],
)
def test_pre_reveal_isolates_named_gate_failures(mutation, gate) -> None:
    evidence = copy.deepcopy(passing_evidence())
    mutation(evidence)
    result = evaluate_pre_reveal(evidence, load_protocol(), AuditResult(True, (), "manifest"))
    assert result["gates"][gate] is False


def test_pre_reveal_rejects_incomplete_multiplet() -> None:
    evidence = copy.deepcopy(passing_evidence())
    del evidence["statistics"]["l2_by_m"]["2"]
    with pytest.raises(ValueError, match="complete L=2 multiplet"):
        evaluate_pre_reveal(evidence, load_protocol(), AuditResult(True, (), "manifest"))
```

- [ ] **Step 6: Run GREEN and commit**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_scalable_gates.py -q
git add tracks/qmc/solutions/BOTS-848/scalable_v1/gates.py tracks/qmc/solutions/BOTS-848/tests/test_scalable_gates.py
git commit -m "feat(qmc): evaluate scalable physics gates"
```

Expected: the clean fixture passes after reveal and each mutation fails its named gate.

### Task 6: Assemble the audit-first evaluator and generic CLI

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/evaluator.py`
- Create: `tracks/qmc/solutions/BOTS-848/run_scalable_evaluator.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/test_scalable_evaluator.py`

- [ ] **Step 1: Write the evaluator ordering tests**

+Create these complete synthetic types and helpers in the test file:

```python
import json
from pathlib import Path

import numpy as np
import pytest

from scalable_v1.audit import freeze_manifest
from scalable_v1.contracts import ConstructionCertificate, ResourceMetrics, SampleBatch
from scalable_v1.evaluator import evaluate_candidate
from scalable_v1.protocol import load_protocol


class FakeState:
    def __init__(self, label: str, l: int, m: int, energy: float, l2: float):
        self.label, self.l, self.m = label, l, m
        self.energy, self.l2 = energy, l2

    def sample(self, n_samples: int, seed: int) -> SampleBatch:
        return SampleBatch(np.arange(n_samples), n_samples, 1024, seed)

    def logpsi(self, config_batch) -> np.ndarray:
        return np.zeros(len(config_batch), dtype=complex)

    def local_energy(self, config_batch) -> np.ndarray:
        return np.full(len(config_batch), self.energy, dtype=complex)

    def local_l2(self, config_batch) -> np.ndarray:
        return np.full(len(config_batch), self.l2, dtype=complex)


class FakeCandidate:
    name, family = "synthetic", "contract-test"

    def ground_state(self):
        return FakeState("ground", 0, 0, 1.0, 0.0)

    def generate_multiplet(self):
        return {m: FakeState(f"l2_m{m}", 2, m, 1.1, 6.0) for m in range(-2, 3)}

    def construction_certificate(self):
        return ConstructionCertificate(True, True, True, 100, "synthetic exact fixture")

    def resource_metrics(self):
        return ResourceMetrics(
            "local", 1e-6, 1024, None, 512, 100, 50.0,
            True, 1.5, 1.2, "cpu:test",
        )


class FakeDiagnostics:
    def evaluate(self, candidate, *, seed, swap_probes, rotation_probes):
        assert seed == 3848
        assert swap_probes == 64
        assert rotation_probes == 32
        return {
            "lll_residual": 0.0, "particle_swap_residual": 0.0,
            "finite_rotation_residual": 0.0, "tower_ladder_residual": 0.0,
        }


def make_evaluation_files(tmp_path: Path, *, tamper: bool):
    project, run = tmp_path / "project", tmp_path / "run"
    project.mkdir(); run.mkdir()
    source = project / "candidate.py"
    artifacts = {
        "checkpoint": run / "checkpoint.bin",
        "optimizer_state": run / "optimizer.bin",
        "training_log": run / "training.log",
    }
    oracle = tmp_path / "oracle.json"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    for role, path in artifacts.items():
        path.write_bytes(role.encode("utf-8"))
    oracle.write_text(
        json.dumps({"ground_energy": 1.0, "l2_by_m": {str(m): 1.1 for m in range(-2, 3)}}),
        encoding="utf-8",
    )
    protocol = load_protocol()
    manifest = freeze_manifest(
        run_dir=run, project_root=project, route="occupation_autoregressive",
        attempt="scalable-v1-s01-a01", protocol=protocol, selected_update=2048,
        training_seed=848,
        source_files=[source], artifact_files=artifacts,
    )
    if tamper:
        artifacts["checkpoint"].write_bytes(b"changed")
    return project, manifest, oracle


def test_clean_evaluator_loads_oracle_after_audit(tmp_path) -> None:
    project, manifest, oracle = make_evaluation_files(tmp_path, tamper=False)
    calls = []

    def loader(text):
        calls.append("oracle")
        return json.loads(text)

    result = evaluate_candidate(
        candidate=FakeCandidate(), diagnostics=FakeDiagnostics(),
        protocol=load_protocol(), manifest_path=manifest,
        project_root=project, oracle_path=oracle, training_seed=848,
        oracle_loader=loader,
    )
    assert calls == ["oracle"]
    assert result["schema_version"] == "challenge-15-scalable-v1.0"
    assert result["blindness"] == {"human_blind": False, "oracle_isolated": True}
    assert result["gates"]["scalable_v1_pass"] is True


def test_tampered_manifest_blocks_oracle_loader(tmp_path) -> None:
    project, manifest, oracle = make_evaluation_files(tmp_path, tamper=True)
    called = False

    def loader(text):
        nonlocal called
        called = True
        return json.loads(text)

    with pytest.raises(ValueError, match="manifest audit failed"):
        evaluate_candidate(
            candidate=FakeCandidate(), diagnostics=FakeDiagnostics(),
            protocol=load_protocol(), manifest_path=manifest,
            project_root=project, oracle_path=oracle, training_seed=848,
            oracle_loader=loader,
        )
    assert called is False
```

- [ ] **Step 2: Run the test and verify RED**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_scalable_evaluator.py -q
```

Expected: import fails because `evaluator.py` is absent.

- [ ] **Step 3: Implement candidate-only evidence collection**

```python
from __future__ import annotations

import json
import math
from dataclasses import asdict
from pathlib import Path

import numpy as np

from .audit import verify_manifest
from .gates import apply_ed_reveal, evaluate_pre_reveal
from .resources import RuntimeMeter
from .statistics import blocking_estimate


def collect_evidence(candidate, diagnostics, protocol, training_seed):
    tower = dict(candidate.generate_multiplet())
    if set(tower) != {-2, -1, 0, 1, 2}:
        raise ValueError("candidate must generate M=-2,...,2")
    states = [("ground", candidate.ground_state())]
    states.extend((str(m), tower[m]) for m in range(-2, 3))
    estimates = {}
    for state_index, (label, state) in enumerate(states):
        energy_rows, l2_rows = [], []
        for chain_index in range(protocol.sampling["chains"]):
            seed = training_seed + 1000 * state_index + chain_index
            batch = state.sample(protocol.sampling["samples_per_chain"], seed)
            if batch.burn_in_steps != protocol.sampling["burn_in_steps"]:
                raise ValueError("candidate did not honor frozen burn-in")
            log_values = np.asarray(state.logpsi(batch.configs))
            if log_values.shape != (batch.n_samples,) or not np.all(np.isfinite(log_values)):
                raise ValueError("logpsi must return one finite complex value per sample")
            energy_rows.append(state.local_energy(batch.configs))
            l2_rows.append(state.local_l2(batch.configs))
        estimates[label] = {
            "energy": blocking_estimate(np.stack(energy_rows), block_size=protocol.sampling["block_size"]).to_dict(),
            "l2": blocking_estimate(np.stack(l2_rows), block_size=protocol.sampling["block_size"]).to_dict(),
        }
    excited = [estimates[str(m)]["energy"] for m in range(-2, 3)]
    combined_mean = sum(item["mean"] for item in excited) / 5.0
    combined_error = math.sqrt(sum(item["standard_error"] ** 2 for item in excited)) / 5.0
    ground = estimates["ground"]["energy"]
    gap_mean = combined_mean - ground["mean"]
    gap_error = math.hypot(combined_error, ground["standard_error"])
    resource_record = asdict(candidate.resource_metrics())
    resource_record["effective_sample_size"] = min(
        state["energy"]["effective_sample_size"] for state in estimates.values()
    )
    return {
        "construction": asdict(candidate.construction_certificate()),
        "statistics": {
            "ground": estimates["ground"],
            "l2_by_m": {str(m): estimates[str(m)] for m in range(-2, 3)},
            "combined_l2": {"mean": combined_mean, "standard_error": combined_error},
            "gap": {"mean": gap_mean, "standard_error": gap_error},
        },
        "diagnostics": dict(diagnostics.evaluate(
            candidate,
            seed=protocol.symmetry["seed"],
            swap_probes=protocol.symmetry["swap_probes"],
            rotation_probes=protocol.symmetry["rotation_probes"],
        )),
        "resources": resource_record,
    }
```

This function accepts no oracle path and imports no Benchmark v0 module.

- [ ] **Step 4: Implement audit-first evaluation and JSON writing**

```python
def evaluate_candidate(*, candidate, diagnostics, protocol, manifest_path,
                       project_root, oracle_path, training_seed,
                       oracle_loader=json.loads,
                       progress=None):
    emit = progress if progress is not None else lambda message: None
    emit("auditing frozen checkpoint")
    audit = verify_manifest(
        Path(manifest_path), project_root=Path(project_root), protocol=protocol,
        expected_training_seed=training_seed,
    )
    if not audit.valid:
        raise ValueError(f"manifest audit failed: {audit.issues}")
    emit("collecting candidate evidence")
    with RuntimeMeter() as meter:
        evidence = collect_evidence(
            candidate, diagnostics, protocol, training_seed
        )
    evidence["resources"]["wall_seconds"] = max(
        evidence["resources"]["wall_seconds"], meter.wall_seconds
    )
    evidence["resources"]["peak_rss_bytes"] = max(
        evidence["resources"]["peak_rss_bytes"], meter.peak_rss_bytes
    )
    evidence["resources"]["checkpoint_bytes"] = max(
        evidence["resources"]["checkpoint_bytes"], audit.artifact_bytes
    )
    evidence["resources"]["ess_per_second"] = (
        evidence["resources"]["effective_sample_size"]
        / evidence["resources"]["wall_seconds"]
    )
    pre_reveal = evaluate_pre_reveal(evidence, protocol, audit)
    emit("revealing N=6 ED oracle")
    oracle_text = Path(oracle_path).read_text(encoding="utf-8")
    result = apply_ed_reveal(pre_reveal, oracle_loader(oracle_text), protocol)
    result["schema_version"] = protocol.schema_version
    result["protocol_sha256"] = protocol.sha256
    result["system"] = dict(protocol.physics)
    result["candidate_model"] = {"name": candidate.name, "family": candidate.family}
    result["training_seed"] = training_seed
    result["blindness"] = {"human_blind": False, "oracle_isolated": True}
    return result


FINAL_GATE_NAMES = {
    "lll_valid", "antisymmetry_valid", "so3_equivariance_valid",
    "l2_casimir_valid", "fivefold_multiplet_valid", "mc_error_valid",
    "ed_crosscheck_valid", "reproducible_run_valid", "scalable_path_valid",
    "oracle_isolated", "blind_training_valid", "resource_budget_valid",
    "scalable_v1_pass",
}


def validate_run_record(result):
    if result.get("schema_version") != "challenge-15-scalable-v1.0":
        raise ValueError("unexpected scalable-v1 schema version")
    if set(result.get("gates", {})) != FINAL_GATE_NAMES:
        raise ValueError("run record has an incomplete gate set")
    if set(result.get("statistics", {}).get("l2_by_m", {})) != {"-2", "-1", "0", "1", "2"}:
        raise ValueError("run record has an incomplete L=2 multiplet")
    if result.get("blindness") != {"human_blind": False, "oracle_isolated": True}:
        raise ValueError("run record has an invalid blindness disclosure")


def write_json_report(result, output):
    validate_run_record(result)
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
```

- [ ] **Step 5: Implement the generic CLI**

The CLI takes `--candidate package.module:factory`, `--manifest`, `--oracle`,
`--output`, `--project-root`, and one required `--training-seed` from the frozen
three-seed set. The factory signature is
`factory(protocol, training_seed) -> tuple[CandidateAdapter, DiagnosticProvider]`.

```python
from __future__ import annotations

import argparse
import importlib
from pathlib import Path

from scalable_v1.evaluator import evaluate_candidate, write_json_report
from scalable_v1.protocol import load_protocol


def load_factory(spec: str):
    module_name, separator, attribute = spec.partition(":")
    if not separator:
        raise ValueError("candidate must use module:factory syntax")
    return getattr(importlib.import_module(module_name), attribute)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate a frozen Challenge #15 scalable candidate")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--oracle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--training-seed", type=int, required=True)
    args = parser.parse_args(argv)
    print("loading frozen protocol", flush=True)
    protocol = load_protocol()
    if args.training_seed not in protocol.training["seeds"]:
        parser.error("--training-seed is outside the frozen comparison set")
    candidate, diagnostics = load_factory(args.candidate)(protocol, args.training_seed)
    result = evaluate_candidate(
        candidate=candidate, diagnostics=diagnostics, protocol=protocol,
        manifest_path=args.manifest, project_root=args.project_root,
        oracle_path=args.oracle, training_seed=args.training_seed,
        progress=lambda message: print(message, flush=True),
    )
    write_json_report(result, args.output)
    print(f"wrote {args.output}", flush=True)
    return 0 if result["gates"]["scalable_v1_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Add the CLI round-trip test**

Install a temporary fake factory module into `sys.modules`, call `main([...])`,
and reload the output. Assert the schema, protocol hash, blindness disclosure,
all gate names, five M keys, resource fields, and final pass. This test uses a
temporary synthetic oracle JSON and must not import the real ED implementation.

```python
import sys
import types

from run_scalable_evaluator import main


def test_cli_round_trip(monkeypatch, tmp_path) -> None:
    project, manifest, oracle = make_evaluation_files(tmp_path, tamper=False)
    output = tmp_path / "run.json"
    module = types.ModuleType("synthetic_scalable_candidate")
    module.create = lambda protocol, training_seed: (FakeCandidate(), FakeDiagnostics())
    monkeypatch.setitem(sys.modules, module.__name__, module)
    exit_code = main([
        "--candidate", "synthetic_scalable_candidate:create",
        "--manifest", str(manifest), "--oracle", str(oracle),
        "--output", str(output), "--project-root", str(project),
        "--training-seed", "848",
    ])
    restored = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert restored["schema_version"] == "challenge-15-scalable-v1.0"
    assert len(restored["protocol_sha256"]) == 64
    assert restored["blindness"]["human_blind"] is False
    assert set(restored["statistics"]["l2_by_m"]) == {"-2", "-1", "0", "1", "2"}
    assert set(restored["gates"]) == {
        "lll_valid", "antisymmetry_valid", "so3_equivariance_valid",
        "l2_casimir_valid", "fivefold_multiplet_valid", "mc_error_valid",
        "ed_crosscheck_valid", "reproducible_run_valid", "scalable_path_valid",
        "oracle_isolated", "blind_training_valid", "resource_budget_valid",
        "scalable_v1_pass",
    }
    assert restored["resources"]["n8_smoke_complete"] is True
    assert restored["resources"]["effective_sample_size"] == 65536.0
    assert restored["resources"]["ess_per_second"] > 0.0
    assert restored["gates"]["scalable_v1_pass"] is True
```

- [ ] **Step 7: Run GREEN and commit**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_scalable_evaluator.py -q
git add tracks/qmc/solutions/BOTS-848/scalable_v1/evaluator.py tracks/qmc/solutions/BOTS-848/run_scalable_evaluator.py tracks/qmc/solutions/BOTS-848/tests/test_scalable_evaluator.py
git commit -m "feat(qmc): add audit-first scalable evaluator"
```

Expected: the clean synthetic candidate writes a passing report; a tampered
manifest prevents any oracle read.

### Task 7: Close Step 1 with logs, documentation, and fresh verification

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/README.md`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s01-a01.md`
- Modify: `tracks/qmc/solutions/BOTS-848/README.md`
- Modify: `docs/superpowers/specs/2026-07-28-challenge-15-scalable-v1-design.md`

- [ ] **Step 1: Run the complete fresh test set**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests -q
git diff --check
git status --short
```

Expected: all old and new tests pass; `git diff --check` is silent; status lists
only the uncommitted Step 1 journal/index/status edits.

- [ ] **Step 2: Run the forbidden-dependency and protocol checks**

```powershell
rg -n --glob '!protocol.json' "benchmark_v0\.(ed_oracle|fock_ed|projected_nqs|nqs_benchmark)" tracks/qmc/solutions/BOTS-848/scalable_v1 tracks/qmc/solutions/BOTS-848/run_scalable_evaluator.py
python -c "import sys; sys.path.insert(0, r'tracks/qmc/solutions/BOTS-848'); from scalable_v1.protocol import load_protocol; p=load_protocol(); print(p.schema_version, p.sha256)"
```

Expected: `rg` prints no match and exits `1`. Python prints
`challenge-15-scalable-v1.0` followed by a 64-character hash.

- [ ] **Step 3: Write the actual attempt journal and five-step index**

Record actual start/end timestamps, starting commit, implementation commits,
commands, exit codes, pytest count, protocol hash, result classification, and
remaining Step 1 attempts. If every verification above passes, classify
`s01-a01` as `step-pass` and record four unused Step 1 attempts.

Create this exact index table:

```markdown
| Step | Purpose | Current attempt | Status |
|---:|---|---:|---|
| 1 | common protocol and evaluator | a01 | step-pass |
| 2 | occupation autoregressive NQS | not started | pending |
| 3 | continuous holomorphic NQS | not started | pending |
| 4 | CF-Flow L=2 and route selection | not started | pending |
| 5 | winner N=8, then SCNet N=10/12 | not started | pending |
```

State explicitly that Step 2 restarts at `a01` in a new worktree.

- [ ] **Step 4: Update project status**

Link `scalable_v1/protocol.json`, `run_scalable_evaluator.py`, and the new log
index from the BOTS:848 README. State that Step 1 provides the evaluation
contract only and that no candidate route exists yet. Change the design status
to `approved; Step 1 protocol/evaluator implemented` only after the full test
set passes.

Add these README rows/bullets:

```markdown
| [Scalable v1 protocol](scalable_v1/protocol.json) | Frozen route-independent budgets, thresholds, and resource ceilings. |
| [Scalable v1 logs](logs/scalable-v1/README.md) | Five research steps and per-step implementation-attempt accounting. |

- Scalable v1 Step 1 is complete: the audit-first evaluator is available through `run_scalable_evaluator.py`.
- No scalable candidate route has been implemented; Step 2 begins with occupation-space autoregressive NQS Attempt a01.
```

Replace the design status line with exactly:

```markdown
> Status: approved; Step 1 protocol/evaluator implemented
```

- [ ] **Step 5: Commit closure and verify cleanliness**

```powershell
git add tracks/qmc/solutions/BOTS-848/logs/scalable-v1 tracks/qmc/solutions/BOTS-848/README.md
git add -f docs/superpowers/specs/2026-07-28-challenge-15-scalable-v1-design.md
git commit -m "docs(qmc): close scalable v1 step 1"
git status --short
```

Expected: closure commit succeeds and final status is empty.

## Step 1 acceptance checklist

- [ ] Frozen `protocol.json` loads, hashes, and rejects inconsistent copies.
- [ ] Candidate state handles expose the approved six-part evaluation surface.
- [ ] Blocking, ESS, error propagation, and residual helpers pass exact tests.
- [ ] Frozen manifests detect changed artifacts and forbidden ED/projector imports.
- [ ] ED data loads only after the manifest/oracle-isolation audit passes.
- [ ] Every Benchmark v0 gate plus scalable, oracle, and resource gates is present.
- [ ] The synthetic end-to-end adapter writes complete `run.json` data through the CLI.
- [ ] N=8 smoke evidence is required structurally; no real N=8 training is present.
- [ ] The attempt journal contains no secret or private connection detail.
- [ ] Full BOTS:848 tests pass and the attempt worktree is clean after closure.
