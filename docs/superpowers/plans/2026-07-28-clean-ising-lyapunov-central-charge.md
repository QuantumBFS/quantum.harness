# Clean Ising Lyapunov Spectrum and Central Charge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compute the first four clean-transfer Lyapunov exponents at `L = 8, 10, 12, 16, 20`, independently validate the leading exponent by repeated normalized transfer, and extract the clean-Ising central charge with finite-size stability fits.

**Architecture:** Keep the exact transfer action in `clean_ising_transfer.py` unchanged. A separate analysis script imports that operator, obtains four leading positive eigenvalues with matrix-free Lanczos, identifies clean Lyapunov exponents as their logarithms, performs a k=1 QR/power check of the leading exponent, and linearly fits the transfer energy `epsilon_0 = -ell_1` to CFT finite-size forms.

**Tech Stack:** WSL Python 3.12.3, NumPy 1.26.4, SciPy 1.11.4, Matplotlib 3.6.3, standard-library `unittest`.

## Global Constraints

- Reuse the exact critical clean-Ising operator with periodic circumference and `K = ln(1 + sqrt(2))/2`.
- Required production widths are `8, 10, 12, 16, 20`.
- Store the four largest clean Lyapunov exponents as `ell_a = ln(lambda_a)`; do not introduce a random-bond or Born-sampled average in this phase.
- Independently estimate only `ell_1` by repeated transfer and scalar QR normalization; this check must not initialize from the Lanczos eigenvector.
- Fit the accurate Lanczos `epsilon_0 = -ell_1`, not the lower-accuracy QR estimate.
- The isotropic lattice uses anisotropy factor `alpha = 1`.
- Report deterministic finite-size model spread, not a Monte Carlo error bar.

---

### Task 1: Clean Lyapunov spectrum and independent leading check

**Files:**
- Create: `scripts/clean_ising_analysis.py`
- Create: `scripts/tests/test_clean_ising_analysis.py`

**Interfaces:**
- Consumes: `clean_ising_transfer.IsingTransferOperator`
- Produces: `clean_lyapunov_spectrum(L: int, count: int, tol: float) -> dict`
- Produces: `leading_lyapunov_iteration(L: int, steps: int, burn_in: int) -> dict`

- [ ] **Step 1: Write failing spectrum tests**

At `L = 4`, build the dense Boltzmann matrix independently in the test. Assert that the first four returned `lambda_a` match its four largest eigenvalues within `1e-11`, every exponent satisfies `ell_a = log(lambda_a)`, and each residual is below `1e-10`. Add a leading-iteration test requiring the normalized-transfer estimate to match `log(lambda_1)` within `1e-10` after a declared burn-in.

- [ ] **Step 2: Run RED**

```text
wsl.exe bash -lc "cd /mnt/c/Users/jinhong/Documents/summer-school/quantum.harness && python3 -m unittest scripts.tests.test_clean_ising_analysis -v"
```

Expected: clean failure because `scripts/clean_ising_analysis.py` is missing.

- [ ] **Step 3: Implement minimal spectrum and k=1 QR routines**

Use matrix-free `eigsh` with `which="LA"`, `count=4`, `ncv=16`, and a seeded non-spin-flip-symmetric random start so both Z2 sectors are accessible. Sort eigenpairs descending, require positive eigenvalues, and calculate one residual per vector. For the independent leading check, start from the normalized all-ones boundary vector, repeatedly apply `T`, record `log(norm(T q))` after burn-in, and average those increments.

- [ ] **Step 4: Run GREEN and commit**

Run the Step 2 command; expected all tests PASS. Then commit the new script and test.

### Task 2: Central-charge finite-size fit

**Files:**
- Modify: `scripts/clean_ising_analysis.py`
- Modify: `scripts/tests/test_clean_ising_analysis.py`

**Interfaces:**
- Produces: `fit_transfer_energy(L: ndarray, epsilon: ndarray, powers: tuple[int, ...], lmin: int) -> dict`
- Produces: `central_charge_summary(L: ndarray, epsilon: ndarray) -> dict`

- [ ] **Step 1: Write failing fit tests**

Generate literal synthetic values from

```text
epsilon(L) = -0.93 L - (pi * 0.5)/(6 L) - 0.15/L^3
```

and assert that `fit_transfer_energy(..., powers=(1, 3), lmin=8)` recovers `c = 0.5` within `1e-12`. Assert that the summary contains exactly the primary all-size `L^-1+L^-3`, drop-`L=8` stability, and all-size `L^-1+L^-3+L^-5` fits, plus the envelope midpoint and half-width.

- [ ] **Step 2: Run RED**

Run the full analysis test module. Expected: FAIL because the fit functions are missing.

- [ ] **Step 3: Implement minimal linear fits**

Fit columns `[L, L^-p for p in powers]` with `numpy.linalg.lstsq`. The coefficient of `1/L` is `B`, and `c = -6 B/pi`. Store coefficients, residual norm, selected widths, and `c`. Define the reported result as the midpoint and half-width of the three stability-fit central charges.

- [ ] **Step 4: Run GREEN and commit**

Run the full analysis tests and `python3 -m py_compile scripts/clean_ising_analysis.py`; expected PASS. Commit the fit implementation and tests.

### Task 3: Production calculation and verified artifacts

**Files:**
- Create: `results/clean_ising_transfer/lyapunov.csv`
- Create: `results/clean_ising_transfer/central_charge_fit.json`
- Create: `results/clean_ising_transfer/central_charge_fit.png`

**Interfaces:**
- Produces one spectrum row per circumference with `lambda_1..lambda_4`, `ell_1..ell_4`, residuals, QR `ell_1`, and QR discrepancy.
- Produces the three declared central-charge fits and their deterministic envelope.

- [ ] **Step 1: Add and test the production CLI**

The CLI accepts `--sizes`, `--count`, `--qr-steps`, `--qr-burn-in`, and `--output-dir`. It writes the spectrum CSV incrementally, then fits `epsilon_0 = -ell_1`, writes JSON, and plots `epsilon_0/L` against `1/L^2` with the primary fit curve and central-charge annotation.

- [ ] **Step 2: Run requested sizes**

```text
wsl.exe bash -lc "cd /mnt/c/Users/jinhong/Documents/summer-school/quantum.harness && python3 -u scripts/clean_ising_analysis.py --sizes 8 10 12 16 20 --count 4 --qr-steps 120 --qr-burn-in 40 --output-dir results/clean_ising_transfer"
```

- [ ] **Step 3: Verify independently**

Assert all five widths are present, all spectrum residuals are below `1e-10`, the recomputed leading eigenvalues match `values.csv`, and each QR `ell_1` differs from Lanczos `ell_1` by less than `1e-9`. Inspect the PNG and confirm that the primary curve, five raw points, and no statistical-error claim are present.

- [ ] **Step 4: Commit reproducible artifacts**

Force-add the ignored `results/` files only after fresh targeted tests and independent checks pass. Keep unrelated symlink changes untouched.
