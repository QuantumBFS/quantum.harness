# Track B technical report

> Status: structure only. This is not the final technical report.

## 1. Scientific objective and final scope

- Challenge #86 Track B goals.
- Completed scope and explicitly unmet observables.

## 2. Hamiltonian and conventions

- Pinned periodic Hurwitz-zeta coupling.
- Rotated TeNPy operator convention and parity sectors.
- Exact and approximated finite-ring Hamiltonians.

## 3. Exponential fitting and MPO construction

- Phase 1 exact-coupling validation.
- Phase 2 variable-projection/NNLS development and tail-stability constraint.
- Phase 3 direct/wrapped channel construction and exact-zero pruning.

## 4. Solver validation

- Small-L ED, dense-MPO, and DMRG comparison.
- Nearest-neighbor benchmark.
- Checkpoint and continuation validation.

## 5. Numerical campaigns

- Local σ=1.75 reproduction.
- Phase 7 crossover exploration.
- Phase 8 σ=7/4 finite-size and critical-field sensitivity.
- Phase 9 NN, σ=2/3, σ=1.8, and σ=2.0 validation.

## 6. Dynamical-exponent estimator provenance

- Define the DMRG gap-based pairwise effective dynamical exponent and
  logarithmic midpoint `L_eff`.
- Distinguish it from Shiratani–Todo's QMC imaginary-time aspect-ratio
  estimator.
- Describe the power/log comparison as analogous correction analysis, not an
  identical estimator.

## 7. Accepted results

- Canonical machine-readable sources only; values will be populated after
  structure approval.

## 8. Superseded and diagnostic branches

- Preserve why each branch was superseded and what was learned.

## 9. Reproducibility

- Environment, commands, checkpoints, provenance fields, fit hashes, and code
  revisions.
- Local resource provenance: 32 GB host, recorded peak-memory bounds,
  campaign-level wall times, and the 1.76 h σ=1.8 gap campaign.
- Interpretation boundary for the L=128 DMRG versus L=362 QMC resource
  comparison.

## 10. Limitations

- Finite-size reach, correction sensitivity, and missing imaginary-time
  susceptibility.
