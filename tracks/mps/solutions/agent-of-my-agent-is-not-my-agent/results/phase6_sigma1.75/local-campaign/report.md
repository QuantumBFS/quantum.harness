# Phase 6 local pilot: σ=1.75

The direct χ=128 pilot used the periodized K=24 exponential MPO with 21
nonzero channels (χ_MPO=44), HDF5 checkpoints, and no approximate MPO
compression.

## Physics output

- The L=32 and L=64 Rξ curves change order between Γ=1.560 and 1.565.
  Preregistered linear interpolation gives the provisional two-size crossing
  Γ×(32,64)=1.5633075241.
- At Γ=1.560, Δ(32)=0.1530992101 and Δ(64)=0.08246281685. Their two-size
  gap-based pairwise diagnostic is z_eff(32,64)=0.8926511908; it is not a
  production z estimate.
- The L=64 even/odd discarded weights are 2.53×10⁻⁹ and 4.31×10⁻⁸, and
  variances are about 2×10⁻⁷. The odd state therefore fails the locked 10⁻⁹
  discarded-weight gate and requires targeted χ refinement before inference.

## Local feasibility

Measured even-sector DMRG time rose from 176 s at L=32 to 581 s at L=64.
The empirical length exponent 1.72 projects an L=128 even calculation to
about 31.9 minutes and an even-plus-odd pair to about 63.8 minutes at χ=128.
Because high-χ refinement is already required at L=64, L=128 is outside the
current local-campaign threshold and should not be launched automatically.

The complete machine-readable values are in `analysis.json` and `rxi.csv`;
the HDF5 checkpoints and per-cell summaries remain in the corresponding
`L*_Gamma*` directories.
