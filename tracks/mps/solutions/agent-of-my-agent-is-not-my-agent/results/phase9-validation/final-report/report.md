# Phase 9 validation report

Here z is obtained from excitation-gap scaling. The gap-based pairwise
effective dynamical exponents are
z_eff(L1,L2)=-log[Delta(L2)/Delta(L1)]/log(L2/L1), with
L_eff=sqrt(L1*L2) used only as this DMRG analysis's logarithmic midpoint
convention. Power/log sensitivity comparisons follow the spirit of
Shiratani--Todo's finite-size correction analysis, while the underlying
estimator differs from their QMC aspect-ratio tuning procedure.

## Method validation

- NN TFIM: **complete_with_warnings**. This checks the Hamiltonian and crossing/gap-scaling pipeline; it is not a precision reproduction of z=1 from the modest sizes.
- Mean-field σ=2/3 at external Γc=3.673: **complete_with_warnings**; assessment `qualitative_consistency_with_convergence_warnings`.
- Mean-field σ=0.4 at external Γc=5.85: **excluded_mpo_bias**; target z=0.2.
- Second published-field benchmark: the reused σ=2.0 Phase 7 crossing is Γₓ(32,64)=1.428411203, versus the published Γc=1.4208. This is a finite-size crossing comparison, not an exact reproduction.

### Nearest-neighbor limit

Hamiltonian: H=-sum_i Z_i Z_(i+1)-Gamma sum_i X_i on the periodic ring, with even/odd parity-sector DMRG.
Crossings: Gamma_x(16,32)=0.997160, Gamma_x(32,64)=0.999281; exact Gamma_c=1.

| L | E_even | E_odd | Delta at Gamma=1 |
|---:|---:|---:|---:|
| 16 | -20.4045944748 | -20.3063407752 | 0.0982536995 |
| 32 | -40.7600324939 | -40.7109352496 | 0.0490972442 |
| 64 | -81.49551258 | -81.4709676793 | 0.0245449006 |

Gap-based pairwise effective dynamical exponents = 16_32: 1.000870, 32_64: 1.000219.
Simple three-size estimate: z=1.000544; expected z=1.
Convergence: 17/18 cells pass the nominal convergence gates; diagnostic warning retained without rerun: L=64, Gamma=1, even: relative_variance.
This is a small-size scaling-pipeline validation, not a high-precision thermodynamic extrapolation.

### Sigma=2/3 mean-field gap benchmark

Gamma_c=3.673 is an external published benchmark. This calculation tests z=sigma/2 and does not independently determine Gamma_c.

| L | E_even | E_odd | Delta | accepted |
|---:|---:|---:|---:|:---:|
| 16 | -61.0184841384 | -59.0648877635 | 1.95359637 | True |
| 32 | -121.392206338 | -119.904189266 | 1.48801707 | True |
| 64 | -242.181098551 | -241.030339989 | 1.15075856 | False |
| 96 | -362.998297449 | -362.000573323 | 0.997724126 | False |

Gap-based pairwise effective dynamical exponents = 16_32: 0.392741, 32_64: 0.370806, 64_96: 0.351941.
Simple four-size estimate: z=0.375314; expected z=0.333333.
Finite-size correction sensitivity using L_eff=sqrt(L1*L2): z_power=0.339081, z_log=0.253069. With only three z_eff values, these are sensitivity estimates, not statistically reliable extrapolations.

## Long-range critical scaling

The σ=1.75 self-consistent and published-field branches remain separate sensitivity analyses.

## Numerical uncertainty

MPO K=24/K=32 bias, even-sector MPS error, odd-sector MPS error, and finite-size/critical-field sensitivity are reported as separate uncertainty sources in the supplied Phase 8 artifacts.

## Limitations

The zero-frequency susceptibility exponent gamma/nu is not measured: this ground-state DMRG workflow has no imaginary-time integration. Equal-time S_eq(0) is only an auxiliary diagnostic.
No L=256 calculation, broad sigma scan, or automatic chi=128 refinement is part of Phase 9.

## Track B readiness checklist

- NN Hamiltonian and scaling pipeline: complete_with_warnings.
- Mean-field σ=2/3 z benchmark: complete_with_warnings.
- Published-field comparisons: σ=1.75 and σ=2.0 documented.
- Unmet observable: zero-frequency susceptibility gamma/nu is outside the ground-state DMRG scope.
- Precision limitation: no thermodynamic-limit claim from Phase 9.
