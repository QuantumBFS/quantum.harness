# PEPS Based Algorithm

Projected Entangled Pair States and associated contraction methods (CTMRG, simple/full update, variational optimization) for two-dimensional quantum and classical lattice problems. The default route in this harness is PEPSKit.jl, using Corner Transfer Matrix Renormalization Group (CTMRG) for environment contraction.

## Setup

Canonical stack: `pepskit` (`skills/using-pepskit/stack.toml`).

```
make install julia
make install pepskit
```

Activate the environment with `julia --project=julia-env`.

Remote route: use `/setup-julia`, then the `pepskit:cpu` profile. CTMRG is
CPU-first in the current stack. Fresh remote accounts may spend most of the
first run in Julia package precompilation; monitor output before declaring the
install done.

Official install and usage docs:

- PEPSKit.jl: https://quantumkithub.github.io/PEPSKit.jl/stable/
- 2D classical Ising CTMRG example: https://quantumkithub.github.io/PEPSKit.jl/stable/examples/2d_ising_partition_function/

## Scope

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

## Onboarding Reproduction Target

Default visual target: reproduce the PEPSKit.jl 2D classical Ising CTMRG
example. Sweep temperature, contract the infinite partition function, and plot
magnetization or free energy against the exact Onsager/Yang result. This is the
cleanest CTMRG onboarding route because it is classical, visual, fast, and has
an analytic reference.

For a paper reproduction claim, first ingest the selected CTMRG paper with
`download-ref` into `.knowledge/literature/peps-based-algorithm/`, then let
`/reproduce-paper` derive the exact figure protocol from that primary source.

## Notation

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

## Code Shape (Julia / PEPSKit.jl)

For the classical Ising onboarding route, follow the PEPSKit example shape:

```julia
using LinearAlgebra
using TensorKit, PEPSKit
using QuadGK

# 1. Build the rank-4 local tensor O(beta), plus optional insertion tensors
#    for magnetization M(beta) and energy E(beta).
O, M, E = classical_ising(; beta, J = 1.0)

# 2. Wrap the infinite square network.
Z = InfinitePartitionFunction(O)

# 3. Build and converge a CTMRG environment.
Venv = ComplexSpace(chi_env)
env0 = CTMRGEnv(Z, Venv)
env, = leading_boundary(env0, Z; tol = 1.0e-8, maxiter = 500)

# 4. Contract observables.
lambda = network_value(Z, env)
m = expectation_value(Z, (1, 1) => M, env)
e = expectation_value(Z, (1, 1) => E, env)
```

The local tensor construction and exact Onsager/Yang comparison live in the
script for the specific reproduction target; do not hide them in the method
card. The script should write per-temperature results incrementally and emit
progress after each temperature or `chi_env` point.

## Knobs

| Knob | Effect | Starting point |
|---|---|---|
| `chi_env` | Environment accuracy and cost. | 20 for smoke; sweep 20, 40, 80+ near criticality. |
| `tol` | CTMRG fixed-point tolerance. | `1e-8` for onboarding; tighten for benchmark figures. |
| `maxiter` | Upper bound on CTMRG iterations. | 500; increase near criticality if residual remains high. |
| Temperature grid | Resolution of the visual curve. | Dense near the critical region, sparse away from it. |
| Tensor normalization | Controls numerical scale. | Keep one explicit convention and report it. |
| Symmetry blocks | Speed and stability when applicable. | Use only when the model convention is already clear. |

## Pitfalls

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

## Verification

- **Install smoke**: run the `pepskit` stack smoke command from
  `skills/using-pepskit/stack.toml`.
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

## Citations

- PEPSKit.jl documentation: https://quantumkithub.github.io/PEPSKit.jl/stable/
- PEPSKit.jl 2D classical Ising CTMRG example:
  https://quantumkithub.github.io/PEPSKit.jl/stable/examples/2d_ising_partition_function/
- Nishino and Okunishi, *J. Phys. Soc. Jpn.* **65**, 891 (1996) - original
  CTMRG development. Ingest the primary source before using it for a reproduction
  claim.
