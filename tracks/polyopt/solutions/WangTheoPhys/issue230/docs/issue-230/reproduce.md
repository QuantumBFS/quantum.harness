# Reproducing the Issue #230 certificates

## Environment

From `tracks/polyopt/solutions/WangTheoPhys/issue230`:

```bash
python3 -m venv .venv
.venv/bin/pip install -e . pytest
```

Python 3.11 or newer is required. Exact proof verification uses
`python-flint`; numerical candidate generation additionally uses NumPy, SciPy,
CVXPY, and CVXOPT.

## Fast implementation checks

```bash
.venv/bin/pytest -q --ignore=tests/test_published_outputs.py
```

These tests cover the Hamiltonian convention, Bethe intervals, LTI
relaxations, SU(2)/reflection reductions, rational repair, MPS contractions,
RG maps, matrix-free derivatives, U(1) charge blocks, schema rejection, and
CLI behavior.

## Individual proof verification

```bash
.venv/bin/xxzcert verify \
  outputs/final/xxx_best/level_47_rg_d6_mps_d32_block_1000.json
```

The level-47 payload contains an exact U(1)-blocked RG dual witness and a
1,000-site bond-32 rational MPS contraction. Its independent verification
takes tens of minutes. A lack of immediate terminal output is expected; a
successful command ends with `PASS`.

## Directory audit

```bash
.venv/bin/xxzcert audit outputs/final/xxx_best \
  --json outputs/final/audit.json
```

The audit re-verifies every selected proof before emitting endpoint errors,
widths, and monotonicity. Do not place `audit.json` inside a directory and then
audit the same directory recursively again; the audit file is a report, not a
level certificate.

## Full release check

```bash
/usr/bin/time -l .venv/bin/pytest -q
git diff --check
git status --short
```

The first command includes all published proof payloads and is intentionally
slow. Repository status should remain clean after the checks.

## Regenerating versus verifying

Verification is deterministic and requires only the JSON proof. Candidate
generation is a separate research computation and may depend on solver
versions and hardware. A regenerated floating-point objective is not expected
to be bit-identical and is not itself a certificate. Promotion requires
freezing its dual or variational data, exact repair, and another independent
verification run.
