use clean_ising::config::RunConfig;
use clean_ising::rng::{derive_seed, make_rng};
use rand_xoshiro::Xoshiro256PlusPlus;
use std::path::Path;

#[test]
fn quick_config_controls_the_approved_production_run() {
    let cfg = RunConfig::load(Path::new("configs/quick.toml")).unwrap();
    assert!(cfg.production_gates);
    assert_eq!(cfg.widths, vec![4, 6, 8, 10, 12, 16]);
    assert_eq!(cfg.aspect_ratio, 8);
    assert_eq!(cfg.mc.replicas, 4);
    assert_eq!(cfg.mc.grid_intervals, 32);
    assert_eq!(cfg.mc.thermal_sweeps, 200);
    assert_eq!(cfg.mc.measurement_sweeps, 800);
    assert_eq!(cfg.mc.block_sweeps, 20);
    cfg.validate().unwrap();
}

#[test]
fn seed_derivation_is_stable_and_separates_replicas() {
    assert_eq!(derive_seed(42, 8, 3, 1), 0xbc38_fb86_b239_3c17);
    assert_eq!(derive_seed(42, 8, 3, 2), 0xa742_56a8_8e09_bc5b);
}

#[test]
fn rng_factory_returns_the_required_xoshiro256plusplus() {
    let _: Xoshiro256PlusPlus = make_rng(42);
}

#[test]
fn production_config_rejects_a_changed_sampling_contract() {
    let mut cfg = RunConfig::load(Path::new("configs/quick.toml")).unwrap();
    cfg.mc.replicas = 3;
    let error = cfg.validate().unwrap_err().to_string();
    assert!(error.contains("four replicas"), "{error}");
}
