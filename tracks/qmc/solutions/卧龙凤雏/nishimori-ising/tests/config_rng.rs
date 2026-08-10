use nishimori_ising::config::{
    RunConfig, ANTIFERROMAGNETIC_PROBABILITY, NISHIMORI_K, PRODUCTION_WIDTHS,
};
use nishimori_ising::rng::{derive_seed, make_rng};
use rand_xoshiro::rand_core::Rng;
use std::path::Path;

#[test]
fn production_configuration_is_the_frozen_scientific_contract() {
    let config = RunConfig::load(Path::new("configs/production.toml")).unwrap();
    config.validate().unwrap();

    assert_eq!(config.widths, PRODUCTION_WIDTHS);
    assert_eq!(
        config.antiferromagnetic_probability,
        ANTIFERROMAGNETIC_PROBABILITY
    );
    assert_eq!(config.nishimori_k, NISHIMORI_K);
    assert_eq!(config.disorder.replicas, 8);
    assert_eq!(config.disorder.burn_in_rows, 4_096);
    assert_eq!(config.disorder.measurement_rows, 1_048_576);
    assert_eq!(config.disorder.block_rows, 16_384);
    assert_eq!(config.refinement_level, 0);
}

#[test]
fn approved_level_one_refinement_only_doubles_measurement_rows() {
    let baseline = RunConfig::load(Path::new("configs/production.toml")).unwrap();
    let refinement = RunConfig::load(Path::new("configs/refinement-1.toml")).unwrap();
    refinement.validate().unwrap();

    assert_eq!(refinement.refinement_level, 1);
    assert_eq!(
        refinement.disorder.measurement_rows,
        2 * baseline.disorder.measurement_rows
    );
    assert_eq!(refinement.disorder.block_rows, baseline.disorder.block_rows);
    assert_eq!(refinement.widths, baseline.widths);
    assert_eq!(refinement.base_seed, baseline.base_seed);
    assert_eq!(refinement.disorder.replicas, baseline.disorder.replicas);
    assert_eq!(
        refinement.disorder.burn_in_rows,
        baseline.disorder.burn_in_rows
    );
}

#[test]
fn production_rows_cannot_change_without_matching_refinement_level() {
    let mut config = RunConfig::load(Path::new("configs/production.toml")).unwrap();
    config.disorder.measurement_rows *= 2;
    assert!(config.validate().is_err());
}

#[test]
fn test_configuration_is_valid_but_cannot_enable_production_gates() {
    let mut config = RunConfig::load(Path::new("configs/test.toml")).unwrap();
    config.validate().unwrap();

    config.production_gates = true;
    let error = config.validate().unwrap_err().to_string();
    assert!(error.contains("production sampling"));
}

#[test]
fn changing_the_fixed_nishimori_point_is_rejected() {
    let mut config = RunConfig::load(Path::new("configs/test.toml")).unwrap();
    config.antiferromagnetic_probability += 1.0e-6;
    assert!(config.validate().is_err());

    let mut config = RunConfig::load(Path::new("configs/test.toml")).unwrap();
    config.nishimori_k += 1.0e-6;
    assert!(config.validate().is_err());
}

#[test]
fn configuration_round_trip_is_compatible() {
    let config = RunConfig::load(Path::new("configs/test.toml")).unwrap();
    let encoded = toml::to_string(&config).unwrap();
    let decoded: RunConfig = toml::from_str(&encoded).unwrap();
    assert!(config.compatible_with(&decoded));
}

#[test]
fn seed_derivation_is_stable_and_width_independent() {
    assert_eq!(derive_seed(122_464, 0, 0), 17_160_368_628_469_487_600);
    assert_eq!(derive_seed(122_464, 7, 0), 7_978_804_757_817_875_988);
    assert_ne!(derive_seed(122_464, 0, 0), derive_seed(122_464, 1, 0));
    assert_ne!(derive_seed(122_464, 0, 0), derive_seed(122_464, 0, 1));
}

#[test]
fn xoshiro256plusplus_replay_is_exact() {
    let seed = derive_seed(122_464, 3, 9);
    let mut first = make_rng(seed);
    let mut second = make_rng(seed);
    let first_words: Vec<u64> = (0..16).map(|_| first.next_u64()).collect();
    let second_words: Vec<u64> = (0..16).map(|_| second.next_u64()).collect();
    assert_eq!(first_words, second_words);
}
