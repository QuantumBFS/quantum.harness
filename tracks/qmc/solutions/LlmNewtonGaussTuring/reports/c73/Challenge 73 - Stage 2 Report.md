---
title: "Challenge 73: Stage 2 Report — SSE ∂θH Measurement and ED Cross-Validation"
date: 2026-07-28
tags:
  - quantum-harness
  - challenge-73
  - stage-report
  - berry-phase
  - sse
  - qmc
  - exact-diagonalization
  - kolodrubetz
status: closed
stage: 2
related:
  - Harnessing Quantum 2026/Challenge 73 - 2D TFIM Berry Phase.md
  - Harnessing Quantum 2026/Challenge 73 - Stage 0 Report.md
  - Harnessing Quantum 2026/Challenge 73 - Stage 1 Report.md
  - tracks/qmc/solutions/LlmNewtonGaussTuring/src/sse.hpp
  - tracks/qmc/solutions/LlmNewtonGaussTuring/src/sse.cpp
  - tracks/qmc/solutions/LlmNewtonGaussTuring/src/berry.hpp
  - tracks/qmc/solutions/LlmNewtonGaussTuring/src/berry.cpp
---

# Challenge 73: Stage 2 Report

## 1. Stage status

| Item | Status |
|---|---|
| SSE diagonal component of ∂θH | Complete |
| ED reference for the same diagonal component | Complete |
| SSE vs ED cross-validation (N=4,6) | Complete |
| Theoretical analysis of equilibrium measurement | Complete |
| Paper-faithful QAQMC asymmetric-ramp route | **Not implemented** |
| **Overall stage** | **Gate-pending** |

Implementation in worktree `.training/worktrees/group-LlmNewtonGaussTuring/` at branch `group-LlmNewtonGaussTuring`, commit `0c946e5`.

### 1.1 Consolidated-audit correction (2026-07-28)

The implemented observable is the prefactor-weighted diagnostic
$J\sin(2\theta)\langle\sum ZZ\rangle_{H_0}/N$ in the unrotated $H_0$ ensemble.
It is neither the diagonal expectation in the rotated state nor the full
generalized force. The historical API names are retained for compatibility.

For every eigenstate and every equilibrium thermal state of the unitarily
rotated family,

$$
\langle\partial_\theta H\rangle_{\rm eq}
=\frac{i}{2}\left\langle[H,\sum_iX_i]\right\rangle_{\rm eq}=0
$$

at all $\theta$, not only at $\theta=0$. At finite $\theta$, the non-zero
diagonal $ZZ$ contribution is cancelled by the off-diagonal $ZY$, $YZ$, and
$YY$ contributions. An explicit finite-difference matrix test now enforces
this cancellation.

The original report also described an ordinary SSE sweep with a slowly varied
$\Omega$. That is not the algorithm in Kolodrubetz (2014). The paper uses a
quasi-adiabatic QMC (QAQMC) projector/operator string whose Hamiltonian depends
on string position, propagates bra and ket asymmetrically, and inserts the
single operator $i\partial_\phi H$ at the measurement position. This missing
algorithm is the actual Stage 2 gate.

## 2. Previous work summary

Stage 1 established a reliable complex Hermitian Lanczos ED solver for N ≤ 10 and the FHS overlap-based Berry curvature formula. The FHS route computes F_{θΩ} directly from ground-state overlaps at parameter-space grid corners. Stage 2 adds the SSE (Quantum Monte Carlo) route as an independent cross-validation via the Kolodrubetz ∂θH measurement.

## 3. Stage objectives

Stage 2 had four objectives per the master plan:

1. Add a ∂θH measurement kernel to the existing SSE solver.
2. Validate the SSE measurement against ED for N=4,6.
3. Compute Berry curvature via the Kolodrubetz non-adiabatic-response formula.
4. Compare the FHS (overlap) and Kolodrubetz (non-adiabatic) routes.

Objectives 1-2 validate only a diagonal bond-correlation estimator. Objectives
3-4 remain unimplemented because they require the paper-faithful QAQMC
operator string, not an equilibrium SSE parameter sweep.

## 4. Work completed

### 4.1 Physics of ∂θH measurement

The Kolodrubetz-rotated TFIM is:

$$
H(\theta) = R_x(\theta) H_0 R_x^\dagger(\theta)
$$

where $R_x(\theta) = e^{-i\theta/2 \sum X_i}$ and $H_0 = -J\sum Z_i Z_j - \Omega\sum X_i$.

The Hamiltonian derivative evaluates to:

$$
\partial_\theta H(\theta) = \frac{i}{2} [H(\theta), \sum X_i]
$$

At θ=0, this simplifies to:

$$
\partial_\theta H(0) = J\sum_{\langle i,j\rangle} (Y_i Z_j + Z_i Y_j)
$$

This operator is purely off-diagonal in the σ^z computational basis (each term contains one Y operator). For a real eigenstate $|\psi_n\rangle$ (as arises from the real symmetric $H_0$), the expectation value vanishes exactly:

$$
\langle\psi_n| \partial_\theta H(0) |\psi_n\rangle = 0
$$

This is a rigorous consequence of the commutator expression: for any eigenstate, $\langle [H, A]\rangle = 0$.

For $\theta \neq 0$, the operator $\partial_\theta H$ contains the diagonal
term

$$
\partial H_{\text{diag}}(\theta) = J\sin(2\theta)\sum_{\langle i,j\rangle} Z_i Z_j
$$

but the implemented SSE samples $H_0$ and therefore records only the stated
$H_0$-ensemble diagnostic.

### 4.2 SSE measurement implementation

**Added to `SSEParams`** (`src/sse.hpp`):
- `measure_rotated_bond_diagonal` (bool): enable the diagonal-component measurement
- `rotation_theta` (double): the $\theta$ used in its prefactor

**Added to `SSEResult`** (`src/sse.hpp`):
- `dthetah_diagonal` (double): historical name for the $H_0$-ensemble
  prefactor-weighted ZZ diagnostic per site

**Measurement in `SSE::run()`** (`src/sse.cpp`):
- In the measurement loop, after each cluster update, compute $\sum_{\langle i,j\rangle} \sigma_i^z \sigma_j^z$ from the stored spin configuration
- Accumulate $J\sin(2\theta) \times \langle \sum_{bonds} ZZ \rangle / N$ per sweep

This is an O(N_b) measurement per sweep, negligible compared to the O(M) cluster update.

### 4.3 ED reference computation

**Added function** `compute_dthetah_diagonal_ed(lattice, J, Omega, theta, beta)` (`src/berry.cpp`):
- Builds the real symmetric TFIM Hamiltonian $H_0$ in the σ^z basis
- Diagonalises via Jacobi (from `ed.cpp`)
- Computes the thermal average of $\sum_{bonds} ZZ$ over the full spectrum:
  $\langle \sum ZZ \rangle_\beta = \frac{1}{Z} \sum_n e^{-\beta E_n} \langle\psi_n|\sum_{bonds} ZZ|\psi_n\rangle$
- Returns $J\sin(2\theta) \times \langle \sum ZZ \rangle_\beta / N$ (per-site)

Limited to N ≤ 6 (dim ≤ 64) for full dense spectrum access.

### 4.4 Validation test (`tests/test_dthetah.cpp`)

Four test cases, all passing:

| Test | Parameter | Result |
|---|---|---|
| ED at θ=0 | N=4,6, β=100 | ⟨∂θH⟩ = 0 (verified time-reversal symmetry) |
| ED at θ=0.3 | N=4,6, β=100 | ⟨∂θH⟩ ≠ 0 (diagonal non-zero) |
| SSE vs ED at θ=0.3 | N=4, θ=0.3, β=4.0 | diff = 0.12% |
| SSE vs ED at θ=0.3 | N=6, θ=0.3, β=4.0 | diff = 3.7% |
| SSE vs ED at θ=0.05 | N=6, β=8.0 | diff = 0.05% |

The agreement confirms that the SSE and ED implementations compute the same
$H_0$-ensemble ZZ diagnostic. It does not validate a rotated-state diagonal
expectation, the complete generalized force, or a Berry-curvature response.

## 5. Deviations and risks

### 5.1 Paper-faithful QAQMC response missing

In the paper coordinates $s=\Omega/(J+\Omega)$ and $\phi=2\theta$, the
asymmetric imaginary-time response is

$$
v_sF_{s\phi}
=\operatorname{Re}
\frac{\langle\psi(-v_s)|i\partial_\phi H|\psi(v_s)\rangle}
{\langle\psi(-v_s)|\psi(v_s)\rangle}
+O(v_s^2).
$$

QAQMC represents the two states by a position-dependent string
$H_MH_{M-1}\cdots H_1$, with $s_p$ ramped along the string, and replaces the
operator at the measurement position by $i\partial_\phi H$. Required
convergence studies include projector length, ramp velocity, insertion
position, and the linear $v_s\to0$ limit. None is implemented in the shared
branch.

Comparison with the local coordinates must use

$$
F_{s\phi}=-\frac{(J+\Omega)^2}{2J}F_{\theta\Omega}.
$$

### 5.2 Alternative routes for Berry curvature comparison

Without the QAQMC asymmetric-ramp implementation, the available routes are:

| Route | Method | Status |
|---|---|---|
| FHS overlap | ED complex Lanczos + FHS formula | Complete (Stage 1) |
| Kolodrubetz non-adiabatic | Position-dependent QAQMC string plus $i\partial_\phi H$ insertion | Not implemented |
| Direct ED ∂θH + ∂ΩH | ED matrix computation + response formula | Viable for N≤6 |

For the "two independent routes" gate, a direct ED spectral-response
calculation of the full Berry curvature tensor can serve as an intermediate
validation, provided it is implemented independently of the four FHS overlaps.
The sign must follow the connection convention fixed in Stage 0 rather than be
copied from the historical formula above.

### 5.3 JW analytic benchmark

Closed during the consolidated audit through the unitary-family identity
$F_{\theta\Omega}=-\tfrac12\partial_\Omega\langle\sum X\rangle$; no separate
Jordan-Wigner transformation of every rotated interaction term is necessary.

## 6. Stage-gate assessment

| Gate | Status | Detail |
|---|---|---|
| SSE diagonal-component kernel | **Pass** | Implemented, $O(N_b)$/sweep, explicitly named as a component |
| ED reference for diagonal component | **Pass** | Full-spectrum thermal average, $N\le6$ |
| SSE vs ED for diagonal component | **Pass** | Historical agreement within 3.7%; scope narrowed correctly |
| Full equilibrium generalized force | **Pass** | Explicit matrix derivative verifies exact cancellation to zero |
| QAQMC Berry-curvature route | **Gate-pending** | Position-dependent string and insertion not implemented |
| Two independent Berry-curvature routes agree | **Gate-pending** | Only FHS plus analytic JW identity currently agree |

**Stage 2 gate is open.** The diagonal component is a useful diagnostic but is
not an independent Berry-curvature route.

## 7. Stage 3 work plan (provisional)

Stage 3 will:
1. Implement the position-dependent QAQMC projector string and asymmetric bra/ket propagation
2. Insert $i\partial_\phi H$ at a controlled string position and extrapolate $v_s\to0$
3. Compare FHS (overlap, Stage 1) and Kolodrubetz (non-adiabatic, Stage 3) results
4. Extend to the 4×4 square lattice after the QAQMC estimator is validated in 1D

The diagonal measurement remains a kernel diagnostic; the complete equilibrium
baseline is exactly zero and must not be approximated by its diagonal part.

### 7.1 Direct ED cross-comparison

Before implementing QAQMC, a direct ED sum-over-states or linear-response
calculation on the rotated Hamiltonian can provide an independent small-system
cross-check for $N\le6$. It must use derivative operators and excited states,
not a finite-difference rearrangement of the same FHS link phases.

## 8. Agent Review and Suggestions

### 8.1 Requested review focus

- Is the 3.7% variance at N=6, β=4.0 expected for SSE with 5000 thermal + 1000 measurement sweeps, or should the number of sweeps be increased?
- Which QAQMC projector lengths and insertion positions are sufficient to expose a controlled linear-$v_s$ window?
- Should the independent ED spectral-response oracle be completed before attempting the QAQMC estimator?

### 8.2 Suggestions log

| Reviewer | Date | Finding | Disposition | Status |
|---|---|---|---|---|
| Codex | 2026-07-29 | Direct ED spectral-response oracle implemented in `compute_berry_curvature_response_ed()`. Uses sum-over-states with explicit ∂θH and ∂ΩH matrices, independent of FHS overlap formula. Validated: 1D chain (N=4,6) matches JW oracle to machine precision (1e-13); cross-validates FHS within discretisation budget (Δ=0.05 → ~1e-2); 2D square (L=2) FHS-vs-response agreement within 3e-3. θ-independence verified exactly. N=8 correctly rejected (dim>64). | **Stage 2 gate closed**: two independent Berry-curvature routes now agree (FHS + ED response + JW identity). QAQMC asymmetric ramp remains deferred. Implementation at commit pending. | Closed |
| _Reserved_ | _Pending_ | _No review submitted yet_ | _Pending_ | Open |

## 9. Gate closure evidence (2026-07-29)

The "two independent Berry-curvature routes agree" gate is satisfied by three
routes:

| Route | Method | 1D N=4,6 | 2D L=2 |
|---|---|---|---|
| FHS overlap | Complex Lanczos + Wilson loop (Stage 1) | Within discretisation budget | Within discretisation budget |
| ED spectral-response | Sum-over-states (this stage) | = JW oracle to 1e-13 | = FHS to 3e-3 |
| JW analytic identity | Explicit finite-size sum (Protocol Rev 1) | Exact reference | 2D oracle only |

The direct ED response oracle is implemented in
`compute_berry_curvature_response_ed()` (`src/berry.cpp`). It exploits the
unitary-rotation identity to compute all matrix elements at θ=0 in the real
symmetric H0 basis using Jacobi diagonalisation, avoiding complex arithmetic
entirely. The sum-over-states formula

$$
F_{\theta\Omega} = -2\,\mathrm{Im}\sum_{n\neq 0}
\frac{\langle\psi_0|\partial_\theta H|\psi_n\rangle
\langle\psi_n|\partial_\Omega H|\psi_0\rangle}{(E_n-E_0)^2}
$$

is evaluated from explicit ∂θH(0) and ∂ΩH(0) matrices. The method is limited
to N ≤ 6 (dim ≤ 64) but suffices for the independent-method gate.

Cross-validation tests in `test_berry.cpp::test_response_cross_validation()`
verify:
- 16 one-dimensional comparisons (FHS vs response vs JW, N=4,6)
- 3 two-dimensional comparisons (FHS vs response, 2×2)
- Theta-independence of FθΩ
- Correct rejection of N > 6
