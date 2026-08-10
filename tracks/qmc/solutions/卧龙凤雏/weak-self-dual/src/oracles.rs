use crate::covariance::{CovarianceState, Measurement};
use crate::network::{BoundarySector, SelfDualNetwork};
use anyhow::{bail, Result};
use nalgebra::{DMatrix, DVector};
use num_complex::Complex64;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TrajectoryProbability {
    pub outcomes: Vec<i8>,
    pub probability: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct OracleComparison {
    pub width: usize,
    pub depth: usize,
    pub trajectories: usize,
    pub max_probability_error: f64,
    pub max_parity_error: f64,
    pub max_covariance_error: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct GaugeOracleComparison {
    pub width: usize,
    pub depth: usize,
    pub max_probability_error: f64,
    pub max_observable_error: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CleanOracle {
    pub width: usize,
    pub layers: usize,
    pub total_surprise: f64,
    pub max_covariance_error: f64,
}

type DenseState = DVector<Complex64>;

pub fn enumerate_dense_trajectories(
    width: usize,
    depth: usize,
    beta: f64,
    sector: BoundarySector,
) -> Result<Vec<TrajectoryProbability>> {
    validate_dense_size(width, depth)?;
    let measurements = schedule(width, depth, beta, sector)?;
    let majoranas = majorana_matrices(width);
    let mut branches = vec![(Vec::new(), 1.0, dense_paired_vacuum(width))];
    for measurement in measurements {
        let observable = bilinear(&majoranas, measurement.a, measurement.b);
        let mut next = Vec::with_capacity(branches.len() * 2);
        for (outcomes, joint, state) in branches {
            for outcome in [-1, 1] {
                let (updated, probability) =
                    dense_apply(&state, &observable, measurement, outcome)?;
                let mut branch_outcomes = outcomes.clone();
                branch_outcomes.push(outcome);
                next.push((branch_outcomes, joint * probability, updated));
            }
        }
        branches = next;
    }
    Ok(branches
        .into_iter()
        .map(|(outcomes, probability, _)| TrajectoryProbability {
            outcomes,
            probability,
        })
        .collect())
}

pub fn compare_covariance_to_dense(
    width: usize,
    depth: usize,
    beta: f64,
) -> Result<OracleComparison> {
    validate_dense_size(width, depth)?;
    let network = SelfDualNetwork::vacuum(width, beta)?;
    let measurements = schedule_from_network(&network, depth);
    let majoranas = majorana_matrices(width);
    let trajectories = enumerate_dense_trajectories(width, depth, beta, BoundarySector::vacuum())?;
    let mut max_probability_error = 0.0_f64;
    let mut max_parity_error = 0.0_f64;
    let mut max_covariance_error = 0.0_f64;

    for trajectory in &trajectories {
        let mut dense = dense_paired_vacuum(width);
        let mut gaussian = CovarianceState::paired_vacuum(width)?;
        let mut gaussian_joint = 1.0;
        for (&outcome, &measurement) in trajectory.outcomes.iter().zip(&measurements) {
            let observable = bilinear(&majoranas, measurement.a, measurement.b);
            let dense_parity =
                measurement.observable_sign as f64 * dense_expectation(&dense, &observable);
            let gaussian_parity = gaussian.parity_expectation(
                measurement.a,
                measurement.b,
                measurement.observable_sign,
            )?;
            max_parity_error = max_parity_error.max((dense_parity - gaussian_parity).abs());
            let (updated, dense_probability) =
                dense_apply(&dense, &observable, measurement, outcome)?;
            let gaussian_probability = gaussian.outcome_probability(measurement, outcome)?;
            max_probability_error =
                max_probability_error.max((dense_probability - gaussian_probability).abs());
            gaussian_joint *= gaussian_probability;
            gaussian.apply_outcome(measurement, outcome)?;
            dense = updated;
        }
        max_probability_error =
            max_probability_error.max((trajectory.probability - gaussian_joint).abs());
        let dense_covariance = covariance_from_dense(&dense, &majoranas);
        max_covariance_error =
            max_covariance_error.max(max_matrix_difference(gaussian.matrix(), &dense_covariance));
    }
    Ok(OracleComparison {
        width,
        depth,
        trajectories: trajectories.len(),
        max_probability_error,
        max_parity_error,
        max_covariance_error,
    })
}

pub fn compare_gauge_equivalent_trajectories(
    width: usize,
    depth: usize,
    beta: f64,
) -> Result<GaugeOracleComparison> {
    validate_dense_size(width, depth)?;
    let network = SelfDualNetwork::vacuum(width, beta)?;
    let measurements = schedule_from_network(&network, depth);
    let trajectories = enumerate_dense_trajectories(width, depth, beta, BoundarySector::vacuum())?;
    let mut gauge = vec![1.0; 2 * width];
    gauge[0] = -1.0;
    gauge[1] = -1.0;
    let original_initial = CovarianceState::paired_vacuum(width)?;
    let gauged_initial = gauge_transform_matrix(original_initial.matrix(), &gauge);
    let mut max_probability_error = 0.0_f64;
    let mut max_observable_error = 0.0_f64;

    for trajectory in trajectories {
        let mut original = CovarianceState::paired_vacuum(width)?;
        let mut gauged = CovarianceState::from_matrix(width, gauged_initial.clone())?;
        for (&outcome, &measurement) in trajectory.outcomes.iter().zip(&measurements) {
            let gauged_measurement = Measurement {
                observable_sign: measurement.observable_sign
                    * (gauge[measurement.a] * gauge[measurement.b]) as i8,
                ..measurement
            };
            let original_probability = original.outcome_probability(measurement, outcome)?;
            let gauged_probability = gauged.outcome_probability(gauged_measurement, outcome)?;
            max_probability_error =
                max_probability_error.max((original_probability - gauged_probability).abs());
            original.apply_outcome(measurement, outcome)?;
            gauged.apply_outcome(gauged_measurement, outcome)?;
            let transformed = gauge_transform_matrix(original.matrix(), &gauge);
            max_observable_error =
                max_observable_error.max(max_matrix_difference(&transformed, gauged.matrix()));
        }
    }
    Ok(GaugeOracleComparison {
        width,
        depth,
        max_probability_error,
        max_observable_error,
    })
}

pub fn clean_positive_trajectory(width: usize, layers: usize, beta: f64) -> Result<CleanOracle> {
    validate_dense_size(width, layers)?;
    let network = SelfDualNetwork::vacuum(width, beta)?;
    let measurements = schedule_from_network(&network, layers);
    let majoranas = majorana_matrices(width);
    let mut dense = dense_paired_vacuum(width);
    let mut gaussian = CovarianceState::paired_vacuum(width)?;
    let mut total_surprise = 0.0;
    for measurement in measurements {
        let observable = bilinear(&majoranas, measurement.a, measurement.b);
        let (updated, _) = dense_apply(&dense, &observable, measurement, 1)?;
        total_surprise += gaussian.apply_outcome(measurement, 1)?.surprise;
        dense = updated;
    }
    let dense_covariance = covariance_from_dense(&dense, &majoranas);
    Ok(CleanOracle {
        width,
        layers,
        total_surprise,
        max_covariance_error: max_matrix_difference(gaussian.matrix(), &dense_covariance),
    })
}

fn validate_dense_size(width: usize, depth: usize) -> Result<()> {
    if !(1..=3).contains(&width) {
        bail!("dense oracle width must be between 1 and 3");
    }
    if depth == 0 {
        bail!("dense oracle depth must be positive");
    }
    if 2 * width * depth > 12 {
        bail!("dense enumeration is limited to twelve measurements");
    }
    Ok(())
}

fn schedule(
    width: usize,
    depth: usize,
    beta: f64,
    sector: BoundarySector,
) -> Result<Vec<Measurement>> {
    let network = SelfDualNetwork::new(width, beta, sector)?;
    Ok(schedule_from_network(&network, depth))
}

fn schedule_from_network(network: &SelfDualNetwork, depth: usize) -> Vec<Measurement> {
    let mut measurements = Vec::with_capacity(2 * network.width() * depth);
    for _ in 0..depth {
        measurements.extend_from_slice(network.onsite_measurements());
        measurements.extend_from_slice(network.bond_measurements());
    }
    measurements
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

fn dense_apply(
    state: &DenseState,
    observable: &DMatrix<Complex64>,
    measurement: Measurement,
    outcome: i8,
) -> Result<(DenseState, f64)> {
    let half = measurement.beta / 2.0;
    let scale = (2.0 * measurement.beta.cosh()).sqrt();
    let coefficient = outcome as f64 * measurement.observable_sign as f64 * half.sinh();
    let mut next = state * Complex64::new(half.cosh(), 0.0)
        + (observable * state) * Complex64::new(coefficient, 0.0);
    next /= Complex64::new(scale, 0.0);
    let probability = next.norm_squared();
    if !probability.is_finite() || probability <= 0.0 {
        bail!("dense oracle produced invalid probability {probability}");
    }
    next /= Complex64::new(probability.sqrt(), 0.0);
    Ok((next, probability))
}

fn dense_expectation(state: &DenseState, observable: &DMatrix<Complex64>) -> f64 {
    state.dotc(&(observable * state)).re
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

fn gauge_transform_matrix(matrix: &DMatrix<f64>, gauge: &[f64]) -> DMatrix<f64> {
    DMatrix::from_fn(matrix.nrows(), matrix.ncols(), |row, column| {
        gauge[row] * matrix[(row, column)] * gauge[column]
    })
}

fn max_matrix_difference(left: &DMatrix<f64>, right: &DMatrix<f64>) -> f64 {
    (left - right)
        .iter()
        .fold(0.0_f64, |largest, value| largest.max(value.abs()))
}
