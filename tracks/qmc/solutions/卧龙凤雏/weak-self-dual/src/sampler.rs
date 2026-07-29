use crate::config::RunConfig;
use crate::covariance::{CovarianceState, Measurement};
use crate::network::{LayerOutcomes, SelfDualNetwork};
use crate::rng::{derive_seed, make_rng};
use anyhow::{bail, Context, Result};
use rand_xoshiro::rand_core::Rng;
use rand_xoshiro::Xoshiro256PlusPlus;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct BlockEstimate {
    pub block_index: usize,
    pub gamma: f64,
    pub electric_count: usize,
    pub magnetic_count: usize,
    pub faces_per_species: usize,
    pub min_probability: f64,
    pub max_invariant_error: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StreamEstimate {
    pub width: usize,
    pub stream: usize,
    pub seed: u64,
    pub burn_in_layers: usize,
    pub measurement_layers: usize,
    pub block_layers: usize,
    pub sector_wilson_loop: i8,
    pub sector_fermion_parity: i8,
    pub blocks: Vec<BlockEstimate>,
}

pub fn estimate_stream(config: &RunConfig, width: usize, stream: usize) -> Result<StreamEstimate> {
    config.validate()?;
    if !config.widths.contains(&width) {
        bail!("width {width} is not present in the run configuration");
    }
    if stream >= config.sampling.streams_per_width {
        bail!(
            "stream {stream} is outside configured range 0..{}",
            config.sampling.streams_per_width
        );
    }
    let burn_in_layers = config.sampling.burn_in_layers_per_width * width;
    let measurement_layers = config.sampling.measurement_layers_per_width * width;
    let block_layers = config.sampling.block_layers_per_width * width;
    let seed = derive_seed(config.base_seed, width, stream, 0);
    let mut rng = make_rng(seed);
    let network = SelfDualNetwork::vacuum(width, config.beta)?;
    let mut state = CovarianceState::paired_vacuum(width)?;
    let mut previous = None;
    let mut absolute_layer = 0;

    for _ in 0..burn_in_layers {
        let sampled = sample_layer(
            &mut state,
            &network,
            &mut rng,
            width,
            stream,
            absolute_layer,
        )?;
        previous = Some(sampled.outcomes);
        absolute_layer += 1;
        stabilize_and_check(&mut state, config, width, stream, absolute_layer)?;
    }

    let block_count = measurement_layers / block_layers;
    let mut blocks = Vec::with_capacity(block_count);
    for block_index in 0..block_count {
        let mut surprise_sum = 0.0;
        let mut electric_count = 0;
        let mut magnetic_count = 0;
        let mut faces_per_species = 0;
        let mut min_probability = 1.0_f64;
        let mut max_invariant_error = 0.0_f64;
        for _ in 0..block_layers {
            let sampled = sample_layer(
                &mut state,
                &network,
                &mut rng,
                width,
                stream,
                absolute_layer,
            )?;
            surprise_sum += sampled.surprise;
            min_probability = min_probability.min(sampled.min_probability);
            if let Some(prior) = &previous {
                let vortices = network.vortices_between(prior, &sampled.outcomes)?;
                electric_count += vortices.electric;
                magnetic_count += vortices.magnetic;
                faces_per_species += vortices.faces_per_species;
            }
            previous = Some(sampled.outcomes);
            absolute_layer += 1;
            let error = stabilize_and_check(&mut state, config, width, stream, absolute_layer)?;
            max_invariant_error = max_invariant_error.max(error);
        }
        blocks.push(BlockEstimate {
            block_index,
            gamma: surprise_sum / block_layers as f64,
            electric_count,
            magnetic_count,
            faces_per_species,
            min_probability,
            max_invariant_error,
        });
    }

    let sector = network.sector();
    Ok(StreamEstimate {
        width,
        stream,
        seed,
        burn_in_layers,
        measurement_layers,
        block_layers,
        sector_wilson_loop: sector.wilson_loop,
        sector_fermion_parity: sector.fermion_parity,
        blocks,
    })
}

struct SampledLayer {
    outcomes: LayerOutcomes,
    surprise: f64,
    min_probability: f64,
}

fn sample_layer(
    state: &mut CovarianceState,
    network: &SelfDualNetwork,
    rng: &mut Xoshiro256PlusPlus,
    width: usize,
    stream: usize,
    layer: usize,
) -> Result<SampledLayer> {
    let mut onsite = Vec::with_capacity(width);
    let mut bond = Vec::with_capacity(width);
    let mut surprise = 0.0;
    let mut min_probability = 1.0_f64;
    for (gate_kind, measurements, outcomes) in [
        ("onsite", network.onsite_measurements(), &mut onsite),
        ("bond", network.bond_measurements(), &mut bond),
    ] {
        for (gate_index, &measurement) in measurements.iter().enumerate() {
            let (outcome, probability, gate_surprise) = sample_measurement(state, measurement, rng)
                .with_context(|| {
                    format!(
                        "sampling failed at width={width} stream={stream} layer={layer} \
                         gate={gate_kind}[{gate_index}]"
                    )
                })?;
            outcomes.push(outcome);
            surprise += gate_surprise;
            min_probability = min_probability.min(probability);
        }
    }
    Ok(SampledLayer {
        outcomes: LayerOutcomes { onsite, bond },
        surprise,
        min_probability,
    })
}

fn sample_measurement(
    state: &mut CovarianceState,
    measurement: Measurement,
    rng: &mut Xoshiro256PlusPlus,
) -> Result<(i8, f64, f64)> {
    let plus_probability = state.outcome_probability(measurement, 1)?;
    let uniform = ((rng.next_u64() >> 11) as f64) * (1.0 / ((1_u64 << 53) as f64));
    let outcome = if uniform < plus_probability { 1 } else { -1 };
    let stats = state.apply_outcome(measurement, outcome)?;
    Ok((outcome, stats.probability, stats.surprise))
}

fn stabilize_and_check(
    state: &mut CovarianceState,
    config: &RunConfig,
    width: usize,
    stream: usize,
    completed_layers: usize,
) -> Result<f64> {
    if completed_layers % config.sampling.stabilize_every_layers == 0 {
        state.stabilize().with_context(|| {
            format!(
                "stabilization failed at width={width} stream={stream} \
                 completed_layers={completed_layers}"
            )
        })?;
    }
    let errors = state.invariant_errors();
    let maximum = errors.antisymmetry.max(errors.purity);
    if !maximum.is_finite() || maximum > config.sampling.invariant_tolerance {
        bail!(
            "Gaussian invariant error {maximum:.6e} exceeds tolerance at \
             width={width} stream={stream} completed_layers={completed_layers}"
        );
    }
    Ok(maximum)
}
