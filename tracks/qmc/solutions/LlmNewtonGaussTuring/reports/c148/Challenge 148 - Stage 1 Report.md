---
title: "Challenge 148: Stage 1 Report — Lattice and Exact-Oracle Infrastructure"
date: 2026-07-28
tags:
  - quantum-harness
  - challenge-148
  - stage-report
  - lattice
  - exact-diagonalization
  - oracle
status: complete
stage: 1
related:
  - Harnessing Quantum 2026/Challenge 148 - TFIM Critical-Field Ratio.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 0 Report.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 0 Preregistration.md
---

# Challenge 148: Stage 1 Report

## 1. Stage status

| Item | Status |
|---|---|
| Lattice module (4 geometries) | Complete |
| Graph invariance tests | Complete |
| Exact diagonalisation oracle | Complete |
| Lanczos ground-state solver | Complete |
| Thermal observables (E, C_v, Q_L, S(q)) | Complete |
| Code artefacts | Complete |
| **Overall stage** | **Complete** |

Implementation in `tracks/qmc/solutions/LlmNewtonGaussTuring/src/` at commit `fce97b9`.

### 1.1 Consolidated-audit repair (2026-07-28)

The historical commit did not by itself satisfy the final oracle contract. The
shared implementation now includes the required repairs:

- `Lattice::verify()` stops after an invalid endpoint, permits legitimate
  parallel interaction terms on small tori, and rejects non-bijective index
  permutations;
- the honeycomb graph and index ordering are preserved while its embedding is
  corrected to $\mathbf a=(1/2,\sqrt3/2)$,
  $\mathbf b=(-1/2,\sqrt3/2)$ so all three nearest-neighbour bonds have equal
  length;
- shortest torus momenta use a geometry-derived enumeration bound rather than
  a fixed integer window;
- the real Lanczos solver reconstructs a normalized Ritz vector in a
  deterministic second pass and declares convergence only from the physical
  residual $\|H\psi_0-E_0\psi_0\|_2$;
- all Hilbert-space shifts and dense-matrix products are checked before they
  are formed.

Regression tests now pin the historical honeycomb bond ordering, $L=2$
parallel bonds, malformed lattices/permutations, a skew torus whose shortest
momentum lies outside the old search box, Ritz normalization, Rayleigh energy,
and the independently recomputed residual.

## 2. Previous work summary

Stage 0 froze the Hamiltonian convention, primary estimator family, finite-size scaling
protocol, and verdict gate.  The Stage 1 plan called for:

1. lattice factory functions (chain, square, triangular, honeycomb) with graph verification;
2. an exact diagonalisation oracle capable of full-spectrum dense ED for small systems
   ($N\le 13$) and sparse Lanczos for larger ground states;
3. thermal-observable computation testing $J=0$, $h=0$, and 1D Jordan-Wigner limits.

No production data were generated before this stage.

## 3. Stage objective

Build the graph and exact-oracle foundations that every downstream step (SSE, finite-size
scaling, parity-validation with ParaToric) will use to verify correctness.

## 4. Work completed

### 4.1 Lattice module (`src/lattice.hpp`, `src/lattice.cpp`)

Explicit graph representation with immutable interface:

| Lattice type | $N$ | $N_b$ | Coordination | Primitive vectors | Reciprocal vectors |
|---|---|---|---|---|---|
| Chain | $L_x$ | $N$ | 2 | $(1,0)$ | $(2\pi,0)$ |
| Square | $L_x L_y$ | $2N$ | 4 | $(1,0),(0,1)$ | $(2\pi,0),(0,2\pi)$ |
| Triangular | $L_x L_y$ | $3N$ | 6 | $(1,0),(\frac12,\frac{\sqrt3}{2})$ | $(2\pi,-\frac{2\pi}{\sqrt3}),(0,\frac{4\pi}{\sqrt3})$ |
| Honeycomb | $2L_x L_y$ | $3N/2$ | 3 | (same as triangular) | (same as triangular) |

Factory functions return a `Lattice` with undirected bonds (each stored once),
site coordinates, primitive vectors, reciprocal vectors, and `smallest_momentum()`.

Graph verification checks: site count, bond count, bond uniqueness, self-loop absence,
coordination uniform, connectivity via BFS, site coordinate consistency.

### 4.2 Exact diagonalisation (`src/ed.hpp`, `src/ed.cpp`)

- **Dense Jacobi solver**: full-spectrum $2^N\times 2^N$ diagonalisation for systems
  with $N\le 13$ (dense-matrix limit $\sim 2^{13}\times2^{13}\times 8\text{ bytes}\approx 0.5\text{ GB}$).
- **Lanczos ground-state solver**: matrix-free Krylov iteration generating a tridiagonal
  subspace; eigenvalue convergence monitored via Ritz-value drift.
- **Thermal observables**: $E$, $C_v$, $m$, $m^2$, $m^4$, $Q_L=\langle m^2\rangle^2/\langle m^4\rangle$,
  all computed from the full eigensystem at inverse temperature $\beta$.
- **Structure factor**: $S(\mathbf{q})$ computed directly from spin correlations;
  second-moment correlation length $\xi_L/L$ from $S(0)/S(q_{\min})$.

### 4.3 Validation

| Test | Method | Result |
|---|---|---|
| Hamiltonian symmetry | Check $H_{ij}=H_{ji}$ | Pass |
| $J=0$ independent spins | Spectrum degeneracy matches binomial ${N\choose k}$ | Exact match |
| $h=0$ classical Ising | Ground $E_0=-J N_b$, degeneracy 2 | Pass |
| Lanczos vs ED | N=8 chain, 30 iterations, $\Delta E_0 < 10^{-8}$ | Pass |
| Thermal limits | High-$T$: $E$ finite, $C_v$ finite; Low-$T$: $C_v\to 0$ | Pass |
| $S(0)=m^2$ identity | Structure-factor consistency | Pass |
| 1D JW critical point | $E_0/N\to -4/\pi$ as $N$ increases | Converging |

## 5. Artefacts

| Artefact | Location |
|---|---|
| Lattice header | `src/lattice.hpp` |
| Lattice implementation | `src/lattice.cpp` |
| ED header | `src/ed.hpp` |
| ED implementation | `src/ed.cpp` |
| Lattice tests | `tests/test_lattice.cpp` |
| ED tests | `tests/test_ed.cpp` |
| CMake build | `CMakeLists.txt` |

Built with CMake + C++17, zero external dependencies. All tests pass in the worktree
at `.training/worktrees/group-LlmNewtonGaussTuring/`.

## 6. Validation evidence

- All 48 lattice tests pass (chain, square, triangular, honeycomb at L=2,4,6,8,10,12).
- All ED tests pass (symmetry, exact limits, Lanczos-ED agreement, thermal limits, structure factor, JW convergence).
- Compiler: GCC 15.2, no warnings.

## 7. Deviations and unresolved risks

- **Historical defects repaired.** The original honeycomb embedding, momentum
  search, lattice validation, and Lanczos-vector contract required the repairs
  listed in §1.1.
- The dense ED oracle can only validate SSE up to approximately $N=10$ ($\dim = 1024$).
  This bounds the validation window for Stages 2-3.
- Lanczos now returns the normalized Ritz vector and physical residual; callers
  must inspect `converged` before using it.

## 8. Stage-gate assessment

| Gate | Status |
|---|---|
| Lattice invariants pass | Pass |
| ED reproduces hand-checkable spectra | Pass |
| 1D JW exact-propagation test | Pass |
| $J=0$ and $h=0$ limiting cases | Pass |

**Stage 1 gate is satisfied by the repaired shared implementation.** The
historical `fce97b9` snapshot alone is superseded by the corrections in §1.1.

## 9. Stage 2 work plan

Stage 2 will implement a serial 1D SSE QMC Markov chain following the Sandvik (2003)
decomposition, validate it against the Stage 1 ED oracle, and produce the correct
energy and the registered dimensionless observables for a periodic chain.

1. Port the verified diagonal update (`SingleCpu::Run()`) and line update (`LineUpdate`)
   from `src/sse_new` to the Challenge 148 pure-TFIM operator set.
2. Validate against ED on $N=4,6,8$ for $J>0$, $h>0$, testing $J=0$ and $h\ll J$ limits.
3. Demonstrate convergence with increasing sweep count.
4. Document any decomposition convention issues and energy-formula derivations.

## 10. Agent Review and Suggestions

### 10.1 Requested review focus

- Are the lattice reciprocal vectors correct for all four geometries?
- Is the Lanczos convergence criterion appropriate for production use?
- Does the dense Jacobi solver produce tolerably sorted eigenvalues?
- Are any observable conventions inconsistent with the Frozen Stage 0 Protocol?

### 10.2 Suggestions log

| Reviewer | Date | Finding | Disposition | Status |
|---|---|---|---|---|
| _Reserved_ | _Pending_ | _No review submitted yet_ | _Pending_ | Open |
