# Attempt 01 ED Oracle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a deterministic `N=6`, `2Q=15` strict-LLL exact-diagonalization oracle for the lowest `L=0` state and the complete `L=2` multiplet, with raw and paper-comparable energy conventions in JSON.

**Architecture:** Construct LLL Coulomb matrix elements from an exact finite spherical-harmonic expansion evaluated by converged Gauss-Legendre/Fourier quadrature. Apply antisymmetrized two-body integrals in fixed-`M` Fock bases, build `L^2` from ladder operators, diagonalize the small dense sector matrices, and classify states by `L(L+1)`. Keep raw Hamiltonian eigenvalues immutable; background and density-shift conventions are derived report views.

**Tech Stack:** Python 3.13, NumPy, SciPy, pytest; no new packages.

---

### Task 1: Define the report conventions and schema

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/benchmark_v0/__init__.py`
- Create: `tracks/qmc/solutions/BOTS-848/benchmark_v0/conventions.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/conftest.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/test_conventions.py`

- [x] **Step 1: Write failing tests for the sphere corrections**

Test that `background_energy(6, 7.5) == -36/(2*sqrt(7.5))`, that the density factor is `sqrt(5/6)`, and that a common background cancels from the gap while density correction multiplies it.

Add a minimal `tests/conftest.py` that prepends the `BOTS-848` solution
directory to `sys.path`, because all declared pytest commands run from the
repository root while the importable `benchmark_v0` package lives beside the
tests.

- [x] **Step 2: Run the test and verify RED**

Run: `python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_conventions.py -q`

Expected: collection fails because `benchmark_v0.conventions` does not exist.

- [x] **Step 3: Implement minimal convention functions**

Implement:

```python
def background_energy(n_electrons: int, q: float) -> float:
    return -(n_electrons**2) / (2.0 * math.sqrt(q))

def density_shift_factor(n_electrons: int, two_q: int, filling: float) -> float:
    return math.sqrt(two_q * filling / n_electrons)
```

Add a function returning both `raw_lll` and `paper_convention` energy records without changing the raw inputs.

- [x] **Step 4: Run the test and verify GREEN**

Run the same pytest command. Expected: all tests pass.

### Task 2: Construct strict-LLL two-body Coulomb integrals

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/benchmark_v0/lll_coulomb.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/test_lll_coulomb.py`

- [x] **Step 1: Write failing tests for the LLL orbital and interaction invariants**

For `2Q=3`, test numerical orbital overlap against the identity, require two-body Hermiticity, require matrix elements that violate `m_a+m_b=m_c+m_d` to vanish, and require the antisymmetrized pair matrix to be Hermitian.

- [x] **Step 2: Run the test and verify RED**

Run: `python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_lll_coulomb.py -q`

Expected: import failure because `lll_coulomb.py` does not exist.

- [x] **Step 3: Implement the finite multipole construction**

Use normalized monopole LLL orbitals

```text
phi_m = (-1)^(Q-m) sqrt[(2Q+1)/(4 pi) binom(2Q,Q-m)]
        u^(Q+m) v^(Q-m)
```

on a Gauss-Legendre x uniform-phi grid. Expand the Coulomb kernel through `k=2Q`, the exact cutoff for products of LLL orbitals, and return unsymmetrized and antisymmetrized pair matrices in units `e^2/(epsilon l_B)`.

- [x] **Step 4: Run the tests and verify GREEN**

Run the same pytest command. Expected: all invariant tests pass at the declared tolerance.

### Task 3: Build fixed-M Fock bases, the Hamiltonian, and L-squared

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/benchmark_v0/fock_ed.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/test_fock_ed.py`

- [x] **Step 1: Write failing operator tests**

Test that the unrestricted `N=6`, `2Q=15` basis contains `binom(16,6)=8008` determinants, fixed-M bases contain only the requested M, fermion creation/annihilation phases match hand-computed two-orbital cases, and `L^2` has eigenvalues `L(L+1)` in the one-particle test system.

- [x] **Step 2: Run the test and verify RED**

Run: `python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_fock_ed.py -q`

Expected: import failure because `fock_ed.py` does not exist.

- [x] **Step 3: Implement the minimal operators**

Represent determinants as integer bitsets. Apply
`c_a^dagger c_b^dagger c_d c_c` with explicit parity counting, construct dense fixed-M Hamiltonians from antisymmetrized pair integrals, construct `L_+`, and use `L^2=L_-L_+ + M(M+1)`.

- [x] **Step 4: Run the tests and verify GREEN**

Run the same pytest command. Expected: all tests pass.

### Task 4: Diagonalize N=6 and emit a machine-readable oracle

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/benchmark_v0/ed_oracle.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/test_ed_oracle.py`
- Create: `tracks/qmc/solutions/BOTS-848/run_ed_oracle.py`

- [x] **Step 1: Write the failing end-to-end test**

Require the result to contain all `M=-2..2` entries, `L^2=6` within tolerance, a unique `L=0` ground state, negligible `[H,L^2]` residual, negligible fivefold splitting, raw and paper-convention outputs, zero ED statistical error, full runtime metadata, and explicit `lll_valid=true`.

- [x] **Step 2: Run the test and verify RED**

Run: `python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_ed_oracle.py -q`

Expected: import failure because `ed_oracle.py` does not exist.

- [x] **Step 3: Implement the oracle and CLI**

Diagonalize `M=-2,-1,0,1,2`; classify states by the expectation and variance of `L^2`; select the lowest `L=0` and `L=2` states; derive both energy conventions; write JSON to a caller-provided output path; print progress with flushing.

- [x] **Step 4: Run the full scoped suite**

Run: `python -m pytest tracks/qmc/solutions/BOTS-848/tests -q`

Expected: all Attempt 01 tests pass.

- [x] **Step 5: Run the N=6 oracle**

Run:

```text
python tracks/qmc/solutions/BOTS-848/run_ed_oracle.py \
  --output tracks/qmc/results/BOTS-848-benchmark-v0-attempt-01/run.json
```

Expected: exit 0 and a JSON report with all ED gates true.

### Task 5: Close the attempt with evidence

**Files:**
- Modify: `tracks/qmc/solutions/BOTS-848/logs/attempt-01.md`
- Modify: `tracks/qmc/solutions/BOTS-848/logs/README.md`

- [x] **Step 1: Record exact commands, commits, numerical result, and residuals**

- [x] **Step 2: Run fresh verification**

Run the scoped pytest suite, the CLI, JSON structural checks, `git diff --check`, and `git status --short`.

- [x] **Step 3: Commit implementation separately from the final journal**

Use one implementation commit and one journal-only commit so a failure journal can be integrated independently.
