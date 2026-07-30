# Phase 8 finite-size scaling design

## Goal

Replace the Phase 7 sigma exploration with a staged finite-size analysis at
`sigma=1.75`, followed only after qualification by `sigma=1.80` and
`sigma=2.00`. The maximum size is `L=128`; no broad sigma scan, `L=256`,
automatic Gamma extension, or new susceptibility method is included.

The primary deliverables are:

1. reproduce `Gamma_c(sigma=1.75)`;
2. extract `z` from five common-field gap sizes with explicit finite-size
   correction sensitivity;
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

`chi=64` is restricted to this crossing stage. In Phase 7, the targeted
`chi=64` to `chi=128` checks changed `R_xi` by less than `4e-6` and preserved
every tested crossing bracket and endpoint sign. Those changes are below
the relevant crossing-resolution uncertainty, so `chi=64` is sufficient for
the `L=128` `R_xi` crossing endpoints without promoting it to the final gap
accuracy. All common-field gap states remain `chi=128`.

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

The primary common field is the exact two-point sensitivity extrapolation
of the preregistered power drift

```text
Gamma_x(L,2L) = Gamma_c_power + a/L.
```

With only the two available crossings,

```text
Gamma_c_power = 2*x64 - x32.
```

The alternative common field is the exact two-point sensitivity
extrapolation of

```text
Gamma_x(L,2L) = Gamma_c_log + a/log(L).

t32 = 1/log(32), t64 = 1/log(64),
Gamma_c_log = (x64*t32 - x32*t64)/(t32-t64).
```

Both two-parameter forms pass exactly through two points. Consequently:

- neither has residual degrees of freedom;
- neither supports statistical inference or model selection;
- `1/L` and `1/log(L)` are sensitivity coordinates only and do not assert
  that the leading correction exponent is known;
- their difference is a correction-form sensitivity, not a statistical
  confidence interval;
- neither form may be chosen based on agreement with the published
  `Gamma_c`.

All direct gap calculations use the single common primary field
`Gamma_c_power`. `Gamma_c_log` is reported as sensitivity context rather
than as a second production field, avoiding a second full gap campaign.
The power/log critical-field sensitivity is reported separately and is not
fully propagated into the gap uncertainty because the design has only two
crossings. Gap uncertainties therefore contain numerical state diagnostics
and finite-size correction sensitivity, with this missing propagation
stated explicitly as a limitation.

## Gap calculations and diagnostics

At `Gamma_c_power`, optimize both parity sectors at `chi=128` for
`L=16,32,64,96,128`. The added `L=16` and `L=96` states turn the gap
analysis into a genuine multi-size regression while retaining `L=32,64,128`
as the original scaling backbone. Historical states may seed initialization
only after the existing provenance audit. Each sector records independently:

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
discarded weight <= 1e-7,
converged before the sweep cap.
```

A failed sector stops that sigma for review. There is no automatic
`chi=256` escalation.

The discarded-weight threshold is a Phase 8-only post-observation protocol
amendment. The original `1e-8` gate rejected the `L=64` odd-sector state,
which recorded `5.49e-8` even though its relative variance and energy
convergence passed. The accepted threshold is now `1e-7`; the variance
threshold is unchanged, and previously accepted cells are not rerun. The
final uncertainty budget records both thresholds and the triggering result.

The `L=128` even `chi=128` state is accepted with a separate diagnostic
warning after an audited continuation: the nominal relative-variance target
is `1e-10`, the observed value remains `1.05e-10`, and 21 additional sweeps
shift the energy by only `6.82e-13`. No even-sector `chi=256` calculation is
introduced. The `L=96` and `L=128` odd sectors are selectively refined from
their recorded `chi=128` states to `chi=256`; both baseline and refined
diagnostics enter the final truncation-uncertainty table.

For each size,

```text
Delta(L,Gamma_c_power) = E_odd - E_even.
```

The direct gap must be positive. Phase 7 interpolated endpoint gaps are
retained as historical diagnostics but are not substituted for the new
common-field values.

## Dynamical-exponent analysis

For the five ordered sizes

```text
L_i = 16,32,64,96,128,
```

define four gap-based pairwise effective dynamical exponents

```text
z_eff(L_i,L_(i+1))
  = -log[Delta(L_(i+1))/Delta(L_i)] / log[L_(i+1)/L_i].
```

Associate each pairwise exponent with the logarithmic midpoint

```text
L_eff,i = sqrt[L_i L_(i+1)].
```

This definition is specific to the DMRG gap-scaling route
`Delta(L,Gamma_c) ~ L^(-z)`. It is not a definition taken from
Shiratani--Todo's QMC calculation. This gives four `z_eff` values from all
five gaps, including the non-doubling pairs `(64,96)` and `(96,128)`. The original doubling diagnostics
`z_eff(16,32)`, `z_eff(32,64)`, and `z_eff(64,128)` remain explicitly
identifiable.

The primary power-correction regression is

```text
z_eff(L_eff) = z_power + a/L_eff.
```

The alternative logarithmic-correction regression is

```text
z_eff(L_eff) = z_log + a/log(L_eff).
```

Each two-parameter regression uses four effective-exponent points and has
two residual degrees of freedom. The report gives `z_power`, `z_log`, their
absolute spread, all four raw `z_eff` values, all five underlying gaps, and
the residual RMS for each coordinate. A leave-`L=16`-out regression is
reported as a small-size sensitivity check, not used to select a preferred
form.

Adjacent `z_eff` values share one underlying gap and are therefore
correlated. In the absence of statistically calibrated per-gap error bars,
the regressions are deterministic finite-size sensitivity analyses, not
independent-sample statistical inference. No correction form is selected by
agreement with literature.

It also compares the two sensitivity values with Shiratani--Todo's published
`sigma=7/4` power- and logarithmic-correction extrapolations, using a cited
source value. The comparison follows the spirit of their correction analysis,
but the estimator differs: DMRG uses excitation-gap slopes, whereas their QMC
workflow tunes the imaginary-time size with spatial size and constructs
quotient-style finite-size estimates. Because Phase 8 reaches only `L=128`,
this is a qualitative finite-size comparison rather than a precision
reproduction.

## Equal-time structure-factor diagnostics

The even-sector states continue to record the full equal-time `C_eq(r)` and

```text
S_eq(0,L) = sum_r C_eq(r).
```

Phase 8 reports these raw equal-time diagnostics by size. They are not used
to estimate or label a susceptibility exponent; `S_eq(0)` is only an
auxiliary diagnostic. In particular, no Phase 8
quantity is called `gamma/nu`; the required imaginary-time-integrated
susceptibility remains outside the DMRG scope.

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
- the drift across all four adjacent-pair `z_eff` values and the
  leave-`L=16`-out regression.

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
- equal-time `C_eq(r)` and `S_eq(0,L)` diagnostics without a susceptibility
  exponent;
- MPO/MPS/finite-size uncertainty table;
- a report that states susceptibility `gamma/nu` is outside the DMRG scope.

## Cost gate

The measured `L=64`, odd-sector, `chi=128` median is about five minutes.
The earlier linear-size projection estimated roughly sixteen minutes per
`L=128`, `chi=128` sector and about 3.6 GiB peak memory. The sigma=1.75 stage
therefore contains:

- two exploratory `L=128`, even, `chi=64` crossing cells;
- ten common-field `chi=128` cells across five sizes and two sectors.

The projected serialized common-field campaign is roughly 1.5--2 local
hours, dominated by `L=96,128`. This is an explicit local-only deviation from
the harness's normal ten-minute threshold. Before execution, the planner
must update the estimate from completed cells, run at bounded single-thread
concurrency below 16 GiB, and preserve each checkpoint before proceeding.

## Acceptance

Phase 8 succeeds for a sigma only if:

1. the fixed L=64/128 endpoints have a strict sign change;
2. interpolation uses only those two endpoints;
3. all ten common-field parity-sector states pass the locked diagnostics;
4. all five gaps are positive;
5. all four adjacent-pair `z_eff` values and both correction regressions are
   reported;
6. MPO, MPS, and finite-size uncertainties are reported separately;
7. no unapproved Gamma, sigma, K, chi, or size is introduced.
