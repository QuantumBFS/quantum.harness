# Phase 8 sigma=1.75 crossing review

## Locked setup

- Hamiltonian: pinned periodic Hurwitz-zeta LRTFIM in the rotated parity basis.
- Crossing cells: `L=128`, `Gamma={1.55,1.60}`, even parity.
- MPO/MPS: `K=24`, `alpha=0.5`, `r_fit=2048`, `chi=64`.
- Physical correlation: full `Sigmax-Sigmax` correlation without connected
  subtraction.

## Endpoint data

| Gamma | R_xi(L=64) | R_xi(L=128) | D=R_xi(64)-R_xi(128) |
|---:|---:|---:|---:|
| 1.55 | 0.3831356898 | 0.4231483721 | -0.0400126823 |
| 1.60 | 0.2482957595 | 0.1924798589 | +0.0558159006 |

The strict endpoint sign-change gate passes. Linear interpolation gives
`Gamma_x(64,128)=1.57087721697`. The Phase 7 result is
`Gamma_x(32,64)=1.56790394523`.

## Two-point sensitivity extrapolations

| sensitivity coordinate | Gamma_c |
|:---|---:|
| `1/L` | 1.57385048871 |
| `1/log(L)` | 1.58574357566 |

The absolute spread is `0.01189308695`. These are exact two-point sensitivity
extrapolations with no residual degrees of freedom. The coordinates do not
assume a known leading correction exponent. Their spread is not a confidence
interval and is not fully propagated into the future gap uncertainty.

## Cell diagnostics

| Gamma | total wall | peak RSS | DMRG wall | sweeps | reached chi | relative variance | discarded weight |
|---:|:---|---:|---:|---:|---:|---:|---:|
| 1.55 | 7:07 | 0.303 GiB | 189.84 s | 22/30 | 64 | 4.10e-9 | 4.93e-7 |
| 1.60 | 7:27 | 0.303 GiB | 212.21 s | 28/30 | 64 | 2.44e-9 | 3.49e-7 |

Both cells report success, remain below the sweep cap, and have complete
HDF5 checkpoints and raw `S(0)`, `S(k_min)`, `xi`, and `R_xi`. The variance
and discarded weights are recorded as exploratory `chi=64` diagnostics; the
strict final-state thresholds apply to the planned `chi=128` gap states.
Phase 7 found `chi=64 -> 128` changes in `R_xi` below the relevant crossing
uncertainty, which is the preregistered justification for using `chi=64`
here.

## Gate

No common-field gap specification or calculation is started until this
crossing result is reviewed.
