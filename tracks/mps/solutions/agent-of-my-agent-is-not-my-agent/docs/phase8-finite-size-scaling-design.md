# Phase 8 finite-size scaling design

## Goal

Replace the Phase 7 sigma exploration with a staged finite-size analysis at
`sigma=1.75`, followed only after qualification by `sigma=1.80` and
`sigma=2.00`. The maximum size is `L=128`; no broad sigma scan, `L=256`,
automatic Gamma extension, or new susceptibility method is included.

The primary deliverables are:

1. reproduce `Gamma_c(sigma=1.75)`;
2. extract `z` with explicit finite-size correction sensitivity;
3. keep MPO, MPS, and finite-size uncertainties quantitatively separate.

## Locked physics convention

The Hamiltonian remains

```text
H = -sum_{i<j} J_L(j-i;sigma) Z_i Z_j - Gamma sum_i X_i,
```

with the pinned periodic Hurwitz-zeta image sum. TeNPy uses the rotated
parity basis `X_phys=Sigmaz` and `Z_phys=Sigmax`. Ground and first-excited
states are optimized in the even and odd parity sectors, respectively. The
MPO uses `K=24`, `alpha=0.5`, `r_fit=2048`, exact-zero channel pruning, and
no approximate compression.

Shiratani--Todo's susceptibility uses the zero-frequency imaginary-time
integral

```text
S(0,0) = sum_r integral d tau C(r,tau),
```

which the validated workflow does not calculate. Phase 8 will not implement
imaginary-time evolution, a correction-vector solver, or another
unvalidated approximation. The Track B susceptibility `gamma/nu` therefore
remains unmeasured and is not a Phase 8 output. The Phase 7 equal-time
structure-factor data remain archived, with their corrected name, but are
not used to claim or infer `gamma/nu`.

## Staged sigma gate

The execution order is fixed:

1. Complete all `sigma=1.75` crossing, gap, and reporting gates.
2. Review its runtime, memory, and convergence.
3. Proceed to `sigma=1.80`.
4. Proceed to `sigma=2.00`.

No later sigma starts before the preceding stage succeeds. `sigma=1.60` is
outside the locked scope.

## L=128 crossing protocol

Phase 7 supplies `Gamma_x(32,64)` and its two endpoint bracket:

| sigma | fixed Gamma endpoints |
|---:|:---|
| 1.75 | 1.55, 1.60 |
| 1.80 | 1.50, 1.55 |
| 2.00 | 1.40, 1.45 |

For each qualified sigma, run only the two `L=128`, even-sector, `chi=64`
endpoint cells. Reuse compatible checkpoints only as initialization and
fully reoptimize with the current code.

At each endpoint define

```text
D_64,128(Gamma) = R_xi(64,Gamma) - R_xi(128,Gamma).
```

Linear interpolation is allowed only when the two values have a strict sign
change:

```text
D_left * D_right < 0.
```

If this condition fails, record the endpoint data, mark the sigma
`unresolved_no_L64_L128_bracket`, and stop for user review. Do not add or
move Gamma points.

## Common critical-field estimates

Let

```text
x32 = Gamma_x(32,64),
x64 = Gamma_x(64,128).
```

The primary common field is the intercept of the preregistered power drift

```text
Gamma_x(L,2L) = Gamma_c_power + a/L.
```

With only the two available crossings,

```text
Gamma_c_power = 2*x64 - x32.
```

The sensitivity field is the intercept of

```text
Gamma_x(L,2L) = Gamma_c_log + a/log(L).

t32 = 1/log(32), t64 = 1/log(64),
Gamma_c_log = (x64*t32 - x32*t64)/(t32-t64).
```

Both two-parameter forms pass exactly through two points. Consequently:

- neither has residual degrees of freedom;
- no goodness-of-fit or model selection is reported;
- their difference is a correction-form sensitivity, not a statistical
  confidence interval;
- neither form may be chosen based on agreement with the published
  `Gamma_c`.

All direct gap calculations use the single common primary field
`Gamma_c_power`. `Gamma_c_log` is reported as sensitivity context rather
than as a second production field, avoiding a second full gap campaign.

## Gap calculations and diagnostics

At `Gamma_c_power`, optimize both parity sectors at `chi=128` for
`L=32,64,128`. Historical states may seed initialization only after the
existing provenance audit. Each sector records independently:

- energy and variance;
- relative variance;
- discarded weight;
- requested and reached chi;
- sweep count and sweep state;
- wall time and memory;
- fit, MPO, operator, lattice, checkpoint, and code hashes.

The existing numerical flags remain:

```text
relative variance <= 1e-10,
discarded weight <= 1e-8,
converged before the sweep cap.
```

A failed sector stops that sigma for review. There is no automatic
`chi=256` escalation.

For each size,

```text
Delta(L,Gamma_c_power) = E_odd - E_even.
```

The direct gap must be positive. Phase 7 interpolated endpoint gaps are
retained as historical diagnostics but are not substituted for the new
common-field values.

## Dynamical-exponent analysis

The two-size diagnostics are

```text
z_eff(32,64)  = -log[Delta(64)/Delta(32)]/log(2),
z_eff(64,128) = -log[Delta(128)/Delta(64)]/log(2).
```

These are reported separately from extrapolated sensitivities. With
`z32=z_eff(32,64)` and `z64=z_eff(64,128)`, the power-correction
sensitivity is the exact two-point intercept of

```text
z_eff(L,2L) = z_power + a/L,
z_power = 2*z64 - z32.
```

The logarithmic sensitivity is the exact two-point intercept of

```text
z_eff(L,2L) = z_log + a/log(L).

t32 = 1/log(32), t64 = 1/log(64),
z_log = (z64*t32 - z32*t64)/(t32-t64).
```

As for the critical-field drift, these are not statistically distinguishable
fits. The report gives `z_power`, `z_log`, their absolute spread, the two raw
`z_eff` values, and all underlying gaps. It makes no correction-form
selection.

## Numerical uncertainty budget

MPO uncertainty uses the completed `sigma=1.75`, `K=24` versus `K=32`
comparison at fixed `chi=128`: distance-resolved coupling reconstruction,
crossing shift, gap shift, and `R_xi` shift. Phase 8 does not repeat `K=32`
at `L=128`.

MPS uncertainty uses two layers:

1. the completed `sigma=1.75`, `chi=128` versus `chi=256` comparison at
   `L=64`;
2. per-sector variance, discarded weight, reached chi, and convergence at
   every new `chi=128` common-field state.

These numerical errors are reported separately from:

- crossing grid/interpolation resolution;
- power-versus-log critical-field sensitivity;
- power-versus-log `z` sensitivity;
- the change from `z_eff(32,64)` to `z_eff(64,128)`.

No new `K=32` or `chi=256` calculation is automatic. A failed numerical
gate stops for review rather than being absorbed into finite-size error.

## Resumability and outputs

Use one independent directory per sigma and cell:

```text
results/phase8-scaling/
  sigma-1.75/
    crossing-L128/
    gaps-common-Gamma/
    analysis/
  sigma-1.80/
  sigma-2.00/
```

Every cell writes an incremental summary, HDF5 checkpoint, raw correlations,
`S_eq(0)`, `S(k_min)`, `xi`, `R_xi`, convergence diagnostics, timing, and
provenance before analysis begins.

The final analysis produces:

- crossing endpoint and interpolation CSV;
- common-field power/log sensitivity table;
- sector-separated gap diagnostic CSV;
- `z_eff` and power/log sensitivity table and plot;
- MPO/MPS/finite-size uncertainty table;
- a report that states susceptibility `gamma/nu` is outside the DMRG scope.

## Cost gate

The measured `L=64`, odd-sector, `chi=128` median is about five minutes.
The earlier linear-size projection estimated roughly sixteen minutes per
`L=128`, `chi=128` sector and about 3.6 GiB peak memory. Each sigma therefore
contains:

- two exploratory `L=128`, even, `chi=64` crossing cells;
- six common-field `chi=128` cells across three sizes and two sectors.

This exceeds the harness's normal ten-minute local-compute threshold when
serialized. Before execution, the planner must use the measured
`sigma=1.75` crossing cells to update the estimate, run at bounded
single-thread concurrency below 16 GiB, and stop after `sigma=1.75` for the
required review.

## Acceptance

Phase 8 succeeds for a sigma only if:

1. the fixed L=64/128 endpoints have a strict sign change;
2. interpolation uses only those two endpoints;
3. all six common-field parity-sector states pass the locked diagnostics;
4. all three gaps are positive;
5. both raw `z_eff` values and both correction sensitivities are reported;
6. MPO, MPS, and finite-size uncertainties are reported separately;
7. no unapproved Gamma, sigma, K, chi, or size is introduced.
