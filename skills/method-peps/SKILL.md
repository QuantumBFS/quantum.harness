---
name: method-peps
description: Use when a PEPS, iPEPS, CTMRG, 2D tensor-network, environment dimension, or classical partition-function reproduction needs method-level route and tool selection.
---

# Method PEPS

PEPS is the method class — the projected-entangled-pair-state ansatz for two-
and higher-dimensional lattice states, and the algorithms built on it; CTMRG on
iPEPS is one instance. This card owns method selection (step 1: which instance
of the class), software routing (step 2), and method-level setup (step 3,
method side). Package parameter *values* live in `/using-pepskit`.

## Sources

- **Methodology reference** (reproduction-grade algorithm, parameters, validation, gap analysis): `references/peps-methodology.md`
- **Method-zoo cards** (property tables, cost classes): `.knowledge/methods/peps-ipeps`; `.knowledge/methods/trg-hotrg` for single-layer classical contraction.
- Track README: `tracks/peps/README.md`
- Tool skill: `/using-pepskit`

## Select method — step 1

### Suited for

- 2D (and higher) quantum lattice ground states — the ansatz encodes the 2D
  area law at fixed bond dimension `D`; sign-problem-free, so frustrated
  magnets and doped models are in reach.
- Observables from a converged environment: energy, magnetization,
  correlation functions, transfer-matrix correlation length; iPEPS reaches
  the thermodynamic limit directly.
- 2D classical partition functions — the single-layer special case: the same
  contraction machinery on rank-4 tensors, no double layer.

### Route elsewhere when

- 1D or quasi-1D chains and ladders — `/method-mps`.
- Finite-temperature thermodynamics of 1D chains — `/method-ltrg`.
- Small clusters where exact spectra or states are the target — `/method-ed`.
- Sign-free models where stochastic sampling is cheaper at scale — `/method-qmc`.

### Options & trade-offs — instances within the class

Every instance approximates the intractable exact contraction under an
environment dimension `chi_env` distinct from `D`; convergence is shown in both.

| Choice | Instances | Trade-off |
|---|---|---|
| Ansatz | finite PEPS vs iPEPS unit cell | finite patches vs thermodynamic limit directly |
| Optimization | simple update / full update / variational-AD | cheap mean-field-environment bias vs accurate but costly full-environment updates |
| Environment contraction | CTMRG (the track instance) / boundary-MPS / VUMPS | equivalent targets, different convergence behavior and implementations |
| Layer structure | double-layer quantum PEPS vs single-layer classical network | same machinery; environments differ in edge-tensor structure |

Distinguish fixed-tensor contraction (given tensors, contract for observables)
from variational PEPS optimization (tensors themselves optimized) before
selecting parameters — they need different knobs.

## Select software — step 2

### Open-source tools

- **PEPSKit.jl / TensorKit.jl** (default) — CTMRG, boundary methods, AD-based
  optimization, symmetric tensors. Route via `/using-pepskit`.
- **When the paper or track requires implementing the algorithm itself** (a
  pedagogical CTMRG written from the source's own construction), the package is
  not the route: it supplies **tensor primitives** for the hand-written loop
  and serves as the **independent cross-check** of it — `/using-pepskit`
  carries both roles.
- If the paper target is a package tutorial or ships official code, offer
  official code / web search before reimplementing formulas.

### Handoff

Invoke `/using-pepskit` after the route is chosen — it owns PEPSKit.jl /
TensorKit.jl setup, CTMRG parameter values, and the time estimate.

## Method setup — step 3 (method side)

Conceptual knobs and what each controls; concrete values live in
`/using-pepskit` (*Parameter setup* / *Knobs*). For a reproduction, the paper's
stated settings win — confirm them, don't re-derive.

| Knob | Controls | Trick / how it affects results |
|---|---|---|
| `D` | ansatz bias | converge or extrapolate observables in `D`; critical or frustrated states need larger `D` |
| unit cell | which ordered states the ansatz can hold | must hold the order period (a Néel state needs a 2-site/checkerboard cell); too small silently forbids the state |
| derivative observables | how `C`, susceptibility are produced | a route choice: differentiate `e`/`f` on a dense temperature grid (differentiation amplifies finite-`chi_env` noise, worst near `T_c`) vs direct fluctuation estimator at extra contraction cost — `references/peps-methodology.md` §5 |
| `chi_env` | contraction bias | an independent knob, not derived from `D`; converge in both (`chi_env ∝ D²` is the standard scale) |
| update scheme | bias vs cost of optimization | simple update to warm-start, full update or AD to finish |
| CTMRG iterations / residual tolerance | environment convergence | near criticality residuals converge slowly — raise `chi_env` and the iteration cap together |
| initialization / symmetry-breaking convention | which ordered state the run selects | record the bias or initial state; magnetization below criticality depends on it |
| normalization convention | free-energy bookkeeping | keep the network construction and the free-energy formula in the same script |

**Cost**: CTMRG observable evaluation scales as `O(chi_env³ D⁶)` with
environment memory `O(chi_env² D⁴)`; full-update / AD optimization
`O(D¹⁰)`–`O(D¹²)`; simple update `~O(D⁵)` per step. Anchors and the estimate
procedure live in `/using-pepskit` *Time estimate*.

## Details

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
- **Insertion-tensor conventions**: splitting bond weights across legs does not
  commute with weighting a bond by an observable — a wrong insertion leaves the
  partition function and magnetization exact while silently corrupting bond
  observables (energy, hence specific heat). Validate every insertion tensor
  against small-lattice enumeration (free, milliseconds) before trusting it;
  the concrete construction lives in `/using-pepskit`.

## Verification — implementation stage

### Intermediate (mid-run)

Always recorded, since they are byproducts of the run and cost nothing:

- **Residual convergence**: CTMRG residual and iteration count for every grid
  point.
- **Discarded weight**: truncation error at each renormalization step.

### Final verification + expert criticism

Opt-in, since they cost extra compute — propose them only when the user
challenges a result, never by default:

- **Chi convergence**: repeat the curve at a second `chi_env`; near criticality,
  more.
- **Analytic limits**: check the high-temperature and low-temperature limits of
  the model.
- **Tiny-network cross-check**: for a small finite patch, compare the local
  tensor construction against direct enumeration.

## Citations

- Nishino and Okunishi, *J. Phys. Soc. Jpn.* **65**, 891 (1996) — original
  CTMRG development. Ingest the primary source before using it for a reproduction
  claim.
