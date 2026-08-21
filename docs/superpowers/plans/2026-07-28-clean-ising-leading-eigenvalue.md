# Clean Ising Leading Eigenvalue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compute the dominant eigenvalue of the exact matrix-free critical Ising row transfer operator for `L = 8, 10, 12, 16, 20` and save verified raw results without Lyapunov analysis or central-charge fitting.

**Architecture:** A focused Python script exposes a SciPy `LinearOperator` whose `matvec` evaluates `D^(1/2) (tensor_product_i v_i) D^(1/2)` on the complete `2^L` boundary vector. A symmetric Lanczos solve returns the leading eigenpair and residual. Small-width dense calculations exist only inside tests as an independent oracle.

**Tech Stack:** WSL Python 3.12.3, NumPy 1.26.4, SciPy 1.11.4, Matplotlib 3.6.3, standard-library `unittest`.

## Global Constraints

- Model: square-lattice ferromagnetic Ising model with `J = 1`, zero field, and `K_x = K_tau = ln(1 + sqrt(2))/2`.
- Geometry: circumference `L` has periodic boundary conditions; the transfer direction is represented by the dominant eigenvalue.
- Required widths: exactly `8, 10, 12, 16, 20` for the production run.
- The boundary vector contains all `2^L` amplitudes; no MPS, SVD, tensor truncation, disorder, or Monte Carlo sampling is permitted.
- Never materialize the production transfer matrix.
- This phase reports raw leading-eigenvalue data and a raw diagnostic plot only; it performs no Lyapunov calculation and no central-charge fit.
- Write progress after every width and write CSV rows incrementally.

---

### Task 1: Exact matrix-free transfer action

**Files:**
- Create: `scripts/clean_ising_transfer.py`
- Create: `scripts/tests/test_clean_ising_transfer.py`

**Interfaces:**
- Produces: `critical_coupling() -> float`
- Produces: `IsingTransferOperator(L: int, kx: float, ktau: float)` implementing SciPy `LinearOperator`
- Produces: `IsingTransferOperator._matvec(x: numpy.ndarray) -> numpy.ndarray`

- [ ] **Step 1: Write the failing transfer-action test**

The test enumerates `L = 4` configurations, constructs an independent dense matrix directly from the Boltzmann formula, and compares its action on a literal deterministic vector with the requested module's matrix-free action. If the module is absent, call `self.fail("scripts/clean_ising_transfer.py is missing")` so RED is a behavioral test failure rather than an import error.

- [ ] **Step 2: Run the test and verify RED**

Run:

```text
wsl.exe bash -lc "cd /mnt/c/Users/jinhong/Documents/summer-school/quantum.harness && python3 -m unittest scripts.tests.test_clean_ising_transfer.TransferActionTests -v"
```

Expected: FAIL with `scripts/clean_ising_transfer.py is missing`.

- [ ] **Step 3: Implement the minimal exact action**

Implement periodic row energies from bitwise domain-wall counts, precompute `D^(1/2)`, and alternate two full-size work arrays while applying each local matrix

```text
v = [[exp(ktau), exp(-ktau)],
     [exp(-ktau), exp(ktau)]]
```

to blocks of shape `(-1, 2, 2^i)`. Reject `L < 2` and vectors with a dimension other than `2^L`.

- [ ] **Step 4: Run the transfer-action test and verify GREEN**

Run the Step 2 command. Expected: PASS, with relative agreement tighter than `1e-12`.

- [ ] **Step 5: Commit Task 1**

```text
git add scripts/clean_ising_transfer.py scripts/tests/test_clean_ising_transfer.py
git commit -m "Add exact matrix-free Ising transfer action"
```

### Task 2: Dominant eigenvalue solver and result writer

**Files:**
- Modify: `scripts/clean_ising_transfer.py`
- Modify: `scripts/tests/test_clean_ising_transfer.py`

**Interfaces:**
- Consumes: `IsingTransferOperator`
- Produces: `dominant_eigenpair(L: int, kx: float, ktau: float, tol: float) -> dict`
- Produces: `run_sizes(sizes: list[int], output_dir: pathlib.Path, tol: float) -> list[dict]`
- Produces CSV columns: `L`, `dimension`, `lambda0`, `log_lambda0`, `reduced_free_energy`, `relative_residual`, `runtime_seconds`

- [ ] **Step 1: Write failing eigenpair and CLI tests**

Add one test comparing `dominant_eigenpair(L=4)` with the largest eigenvalue of the independently built dense oracle to relative tolerance `1e-11`, and require relative residual below `1e-10`. Add one integration test running sizes `4, 6` into a temporary directory and asserting that the CSV has exactly two rows, both dimensions are correct, all eigenvalues are positive, and the raw PNG exists.

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```text
wsl.exe bash -lc "cd /mnt/c/Users/jinhong/Documents/summer-school/quantum.harness && python3 -m unittest scripts.tests.test_clean_ising_transfer -v"
```

Expected: FAIL because `dominant_eigenpair` and `run_sizes` are missing.

- [ ] **Step 3: Implement the minimal solver and CLI**

Use `scipy.sparse.linalg.eigsh` with `k=1`, `which="LA"`, a normalized all-ones deterministic start vector, `ncv=12`, and the requested tolerance. Compute

```text
relative_residual = norm(T psi - lambda0 psi) / abs(lambda0)
reduced_free_energy = -log(lambda0) / L
```

Fail rather than write a row when the result is non-finite, non-positive, or the residual exceeds `10 * tol`. Write the CSV after each completed size. Generate a scatter-only PNG of reduced free energy against `1/L^2`; do not fit a line or report a central charge.

- [ ] **Step 4: Run the targeted tests and verify GREEN**

Run the Step 2 command. Expected: all tests PASS.

- [ ] **Step 5: Run the relevant repository tests**

Because WSL lacks pytest, run the new pure-`unittest` module directly. Record the missing pytest dependency rather than installing an unrequested package. Also run `python3 -m py_compile scripts/clean_ising_transfer.py`.

- [ ] **Step 6: Commit Task 2**

```text
git add scripts/clean_ising_transfer.py scripts/tests/test_clean_ising_transfer.py
git commit -m "Compute dominant clean Ising transfer eigenvalues"
```

### Task 3: Execute the requested widths and verify artifacts

**Files:**
- Create: `results/clean_ising_transfer/values.csv`
- Create: `results/clean_ising_transfer/leading_eigenvalues.png`

**Interfaces:**
- Consumes: `scripts/clean_ising_transfer.py --sizes 8 10 12 16 20`
- Produces: raw values and a no-fit diagnostic plot

- [ ] **Step 1: Run all requested widths in WSL**

Run:

```text
wsl.exe bash -lc "cd /mnt/c/Users/jinhong/Documents/summer-school/quantum.harness && python3 -u scripts/clean_ising_transfer.py --sizes 8 10 12 16 20 --output-dir results/clean_ising_transfer"
```

Expected: one flushed progress line per width and a zero exit status. If the `L=20` width exceeds the declared 10-minute local budget, stop and report rather than silently continuing.

- [ ] **Step 2: Verify the result table independently**

Read the CSV with a short Python command and assert:

```text
sizes == [8, 10, 12, 16, 20]
all(lambda0 > 0)
all(relative_residual < 1e-10)
all(log_lambda0 == log(lambda0) within floating tolerance)
```

- [ ] **Step 3: Inspect the raw plot and summarize**

Open the PNG, confirm all five points are present and axes state that no fit was performed. Report the five leading eigenvalues, residuals, runtimes, WSL rerun command, and artifact paths. Do not infer `c` yet.

- [ ] **Step 4: Commit the reproducible results**

```text
git add results/clean_ising_transfer/values.csv results/clean_ising_transfer/leading_eigenvalues.png
git commit -m "Record clean Ising leading transfer eigenvalues"
```
