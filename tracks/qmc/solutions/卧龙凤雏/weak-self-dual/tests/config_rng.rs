use rand_xoshiro::rand_core::Rng;
use std::path::Path;
use weak_self_dual::config::{
    RunConfig, SamplingConfig, SELF_DUAL_BETA, SELF_DUAL_THETA, TARGET_CENTRAL_CHARGE,
};
use weak_self_dual::rng::{derive_seed, make_rng};

fn test_config() -> RunConfig {
    RunConfig {
        widths: vec![2, 4],
        theta: SELF_DUAL_THETA,
        beta: SELF_DUAL_BETA,
        base_seed: 122_447,
        production_gates: false,
        refinement_level: 0,
        sampling: SamplingConfig {
            streams_per_width: 1,
            burn_in_layers_per_width: 2,
            measurement_layers_per_width: 8,
            block_layers_per_width: 2,
            stabilize_every_layers: 1,
            invariant_tolerance: 1.0e-9,
        },
    }
}

#[test]
fn fixed_physics_constants_drive_the_config_contract() {
    let config = test_config();
    config.validate().unwrap();
    assert!((SELF_DUAL_BETA - (1.0_f64 + 2.0_f64.sqrt()).ln()).abs() < 1.0e-15);
    assert_eq!(TARGET_CENTRAL_CHARGE, 0.447);
}

#[test]
fn derived_streams_are_stable_and_distinct() {
    let a = derive_seed(122_447, 6, 0, 0);
    let b = derive_seed(122_447, 8, 0, 0);
    assert_ne!(a, b);
    let mut first = make_rng(a);
    let mut replay = make_rng(a);
    assert_eq!(first.next_u64(), replay.next_u64());
}

#[test]
fn invalid_widths_are_rejected() {
    let mut config = test_config();
    config.widths = vec![6, 7, 8];
    assert!(config.validate().unwrap_err().to_string().contains("even"));
    config.widths = vec![6, 6, 8];
    assert!(config
        .validate()
        .unwrap_err()
        .to_string()
        .contains("unique"));
}

#[test]
fn incomplete_blocks_are_rejected() {
    let mut config = test_config();
    config.sampling.measurement_layers_per_width = 9;
    assert!(config
        .validate()
        .unwrap_err()
        .to_string()
        .contains("complete blocks"));
}

#[test]
fn final_precision_refinement_matches_the_frozen_contract() {
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("configs/refinement-2.toml");
    let config = RunConfig::load(&path).unwrap();
    config.validate().unwrap();
    assert!(config.production_gates);
    assert_eq!(config.refinement_level, 2);
    assert_eq!(config.sampling.streams_per_width, 128);
}
