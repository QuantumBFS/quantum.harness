# Issue 147 Thermodynamic PEPO Compression Implementation Plan

> **For agents:** Use task-by-task execution with checkpoints. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fixed-bond PEPO compression layer that can run either ordinary Frobenius compression or the approved thermodynamic compression preserving `z = log(Z) / N`, internal-energy density `u`, and Hermiticity.

**Architecture:** A backend-neutral boundary contractor reduces PEPO traces, operator insertions, and double-layer overlaps to scalar 2D networks. A loss object compares a high-bond teacher with a fixed-bond student and exposes both the ordinary Frobenius objective and the thermodynamic composite objective. A JAX-backed optimizer uses the same seed, bond limit, contraction cutoff, environment dimension, iteration budget, and optimizer for fair ablations.

**Tech Stack:** Python 3.12, NumPy, autoray, quimb 1.14, JAX CPU, SciPy, pytest

---

## Global Constraints

- The physical convention is `H = -J sum_<ij> sigma_z(i) sigma_z(j) - h sum_i sigma_x(i)` on a finite open square lattice.
- The teacher is the temporary high-bond PEPO before compression; the student is a PEPO whose every virtual bond is at most `D`.
- The global relative Frobenius loss remains present in thermodynamic mode.
- Thermodynamic mode adds penalties for `z = log(Z) / N`, internal-energy density `u`, and Hermiticity.
- Specific heat `C` is not part of the first loss.
- QMC values are never accepted by the compression API and never enter training.
- Tolerances must be strictly larger than the declared boundary-contraction noise floor.
- Ordinary and thermodynamic modes differ only in loss terms; all compute-budget knobs are shared.
- Small exact tests use 1x1 and 2x2 systems. A later plan tunes tolerances on 4x4 ED, freezes them, then evaluates 10x10 against QMC.

## File Map

- `qh147/contract.py`: backend-neutral scalar networks, boundary contraction, overlaps, `z`, `u`, and Hermiticity residual.
- `qh147/compress.py`: loss configuration, diagnostics, fixed-bond seed, and JAX variational optimizer.
- `tests/test_contract.py`: exact dense contracts for traces, insertions, overlaps, and thermodynamic diagnostics.
- `tests/test_compress.py`: loss semantics, tolerance guard, fixed-D optimization, and fair-mode contracts.
- `pyproject.toml`: JAX runtime dependency.

### Task 1: Add Boundary Contraction and Thermodynamic Diagnostics

**Files:**
- Create: `tracks/peps/solutions/avi7ii/qh147/contract.py`
- Create: `tracks/peps/solutions/avi7ii/tests/test_contract.py`

- [ ] **Step 1: Write failing exact-contraction tests**

Add tests that require this public API:

```python
contractor = BoundaryContractor(chi=64, cutoff=1e-12)
contractor.trace(pepo)
contractor.expectation_numerator(pepo, {(x, y): operator})
contractor.overlap(bra, ket)
contractor.relative_frobenius_loss(student, teacher)
contractor.thermodynamic_point(pepo, j=1.0, h=3.0, log_scale=0.0)
contractor.hermiticity_residual(pepo)
```

Compare every scalar against `FinitePEPO.to_dense()` and `tfim_dense()` on identity and one Trotter step for 1x1 and 2x2. Assert `z`, `u`, and the Hermiticity residual, not only the partition function.

- [ ] **Step 2: Verify RED**

Run:

```powershell
& "C:\Users\c'c\Desktop\qh\.venv\Scripts\python.exe" -m pytest tests/test_contract.py -q
```

Expected: import failure for `qh147.contract`.

- [ ] **Step 3: Implement backend-neutral scalar networks**

Use `autoray.do` for trace, einsum, conjugation, real part, logarithm, and square root so the same code remains differentiable under JAX. Build one scalar tensor per lattice site, preserve `I{x},{y}` tags, view the result as `TensorNetwork2D`, and contract with:

```python
network.contract_boundary(
    max_bond=self.chi,
    cutoff=self.cutoff,
    canonize=True,
)
```

For an insertion `O`, reduce physical axes as `sum_{o,i} R[o,i,...] O[i,o]`. For overlaps, contract the bra and ket physical axes locally while keeping separately named bra and ket virtual indices.

Define:

```python
@dataclass(frozen=True)
class ThermodynamicPoint:
    z: object
    u: object
```

`thermodynamic_point` must sum all open-boundary bond and field insertions with the Hamiltonian convention above. Reject non-positive real partition functions only when converting diagnostics to Python floats; the differentiable path must not coerce traced values through NumPy.

- [ ] **Step 4: Verify GREEN and regression suite**

Run focused tests, then all tests. Expected: the new tests pass and the previous 21 tests remain green.

- [ ] **Step 5: Commit**

```bash
git add tracks/peps/solutions/avi7ii/qh147/contract.py tracks/peps/solutions/avi7ii/tests/test_contract.py
git commit -m "feat(pepo): add thermodynamic boundary contractions"
```

### Task 2: Define Ordinary and Thermodynamic Losses

**Files:**
- Create: `tracks/peps/solutions/avi7ii/qh147/compress.py`
- Create: `tracks/peps/solutions/avi7ii/tests/test_compress.py`

- [ ] **Step 1: Write failing loss tests**

Require these immutable configurations:

```python
ThermodynamicTolerances(z=1e-5, u=1e-4, contraction_noise=1e-7)
ThermodynamicWeights(z=1.0, u=1.0, hermiticity=1.0)
CompressionObjective(contractor, j=1.0, h=3.0, tolerances=..., weights=...)
```

Test that ordinary mode equals relative Frobenius loss exactly. Test that thermodynamic mode equals:

```text
L_F + lambda_z ((z_s-z_t)/epsilon_z)^2
    + lambda_u ((u_s-u_t)/epsilon_u)^2
    + lambda_H L_H
```

Test that `epsilon_z <= contraction_noise` or `epsilon_u <= contraction_noise` raises `ValueError`. Test that the API has no `C`, QMC, or reference-data input.

- [ ] **Step 2: Verify RED**

Run `pytest tests/test_compress.py -q`. Expected: import failure for `qh147.compress`.

- [ ] **Step 3: Implement immutable loss configuration and diagnostics**

Define a `CompressionDiagnostics` dataclass containing total, Frobenius, scaled `z` penalty, scaled `u` penalty, Hermiticity penalty, and the unscaled `z` and `u` differences. Keep scalar values backend-native in the loss path. Provide a separate `as_floats()` conversion for reports and tests.

The objective must compute teacher `z` and `u` once per `compress()` call and pass them as optimizer constants. `mode="ordinary"` must zero only the three extra terms; it must not change any optimizer or contraction setting.

- [ ] **Step 4: Verify GREEN and regression suite**

Run focused tests, then all tests. Expected: all pass without warnings.

- [ ] **Step 5: Commit**

```bash
git add tracks/peps/solutions/avi7ii/qh147/compress.py tracks/peps/solutions/avi7ii/tests/test_compress.py
git commit -m "feat(pepo): define thermodynamic compression loss"
```

### Task 3: Add Fixed-Bond JAX Variational Compression

**Files:**
- Modify: `tracks/peps/solutions/avi7ii/pyproject.toml`
- Modify: `tracks/peps/solutions/avi7ii/qh147/compress.py`
- Modify: `tracks/peps/solutions/avi7ii/tests/test_compress.py`

- [ ] **Step 1: Install the declared JAX dependency**

Add `jax>=0.4` to project dependencies and install CPU JAX into the existing Windows environment with the repository's `make install jax EXTRA=cpu` target or equivalent `uv pip install --python .venv/Scripts/python.exe jax` command.

- [ ] **Step 2: Write failing optimizer tests**

Create a one-step teacher PEPO, locally compress a copy to the requested bond dimension, then require:

```python
result = VariationalCompressor(objective, max_iterations=20).compress(
    teacher,
    max_bond=1,
    mode="thermodynamic",
)
```

Assert the maximum virtual bond is at most one, the total loss does not increase, diagnostics are finite, and result metadata records the mode and shared budget. Run the same seed in ordinary mode and assert both results record identical `chi`, cutoff, maximum iterations, and optimizer name.

- [ ] **Step 3: Verify RED**

Run the focused optimizer tests. Expected: `VariationalCompressor` is missing.

- [ ] **Step 4: Implement the fixed-bond optimizer**

Create the student by copying the teacher and calling `compress_all_(max_bond=max_bond, cutoff=0.0)`. Reject a seed whose remaining virtual bond exceeds the requested limit. Optimize only student tensors with `quimb.tensor.TNOptimizer`, `autodiff_backend="jax"`, and `optimizer="L-BFGS-B"`. Cache teacher diagnostics outside the differentiated student loss.

Return an immutable `CompressionResult` with the PEPO, initial/final diagnostics, iteration count, loss history, maximum bond, mode, and a frozen budget record. Do not accept target observables from outside the teacher PEPO.

- [ ] **Step 5: Verify GREEN and full suite**

Run:

```powershell
& "C:\Users\c'c\Desktop\qh\.venv\Scripts\python.exe" -m pytest tests -q
```

Expected: all tests pass. Also run a 2x2 one-step smoke comparison and print ordinary versus thermodynamic `Delta z`, `Delta u`, wall time, and maximum bond. This is a functionality smoke test, not the 4x4 tolerance calibration or 10x10 QMC result.

- [ ] **Step 6: Commit**

```bash
git add tracks/peps/solutions/avi7ii/pyproject.toml tracks/peps/solutions/avi7ii/qh147/compress.py tracks/peps/solutions/avi7ii/tests/test_compress.py
git commit -m "feat(pepo): add fixed-bond thermodynamic compressor"
```

## Completion Gate

- Every new behavior followed a red-green TDD cycle.
- Full local suite passes.
- A task review approved each task and a final whole-branch review found no load-bearing issue.
- The branch contains no 10x10 output and no QMC-trained value.
- The implementation is merged back to local `main`; pushing remains a separate user decision.
