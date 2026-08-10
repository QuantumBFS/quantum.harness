use weak_self_dual::covariance::{CovarianceState, Measurement};

#[test]
fn born_probability_matches_a_hand_derived_eigenstate_value() {
    let state = CovarianceState::paired_vacuum(2).unwrap();
    let beta = 0.4;
    let measurement = Measurement {
        a: 0,
        b: 1,
        observable_sign: 1,
        beta,
    };
    let expected = 0.5 * (1.0 + beta.tanh());
    let actual = state.outcome_probability(measurement, 1).unwrap();
    assert!((actual - expected).abs() < 1.0e-14);
}

#[test]
fn weak_update_matches_the_mobius_formula_from_zero_parity() {
    let mut state = CovarianceState::paired_vacuum(2).unwrap();
    let beta = 0.3;
    let measurement = Measurement {
        a: 1,
        b: 2,
        observable_sign: 1,
        beta,
    };
    let stats = state.apply_outcome(measurement, -1).unwrap();
    assert!((stats.probability - 0.5).abs() < 1.0e-14);
    assert!((state.parity_expectation(1, 2, 1).unwrap() + beta.tanh()).abs() < 1.0e-13);
}

#[test]
fn update_preserves_pure_gaussian_invariants() {
    let mut state = CovarianceState::paired_vacuum(3).unwrap();
    let measurement = Measurement {
        a: 1,
        b: 2,
        observable_sign: 1,
        beta: 0.7,
    };
    state.apply_outcome(measurement, 1).unwrap();
    let errors = state.invariant_errors();
    assert!(errors.antisymmetry < 1.0e-12);
    assert!(errors.purity < 1.0e-11);
}

#[test]
fn reversed_observable_orientation_flips_the_expectation() {
    let state = CovarianceState::paired_vacuum(2).unwrap();
    assert_eq!(state.parity_expectation(0, 1, 1).unwrap(), 1.0);
    assert_eq!(state.parity_expectation(0, 1, -1).unwrap(), -1.0);
}

#[test]
fn malformed_measurements_are_rejected() {
    let state = CovarianceState::paired_vacuum(2).unwrap();
    let same_index = Measurement {
        a: 1,
        b: 1,
        observable_sign: 1,
        beta: 0.4,
    };
    assert!(state
        .outcome_probability(same_index, 1)
        .unwrap_err()
        .to_string()
        .contains("distinct"));
}

#[test]
fn stabilization_is_idempotent_on_a_pure_covariance() {
    let mut state = CovarianceState::paired_vacuum(3).unwrap();
    let before = state.matrix().clone();
    state.stabilize().unwrap();
    assert!((&before - state.matrix()).amax() < 1.0e-14);
    assert!(state.invariant_errors().purity < 1.0e-13);
}
