# Phase 8 Sigma=1.75 Finite-Size Scaling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the fixed `L=64,128` correlation-ratio crossing at
`sigma=1.75`, evaluate direct `chi=128` gaps at one common primary critical
field for `L=32,64,128`, and report two-point finite-size sensitivities for
`Gamma_c` and `z`.

**Architecture:** A pure analysis module owns strict two-endpoint crossing
and two-point sensitivity mathematics. A planner CLI creates the two-cell
crossing specification, then creates the six-state common-field
specification only after the crossing gate passes. The existing
`benchmark_phase6_optimizations.py` runner performs every TeNPy calculation
and retains checkpoint/provenance behavior; a Phase 8 report CLI consumes
only successful summaries.

**Tech Stack:** Python 3.11, NumPy, TeNPy, pytest, matplotlib, JSON/CSV/HDF5.

## Global Constraints

- Hamiltonian: pinned periodic Hurwitz-zeta LRTFIM in the rotated parity
  basis.
- First and only active sigma: `sigma=1.75`.
- Sizes: `L=32,64,128`; never `L=256`.
- MPO: `K=24`, `alpha=0.5`, `r_fit=2048`, exact-zero pruning, no
  approximate compression.
- Crossing: `chi=64`, even sector, only `Gamma=1.55,1.60`.
- The Phase 7 `chi=64` to `chi=128` `R_xi` shifts were below the relevant
  crossing-resolution uncertainty, which justifies `chi=64` only for these
  `L=128` crossing endpoints.
- Gaps: direct even and odd states at `chi=128` and the common
  `Gamma_c_power`.
- A crossing requires a strict sign change; otherwise stop unresolved.
- No Gamma extension, adaptive search, `K=32`, or automatic `chi=256`.
- `Gamma_c_power`, `Gamma_c_log`, `z_power`, and `z_log` are exact
  two-point sensitivity extrapolations, not regression analyses.
- `1/L` and `1/log(L)` are sensitivity coordinates only; neither assumes a
  known leading correction exponent.
- `Gamma_c` power/log sensitivity is not fully propagated into gap
  uncertainties.
- Susceptibility `gamma/nu` is outside scope. Store equal-time correlations
  and `S_eq(0)` only as auxiliary diagnostics.
- Do not create a `sigma=1.80` or `sigma=2.00` run specification during
  this plan; the completed `sigma=1.75` result requires explicit review
  first.

---

### Task 1: Add strict Phase 8 sensitivity mathematics

**Files:**
- Create: `src/lrtfim/phase8_scaling.py`
- Create: `tests/test_phase8_scaling.py`

**Interfaces:**
- Consumes: two endpoint Gamma values and `R_xi` values; three positive
  gaps.
- Produces:
  - `strict_endpoint_crossing(gammas, r_small, r_large) -> dict`
  - `two_point_sensitivity(values, base_lengths, form) -> dict`
  - `gap_scaling_summary(lengths, gaps) -> dict`

- [x] **Step 1: Write failing tests for the crossing gate**

```python
import pytest

from lrtfim.phase8_scaling import strict_endpoint_crossing


def test_strict_crossing_interpolates_only_a_sign_change():
    result = strict_endpoint_crossing(
        [1.55, 1.60],
        [0.41, 0.47],
        [0.44, 0.45],
    )
    assert result["status"] == "resolved"
    assert result["differences"] == pytest.approx([-0.03, 0.02])
    assert 1.55 < result["Gamma_x"] < 1.60


def test_strict_crossing_rejects_unbracketed_endpoints():
    result = strict_endpoint_crossing(
        [1.55, 1.60],
        [0.41, 0.43],
        [0.44, 0.45],
    )
    assert result["status"] == "unresolved_no_L64_L128_bracket"
    assert "Gamma_x" not in result
```

- [x] **Step 2: Run the crossing tests and verify RED**

Run:

```bash
PYTHONPATH=src:. conda run -n mps \
  pytest -q tests/test_phase8_scaling.py
```

Expected: collection fails because `lrtfim.phase8_scaling` does not exist.

- [x] **Step 3: Write failing tests for the exact two-point evaluations**

```python
from lrtfim.phase8_scaling import (
    gap_scaling_summary,
    two_point_sensitivity,
)


def test_power_and_log_sensitivities_are_explicit_two_point_evaluations():
    power = two_point_sensitivity([1.56, 1.558], [32, 64], "power")
    log = two_point_sensitivity([1.56, 1.558], [32, 64], "log")
    assert power["estimate"] == pytest.approx(1.556)
    assert power["residual_degrees_of_freedom"] == 0
    assert log["residual_degrees_of_freedom"] == 0
    assert power["interpretation"] == "two_point_sensitivity_extrapolation"


def test_gap_summary_keeps_effective_and_sensitivity_values_separate():
    result = gap_scaling_summary([32, 64, 128], [0.20, 0.12, 0.073])
    assert set(result["z_eff"]) == {"32_64", "64_128"}
    assert set(result["sensitivity"]) == {"power", "log", "spread"}
    assert result["sensitivity"]["power"]["residual_degrees_of_freedom"] == 0


def test_gap_summary_rejects_nonpositive_or_nondoubling_inputs():
    with pytest.raises(ValueError, match="positive"):
        gap_scaling_summary([32, 64, 128], [0.20, 0.0, 0.073])
    with pytest.raises(ValueError, match="doubling"):
        gap_scaling_summary([32, 60, 128], [0.20, 0.12, 0.073])
```

- [x] **Step 4: Implement the minimal pure module**

```python
"""Strict Phase 8 crossing and two-point sensitivity evaluations."""

from __future__ import annotations

import math
import numpy as np


def strict_endpoint_crossing(gammas, r_small, r_large) -> dict:
    x = np.asarray(gammas, dtype=float)
    small = np.asarray(r_small, dtype=float)
    large = np.asarray(r_large, dtype=float)
    if x.shape != (2,) or small.shape != (2,) or large.shape != (2,):
        raise ValueError("exactly two endpoint values are required")
    if not x[0] < x[1]:
        raise ValueError("Gamma endpoints must be strictly increasing")
    differences = small - large
    base = {
        "Gamma_endpoints": x.tolist(),
        "differences": differences.tolist(),
    }
    if not differences[0] * differences[1] < 0.0:
        return {
            **base,
            "status": "unresolved_no_L64_L128_bracket",
        }
    fraction = -differences[0] / (differences[1] - differences[0])
    return {
        **base,
        "status": "resolved",
        "fraction": float(fraction),
        "Gamma_x": float(x[0] + fraction * (x[1] - x[0])),
        "crossing_resolution": float((x[1] - x[0]) / 2.0),
    }


def two_point_sensitivity(values, base_lengths, form: str) -> dict:
    y = np.asarray(values, dtype=float)
    lengths = np.asarray(base_lengths, dtype=float)
    if y.shape != (2,) or lengths.shape != (2,):
        raise ValueError("exactly two size-pair values are required")
    if np.any(lengths <= 1.0) or not lengths[0] < lengths[1]:
        raise ValueError("base lengths must be increasing and exceed one")
    if form == "power":
        coordinate = 1.0 / lengths
    elif form == "log":
        coordinate = 1.0 / np.log(lengths)
    else:
        raise ValueError("form must be power or log")
    slope = (y[1] - y[0]) / (coordinate[1] - coordinate[0])
    estimate = y[0] - slope * coordinate[0]
    return {
        "form": form,
        "estimate": float(estimate),
        "coefficient": float(slope),
        "residual_degrees_of_freedom": 0,
        "interpretation": "two_point_sensitivity_extrapolation",
    }


def gap_scaling_summary(lengths, gaps) -> dict:
    sizes = np.asarray(lengths, dtype=int)
    values = np.asarray(gaps, dtype=float)
    if sizes.shape != (3,) or np.any(sizes[1:] != 2 * sizes[:-1]):
        raise ValueError("sizes must be three consecutive doubling values")
    if values.shape != (3,) or np.any(values <= 0.0):
        raise ValueError("gaps must contain three positive values")
    z32 = float(math.log(values[0] / values[1]) / math.log(2.0))
    z64 = float(math.log(values[1] / values[2]) / math.log(2.0))
    power = two_point_sensitivity([z32, z64], sizes[:2], "power")
    log = two_point_sensitivity([z32, z64], sizes[:2], "log")
    return {
        "lengths": sizes.tolist(),
        "gaps": values.tolist(),
        "z_eff": {"32_64": z32, "64_128": z64},
        "sensitivity": {
            "power": power,
            "log": log,
            "spread": abs(power["estimate"] - log["estimate"]),
        },
    }
```

- [x] **Step 5: Run the focused tests and verify GREEN**

Run:

```bash
PYTHONPATH=src:. conda run -n mps \
  pytest -q tests/test_phase8_scaling.py
```

Expected: all Phase 8 scaling tests pass.

- [x] **Step 6: Commit Task 1**

```bash
git add \
  tracks/mps/solutions/agent-of-my-agent-is-not-my-agent/src/lrtfim/phase8_scaling.py \
  tracks/mps/solutions/agent-of-my-agent-is-not-my-agent/tests/test_phase8_scaling.py
git commit -m "feat: add phase8 two-point sensitivity analysis"
```

---

### Task 2: Build the sigma=1.75 crossing planner and hard gate

**Files:**
- Create: `src/lrtfim/phase8_protocol.py`
- Create: `scripts/plan_phase8_scaling.py`
- Create: `tests/test_phase8_protocol.py`
- Create: `tests/test_phase8_planner_cli.py`

**Interfaces:**
- Consumes:
  - `results/phase7-crossover/broad/decisions/sigma-1.75.json`
  - `results/phase7-crossover/proposal/fits/sigma-1.75/fit-summary.json`
  - Phase 7 `L=64`, `chi=64` endpoint summaries.
- Produces:
  - `build_crossing_spec(output_dir) -> dict`
  - `decide_crossing(spec, summaries) -> dict`
  - `common_field_sensitivity(x32, x64) -> dict`
  - `build_gap_spec(decision, output_dir) -> dict`
  - CLI subcommands `crossing`, `decide`, and `gaps`.

- [x] **Step 1: Write failing protocol tests**

```python
from lrtfim.phase8_protocol import (
    build_crossing_spec,
    build_gap_spec,
    common_field_sensitivity,
)


def test_crossing_spec_contains_only_two_sigma175_even_chi64_cells(tmp_path):
    spec = build_crossing_spec(tmp_path)
    assert [(c["sigma"], c["L"], c["Gamma"], c["sector"], c["chi"])
            for c in spec["cells"]] == [
        (1.75, 128, 1.55, "even", 64),
        (1.75, 128, 1.60, "even", 64),
    ]
    assert spec["settings"]["adaptive_gamma"] is False
    assert spec["settings"]["K"] == 24


def test_common_field_records_power_and_log_without_model_selection():
    result = common_field_sensitivity(1.5679, 1.5620)
    assert result["primary"] == "power"
    assert result["power"]["residual_degrees_of_freedom"] == 0
    assert result["log"]["residual_degrees_of_freedom"] == 0
    assert result["gap_field"] == result["power"]["estimate"]
    assert result["propagated_to_gap_uncertainty"] is False


def test_gap_spec_is_six_chi128_states_only_after_resolved_crossing(tmp_path):
    decision = {
        "status": "resolved",
        "sigma": 1.75,
        "common_field": {"gap_field": 1.5609},
    }
    spec = build_gap_spec(decision, tmp_path)
    assert len(spec["cells"]) == 6
    assert {c["L"] for c in spec["cells"]} == {32, 64, 128}
    assert {c["sector"] for c in spec["cells"]} == {"even", "odd"}
    assert {c["chi"] for c in spec["cells"]} == {128}


def test_gap_spec_refuses_unresolved_crossing(tmp_path):
    with pytest.raises(ValueError, match="resolved"):
        build_gap_spec(
            {"status": "unresolved_no_L64_L128_bracket"},
            tmp_path,
        )
```

- [x] **Step 2: Run the protocol tests and verify RED**

Run:

```bash
PYTHONPATH=src:. conda run -n mps \
  pytest -q tests/test_phase8_protocol.py
```

Expected: import fails because `phase8_protocol.py` does not exist.

- [x] **Step 3: Implement the locked constants and specifications**

Create `phase8_protocol.py` with these immutable values:

```python
SIGMA = 1.75
ENDPOINTS = (1.55, 1.60)
SIZES = (32, 64, 128)
K = 24
CROSSING_CHI = 64
GAP_CHI = 128
ALPHA = 0.5
R_FIT = 2048
```

`build_crossing_spec()` must emit exactly the two cells asserted above.
`common_field_sensitivity()` must call
`two_point_sensitivity([x32, x64], [32, 64], form)` for both forms and record
`primary="power"`, `gap_field=power["estimate"]`, and
`propagated_to_gap_uncertainty=False`.

`build_gap_spec()` must reject any status other than `resolved` and emit the
Cartesian product `L=(32,64,128)` by `sector=(even,odd)` at one identical
Gamma.

- [x] **Step 4: Write failing CLI tests**

```python
def test_crossing_cli_writes_two_resumable_commands(tmp_path):
    output = tmp_path / "crossing" / "run_spec.json"
    completed = run_cli("crossing", "--output", str(output))
    assert completed.returncode == 0, completed.stderr
    spec = json.loads(output.read_text())
    assert len(spec["cells"]) == 2
    assert all("--chi-schedule" in c["command"] for c in spec["cells"])
    assert all(c["command"][c["command"].index("--chi-schedule") + 1] == "64"
               for c in spec["cells"])
    assert not list(tmp_path.rglob("*.h5"))


def test_decide_cli_records_unresolved_without_writing_gap_spec(tmp_path):
    # Write two synthetic successful summaries whose differences have one sign.
    completed = run_cli(
        "decide",
        "--crossing-spec", str(crossing_spec),
        "--phase7-decision", str(phase7_decision),
        "--summary-root", str(summary_root),
        "--output", str(decision_path),
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(decision_path.read_text())["status"].startswith("unresolved")
    assert not (tmp_path / "gaps/run_spec.json").exists()
```

- [x] **Step 5: Implement `plan_phase8_scaling.py`**

The CLI must:

- use atomic JSON writes;
- embed commands invoking `scripts/benchmark_phase6_optimizations.py`;
- use the existing sigma-specific fit summary;
- never include a Gamma outside `1.55,1.60` in `crossing`;
- load exactly the two Phase 8 L=128 summaries plus the two existing Phase 7
  L=64 summaries in `decide`;
- call `strict_endpoint_crossing`;
- write `status=resolved` plus both common-field sensitivities only after a
  strict sign change;
- make `gaps` refuse unresolved input.

Every crossing command has:

```text
--length 128 --num-exponentials 24 --alpha 0.5 --r-fit 2048
--chi-schedule 64 --direct-only --sectors even
```

Every gap command has:

```text
--num-exponentials 24 --alpha 0.5 --r-fit 2048
--chi-schedule 128 --direct-only --sectors <even|odd>
```

- [x] **Step 6: Run protocol and CLI tests**

Run:

```bash
PYTHONPATH=src:. conda run -n mps pytest -q \
  tests/test_phase8_scaling.py \
  tests/test_phase8_protocol.py \
  tests/test_phase8_planner_cli.py
```

Expected: all tests pass and no HDF5 file is created by planning tests.

- [x] **Step 7: Commit Task 2**

```bash
git add \
  tracks/mps/solutions/agent-of-my-agent-is-not-my-agent/src/lrtfim/phase8_protocol.py \
  tracks/mps/solutions/agent-of-my-agent-is-not-my-agent/scripts/plan_phase8_scaling.py \
  tracks/mps/solutions/agent-of-my-agent-is-not-my-agent/tests/test_phase8_protocol.py \
  tracks/mps/solutions/agent-of-my-agent-is-not-my-agent/tests/test_phase8_planner_cli.py
git commit -m "feat: gate phase8 sigma175 scaling cells"
```

---

### Task 3: Add the Phase 8 report assembler

**Files:**
- Create: `scripts/report_phase8_scaling.py`
- Create: `tests/test_phase8_report_cli.py`

**Interfaces:**
- Consumes:
  - resolved Phase 8 crossing decision;
  - six successful common-field summaries;
  - `results/phase6_sigma1.75/validated-local-reproduction/analysis.json`.
- Produces:
  - `crossings.csv`
  - `critical-field-sensitivity.csv`
  - `gap-diagnostics.csv`
  - `z-sensitivity.csv`
  - `equal-time-diagnostics.csv`
  - `uncertainty-budget.csv`
  - `analysis.json`
  - `phase8-sigma175.png` and `.pdf`
  - `report.md`

- [x] **Step 1: Write a failing fixture-based CLI test**

Build synthetic crossing/gap summaries under `tmp_path` and assert:

```python
def test_report_separates_effective_z_sensitivities_and_uncertainties(tmp_path):
    completed = run_report(fixture_root, output)
    assert completed.returncode == 0, completed.stderr
    analysis = json.loads((output / "analysis.json").read_text())
    assert set(analysis["z"]["z_eff"]) == {"32_64", "64_128"}
    assert analysis["z"]["sensitivity"]["power"][
        "interpretation"
    ] == "two_point_sensitivity_extrapolation"
    assert analysis["critical_field"][
        "propagated_to_gap_uncertainty"
    ] is False
    assert analysis["susceptibility_gamma_over_nu"] == "not_measured"
    assert set(analysis["uncertainty"]) == {
        "MPO", "MPS", "finite_size", "critical_field_propagation",
    }
    assert (output / "phase8-sigma175.png").stat().st_size > 0
```

- [x] **Step 2: Run the report test and verify RED**

Run:

```bash
PYTHONPATH=src:. conda run -n mps \
  pytest -q tests/test_phase8_report_cli.py
```

Expected: failure because `report_phase8_scaling.py` does not exist.

- [x] **Step 3: Implement strict input validation**

The report script must stop unless:

- decision status is `resolved`;
- sigma is exactly `1.75`;
- all six expected `(L,sector)` summaries exist and report success;
- every summary has `K=24`, `chi=128`, the same Gamma, and no approximate
  compression;
- both sectors pass relative variance, discarded-weight, and sweep-cap
  rules;
- all gaps are positive.

- [x] **Step 4: Implement tables and the report**

Use `gap_scaling_summary()` for z. Copy the previously measured maximum
`K=24` to `K=32` coupling/crossing/gap shifts and `chi=128` to `chi=256`
energy/gap/`R_xi` shifts from the Phase 6 analysis JSON rather than rerunning
them.

The figure has three colorblind-safe panels:

1. `Gamma_x(32,64)` and `Gamma_x(64,128)` against `1/L`, with the two-point
   power sensitivity line;
2. the two raw `z_eff` points plus separately marked power/log sensitivity
   values;
3. positive gaps versus L on log-log axes.

The report must say:

- `z_eff` values are two-size diagnostics;
- power/log values are two-point sensitivity extrapolations;
- the power/log `Gamma_c` spread is not fully propagated into gap
  uncertainty;
- `gamma/nu` susceptibility is not measured;
- equal-time `C_eq(r)` and `S_eq(0)` are auxiliary diagnostics only;
- the Phase 8 power/log sensitivity values are compared with the
  source-cited Shiratani--Todo `sigma=7/4` power/log extrapolations, while
  stating that the smaller `L<=128` range prevents a precision
  reproduction.

- [x] **Step 5: Run the report test and verify GREEN**

Run:

```bash
MPLCONFIGDIR=/tmp/mpl-phase8 PYTHONPATH=src:. conda run -n mps \
  pytest -q tests/test_phase8_report_cli.py
```

Expected: test passes with nonempty CSV, JSON, PNG, and PDF artifacts.

- [x] **Step 6: Commit Task 3**

```bash
git add \
  tracks/mps/solutions/agent-of-my-agent-is-not-my-agent/scripts/report_phase8_scaling.py \
  tracks/mps/solutions/agent-of-my-agent-is-not-my-agent/tests/test_phase8_report_cli.py
git commit -m "feat: report phase8 sigma175 scaling"
```

---

### Task 4: Verify implementation before compute

**Files:**
- Modify: `README.md`
- Modify: `docs/methodology.md`

**Interfaces:**
- Consumes: the implemented Phase 8 protocol.
- Produces: reproducible commands and corrected observable language.

- [ ] **Step 1: Update documentation**

Document:

- Phase 8 is sigma=1.75 first and finite-size focused;
- `chi=64` crossing justification is the measured `<4e-6` R_xi shift;
- final gaps use `chi=128`;
- power/log results are two-point sensitivity extrapolations;
- susceptibility `gamma/nu` is outside the DMRG scope;
- equal-time structure factors are diagnostics only.

- [ ] **Step 2: Run focused and full tests**

Run:

```bash
PYTHONPATH=src:. conda run -n mps pytest -q \
  tests/test_phase8_scaling.py \
  tests/test_phase8_protocol.py \
  tests/test_phase8_planner_cli.py \
  tests/test_phase8_report_cli.py
PYTHONPATH=src:. conda run -n mps pytest -q tests
```

Expected: focused tests and the complete project suite pass.

- [ ] **Step 3: Generate and inspect the two-cell crossing plan**

Run:

```bash
PYTHONPATH=src:. conda run -n mps python -u \
  scripts/plan_phase8_scaling.py crossing \
  --output results/phase8-scaling/sigma-1.75/crossing-L128/run_spec.json
```

Audit:

```bash
PYTHONPATH=src:. conda run -n mps python -c "
import json
p=json.load(open('results/phase8-scaling/sigma-1.75/crossing-L128/run_spec.json'))
assert len(p['cells']) == 2
assert {(c['L'],c['Gamma'],c['sector'],c['chi']) for c in p['cells']} == {
    (128,1.55,'even',64),(128,1.60,'even',64)}
print('phase8 crossing plan: PASS')
"
```

Expected: exactly two pending cells and no `L>128`, other sigma, or other
Gamma.

- [ ] **Step 4: Commit Task 4**

```bash
git add \
  tracks/mps/solutions/agent-of-my-agent-is-not-my-agent/README.md \
  tracks/mps/solutions/agent-of-my-agent-is-not-my-agent/docs/methodology.md
git commit -m "docs: document phase8 sigma175 scaling"
```

---

### Task 5: Execute and gate the sigma=1.75 L=128 crossing

**Files:**
- Generate:
  `results/phase8-scaling/sigma-1.75/crossing-L128/cells/*`
- Generate:
  `results/phase8-scaling/sigma-1.75/analysis/crossing-decision.json`

**Interfaces:**
- Consumes: Task 4 crossing run spec.
- Produces: two successful L=128 even summaries or an unresolved stop record.

- [ ] **Step 1: Reconfirm compute setup**

Before launching, surface:

```text
sigma=1.75; L=128; Gamma={1.55,1.60}; even parity;
K=24; chi=64; rotated physical Z=Sigmax; target R_xi.
```

Obtain explicit confirm-or-correct.

- [ ] **Step 2: Confirm the local cost gate**

Use the measured `L=64` timing and memory provenance to estimate the two
`L=128`, `chi=64` endpoint cells. Do not launch unless the projected wall
time is acceptable for the local campaign and the projected combined
resident memory is below 16 GiB. If either threshold is not satisfied,
report the estimate and stop for review.

- [ ] **Step 3: Execute only the two crossing commands**

Run each `cell["command"]` from the run specification with:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
PYTHONPATH=src:. conda run -n mps <cell command>
```

Use at most two concurrent processes under the confirmed memory estimate.
Preserve each cell log and do not delete a running or failed summary.

- [ ] **Step 4: Inspect convergence and update the measured cost**

Record for each endpoint:

- wall time and peak memory;
- energy, variance, relative variance, discarded weight;
- reached chi and sweeps;
- `S_eq(0)`, `S(k_min)`, `xi`, and `R_xi`.

If either cell fails, stop.

- [ ] **Step 5: Apply the strict crossing decision**

Run:

```bash
PYTHONPATH=src:. conda run -n mps python -u \
  scripts/plan_phase8_scaling.py decide \
  --crossing-spec results/phase8-scaling/sigma-1.75/crossing-L128/run_spec.json \
  --phase7-decision results/phase7-crossover/broad/decisions/sigma-1.75.json \
  --summary-root results/phase8-scaling/sigma-1.75/crossing-L128/cells \
  --output results/phase8-scaling/sigma-1.75/analysis/crossing-decision.json
```

If status is `unresolved_no_L64_L128_bracket`, report the two signed
differences and stop. Do not generate gaps.

- [ ] **Step 6: Review gate**

If resolved, report:

- both endpoint differences;
- `Gamma_x(32,64)` and `Gamma_x(64,128)`;
- `Gamma_c_power`, `Gamma_c_log`, and their spread;
- crossing-cell time, memory, and convergence.

Do not begin Task 6 until this sigma=1.75 crossing result is reviewed.

---

### Task 6: Execute common-field gaps and assemble sigma=1.75 results

**Files:**
- Generate:
  `results/phase8-scaling/sigma-1.75/gaps-common-Gamma/*`
- Generate:
  `results/phase8-scaling/sigma-1.75/analysis/*`

**Interfaces:**
- Consumes: a reviewed resolved crossing decision.
- Produces: six direct chi=128 states and the complete sigma=1.75 report.

- [ ] **Step 1: Generate the six-state gap plan**

Run:

```bash
PYTHONPATH=src:. conda run -n mps python -u \
  scripts/plan_phase8_scaling.py gaps \
  --decision results/phase8-scaling/sigma-1.75/analysis/crossing-decision.json \
  --output results/phase8-scaling/sigma-1.75/gaps-common-Gamma/run_spec.json
```

Audit one common Gamma, `L={32,64,128}`, sectors `{even,odd}`, `chi=128`.

- [ ] **Step 2: Reconfirm the gap setup**

Surface the resolved numeric `Gamma_c_power` and:

```text
sigma=1.75; L={32,64,128}; even and odd parity;
K=24; chi=128; target Delta=E_odd-E_even.
```

Obtain explicit confirm-or-correct before compute.

- [ ] **Step 3: Execute resumable gap cells**

Run smaller sizes first, then L=128. Bound concurrency so projected memory
stays below 16 GiB. Each cell uses existing audited initialization only when
all provenance fields match; otherwise initialize independently.

- [ ] **Step 4: Apply the numerical acceptance gate**

For all six states require:

```text
relative variance <= 1e-10
discarded weight <= 1e-8
sweeps < max_sweeps
reached chi recorded
```

Require all three gaps positive. Stop for review on failure; do not
automatically increase chi.

- [ ] **Step 5: Generate the final sigma=1.75 analysis**

Run:

```bash
MPLCONFIGDIR=/tmp/mpl-phase8 PYTHONPATH=src:. conda run -n mps python -u \
  scripts/report_phase8_scaling.py \
  --decision results/phase8-scaling/sigma-1.75/analysis/crossing-decision.json \
  --gap-root results/phase8-scaling/sigma-1.75/gaps-common-Gamma \
  --phase6-uncertainty results/phase6_sigma1.75/validated-local-reproduction/analysis.json \
  --output-dir results/phase8-scaling/sigma-1.75/analysis
```

- [ ] **Step 6: Verify artifacts and inspect plots**

Require every declared CSV/JSON/PNG/PDF/report artifact to be nonempty.
Visually inspect the figure. Run the full tests again and record the code
revision used by every compute cell.

- [ ] **Step 7: Stop before later sigma values**

Report the sigma=1.75 result and resource usage. Do not create or run
sigma=1.80 or sigma=2.00 plans until the user reviews and approves the
completed sigma=1.75 scaling analysis.
