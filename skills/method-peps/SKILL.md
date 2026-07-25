---
name: method-peps
description: Use when a PEPS, iPEPS, CTMRG, 2D tensor-network, environment dimension, or classical partition-function reproduction needs method-level route and tool selection.
---

# Method PEPS

PEPS is the tensor-network track for environment contraction, classical
partition functions, and PEPS optimization. Use it to decide which method card
and tool skill own the next step.

## Sources

- **Methodology reference** (reproduction-grade algorithm, parameters, validation, gap analysis): `references/peps-methodology.md`
- Track README: `tracks/peps/README.md`
- Tool skill: `/using-pepskit`

## Route

1. Use CTMRG/environment contraction when the figure depends on free energy, magnetization, transfer matrices, correlation length, or PEPS expectation values.
2. Distinguish fixed-tensor contraction from variational PEPS optimization before selecting parameters.
3. Recommend `/using-pepskit` for PEPSKit.jl / TensorKit.jl setup, CTMRG settings, and timing.
4. If the paper target is a package tutorial or official code, offer official code / web search before reimplementing formulas.

## Tool Handoff

Invoke `/using-pepskit` for PEPS or CTMRG routes.

## Details

### Scope

The PEPS family of algorithms — the projected-entangled-pair-state ansatz for
two- and higher-dimensional lattice states, and everything built on it:

- **Ansatz construction** — finite PEPS or an iPEPS unit cell, bond dimension `D`.
- **Ground-state optimization** — imaginary-time simple update and full update,
  variational / automatic-differentiation energy minimization.
- **Environment contraction** — CTMRG, boundary-MPS / VUMPS.
- **Observables** — read off the converged environment.

Exact contraction of a PEPS is intractable, so every route approximates it under
an environment dimension `chi_env` distinct from `D`. Convergence is shown in
both.

Two-dimensional classical partition functions are the single-layer special case:
the same contraction machinery on rank-4 tensors, with no double layer.

### Notation

- Local tensor: rank-4 tensor for a square-lattice classical model, or PEPS
  tensor / double-layer tensor for a quantum state.
- `D`: PEPS virtual bond dimension when contracting a PEPS.
- `chi_env`: CTMRG environment bond dimension.
- Corner tensors `C` and edge tensors `T`: environment tensors approximating the
  infinite network boundary.
- CTMRG residual: convergence metric returned by the boundary iteration.
- Transfer-matrix correlation length: diagnostic extracted from the converged
  environment.
- Free energy per site: for a classical partition function, obtained from the
  dominant network value and the chosen normalization convention.

### Pitfalls

- **Finite-chi rounding**: CTMRG smooths sharp critical behavior at finite
  `chi_env`. Show chi convergence before interpreting critical data.
- **Convergence slowdown**: near criticality, residuals and correlation lengths
  converge slowly. Increase both `chi_env` and `maxiter`.
- **Normalization mismatch**: free energy is sensitive to tensor normalization.
  Keep the partition-function construction and free-energy formula in the same
  script.
- **Symmetry breaking**: magnetization below the critical temperature can depend
  on initialization or explicit bias. Record the symmetry-breaking convention.
- **PEPS versus partition-function environments**: PEPS double-layer
  environments and classical partition-function environments have different edge
  tensor structure. Do not copy observable formulas across them blindly.

### Verification

Always recorded, since they are byproducts of the run and cost nothing:

- **Residual convergence**: CTMRG residual and iteration count for every grid
  point.
- **Discarded weight**: truncation error at each renormalization step.

Opt-in, since they cost extra compute — propose them only when the user
challenges a result, never by default:

- **Chi convergence**: repeat the curve at a second `chi_env`; near criticality,
  more.
- **Analytic limits**: check the high-temperature and low-temperature limits of
  the model.
- **Tiny-network cross-check**: for a small finite patch, compare the local
  tensor construction against direct enumeration.

### Citations

- Nishino and Okunishi, *J. Phys. Soc. Jpn.* **65**, 891 (1996) — original
  CTMRG development. Ingest the primary source before using it for a reproduction
  claim.
