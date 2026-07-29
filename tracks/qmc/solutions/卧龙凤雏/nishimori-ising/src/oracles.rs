use crate::disorder::{sample_row, DisorderRow};
use crate::lyapunov::ProductState;
use crate::rng::make_rng;
use anyhow::{bail, Result};
use clean_ising::config::ExactConfig;
use clean_ising::transfer::dominant_eigenpair;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CleanOraclePoint {
    pub width: usize,
    pub observed_log_lambda: f64,
    pub exact_log_lambda: f64,
    pub absolute_error: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EnergyIdentityResult {
    pub width: usize,
    pub derivative: f64,
    pub expected: f64,
    pub absolute_error: f64,
    pub delta_k: f64,
    pub rows: usize,
}

pub fn clean_transfer_oracle(
    widths: &[usize],
    k: f64,
    burn_in_rows: usize,
    measurement_rows: usize,
) -> Result<Vec<CleanOraclePoint>> {
    if measurement_rows == 0 {
        bail!("clean oracle measurement_rows must be positive");
    }
    let mut points = Vec::with_capacity(widths.len());
    for &width in widths {
        let row = DisorderRow {
            horizontal: vec![1; width],
            vertical: vec![1; width],
        };
        let mut state = ProductState::new(width)?;
        for _ in 0..burn_in_rows {
            state.advance(k, &row)?;
        }
        let mut log_norm = 0.0;
        for _ in 0..measurement_rows {
            log_norm += state.advance(k, &row)?;
        }
        let observed_log_lambda = log_norm / measurement_rows as f64;
        let exact_log_lambda = dominant_eigenpair(width, k, &ExactConfig::strict_for_test())?
            .lambda
            .ln();
        points.push(CleanOraclePoint {
            width,
            observed_log_lambda,
            exact_log_lambda,
            absolute_error: (observed_log_lambda - exact_log_lambda).abs(),
        });
    }
    Ok(points)
}

#[allow(clippy::too_many_arguments)]
pub fn nishimori_energy_identity(
    width: usize,
    antiferromagnetic_probability: f64,
    k: f64,
    delta_k: f64,
    seed: u64,
    burn_in_rows: usize,
    measurement_rows: usize,
) -> Result<EnergyIdentityResult> {
    if !delta_k.is_finite() || delta_k <= 0.0 || delta_k >= k {
        bail!("identity delta_k must be positive, finite, and smaller than K");
    }
    if measurement_rows == 0 {
        bail!("identity measurement_rows must be positive");
    }

    let mut rng = make_rng(seed);
    let mut plus = ProductState::new(width)?;
    let mut minus = ProductState::new(width)?;
    for _ in 0..burn_in_rows {
        let row = sample_row(width, antiferromagnetic_probability, &mut rng)?;
        plus.advance(k + delta_k, &row)?;
        minus.advance(k - delta_k, &row)?;
    }

    let mut plus_sum = 0.0;
    let mut minus_sum = 0.0;
    for _ in 0..measurement_rows {
        let row = sample_row(width, antiferromagnetic_probability, &mut rng)?;
        plus_sum += plus.advance(k + delta_k, &row)?;
        minus_sum += minus.advance(k - delta_k, &row)?;
    }
    let denominator = 2.0 * delta_k * measurement_rows as f64 * width as f64;
    let derivative = (plus_sum - minus_sum) / denominator;
    let expected = 2.0 * k.tanh();
    Ok(EnergyIdentityResult {
        width,
        derivative,
        expected,
        absolute_error: (derivative - expected).abs(),
        delta_k,
        rows: measurement_rows,
    })
}
