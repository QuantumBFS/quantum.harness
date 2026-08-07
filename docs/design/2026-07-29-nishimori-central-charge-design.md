# Ordinary Nishimori Effective Central-Charge Verification

**Date:** 2026-07-29

**Challenge:** Quantum Harness issue #122

**Team:** 卧龙凤雏

## Goal

Verify the Casimir effective central charge of the ordinary two-dimensional
±J random-bond Ising model at the Nishimori multicritical point. The target is
the established transfer-matrix result

`c_eff = 0.464 ± 0.004`.

This benchmark is distinct from the higher/Born-rule Nishimori point, whose
disorder ensemble and replica limit differ.

## Fixed Model Convention

The square-lattice Hamiltonian is

`H = -Σ_<ij> τ_ij s_i s_j`,

where `s_i = ±1` and every bond is sampled independently as

- `τ_ij = -1` with probability `p = 0.1092212`;
- `τ_ij = +1` with probability `1-p`.

The calculation is fixed to the Nishimori line at

`K_N = 0.5 log((1-p)/p) = 1.04936047630256835`.

It does not scan or relocalize `p_c`. The uncertainty in the quoted
high-precision `p_c` is negligible relative to the planned finite-size and
disorder-sampling uncertainties.

## Numerical Method

### Random transfer products

For each cylinder row, Rust samples independent horizontal and vertical ±J
bonds and applies the positive random transfer operator

`v_(r+1)(s') = exp[K Σ_i τ^h_i s'_i s'_(i+1)]`
`               × Σ_s exp[K Σ_i τ^v_i s_i s'_i] v_r(s)`.

Periodic boundary conditions apply around circumference `L`. The vertical
factor is applied matrix-free as a product of `L` local two-state transforms,
followed by the horizontal diagonal factor. One row therefore costs
`O(L 2^L)` time and `O(2^L)` memory.

The state is normalized after every row. Accumulated logarithmic
normalizations give the leading Lyapunov exponent and hence the quenched
dimensionless free energy

`φ_L = E_disorder[log Z]/(M L)`.

No thermal Monte Carlo is used: spin configurations are summed exactly by the
transfer operator, while only quenched bond disorder is sampled.

### Reproducibility and variance reduction

All disorder is generated in Rust with
`rand_xoshiro 0.8.1::Xoshiro256PlusPlus`. Stable seeds are derived from the
base seed and disorder-replica index.

Within each replica, all widths consume nested views of the same
maximum-width bond stream. Each width retains the correct i.i.d. ±J marginal
distribution, while common disorder cancels part of the nonuniversal bulk
fluctuation in finite-size differences. Bootstrap resampling keeps complete
cross-width blocks together so this covariance is propagated rather than
discarded.

### Production geometry and statistics

- Circumferences: `L = 4, 6, 8, 10, 12, 14`.
- Independent disorder replicas: `8`.
- Burn-in rows per replica: `4,096`.
- Measurement rows per replica: `1,048,576`.
- Block length: `16,384` rows, giving `64` blocks per replica.
- Runtime ceiling: `600` seconds on the local machine.

The first production run uses these fixed values. If it misses a declared
statistical gate, its output is preserved and any increase in rows is made
only by a separately approved power-of-two refinement.

## Estimator and Fits

Python consumes joint cross-width disorder blocks and performs a hierarchical
bootstrap over replicas and blocks. It fits

`φ_L = φ_inf + π c_eff/(6 L^2) + a/L^4`.

The primary window is `L_min = 4`; `L_min = 6` is a predeclared stability
window. The point estimate is the mean of the primary bootstrap distribution,
and its uncertainty is reported as both standard error and percentile 95%
interval.

## Independent Validation

The random transfer implementation must pass these checks before production:

1. **Clean transfer oracle:** with every bond fixed to `+1` at the clean Ising
   critical coupling, Lyapunov free energies agree with the existing
   deterministic transfer-matrix values through `L=10`.
2. **Direct small-width oracle:** explicit dense random row matrices agree
   with the matrix-free row application through `L=6`.
3. **Nishimori energy identity:** a common-disorder centered finite difference
   in `K` reproduces
   `∂φ/∂K = 2 tanh(K_N)` per site on the square lattice.
4. **Disorder contract:** observed antiferromagnetic-bond counts are consistent
   with the configured binomial distribution and deterministic replay gives
   byte-identical block records.

## Acceptance Gates

The benchmark passes only if every gate is true:

- `|c_eff - 0.464| ≤ 0.020`;
- the primary 95% interval contains `0.464`;
- primary standard error is at most `0.010`;
- the `L_min=4` and `L_min=6` fits agree within their bootstrap uncertainty;
- first-half and second-half block estimates agree within `|z| < 4`;
- independent disorder replicas agree within `|z| < 4`;
- the Nishimori energy-identity error is at most `0.005`;
- total runtime is below `600` seconds.

No gate may be weakened after viewing production results.

## Artifacts and Reporting

Each run writes a new timestamped directory under `tracks/qmc/results/`:

- a manifest containing the complete configuration, seeds, versions, commands,
  and stage timings;
- raw JSONL disorder blocks with joint width values, bond counts, and
  cumulative timing;
- processed CSV files for free energies, fits, convergence, and diagnostics;
- plots for free-energy scaling, central-charge comparison, block convergence,
  fit-window stability, disorder statistics, and the energy identity;
- a self-contained offline HTML report with explicit pass/fail verdicts.

Rust owns random generation and all numerical transfer calculations. Python is
restricted to validation, bootstrap analysis, tabulation, plotting, and report
generation.

## References

- A. Honecker, M. Picco, and P. Pujol, “Nishimori point in the 2D ±J
  random-bond Ising model,”
  <https://arxiv.org/abs/cond-mat/0010143>.
- Z.-Q. Wan, X.-D. Dai, and G.-Y. Zhu, “Revisiting Nishimori
  multicriticality through the lens of information measures,” Phys. Rev.
  Research 8, 023059 (2026),
  <https://doi.org/10.1103/b8y5-k3y6>.
