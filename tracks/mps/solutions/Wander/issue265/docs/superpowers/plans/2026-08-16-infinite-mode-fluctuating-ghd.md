# Infinite-Mode Fluctuating GHD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a target-free finite-window spin structure factor from the complete non-diagonal fluctuating-GHD operator, or a machine-readable proof that the available UV and limit controls do not yet determine it uniquely.

**Architecture:** The finite-field GHD occupation space remains intact.  Linear non-spin modes are eliminated only by an exact Schur/Krylov resolvent; nonlinear velocity, diffusion, conservative-noise, cross, and observable diagrams are evaluated by Wick/Duhamel contractions.  Exact Heisenberg Mori moments through `mu20` are imposed by peeling and reinserting ten continued-fraction levels around a positive continuum terminator before any wall or Burgers projection is allowed.

**Tech Stack:** Python 3, NumPy, SciPy, pytest, JSON certificates.

## Global Constraints

- Do not read target Heisenberg trajectories or accept target `a,D` as inputs.
- Do not replace the orthogonal GHD spectrum by a prescribed second field or finite pole count.
- Retain the complete non-diagonal diffusion matrix and FDT noise covariance.
- Treat all finite-field, node, string, rapidity, Fourier, and matching choices as regulators with explicit convergence gates.
- A numerical survivor is only “not rejected in the declared domain,” never a mathematical proof.

---

### Task 1: Complete nonlinear full-mode Mori kernel

**Files:**
- Modify: `src/full_mode_analytic_certificates.py`
- Modify: `scripts/derive_full_mode_physical_one_loop.py`
- Test: `tests/test_full_mode_analytic_certificates.py`

**Interfaces:**
- Consumes: full matrices and Frechet tensors returned by `full_diffusion_operator_field` and `full_diffusion_noise_frechet_derivatives`.
- Produces: `one_loop_physical_spin_corrections(...)` with separately serialized velocity, diffusion, cross, multiplicative-noise-contact, mixed observable/dynamics, and total kernels.

- [ ] **Step 1: Write a failing FDT/full-matrix test**

```python
def test_physical_one_loop_retains_full_diffusion_noise_and_cross_terms():
    result = one_loop_physical_spin_corrections(...)
    assert result["full_off_diagonal_diffusion_retained"]
    assert result["full_fdt_noise_covariance_retained"]
    np.testing.assert_allclose(
        result["total_colored_force_memory"],
        result["velocity_force_memory"]
        + result["diffusion_force_memory"]
        + result["velocity_diffusion_cross_memory"],
    )
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python3 -m pytest tests/test_full_mode_analytic_certificates.py -q`

Expected: FAIL because the retention flags or complete assembled correction are absent.

- [ ] **Step 3: Add explicit diagram accounting**

Return the two retention flags, the colored-kernel sum, the white contact coefficient, and the mixed `Gamma H` correction.  Validate every tensor shape and reject a non-positive static susceptibility or inconsistent FDT root.

- [ ] **Step 4: Run focused tests**

Run: `python3 -m pytest tests/test_full_mode_analytic_certificates.py tests/test_full_mode_fluctuating_ghd.py -q`

Expected: PASS.

### Task 2: Match nonlinear hydrodynamic UV to exact Mori moments

**Files:**
- Create: `src/mori_moment_matching.py`
- Create: `scripts/derive_matched_infinite_mode_mori.py`
- Create: `tests/test_mori_moment_matching.py`

**Interfaces:**
- Consumes: exact `xxx_mori_long_wave_lanczos()` data, a low-frequency colored kernel sampled on a common time grid, its contact term, and declared matching/probe frequencies.
- Produces: `match_kernels_to_exact_lanczos(...) -> dict` containing exact moment intervals, positive continuum-terminator reconstructions, regulator variation, and `matching_complete`.

- [ ] **Step 1: Write failing moment-preservation tests**

```python
def test_matching_rejects_cutoff_drift():
    result = match_kernels_to_exact_lanczos(z, cutoff_kernels, spectral_frequencies=omega)
    assert not result["matching_complete"]

def test_continuum_terminator_preserves_exact_prefix():
    result = match_kernels_to_exact_lanczos(z, exact_candidates, spectral_frequencies=omega)
    assert result["exact_moment_order_preserved"] == 20
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python3 -m pytest tests/test_mori_moment_matching.py -q`

Expected: FAIL because the matching module does not exist.

- [ ] **Step 3: Implement fail-closed band matching**

Use compensated Laplace quadrature, peel the ten exact recurrents, and fit the residual terminator to a nonnegative normalized continuum measure.  Reinsert the fitted terminator through the exact prefix.  Set `matching_complete=true` only if every candidate lies inside the moment interval, every spectrum is nonnegative, the continuum reconstruction passes over the whole band, and the last regulator pair is stable.

- [ ] **Step 4: Run matching and regression tests**

Run: `python3 -m pytest tests/test_mori_moment_matching.py tests/test_heisenberg_burgers_bridge.py -q`

Expected: PASS.

### Task 3: Construct finite-window `F1_perp` and gate the Burgers projection

**Files:**
- Create: `scripts/derive_matched_full_mode_wall.py`
- Modify: `scripts/audit_finite_window_full_mode_wall_convergence.py`
- Modify: `docs/FIRST_PRINCIPLES_WINDOW_DERIVATION.md`
- Modify: `project_summary.md`
- Test: `tests/test_mori_moment_matching.py`

**Interfaces:**
- Consumes: a Task 2 certificate with `matching_complete`, the full linear structure factor, the matched nonlinear Duhamel correction, and the declared `50<t<200` window.
- Produces: normalized `S(k,t)/chi`, `F1`, the dilation-orthogonal `F1_perp`, a real-space wall, and frozen weak `(a,D)` only when all gates pass.

- [ ] **Step 1: Write a failing fail-closed projection test**

```python
def test_wall_projection_is_blocked_when_matching_is_incomplete(tmp_path):
    certificate = {"matching_complete": False}
    result = derive_matched_wall(certificate, t_start=50.0, t_stop=200.0)
    assert result["status"] == "blocked"
    assert "a" not in result and "D" not in result
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python3 -m pytest tests/test_mori_moment_matching.py -q`

Expected: FAIL because the wall constructor does not exist.

- [ ] **Step 3: Implement normalization and orthogonalization**

Enforce `S(0,t)=chi`, subtract the susceptibility and dilation directions from the one-loop correction, Fourier transform on nested `q` cutoffs, integrate the continuity equation once to form the wall, and apply the existing frozen weak estimator only after all matching and convergence flags pass.

- [ ] **Step 4: Run the complete verification suite**

Run: `python3 -m pytest -q`

Expected: all tests pass.  Run `python3 -m compileall -q src scripts hpc tests`; expected exit code 0.

- [ ] **Step 5: Record the scientific outcome**

Update the derivation and project summary with the actual gate result.  If the matching gate fails, state which frequency/cutoff causes it and retain `physical_F1_perp_certified=false`; do not quote a new microscopic `(a,D)`.
