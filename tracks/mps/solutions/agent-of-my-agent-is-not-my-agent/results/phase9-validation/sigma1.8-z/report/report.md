# Phase 9 sigma=1.8 dynamical-exponent validation

Gamma_c=1.5288 is an external Shiratani-Todo benchmark field. This calculation validates finite-size gap scaling and does not independently determine Gamma_c.

| L | E_even | E_odd | Delta | accepted |
|---:|---:|---:|---:|:---:|
| 16 | -28.1040851223 | -27.8387016094 | 0.265383513 | True |
| 32 | -56.079159178 | -55.935073651 | 0.144085527 | True |
| 64 | -112.08547598 | -112.008080249 | 0.0773957317 | True |
| 96 | -168.106356102 | -168.052782054 | 0.0535740473 | True |
| 128 | -224.131209352 | -224.090013029 | 0.0411963226 | False |

Gap-based pairwise effective dynamical exponents: 16_32: 0.881153, 32_64: 0.896600, 64_96: 0.907271, 96_128: 0.913216.
Finite-size sensitivity estimates using L_eff=sqrt(L1*L2): z_power=0.918948, z_log=0.974931.
Shiratani-Todo comparison: z_power≈0.93 and z_log≈1.00. The power/log
comparison follows the spirit of their finite-size correction analysis, but
the estimator differs: DMRG uses excitation gaps and their QMC
aspect-ratio-tuning procedure uses the tuned imaginary-time size. This is a
validation comparison only, not a precision reproduction claim.
Convergence: 9/10 states pass the nominal gates; warnings: L=128 even: relative_variance.

## Numerical scope

K=24, chi=128, exact-zero MPO pruning, no approximate MPO compression, no Gamma search, no K=32 comparison, and no automatic chi increase.
