---
name: using-pepskit
description: Use when choosing or running PEPSKit.jl or TensorKit.jl for PEPS, CTMRG, 2D classical/quantum tensor-network calculations, or PEPSKit setup failures.
---

# PEPSKit

Use PEPSKit with TensorKit for PEPS / CTMRG calculations where convergence knobs and tensor symmetries matter.

## Sources

- Stack contract: `skills/using-pepskit/stack.toml`
- Method card: `.knowledge/methods/peps-based-algorithm.md`
- Install target: `make install pepskit`
- Smoke test: `julia --project=julia-env -e 'using TensorKit, PEPSKit, QuadGK'`

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

## Time estimate

Estimate from PEPS bond dimension, environment dimension, unit-cell size, CTMRG iterations, and whether optimization is included.

- CTMRG wall time grows steeply with environment dimension and PEPS bond dimension; memory is usually dominated by environment tensors.
- Variational optimization multiplies CTMRG cost by the number of optimizer iterations and gradient/evaluation calls.
- Julia precompilation is setup time and should be reported separately from physics runtime.
- For uncertain cases, time a tiny CTMRG probe with reduced environment dimension, then extrapolate and compare paper size against the largest local-PC-in-15-min setting.

## Common Setup Notes

- Use cluster compute when environment dimensions or parameter scans exceed local memory/time.
- A converged energy alone is not enough; check the target observable and environment residual.
- Do not hide changes to bond dimension or environment dimension; they alter the scientific claim.
