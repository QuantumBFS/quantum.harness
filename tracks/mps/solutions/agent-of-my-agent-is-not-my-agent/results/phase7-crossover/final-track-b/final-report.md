# Challenge #86 Track B: validated local MPS deliverable

This bounded local reproduction uses the pinned periodic Hurwitz-zeta coupling, a custom periodized exponential MPO, and parity-resolved TeNPy DMRG. It reports finite-size results through L=64 and makes no thermodynamic-limit crossover claim.

## Gamma crossing trend

| sigma | Gamma_x(32,64) | grid resolution |
|---:|---:|---:|
| 1.50 | 1.769269830 | 0.025 |
| 1.60 | 1.679839625 | 0.025 |
| 1.70 | 1.598397279 | 0.025 |
| 1.75 | 1.567903945 | 0.025 |
| 1.80 | 1.535384903 | 0.025 |
| 1.90 | 1.478573839 | 0.025 |
| 2.00 | 1.428411203 | 0.025 |

## Validated two-size gap exponents

| sigma | Delta(32) | Delta(64) | gap-based pairwise z_eff | change from chi=64 |
|---:|---:|---:|---:|---:|
| 1.60 | 0.20948120 | 0.12773870 | 0.713625 | n/a |
| 1.75 | 0.16784045 | 0.09996866 | 0.747543 | 1.324e-05 |
| 1.80 | 0.15647664 | 0.09258157 | 0.757150 | 1.313e-05 |
| 2.00 | 0.12653832 | 0.07523604 | 0.750078 | 1.198e-05 |

The sigma=1.60 estimate is incomplete because both L=64 chi=128 odd-sector endpoints retain discarded-weight flags; the other three requested sigma points pass the selective excited-state criteria.

## Two-size structure-factor estimates

| sigma | S(0), L=32 | S(0), L=64 | gamma/nu estimate |
|---:|---:|---:|---:|
| 1.75 | 10.37625403 | 16.63909537 | 0.681291 |
| 1.80 | 10.60934401 | 17.01573017 | 0.681534 |
| 2.00 | 11.34930793 | 18.39765144 | 0.696917 |

These gamma/nu values are two-size estimates from equal-time S(0) scaling at the broad-grid crossing, not extrapolated critical exponents.

## Error separation

- MPO: K=24 to K=32 changes the validated relative gap by at most 5.57e-06 and R_xi by 1.14e-06.
- MPS: chi=128 to chi=256 changes the validated relative gap by at most 3.36e-08 and R_xi by 5.00e-08.
- Finite size is dominant: only L=32,64 enter z_eff and gamma/nu, and Gamma_x has broad-grid resolution 0.025.

## Completed

- Hurwitz-zeta periodic convention and exponential MPO.
- NN TFIM and small-system long-range validation.
- Gamma_x(sigma) crossover scan.
- Selectively converged odd-sector gap-based pairwise effective dynamical
  exponents.

## Limitations

- No L=256 scaling and no thermodynamic Gamma_c extrapolation.
- No new K=32, L=128, or Gamma-refinement calculation.
- The gamma/nu values are finite-size structure-factor estimates.
