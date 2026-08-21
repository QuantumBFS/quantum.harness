---
title: "Challenge 73: Stage 0 Report — FHS Formula Validation and Protocol"
date: 2026-07-28
tags:
  - quantum-harness
  - challenge-73
  - stage-report
  - berry-phase
  - berry-curvature
  - fhs-formula
  - kolodrubetz-rotation
status: complete
stage: 0
related:
  - Harnessing Quantum 2026/Challenge 73 - 2D TFIM Berry Phase.md
  - Harnessing Quantum 2026/Challenge 73 - Stage 0 Preregistration.md
  - tracks/qmc/solutions/LlmNewtonGaussTuring/src/berry.hpp
  - tracks/qmc/solutions/LlmNewtonGaussTuring/src/berry.cpp
---

# Challenge 73: Stage 0 Report

## 1. Stage status

| Item | Status |
|---|---|
| FHS formula numerical validation (1D N=2, N=4, N=6) | Complete |
| FHS gauge invariance confirmed | Complete |
| 2D square 2×2 Berry curvature computed | Complete |
| 1D finite-size convergence verified | Complete |
| Primary-source and 2017 review audit via MinerU | Complete |
| JW analytic benchmark | Complete |
| Parameterisation/protocol freeze | Complete |
| **Overall stage** | **Complete after consolidated-audit repair** |

The historical implementation began at commit `25d6e6c`; the corrected code is
in the shared `group-LlmNewtonGaussTuring` branch.

### 1.1 Consolidated-audit closure (2026-07-28)

The historical Stage 0/1 code contained two compensating sign errors and one
normalisation error: the $ZY/YZ$ matrix elements had the opposite sign from the
declared unitary rotation, the Wilson-loop phase was interpreted with the wrong
sign, and the plaquette flux was labelled as a local curvature without division
by its oriented area. The parameter grid also passed $\theta$ and $\Omega$ in
the opposite order. Consequently, every numerical curvature quoted later in
this historical report is superseded.

The repaired implementation is pinned by an explicit matrix identity,

$$
H(\theta,\Omega)=R_x(\theta)H(0,\Omega)R_x^\dagger(\theta),
\qquad
R_x(\theta)=e^{-i\theta\sum_iX_i/2},
$$

and by independent FHS, magnetisation-response, and Jordan-Wigner tests.

For $|\psi(\theta,\Omega)\rangle=R_x(\theta)|\psi(0,\Omega)\rangle$ and
$A_\mu=i\langle\psi|\partial_\mu\psi\rangle$,

$$
A_\theta=\frac12\left\langle\sum_iX_i\right\rangle,
\qquad
F_{\theta\Omega}=-\frac12\partial_\Omega
\left\langle\sum_iX_i\right\rangle.
$$

The one-dimensional ground-state energy density is

$$
e_0=-\frac1\pi\int_0^\pi\varepsilon_k\,dk,
\qquad
\varepsilon_k=\sqrt{J^2+\Omega^2-2J\Omega\cos k}.
$$

Hellmann-Feynman gives

$$
\frac1N\left\langle\sum_iX_i\right\rangle
=-\partial_\Omega e_0
=\frac1\pi\int_0^\pi
\frac{\Omega-J\cos k}{\varepsilon_k}\,dk.
$$

Differentiating once more closes the Stage 0 analytic gate:

$$
\boxed{
\frac{F_{\theta\Omega}}{N}
=-\frac{J^2}{2\pi}\int_0^\pi
\frac{\sin^2k}{(J^2+\Omega^2-2J\Omega\cos k)^{3/2}}\,dk
}.
$$

The density is negative in this convention, independent of $\theta$, and has a
logarithmic divergence at $|\Omega|=J$ in one dimension. The adaptive-Simpson
oracle in `src/berry.cpp` is checked against finite-chain FHS data and the
large-field limit $F/N\sim-J^2/(4|\Omega|^3)$.

Kolodrubetz uses $\phi=2\theta$ and
$s=\Omega/(J+\Omega)$. The two-form Jacobian is

$$
F_{s\phi}
=F_{\theta\Omega}
\left(
\frac{\partial\theta}{\partial s}\frac{\partial\Omega}{\partial\phi}
-\frac{\partial\theta}{\partial\phi}\frac{\partial\Omega}{\partial s}
\right)
=-\frac{(J+\Omega)^2}{2J}F_{\theta\Omega}.
$$

This Jacobian is required before comparing the local implementation with the
paper's plotted $F_{s\phi}$.

## 2. Previous work summary

Before Stage 0 began, the master research plan (`Challenge 73 - 2D TFIM Berry Phase.md`) established the target Hamiltonian, parameterisation (Kolodrubetz x-axis rotation + Rydberg laser phase), FHS gauge-invariant discretisation formula, and a multi-route validation strategy (ED oracle → SSE/QMC → PEPS). The infrastructure (lattice module, ED oracle, SSE solver) from Challenge 148 was available for reuse.

## 3. Stage objective

Stage 0 had four objectives:
1. construct the Kolodrubetz-rotated TFIM Hamiltonian and compute the Berry curvature via the Fukui-Hatsugai-Suzuki (FHS) discretised overlap formula;
2. validate against the 1D Jordan-Wigner exact solution;
3. audit post-2014 Berry curvature TFIM literature;
4. freeze the parameterisation, grid convention, and cross-validation protocol.

## 4. Work completed

### 4.1 Kolodrubetz rotation axis discovery

A critical finding: the Kolodrubetz (2014) rotation is about the **x-axis** ($R_x(\theta) = e^{-i\theta/2 \sum X_i}$), not the y-axis. This was verified by observing that a y-axis rotation produces a real symmetric Hamiltonian ($\sigma^y$-to-$\sigma^y$ mapping), whose ground state is real and whose Berry curvature is identically zero. The x-axis rotation introduces complex $\sigma^y$ matrix elements:
$$
Z \to \cos\theta\,Z - \sin\theta\,Y, \qquad Y \to \sin\theta\,Z + \cos\theta\,Y, \qquad X \to X
$$
generating a complex Hermitian Hamiltonian with non-zero Berry curvature.

### 4.2 Complex Hamiltonian builder (`src/berry.cpp`)

A dense matrix builder constructs $H(\theta,\Omega)$ in the $\sigma^z$ basis for the x-axis Kolodrubetz rotation:
$$
H(\theta,\Omega) = -J\sum_{\langle ij\rangle}\big[c^2 Z_iZ_j - cs(Z_iY_j+Y_iZ_j) + s^2 Y_iY_j\big] - \Omega\sum_i X_i
$$
where $c=\cos\theta$, $s=\sin\theta$. The $Y_iY_j$ and $Z_iY_j$ terms contribute real and complex off-diagonal matrix elements respectively, stored as `std::complex<double>`.

### 4.3 Krylov-subspace ground-state solver

A complex Lanczos-like Krylov-subspace solver computes the ground state for $N\le 8$ ($\dim\le 256$):
- Build a $K$-dimensional Krylov basis $\{H^k|\psi_0\rangle\}_{k=0}^{K-1}$ with explicit re-orthogonalisation;
- Project $H$ onto the Krylov subspace to form a $K\times K$ tridiagonal-like matrix;
- Diagonalise the projected matrix via power iteration to obtain the ground-state Ritz value and vector.

This is a dense Hermitian solver with no external dependencies.

### 4.4 FHS Berry curvature formula

The Fukui-Hatsugai-Suzuki (JPSJ 74, 1674, 2005) gauge-invariant discretisation computes a Wilson phase on a parameter-space plaquette:
$$
\varphi_W = \arg\Big[U_1(\lambda)\,U_2(\lambda+\hat\delta_1)\,U_1^*(\lambda+\hat\delta_2)\,U_2^*(\lambda)\Big]
$$
where $U_\mu(\lambda) = \langle\psi_0(\lambda)|\psi_0(\lambda+\hat\delta_\mu)\rangle / |\cdots|$ are U(1) link variables. Gauge invariance was verified by applying random U(1) phases to the four ground states and confirming $F_{12}$ unchanged to $\sim 10^{-10}$.

With the connection convention used here, an overlap has phase
$-A_\mu d\lambda^\mu$, so

$$
\varphi_W=-\int_{\square}F_{12}\,d\lambda_1d\lambda_2,
\qquad
F_{12}=-\frac{\varphi_W}{\Delta\lambda_1\Delta\lambda_2}.
$$

### 4.5 Historical numerical output (withdrawn)

All pre-audit curvature numbers are removed because they mixed Wilson phase,
physical flux, and curvature, and were also affected by Hamiltonian-sign and
grid-axis defects. They have no benchmark or finite-size status. The retained
evidence is the repaired executable test suite and the finite-size oracle in
[[Challenge 73 - Protocol Revision 1]].

### 4.6 Code artefacts

| Artefact | Location | Purpose |
|---|---|---|
| `src/berry.hpp` | C73 worktree | Complex Hamiltonian, FHS formula, grid computation |
| `src/berry.cpp` | C73 worktree | Implementation (140 lines) |
| `tests/test_berry.cpp` | C73 worktree | Gauge invariance, 1D/2D validation |

## 5. Validation evidence

- An explicit dense-matrix test verifies
  $H(\theta)=R_x(\theta)H(0)R_x^\dagger(\theta)$ element by element, including
  the signs of $ZY$, $YZ$, and $YY$ terms.
- A synthetic spin-$1/2$ manifold with known
  $F_{\alpha\phi}=-\tfrac12\sin\alpha$ verifies the FHS sign, oriented-area
  normalization, gauge invariance, and zero-overlap rejection.
- A grid test verifies that the first axis is $\theta$ and the second is
  $\Omega$.
- Finite-chain FHS agrees with the independent identity
  $F_{\theta\Omega}=-\tfrac12\partial_\Omega\langle\sum X\rangle$.
- The $N=6\to8$ finite-size error decreases toward the thermodynamic JW oracle
  away from criticality.

## 6. Deviations and unresolved risks

### 6.1 1D JW analytic benchmark

Closed by the derivation and executable oracle in §1.1. The earlier tentative
formula in this section was dimensionally and algebraically incorrect.

### 6.2 Literature audit

The correct Kolodrubetz 2014 paper (SHA-256 prefix `7ea1e2b39ddd`) and the 2017
review (prefix `47403927b500`) were parsed through the MinerU API and checked
against their source hashes, frontmatter, equations, and local image links.

### 6.3 Krylov solver accuracy

The $K=16$ implementation is superseded. The current complex Hermitian Lanczos
uses two-pass full reorthogonalisation and a physical residual
$\|H\psi-E\psi\|_2$; tests cover $N\le10$.

### 6.4 Phase sensitivity at small grid spacing

When $|\hat\delta_\mu|$ is very small, the overlaps approach 1 and the U(1) link-variable phase becomes numerically sensitive (cancellation of large real parts). The FHS formula is mathematically gauge-invariant but the raw product should be used for extreme precision.

## 7. Stage-gate assessment

| Gate | Status | Detail |
|---|---|---|
| FHS formula validated numerically | **Pass** | N=2,4,6; gauge invariance confirmed |
| Finite-size convergence | **Pass** | F₁₂/N bounded, non-divergent for N=2→6 |
| Primary-source and review audit | **Pass** | Correct MinerU sources and hashes verified (§6.2) |
| Parameterisation/protocol freeze | **Pass** | See `Challenge 73 - Stage 0 Preregistration.md` |
| JW analytic benchmark | **Pass** | Closed-form density, critical asymptotic, and executable oracle (§1.1) |

**Stage 0 gate is satisfied by the repaired shared implementation and corrected
MinerU sources.** Historical numerical values in §4.5 remain superseded.

## 8. Remaining Stage 0 work

None. Larger-system QMC and PEPS work belongs to later stages. Any comparison
with Kolodrubetz figures must first apply the $(\theta,\Omega)\to(s,\phi)$
Jacobian in §1.1.

## 9. Stage 1 work plan (provisional)

Stage 1 (after gate clearance) will:
1. Extend the complex ED solver to $N=8$ via shift-invert Lanczos.
2. Compute Berry curvature on a dense $(\theta,\Omega)$ grid for 1D chains up to $N=10$.
3. Validate against the JW analytic formula to confirm $F_{\theta\Omega}/N$ converges to the thermodynamic limit.
4. Compute 2D square-lattice Berry curvature for $3\times 3$ ($N=9$, $\dim=512$) and validate finite-size trends.

## 10. Agent Review and Suggestions

### 10.1 Requested review focus

- Is the Krylov-subspace solver ($K=16$, simple re-orthogonalisation) reliable for $N\le 8$? Should a shift-invert Lanczos or a formal Arnoldi be used instead?
- Does the FHS formula produce the CORRECT sign of $F_{12}$ (right-hand rule in parameter space)?
- Should the JW benchmark be completed before moving to Stage 1, or is the numerical self-consistency (gauge invariance, grid convergence) sufficient?
- Should Challenge 148 ED results on the square lattice be used as a cross-check (same Hamiltonian at $\theta=0$)?

### 10.2 Suggestions log

| Reviewer | Date | Finding | Disposition | Status |
|---|---|---|---|---|
| _Reserved_ | _Pending_ | _No review submitted yet_ | _Pending_ | Open |
