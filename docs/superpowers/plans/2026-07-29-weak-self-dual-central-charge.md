# Weak Self-Dual Central-Charge Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run a reproducible Rust/Python benchmark that verifies the weak self-dual effective central charge \(c_{\mathrm{eff}}=0.447(1)\) from Born-correlated Majorana trajectories.

**Architecture:** Rust evolves a pure Majorana Gaussian covariance matrix, samples every weak-measurement result from its conditional Born probability with Xoshiro256++, and records blockwise vacuum free-energy/Lyapunov estimates. Python validates the raw artifacts, performs autocorrelation-aware hierarchical bootstrap finite-size fits, generates diagnostic plots, and renders a self-contained HTML report.

**Tech Stack:** Rust 2021, `rand_xoshiro::Xoshiro256PlusPlus` 0.8.1, `nalgebra` 0.33, Rayon, Serde/TOML; Python 3 with NumPy 2.0.2, Matplotlib 3.9.4, and pytest 8.3.5.

## Global Constraints

- Work under `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/`; generated runs belong under `tracks/qmc/results/`.
- Fix \(\theta=\pi/4\), \(\beta=\beta'=\ln(1+\sqrt2)\), spacetime anisotropy \(\alpha=1\), even periodic widths, and the \(W=+1,\ P=+1\) vacuum sector.
- Rust owns all random sampling, Gaussian evolution, blocking, and physical estimators.
- Python may only validate, aggregate, fit, bootstrap, plot, and render reports.
- Use `rand_xoshiro::Xoshiro256PlusPlus`; record every base and derived seed.
- The primary finite-size model is \(\gamma_1(L)=f_\infty L-\pi c_{\mathrm{eff}}/(6L)+a/L^3\).
- Production widths are \(L=6,8,\ldots,30\); \(L=32\) is the predeclared refinement width.
- The final 95% confidence interval must contain `0.447` and have half-width at most `0.01`.
- Preserve failed production attempts and never weaken a gate after inspecting results.
- Follow test-driven development and commit after every independently reviewable task.

---

## File Map

### Rust crate

- `Cargo.toml`, `Cargo.lock` — locked dependencies and crate metadata.
- `src/lib.rs` — public module boundary.
- `src/config.rs` — fixed physics constants, TOML schema, and production-contract validation.
- `src/rng.rs` — stable width/stream/purpose seed derivation and Xoshiro256++ construction.
- `src/covariance.rs` — pure Gaussian covariance state, Born probabilities, analytic weak-measurement update, and stabilization.
- `src/network.rs` — alternating onsite/bond Majorana measurement geometry, vacuum boundary sign, Wilson-loop metadata, and checkerboard vortex bookkeeping.
- `src/sampler.rs` — one-stream burn-in, block accumulation, invariant checks, and diagnostics.
- `src/oracles.rs` — dense small-system trajectory enumeration and analytic update comparisons.
- `src/schema.rs` — versioned raw artifacts and manifest types.
- `src/main.rs` — `oracles` and resumable parallel `simulate` commands.
- `tests/config_rng.rs` — configuration and deterministic RNG contracts.
- `tests/covariance.rs` — Gaussian update unit and property tests.
- `tests/network_sampler.rs` — layer schedule, boundary sector, blocking, and replay tests.
- `tests/scientific_oracles.rs` — exact Born-distribution and clean-limit tests.
- `tests/cli.rs` — CLI, artifact, resume, and incompatibility tests.

### Python analysis

- `analysis/data_io.py` — strict manifest/artifact loading and array assembly.
- `analysis/fitting.py` — primary and variant finite-size models.
- `analysis/bootstrap.py` — stream/block hierarchical bootstrap.
- `analysis/diagnostics.py` — ESS, autocorrelation, self-duality, residual, and stability metrics.
- `analysis/gates.py` — immutable production acceptance criteria.
- `analysis/plots.py` — scaling, residual, stability, convergence, and vortex figures.
- `analysis/report_builder.py` — report document model.
- `analysis/run_analysis.py` — analysis orchestration and processed outputs.
- `analysis/finalize_runtime.py`, `analysis/run_analysis_stage.sh` — timing-safe report stage.
- `analysis/requirements.txt`, `analysis/__init__.py` — pinned environment and package marker.
- `analysis/tests/helpers.py` — deterministic synthetic run fixture.
- `analysis/tests/test_data_io.py` — schema and integrity failures.
- `analysis/tests/test_fitting.py` — exact synthetic coefficient recovery.
- `analysis/tests/test_bootstrap.py` — paired resampling and determinism.
- `analysis/tests/test_diagnostics.py` — ESS and stability metrics.
- `analysis/tests/test_gates.py` — every pass/fail boundary.
- `analysis/tests/test_report.py` — required sections and figures.
- `analysis/tests/test_end_to_end.py` — synthetic raw run through report data.

### Workflow and documentation

- `configs/test.toml` — seconds-long validation run.
- `configs/quick.toml` — small scientific pilot.
- `configs/production.toml` — fixed \(L=6\ldots30\) production contract.
- `configs/refinement-1.toml` — predeclared doubled sampling plus \(L=32\).
- `Makefile`, `run.sh`, `pytest.ini`, `.gitignore` — reproducible entry points and output isolation.
- `README.md` — model, conventions, commands, expected artifacts, and interpretation.
- `tracks/qmc/solutions/卧龙凤雏/README.md` — add the completed benchmark to the team index.

---

### Task 1: Scaffold the Crate, Configuration, and RNG Contract

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/Cargo.toml`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/src/lib.rs`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/src/config.rs`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/src/rng.rs`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/configs/test.toml`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/tests/config_rng.rs`

**Interfaces:**
- Produces: `RunConfig::load(&Path) -> Result<RunConfig>` and `RunConfig::validate() -> Result<()>`.
- Produces: `derive_seed(base_seed: u64, width: usize, stream: usize, purpose: u64) -> u64`.
- Produces: `make_rng(seed: u64) -> Xoshiro256PlusPlus`.
- Produces constants `SELF_DUAL_THETA`, `SELF_DUAL_BETA`, `TARGET_CENTRAL_CHARGE`, and `PRODUCTION_WIDTHS`.

- [ ] **Step 1: Write configuration and RNG tests**

```rust
use weak_self_dual::config::{
    RunConfig, SELF_DUAL_BETA, TARGET_CENTRAL_CHARGE,
};
use weak_self_dual::rng::{derive_seed, make_rng};
use rand_xoshiro::rand_core::RngCore;

#[test]
fn physics_constants_are_fixed() {
    assert!((SELF_DUAL_BETA - (1.0_f64 + 2.0_f64.sqrt()).ln()).abs() < 1e-15);
    assert_eq!(TARGET_CENTRAL_CHARGE, 0.447);
}

#[test]
fn derived_streams_are_stable_and_distinct() {
    let a = derive_seed(122_447, 6, 0, 0);
    let b = derive_seed(122_447, 8, 0, 0);
    assert_ne!(a, b);
    let mut first = make_rng(a);
    let mut replay = make_rng(a);
    assert_eq!(first.next_u64(), replay.next_u64());
}

#[test]
fn rejects_odd_or_duplicate_widths() {
    let mut config = test_config();
    config.widths = vec![6, 7, 8];
    assert!(config.validate().unwrap_err().to_string().contains("even"));
    config.widths = vec![6, 6, 8];
    assert!(config.validate().unwrap_err().to_string().contains("unique"));
}
```

In the test file, `test_config()` constructs a valid width-`[2, 4]`,
non-production `RunConfig` with one stream, two burn-in layers per width,
eight measurement layers per width, two block layers per width, stabilization
every layer, and invariant tolerance `1e-9`.

- [ ] **Step 2: Run the tests and verify the crate is absent**

Run:

```bash
cargo test --manifest-path tracks/qmc/solutions/卧龙凤雏/weak-self-dual/Cargo.toml --test config_rng
```

Expected: failure because `Cargo.toml` and the `weak_self_dual` crate do not exist.

- [ ] **Step 3: Add the crate and exact configuration types**

Use these dependency floors and fixed versions:

```toml
[package]
name = "weak-self-dual"
version = "0.1.0"
edition = "2021"

[dependencies]
anyhow = "1.0"
clap = { version = "4.5", features = ["derive"] }
nalgebra = { version = "0.33", features = ["serde-serialize"] }
num-complex = "0.4"
rand_xoshiro = "=0.8.1"
rayon = "1.10"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
sha2 = "0.10"
toml = "0.8"

[dev-dependencies]
assert_cmd = "2.0"
predicates = "3.1"
tempfile = "3.12"
```

Define the configuration contract:

```rust
pub const SELF_DUAL_THETA: f64 = std::f64::consts::FRAC_PI_4;
pub const SELF_DUAL_BETA: f64 = 0.881_373_587_019_543;
pub const TARGET_CENTRAL_CHARGE: f64 = 0.447;
pub const PRODUCTION_WIDTHS: [usize; 13] =
    [6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30];

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RunConfig {
    pub widths: Vec<usize>,
    pub theta: f64,
    pub beta: f64,
    pub base_seed: u64,
    pub production_gates: bool,
    pub refinement_level: usize,
    pub sampling: SamplingConfig,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SamplingConfig {
    pub streams_per_width: usize,
    pub burn_in_layers_per_width: usize,
    pub measurement_layers_per_width: usize,
    pub block_layers_per_width: usize,
    pub stabilize_every_layers: usize,
    pub invariant_tolerance: f64,
}
```

Validation must enforce finite fixed physics values, sorted unique even widths,
positive counts, complete blocks, `burn_in_layers_per_width < measurement_layers_per_width`,
and the exact production width/configuration contract.

- [ ] **Step 4: Implement stable SplitMix64-derived Xoshiro streams**

Use separate keys for width, stream, and purpose:

```rust
pub fn derive_seed(base_seed: u64, width: usize, stream: usize, purpose: u64) -> u64 {
    let width_key = mix64((width as u64) ^ 0x7769_6474_6800_0000);
    let stream_key = mix64((stream as u64) ^ 0x7374_7265_616d_0000);
    let purpose_key = mix64(purpose ^ 0x7075_7270_6f73_6500);
    mix64(base_seed ^ width_key ^ stream_key ^ purpose_key)
}
```

- [ ] **Step 5: Run formatting and focused tests**

Run:

```bash
cargo fmt --manifest-path tracks/qmc/solutions/卧龙凤雏/weak-self-dual/Cargo.toml --check
cargo test --manifest-path tracks/qmc/solutions/卧龙凤雏/weak-self-dual/Cargo.toml --test config_rng
```

Expected: all `config_rng` tests pass.

- [ ] **Step 6: Commit**

```bash
git add tracks/qmc/solutions/卧龙凤雏/weak-self-dual
git commit -m "feat: scaffold weak self-dual benchmark"
```

---

### Task 2: Implement the Gaussian Covariance and Born Update

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/src/covariance.rs`
- Modify: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/src/lib.rs`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/tests/covariance.rs`

**Interfaces:**
- Consumes: fixed `beta` from `RunConfig`.
- Produces: `CovarianceState::paired_vacuum(width: usize) -> Result<Self>`.
- Produces: `parity_expectation(&self, a: usize, b: usize, observable_sign: i8) -> Result<f64>`.
- Produces: `outcome_probability(&self, measurement: Measurement, outcome: i8) -> Result<f64>`.
- Produces: `apply_outcome(&mut self, measurement: Measurement, outcome: i8) -> Result<UpdateStats>`.
- Produces: `invariant_errors(&self) -> InvariantErrors` and `stabilize(&mut self) -> Result<()>`.

- [ ] **Step 1: Write analytic one-measurement tests**

```rust
#[test]
fn born_probabilities_match_closed_form() {
    let state = CovarianceState::paired_vacuum(2).unwrap();
    let beta = 0.4;
    let measurement = Measurement { a: 0, b: 1, observable_sign: 1, beta };
    let expected = 0.5 * (1.0 + beta.tanh());
    assert!((state.outcome_probability(measurement, 1).unwrap() - expected).abs() < 1e-14);
}

#[test]
fn weak_update_matches_mobius_formula() {
    let mut state = CovarianceState::paired_vacuum(2).unwrap();
    let beta = 0.3;
    let measurement = Measurement { a: 1, b: 2, observable_sign: 1, beta };
    state.apply_outcome(measurement, -1).unwrap();
    assert!((state.parity_expectation(1, 2, 1).unwrap() + beta.tanh()).abs() < 1e-13);
}

#[test]
fn update_preserves_pure_gaussian_invariants() {
    let mut state = CovarianceState::paired_vacuum(3).unwrap();
    let measurement = Measurement { a: 1, b: 2, observable_sign: 1, beta: 0.7 };
    state.apply_outcome(measurement, 1).unwrap();
    let errors = state.invariant_errors();
    assert!(errors.antisymmetry < 1e-12);
    assert!(errors.purity < 1e-11);
}
```

- [ ] **Step 2: Run the focused test and confirm missing symbols**

Run:

```bash
cargo test --manifest-path tracks/qmc/solutions/卧龙凤雏/weak-self-dual/Cargo.toml --test covariance
```

Expected: compile failure because `covariance` is not defined.

- [ ] **Step 3: Implement the covariance convention and probability**

Use

\[
\Gamma_{ij}=\langle i\gamma_i\gamma_j\rangle,\quad
\Gamma^\mathsf{T}=-\Gamma,\quad \Gamma^2=-I.
\]

For observable sign \(\eta=\pm1\), set \(m=\eta\Gamma_{ab}\),
\(t=\tanh\beta\), and

```rust
let probability = 0.5 * (1.0 + outcome as f64 * t * m);
```

Reject indices with `a == b`, non-finite `beta`, observable or outcome signs
other than `±1`,
or probabilities outside `[-64*EPSILON, 1+64*EPSILON]`. Clamp only the
roundoff-sized excess to `[0,1]`.

- [ ] **Step 4: Implement the \(O(L^2)\) analytic update**

Copy the old covariance before updating. With \(q=s\eta\tanh\beta\),
\(d=1+q\Gamma_{ab}\), and \(r=\sqrt{1-\tanh^2\beta}\), apply:

```text
Γ'_ab = (Γ_ab + q) / d
Γ'_aj = r Γ_aj / d
Γ'_bj = r Γ_bj / d
Γ'_ij = Γ_ij + q(Γ_ia Γ_bj - Γ_ib Γ_aj) / d
```

for `i,j` outside `{a,b}`, fill the lower triangle by antisymmetry, and return:

```rust
pub struct UpdateStats {
    pub probability: f64,
    pub surprise: f64, // -probability.ln()
    pub pre_measurement_parity: f64,
}
```

For `observable_sign == -1`, absorb \(\eta\) into `q`; do not mutate the
stored orientation convention.

- [ ] **Step 5: Add invariant measurement and polar stabilization**

Compute `max_abs(Γ + Γᵀ)` and `max_abs(ΓΓ + I)`. Stabilization first
antisymmetrizes, then performs up to four Newton polar iterations

```text
X_next = 0.5 * (X + X^{-T})
```

and antisymmetrizes once more. Fail if inversion fails or purity remains above
the configured tolerance.

- [ ] **Step 6: Run focused and property tests**

Run:

```bash
cargo test --manifest-path tracks/qmc/solutions/卧龙凤雏/weak-self-dual/Cargo.toml --test covariance
cargo clippy --manifest-path tracks/qmc/solutions/卧龙凤雏/weak-self-dual/Cargo.toml --all-targets -- -D warnings
```

Expected: analytic values and Gaussian invariants pass.

- [ ] **Step 7: Commit**

```bash
git add tracks/qmc/solutions/卧龙凤雏/weak-self-dual/src tracks/qmc/solutions/卧龙凤雏/weak-self-dual/tests/covariance.rs
git commit -m "feat: add Born-updated Majorana covariance"
```

---

### Task 3: Define the Self-Dual Network, Vacuum Sector, and Vortices

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/src/network.rs`
- Modify: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/src/lib.rs`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/tests/network_sampler.rs`

**Interfaces:**
- Consumes: `Measurement` and `CovarianceState`.
- Produces: `BoundarySector { wilson_loop: i8, fermion_parity: i8 }`.
- Produces: `SelfDualNetwork::new(width, beta, BoundarySector) -> Result<Self>`.
- Produces: `onsite_measurements()`, `bond_measurements()`, and `record_layer_outcomes`.
- Produces: `VortexCounts { electric, magnetic, faces_per_species }`.

- [ ] **Step 1: Write schedule and boundary tests**

```rust
#[test]
fn self_dual_layer_measures_every_adjacent_majorana_pair() {
    let network = SelfDualNetwork::vacuum(4, SELF_DUAL_BETA).unwrap();
    assert_eq!(network.onsite_measurements().len(), 4);
    assert_eq!(network.bond_measurements().len(), 4);
    assert_eq!((network.onsite_measurements()[0].a, network.onsite_measurements()[0].b), (0, 1));
    assert_eq!((network.bond_measurements()[0].a, network.bond_measurements()[0].b), (1, 2));
}

#[test]
fn vacuum_boundary_bilinear_has_minus_wp_sign() {
    let network = SelfDualNetwork::vacuum(4, SELF_DUAL_BETA).unwrap();
    let boundary = network.bond_measurements().last().unwrap();
    assert_eq!((boundary.a, boundary.b), (7, 0));
    assert_eq!(boundary.observable_sign, -1);
}
```

- [ ] **Step 2: Run and confirm the missing network module**

Run:

```bash
cargo test --manifest-path tracks/qmc/solutions/卧龙凤雏/weak-self-dual/Cargo.toml --test network_sampler
```

Expected: compile failure on `SelfDualNetwork`.

- [ ] **Step 3: Implement alternating measurement geometry**

For zero-based spin site `j`, onsite measurements act on `(2j, 2j+1)` and
bond measurements act on `(2j+1, 2(j+1) mod 2L)`. The wraparound observable
sign is `-W*P`; every other observable sign is `+1`. Require the production
sector `W=P=+1`, while allowing all four sectors in oracle tests.

- [ ] **Step 4: Implement checkerboard vortex bookkeeping**

Store two consecutive complete outcome layers as edge signs on the
Majorana spacetime network. For each checkerboard face, compute

```rust
let flux = left * top * right * bottom;
let occupied = usize::from(flux == -1);
```

Faces whose lower-left Majorana index is even contribute to electric counts;
odd faces contribute to magnetic counts. Unit tests must cover a no-vortex
all-positive tile and a single flipped edge, which creates one vortex of each
adjacent face species under periodic boundaries.

- [ ] **Step 5: Add the exact self-dual symmetry test**

Construct a layer, translate all Majorana indices by one modulo `2L`, exchange
electric and magnetic labels, and assert identical face counts. This tests the
microscopic Kramers-Wannier/Majorana-translation symmetry independently of
Monte Carlo statistics.

- [ ] **Step 6: Run focused tests**

Run:

```bash
cargo test --manifest-path tracks/qmc/solutions/卧龙凤雏/weak-self-dual/Cargo.toml --test network_sampler
```

Expected: schedule, boundary sign, flux, and translation-duality tests pass.

- [ ] **Step 7: Commit**

```bash
git add tracks/qmc/solutions/卧龙凤雏/weak-self-dual/src tracks/qmc/solutions/卧龙凤雏/weak-self-dual/tests/network_sampler.rs
git commit -m "feat: add self-dual Majorana network geometry"
```

---

### Task 4: Add Dense Scientific Oracles

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/src/oracles.rs`
- Modify: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/src/lib.rs`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/tests/scientific_oracles.rs`

**Interfaces:**
- Consumes: network measurement schedules and covariance update.
- Produces: `enumerate_dense_trajectories(width, depth, beta, sector) -> Result<Vec<TrajectoryProbability>>`.
- Produces: `compare_covariance_to_dense(width, depth, beta) -> Result<OracleComparison>`.
- Produces: `compare_gauge_equivalent_trajectories(width, depth, beta) -> Result<GaugeOracleComparison>`.
- Produces: `clean_positive_trajectory(width, layers, beta) -> Result<CleanOracle>`.

- [ ] **Step 1: Write oracle acceptance tests**

```rust
#[test]
fn enumerated_born_distribution_normalizes() {
    let rows = enumerate_dense_trajectories(2, 1, SELF_DUAL_BETA, BoundarySector::vacuum()).unwrap();
    let total: f64 = rows.iter().map(|row| row.probability).sum();
    assert!((total - 1.0).abs() < 1e-12);
}

#[test]
fn gaussian_and_dense_trajectory_probabilities_match() {
    let comparison = compare_covariance_to_dense(2, 2, SELF_DUAL_BETA).unwrap();
    assert!(comparison.max_probability_error < 1e-11);
    assert!(comparison.max_parity_error < 1e-10);
}

#[test]
fn gauge_equivalent_dense_trajectories_match() {
    let comparison = compare_gauge_equivalent_trajectories(2, 2, SELF_DUAL_BETA).unwrap();
    assert!(comparison.max_probability_error < 1e-11);
    assert!(comparison.max_observable_error < 1e-10);
}
```

- [ ] **Step 2: Run and confirm oracle symbols are missing**

Run:

```bash
cargo test --manifest-path tracks/qmc/solutions/卧龙凤雏/weak-self-dual/Cargo.toml --test scientific_oracles
```

Expected: compile failure.

- [ ] **Step 3: Implement dense Jordan-Wigner Majoranas**

For `L <= 3`, build

```text
γ_(2j)   = Z_0 ... Z_(j-1) X_j
γ_(2j+1) = Z_0 ... Z_(j-1) Y_j
```

as dense complex matrices. Apply

```text
K_s = exp[(s β / 2) iγ_aγ_b] / sqrt(2 cosh β)
```

to the state vector, use its squared norm as the conditional probability, and
renormalize. Enumerate both outcomes recursively in a fixed lexicographic
order.

- [ ] **Step 4: Compare dense and covariance paths outcome by outcome**

For every trajectory through width `2`, depth `2`, compare joint probability,
all measured parity expectations, final covariance entries, and the sum of
surprises. Report the maximum absolute error and the offending bit string.

Apply the gauge transformation \(\gamma_j\mapsto-\gamma_j\), flip the
orientation signs of every incident bilinear, and verify that joint
probabilities and all gauge-invariant fluxes are unchanged. This is the
required gauge-equivalence oracle.

- [ ] **Step 5: Implement the all-positive clean oracle**

Apply only `s=+1` outcomes at the self-dual coupling and compare the resulting
Gaussian covariance against the dense state. Record the per-layer log norm so
later CLI artifacts can prove the clean limit was tested.

- [ ] **Step 6: Run oracle tests in release mode**

Run:

```bash
cargo test --release --manifest-path tracks/qmc/solutions/卧龙凤雏/weak-self-dual/Cargo.toml --test scientific_oracles
```

Expected: normalization and dense/Gaussian comparisons pass.

- [ ] **Step 7: Commit**

```bash
git add tracks/qmc/solutions/卧龙凤雏/weak-self-dual/src/oracles.rs tracks/qmc/solutions/卧龙凤雏/weak-self-dual/src/lib.rs tracks/qmc/solutions/卧龙凤雏/weak-self-dual/tests/scientific_oracles.rs
git commit -m "test: add exact Born-trajectory oracles"
```

---

### Task 5: Implement Stream Sampling and the Vacuum Lyapunov Estimator

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/src/sampler.rs`
- Modify: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/src/lib.rs`
- Modify: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/tests/network_sampler.rs`

**Interfaces:**
- Consumes: `RunConfig`, `CovarianceState`, `SelfDualNetwork`, and width-specific RNG.
- Produces: `estimate_stream(config: &RunConfig, width: usize, stream: usize) -> Result<StreamEstimate>`.
- Produces: `BlockEstimate { block_index, gamma, electric_density, magnetic_density, min_probability, max_invariant_error }`.

- [ ] **Step 1: Write deterministic block-estimator tests**

```rust
#[test]
fn gamma_is_born_surprise_per_complete_layer() {
    let config = tiny_config(2, 0, 4, 2);
    let estimate = estimate_stream(&config, 2, 0).unwrap();
    assert_eq!(estimate.blocks.len(), 2);
    assert!(estimate.blocks.iter().all(|block| block.gamma.is_finite() && block.gamma > 0.0));
}

#[test]
fn replay_is_byte_identical_at_the_schema_level() {
    let config = tiny_config(2, 2, 8, 2);
    assert_eq!(
        estimate_stream(&config, 2, 1).unwrap(),
        estimate_stream(&config, 2, 1).unwrap()
    );
}
```

`tiny_config(width, burn_in, measurement, block)` is a test-local constructor
that returns one non-production width and one stream, with stabilization every
layer and invariant tolerance `1e-9`.

- [ ] **Step 2: Run and confirm sampler failure**

Run:

```bash
cargo test --manifest-path tracks/qmc/solutions/卧龙凤雏/weak-self-dual/Cargo.toml --test network_sampler
```

Expected: compile failure on `estimate_stream`.

- [ ] **Step 3: Implement one complete stochastic layer**

For every onsite measurement followed by every bond measurement:

1. evaluate both conditional probabilities;
2. draw a uniform `u` from Xoshiro256++;
3. choose `+1` iff `u < p_plus`;
4. apply the analytic covariance update;
5. add `-ln(p_chosen)` to the layer surprise;
6. record the signed edge outcome for vortex bookkeeping.

Return `gamma = sum(layer_surprise) / block_layers`. Do not divide by width:
the finite-size model is for the per-layer cylinder free energy
\(\gamma_1(L)\), not its density.

- [ ] **Step 4: Add stabilization and hard numerical failures**

At the configured layer interval, run covariance stabilization and require:

```rust
probability.is_finite()
    && probability > 0.0
    && surprise.is_finite()
    && invariant_error <= config.sampling.invariant_tolerance
```

Every error must include width, stream, layer, gate type, gate index, and seed.

- [ ] **Step 5: Add burn-in and complete-block semantics**

Burn-in evolves the same state but does not contribute to reported blocks.
Reset vortex history after burn-in. Require measurement layers to contain
whole blocks and record first/second-half block order without shuffling.

- [ ] **Step 6: Add statistical self-duality fields**

Each block stores electric and magnetic face counts and denominators, rather
than only rounded densities. This lets Python compute the joint uncertainty
of their difference without assuming independent denominators.

- [ ] **Step 7: Run sampler tests and clippy**

Run:

```bash
cargo test --release --manifest-path tracks/qmc/solutions/卧龙凤雏/weak-self-dual/Cargo.toml --test network_sampler
cargo clippy --manifest-path tracks/qmc/solutions/卧龙凤雏/weak-self-dual/Cargo.toml --all-targets -- -D warnings
```

Expected: blocking, replay, and numerical-invariant tests pass.

- [ ] **Step 8: Commit**

```bash
git add tracks/qmc/solutions/卧龙凤雏/weak-self-dual/src tracks/qmc/solutions/卧龙凤雏/weak-self-dual/tests/network_sampler.rs
git commit -m "feat: sample Born-correlated vacuum trajectories"
```

---

### Task 6: Add Versioned Artifacts and a Resumable Parallel CLI

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/src/schema.rs`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/src/main.rs`
- Modify: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/src/lib.rs`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/tests/cli.rs`

**Interfaces:**
- Consumes: `estimate_stream` and all oracle functions.
- Produces commands:
  - `weak-self-dual oracles --config <toml> --output <json> --manifest <json>`
  - `weak-self-dual simulate --config <toml> --output-dir <dir> --manifest <json>`
- Produces `streams/stream-L{width:02}-{stream:03}.json` with schema version `1`.
- Produces a sorted consolidated `blocks.csv` containing every raw block.

- [ ] **Step 1: Write CLI failure and resume tests**

```rust
#[test]
fn simulate_writes_one_artifact_per_width_stream() {
    let run = TestRun::new();
    run.command("simulate").assert().success();
    assert!(run.raw_dir().join("streams/stream-L02-000.json").exists());
}

#[test]
fn simulate_reuses_compatible_artifacts() {
    let run = TestRun::new();
    run.command("simulate").assert().success();
    let before = sha256(run.raw_dir().join("streams/stream-L02-000.json"));
    run.command("simulate").assert().success().stderr(predicate::str::contains("reusing"));
    assert_eq!(before, sha256(run.raw_dir().join("streams/stream-L02-000.json")));
}
```

- [ ] **Step 2: Run and confirm the binary is absent**

Run:

```bash
cargo test --manifest-path tracks/qmc/solutions/卧龙凤雏/weak-self-dual/Cargo.toml --test cli
```

Expected: failure because no binary target exists.

- [ ] **Step 3: Define the exact schemas**

```rust
pub const SCHEMA_VERSION: u32 = 1;

pub struct StreamArtifact {
    pub schema_version: u32,
    pub config: RunConfig,
    pub estimate: StreamEstimate,
    pub elapsed_s: f64,
}

pub struct OracleArtifact {
    pub schema_version: u32,
    pub config: RunConfig,
    pub born_enumeration: OracleComparison,
    pub clean_positive: CleanOracle,
    pub elapsed_s: f64,
}
```

The manifest records config path, commands, Rust version, `Cargo.lock` SHA-256,
thread count, all width/stream seeds, artifact hashes, timestamps, stage
timings, and completion status.

- [ ] **Step 4: Implement atomic writes and strict reuse validation**

Write to a sibling temporary file, flush and `sync_all`, then rename. Before
reuse, verify schema version, complete config equality, width, stream, derived
seed, block count, and SHA-256. An incompatible existing artifact must stop
the command rather than be overwritten.

After all stream artifacts validate, write `blocks.csv` atomically with
columns `width,stream,seed,block_index,gamma,electric_count,magnetic_count,`
`faces_per_species,min_probability,max_invariant_error`. Numeric fields retain
17 significant digits. Hash this raw table in the manifest.

- [ ] **Step 5: Parallelize only independent streams**

Create the Cartesian product of configured widths and streams, then use
Rayon’s `par_iter`. Each worker owns its covariance state and RNG. Sort
completed metadata by `(width, stream)` before writing the manifest so thread
scheduling cannot change serialized output.

- [ ] **Step 6: Run CLI and full Rust tests**

Run:

```bash
cargo fmt --manifest-path tracks/qmc/solutions/卧龙凤雏/weak-self-dual/Cargo.toml --check
cargo clippy --manifest-path tracks/qmc/solutions/卧龙凤雏/weak-self-dual/Cargo.toml --all-targets -- -D warnings
cargo test --release --manifest-path tracks/qmc/solutions/卧龙凤雏/weak-self-dual/Cargo.toml
```

Expected: all Rust tests pass.

- [ ] **Step 7: Commit**

```bash
git add tracks/qmc/solutions/卧龙凤雏/weak-self-dual/src tracks/qmc/solutions/卧龙凤雏/weak-self-dual/tests/cli.rs tracks/qmc/solutions/卧龙凤雏/weak-self-dual/Cargo.lock
git commit -m "feat: add resumable weak self-dual runner"
```

---

### Task 7: Implement Strict Data Loading and Finite-Size Fits

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/__init__.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/data_io.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/fitting.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/requirements.txt`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/tests/__init__.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/tests/helpers.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/tests/test_data_io.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/tests/test_fitting.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/pytest.ini`

**Interfaces:**
- Produces: `load_run(run_dir: Path) -> LoadedRun`.
- Produces: `LoadedRun.gamma_blocks: dict[int, np.ndarray]` shaped `(streams, blocks)`.
- Produces: `fit_gamma(widths, gamma, sigma, minimum_width, correction) -> GammaFit`.
- Produces: `evaluate_fit(fit, widths) -> np.ndarray`.

- [ ] **Step 1: Write exact coefficient-recovery tests**

```python
def test_primary_fit_recovers_known_central_charge():
    widths = np.arange(6, 32, 2, dtype=float)
    gamma = 0.73 * widths - np.pi * 0.447 / (6.0 * widths) + 1.2 / widths**3
    fit = fit_gamma(widths, gamma, np.full_like(widths, 1e-4), 6, "l3")
    assert fit.central_charge == pytest.approx(0.447, abs=1e-10)

def test_fit_rejects_too_few_widths():
    with pytest.raises(ValueError, match="at least three"):
        fit_gamma(np.array([6, 8]), np.array([1.0, 2.0]), np.ones(2), 6, "l3")
```

- [ ] **Step 2: Run and verify analysis modules are missing**

Run:

```bash
python3 -m pytest -q tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/tests/test_data_io.py tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/tests/test_fitting.py
```

Expected: import failures.

- [ ] **Step 3: Implement strict run loading**

Verify manifest and stream artifact schema `1`, configuration equality,
artifact SHA-256, every expected `(width, stream)` pair exactly once, identical
block counts, finite gamma values, positive probabilities, and valid count
denominators. Return widths sorted numerically, never filesystem order.

- [ ] **Step 4: Implement primary and variant design matrices**

Use weighted least squares with `weights = 1/sigma**2` and:

```python
def design_matrix(widths, correction):
    columns = [widths, -np.pi / (6.0 * widths)]
    if correction == "none":
        return np.column_stack(columns)
    if correction == "l3":
        return np.column_stack([*columns, 1.0 / widths**3])
    if correction == "l3_l5":
        return np.column_stack([*columns, 1.0 / widths**3, 1.0 / widths**5])
    raise ValueError(f"unknown correction model: {correction}")
```

The second coefficient is `central_charge`. Return coefficients, covariance,
weighted residuals, chi-square, degrees of freedom, and RMS residual.

- [ ] **Step 5: Pin and install analysis requirements**

Use:

```text
matplotlib==3.9.4
numpy==2.0.2
pyparsing==3.2.3
pytest==8.3.5
```

- [ ] **Step 6: Run focused Python tests**

Run:

```bash
python3 -m pytest -q tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/tests/test_data_io.py tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/tests/test_fitting.py
```

Expected: strict loading and all fit variants pass.

- [ ] **Step 7: Commit**

```bash
git add tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis tracks/qmc/solutions/卧龙凤雏/weak-self-dual/pytest.ini
git commit -m "feat: analyze weak self-dual finite-size data"
```

---

### Task 8: Add Bootstrap, Diagnostics, and Immutable Gates

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/bootstrap.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/diagnostics.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/gates.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/tests/test_bootstrap.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/tests/test_diagnostics.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/tests/test_gates.py`

**Interfaces:**
- Consumes: per-width `(streams, blocks)` arrays and fit functions.
- Produces: `bootstrap_fits(gamma_blocks, widths, samples, seed, variants)`.
- Produces: `effective_sample_size(series)`, `self_duality_diagnostic`, and `fit_stability`.
- Produces: `evaluate_gates(...) -> dict`.

- [ ] **Step 1: Write deterministic bootstrap and gate-boundary tests**

```python
def test_bootstrap_is_seed_reproducible():
    first = bootstrap_fits(blocks, widths, samples=200, seed=447122, variants=variants)
    second = bootstrap_fits(blocks, widths, samples=200, seed=447122, variants=variants)
    np.testing.assert_array_equal(first["primary"], second["primary"])

def test_target_gate_requires_interval_and_precision():
    result = evaluate_gates(ci_low=0.440, ci_high=0.454, **passing_gate_inputs())
    assert result["by_name"]["target_interval"]["passed"]
    result = evaluate_gates(ci_low=0.430, ci_high=0.466, **passing_gate_inputs())
    assert not result["by_name"]["precision"]["passed"]
```

`passing_gate_inputs()` supplies exact-oracle pass, invariant error `1e-12`,
self-duality `z=0`, minimum ESS `200`, zero paired fit-window shifts,
systematic spread `0.002`, maximum studentized residual `1`, and residual
trend correlation `0`.

- [ ] **Step 2: Run and verify missing modules**

Run:

```bash
python3 -m pytest -q tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/tests/test_bootstrap.py tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/tests/test_diagnostics.py tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/tests/test_gates.py
```

Expected: import failures.

- [ ] **Step 3: Implement hierarchical resampling**

For each width independently, resample complete streams with replacement and
then complete blocks within each selected stream. Keep a width’s gamma,
electric count, magnetic count, and diagnostic values in the same resampled
index. Fit every bootstrap draw for these predeclared variants:

```python
variants = [
    ("primary", 6, "l3"),
    ("lmin8", 8, "l3"),
    ("lmin10", 10, "l3"),
    ("extra_burnin", 6, "l3"),
    ("double_block", 6, "l3"),
    ("no_correction", 6, "none"),
    ("extended_correction", 6, "l3_l5"),
    ("drop_l30", 6, "l3"),
]
```

`drop_l30` explicitly removes width `30`; refinement analysis additionally
fits a variant including `32`. `extra_burnin` discards the first quarter of
measurement blocks before resampling. `double_block` combines adjacent raw
blocks before resampling. Both preserve stream boundaries.

- [ ] **Step 4: Implement autocorrelation and ESS**

Estimate autocorrelation per stream from centered block values. Sum the paired
initial-positive sequence `rho[2k-1] + rho[2k]` until it becomes non-positive:

```python
tau = max(1.0, 1.0 + 2.0 * positive_pair_sum)
ess = number_of_blocks / tau
```

Report the sum of per-stream ESS values at each width and the maximum absolute
lag-one correlation.

- [ ] **Step 5: Implement self-duality and fit stability**

Compute electric-minus-magnetic density per joint block, then its
stream-aware standard error and `z = mean_difference / SE`. For fit
stability, report each variant’s bootstrap median and CI, maximum shift from
the primary in units of the paired-bootstrap difference error, and the full
systematic range.

- [ ] **Step 6: Encode all required gates**

Required production gates are:

```text
exact_oracles: all Rust oracle errors below their declared tolerances
gaussian_invariants: maximum recorded error <= configured tolerance
self_duality: |electric_minus_magnetic_z| <= 1.96
effective_sample_size: minimum ESS across included widths >= 100
target_interval: CI95_low <= 0.447 <= CI95_high
precision: (CI95_high - CI95_low)/2 <= 0.01
fit_stability: every valid l3 window paired shift < 2 sigma
burnin_stability: extra_burnin paired shift < 2 sigma
blocking_stability: double_block paired shift < 2 sigma
systematic_spread: accepted l3-window central charges span <= 0.01
residuals: maximum absolute studentized residual < 3
residual_trend: |corr(residual, 1/L)| < 0.8
```

The no-correction and extended-correction variants are diagnostics, not
required stability gates when their design matrix is underdetermined or their
coefficient covariance is singular.

- [ ] **Step 7: Run focused tests**

Run:

```bash
python3 -m pytest -q tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/tests/test_bootstrap.py tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/tests/test_diagnostics.py tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/tests/test_gates.py
```

Expected: resampling, ESS, self-duality, and exact gate boundaries pass.

- [ ] **Step 8: Commit**

```bash
git add tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis
git commit -m "feat: add weak self-dual statistical gates"
```

---

### Task 9: Build Plots, Processed Data, and the Offline Report

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/plots.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/report_builder.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/run_analysis.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/finalize_runtime.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/run_analysis_stage.sh`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/tests/test_report.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/tests/test_end_to_end.py`

**Interfaces:**
- Consumes: a complete raw run and renderer `skills/report/render_report.py`.
- Produces: `processed/summary.json`, `processed/gates.json`, CSV tables, figures, `report.json`, and `report.html`.

- [ ] **Step 1: Write report-content and end-to-end tests**

```python
def test_report_contains_scientific_contract(synthetic_summary, manifest):
    report = build_report_document(synthetic_summary, manifest)
    text = json.dumps(report)
    for required in ["Born-correlated", "Xoshiro256++", "W=+1", "0.447", "fit stability"]:
        assert required in text

def test_analysis_writes_all_required_outputs(tmp_path):
    run_dir = make_synthetic_run(tmp_path)
    analyze_run(run_dir, bootstrap_samples=200, bootstrap_seed=447122)
    for relative in [
        "processed/summary.json", "processed/gates.json",
        "processed/finite_size.csv", "processed/fit_variants.csv",
        "figures/finite-size-scaling.png", "figures/residuals.png",
        "figures/fit-stability.png", "figures/convergence-ess.png",
        "figures/self-duality.png",
    ]:
        assert (run_dir / relative).exists()
```

- [ ] **Step 2: Run and verify orchestration modules are missing**

Run:

```bash
python3 -m pytest -q tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/tests/test_report.py tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/tests/test_end_to_end.py
```

Expected: import failures.

- [ ] **Step 3: Implement processed outputs**

`summary.json` must include model convention, target, widths, stream/block
counts, beta, sector, point estimate, SE, CI95, primary fit, all fit variants,
systematic range, ESS, autocorrelation, vortex difference, invariant maxima,
oracle results, runtime, and gates. CSV files must contain full-precision
values for finite-size data, residuals, bootstrap samples, fit variants, ESS,
and self-duality counts.

- [ ] **Step 4: Implement the five required plot families**

Use Matplotlib’s noninteractive `Agg` backend:

1. `finite-size-scaling.png`: plot \(\gamma/L\) versus \(1/L^2\), error bars,
   primary fit, and target-derived slope.
2. `residuals.png`: studentized residual versus width with \(\pm3\) lines.
3. `fit-stability.png`: central charge and CI by \(L_{\min}\)/model, with
   `0.447 ± 0.001` reference band.
4. `convergence-ess.png`: per-width block traces, lag-one correlation, and ESS.
5. `self-duality.png`: electric and magnetic vortex densities plus their
   paired difference.

- [ ] **Step 5: Build the report document**

Follow the existing harness report renderer schema and include sections:
Verdict, Physical Model, Born Sampler, Gaussian Validation, Production Data,
Finite-Size Fit, Uncertainty and Stability, Self-Duality, Reproducibility,
Limitations, and References. A failed gate must appear in the first screen
and in a complete gate table.

- [ ] **Step 6: Hash analysis outputs and finalize runtime**

Update the manifest atomically with Python version, requirements hash,
analysis time, total time, and hashes of every processed file and figure.
Render only after processed files and manifest are complete; then hash
`report.json` and `report.html`.

- [ ] **Step 7: Run all Python tests**

Run:

```bash
MPLCONFIGDIR=/tmp/weak-self-dual-mpl python3 -m pytest -q tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis/tests
```

Expected: all analysis and synthetic end-to-end tests pass.

- [ ] **Step 8: Commit**

```bash
git add tracks/qmc/solutions/卧龙凤雏/weak-self-dual/analysis
git commit -m "feat: report weak self-dual central charge"
```

---

### Task 10: Add Reproducible Workflows and Documentation

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/configs/quick.toml`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/configs/production.toml`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/configs/refinement-1.toml`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/Makefile`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/run.sh`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/.gitignore`
- Create: `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/README.md`
- Modify: `tracks/qmc/solutions/卧龙凤雏/README.md`

**Interfaces:**
- Produces: `make setup`, `make test`, `make run-test`, `make run-quick`, and `make run`.
- Produces: `bash run.sh <config> [explicit-run-dir]`.

- [ ] **Step 1: Write the fixed production configurations**

Use `production.toml`:

```toml
widths = [6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30]
theta = 0.7853981633974483
beta = 0.881373587019543
base_seed = 122447
production_gates = true
refinement_level = 0

[sampling]
streams_per_width = 8
burn_in_layers_per_width = 20
measurement_layers_per_width = 100
block_layers_per_width = 5
stabilize_every_layers = 4
invariant_tolerance = 1.0e-9
```

Counts with `_per_width` are multipliers: for width `L`, Rust uses
`multiplier * L` layers. `refinement-1.toml` adds width `32`, uses `16`
streams, `200L` measurement layers, and `refinement_level=1`. The test and
quick configurations disable required production gates.

- [ ] **Step 2: Implement an output-safe runner**

Resolve all paths absolutely, reject output directories containing
`/solutions/`, create `raw/streams`, `processed`, `figures`, and a private
Matplotlib directory, build with `cargo --locked --release`, run `oracles`,
run `simulate`, then run Python analysis and the harness report renderer.
Print stage progress to stderr so long production runs remain observable.
The Rust simulation command writes the consolidated `raw/blocks.csv` before
Python starts.

- [ ] **Step 3: Add Make targets matching sibling benchmarks**

```make
test:
	cargo fmt --check
	cargo clippy --all-targets -- -D warnings
	cargo test --release
	MPLCONFIGDIR=/tmp/weak-self-dual-mpl .venv/bin/pytest -q
```

`clean-generated` must only explain where explicit run directories live; it
must not recursively delete user data.

- [ ] **Step 4: Document scientific and operational conventions**

The README must state the covariance convention, conditional Born formula,
vacuum boundary sign, layer schedule, vortex definition, scalar Lyapunov
estimator, fit equation, production/refinement contracts, every gate, commands,
artifact layout, and the distinction from IID Cho-Fisher or Nishimori disorder.
Link issue #122 and arXiv:2502.14034.

- [ ] **Step 5: Run the complete local test target**

Run:

```bash
cd tracks/qmc/solutions/卧龙凤雏/weak-self-dual
make setup
make test
make run-test
```

Expected: Rust and Python tests pass and the test run renders an HTML report
with non-required gates clearly labeled.

- [ ] **Step 6: Commit**

```bash
git add tracks/qmc/solutions/卧龙凤雏/weak-self-dual tracks/qmc/solutions/卧龙凤雏/README.md
git commit -m "docs: add weak self-dual benchmark workflow"
```

---

### Task 11: Run the Scientific Pilot and Production Verification

**Files:**
- Generated: `tracks/qmc/results/weak-self-dual-<timestamp>/`
- Modify only if a pre-production defect is proven: files under `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/`

**Interfaces:**
- Consumes: the completed runner and immutable gates.
- Produces: a preserved quick report and a preserved production report.

- [ ] **Step 1: Run the quick scientific pilot**

Run:

```bash
cd tracks/qmc/solutions/卧龙凤雏/weak-self-dual
make run-quick
```

Expected: exact oracles and Gaussian invariants pass; the report shows finite
Born-correlated gamma values for every quick width. Production-only precision
gates are informational.

- [ ] **Step 2: Inspect pilot diagnostics without changing gates**

Read `processed/summary.json` and confirm:

```text
oracle max_probability_error < 1e-11
oracle max_parity_error < 1e-10
maximum covariance invariant error <= 1e-9
all widths and configured streams are present
electric and magnetic densities are finite
```

If any fails, apply the systematic-debugging skill, add a reproducing test,
fix the defect, rerun `make test` and `make run-quick`, then commit the fix
before production.

- [ ] **Step 3: Run the immutable production configuration**

Run:

```bash
cd tracks/qmc/solutions/卧龙凤雏/weak-self-dual
make run
```

Expected: a new timestamped production directory containing raw artifacts,
processed tables, five plot families, `report.json`, and `report.html`.

- [ ] **Step 4: Apply the predeclared refinement rule if needed**

If and only if production fails `effective_sample_size`, `precision`, or the
predeclared \(L_{\min}\) stability gates while all scientific correctness
gates pass, preserve the first run and execute:

```bash
bash run.sh configs/refinement-1.toml
```

Do not use refinement to conceal a failed oracle, invariant, self-duality, or
residual-trend gate; diagnose those as implementation/model failures.

- [ ] **Step 5: Verify artifacts independently**

Run:

```bash
make test
git status --short
```

Open the final `processed/summary.json` and confirm the reported CI contains
`0.447`, its half-width is at most `0.01`, and `all_required_pass` is true.
Open the HTML report and visually check every plot, table, equation, path, and
verdict.

- [ ] **Step 6: Commit any report-index metadata, not generated results**

If the repository convention requires a stable pointer to the ignored run,
add only that pointer and the final numerical summary to the solution README:

```bash
git add tracks/qmc/solutions/卧龙凤雏/weak-self-dual/README.md
git commit -m "docs: record weak self-dual verification"
```

Do not force-add bulky raw data or generated figures unless the challenge
submission rules explicitly require them.

---

### Task 12: Final Verification and Review

**Files:**
- Review: all files under `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/`
- Review: `tracks/qmc/solutions/卧龙凤雏/README.md`

**Interfaces:**
- Consumes: completed implementation and final report.
- Produces: a clean, review-ready branch with evidence-backed results.

- [ ] **Step 1: Run the full verification suite from a clean shell**

```bash
cd tracks/qmc/solutions/卧龙凤雏/weak-self-dual
make test
```

Expected: formatting, clippy with warnings denied, all release Rust tests, and
all Python tests pass.

- [ ] **Step 2: Verify reproducibility**

Run the test configuration twice into two explicit temporary directories and
compare the hashes of raw oracle and stream artifacts after excluding elapsed
times and timestamps. Expected: scientific payloads and derived seeds are
identical.

- [ ] **Step 3: Check submission cleanliness**

```bash
git diff --check
git status --short
git log --oneline --decorate -12
```

Expected: no whitespace errors, no virtual environment, build output, cache,
or generated production data staged for commit, and one focused commit per
task.

- [ ] **Step 4: Request code review**

Invoke the `requesting-code-review` skill with the approved design, this plan,
the final test output, and the production summary. Address only evidence-backed
findings, using `receiving-code-review` before changing reviewed code.

- [ ] **Step 5: Re-run verification after review changes**

```bash
cd tracks/qmc/solutions/卧龙凤雏/weak-self-dual
make test
```

Expected: all checks still pass and the final production result remains
traceable to its exact committed simulator and analysis version.
