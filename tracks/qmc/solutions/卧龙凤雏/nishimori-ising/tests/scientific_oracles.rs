use clean_ising::config::{ExactConfig, CRITICAL_K};
use clean_ising::transfer::dominant_eigenpair;
use nishimori_ising::config::{RunConfig, NISHIMORI_K};
use nishimori_ising::disorder::DisorderRow;
use nishimori_ising::lyapunov::{estimate_replica, ProductState};
use nishimori_ising::oracles::{clean_transfer_oracle, nishimori_energy_identity};
use std::path::Path;

#[test]
fn product_state_normalizes_every_row_and_accumulates_log_norms() {
    let width = 4;
    let row = DisorderRow {
        horizontal: vec![1; width],
        vertical: vec![1; width],
    };
    let mut state = ProductState::new(width).unwrap();
    let first = state.advance(CRITICAL_K, &row).unwrap();
    let second = state.advance(CRITICAL_K, &row).unwrap();
    assert!(first.is_finite());
    assert!(second.is_finite());
    assert!((state.l1_norm() - 1.0).abs() < 1.0e-14);
}

#[test]
fn joint_block_estimator_is_exactly_replayable() {
    let mut config = RunConfig::load(Path::new("configs/test.toml")).unwrap();
    config.widths = vec![4, 6];
    config.disorder.replicas = 1;
    config.disorder.burn_in_rows = 16;
    config.disorder.measurement_rows = 64;
    config.disorder.block_rows = 16;

    let first = estimate_replica(&config, 0).unwrap();
    let second = estimate_replica(&config, 0).unwrap();
    assert_eq!(first, second);
    assert_eq!(first.blocks.len(), 4);
    assert!(first
        .blocks
        .iter()
        .all(|block| block.phi_by_width.len() == 2));
    assert_eq!(first.total_bonds, 2 * 6 * (16 + 64));
}

#[test]
fn clean_random_operator_has_the_deterministic_clean_eigenvalue_through_l10() {
    let points = clean_transfer_oracle(&[4, 6, 8, 10], CRITICAL_K, 512, 128).unwrap();
    for point in points {
        assert!(
            point.absolute_error < 2.0e-10,
            "L={} observed={} exact={} error={}",
            point.width,
            point.observed_log_lambda,
            point.exact_log_lambda,
            point.absolute_error
        );

        let direct =
            dominant_eigenpair(point.width, CRITICAL_K, &ExactConfig::strict_for_test()).unwrap();
        assert!((point.exact_log_lambda - direct.lambda.ln()).abs() < 1.0e-13);
    }
}

#[test]
fn common_disorder_finite_difference_recovers_nishimori_energy_identity() {
    let result =
        nishimori_energy_identity(4, 0.109_221_2, NISHIMORI_K, 1.0e-4, 771_991, 512, 32_768)
            .unwrap();
    assert!((result.expected - 2.0 * NISHIMORI_K.tanh()).abs() < 1.0e-15);
    assert!(
        result.absolute_error < 0.02,
        "derivative={} expected={} error={}",
        result.derivative,
        result.expected,
        result.absolute_error
    );
}
