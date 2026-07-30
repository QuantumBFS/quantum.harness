//! Independent dense-state and limiting-case validation oracles.

use crate::angles::GateCouplings;
use crate::circuit::{
    apply_forced_gate, BoundarySector, ConditionalGate, GenericCircuit, SamplingMode,
};
use crate::config::RunConfig;
use crate::gaussian::MajoranaState;
use crate::rng::{derive_seed, make_rng};
use crate::schema::SCHEMA_VERSION;
use anyhow::{bail, Result};
use nalgebra::{DMatrix, DVector};
use num_complex::Complex64;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};

type DenseState = DVector<Complex64>;

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct DenseComparison {
    pub width: usize,
    pub periods: usize,
    pub trajectories: usize,
    pub max_joint_probability_error: f64,
    pub max_covariance_error: f64,
    pub max_entropy_error: f64,
    pub total_probability: f64,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct LimitOracle {
    pub width: usize,
    pub periods: usize,
    pub max_probability_error: f64,
    pub max_covariance_error: f64,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct PhysicalLimitOracle {
    pub y_swap_residual: f64,
    pub y_volume_law_fractions: Vec<f64>,
    pub y_min_volume_law_fraction: f64,
    pub x_entropy_densities: Vec<f64>,
    pub x_entropy_density_decreases: bool,
    pub passed: bool,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct NegativeControlOracle {
    pub born_mean: f64,
    pub iid_mean: f64,
    pub difference: f64,
    pub z_score: f64,
    pub required_z_score: f64,
    pub streams_per_mode: usize,
    pub passed: bool,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct OracleArtifact {
    pub schema_version: u32,
    pub dense: DenseComparison,
    pub physical_limits: PhysicalLimitOracle,
    pub negative_control: NegativeControlOracle,
    pub xy_block_residual: f64,
    pub generic_block_residual: f64,
    pub required_pass: bool,
}

pub fn compare_dense_to_gaussian(
    width: usize,
    periods: usize,
    couplings: GateCouplings,
    sector: BoundarySector,
) -> Result<DenseComparison> {
    if width == 0 || width > 4 || periods == 0 {
        bail!("dense comparison requires 1 <= width <= 4 and positive periods");
    }
    let circuit = GenericCircuit::new(width, couplings, sector)?;
    let schedule = (0..periods)
        .flat_map(|_| {
            circuit
                .onsite_gates()
                .iter()
                .chain(circuit.bond_gates())
                .copied()
        })
        .collect::<Vec<_>>();
    if schedule.len() > 16 {
        bail!("dense trajectory enumeration is limited to sixteen gates");
    }

    let majoranas = majorana_matrices(width);
    let trajectory_count = 1_usize << schedule.len();
    let mut max_joint_probability_error = 0.0_f64;
    let mut max_covariance_error = 0.0_f64;
    let mut max_entropy_error = 0.0_f64;
    let mut total_probability = 0.0;

    for mask in 0..trajectory_count {
        let mut dense = dense_paired_vacuum(width);
        let mut gaussian = MajoranaState::paired_vacuum(width)?;
        let mut dense_joint = 1.0;
        let mut gaussian_joint = 1.0;

        for (gate_index, &gate) in schedule.iter().enumerate() {
            let outcome = if mask & (1 << gate_index) == 0 { -1 } else { 1 };
            let (updated, probability) = dense_apply_forced(&dense, &majoranas, gate, outcome)?;
            dense = updated;
            dense_joint *= probability;
            gaussian_joint *= apply_forced_gate(&mut gaussian, gate, outcome)?.probability;
        }

        total_probability += dense_joint;
        max_joint_probability_error =
            max_joint_probability_error.max((dense_joint - gaussian_joint).abs());
        let dense_covariance = covariance_from_dense(&dense, &majoranas);
        max_covariance_error =
            max_covariance_error.max((&dense_covariance - gaussian.matrix()).amax());
        let dense_entropy = dense_interval_entropy(&dense, width, width / 2)?;
        let gaussian_entropy = gaussian.interval_entropy(0, width / 2)?;
        max_entropy_error = max_entropy_error.max((dense_entropy - gaussian_entropy).abs());
    }

    Ok(DenseComparison {
        width,
        periods,
        trajectories: trajectory_count,
        max_joint_probability_error,
        max_covariance_error,
        max_entropy_error,
        total_probability,
    })
}

/// Residual coupling the two class-D blocks; it vanishes exactly on the XY line.
pub fn class_d_block_residual(couplings: GateCouplings) -> Result<f64> {
    if !couplings.j.is_finite() {
        bail!("class-D residual requires finite couplings");
    }
    Ok(couplings.j.abs())
}

pub fn physical_limit_oracle() -> Result<PhysicalLimitOracle> {
    let y_couplings = GateCouplings::from_pi_units(0.5, 0.5)?;
    let y_fixture = GenericCircuit::new(4, y_couplings, BoundarySector::vacuum())?;
    let y_swap_residual = y_fixture
        .onsite_gates()
        .iter()
        .chain(y_fixture.bond_gates())
        .flat_map(|gate| {
            [
                gate.measurement.strength.abs(),
                (gate.positive_rotation.abs() - std::f64::consts::FRAC_PI_2).abs(),
                (gate.negative_rotation.abs() - std::f64::consts::FRAC_PI_2).abs(),
            ]
        })
        .fold(0.0_f64, f64::max);

    let mut y_volume_law_fractions = Vec::new();
    for width in [4, 8, 12] {
        let circuit = GenericCircuit::new(width, y_couplings, BoundarySector::vacuum())?;
        let mut state = MajoranaState::paired_vacuum(width)?;
        let maximum = (width / 2) as f64 * std::f64::consts::LN_2;
        let mut largest_entropy = 0.0_f64;
        for _ in 0..width {
            apply_positive_period(&circuit, &mut state)?;
            largest_entropy = largest_entropy.max(state.interval_entropy(0, width / 2)?);
        }
        y_volume_law_fractions.push(largest_entropy / maximum);
    }
    let y_min_volume_law_fraction = y_volume_law_fractions
        .iter()
        .copied()
        .fold(f64::INFINITY, f64::min);

    let x_couplings = GateCouplings::from_pi_units(0.02, 0.0)?;
    let mut x_entropy_densities = Vec::new();
    for width in [4, 6, 8] {
        let circuit = GenericCircuit::new(width, x_couplings, BoundarySector::vacuum())?;
        let mut state = MajoranaState::paired_vacuum(width)?;
        for _ in 0..4 {
            apply_positive_period(&circuit, &mut state)?;
        }
        x_entropy_densities.push(state.interval_entropy(0, width / 2)? / (width / 2) as f64);
    }
    let x_entropy_density_decreases = x_entropy_densities
        .windows(2)
        .all(|pair| pair[1] <= pair[0] + 1.0e-12)
        && x_entropy_densities.last().unwrap() < x_entropy_densities.first().unwrap();
    let passed = y_swap_residual < 1.0e-12
        && y_min_volume_law_fraction > 0.99
        && x_entropy_density_decreases;

    Ok(PhysicalLimitOracle {
        y_swap_residual,
        y_volume_law_fractions,
        y_min_volume_law_fraction,
        x_entropy_densities,
        x_entropy_density_decreases,
        passed,
    })
}

pub fn negative_control_oracle(base_seed: u64) -> Result<NegativeControlOracle> {
    const STREAMS: usize = 32;
    let couplings = GateCouplings::from_pi_units(0.45, 0.18)?;
    let circuit = GenericCircuit::new(4, couplings, BoundarySector::vacuum())?;
    let born = diagnostic_stream_means(&circuit, base_seed, SamplingMode::Born, STREAMS)?;
    let iid = diagnostic_stream_means(&circuit, base_seed, SamplingMode::IidDiagnostic, STREAMS)?;
    let born_mean = mean(&born);
    let iid_mean = mean(&iid);
    let difference = (born_mean - iid_mean).abs();
    let standard_error =
        (sample_variance(&born) / STREAMS as f64 + sample_variance(&iid) / STREAMS as f64).sqrt();
    let z_score = if standard_error > 0.0 {
        difference / standard_error
    } else if difference > 0.0 {
        f64::INFINITY
    } else {
        0.0
    };
    let required_z_score = 3.0;
    Ok(NegativeControlOracle {
        born_mean,
        iid_mean,
        difference,
        z_score,
        required_z_score,
        streams_per_mode: STREAMS,
        passed: z_score > required_z_score,
    })
}

pub fn run_oracles(config: &RunConfig) -> Result<OracleArtifact> {
    config.validate()?;
    let dense = compare_dense_to_gaussian(
        2,
        2,
        GateCouplings::from_pi_units(0.45, 0.18)?,
        BoundarySector::vacuum(),
    )?;
    let physical_limits = physical_limit_oracle()?;
    let negative_control = negative_control_oracle(config.base_seed)?;
    let xy_block_residual = class_d_block_residual(GateCouplings::from_pi_units(0.5, 0.25)?)?;
    let generic_block_residual = class_d_block_residual(GateCouplings::from_pi_units(0.45, 0.18)?)?;
    let required_pass = dense.max_joint_probability_error < 1.0e-11
        && dense.max_covariance_error < 1.0e-10
        && dense.max_entropy_error < 1.0e-10
        && (dense.total_probability - 1.0).abs() < 1.0e-12
        && physical_limits.passed
        && negative_control.passed
        && xy_block_residual < 1.0e-12
        && generic_block_residual > 1.0e-3;
    Ok(OracleArtifact {
        schema_version: SCHEMA_VERSION,
        dense,
        physical_limits,
        negative_control,
        xy_block_residual,
        generic_block_residual,
        required_pass,
    })
}

pub fn write_oracle_artifact(config: &RunConfig, run_dir: &Path) -> Result<PathBuf> {
    let artifact = run_oracles(config)?;
    let raw_dir = run_dir.join("raw");
    fs::create_dir_all(&raw_dir)?;
    let destination = raw_dir.join("oracles.json");
    let temporary = raw_dir.join(".oracles.json.tmp");
    let bytes = serde_json::to_vec_pretty(&artifact)?;
    fs::write(&temporary, bytes)?;
    fs::rename(&temporary, &destination)?;
    if !artifact.required_pass {
        bail!("one or more required scientific oracles failed");
    }
    Ok(destination)
}

fn apply_positive_period(circuit: &GenericCircuit, state: &mut MajoranaState) -> Result<()> {
    for &gate in circuit.onsite_gates().iter().chain(circuit.bond_gates()) {
        apply_forced_gate(state, gate, 1)?;
    }
    Ok(())
}

fn diagnostic_stream_means(
    circuit: &GenericCircuit,
    base_seed: u64,
    mode: SamplingMode,
    streams: usize,
) -> Result<Vec<f64>> {
    let purpose = if mode.is_physical() {
        0x424f_524e
    } else {
        0x4949_4400
    };
    (0..streams)
        .map(|stream| {
            let seed = derive_seed(base_seed, 0, 0, circuit.width(), stream, purpose);
            let mut rng = make_rng(seed);
            let mut state = MajoranaState::paired_vacuum(circuit.width())?;
            for _ in 0..4 {
                circuit.sample_period(&mut state, &mut rng, mode)?;
            }
            let mut total = 0.0;
            for _ in 0..24 {
                total += circuit
                    .sample_period(&mut state, &mut rng, mode)?
                    .conditional_entropy
                    / 2.0;
            }
            Ok(total / 24.0)
        })
        .collect()
}

fn mean(values: &[f64]) -> f64 {
    values.iter().sum::<f64>() / values.len() as f64
}

fn sample_variance(values: &[f64]) -> f64 {
    let average = mean(values);
    values
        .iter()
        .map(|value| (value - average).powi(2))
        .sum::<f64>()
        / (values.len() - 1) as f64
}

fn dense_apply_forced(
    state: &DenseState,
    majoranas: &[DMatrix<Complex64>],
    gate: ConditionalGate,
    outcome: i8,
) -> Result<(DenseState, f64)> {
    if !matches!(outcome, -1 | 1) {
        bail!("dense forced outcome must be +1 or -1");
    }
    let observable = bilinear(majoranas, gate.measurement.a, gate.measurement.b);
    let rotation = gate.rotation_for(outcome)?;
    let parameter = Complex64::new(
        outcome as f64 * gate.measurement.observable_sign as f64 * gate.measurement.strength,
        rotation,
    );
    let half = parameter * 0.5;
    let scale = (2.0 * gate.measurement.strength.cosh()).sqrt();
    let mut next = state * half.cosh() + (&observable * state) * half.sinh();
    next /= Complex64::new(scale, 0.0);
    let probability = next.norm_squared();
    if !probability.is_finite() || probability <= 0.0 {
        bail!("dense oracle produced invalid probability {probability}");
    }
    next /= Complex64::new(probability.sqrt(), 0.0);
    Ok((next, probability))
}

fn dense_paired_vacuum(width: usize) -> DenseState {
    let dimension = 1 << width;
    let mut state = DVector::zeros(dimension);
    state[dimension - 1] = Complex64::new(1.0, 0.0);
    state
}

fn majorana_matrices(width: usize) -> Vec<DMatrix<Complex64>> {
    let dimension = 1 << width;
    let mut matrices = Vec::with_capacity(2 * width);
    for site in 0..width {
        for flavor in 0..2 {
            let mut matrix = DMatrix::zeros(dimension, dimension);
            for basis in 0..dimension {
                let flipped = basis ^ (1 << site);
                let lower_parity = (basis & ((1 << site) - 1)).count_ones() % 2;
                let jordan_wigner = if lower_parity == 0 { 1.0 } else { -1.0 };
                let phase = if flavor == 0 {
                    Complex64::new(jordan_wigner, 0.0)
                } else if basis & (1 << site) == 0 {
                    Complex64::new(0.0, jordan_wigner)
                } else {
                    Complex64::new(0.0, -jordan_wigner)
                };
                matrix[(flipped, basis)] = phase;
            }
            matrices.push(matrix);
        }
    }
    matrices
}

fn bilinear(majoranas: &[DMatrix<Complex64>], a: usize, b: usize) -> DMatrix<Complex64> {
    (&majoranas[a] * &majoranas[b]) * Complex64::i()
}

fn covariance_from_dense(state: &DenseState, majoranas: &[DMatrix<Complex64>]) -> DMatrix<f64> {
    let dimension = majoranas.len();
    let mut covariance = DMatrix::zeros(dimension, dimension);
    for a in 0..dimension {
        for b in (a + 1)..dimension {
            let value = dense_expectation(state, &bilinear(majoranas, a, b));
            covariance[(a, b)] = value;
            covariance[(b, a)] = -value;
        }
    }
    covariance
}

fn dense_expectation(state: &DenseState, observable: &DMatrix<Complex64>) -> f64 {
    state.dotc(&(observable * state)).re
}

fn dense_interval_entropy(state: &DenseState, width: usize, sites: usize) -> Result<f64> {
    if sites == 0 || sites > width {
        bail!("dense entropy interval is invalid");
    }
    let subsystem_dimension = 1 << sites;
    let environment_dimension = 1 << (width - sites);
    let mut reduced = DMatrix::<Complex64>::zeros(subsystem_dimension, subsystem_dimension);
    for environment in 0..environment_dimension {
        for left in 0..subsystem_dimension {
            let left_index = left | (environment << sites);
            for right in 0..subsystem_dimension {
                let right_index = right | (environment << sites);
                reduced[(left, right)] += state[left_index] * state[right_index].conj();
            }
        }
    }
    let singular_values = reduced.svd(false, false).singular_values;
    Ok(singular_values
        .iter()
        .filter(|&&value| value > 0.0)
        .map(|&value| -value * value.ln())
        .sum())
}
