# Phase 9 Challenge Validation Design

## Status and review gate

Phase 9 adds challenge-required validation evidence without extending the
production finite-size campaign. This document fixes the proposed
Hamiltonians, fields, sizes, sectors, acceptance rules, outputs, and cost
ceiling. No Phase 9 physics calculation may start until this design is
reviewed and approved.

The recommended route is **reuse-first validation**:

1. reuse the accepted Phase 4 nearest-neighbor ED fixtures and Phase 7
   long-range crossing records;
2. compute only the missing nearest-neighbor crossing evidence and the two
   fixed-published-field mean-field gap benchmarks;
3. use the existing sigma=2.0 crossing as the second published critical-field
   benchmark;
4. stop rather than enlarge a grid when a preregistered validation is
   unresolved.

A fresh compact rerun of every benchmark would give uniform provenance but
would duplicate accepted calculations. A larger finite-size campaign would
improve extrapolations but contradicts the validation-only objective. Neither
alternative is selected.

## Shared numerical conventions

All new MPS calculations use finite-chain TeNPy DMRG with a finite OBC MPS.
The Hamiltonian may contain periodic ring interactions through its MPO. The
rotated parity basis is retained:

- physical `X` is TeNPy `Sigmaz`;
- physical `Z` is TeNPy `Sigmax`;
- the ground state is optimized in the even parity sector;
- the first excitation is optimized in the odd parity sector;
- the gap is `Delta=E_odd-E_even`.

Every cell records the Hamiltonian parameters, lattice, boundary convention,
operator convention, parity, `K`, `alpha`, `r_fit`, exponential-coefficient
hash, active MPO channels, requested and reached `chi`, sweep statistics,
energy, variance, discarded weight, runtime, memory, code hash, and checkpoint
provenance. Checkpoints are initialization states only and every reported
energy comes from a completed optimization at that cell's Hamiltonian.

For this phase, the accepted Phase 8 numerical gates remain:

- relative variance at most `1e-10`;
- discarded weight at most `1e-7`;
- positive gap and correct energy ordering;
- completion before the fixed sweep cap;
- no approximate MPO compression.

A failed gate is reported and the affected observable is marked
`numerically_unresolved`; it does not automatically increase `chi`, add a
size, or extend a Gamma window. Independent baseline cells continue so that
the complete validation report can be assembled. Only after all baseline
runs and reporting are complete may the user review the flags and authorize
any targeted `chi=128` calculation.

## 1. Nearest-neighbor limit

### Model and purpose

Use the periodic nearest-neighbor Pauli chain

```text
H = -sum_i Z_i Z_(i+1) - Gamma sum_i X_i,
```

with `J=1`. This benchmark must recover the exact critical point
`Gamma_c=1` and show gap behavior consistent with `z=1`. It validates the
Hamiltonian, parity-sector gap construction, crossing interpolation, and
scaling pipeline. The small-size result is not a precision reproduction of
the asymptotic exponent.

The accepted Phase 4 `L=8,10,12` ED/DMRG fixtures remain the operator,
normalization, and excited-state-targeting gate. They are not rerun.

### Missing critical-point evidence

Use:

```text
L = 16, 32, 64
Gamma = 0.98, 1.00, 1.02
chi = 64
sector = even, odd
```

Both parity sectors are recorded at all nine `(L,Gamma)` points for uniform
provenance. Only the even-sector `R_xi` values enter the crossing, and only
the `Gamma=1` even/odd pairs enter the gap scaling.

For each size pair `(16,32)` and `(32,64)`, define

```text
D_L(Gamma) = R_xi(L,Gamma) - R_xi(2L,Gamma).
```

Require an actual sign change between adjacent fixed-grid values. When
bracketed, obtain `Gamma_x(L,2L)` by linear interpolation between those two
points and record the two interpolation points plus the half-grid resolution
`0.01`. If either crossing is unbracketed or multiple brackets occur, mark
the NN crossing unresolved and stop for review. Do not extend the grid.

### Gap and z benchmark

Use the exact benchmark field `Gamma=1` for all gaps. Use the independently
optimized even and odd states at that grid point for `L=16,32,64`.
Report:

```text
Delta(L) = E_odd(L) - E_even(L)
z_eff(L,2L) = -log[Delta(2L)/Delta(L)]/log(2)
Delta(L) = A L^(-z)                 (three-size direct regression)
```

Here `z_eff` is the gap-based pairwise effective dynamical exponent used by
the DMRG route. It should not be called `z(L)` or attributed to
Shiratani--Todo's QMC aspect-ratio estimator.

Also report `L*Delta(L)`, which should be approximately size-independent.
The crossing estimates and the exact-field gap benchmark are separate
observables; the crossing result is not substituted into the gap field.

### Numerical convergence

The baseline is `chi=64`. Report sector-resolved energy, variance, discarded
weight, reached `chi`, runtime, and sweep termination. Flag failed cells in
the complete report. Do not automatically run `chi=128`; any targeted
refinement is a separate post-report decision. No `chi=256` NN calculation is
planned.

## 2. Mean-field limit

### Model and external benchmarks

Use the pinned periodic Hurwitz-zeta long-range Hamiltonian

```text
H = -sum_(i<j) J_L(j-i;sigma) Z_i Z_j - Gamma sum_i X_i
```

Use exactly two external published critical fields:

```text
sigma = 2/3, Gamma_c = 3.673, expected z = 1/3
sigma = 0.4, Gamma_c = 5.85, expected z = 0.2
```

These fields test the prediction `z=sigma/2` for `sigma<=2/3`. This branch
does not determine a thermodynamic critical field independently and performs
no Gamma scan, refinement, crossing interpolation, or field optimization.

### MPO and size protocol

Regenerate the infinite-kernel exponential fit independently for each sigma
with:

```text
K = 24
alpha = 0.5
r_fit = 2048
exact-zero channel pruning = enabled
approximate MPO compression = disabled
```

Before DMRG, record each lambda/coefficient hash and validate periodized
coupling reconstruction for every target size:

```text
L = 16, 32, 64, 96.
```

Before sigma=0.4 DMRG, compare `K=24` and `K=32` at `L=64,96`. K=32 must
reduce the maximum finite-ring coupling error below approximately 1% to
qualify that branch. The observed errors are 5.9999% at `L=64` and 7.0564%
at `L=96`, so sigma=0.4 fails this gate and no DMRG is run. It remains a
documented MPO-limited validation.

Sigma=2/3 remains unchanged at `K=24`. Run even and odd sectors at its fixed
field with baseline `chi=64`. Report four raw gaps, the three adjacent-pair
`z_eff` values, `L^(1/3)*Delta`, and the simple four-size estimate from
`Delta=A L^(-z)`.

These branches report only the dynamical exponent `z=sigma/2`. They do not
calculate or report `beta/nu`, `gamma/nu`, or any equal-time proxy under
either label.

Flag every state that fails a numerical gate, but complete the remaining
baseline and final report first. Do not automatically run `chi=128`.
Targeted refinement requires a separate post-report review. `chi=256` is not
part of this design.

## 3. Second published critical-field benchmark

Use `sigma=2.0`, not `sigma=1.8`, because the accepted Phase 7 data already
provide the complete benchmark without a new calculation:

```text
Phase 7 Gamma_x(32,64) = 1.428411
broad fixed bracket = [1.40, 1.45]
crossing resolution = 0.025
Table II Gamma_c = 1.4208(2)
```

The finite-size difference is `+0.007611`, or approximately `+0.54%`, and is
smaller than the preregistered broad-grid resolution. Phase 7 selective
`chi=64 -> 128` validation already showed that the bracket and the sign
structure of `D_sigma(Gamma)` remain unchanged, with `R_xi` shifts below
`4e-6`.

The final report must label this as a finite-size crossing comparison, not an
exact reproduction or precision thermodynamic estimate. If reviewers require
a narrower resolution, Phase 9 stops for review; it does not automatically
refine Gamma.

Together with the completed `sigma=1.75`, `Gamma_c=1.5609(3)` external
benchmark, this supplies two Table II critical-field comparisons.

## 4. Analysis and final validation report

The final report has four sections.

### A. Method validation

- accepted Phase 4 ED fixtures and the new NN `Gamma_x`, `L*Delta`, and `z`;
- sigma=2/3 fixed-published-field gaps and `z`;
- sigma=0.4 K=24/K=32 coupling qualification and the resulting limitation;
- sigma=1.75 and sigma=2.0 Table II `Gamma_c` comparisons.

### B. Long-range critical scaling

- the completed sigma=1.75 result;
- self-consistent `Gamma_c_power=1.5738504887054727` versus external
  `Gamma_c_ST=1.5609`;
- direct power-law, `1/L`, and `1/log(L)` z sensitivity estimates.

### C. Numerical uncertainty

- coupling-level and physics-level `K=24 -> 32` MPO changes;
- sector-resolved `chi=128 -> 256` MPS changes;
- ground-state and excited-state variance/discarded-weight records
  separately;
- finite-size and critical-field sensitivity kept distinct from MPO/MPS
  truncation.

### D. Limitations

- no `L=256`;
- no new sigma scan;
- no thermodynamic extrapolation from the Phase 7 two-size crossings;
- no precision `z=1` claim from the modest NN sizes;
- no zero-frequency susceptibility exponent `gamma/nu`, because the
  ground-state DMRG workflow does not compute imaginary-time-integrated
  correlations;
- equal-time `S_eq(0)` is only an auxiliary structure-factor diagnostic and
  is never labeled `gamma/nu`.

## Resumability and output layout

Each calculation is one independently restartable directory with an atomic
summary and HDF5 checkpoint:

```text
results/phase9-validation/
  proposal/
    cost-estimate.json
    execution-order.md
  nn-limit/
    run_spec.json
    cells/
    analysis/
  mean-field-fixed-fields/
    fits/
      sigma-2over3/
      sigma-0p4/
    run_spec.json
    cells/
    analysis/
  published-gamma/
    analysis/
  final-report/
```

Planning, execution, and reporting are separate commands. The planner skips
accepted cells by stable cell identifier and never infers a new field or
size from partial results.

The cost estimate retains the previously approved local-only campaign route.
This is an explicit deviation from the harness's usual remote-compute default
for work exceeding ten minutes. Serial execution, incremental summaries, and
checkpoints keep the revised 56-minute conservative baseline bounded and
resumable.

## Stop conditions

Stop and request review if:

- a fixed NN crossing has no unique sign-change bracket;
- either mean-field MPO fit fails coupling validation;
- the completed baseline report contains a numerical-convergence flag that
  blocks a required conclusion;
- a report would require a new Gamma point, `L>128`, `chi>256`, `K=32`, or a
  new sigma;
- the projected baseline local wall time exceeds the cost ceiling in the
  approved estimate.
