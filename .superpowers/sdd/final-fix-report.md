# Challenge #194 Final Fix Report

## Scope

Applied the requested final Day-0 fix wave on branch `challenge/194` with no scope expansion.

## Root Cause

`ModelSpec` previously accepted positive finite `sigma` values so small that `1.0 + sigma` rounded back to exactly `1.0`. Downstream Hurwitz-zeta and reference-tail formulas assume exponent strictly greater than `1.0`, so that boundary admitted pole and division-by-zero behavior.

## RED -> GREEN

### RED tests added first

- `tests/test_model.py`
  - rejects a positive `sigma` with `1.0 + sigma == 1.0`
  - accepts `math.ulp(1.0)`, `0.8`, `1.0`, and `1.1`, and checks `periodic_kernel()` stays finite
  - adds direct invalid-input tests for `distance_classes()` and `canonical_edge()`
- `tests/test_kernel.py`
  - checks `kernel_weight_sum()` equals the multiplicity-weighted `periodic_kernel()` table
  - adds a regression proving the periodic-image kernel differs from bare minimum-image `r^-(1+sigma)` while matching the Hurwitz-zeta expression
- `tests/test_oracle.py`
  - checks oracle public symbols are exported from the package root and listed in `__all__`

### RED command

```bash
./.venv/bin/python -m pytest tests/test_model.py tests/test_kernel.py tests/test_oracle.py -q
```

Result:

```text
.F...........................                                            [100%]
=================================== FAILURES ===================================
___ test_model_spec_rejects_positive_sigma_when_one_plus_sigma_rounds_to_one ___

E       Failed: DID NOT RAISE <class 'ValueError'>

1 failed, 28 passed in 5.48s
```

### GREEN implementation

- Updated `src/long_range_percolation/model.py` to reject `sigma` unless:
  - `sigma` is finite
  - `sigma > 0.0`
  - `math.isfinite(1.0 + sigma)`
  - `(1.0 + sigma) > 1.0`
- Removed the unused `math` import from `src/long_range_percolation/kernel.py`

### GREEN command

```bash
./.venv/bin/python -m pytest tests/test_model.py tests/test_kernel.py tests/test_oracle.py -q
```

Result:

```text
.............................                                            [100%]
29 passed in 11.27s
```

## Full Verification

### Full suite

```bash
./.venv/bin/python -m pytest -q
```

Result:

```text
........................................................................ [100%]
72 passed in 40.84s
```

### Diff formatting

```bash
git diff --check
```

Result:

```text
[no output]
```

### Working tree artifact check before report/commit

```bash
git status --short
```

Result:

```text
 M tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/kernel.py
 M tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/model.py
 M tracks/qmc/solutions/frustration-free/challenge-194/tests/test_kernel.py
 M tracks/qmc/solutions/frustration-free/challenge-194/tests/test_model.py
 M tracks/qmc/solutions/frustration-free/challenge-194/tests/test_oracle.py
```

No unrelated untracked artifacts were produced by this fix wave.

## Files Changed

- `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/model.py`
- `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/kernel.py`
- `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_model.py`
- `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_kernel.py`
- `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_oracle.py`
- `.superpowers/sdd/final-fix-report.md`
