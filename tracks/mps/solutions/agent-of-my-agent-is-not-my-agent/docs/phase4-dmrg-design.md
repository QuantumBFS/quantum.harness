# Phase 4 TeNPy DMRG Design

## Gates and shared workflow

Use finite two-site TeNPy DMRG with `conserve=None`, Pauli operators, an OBC
MPS, and periodic interactions encoded in the MPO. The nearest-neighbor and
long-range TFIM must use the same initialization, sweep schedule, truncation
settings, diagnostics, and excited-state procedure.

The strict first gate compares DMRG with dense ED at L=8,10,12 for E0, E1,
the gap, and variance. The nearest-neighbor model at Gamma=1 must also show
approximately constant L*Delta(L), demonstrating z=1 before any fit of z.
Only after the nearest-neighbor gate passes is the same gate applied to the
validated K=24, alpha=0.5 long-range MPO.

## State targeting

Ground-state DMRG runs from both z-polarized and +x-polarized product states;
the lower accepted energy is retained. The first excited state is optimized
from a fresh state with TeNPy's `orthogonal_to=[psi0]`. Before scaling, this
method must pass ED energies and gaps, overlap `abs(<psi0|psi1>) < 1e-10`,
positive energy ordering, and independent convergence checks for both states.

## Diagnostics and acceptance

Use two-site DMRG, a chi schedule ending at the requested `chi_max`,
`max_E_err=1e-10`, `max_S_err=1e-8`, at least six and at most thirty sweeps,
and `svd_min=1e-12`. Persist the complete sweep statistics: energy and entropy
changes, maximum discarded weight, truncation-energy change, maximum chi, and
canonical norm error. Also report MPO variance and state overlap.

For the L=8,10,12 benchmark, require variance below 1e-10 and strict ED
agreement. For larger production calculations, variance is reported rather
than used as an unconditional hard cutoff; acceptance comes from variance,
discarded-weight, and chi-convergence trends together.

## Outputs

The benchmark command writes per-size JSON records, an aggregate CSV/JSON,
and vector/raster plots of Delta(L) and L*Delta(L). It never includes L=256
unless separately authorized.
