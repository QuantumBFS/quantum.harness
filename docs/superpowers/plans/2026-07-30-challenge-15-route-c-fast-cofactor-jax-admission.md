# Challenge #15 Route C Fast Cofactor-JAX Admission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decide within 90 implementation minutes whether the exact one-layer strict-LLL Route C backend can pass the unchanged N=6 batch-512 CPU resource gate.

**Architecture:** Replace the a02 determinant-over-sparse-jets hot path with a division-free analytic JK cofactor polynomial returning the L=0 seed and all five L=2 components. Apply the fixed pair-Casimir polynomials with nested JAX directional JVPs and one vector-valued Horner chain, then JIT whole sector batches on an explicitly selected CPU device. Stop Route C deadline work if the full N=6 gate is not GREEN inside the timebox.

**Tech Stack:** Python 3, NumPy, JAX CPU/x64, pytest, SCNet Slurm, existing `PairJet` and pair-Casimir references.

---

## Fixed execution boundary

- Start the 90-minute clock immediately before Task 1 Step 1.
- Checkpoints: cofactor GREEN by minute 30; JVP small-exact GREEN and an N=6 single-config compile by minute 60; unchanged N=6 batch-512 classification by minute 90.
- A GREEN resource classification requires two warmups and five measured calls for both the L=0 and reduced-L=2 views, `compile_seconds + 2*2048*max(median_sector_seconds) <= 3600`, and peak RSS at most `51539607552` bytes.
- An early RED is allowed after a full-shape call only if its observed lower bound already makes the inequality impossible. Reduced batches never produce GREEN.
- Do not start trainer, ED reveal, approximation, dense jets, or a03 allocation in this plan.

### Task 1: Division-free six-component JK cofactor seed

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/cofactor_seed.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_cofactor_seed.py`

- [ ] **Step 1: Write the failing direct-determinant comparison**

```python
from __future__ import annotations

import numpy as np
import pytest

from scalable_v1.routes.cf_operator_nqs.cofactor_seed import (
    cofactor_seed_family_amplitudes,
)
from scalable_v1.routes.cf_operator_nqs.seeds import JKCFSeedFamily


def _configs(n: int) -> np.ndarray:
    rng = np.random.default_rng(848 + n)
    values = rng.normal(size=(2, n, 2)) + 1j * rng.normal(size=(2, n, 2))
    return values / np.linalg.norm(values, axis=-1, keepdims=True)


@pytest.mark.parametrize("n", range(2, 9))
def test_cofactor_family_matches_direct_jk_determinants(n: int) -> None:
    family = JKCFSeedFamily(n_electrons=n, two_q=3 * (n - 1))
    configs = _configs(n)
    expected = np.column_stack(
        (
            family.ground_state().amplitude(configs),
            *(family.generate_multiplet()[m].amplitude(configs) for m in range(-2, 3)),
        )
    )
    actual = np.stack(
        [cofactor_seed_family_amplitudes(family, config) for config in configs]
    )
    np.testing.assert_allclose(actual, expected, rtol=1.0e-12, atol=1.0e-300)
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_cofactor_seed.py -q
```

Expected: collection fails with `ModuleNotFoundError` for `cofactor_seed`.

- [ ] **Step 3: Implement the minimal analytic cofactor polynomial**

Implement `cofactor_seed_family_amplitudes(family, spinors, *, xp=np)` with these exact identities:

```python
def _product(values: list[object]) -> object:
    result: object = 1.0
    for value in values:
        result = result * value
    return result


def _elementary_homogeneous(spinors: object, rows: tuple[int, ...], xp: object) -> object:
    coefficients = [xp.asarray(1.0 + 0.0j)] + [xp.asarray(0.0 + 0.0j)] * len(rows)
    for row in rows:
        updated = [xp.asarray(0.0 + 0.0j)] * len(coefficients)
        for degree in range(len(coefficients)):
            updated[degree] = updated[degree] + spinors[row, 1] * coefficients[degree]
            if degree:
                updated[degree] = updated[degree] + spinors[row, 0] * coefficients[degree - 1]
        coefficients = updated
    return xp.stack(coefficients)


def _replacement_determinant(
    family: JKCFSeedFamily,
    spinors: object,
    jastrow: list[object],
    derivative_u: list[object],
    derivative_v: list[object],
    delta: list[list[object]],
    *,
    hole: int,
    particle_twice_m: int,
    xp: object,
) -> object:
    n = family.n_electrons
    twice_l = int(round(2.0 * family.particle_l))
    a = (twice_l + particle_twice_m) // 2
    b = (twice_l - particle_twice_m) // 2
    orbital_norm = math.sqrt(math.comb(twice_l, a))
    column = [
        orbital_norm
        * (
            (b * spinors[r, 0] ** a * spinors[r, 1] ** (b - 1) * derivative_u[r] if b else 0.0)
            - (a * spinors[r, 0] ** (a - 1) * spinors[r, 1] ** b * derivative_v[r] if a else 0.0)
        )
        for r in range(n)
    ]
    normalization = _product(
        [math.sqrt(math.comb(n - 1, k)) for k in range(n) if k != hole]
    )
    vandermonde_sign = -1.0 if ((n - 1) * (n - 2) // 2) % 2 else 1.0
    terms = []
    for r in range(n):
        rows = tuple(s for s in range(n) if s != r)
        excluded_vandermonde = _product(
            [delta[i][j] for i in rows for j in rows if i < j]
        )
        elementary = _elementary_homogeneous(spinors, rows, xp)[n - 1 - hole]
        cofactor = (
            ((-1.0) ** (r + hole))
            * vandermonde_sign
            * normalization
            * _product([jastrow[s] for s in rows])
            * excluded_vandermonde
            * elementary
        )
        terms.append(cofactor * column[r])
    return sum(terms)
```

The public function must validate `family`, require shape `(N,2)`, build all `Delta_ij`, division-free `J_i`, `dJ_i/du_i`, and `dJ_i/dv_i`, return `xp.stack([L0, L2M-2, ..., L2M2])`, and contract `family._couplings[m]` without a determinant or division.

- [ ] **Step 4: Run focused and existing seed tests**

Run:

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_cofactor_seed.py tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_seeds.py -q
```

Expected: all tests pass; the worst cofactor/direct relative residual is at most `1e-12`.

- [ ] **Step 5: Commit the cofactor slice**

```powershell
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/cofactor_seed.py tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_cofactor_seed.py
git commit -m "feat(qmc): add analytic JK cofactor family"
```

### Task 2: Exact JAX JVP pair-Casimir action

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/jax_action.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_jax_action.py`

- [ ] **Step 1: Install and smoke the selected CPU/x64 backend on D:**

Run from Git Bash or the repository Make environment:

```text
make install jax EXTRA=cpu
```

Then on Windows:

```powershell
.venv\Scripts\python.exe -c "import jax; jax.config.update('jax_enable_x64', True); print(jax.devices()); print(jax.numpy.ones(1, dtype=jax.numpy.complex128).dtype)"
```

Expected: only the selected CPU is used and the dtype is `complex128`.

- [ ] **Step 2: Write failing JVP/reference tests**

```python
from __future__ import annotations

import numpy as np
import pytest

from scalable_v1.routes.cf_operator_nqs.coordinate_action import evaluate_seed_and_actions
from scalable_v1.routes.cf_operator_nqs.jax_action import build_family_action_kernel
from scalable_v1.routes.cf_operator_nqs.seeds import JKCFSeedFamily


@pytest.mark.parametrize("n", (2, 3))
def test_jax_family_action_matches_pairjet_reference(n: int) -> None:
    family = JKCFSeedFamily(n_electrons=n, two_q=3 * (n - 1))
    rng = np.random.default_rng(1848 + n)
    configs = rng.normal(size=(1, n, 2)) + 1j * rng.normal(size=(1, n, 2))
    configs /= np.linalg.norm(configs, axis=-1, keepdims=True)
    kernel = build_family_action_kernel(family, platform="cpu", sector="family")
    seeds, actions = (np.asarray(item) for item in kernel(configs))
    states = (family.ground_state(), *(family.generate_multiplet()[m] for m in range(-2, 3)))
    expected = [evaluate_seed_and_actions(state, configs) for state in states]
    np.testing.assert_allclose(seeds[:, 0], expected[0][0], rtol=1e-10, atol=1e-300)
    for sector, (expected_seed, expected_action) in enumerate(expected):
        np.testing.assert_allclose(seeds[:, sector], expected_seed, rtol=1e-10, atol=1e-300)
        np.testing.assert_allclose(actions[:, sector], expected_action, rtol=1e-10, atol=1e-11)
    assert seeds.dtype == np.complex128
    assert actions.dtype == np.complex128


def test_jax_action_rejects_missing_platform() -> None:
    family = JKCFSeedFamily(n_electrons=2, two_q=3)
    with pytest.raises(RuntimeError, match="platform"):
        build_family_action_kernel(family, platform="not-a-platform", sector="family")
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_jax_action.py -q
```

Expected: collection fails with `ModuleNotFoundError` for `jax_action`.

- [ ] **Step 4: Implement vector fields, pair dot, and shared Horner kernel**

Implement these exact internal shapes and recurrences:

```python
_SECTORS = {"l0": (0,), "l2": (1, 2, 3, 4, 5), "family": (0, 1, 2, 3, 4, 5)}


def _field_tangent(x: object, particle: object, field: str) -> object:
    tangent = jnp.zeros_like(x)
    u, v = x[particle, 0], x[particle, 1]
    if field == "z":
        return tangent.at[particle, 0].set(0.5 * u).at[particle, 1].set(-0.5 * v)
    if field == "plus":
        return tangent.at[particle, 1].set(u)
    if field == "minus":
        return tangent.at[particle, 0].set(v)
    raise ValueError("unknown vector field")


def _apply_field(function: object, x: object, particle: object, field: str) -> object:
    return jax.jvp(function, (x,), (_field_tangent(x, particle, field),))[1]


def _pair_dot(function: object, x: object, first: object, second: object) -> object:
    zi = lambda y: _apply_field(function, y, first, "z")
    plus_i = lambda y: _apply_field(function, y, first, "plus")
    minus_i = lambda y: _apply_field(function, y, first, "minus")
    return (
        _apply_field(zi, x, second, "z")
        + 0.5 * _apply_field(plus_i, x, second, "minus")
        + 0.5 * _apply_field(minus_i, x, second, "plus")
    )


def _pair_polynomials(seed_function, x, pair, coefficients, scale):
    first, second = pair[0], pair[1]
    current = lambda y: coefficients[:, 4, None] * seed_function(y)[None, :]
    for degree in range(3, -1, -1):
        previous = current
        current = lambda y, previous=previous, degree=degree: (
            coefficients[:, degree, None] * seed_function(y)[None, :]
            + _pair_dot(previous, y, first, second) / scale
        )
    return current(x)
```

`build_family_action_kernel` must:

- call `jax.config.update("jax_enable_x64", True)` before constructing arrays;
- resolve `jax.devices(platform)` and raise instead of falling back;
- pad the three pair-Casimir coefficient rows to shape `(3,5)` and verify one shared scale;
- select `l0`, `l2`, or all six seed outputs before differentiation so XLA can eliminate unused sectors;
- `vmap` `_pair_polynomials` over all unordered particle pairs, sum them, add `N*self_scalar*seed`, transpose to actions shape `(sector_count,3)`, then `vmap` over batch;
- return `jax.jit(batch_function, device=selected_device)` producing `(seeds, actions)`.

- [ ] **Step 5: Run reduced exact tests and the N=6 single-config compile checkpoint**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_jax_action.py -q
.venv\Scripts\python.exe -c "import numpy as np; from scalable_v1.routes.cf_operator_nqs.jax_action import build_family_action_kernel; from scalable_v1.routes.cf_operator_nqs.seeds import JKCFSeedFamily; f=JKCFSeedFamily(n_electrons=6,two_q=15); x=np.ones((1,6,2),dtype=np.complex128); x/=np.linalg.norm(x,axis=-1,keepdims=True); y=build_family_action_kernel(f,platform='cpu',sector='l2')(x); y[0].block_until_ready(); print(y[0].shape,y[1].shape)"
```

Expected: tests pass; the N=6 call compiles and returns shapes `(1,5)` and `(1,5,3)`. If minute 60 is exceeded before this result, record RED and stop.

- [ ] **Step 6: Commit the exact JVP slice**

```powershell
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/jax_action.py tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_jax_action.py
git commit -m "feat(qmc): add exact JAX pair-Casimir action"
```

### Task 3: Frozen action microbenchmark and classifier

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/microbenchmark.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_microbenchmark.py`

- [ ] **Step 1: Write failing classifier and reduced-smoke tests**

```python
from __future__ import annotations

import json

from scalable_v1.routes.cf_operator_nqs.microbenchmark import classify_record


def test_classifier_requires_frozen_full_shape() -> None:
    record = {
        "n_electrons": 6,
        "two_q": 15,
        "batch_size": 512,
        "warmup_repetitions": 2,
        "measured_repetitions": 5,
        "compile_seconds": 10.0,
        "sector_median_seconds": {"l0": 0.20, "l2": 0.30},
        "peak_rss_bytes": 1024,
        "finite": True,
    }
    result = classify_record(record)
    assert result["classification"] == "GREEN"
    assert result["projected_action_seconds"] == 10.0 + 2 * 2048 * 0.30


def test_classifier_rejects_reduced_batch() -> None:
    record = {
        "n_electrons": 6,
        "two_q": 15,
        "batch_size": 8,
        "warmup_repetitions": 2,
        "measured_repetitions": 5,
        "compile_seconds": 1.0,
        "sector_median_seconds": {"l0": 0.01, "l2": 0.01},
        "peak_rss_bytes": 1024,
        "finite": True,
    }
    assert classify_record(record)["classification"] == "RED"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_microbenchmark.py -q
```

Expected: collection fails with `ModuleNotFoundError` for `microbenchmark`.

- [ ] **Step 3: Implement exact timing and atomic JSON evidence**

Implement:

```python
def classify_record(record: Mapping[str, object]) -> dict[str, object]:
    medians = record["sector_median_seconds"]
    projected = float(record["compile_seconds"]) + 2 * 2048 * max(
        float(medians["l0"]), float(medians["l2"])
    )
    frozen_shape = (
        record["n_electrons"] == 6
        and record["two_q"] == 15
        and record["batch_size"] == 512
        and record["warmup_repetitions"] == 2
        and record["measured_repetitions"] == 5
    )
    green = (
        frozen_shape
        and bool(record["finite"])
        and projected <= 3600.0
        and int(record["peak_rss_bytes"]) <= 51539607552
    )
    return {
        "classification": "GREEN" if green else "RED",
        "projected_action_seconds": projected,
    }
```

The CLI must accept `--n-electrons`, `--batch-size`, `--platform`, and `--output`; generate normalized deterministic complex probes; build separate `l0` and `l2` kernels; time first blocked calls as compile, perform exactly two blocked warmups and five blocked measurements per sector for the frozen run; record every sample, medians, JAX/Python/device/source/protocol metadata, finiteness, and `peak_rss_bytes()`; write through a sibling temporary file and `os.replace`; print progress with `flush=True` after each compile/warmup/measurement.

- [ ] **Step 4: Run classifier tests and a reduced N=2 smoke**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_microbenchmark.py -q
.venv\Scripts\python.exe -m scalable_v1.routes.cf_operator_nqs.microbenchmark --n-electrons 2 --batch-size 4 --platform cpu --warmups 1 --repetitions 2 --output results/route-c-jvp-smoke/action-microbenchmark.json
```

Expected: tests pass; JSON exists, is finite, records CPU/complex128, and classifies reduced smoke as RED because it is not the frozen full shape.

- [ ] **Step 5: Commit benchmark machinery**

```powershell
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/microbenchmark.py tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_microbenchmark.py
git commit -m "feat(qmc): add Route C JVP admission gate"
```

### Task 4: SCNet CPU full-shape admission

**Files:**
- Create: `scripts/run_route_c_jvp_admission.sbatch`
- Produce: `results/route-c-jvp-admission/action-microbenchmark.json`
- Modify after result: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02c-a02.md`

- [ ] **Step 1: Create the exact SCNet job wrapper**

```bash
#!/usr/bin/env bash
#SBATCH --job-name=qmc-c-jvp
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --time=00:30:00
#SBATCH --output=results/route-c-jvp-admission/slurm-%j.out
#SBATCH --error=results/route-c-jvp-admission/slurm-%j.err
set -euo pipefail
mkdir -p results/route-c-jvp-admission
export JAX_PLATFORM_NAME=cpu
export JAX_ENABLE_X64=True
export XLA_FLAGS="--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads=32"
.venv/bin/python -u -m scalable_v1.routes.cf_operator_nqs.microbenchmark \
  --n-electrons 6 \
  --batch-size 512 \
  --platform cpu \
  --warmups 2 \
  --repetitions 5 \
  --output results/route-c-jvp-admission/action-microbenchmark.json
```

- [ ] **Step 2: Re-run focused correctness before shipping**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_cofactor_seed.py tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_jax_action.py tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_microbenchmark.py -q
git diff --check
git status --short
```

Expected: all focused tests pass, diff check is clean, and only the intended job wrapper/plan bookkeeping is dirty.

- [ ] **Step 3: Commit and ship through the authorized branch**

```powershell
git add scripts/run_route_c_jvp_admission.sbatch
git commit -m "chore(qmc): add SCNet Route C admission job"
git push -u origin challenge/qmc-chiral-graviton-scalable-v1-s02c-a02
```

On SCNet, fetch and check out the exact pushed commit in `~/quantum.harness`, then create `.venv` on SCNet and install CPU JAX only if its import smoke fails. Record `git rev-parse HEAD`, Python, JAX, and `jax.devices()`.

- [ ] **Step 4: Run Slurm precheck, live partition probe, and exact test-only request**

Run via `scripts/harness_slurm.sh` with `HARNESS_CLUSTER_PROFILE=skills/using-slurm/profiles/scnet.toml`:

```text
precheck
probe-partitions
submit --test-only --script scripts/run_route_c_jvp_admission.sbatch --partition hx1hdnormal01 --time 00:30:00 --cpus 32
```

Expected: SSH succeeds, the selected partition is CPU-capable and currently viable, and Slurm accepts the exact 32-CPU/64-GiB request. Do not submit if the estimated start is incompatible with the remaining deadline.

- [ ] **Step 5: Submit, monitor startup, and fetch evidence**

Submit the exact script, record job id, confirm `PD -> R`, tail the first progress line, then monitor to scheduler completion. Fetch both logs and `results/route-c-jvp-admission/action-microbenchmark.json`; verify that the JSON commit matches the submitted commit and that all timings are finite.

Expected GREEN: complete two-warmup/five-measurement record with classifier GREEN. Expected RED: explicit timeout/OOM/numerical/classifier evidence. `sbatch` or `COMPLETED` alone is not evidence.

- [ ] **Step 6: Record the deadline decision and commit**

Append to `s02c-a02.md`:

- design/plan/implementation commit hashes;
- local exact-test results;
- SCNet job id, partition, device, compile and all steady timings, MaxRSS;
- frozen classifier inputs and GREEN/RED result;
- if GREEN, state that a03 allocation/training planning is now unblocked but not yet completed;
- if RED or minute 90 expired, state that Route C is not salvageable inside the remaining deadline and that no dense-jet/training/ED fallback was started.

Then run:

```powershell
git add tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02c-a02.md results/route-c-jvp-admission/action-microbenchmark.json
git commit -m "docs(qmc): record Route C JVP admission result"
```

## Plan self-review result

- Spec coverage: exact cofactor, strict JVP action, CPU/x64 placement, unchanged N=6 gate, SCNet evidence, stop boundary, and oracle isolation are each mapped to a task.
- Scope: this plan decides backend admission only; trainer and a03 work remain a separate post-GREEN plan.
- Type consistency: family sector order is `(L0M0,L2M-2,L2M-1,L2M0,L2M1,L2M2)`; action shape is `(B,sectors,3)` throughout.
- Completeness scan: every implementation and verification step is concrete.
