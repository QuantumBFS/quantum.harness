# Phase 6 validated local reproduction: sigma=1.75

## Result

The fixed `L=32,64` R_xi crossing is stable:

| MPO fit | Crossing Gamma_x |
|---|---:|
| K=24 | 1.5633075241 |
| K=32 | 1.5633070351 |

The K-induced crossing shift is `-4.89e-7`. This is a two-size local
crossing, not a thermodynamic critical-field estimate.

## Separated numerical uncertainties

At `L=64`, the `chi=128 -> 256` refinement changes R_xi by
`+5.00e-8` at `Gamma=1.560` and `+4.82e-8` at `Gamma=1.565`. Relative gap
changes are `3.36e-8` and `2.45e-8`. The four `chi=256` states have
variances near `2e-9` and maximum discarded weights near `1e-10`.

At common `chi=128`, changing `K=24 -> 32` changes R_xi by
`-(3.94...4.03)e-7` at `L=32` and `-(1.10...1.14)e-6` at `L=64`. Relative
gap changes are `1.90...1.94e-6` at `L=32` and `5.35...5.57e-6` at `L=64`.
The MPO uncertainty is therefore larger than the measured MPS uncertainty,
but both leave the fixed-bracket crossing behavior unchanged.

The coupling reconstruction remains controlled. At `L=64`, the maximum
relative Hurwitz-zeta residual at `r=32` decreases from `8.28e-6` for K=24
to `7.61e-6` for K=32. At `L=32`, it changes from `2.29e-6` to `2.26e-6`.

## Runtime and scope

The four `K=24`, `chi=256` DMRG optimizations used 2.73 DMRG wall-hours in
total and peaked near 2.7 GiB per cell. The eight `K=32`, `chi=128`
optimizations used 1.16 DMRG wall-hours and peaked near 1.3 GiB per cell.
All cells were serialized, checkpointed, and run locally.

No `L>64`, `chi>256`, expanded Gamma grid, Slurm job, or approximate MPO
compression was used. The result supports a validated local reproduction
with separated MPS and MPO uncertainties; it does not claim thermodynamic
Gamma_c or z.

Machine-readable details are in `analysis.json`, `mps-uncertainty.csv`,
`mpo-uncertainty.csv`, `rxi-by-chi-k.csv`, and `fits/fit-summary.json`.
