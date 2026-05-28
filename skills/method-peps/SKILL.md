---
name: method-peps
description: Use when a PEPS, iPEPS, CTMRG, 2D tensor-network, environment dimension, or classical partition-function reproduction needs method-level route and tool selection.
---

# Method PEPS

PEPS is the tensor-network track for environment contraction, classical
partition functions, and PEPS optimization. Use it to decide which method card
and tool skill own the next step.

## Sources

- Track README: `tracks/peps/README.md`
- Tool skill: `/using-pepskit`

## Route

1. Use CTMRG/environment contraction when the figure depends on free energy, magnetization, transfer matrices, correlation length, or PEPS expectation values.
2. Distinguish fixed-tensor contraction from variational PEPS optimization before selecting parameters.
3. If the target is finite-temperature Linearized Tensor Renormalization Group, hand off to `/method-ltrg`; it owns the LTRG route, method card, and tool selection.
4. Recommend `/using-pepskit` for PEPSKit.jl / TensorKit.jl setup, CTMRG settings, and timing.
5. If the paper target is a package tutorial or official code, offer official code / web search before reimplementing formulas.

## Tool Handoff

Invoke `/using-pepskit` for PEPS or CTMRG routes. For LTRG, hand off to `/method-ltrg`.

## Details

Projected Entangled Pair States and associated contraction methods (CTMRG, simple/full update, variational optimization) for two-dimensional quantum and classical lattice problems, with CTMRG as the default environment-contraction route.

### Scope

Use this card for:

- Infinite 2D classical partition functions represented as local tensors.
- PEPS environment contractions through CTMRG.
- Visual finite-chi convergence studies of free energy, magnetization, energy,
  or correlation length.
- Simple classical onboarding figures, especially the 2D square-lattice Ising
  model.

Do not use this card as the full recipe for:

- Optimizing an iPEPS ground state.
- Finite PEPS contraction.
- Time evolution.
- Claiming reproduction of an original CTMRG paper before its primary source
  has been ingested under `.knowledge/literature/peps-based-algorithm/`.

### Onboarding Reproduction Target

Default visual target: the 2D classical Ising CTMRG example. Sweep temperature,
contract the infinite partition function, and plot magnetization or free energy
against the exact Onsager/Yang result. This is the cleanest CTMRG onboarding
route because it is classical, visual, fast, and has an analytic reference.

For a paper reproduction claim, first ingest the selected CTMRG paper with
`download-ref` into `.knowledge/literature/peps-based-algorithm/`, then let
`/reproduce-paper` derive the exact figure protocol from that primary source.

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

- **Residual convergence**: record CTMRG residual and iteration count for every
  grid point.
- **Chi convergence**: repeat the curve for at least two `chi_env` values; near
  criticality, use more.
- **Analytic limits**: check high-temperature and low-temperature Ising limits
  before plotting a full curve.
- **Exact curve**: compare the 2D Ising free energy, magnetization, and/or
  energy against the analytic Onsager/Yang formulas used in the script.
- **Tiny-network cross-check**: for a small finite patch, compare the local
  tensor construction against direct enumeration before trusting the infinite
  contraction.

### Citations

- Nishino and Okunishi, *J. Phys. Soc. Jpn.* **65**, 891 (1996) — original
  CTMRG development. Ingest the primary source before using it for a reproduction
  claim.
