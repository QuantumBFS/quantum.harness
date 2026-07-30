use learning_mit::config::{RunConfig, RuntimeBudget, StageConfig};
use learning_mit::rng::derive_seed;
use std::path::Path;

fn fixture() -> RunConfig {
    RunConfig {
        base_seed: 122,
        production_gates: true,
        invariant_tolerance: 1.0e-9,
        runtime: RuntimeBudget {
            target_seconds: 3600,
            ordinary_stop_seconds: 3300,
            hard_stop_seconds: 5100,
            finalize_reserve_seconds: 300,
        },
        stages: vec![StageConfig {
            name: "xy-coarse".to_string(),
            theta_pi: 0.5,
            phi_pi: vec![0.18, 0.21],
            widths: vec![8, 12, 16, 24],
            streams: 4,
            burn_in_layers_per_width: 12,
            measurement_layers_per_width: 40,
            block_layers_per_width: 5,
        }],
    }
}

#[test]
fn production_budget_rejects_a_late_hard_stop() {
    let mut config = fixture();
    config.validate().unwrap();
    config.runtime.hard_stop_seconds = 5101;
    assert!(config.validate().unwrap_err().to_string().contains("5100"));
}

#[test]
fn short_test_budget_remains_valid_without_production_gates() {
    let mut config = fixture();
    config.production_gates = false;
    config.runtime = RuntimeBudget {
        target_seconds: 4,
        ordinary_stop_seconds: 3,
        hard_stop_seconds: 5,
        finalize_reserve_seconds: 1,
    };
    config.validate().unwrap();
}

#[test]
fn incomplete_blocks_are_rejected() {
    let mut config = fixture();
    config.stages[0].measurement_layers_per_width = 41;
    assert!(config
        .validate()
        .unwrap_err()
        .to_string()
        .contains("complete blocks"));
}

#[test]
fn seed_derivation_separates_every_coordinate() {
    let a = derive_seed(122, 1, 2, 16, 0, 0);
    let b = derive_seed(122, 1, 2, 16, 1, 0);
    let c = derive_seed(122, 2, 2, 16, 0, 0);
    assert_ne!(a, b);
    assert_ne!(a, c);
    assert_eq!(a, derive_seed(122, 1, 2, 16, 0, 0));
}

#[test]
fn production_v2_declares_independent_xy_validation_and_seven_width_diii_locator() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let config = RunConfig::load(&root.join("configs/production-v2.toml")).unwrap();
    assert!(config.production_gates);
    assert_eq!(
        (
            config.runtime.target_seconds,
            config.runtime.ordinary_stop_seconds,
            config.runtime.hard_stop_seconds,
            config.runtime.finalize_reserve_seconds,
        ),
        (3600, 3300, 5100, 300)
    );
    assert_eq!(config.stages.len(), 2);

    let xy = &config.stages[0];
    assert_eq!(xy.name, "xy-validation");
    assert_eq!(xy.theta_pi, 0.5);
    assert_eq!(xy.phi_pi, vec![0.18, 0.21, 0.24, 0.25, 0.27, 0.30]);
    assert_eq!(xy.widths, vec![8, 12, 16, 24]);

    let diii = &config.stages[1];
    assert_eq!(diii.name, "diii-locator");
    assert_eq!(diii.theta_pi, 0.45);
    assert_eq!(
        diii.phi_pi,
        vec![0.16, 0.18, 0.20, 0.22, 0.24, 0.26, 0.28, 0.30, 0.32]
    );
    assert_eq!(diii.widths, vec![8, 12, 16, 20, 24, 28, 32]);
    assert_eq!(diii.streams, 4);
    assert_eq!(diii.burn_in_layers_per_width, 16);
    assert_eq!(diii.measurement_layers_per_width, 64);
    assert_eq!(diii.block_layers_per_width, 8);
}
