# Runnable scripts

- `validate_couplings.py` checks the exact finite-ring Hurwitz-zeta coupling
  against a symmetrically truncated direct image sum.
- `validate_exponential_fit.py` fits the infinite power-law kernel and writes
  K-resolved kernel and analytically periodized coupling error profiles.
- `benchmark_tfim.py` applies the shared two-site DMRG and orthogonal
  excited-state workflow to the periodic nearest-neighbor Pauli TFIM. Its
  default L=8,10,12 run performs the strict ED gate and writes incremental
  JSON, CSV, and Δ(L)/LΔ(L) plots.
- `validate_long_range_mpo.py` runs the Phase 5 three-layer comparison:
  exact Hurwitz-pair ED, dense compact-MPO ED, and compact-MPO DMRG. It
  records distance-resolved coupling errors, absolute/relative spectrum
  errors, and translation-averaged periodic ZZ correlations.
- `regenerate_sigma_fit.py` regenerates and validates one sigma fit family.
- `plan_phase6_scan.py` writes immutable pending cells and performs no compute.
- `run_phase6_cell.py` runs or resumes exactly one rotated-basis cell and
  preserves its raw correlations and diagnostics.
- `benchmark_phase6_optimizations.py` compares direct and staged-chi parity
  calculations, uses exact-zero MPO pruning, and writes provenance-safe HDF5
  checkpoints plus complete raw observables.

No command automatically launches the full long-range production grid.

Phase 7 uses `plan_phase7_scan.py` to prepare the validated local
reproduction's crossover exploration without launching TeNPy. Its fixed
scope is `sigma=1.50,1.60,1.70,1.75,1.80,1.90,2.00`, `K=24`, `chi=64`, and
`L=32,64`. The `broad`, `decide`, `gaps`, and `estimate` subcommands preserve
pending and failed work for resumability. The workflow makes no
thermodynamic-limit claim and never expands the Gamma grid automatically.
