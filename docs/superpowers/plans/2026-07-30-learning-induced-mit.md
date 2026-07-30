# Learning-Induced Metal–Insulator Transition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run a standalone Rust/Python research pipeline that reproduces the known \(XY\)-line learning transition, locates a candidate generic DIII metal–insulator transition, and reports a carefully qualified Casimir amplitude and candidate effective central charge.

**Architecture:** A new `learning-mit` Rust crate owns angle conversion, Gaussian Born trajectories, entanglement and Lyapunov observables, deterministic scheduling, and atomic raw artifacts. A Python package validates the frozen artifacts, performs hierarchical finite-size analysis and anisotropy calibration, and renders numerically identical English and Simplified Chinese HTML/PDF reports. The completed `weak-self-dual` implementation remains untouched and is used only as an external regression oracle.

**Tech Stack:** Rust 2021, `nalgebra`, `num-complex`, `rand_xoshiro::Xoshiro256PlusPlus`, `rayon`, `serde`, `clap`, `sha2`; Python 3 with NumPy, SciPy, Matplotlib, ReportLab, pypdf, and pytest.

## Global Constraints

- Create all new implementation under `tracks/qmc/solutions/卧龙凤雏/learning-mit/`.
- Do not modify `tracks/qmc/solutions/卧龙凤雏/weak-self-dual/`.
- Rust performs every stochastic trajectory, Gaussian update, Lyapunov evolution, and physical observable calculation.
- Python performs deterministic validation, statistics, fitting, plotting, and rendering only.
- Pin the physical RNG to `rand_xoshiro = "=0.8.1"` and instantiate `Xoshiro256PlusPlus`.
- Use the projective-measurement model and complex Kramers–Wannier convention in the approved design specification.
- Treat the \(XY\) line as a class-D validation slice and \(\theta=0.45\pi\), \(\phi>0\) away from symmetry planes as the generic DIII slice.
- Production target is 60 minutes; stop new ordinary work at minute 55, allow only scientifically justified redundancy, stop new work at minute 85, and finish atomically by minute 90.
- Never report standalone \(c_{\rm eff}\) when anisotropy \(\alpha\) fails its stability gate; report \(c_{\rm eff}\alpha\) instead.
- Mark every DIII result exploratory and keep it visually distinct from the three verified central-charge benchmarks.
- English and Simplified Chinese reports must use one frozen summary and contain identical numerical claims.
- Follow TDD for every implementation task and commit after each green task.

## File Map

- `src/config.rs`, `src/rng.rs`, and `src/schema.rs`: immutable run contracts,
  deterministic seed derivation, artifact/status types, and runtime limits.
- `src/angles.rs`: the only implementation of physical-angle to complex-gate
  conversion and Kramers–Wannier branch conventions.
- `src/gaussian.rs`: covariance measurements, rotations, invariants,
  entanglement, and equal-time correlations.
- `src/circuit.rs` and `src/sampler.rs`: gate ordering, Born/IID modes,
  trajectories, block observables, and stream estimates.
- `src/lyapunov.rs`: single-particle transfer matrices and periodic complex QR.
- `src/oracles.rs`: independent dense Hilbert-space and physical-limit checks.
- `src/runner.rs` and `src/main.rs`: CLI, resumable scheduling, atomic writes,
  task requests, and runtime decisions.
- `analysis/data_io.py`: the sole trusted boundary from hashed Rust artifacts
  to NumPy arrays.
- `analysis/entanglement.py` and `analysis/phase.py`: arc-model fits, phase
  evidence, brackets, and refinement requests.
- `analysis/bootstrap.py`, `analysis/casimir.py`,
  `analysis/anisotropy.py`, and `analysis/gates.py`: joint uncertainty,
  universal-amplitude fits, sound-velocity calibration, and claim states.
- `analysis/locale.py`, `analysis/plots.py`, `analysis/report_model.py`, and
  the renderers: one numerical report model with bilingual presentation.
- `run.sh` and `Makefile`: tested end-to-end entry points only; no scientific
  formulas live in shell.

---

### Task 1: Standalone crate, configuration contract, and deterministic RNG

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/Cargo.toml`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/src/lib.rs`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/src/config.rs`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/src/rng.rs`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/src/schema.rs`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/src/main.rs`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/configs/test.toml`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/tests/config_rng.rs`

**Interfaces:**
- Produces: `RunConfig::load(&Path) -> Result<RunConfig>`
- Produces: `RunConfig::validate(&self) -> Result<()>`
- Produces: `derive_seed(base: u64, stage: u64, angle: usize, width: usize, stream: usize, purpose: u64) -> u64`
- Produces: schema structs `RunManifest`, `TaskRecord`, `SeedRecord`, and `RunStatus`
- Consumes: no new project code

- [ ] **Step 1: Write failing configuration and RNG tests**

```rust
#[test]
fn production_budget_is_bounded() {
    let mut config = fixture();
    config.runtime.target_seconds = 3600;
    config.runtime.hard_stop_seconds = 5100;
    config.runtime.finalize_reserve_seconds = 300;
    config.validate().unwrap();
    config.runtime.hard_stop_seconds = 5101;
    assert!(config.validate().unwrap_err().to_string().contains("5100"));
}

#[test]
fn seed_derivation_separates_every_coordinate() {
    let a = derive_seed(122, 1, 2, 16, 0, 0);
    let b = derive_seed(122, 1, 2, 16, 1, 0);
    let c = derive_seed(122, 2, 2, 16, 0, 0);
    assert_ne!(a, b);
    assert_ne!(a, c);
    assert_eq!(a, derive_seed(122, 1, 2, 16, 0, 0));
}
```

- [ ] **Step 2: Run the test and verify the red state**

Run: `cargo test --test config_rng -- --nocapture`

Expected: compilation fails because `RunConfig` and `derive_seed` do not exist.

- [ ] **Step 3: Implement the minimal configuration and schema**

Define these exact configuration shapes:

```rust
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RunConfig {
    pub base_seed: u64,
    pub production_gates: bool,
    pub invariant_tolerance: f64,
    pub runtime: RuntimeBudget,
    pub stages: Vec<StageConfig>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RuntimeBudget {
    pub target_seconds: u64,
    pub ordinary_stop_seconds: u64,
    pub hard_stop_seconds: u64,
    pub finalize_reserve_seconds: u64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StageConfig {
    pub name: String,
    pub theta_pi: f64,
    pub phi_pi: Vec<f64>,
    pub widths: Vec<usize>,
    pub streams: usize,
    pub burn_in_layers_per_width: usize,
    pub measurement_layers_per_width: usize,
    pub block_layers_per_width: usize,
}
```

Validation must enforce the exact 3600/3300/5100/300 production timing
contract, the derived total limit of 5400 seconds, unique increasing even widths, finite
angles in the first octant, positive complete blocks, and nonempty stages.
Use SplitMix64-style mixing for coordinate-separated deterministic seeds and
return `Xoshiro256PlusPlus::seed_from_u64(seed)` from `make_rng`.

- [ ] **Step 4: Add the CLI skeleton**

Expose these subcommands without implementing their bodies yet:

```text
learning-mit oracles --config configs/test.toml --run-dir /tmp/learning-mit-test
learning-mit benchmark --config configs/test.toml --run-dir /tmp/learning-mit-test
learning-mit simulate --config configs/test.toml --run-dir /tmp/learning-mit-test
learning-mit negative-control --config configs/test.toml --run-dir /tmp/learning-mit-test
```

Each unimplemented command must return an explicit
`"runner is unavailable before the Gaussian core is validated"` error rather
than succeeding.

- [ ] **Step 5: Run the focused and crate tests**

Run: `cargo test --test config_rng -- --nocapture`

Expected: all configuration and RNG tests pass.

Run: `cargo test`

Expected: all crate tests pass and no command silently succeeds.

- [ ] **Step 6: Commit**

```bash
git add tracks/qmc/solutions/卧龙凤雏/learning-mit
git commit -m "feat: scaffold learning MIT simulation contract"
```

---

### Task 2: Complex angle conversion and Kramers–Wannier gates

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/src/angles.rs`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/tests/angles.rs`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/src/lib.rs`

**Interfaces:**
- Consumes: validated `theta_pi` and `phi_pi` from `StageConfig`
- Produces: `GateCouplings::from_pi_units(theta_pi: f64, phi_pi: f64) -> Result<GateCouplings>`
- Produces: `kw_dual(z: Complex64) -> Result<Complex64>`
- Produces: `GateCouplings { theta, phi, j, j_dual, phi_dual }`

- [ ] **Step 1: Write failing analytic-limit tests**

```rust
#[test]
fn x_plus_z_is_real_self_dual() {
    let g = GateCouplings::from_pi_units(0.25, 0.0).unwrap();
    let expected = (1.0_f64 + 2.0_f64.sqrt()).ln();
    assert!((g.j - expected).abs() < 1e-12);
    assert!((g.j_dual - expected).abs() < 1e-12);
    assert!(g.phi_dual.abs() < 1e-12);
}

#[test]
fn xy_line_matches_closed_form() {
    let phi_pi = 0.25;
    let g = GateCouplings::from_pi_units(0.5, phi_pi).unwrap();
    let phi = std::f64::consts::PI * phi_pi;
    assert!(g.j.abs() < 1e-12);
    assert!((g.j_dual + (phi / 2.0).tan().ln()).abs() < 1e-12);
    assert!((g.phi_dual + std::f64::consts::FRAC_PI_2).abs() < 1e-12);
}
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `cargo test --test angles -- --nocapture`

Expected: compilation fails because `GateCouplings` is undefined.

- [ ] **Step 3: Implement the exact complex map**

```rust
pub fn kw_dual(z: Complex64) -> Result<Complex64> {
    let value = -(z * 0.5).tanh().ln();
    if !value.re.is_finite() || !value.im.is_finite() {
        bail!("complex Kramers-Wannier map is non-finite");
    }
    Ok(value)
}

pub fn from_pi_units(theta_pi: f64, phi_pi: f64) -> Result<Self> {
    let theta = PI * theta_pi;
    let phi = PI * phi_pi;
    let cosine = theta.cos().clamp(-1.0, 1.0);
    let j = cosine.atanh();
    let dual = kw_dual(Complex64::new(j, phi))?;
    Ok(Self { theta, phi, j, j_dual: dual.re, phi_dual: dual.im })
}
```

Normalize the logarithm branch so the first-octant \(XY\) limit has
\(\phi_d=-\pi/2\). Reject the exact singular \(X\) endpoint in production;
test it only through a finite-angle limiting oracle.

- [ ] **Step 4: Add property tests**

Test `KW(conj(z)) == conj(KW(z))`, the defining
`exp(-dual) == tanh(z/2)` relation, self-dual-line residuals, and finite
values for every approved scan point.

- [ ] **Step 5: Run tests**

Run: `cargo test --test angles -- --nocapture`

Expected: all analytic and property tests pass with maximum residual below
`1e-12`.

- [ ] **Step 6: Commit**

```bash
git add tracks/qmc/solutions/卧龙凤雏/learning-mit/src/angles.rs tracks/qmc/solutions/卧龙凤雏/learning-mit/src/lib.rs tracks/qmc/solutions/卧龙凤雏/learning-mit/tests/angles.rs
git commit -m "feat: implement generic measurement-angle couplings"
```

---

### Task 3: Majorana covariance measurements, rotations, and entropy

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/src/gaussian.rs`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/tests/gaussian.rs`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/src/lib.rs`

**Interfaces:**
- Consumes: `nalgebra::DMatrix<f64>`
- Produces: `MajoranaState::paired_vacuum(width: usize) -> Result<Self>`
- Produces: `outcome_probability(&self, gate: MeasurementGate, outcome: i8) -> Result<f64>`
- Produces: `apply_measurement(&mut self, gate: MeasurementGate, outcome: i8) -> Result<UpdateStats>`
- Produces: `apply_rotation(&mut self, a: usize, b: usize, angle: f64) -> Result<()>`
- Produces: `interval_entropy(&self, first_site: usize, sites: usize) -> Result<f64>`
- Produces: `connected_parity_correlation(&self, left: usize, right: usize) -> Result<f64>`

- [ ] **Step 1: Write failing measurement and rotation tests**

```rust
#[test]
fn rotation_and_inverse_recover_covariance() {
    let mut state = MajoranaState::paired_vacuum(3).unwrap();
    let before = state.matrix().clone();
    state.apply_rotation(1, 2, 0.37).unwrap();
    state.apply_rotation(1, 2, -0.37).unwrap();
    assert_relative_eq!(state.matrix(), &before, epsilon = 1e-12);
}

#[test]
fn born_probabilities_normalize() {
    let state = MajoranaState::paired_vacuum(2).unwrap();
    let gate = MeasurementGate { a: 0, b: 1, observable_sign: 1, strength: 0.8 };
    let total = state.outcome_probability(gate, 1).unwrap()
        + state.outcome_probability(gate, -1).unwrap();
    assert!((total - 1.0).abs() < 1e-14);
}
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `cargo test --test gaussian -- --nocapture`

Expected: compilation fails because `MajoranaState` is undefined.

- [ ] **Step 3: Implement measurement and rotation**

Port the verified rational covariance measurement update into the standalone
crate, keeping names distinct from `weak-self-dual`. Implement rotation as

```rust
let mut r = DMatrix::identity(dimension, dimension);
r[(a, a)] = angle.cos();
r[(a, b)] = -angle.sin();
r[(b, a)] = angle.sin();
r[(b, b)] = angle.cos();
self.matrix = &r * &self.matrix * r.transpose();
```

Antisymmetrize after updates and expose
`InvariantErrors { antisymmetry, purity }`.

- [ ] **Step 4: Implement interval entropy and parity correlations**

For a \(2\ell\times2\ell\) restricted covariance, use singular values
\(\nu_k\), remove their pair duplication, clamp to \([0,1]\), and sum

\[
-\frac{1+\nu_k}{2}\log\frac{1+\nu_k}{2}
-\frac{1-\nu_k}{2}\log\frac{1-\nu_k}{2}.
\]

Use Wick's theorem for the connected onsite-parity correlation. Add paired,
Bell-pair, complement-symmetry, and translated-correlation tests.

- [ ] **Step 5: Run tests**

Run: `cargo test --test gaussian -- --nocapture`

Expected: probabilities normalize, rotations preserve purity, inverse
rotations recover the state, and entropy fixtures agree below `1e-11`.

- [ ] **Step 6: Commit**

```bash
git add tracks/qmc/solutions/卧龙凤雏/learning-mit/src/gaussian.rs tracks/qmc/solutions/卧龙凤雏/learning-mit/src/lib.rs tracks/qmc/solutions/卧龙凤雏/learning-mit/tests/gaussian.rs
git commit -m "feat: add Gaussian measurement and unitary evolution"
```

---

### Task 4: Generic Born circuit and trajectory observables

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/src/circuit.rs`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/src/sampler.rs`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/tests/circuit_sampler.rs`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/src/lib.rs`

**Interfaces:**
- Consumes: `GateCouplings`, `MajoranaState`, and `Xoshiro256PlusPlus`
- Produces: `GenericCircuit::new(width: usize, couplings: GateCouplings, sector: BoundarySector) -> Result<Self>`
- Produces: `sample_period(&self, state: &mut MajoranaState, rng: &mut Xoshiro256PlusPlus, mode: SamplingMode) -> Result<PeriodSample>`
- Produces: `estimate_stream(config: &RunConfig, stage_index: usize, angle_index: usize, width: usize, stream: usize, mode: SamplingMode) -> Result<StreamEstimate>`

- [ ] **Step 1: Write failing gate-order and sampling tests**

```rust
#[test]
fn one_period_has_exactly_two_measurement_rows() {
    let circuit = fixture_circuit(4, 0.5, 0.25);
    let mut state = MajoranaState::paired_vacuum(4).unwrap();
    let mut rng = make_rng(7);
    let sample = circuit.sample_period(&mut state, &mut rng, SamplingMode::Born).unwrap();
    assert_eq!(sample.onsite.len(), 4);
    assert_eq!(sample.bond.len(), 4);
    assert_eq!(sample.conditional_entropy_terms, 8);
}

#[test]
fn fixed_seed_replays_trajectory() {
    assert_eq!(run_fixture(122), run_fixture(122));
}
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `cargo test --test circuit_sampler -- --nocapture`

Expected: compilation fails because `GenericCircuit` is undefined.

- [ ] **Step 3: Construct onsite and bond gate specifications**

Represent each gate as:

```rust
pub struct ConditionalGate {
    pub measurement: MeasurementGate,
    pub positive_rotation: f64,
    pub negative_rotation: f64,
}
```

Use real strengths `j` and `j_dual`. Apply the sampled measurement first,
then the corresponding phase rotation. The wraparound bond sign is
`-wilson_loop * fermion_parity`. Keep all sign/factor decisions isolated in
`GenericCircuit::new` so dense oracles can reject them.

- [ ] **Step 4: Implement Born and IID diagnostic modes**

`SamplingMode::Born` draws from the conditional probability.
`SamplingMode::IidDiagnostic` draws unbiased signs but still records the Born
probability of the forced outcome. Only `Born` may contribute to physical
summaries. Compute conditional binary entropy before the draw and accumulate
it as the Rao–Blackwellized record-free-energy estimator.

- [ ] **Step 5: Record block observables**

For every completed block, return:

```rust
pub struct BlockEstimate {
    pub block_index: usize,
    pub gamma: f64,
    pub half_chain_entropy: f64,
    pub entropy_arc: Vec<EntropyPoint>,
    pub spatial_correlations: Vec<CorrelationPoint>,
    pub min_probability: f64,
    pub max_antisymmetry_error: f64,
    pub max_purity_error: f64,
}
```

Divide total conditional entropy by `2 * completed_periods` to obtain the
per-row \(\gamma_1(L)\).

- [ ] **Step 6: Run focused tests**

Run: `cargo test --test circuit_sampler -- --nocapture`

Expected: deterministic replay passes, Born probabilities remain in
`(0,1]`, and IID mode is tagged diagnostic.

- [ ] **Step 7: Commit**

```bash
git add tracks/qmc/solutions/卧龙凤雏/learning-mit/src/circuit.rs tracks/qmc/solutions/卧龙凤雏/learning-mit/src/sampler.rs tracks/qmc/solutions/卧龙凤雏/learning-mit/src/lib.rs tracks/qmc/solutions/卧龙凤雏/learning-mit/tests/circuit_sampler.rs
git commit -m "feat: sample generic Born Gaussian trajectories"
```

---

### Task 5: Single-particle transfer evolution and anisotropy inputs

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/src/lyapunov.rs`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/tests/lyapunov.rs`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/src/circuit.rs`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/src/sampler.rs`

**Interfaces:**
- Consumes: the exact forced gate sequence emitted by `sample_period`
- Produces: `LyapunovAccumulator::new(dimension: usize, qr_every: usize) -> Result<Self>`
- Produces: `push(&mut self, gate: &DMatrix<Complex64>) -> Result<()>`
- Produces: `spectrum(&self) -> Result<Vec<f64>>`
- Adds to `BlockEstimate`: `lyapunov: Vec<f64>`

- [ ] **Step 1: Write failing QR and clean-limit tests**

```rust
#[test]
fn diagonal_transfer_recovers_known_exponents() {
    let mut acc = LyapunovAccumulator::new(2, 1).unwrap();
    let gate = DMatrix::from_diagonal(&DVector::from_vec(vec![
        Complex64::new(2.0, 0.0),
        Complex64::new(0.5, 0.0),
    ]));
    for _ in 0..10 { acc.push(&gate).unwrap(); }
    let values = acc.spectrum().unwrap();
    assert!((values[0] - 2.0_f64.ln()).abs() < 1e-12);
    assert!((values[1] + 2.0_f64.ln()).abs() < 1e-12);
}
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `cargo test --test lyapunov -- --nocapture`

Expected: compilation fails because `LyapunovAccumulator` is undefined.

- [ ] **Step 3: Implement periodic complex QR**

Propagate a complex single-particle basis with the same forced gates as the
covariance trajectory. Every `qr_every` layers, compute QR, make diagonal
phases positive, accumulate `ln(abs(R_ii))`, and replace the propagated basis
with `Q`. Normalize by completed layers in `spectrum`.

- [ ] **Step 4: Expose the temporal gap**

Store at least the four leading exponents. Define

```rust
pub fn temporal_gap(exponents: &[f64]) -> Result<f64> {
    let gap = exponents[0] - exponents[1];
    if !gap.is_finite() || gap <= 0.0 { bail!("temporal gap is not positive"); }
    Ok(gap)
}
```

The Python anisotropy stage will combine this gap with the spatial scaling
dimension extracted from connected parity correlations. Do not compute
\(\alpha\) in Rust.

- [ ] **Step 5: Cross-check gate matrices**

For width 2, compare each single-particle gate with the corresponding
covariance transformation and confirm that the induced covariance agrees
below `1e-10`.

- [ ] **Step 6: Run tests and commit**

Run: `cargo test --test lyapunov -- --nocapture`

Expected: analytic exponents and covariance-induced transformations pass.

```bash
git add tracks/qmc/solutions/卧龙凤雏/learning-mit/src/lyapunov.rs tracks/qmc/solutions/卧龙凤雏/learning-mit/src/circuit.rs tracks/qmc/solutions/卧龙凤雏/learning-mit/src/sampler.rs tracks/qmc/solutions/卧龙凤雏/learning-mit/tests/lyapunov.rs
git commit -m "feat: track generic-circuit Lyapunov spectrum"
```

---

### Task 6: Dense Hilbert-space and physical-limit oracles

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/src/oracles.rs`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/tests/oracles.rs`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/src/main.rs`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/src/schema.rs`

**Interfaces:**
- Consumes: `GenericCircuit` forced outcome paths
- Produces: `run_oracles(config: &RunConfig) -> Result<OracleArtifact>`
- Produces: `DenseComparison`, `LimitOracle`, and `NegativeControlOracle`

- [ ] **Step 1: Write failing dense-enumeration test**

Enumerate all outcomes for two circuit periods at \(L=2\), and require:

```rust
assert!(comparison.max_joint_probability_error < 1e-11);
assert!(comparison.max_covariance_error < 1e-10);
assert!(comparison.max_entropy_error < 1e-10);
assert!((comparison.total_probability - 1.0).abs() < 1e-12);
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `cargo test --test oracles -- --nocapture`

Expected: compilation fails because dense enumeration is absent.

- [ ] **Step 3: Implement dense gates independently**

Build Pauli matrices and Kronecker products with
`DMatrix<Complex64>`. Apply the exact \(M_Z\) and \(M_X\) operators from the
paper directly to state vectors. Do not call covariance-update code inside
the dense implementation. Normalize every branch and compare its probability,
parities, covariance, and interval entropy.

- [ ] **Step 4: Implement physical-limit regressions**

Add:

- a dev-only path dependency
  `weak-self-dual = { path = "../weak-self-dual" }` and an \(X+Z\) comparison
  that applies the same forced outcomes to both public covariance types;
- \(X\)-like finite angle with decreasing half-chain entropy versus \(L\);
- exact \(Y\) gates equal to Majorana swaps and produce increasing
  volume-law entropy;
- Born and IID diagnostic means differ by a predeclared z-score on a small
  nontrivial angle;
- generic off-plane gate matrices fail the special class-D block-decomposition
  residual test, while \(XY\) passes it.

- [ ] **Step 5: Wire the `oracles` CLI**

Write `raw/oracles.json` atomically and place all thresholds and pass/fail
fields in the artifact. A failed required oracle returns a nonzero exit.

- [ ] **Step 6: Run all Rust tests**

Run: `cargo test --all-targets`

Expected: all tests pass; dense comparisons meet the declared tolerances.

- [ ] **Step 7: Commit**

```bash
git add tracks/qmc/solutions/卧龙凤雏/learning-mit
git commit -m "test: validate generic Born circuit against dense oracles"
```

---

### Task 7: Resumable scheduler, runtime policy, and atomic artifacts

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/src/runner.rs`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/tests/runner_cli.rs`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/src/main.rs`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/src/schema.rs`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/configs/pilot.toml`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/configs/production.toml`

**Interfaces:**
- Consumes: `estimate_stream` and `RunConfig`
- Produces: `run_simulation(config_path: &Path, run_dir: &Path, mode: SamplingMode) -> Result<RunManifest>`
- Produces: `run_requested_tasks(config_path: &Path, run_dir: &Path, request_path: &Path) -> Result<RunManifest>`
- Produces: `RuntimeDecision::{Continue, OrdinaryStop, ReserveAllowed, HardStop}`
- Produces: `raw/blocks.csv`, `raw/streams/*.json`, and `manifest.json`

- [ ] **Step 1: Write failing runtime-policy tests with a fake clock**

```rust
#[test]
fn reserve_requires_scientific_reason() {
    let policy = RuntimePolicy::production();
    assert_eq!(policy.decision(3400, ReserveReason::None), RuntimeDecision::OrdinaryStop);
    assert_eq!(policy.decision(3400, ReserveReason::LargestWidthIncomplete), RuntimeDecision::ReserveAllowed);
    assert_eq!(policy.decision(5100, ReserveReason::LargestWidthIncomplete), RuntimeDecision::HardStop);
}
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `cargo test --test runner_cli -- --nocapture`

Expected: compilation fails because `RuntimePolicy` is undefined.

- [ ] **Step 3: Implement priority scheduling**

Schedule in this order:

1. approved oracles;
2. \(XY\) coarse angles and widths;
3. DIII coarse endpoints, then interior angles;
4. bracket refinement;
5. larger widths at the current candidate;
6. extra streams and measurement depth;
7. anisotropy-focused Lyapunov blocks.

Persist every completed stream as
`raw/streams/<stage>-aNN-LNN-sNNN.json`. On resume, validate schema, config
subsection, seed, and SHA-256 before reuse.

The production configuration must contain the exact approved coarse stages:

```toml
[[stages]]
name = "xy-coarse"
theta_pi = 0.5
phi_pi = [0.18, 0.21, 0.24, 0.25, 0.27, 0.30]
widths = [8, 12, 16, 24]
streams = 4

[[stages]]
name = "diii-coarse"
theta_pi = 0.45
phi_pi = [0.06, 0.10, 0.14, 0.18, 0.22, 0.26, 0.30, 0.34]
widths = [8, 12, 16, 24]
streams = 4
```

The remaining layer and block fields use the approved targets. Refined tasks
are not guessed by Rust: they are read from the hash-checked
`processed/refinement_request.json` written by Task 8.

- [ ] **Step 4: Implement atomic writes and task ledger**

Write to a sibling `.tmp`, flush, `sync_all`, and rename. Record task state,
elapsed seconds, reserve reason, and artifact hashes in `manifest.json`.
Never add a partial block to `raw/blocks.csv`.

- [ ] **Step 5: Wire benchmark, simulate, and negative-control CLI commands**

`benchmark` runs a fixed \(L=16\), two-stream microbenchmark and writes a
cost forecast. `simulate` runs Born tasks. `negative-control` runs only the
small predeclared IID diagnostic and marks every artifact nonphysical.
`simulate --task-request processed/refinement_request.json` runs only the
requested bracket widths and angles while continuing the original runtime
ledger.

- [ ] **Step 6: Run restart and timeout tests**

Run: `cargo test --test runner_cli -- --nocapture`

Expected: interrupted runs reuse complete streams, reject corrupt streams,
respect all clock boundaries, and produce byte-identical CSV for fixed seeds.

- [ ] **Step 7: Commit**

```bash
git add tracks/qmc/solutions/卧龙凤雏/learning-mit
git commit -m "feat: add resumable budget-aware MIT runner"
```

---

### Task 8: Frozen-data loading and phase-classification analysis

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/__init__.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/data_io.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/entanglement.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/phase.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/test_data_io.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/test_entanglement.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/test_phase.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/requirements.txt`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/pytest.ini`

**Interfaces:**
- Consumes: manifest and Rust stream artifacts from Task 7
- Produces: `load_run(run_dir: Path) -> LoadedRun`
- Produces: `fit_entropy_arc(points: np.ndarray, models: tuple[str, ...]) -> EntropyFitSet`
- Produces: `classify_angle(fits_by_width: dict[int, EntropyFitSet]) -> PhaseEvidence`
- Produces: `locate_bracket(evidence: list[PhaseEvidence]) -> TransitionBracket`
- Produces: `propose_refinement(loaded: LoadedRun, budget_forecast: dict) -> dict`

- [ ] **Step 1: Write failing schema/hash tests**

```python
def test_load_run_rejects_changed_stream_hash(frozen_run):
    path = next((frozen_run / "raw/streams").glob("*.json"))
    path.write_text(path.read_text() + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        load_run(frozen_run)
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `.venv/bin/python -m pytest analysis/tests/test_data_io.py -q`

Expected: import fails because `analysis.data_io` does not exist.

- [ ] **Step 3: Implement strict loading**

Validate schema version, config equality, seeds, stage/angle/width membership,
consecutive blocks, finite values, probability ranges, physical-mode tags,
artifact hashes, and complete blocks. Return immutable dataclasses containing
arrays grouped by `(stage, theta_pi, phi_pi, width, stream)`.

- [ ] **Step 4: Write and run failing synthetic phase tests**

Construct deterministic synthetic area-law, logarithmic, and
squared-logarithmic arcs. Require the correct model to have the lowest AICc
and require `locate_bracket` to reject evidence with no phase change.

Run: `.venv/bin/python -m pytest analysis/tests/test_entanglement.py analysis/tests/test_phase.py -q`

Expected: tests fail because fit functions are undefined.

- [ ] **Step 5: Implement weighted arc fits and evidence**

Use linear design matrices for `constant`, `log`, `log2`, `log_log2`, and
`page_log_log2`. Return coefficients, covariance, AICc, residuals, and model
weights. Classify only when trends persist over at least three widths; return
`inconclusive` otherwise.

- [ ] **Step 6: Implement the refinement request**

When the \(XY\) gate and DIII endpoint gates pass, write a request with this
schema:

```json
{
  "schema_version": 1,
  "status": "bracketed",
  "stage": "diii-refine",
  "theta_pi": 0.45,
  "phi_pi": [0.18, 0.20, 0.22],
  "widths": [8, 12, 16, 20, 24, 28, 32],
  "streams": 8,
  "burn_in_layers_per_width": 12,
  "measurement_layers_per_width": 40,
  "block_layers_per_width": 5
}
```

The shown angles are the test fixture. Production values are the detected
lower endpoint, midpoint, and upper endpoint. If no bracket exists, write
`status: "inconclusive"` with an empty angle list. Hash the request into the
manifest before Rust accepts it.

- [ ] **Step 7: Run Python tests and commit**

Run: `.venv/bin/python -m pytest analysis/tests -q`

Expected: loader and synthetic phase tests pass.

```bash
git add tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis tracks/qmc/solutions/卧龙凤雏/learning-mit/pytest.ini
git commit -m "feat: classify learning MIT from frozen entanglement data"
```

---

### Task 9: Bootstrap, Casimir fitting, anisotropy, and claim gates

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/bootstrap.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/casimir.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/anisotropy.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/gates.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/test_bootstrap.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/test_casimir.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/test_anisotropy.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/test_gates.py`

**Interfaces:**
- Consumes: `LoadedRun` and `TransitionBracket`
- Produces: `fit_casimir(widths, gamma, covariance, minimum_width, correction) -> CasimirFit`
- Produces: `fit_spatial_dimension(correlation_blocks, widths, window) -> SpatialFit`
- Produces: `calibrate_alpha(spatial_fit, lyapunov_blocks, window) -> AlphaFit`
- Produces: `bootstrap_candidate(loaded, bracket, samples, seed) -> CandidateDistribution`
- Produces: `evaluate_claim_gates(...) -> ClaimDecision`

- [ ] **Step 1: Write failing synthetic Casimir test**

```python
def test_casimir_recovers_amplitude_with_l3_correction():
    widths = np.array([8, 12, 16, 20, 24, 28, 32], dtype=float)
    expected = 0.41
    gamma = 0.73 * widths - np.pi * expected / (6 * widths) + 1.2 / widths**3
    fit = fit_casimir(widths, gamma, np.eye(len(widths)) * 1e-10, 8, "l3")
    assert fit.casimir_amplitude == pytest.approx(expected, abs=1e-8)
```

- [ ] **Step 2: Run tests and verify the red state**

Run: `.venv/bin/python -m pytest analysis/tests/test_casimir.py analysis/tests/test_anisotropy.py -q`

Expected: imports fail because the fit modules do not exist.

- [ ] **Step 3: Implement correlated Casimir fits**

Use generalized least squares for

\[
\gamma(L)=f_\infty L-\pi A/(6L)+a/L^3,
\quad A=c_{\rm eff}\alpha.
\]

Require at least five widths and full-rank covariance after a documented
eigenvalue floor. Implement `none`, `l3`, and `l3_l5` sensitivity variants.

- [ ] **Step 4: Implement anisotropy calibration**

Fit the spatial connected-parity correlation to

\[
C_x(r)\propto
\left[\frac{L}{\pi}\sin\frac{\pi r}{L}\right]^{-2\Delta}
\]

and combine \(\Delta\) with the leading positive temporal Lyapunov gap \(g\):

\[
\alpha=\frac{gL}{2\pi\Delta}.
\]

Repeat over predeclared spatial windows
`[L/8, 3L/8]`, `[L/6, L/3]` and Lyapunov block deletions. The alpha gate
passes only when all estimates are positive, their intervals overlap, and
the maximum window shift is below two pooled standard errors.

- [ ] **Step 5: Implement hierarchical joint bootstrap**

Resample streams, then complete blocks within streams. In each replicate,
recompute phase evidence, bracket interpolation, Casimir fit, spatial
dimension, alpha, and the ratio `central_charge = amplitude / alpha`.
Preserve angle/width covariance by using shared resampling indices where
streams share the same seed family.

- [ ] **Step 6: Implement exact result-state gates**

Return one of:

```python
"xy_reproduced_diii_candidate"
"xy_reproduced_diii_inconclusive"
"validation_failed"
```

Require the paper's \(XY\) bracket overlap, at least five DIII widths,
opposite phase evidence on the two bracket sides, oracle pass, invariant pass,
minimum effective sample size, fit stability, and alpha stability before
publishing standalone `central_charge`.

- [ ] **Step 7: Run all analysis tests and commit**

Run: `.venv/bin/python -m pytest analysis/tests -q`

Expected: synthetic amplitude, alpha, bootstrap covariance, and claim-state
tests pass.

```bash
git add tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis
git commit -m "feat: quantify exploratory DIII Casimir evidence"
```

---

### Task 10: Bilingual plots, HTML/PDF reports, and output verification

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/locale.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/plots.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/report_model.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/html_renderer.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/pdf_renderer.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/verify_outputs.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/run_analysis.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/test_reports.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/test_plots.py`

**Interfaces:**
- Consumes: one frozen `summary.json`
- Produces: `make_plots(summary, locale, output_dir) -> list[Path]`
- Produces: `build_report(summary, locale) -> ReportDocument`
- Produces: `render_html(document, destination) -> Path`
- Produces: `render_pdf(document, destination) -> Path`
- Produces: `verify_report_pair(run_dir) -> VerificationResult`
- Produces: `run_analysis.py --phase-only "$RUN_DIR"` for the refinement request
- Produces: `run_analysis.py --final "$RUN_DIR"` for frozen summaries/reports
- Produces: root-level `summary.json`, `report.html`, `report-zh.html`,
  `report.pdf`, and `report-zh.pdf`

- [ ] **Step 1: Write failing bilingual identity tests**

Require both report models to have identical serialized numeric facts,
identical result state, identical figure data hashes, and different localized
reader-facing strings. Require Chinese output to contain no English renderer
labels such as `Contents`, `Figure`, or `Interpretation limit`.

- [ ] **Step 2: Run tests and verify the red state**

Run: `.venv/bin/python -m pytest analysis/tests/test_reports.py analysis/tests/test_plots.py -q`

Expected: report and plot modules are missing.

- [ ] **Step 3: Implement plots from frozen arrays**

Generate, in both locales:

- \(XY\) phase-evidence scan and reference window;
- DIII coarse scan and selected bracket;
- representative entanglement arcs;
- fitted \(v,c',c\) versus angle and width;
- Casimir finite-size fit and residuals;
- bootstrap amplitude distribution;
- spatial-dimension and temporal-gap calibration;
- alpha window sensitivity;
- Born versus IID negative control;
- runtime allocation and effective sample size.

Use no web resources or external fonts in HTML. Use a discovered local CJK
font for PDF and fail explicitly when none is available.

- [ ] **Step 4: Implement the shared report model**

Sections must cover concept, surface-code mapping, DIII/class-D distinction,
Gaussian implementation, Born sampling, parameter budget, oracle evidence,
\(XY\) reproduction, DIII candidate, Casimir fit, anisotropy, error analysis,
claim boundary, reproducibility, and code/data inventory. The status banner
must visibly say “exploratory”/“探索性”.

- [ ] **Step 5: Render and verify**

HTML must be self-contained with embedded PNG data and responsive tables.
PDF must be A4, text-extractable, contain every required section, and include
all figures. Verification must reject unfinished-placeholder markers, missing
hashes, conflicting numbers, missing claim labels, and a standalone central
charge when the alpha gate is false.

- [ ] **Step 6: Run report tests and commit**

Run: `.venv/bin/python -m pytest analysis/tests -q`

Expected: all analysis, localization, plot, and report tests pass.

```bash
git add tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis
git commit -m "feat: report learning MIT evidence bilingually"
```

---

### Task 11: End-to-end commands, documentation, and tiny-run regression

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/Makefile`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/run.sh`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/README.md`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/tests/cli.rs`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/test_end_to_end.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/README.md`

**Interfaces:**
- Consumes: all Rust and Python components
- Produces: `make setup`, `make test`, `make run-test`, `make run-pilot`, and `make run-production`

- [ ] **Step 1: Write failing CLI and end-to-end tests**

The tiny run must execute oracles, benchmark, Born simulation, IID diagnostic,
analysis, bilingual plots, HTML, and PDF in a temporary directory. Assert the
manifest hashes every stable artifact and both reports share one summary hash.

- [ ] **Step 2: Run tests and verify the red state**

Run: `cargo test --test cli -- --nocapture`

Run: `.venv/bin/python -m pytest analysis/tests/test_end_to_end.py -q`

Expected: commands fail because orchestration files are absent.

- [ ] **Step 3: Implement orchestration**

`run.sh` must:

1. create a timestamped result directory;
2. copy the selected validated configuration;
3. run Rust oracles and stop on failure;
4. run the cost benchmark;
5. run the coarse Born simulation;
6. run preliminary phase analysis and write the refinement request;
7. resume Rust with the hash-checked request when it is bracketed;
8. run the small IID negative control;
9. invoke final Python analysis and renderers;
10. verify both report pairs;
11. finalize manifest runtime and hashes.

Use `set -euo pipefail`; do not synthesize missing artifacts after a failed
stage.

- [ ] **Step 4: Document scientific and operational boundaries**

The README must explain the model, equations, scan slices, class distinction,
RNG, runtime policy, status values, resume behavior, commands, output schema,
and why \(c_{\rm eff}\alpha\) may be the only publishable result.

- [ ] **Step 5: Run the complete pre-production suite**

Run: `make setup`

Run: `make test`

Run: `make run-test`

Expected: all Rust/Python tests pass; the tiny run status is not
`validation_failed`; generated reports pass structural verification.

- [ ] **Step 6: Commit**

```bash
git add tracks/qmc/solutions/卧龙凤雏/learning-mit tracks/qmc/solutions/卧龙凤雏/README.md
git commit -m "feat: complete reproducible learning MIT workflow"
```

---

### Task 12: Execute the bounded production study and freeze results

**Files:**
- Create at runtime: `tracks/qmc/results/learning-mit-<timestamp>/`
- Modify after runtime: `tracks/qmc/solutions/卧龙凤雏/learning-mit/README.md`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/FROZEN_RESULT`
- Create: `output/html/learning-induced-mit-report.html`
- Create: `output/html/learning-induced-mit-report-zh.html`
- Create: `output/pdf/learning-induced-mit-report.pdf`
- Create: `output/pdf/learning-induced-mit-report-zh.pdf`

**Interfaces:**
- Consumes: green Task 11 pipeline and `configs/production.toml`
- Produces: one frozen, hashed, bilingual research result

- [ ] **Step 1: Record preflight state**

Run:

```bash
git status --short
git rev-parse HEAD
make test
```

Expected: clean worktree and complete green suite.

- [ ] **Step 2: Run the production pipeline**

Run: `make run-production`

Expected: normal target near 60 minutes; hard termination and finalization no
later than 90 minutes. Send user progress updates before long-running phases
and at least once per 60 seconds while actively waiting.

- [ ] **Step 3: Inspect the runtime decision**

Read `manifest.json` and confirm any reserve use has one of the allowed
reasons. If the run ends without a DIII bracket, do not rerun the same grid;
accept `xy_reproduced_diii_inconclusive` and preserve diagnostics.

- [ ] **Step 4: Re-run analysis from frozen raw data**

Run the analysis command twice without rerunning Rust. Compute SHA-256 of
processed JSON, bilingual HTML, and PDFs after each run.

Expected: byte-identical deterministic artifacts.

- [ ] **Step 5: Freeze and audit**

Write the selected result path and summary SHA-256 to `FROZEN_RESULT`.
Update the README with actual widths, angles, elapsed time, state, estimates,
intervals, and explicit exploratory wording.
Copy the four verified standalone reports to the stable `output/html` and
`output/pdf` paths listed above without altering their bytes.

- [ ] **Step 6: Commit**

```bash
git add tracks/qmc/solutions/卧龙凤雏/learning-mit output/html/learning-induced-mit-report.html output/html/learning-induced-mit-report-zh.html output/pdf/learning-induced-mit-report.pdf output/pdf/learning-induced-mit-report-zh.pdf
git commit -m "results: freeze exploratory learning MIT study"
```

The timestamped raw result is intentionally ignored, matching the existing
QMC result policy. Preserve it through branch integration by copying the exact
hashed directory into the main repository's `tracks/qmc/results/` before an
owned worktree is removed.

---

### Task 13: Add the exploratory chapter to the integrated reports

**Files:**
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/sources.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/report_model.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/report_model_zh.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/build_report.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_sources.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_report_model.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_report_model_zh.py`
- Modify at build time: `output/html/three-model-central-charge-report.html`
- Modify at build time: `output/pdf/three-model-central-charge-report.pdf`
- Modify at build time: `output/html/three-model-central-charge-report-zh.html`
- Modify at build time: `output/pdf/three-model-central-charge-report-zh.pdf`

**Interfaces:**
- Consumes: only the frozen `summary.json` selected by `FROZEN_RESULT`
- Produces: a clearly separated “Open research”/“开放研究” chapter

- [ ] **Step 1: Write failing source and claim-level tests**

Require loading by frozen hash, reject unfrozen result directories, and assert
that every DIII number is tagged `exploratory`. Require the three benchmark
cards to remain unchanged.

- [ ] **Step 2: Run tests and verify the red state**

Run: `.venv/bin/python -m pytest tests/test_sources.py tests/test_report_model.py tests/test_report_model_zh.py -q`

Expected: tests fail because no learning-MIT source adapter exists.

- [ ] **Step 3: Implement the source adapter and chapter**

Load only summary-level facts and selected bilingual figures. Present the
\(XY\) reproduction gate, DIII result state, Casimir amplitude, alpha status,
runtime limit, and unresolved questions. Do not alter the established
clean/Nishimori/weak-self-dual result table.

- [ ] **Step 4: Rebuild and verify both integrated reports**

Run: `make build-all`

Run: `make test`

Expected: English and Chinese artifacts coexist, all old benchmark assertions
pass, and the new chapter has identical numeric facts in both languages.

- [ ] **Step 5: Commit**

```bash
git add tracks/qmc/solutions/卧龙凤雏/integrated-report output/html output/pdf
git commit -m "docs: add exploratory learning MIT evidence to reports"
```

---

### Task 14: Final scientific, visual, and reproducibility verification

**Files:**
- Modify only if verification finds a defect: files introduced by Tasks 1–13

**Interfaces:**
- Consumes: merged implementation and frozen artifacts
- Produces: evidence required for completion

- [ ] **Step 1: Run all relevant test suites**

Run:

```bash
make -C tracks/qmc/solutions/卧龙凤雏/learning-mit test
make -C tracks/qmc/solutions/卧龙凤雏/integrated-report test
```

Expected: zero failures.

- [ ] **Step 2: Verify frozen hashes and deterministic replay**

Run analysis-only replay and compare every stable artifact hash with the
manifest. Confirm fixed-seed tiny Rust runs are byte-identical.

- [ ] **Step 3: Render and inspect PDFs**

Render every page of the two standalone PDFs and two updated integrated PDFs
to PNG. Inspect title pages, dense equation/table pages, all plot pages, and
final pages for clipping, missing CJK glyphs, overlap, and unreadable labels.

- [ ] **Step 4: Inspect HTML**

Use the in-app browser when available. Otherwise use a local rendering
fallback plus static audit. Check desktop and narrow layouts, navigation,
embedded images, offline behavior, Chinese localization, and horizontal table
scrolling.

- [ ] **Step 5: Audit scientific claims**

Confirm:

- reported \(XY\) bracket matches the frozen analysis;
- DIII phase endpoints bracket the candidate;
- no result exceeds its gate status;
- \(c_{\rm eff}\) is absent when alpha fails;
- IID data are labeled nonphysical;
- runtime and actual widths/angles match the manifest;
- English and Chinese numbers are identical;
- old benchmark estimates remain unchanged.

- [ ] **Step 6: Run final repository checks**

Run:

```bash
git diff --check
git status --short
git log -15 --oneline
```

Expected: no whitespace errors, no unintended files, and only planned commits.

- [ ] **Step 7: Request review and finish the branch**

Invoke `superpowers:requesting-code-review`, address findings with
`superpowers:receiving-code-review`, rerun verification, then invoke
`superpowers:finishing-a-development-branch` and present the integration
options. For a local merge, copy the ignored frozen result directory to the
main repository before worktree cleanup and verify its `summary.json` hash
against `FROZEN_RESULT`.
