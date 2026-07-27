---
name: using-pepskit
description: Use when choosing or running PEPSKit.jl or TensorKit.jl for PEPS, CTMRG, 2D classical/quantum tensor-network calculations, or PEPSKit setup failures.
---

# PEPSKit

Use PEPSKit with TensorKit for PEPS / CTMRG calculations where convergence knobs and tensor symmetries matter.

## Sources

- Stack contract: `skills/using-pepskit/stack.toml`
- Method card: `skills/method-peps/SKILL.md`
- Install target: `make install pepskit`
- Smoke test: `julia --project=julia-env -e 'using TensorKit, PEPSKit, QuadGK'`
- Docs: PEPSKit.jl <https://quantumkithub.github.io/PEPSKit.jl/stable/>; 2D classical Ising CTMRG example <https://quantumkithub.github.io/PEPSKit.jl/stable/examples/2d_ising_partition_function/>
- Local API reference (key API + worked examples, with links to upstream docs): `references/pepskit-api.md`

## Workflow

1. Consult the stack contract before setup; fresh Julia precompilation can dominate first-run time.
2. Pin lattice, unit cell, boundary/thermodynamic convention, bond dimension, environment dimension, truncation, and convergence tolerance.
3. Record CTMRG iteration count, convergence residual, observable stability, and symmetry assumptions.
4. For paper reproductions, distinguish CTMRG environment convergence from variational optimization convergence.

## Parameter setup

Use this section as the source for PEPSKit-specific reproduction knobs unless the paper or official code fixes a value. The method card supplies the CTMRG/PEPS notation and onboarding defaults; this skill exposes the convergence controls.

- System/tensor: lattice, unit cell, boundary or thermodynamic convention, local space, tensor symmetry, normalization, and operator convention.
- Ansatz/network: PEPS bond dimension or classical local tensor, initialization, gauge/canonicalization convention, and whether tensors are fixed or optimized.
- Environment: CTMRG environment dimension `chi_env`, truncation scheme, tolerance, maximum iterations, update style, and initialization/bias for symmetry breaking.
- Optimization: optimizer, line search/step size, gradient settings, iteration count, and stopping criterion when variational optimization is part of the target.
- Observables: target observable, normalization, correlation length/range, transfer-matrix quantity, and measurement cadence.
- Validation: CTMRG residual, observable stability vs environment dimension, bond-dimension trend, and comparison to exact/classical limits when available.

## Knobs

Concrete starting points for the convergence controls in Parameter setup.

| Knob | Effect | Starting point |
|---|---|---|
| `chi_env` | Environment accuracy and cost. | 20 for smoke; sweep 20, 40, 80+ near criticality. |
| `tol` | CTMRG fixed-point tolerance. | `1e-8` for onboarding; tighten for benchmark figures. |
| `maxiter` | Upper bound on CTMRG iterations. | 500; increase near criticality if residual remains high. |
| Temperature grid | Resolution of the visual curve. | Dense near the critical region, sparse away from it. |
| Tensor normalization | Controls numerical scale. | Keep one explicit convention and report it. |
| Symmetry blocks | Speed and stability when applicable. | Use only when the model convention is already clear. |

## Code shape

Two modes — decided upstream (`/method-peps` step 2; the track README wins):
a **hand-written loop on TensorKit primitives** when the target requires
implementing the algorithm itself, or the **packaged high-level call**. When
the loop is hand-written, the packaged call is the independent cross-check,
not the deliverable.

### CTMRG primitives (hand-written loop)

The renormalization loop — grow the corner/edge, contract, SVD-truncate to
`chi_env`, normalize, accumulate log scale factors — is owned by the source
being reproduced and `/method-peps`. TensorKit supplies the primitives (check
exact API against the TensorKit docs; illustrative shape):

```julia
using TensorKit   # @tensor contraction + tsvd truncation are the two primitives

@tensor M[a b; c d] := C[a, e] * T[e, s, c] * ...        # grow the corner
U, S, _ = tsvd(M; trunc = truncdim(chi_env))             # truncate to chi_env
C = U' * M * ...                                          # renormalize the environment
C = C / norm(C); # log the normalization factor with the step's output
```

### Packaged route (or cross-check of a hand-written loop)

For the classical Ising route, the PEPSKit example shape:

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
reproduction script, not here. Write per-temperature results incrementally and
emit progress after each temperature or `chi_env` point.

> **Energy-insertion caution (verified against enumeration).** The upstream
> example builds its energy tensor with an element-wise leg
> `e = (-J s s') .* nt` (with `nt = sqrt(t)`, `t` the bond Boltzmann matrix).
> That is wrong: element-wise and matrix products don't commute, so the
> contracted link carries `nt·(E∘nt) ≠ E∘t` — internal energy comes out off by
> O(1e-2–1e-1) while the partition function and magnetization stay
> machine-exact. Build the energy leg `A` by solving `nt * A = (-J s s') .* t`,
> so the full link is the energy-weighted Boltzmann factor `(-J s s')·e^{βJss'}`.
> Validate **every** insertion tensor against brute-force enumeration on a
> 2×2/3×3 torus before production — it costs milliseconds, and it is the only
> check that catches a wrong insertion (a corrupted energy also silently
> poisons the specific heat differentiated from it).

## Time estimate

Estimate from PEPS bond dimension, environment dimension, unit-cell size, CTMRG iterations, and whether optimization is included.

- CTMRG wall time grows steeply with environment dimension and PEPS bond dimension; memory is usually dominated by environment tensors.
- Variational optimization multiplies CTMRG cost by the number of optimizer iterations and gradient/evaluation calls.
- Julia precompilation is setup time and should be reported separately from physics runtime.
- For uncertain cases, time a tiny CTMRG probe with reduced environment dimension, then extrapolate and compare paper size against the largest local-PC-in-15-min setting.

## Common Setup Notes

- Use cluster compute when environment dimensions or parameter scans exceed local memory/time.
- Remote route: run `/setup-julia`, then use the `pepskit:cpu` profile; CTMRG is CPU-first in the current stack, and fresh accounts may spend most of the first run in Julia precompilation.
- A converged energy alone is not enough; check the target observable and environment residual.
- Do not hide changes to bond dimension or environment dimension; they alter the scientific claim.
