# Weak self-dual effective central charge

This benchmark addresses
[challenge #122](https://github.com/QuantumBFS/quantum.harness/issues/122)
and reproduces the weak Kramers-Wannier self-dual Casimir amplitude reported
in [arXiv:2502.14034](https://arxiv.org/abs/2502.14034):

`c_eff = 0.447(1)`.

## Fixed physical convention

The monitored Majorana chain is simulated at `θ = π/4` with isotropic
couplings `β = β′ = ln(1+√2)`. Each circumference is even and periodic. The
vacuum calculation fixes Wilson loop `W=+1` and fermion parity `P=+1`, so the
wraparound Majorana bilinear carries sign `−WP = −1`.

For `Γ_ab = ⟨iγ_aγ_b⟩`, Rust samples every measurement result conditionally:

`P(s|Γ) = [1 + s tanh(β) η Γ_ab]/2`, `s,η = ±1`.

The analytic Gaussian update is applied after each result. Outcomes are
therefore Born-correlated; replacing them with IID random bonds would simulate
a different replica limit and universality class.

## Estimator and fit

At every sampled gate, Rust accumulates the conditional binary entropy
`−p log p − (1−p) log(1−p)`. Its trajectory mean is exactly the Shannon
entropy `−Σ_s P(s) log P(s)` by the chain rule, while avoiding the extra
variance of realized `−log P(s|Γ)` values. Each circuit period contains an
onsite and a bond measurement row, so division by twice the number of periods
gives the per-row rate `γ₁(L)` used in the cylinder depth `L_y`. Python fits

`γ₁(L) = f∞ L − π c_eff/(6L) + a/L³`.

Rust uses `rand_xoshiro 0.8.1::Xoshiro256PlusPlus`. Python performs no random
physics sampling; it only validates artifacts, bootstraps blocks/streams,
fits, plots, and renders the report.

## Validation

- Dense Hilbert-space enumeration agrees with Gaussian joint probabilities,
  parities, and final covariances at small width.
- Gauge-related trajectories have identical probabilities and observables.
- The all-positive path agrees with dense clean evolution.
- Covariance antisymmetry and purity are checked throughout every stream.
- Electric and magnetic checkerboard vortex densities must agree at
  self-duality.
- Raw streams are atomic, resumable, seed-recorded, and SHA-256 audited.

Production uses `L=6,8,…,30`, eight independent streams, `20L` burn-in layers,
`100L` measured layers, and `5L` blocks. The predeclared refinement adds
`L=32`, doubles streams, and uses `200L` measured layers. If its precision
gate alone fails, `configs/refinement-2.toml` retains those widths and lengths
while increasing to 128 streams, as determined from the observed
`1/sqrt(N)` uncertainty scaling.

## Commands

```bash
make setup
make test
make run-test
make run-quick
make run
```

Runs are written under `tracks/qmc/results/weak-self-dual-<timestamp>/` with
raw JSON/CSV, processed tables, five plot families, `report.json`, and a
self-contained `report.html`.
