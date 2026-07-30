# Phase 5 Long-Range MPO Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run the `L=8,10,12` three-layer validation of the fixed
`K=24` periodized long-range MPO.

**Architecture:** `lrtfim.validation` owns dense exact-pair construction,
spectral observables, translation averaging, and error records. A focused
command composes those routines with the existing exponential fit, MPO, and
shared DMRG workflow, writing each completed cell incrementally.

**Tech Stack:** Python 3.11, NumPy, SciPy, TeNPy 1.1.0, matplotlib, pytest.

## Global Constraints

- Use `sigma=1.75`, `K=24`, `alpha=0.5`, and `r_fit=2048`.
- Validate only `L=8,10,12` and `Gamma=1.2,1.56,2.0`.
- Compare exact pair ED, compact-MPO dense ED, and compact-MPO DMRG.
- Report absolute and relative `E0`, `E1`, and gap errors.
- Report translation-averaged periodic `C(r)`.
- Keep Frobenius error a small-system diagnostic; coupling error is primary.
- Do not run larger systems or locate a critical point.

---

### Task 1: Dense reference and observable utilities

**Files:**
- Create: `src/lrtfim/validation.py`
- Create: `tests/test_validation.py`

**Interfaces:**
- Produces: `exact_pair_hamiltonian(length, sigma, gamma) -> ndarray`
- Produces: `lowest_eigenpairs(matrix, count=2) -> (energies, vectors)`
- Produces: `translation_averaged_zz_statevector(vector, length) -> ndarray`
- Produces: `translation_averaged_zz_mps(psi) -> ndarray`
- Produces: `scalar_errors(reference, value) -> dict`

- [ ] Write tests that compare the exact dense Hamiltonian with direct Pauli
      products at `L=4`, verify periodic translation averaging by hand, and
      require both absolute/relative scalar errors with a `None` zero policy.
- [ ] Run `PYTHONPATH=src conda run -n mps python -m pytest
      tests/test_validation.py -q`; verify failure because
      `lrtfim.validation` is absent.
- [ ] Implement the five interfaces with exact Hurwitz-zeta couplings,
      `scipy.linalg.eigh(subset_by_index=...)`, and explicit wrapped-pair
      averaging for the MPS.
- [ ] Re-run the focused test and require all cases to pass.

### Task 2: One-cell three-layer validation

**Files:**
- Modify: `src/lrtfim/validation.py`
- Modify: `src/lrtfim/__init__.py`
- Modify: `tests/test_validation.py`

**Interfaces:**
- Produces: `validate_cell(length, sigma, gamma, fit, dmrg_options) -> dict`
- Consumes: `build_periodized_mpo`, `build_mpo_model`, and
  `run_ground_and_first_excited`.

- [ ] Add a reduced `L=4` test requiring all three layer records, relative
      Frobenius error, distance-resolved coupling errors, spectrum error
      separation, `C(r)` error separation, and DMRG diagnostics.
- [ ] Run the focused test and verify failure because `validate_cell` is
      absent.
- [ ] Implement one-cell validation, releasing unneeded dense arrays before
      DMRG and converting NumPy values to JSON-safe Python scalars.
- [ ] Re-run the focused test and the existing MPO/DMRG tests.

### Task 3: Incremental command and plots

**Files:**
- Create: `scripts/validate_long_range_mpo.py`
- Create: `tests/test_validate_long_range_mpo_cli.py`
- Modify: `scripts/README.md`
- Modify: `README.md`
- Modify: `docs/methodology.md`

**Interfaces:**
- Command defaults to the complete approved validation grid.
- Writes `summary.json`, `summary.csv`, per-cell JSON, coupling/correlation
  CSV profiles, `coupling_error.png`, and `observable_errors.png`.

- [ ] Add a CLI test using `L=4`, one Gamma, smaller `K/r_fit`, and reduced
      DMRG settings; require the complete output schema and both plots.
- [ ] Run the CLI test and verify failure because the command is absent.
- [ ] Implement deterministic fitting, per-cell incremental writes, flat
      tables, accessible plots, and progress lines with `flush=True`.
- [ ] Re-run the CLI test and full test suite.

### Task 4: Approved Phase 5 run and verification

**Files:**
- Update generated artifacts under: `results/phase5_mpo_validation/`
- Modify: `docs/phase5-mpo-validation-plan.md`

- [ ] Estimate the dense `L=12` peak memory and confirm it remains below
      16 GB and the local wall estimate remains below ten minutes.
- [ ] Run `PYTHONPATH=src conda run -n mps python
      scripts/validate_long_range_mpo.py --lengths 8 10 12
      --gammas 1.2 1.56 2.0 --sigma 1.75 --k 24 --alpha 0.5
      --r-fit 2048 --output-dir results/phase5_mpo_validation`.
- [ ] Inspect every cell for completion, positive gap, error-layer labels,
      translation-averaged correlation profiles, and DMRG diagnostics.
- [ ] Run `PYTHONPATH=src conda run -n mps python -m pytest -q` and report the
      exact pass/fail count without starting any larger calculation.
