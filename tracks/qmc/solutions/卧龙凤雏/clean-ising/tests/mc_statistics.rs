use clean_ising::config::RunConfig;
use clean_ising::lattice::IsingLattice;
use clean_ising::mc::{run_all_chains, run_chain};
use clean_ising::rng::make_rng;
use clean_ising::wolff::fixed_cluster_sweep;
use std::path::Path;

#[test]
fn same_chain_key_replays_identical_blocks() {
    let cfg = RunConfig::load(Path::new("configs/test.toml")).unwrap();
    let a = run_chain(&cfg, 4, 2, 0).unwrap();
    let b = run_chain(&cfg, 4, 2, 0).unwrap();
    assert_eq!(a, b);
    assert_eq!(a.len(), cfg.mc.measurement_sweeps / cfg.mc.block_sweeps);
}

#[test]
fn parallel_chain_output_has_a_stable_key_order() {
    let cfg = RunConfig::load(Path::new("configs/test.toml")).unwrap();
    let records = run_all_chains(&cfg).unwrap();
    let keys: Vec<_> = records
        .iter()
        .map(|record| (record.l, record.k_index, record.replica, record.block_index))
        .collect();
    let mut sorted = keys.clone();
    sorted.sort_unstable();
    assert_eq!(keys, sorted);
}

#[test]
fn wolff_energy_agrees_with_exhaustive_four_by_four_thermodynamics() {
    let k = 0.2;
    let exact = exact_mean_energy_4x4(k);
    let mut block_means = Vec::new();
    for seed in [101_u64, 202, 303, 404] {
        let mut rng = make_rng(seed);
        let mut lattice = IsingLattice::random(4, 4, &mut rng);
        for _ in 0..1_000 {
            fixed_cluster_sweep(&mut lattice, k, &mut rng, 4);
        }
        for _ in 0..200 {
            let mut block_sum = 0.0;
            for _ in 0..100 {
                fixed_cluster_sweep(&mut lattice, k, &mut rng, 4);
                block_sum += lattice.energy() as f64;
            }
            block_means.push(block_sum / 100.0);
        }
    }
    let estimate = mean(&block_means);
    let standard_error =
        sample_standard_deviation(&block_means) / (block_means.len() as f64).sqrt();
    assert!(
        (estimate - exact).abs() <= 4.0 * standard_error,
        "exact={exact:.8}, estimate={estimate:.8}, standard_error={standard_error:.8}"
    );
}

fn exact_mean_energy_4x4(k: f64) -> f64 {
    let mut weighted_energy = 0.0;
    let mut partition = 0.0;
    for state in 0_u32..(1_u32 << 16) {
        let spins: Vec<i8> = (0..16)
            .map(|bit| if state & (1 << bit) == 0 { -1 } else { 1 })
            .collect();
        let energy = IsingLattice::from_spins(4, 4, spins).energy();
        let weight = (-k * energy as f64).exp();
        partition += weight;
        weighted_energy += weight * energy as f64;
    }
    weighted_energy / partition
}

fn mean(values: &[f64]) -> f64 {
    values.iter().sum::<f64>() / values.len() as f64
}

fn sample_standard_deviation(values: &[f64]) -> f64 {
    let average = mean(values);
    let variance = values
        .iter()
        .map(|value| (value - average).powi(2))
        .sum::<f64>()
        / (values.len() - 1) as f64;
    variance.sqrt()
}
