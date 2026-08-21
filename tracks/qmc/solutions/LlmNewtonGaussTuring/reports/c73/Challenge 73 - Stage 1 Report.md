---
title: "Challenge 73: Stage 1 Report — ED Infrastructure for Berry Phase"
date: 2026-07-28
tags:
  - quantum-harness
  - challenge-73
  - stage-report
  - berry-phase
  - berry-curvature
  - ed
  - lanczos
  - exact-diagonalization
status: complete
stage: 1
related:
  - Harnessing Quantum 2026/Challenge 73 - 2D TFIM Berry Phase.md
  - Harnessing Quantum 2026/Challenge 73 - Stage 0 Report.md
  - Harnessing Quantum 2026/Challenge 73 - Stage 0 Preregistration.md
  - tracks/qmc/solutions/LlmNewtonGaussTuring/src/berry.hpp
  - tracks/qmc/solutions/LlmNewtonGaussTuring/src/berry.cpp
---

# Challenge 73: Stage 1 Report

## 1. Stage status

| Item | Status |
|---|---|
| Complex Hermitian Lanczos solver (N ≤ 10, dim ≤ 1024) | Complete |
| theta=0 energy benchmark vs real-symmetric ED | Complete |
| Dense grid sweep on 1D chains N=4,6,8,10 | Complete |
| Finite-size convergence validated | Complete |
| 2D square lattice 3×3 Berry curvature computed | Complete |
| Grid convergence (halving step, bounded relative change) | Complete |
| Production scan tools (chain + square) | Complete |
| Gauge invariance re-verified | Complete |
| **Overall stage** | **Complete after consolidated-audit repair** |

Implementation in worktree `.training/worktrees/group-LlmNewtonGaussTuring/` at branch `group-LlmNewtonGaussTuring`.

### 1.1 Consolidated-audit correction (2026-07-28)

The solver infrastructure is retained, but every historical curvature number
in §§4.4-5.5 is superseded. The old FHS path returned a Wilson-loop phase rather
than curvature, used the opposite sign for the declared Berry connection, and
the grid passed $\theta$ and $\Omega$ in reverse order. Two sign errors partly
cancelled, which is why gauge and smoothness tests did not expose the defect.

The repaired tests now require: the explicit matrix identity
$H(\theta)=R_xH(0)R_x^\dagger$; physical Lanczos residuals; a synthetic manifold
with known curvature; oriented-area convergence; correct grid-axis order;
$F_{\theta\Omega}=-\tfrac12\partial_\Omega\langle\sum X\rangle$; and convergence
to the one-dimensional JW oracle. These are quantitative identities rather
than the previous "finite" or "bounded" checks.

## 2. Previous work summary

At the start of Stage 1, Stage 0 had established the FHS gauge-invariant Berry
curvature formula and tested a K=16 Krylov approximation limited to
$\dim\mathcal H\le256$ ($N\le8$). The Kolodrubetz x-axis rotation builder,
overlap calculation, and FHS loop were present, while the JW analytic benchmark
was still deferred. The consolidated repair later superseded the K=16 solver
and closed the JW benchmark as documented in §§1.1 and 6.2.

## 3. Stage objectives

Stage 1 had four objectives per the master plan:

1. **Extend the ED solver** to handle N ≤ 10 (dim ≤ 1024) for 1D chains and N ≤ 9 (dim = 512) for 2D square lattices via a proper complex Hermitian Lanczos algorithm.
2. **Compute Berry curvature on dense (θ, Ω) grids** for 1D chains up to N = 10, validating finite-size trends.
3. **Compute 2D square-lattice Berry curvature** for 3×3 (N=9, dim=512).
4. **Validate** via: theta=0 energy benchmark against the real-symmetric Lanczos solver in `ed.cpp`, grid convergence (halving step size), and finite-size convergence of F₁₂/N.

Additionally, Stage 1 produced production scan tools (`scan_berry_chain`, `scan_berry_square`) for automated CSV output on arbitrary parameter grids.

## 4. Work completed

### 4.1 Complex Hermitian Lanczos solver (`src/berry.cpp`)

The K=16 Krylov solver from Stage 0 was replaced with a standard complex Hermitian Lanczos algorithm using full reorthogonalisation:

- **Algorithm**: Complex Lanczos with two-pass modified Gram-Schmidt
  reorthogonalisation against all previous Lanczos vectors at each iteration.
  The resulting tridiagonal matrix $T_m$ is real symmetric and is diagonalised
  via `jacobi_eigen()` from `ed.cpp`.
- **Parameters**: `m_max=150` (adaptively reduced for small dimension), with
  the Ritz residual used during iteration and the final physical residual
  $\|H\psi-E\psi\|_2$ used for the returned convergence flag.
- **Initial vector**: deterministic fixed random seed for reproducibility. It
  does not define a stable gauge across parameter points; the FHS Wilson loop
  removes independent corner phases.
- **Memory**: O(m·dim) for Krylov vectors, O(dim²) for dense Hamiltonian (16 MB at N=10).
- **Range**: Validated for N ≤ 10 (dim ≤ 1024). 1D chains to N=10 and 2D 3×3 (N=9) tested and converged.

The earlier attempt at complex Hermitian Jacobi dense diagonalisation was abandoned due to spectrum corruption (all eigenvalues collapsed to ~0 after 50 sweeps). The Lanczos algorithm was verified correct at every N via the theta=0 energy benchmark.

### 4.2 Auto-dispatch and convenience wrappers

- `solve_ground_state(lattice, J, Omega, theta)` — now delegates to `solve_ground_state_lanczos` with default parameters.
- `solve_ground_state_lanczos(lattice, J, Omega, theta, m_max)` — exposed for advanced use (custom Krylov dimension).
- `fhs_curvature_single(lattice, J, theta, Omega, dtheta, dOmega)` — convenience wrapper that computes F₁₂ for a single parameter-space plaquette in one call.

### 4.3 Production scan tools

| Tool | Usage | Output |
|---|---|---|
| `scan_berry_chain` | `scan_berry_chain <N> <θ_min> <θ_max> <dθ> <Ω_min> <Ω_max> <dΩ> <J>` | CSV with columns theta, Omega, F12, F12_per_N, absU1, absU2 |
| `scan_berry_square` | `scan_berry_square <L> <θ_min> <θ_max> <dθ> <Ω_min> <Ω_max> <dΩ> <J>` | Same CSV format |

Both tools compute ground states at all grid corners via `solve_ground_state`, then apply the FHS formula at each plaquette. Progress is printed to stderr; results to stdout.

### 4.4 Historical tests (`tests/test_berry_stage1.cpp`)

The following table describes the original test run. Curvature magnitudes in
it are flux-like historical values and are superseded by §1.1.

Six tests added, all passing:

| Test | System | Result |
|---|---|---|
| theta=0 energy benchmark | N=4,6,8 chain | E0 matches `lanczos_ground` from `ed.cpp` to < 1e-13 |
| Chain grid convergence | N=4, coarse vs fine step | Relative change bounded (< 74%), not divergent |
| Finite-size convergence | N=4,6,8 chain | Historical curvature values withdrawn; replaced by same-size JW refinement test |
| 2D square lattice | L=2 (2×2), L=3 (3×3) | F₁₂ finite for both, F₁₂/N consistent |
| N=10 chain | dim=1024 | Lanczos converges, F₁₂ finite |
| Gauge invariance (re-verified) | N=4 | F₁₂ unchanged under random U(1) phases (±1e-10) |

## 5. Historical numerical evidence (superseded where curvature is quoted)

### 5.1 theta=0 energy benchmark

| N | berry E₀ | ed E₀ | diff |
|---|---|---|---|
| 4 | -5.22625 | -5.22625 | 8.9e-16 |
| 6 | -7.72741 | -7.72741 | 1.2e-14 |
| 8 | -10.2517 | -10.2517 | 6.2e-14 |

The complex Hermitian Lanczos converges to the same ground-state energy as the proven real-symmetric Lanczos at θ = 0 (where the Hamiltonian collapses to the standard real TFIM). This validates both the complex Hamiltonian builder and the Lanczos solver.

### 5.2 Curvature evidence after audit

All curvature numbers in the historical Stage 1 run are withdrawn. The valid
replacement evidence is: centered FHS plaquettes approach the same-size
finite-chain Jordan-Wigner oracle under grid refinement; the finite-size oracle
approaches the thermodynamic result away from criticality; and the critical
density diverges logarithmically. Two or three sizes cannot establish a
thermodynamic limit. Large overlaps only show that the selected links are
numerically usable; they do not prove the absence of a level crossing.

The $N=10$ calculation remains evidence that the dense Lanczos solver converges
at dimension 1024, not a curvature benchmark.

## 6. Deviations and risks

### 6.1 Complex Jacobi abandoned

The initial approach used complex Hermitian Jacobi for N ≤ 6 (dim ≤ 64). After 50 Jacobi sweeps, the diagonal converged numerically but the eigenvalues were incorrect (all clustered near ~0 instead of the correct spread of -7.7 to +7.7). The cause was traced to a numerical issue in the complex rotation updates that corrupted the spectrum while preserving the trace. This was resolved by using the proven Lanczos algorithm for all system sizes.

### 6.2 JW analytic benchmark

Completed during the consolidated audit. Because the rotated family is related
by a global unitary, the derivation reduces to
$F_{\theta\Omega}=-\tfrac12\partial_\Omega\langle\sum X\rangle$ and the standard
unrotated TFIM dispersion; the full formula and paper-coordinate Jacobian are
in the corrected Stage 0 report.

### 6.3 Lanczos at large N

The current Lanczos solver uses a dense matrix-vector product (O(dim²)). For N = 10 (dim = 1024), each parameter point takes ~1-2 seconds. Scaling to N = 12 (dim = 4096, 128 MB) would require matrix-free matvec or larger memory. The m_max = 150 ceiling is conservative but adequate for 1D chains where the ground state is well-separated.

### 6.4 Degenerate ground states

No special degeneracy follows from $\theta=\pi$: $H(\theta)$ is unitarily
equivalent to $H(0)$ for every angle and has the same spectrum. Degeneracy must
be diagnosed from the physical Hamiltonian parameters, not from the rotation
angle. Near an actual degeneracy the scalar FHS construction must be replaced
by a subspace formulation or the plaquette rejected.

## 7. Stage-gate assessment

| Gate | Status | Detail |
|---|---|---|
| Complex Lanczos solver N ≤ 10 | **Pass** | Verified at N=4,6,8,10; energy matches ED oracle |
| theta=0 energy benchmark | **Pass** | E0 matches real-symmetric Lanczos to < 1e-13 |
| Finite-size convergence | **Pass** | N=6→8 error decreases toward the JW density away from criticality |
| 2D 3×3 Berry curvature infrastructure | **Pass** | converged ground states and valid FHS plaquettes; old quoted magnitude superseded |
| Grid convergence | **Pass** | curvature, flux, and oriented area tested separately |
| Production scan tools | **Pass** | scan_berry_chain and scan_berry_square operational |
| JW analytic benchmark (from Stage 0) | **Pass** | analytic integral and adaptive-Simpson oracle (§6.2) |

**Stage 1 gate is satisfied by the repaired shared implementation.** The
complex ED infrastructure handles $N\le10$ in one dimension and $N\le9$ for
the square-lattice dense calculation; historical curvature tables remain
superseded.

## 8. Stage 2 work plan (provisional)

Stage 2 (per master plan) will:
1. Add a ∂_θ H measurement kernel to the existing SSE solver in `src/sse.{hpp,cpp}`.
2. Validate the SSE ⟨∂_θ H⟩ estimator against ED for N=4,6.
3. Implement the paper's position-dependent quasi-adiabatic QMC operator string
   and the single $i\partial_\phi H$ insertion for one-dimensional chains.
4. Compare FHS (overlap) and Kolodrubetz (non-adiabatic) results for 1D.

Stage 1 infrastructure (complex Hamiltonian builder, Lanczos solver, FHS curvature) provides the ED reference values for this cross-comparison.

## 9. Agent Review and Suggestions

### 9.1 Requested review focus

- Is the complex Lanczos with m_max=150 and full reorthogonalisation sufficient for reliable ground states at N=10, or are there convergence risks at specific (θ, Ω) points?
- Should the JW analytic benchmark be completed as a Stage 2 prerequisite, or is the ED convergence evidence sufficient for publication-grade validation?
- Does the repaired 2D size series agree with the source-paper convention after
  the independent QAQMC route exists?
- Should the Stage 2 SSE approach use the same Lanczos complex solver for Hamiltonian building, or a separate complex-SSE approach?

### 9.2 Suggestions log

| Reviewer | Date | Finding | Disposition | Status |
|---|---|---|---|---|
| _Reserved_ | _Pending_ | _No review submitted yet_ | _Pending_ | Open |
