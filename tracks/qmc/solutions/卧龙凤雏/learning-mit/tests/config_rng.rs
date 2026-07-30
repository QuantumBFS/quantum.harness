use learning_mit::config::{RunConfig, RuntimeBudget, StageConfig};
use learning_mit::rng::derive_seed;

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
