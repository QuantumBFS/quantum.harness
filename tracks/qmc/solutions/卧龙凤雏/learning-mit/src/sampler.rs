//! Stream-level trajectory estimation and block observables.

use crate::angles::GateCouplings;
use crate::circuit::{BoundarySector, GenericCircuit, SamplingMode};
use crate::config::RunConfig;
use crate::gaussian::MajoranaState;
use crate::rng::{derive_seed, make_rng};
use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct EntropyPoint {
    pub interval_sites: usize,
    pub entropy: f64,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct CorrelationPoint {
    pub distance: usize,
    pub connected_parity: f64,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
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

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct StreamEstimate {
    pub stage_index: usize,
    pub angle_index: usize,
    pub width: usize,
    pub stream: usize,
    pub seed: u64,
    pub mode: SamplingMode,
    pub is_physical: bool,
    pub blocks: Vec<BlockEstimate>,
}

pub fn estimate_stream(
    config: &RunConfig,
    stage_index: usize,
    angle_index: usize,
    width: usize,
    stream: usize,
    mode: SamplingMode,
) -> Result<StreamEstimate> {
    config.validate()?;
    let stage = config
        .stages
        .get(stage_index)
        .ok_or_else(|| anyhow::anyhow!("stage index is outside the configuration"))?;
    let &phi_pi = stage
        .phi_pi
        .get(angle_index)
        .ok_or_else(|| anyhow::anyhow!("angle index is outside the stage"))?;
    if !stage.widths.contains(&width) {
        bail!("requested width is absent from the stage");
    }
    if stream >= stage.streams {
        bail!("requested stream is absent from the stage");
    }

    let couplings = GateCouplings::from_pi_units(stage.theta_pi, phi_pi)?;
    let circuit = GenericCircuit::new(width, couplings, BoundarySector::vacuum())?;
    let seed = derive_seed(
        config.base_seed,
        stage_index as u64,
        angle_index,
        width,
        stream,
        0x424f_524e,
    );
    let mut rng = make_rng(seed);
    let mut state = MajoranaState::paired_vacuum(width)?;

    let burn_in_periods = stage.burn_in_layers_per_width * width;
    for period in 0..burn_in_periods {
        let sample = circuit
            .sample_period(&mut state, &mut rng, mode)
            .with_context(|| format!("burn-in period {period} failed"))?;
        enforce_invariants(config, &sample.invariant_errors, period)?;
    }

    let measurement_periods = stage.measurement_layers_per_width * width;
    let block_periods = stage.block_layers_per_width * width;
    let block_count = measurement_periods / block_periods;
    let mut blocks = Vec::with_capacity(block_count);

    for block_index in 0..block_count {
        let mut entropy_sum = 0.0;
        let mut min_probability = 1.0_f64;
        let mut max_antisymmetry_error = 0.0_f64;
        let mut max_purity_error = 0.0_f64;
        for period_in_block in 0..block_periods {
            let sample = circuit
                .sample_period(&mut state, &mut rng, mode)
                .with_context(|| {
                    format!("measurement block {block_index} period {period_in_block} failed")
                })?;
            enforce_invariants(config, &sample.invariant_errors, period_in_block)?;
            entropy_sum += sample.conditional_entropy;
            min_probability = min_probability.min(sample.min_probability);
            max_antisymmetry_error =
                max_antisymmetry_error.max(sample.invariant_errors.antisymmetry);
            max_purity_error = max_purity_error.max(sample.invariant_errors.purity);
        }

        blocks.push(BlockEstimate {
            block_index,
            gamma: entropy_rate_per_measurement_row(entropy_sum, block_periods)?,
            half_chain_entropy: state.interval_entropy(0, width / 2)?,
            entropy_arc: entropy_arc(&state)?,
            spatial_correlations: spatial_correlations(&state)?,
            min_probability,
            max_antisymmetry_error,
            max_purity_error,
        });
    }

    Ok(StreamEstimate {
        stage_index,
        angle_index,
        width,
        stream,
        seed,
        mode,
        is_physical: mode.is_physical(),
        blocks,
    })
}

pub fn entropy_rate_per_measurement_row(total_entropy: f64, periods: usize) -> Result<f64> {
    if !total_entropy.is_finite() || total_entropy < 0.0 {
        bail!("total conditional entropy must be finite and non-negative");
    }
    if periods == 0 {
        bail!("entropy rate requires at least one complete circuit period");
    }
    Ok(total_entropy / (2 * periods) as f64)
}

fn entropy_arc(state: &MajoranaState) -> Result<Vec<EntropyPoint>> {
    (1..state.width())
        .map(|sites| {
            Ok(EntropyPoint {
                interval_sites: sites,
                entropy: state.interval_entropy(0, sites)?,
            })
        })
        .collect()
}

fn spatial_correlations(state: &MajoranaState) -> Result<Vec<CorrelationPoint>> {
    (1..=state.width() / 2)
        .map(|distance| {
            let sum = (0..state.width())
                .map(|left| {
                    state.connected_parity_correlation(left, (left + distance) % state.width())
                })
                .collect::<Result<Vec<_>>>()?
                .into_iter()
                .sum::<f64>();
            Ok(CorrelationPoint {
                distance,
                connected_parity: sum / state.width() as f64,
            })
        })
        .collect()
}

fn enforce_invariants(
    config: &RunConfig,
    errors: &crate::gaussian::InvariantErrors,
    completed_period: usize,
) -> Result<()> {
    let maximum = errors.antisymmetry.max(errors.purity);
    if !maximum.is_finite() || maximum > config.invariant_tolerance {
        bail!(
            "Gaussian invariant error {maximum:.6e} exceeds tolerance after period {completed_period}"
        );
    }
    Ok(())
}
