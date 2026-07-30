# Data dictionary

All tabular and JSON outputs use UTF-8 text. Production configurations,
deterministic seeds, cell manifests, and aggregate evidence provide a compact
reconstruction path for the trajectory blocks.

## results/central_charge_estimates.csv

- model: calibration model.
- run: benchmark, production, or calibration-extension provenance.
- fit: finite-size ansatz. L^-1+L^-3 fits
  \(F(L)=aL+b/L+d/L^3\); L^-1_only sets \(d=0\).
- lengths: circumferences entering the fit.
- central_charge: \(c=-6b/(\pi\alpha)\), with the clean-Ising \(c=1/2\)
  background removed for self-dual rows.
- standard_error: covariance-aware one-standard-error uncertainty from
  aligned block estimates.
- target and target_standard_error: challenge reference coordinates.
- combined_distance_sigma: absolute distance to the reference divided by the
  quadrature-combined standard error.
- stage: scientific role of the coordinate in the convergence program.
- interpretation: concise provenance and next-use description.

## results/production_resolution.csv

Observer-dependent central charge as a function of channel and
information-loss parameter. Samples counts aligned blocks entering the GLS
fit.

## results/self_dual_extension_resolution.csv

Independent identity-channel calibration through circumference 24. Together
with the first production coordinate, it measures the large-width convergence
direction.

## results/measurement_rg_commutator.json

Exact and optimized statistical-deficiency witnesses for the local
measurement-RG comparison. TV denotes total variation distance; KL values use
nats. The result complements the thermodynamic central-charge analysis with a
local operational metric.

## results/submission_summary.json

Machine-readable headline results, execution census, capability map,
innovation map, and next-stage compute priorities.
