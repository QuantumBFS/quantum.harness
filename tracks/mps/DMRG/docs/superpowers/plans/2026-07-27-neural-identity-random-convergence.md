# Neural Identity Random Convergence Implementation Plan

> **Issue #28 N1 integration (2026-07-28).** The random-start identity test is
> now implemented by `scripts/issue28_identity.py` with the frozen literal
> Robbins-Monro protocol, independent monitoring/final streams, exact-zero
> 13-operator branch, atomic neural checkpoints, three locked formal identity
> bundles, and explicit gradient-estimator failure classification. This older
> plan remains the provenance record for the original N1.1 design.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the locked N1.1 entry point that tests whether pure-neural identity-RG VMCRG can converge from random initialization under the preregistered Robbins-Monro pilot protocol.

**Architecture:** Reuse the existing `train`, `validate`, and `project` stages from `scripts/neural_challenge.py`; the new script owns only the identity-RG protocol, independent seeds, and a compact convergence report. `reproduce.py` remains the sole user-facing command and continues to run deterministic tests before experiments.

**Tech Stack:** Python 3.10+, NumPy, `argparse`, `unittest`, existing `vmcrg_ref` implementation.

## Global Constraints

- The pilot system is the periodic 15x15 two-dimensional Ising model with identity RG (`block_size=1`).
- The microscopic Hamiltonian is the existing published 13-even-operator linear fixed-point map.
- The learned bias is a pure radius-3, hidden-32, D4/Z2/translation-symmetric multiscale neural energy; the fixed 13-operator bias must remain exactly zero.
- Pilot training is locked to 8 walkers, 1000 updates, 5 sweeps per gradient block, 2 accumulated gradient blocks, 32 target samples, learning rate 0.02, decay scale 250, decay power 0.75, and Polyak averaging from update 500.
- Model, optimizer, frozen-validation, and projection random streams must be pairwise distinct.
- Acceptance requires frozen-distribution `PASS`, 13-term projection `PASS`, fixed-linear-bias L-infinity norm exactly zero, projection L-infinity residual at most 0.001, and relative L2 residual at most 0.005.
- Existing thresholds, architectures, fixed-point data, and result directories must not be changed or overwritten.
- N1.1 may run locally in smoke mode; the 80000-walker-sweep pilot is routed to Slurm after explicit setup ratification.

---

### Task 1: Lock the random-convergence contract

**Files:**
- Create: `tests/test_neural_identity_random_convergence.py`
- Produces: executable contract for `PROTOCOLS`, `validate_seeds`, `run`, and the `neural-identity-random` CLI.

- [ ] **Step 1: Write the failing protocol and CLI tests**

```python
from pathlib import Path
import unittest

import reproduce
from scripts.neural_identity_random_convergence import PROTOCOLS, validate_seeds


class NeuralIdentityRandomConvergenceTests(unittest.TestCase):
    def test_pilot_protocol_matches_preregistered_budget(self) -> None:
        protocol = PROTOCOLS["pilot"]
        self.assertEqual(
            protocol["training"],
            {"walkers": 8, "steps": 1000, "sweeps": 5, "targets": 32},
        )
        self.assertEqual(protocol["gradient_accumulation_steps"], 2)
        self.assertEqual(protocol["learning_rate"], 0.02)
        self.assertEqual(protocol["decay_scale"], 250.0)
        self.assertEqual(protocol["decay_power"], 0.75)

    def test_seed_streams_must_be_independent(self) -> None:
        with self.assertRaisesRegex(ValueError, "pairwise distinct"):
            validate_seeds(11, 12, 11, 14)

    def test_unified_entry_exposes_random_identity_pilot(self) -> None:
        args = reproduce.build_parser().parse_args(
            ["neural-identity-random", "--preset", "pilot", "--dry-run"]
        )
        self.assertEqual(args.handler, reproduce._neural_identity_random)
        self.assertEqual(args.preset, "pilot")
        self.assertEqual(
            args.fixed_point_map,
            Path("output/reproduction/fixed_point_newton_v2/corrected_rg_v3/summary.json"),
        )
```

- [ ] **Step 2: Run the new test and verify RED**

Run: `PYTHONPATH=src python -m unittest tests.test_neural_identity_random_convergence -v`

Expected: import failure because `scripts.neural_identity_random_convergence` does not exist.

### Task 2: Implement the locked experiment and unified entry

**Files:**
- Create: `scripts/neural_identity_random_convergence.py`
- Modify: `reproduce.py`
- Test: `tests/test_neural_identity_random_convergence.py`

**Interfaces:**
- Consumes: `scripts.neural_challenge.train`, `validate`, `project`, `read_json`, and `write_json`.
- Produces: `validate_seeds(*seeds: int) -> None`, `run(...) -> dict`, `random_convergence_report.json`, and CLI command `neural-identity-random`.

- [ ] **Step 1: Implement the minimal protocol runner**

```python
PROTOCOLS = {
    "smoke": {
        "training": dict(walkers=4, steps=5, sweeps=1, targets=8),
        "gradient_accumulation_steps": 2,
        "learning_rate": 0.02,
        "decay_scale": 2.0,
        "decay_power": 0.75,
    },
    "pilot": {
        "training": dict(walkers=8, steps=1000, sweeps=5, targets=32),
        "gradient_accumulation_steps": 2,
        "learning_rate": 0.02,
        "decay_scale": 250.0,
        "decay_power": 0.75,
    },
}


def validate_seeds(*seeds: int) -> None:
    if len(seeds) != len(set(seeds)):
        raise ValueError("model, optimizer, validation, and projection seeds must be pairwise distinct")
```

`run` calls `train` with `representation="pure"`, `block_size=1`, `length_override=15`, `optimizer_name="robbins_monro_sgd"`, no `initial_model_path`, and the locked schedule. It then calls independent `validate` and `project` stages with `enforce_formal_gate=False`, verifies the fixed linear bias is exactly zero, and writes `random_convergence_report.json`.

- [ ] **Step 2: Register the unified command**

Add `_neural_identity_random(args)` next to `_neural_optimizer_stability`, refuse to overwrite `random_convergence_report.json`, run the deterministic test suite first, and invoke the new script with all four seed arguments. Register:

```python
neural_identity_random = subparsers.add_parser(
    "neural-identity-random",
    help="test Robbins-Monro identity-RG convergence from random initialization",
)
neural_identity_random.add_argument(
    "--preset", choices=("smoke", "pilot"), required=True
)
```

Use default output `output/neural_identity_random_<preset>_v1` and distinct default seeds `202607301` through `202607304`.

- [ ] **Step 3: Run the focused tests and verify GREEN**

Run: `PYTHONPATH=src python -m unittest tests.test_neural_identity_random_convergence -v`

Expected: all focused tests pass.

### Task 3: Exercise real smoke behavior and protect the report contract

**Files:**
- Modify: `tests/test_neural_identity_random_convergence.py`
- Test: `scripts/neural_identity_random_convergence.py`

**Interfaces:**
- Consumes: `run(...) -> dict` from Task 2 and the checked-in fixed-point map.
- Produces: a smoke integration test proving random initialization, zero linear bias, independent evaluation streams, and output artifacts.

- [ ] **Step 1: Add a failing smoke integration test**

Use `tempfile.TemporaryDirectory`, call `run(preset="smoke", ...)` with four literal distinct seeds and the checked-in fixed-point map, then assert:

```python
self.assertEqual(report["experiment"], "identity_rg_random_initialization_convergence")
self.assertEqual(report["scope"], "single_seed_gate_not_formal_or_multiseed_confirmation")
self.assertEqual(report["model_initialization"], "random")
self.assertEqual(report["fixed_linear_bias_linf"], 0.0)
self.assertEqual(report["total_walker_sweeps"], 40)
self.assertTrue((output / "bias_model.npz").is_file())
self.assertTrue((output / "random_convergence_report.json").is_file())
```

The test deliberately does not require a stochastic five-update smoke run to pass the scientific convergence thresholds.

- [ ] **Step 2: Run the integration test and verify RED**

Run: `PYTHONPATH=src python -m unittest tests.test_neural_identity_random_convergence.NeuralIdentityRandomConvergenceTests.test_smoke_run_records_random_zero_bias_contract -v`

Expected: failure on a missing or incomplete report field.

- [ ] **Step 3: Complete the report fields and verify GREEN**

Run the same focused command. Expected: PASS with all artifacts present.

### Task 4: Verify N1.1 and update the durable roadmap

**Files:**
- Modify: `PROJECT_STATUS_AND_ROADMAP.md`
- Test: all deterministic tests and CLI dry-run.

**Interfaces:**
- Consumes: the completed CLI and tests.
- Produces: an accurate roadmap that marks N1.1 implemented while leaving N1.2 unexecuted.

- [ ] **Step 1: Run all deterministic tests**

Run: `python reproduce.py test`

Expected: all tests pass with no warnings or tracebacks.

- [ ] **Step 2: Verify the exact pilot command without starting compute**

Run: `python reproduce.py neural-identity-random --preset pilot --dry-run`

Expected: tests plus a command targeting `scripts/neural_identity_random_convergence.py`, preset `pilot`, the fixed-point map, output `output/neural_identity_random_pilot_v1`, and four distinct seeds. No output directory is created.

- [ ] **Step 3: Update status without claiming a result**

Mark N1.1 as implemented and set the unique next step to the remote 1000-update pilot. Keep random-initialization convergence as `未执行`; do not record a `PASS` or `FAIL` before the pilot exists.

- [ ] **Step 4: Review the diff**

Run: `git diff -- scripts/neural_identity_random_convergence.py tests/test_neural_identity_random_convergence.py reproduce.py PROJECT_STATUS_AND_ROADMAP.md docs/superpowers/plans/2026-07-27-neural-identity-random-convergence.md`

Expected: only N1.1 implementation, tests, and the matching roadmap update.
