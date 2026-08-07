use crate::config::RunConfig;
use crate::lattice::IsingLattice;
use crate::rng::{derive_seed, make_rng};
use crate::schema::{McBlockRecord, SCHEMA_VERSION};
use crate::wolff::{effective_sweep, fixed_cluster_sweep};
use anyhow::{bail, Context, Result};
use rayon::prelude::*;

pub fn run_chain(
    config: &RunConfig,
    l: usize,
    k_index: usize,
    replica: usize,
) -> Result<Vec<McBlockRecord>> {
    config.validate()?;
    if !config.widths.contains(&l) {
        bail!("L={l} is not present in the configured widths");
    }
    if k_index > config.mc.grid_intervals {
        bail!(
            "K_index={k_index} exceeds grid_intervals={}",
            config.mc.grid_intervals
        );
    }
    if replica >= config.mc.replicas {
        bail!(
            "replica={replica} exceeds configured replica count {}",
            config.mc.replicas
        );
    }

    let m = l
        .checked_mul(config.aspect_ratio)
        .context("L*aspect_ratio overflowed usize")?;
    let k = config.critical_k * k_index as f64 / config.mc.grid_intervals as f64;
    let seed = derive_seed(config.base_seed, l, k_index, replica);
    let mut rng = make_rng(seed);
    let mut lattice = IsingLattice::random(l, m, &mut rng);

    let calibration_sweeps = (config.mc.thermal_sweeps / 2).max(1);
    let mut calibration_updates = 0_usize;
    for _ in 0..calibration_sweeps {
        calibration_updates += effective_sweep(&mut lattice, k, &mut rng).updates;
    }
    let cluster_updates_per_sweep =
        ((calibration_updates as f64 / calibration_sweeps as f64).round() as usize).max(1);
    for _ in calibration_sweeps..config.mc.thermal_sweeps {
        fixed_cluster_sweep(&mut lattice, k, &mut rng, cluster_updates_per_sweep);
    }

    let block_count = config.mc.measurement_sweeps / config.mc.block_sweeps;
    let mut records = Vec::with_capacity(block_count);
    for block_index in 0..block_count {
        let mut energy_sum = 0_i64;
        let mut energy_squared_sum = 0_i64;
        let mut cluster_flips = 0_usize;
        let mut cluster_updates = 0_usize;
        let mut max_cluster_size = 0_usize;
        for _ in 0..config.mc.block_sweeps {
            let sweep = fixed_cluster_sweep(&mut lattice, k, &mut rng, cluster_updates_per_sweep);
            let energy = lattice.energy();
            energy_sum += energy;
            energy_squared_sum = energy_squared_sum
                .checked_add(energy * energy)
                .context("energy-squared block sum overflowed i64")?;
            cluster_flips += sweep.total_flipped;
            cluster_updates += sweep.updates;
            max_cluster_size = max_cluster_size.max(sweep.max_cluster_size);
        }
        records.push(McBlockRecord {
            schema_version: SCHEMA_VERSION,
            l,
            m,
            k_index,
            k,
            replica,
            seed,
            thermal_sweeps: config.mc.thermal_sweeps,
            measurement_sweeps: config.mc.measurement_sweeps,
            block_index,
            block_sweeps: config.mc.block_sweeps,
            cluster_updates_per_sweep,
            energy_sum,
            energy_squared_sum,
            measurement_count: config.mc.block_sweeps,
            mean_cluster_size: cluster_flips as f64 / cluster_updates as f64,
            max_cluster_size,
            // Timings live in the manifest so raw scientific records replay byte-for-byte.
            cumulative_elapsed_s: 0.0,
        });
    }
    Ok(records)
}

pub fn run_all_chains(config: &RunConfig) -> Result<Vec<McBlockRecord>> {
    config.validate()?;
    let mut keys = Vec::new();
    for &l in &config.widths {
        for k_index in 0..=config.mc.grid_intervals {
            for replica in 0..config.mc.replicas {
                keys.push((l, k_index, replica));
            }
        }
    }
    let nested: Result<Vec<_>> = keys
        .par_iter()
        .map(|&(l, k_index, replica)| run_chain(config, l, k_index, replica))
        .collect();
    let mut records: Vec<_> = nested?.into_iter().flatten().collect();
    records.sort_by_key(|record| (record.l, record.k_index, record.replica, record.block_index));
    Ok(records)
}
