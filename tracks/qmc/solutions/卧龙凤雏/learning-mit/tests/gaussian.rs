use learning_mit::gaussian::{MajoranaState, MeasurementGate};
use nalgebra::DMatrix;

const TOLERANCE: f64 = 1.0e-11;

#[test]
fn rotation_and_inverse_recover_covariance() {
    let mut state = MajoranaState::paired_vacuum(3).unwrap();
    let before = state.matrix().clone();

    state.apply_rotation(1, 2, 0.37).unwrap();
    assert!(state.invariant_errors().purity < TOLERANCE);
    state.apply_rotation(1, 2, -0.37).unwrap();

    assert!((&before - state.matrix()).amax() < 1.0e-12);
}

#[test]
fn born_probabilities_normalize_and_updates_remain_pure() {
    let mut state = MajoranaState::paired_vacuum(2).unwrap();
    let gate = MeasurementGate {
        a: 1,
        b: 2,
        observable_sign: 1,
        strength: 0.8,
    };
    let total =
        state.outcome_probability(gate, 1).unwrap() + state.outcome_probability(gate, -1).unwrap();
    assert!((total - 1.0).abs() < 1.0e-14);

    let stats = state.apply_measurement(gate, 1).unwrap();
    assert!((stats.probability - 0.5).abs() < 1.0e-14);
    let errors = state.invariant_errors();
    assert!(errors.antisymmetry < 1.0e-12);
    assert!(errors.purity < TOLERANCE);
}

#[test]
fn paired_and_bell_pair_entropies_match_exact_fixtures() {
    let paired = MajoranaState::paired_vacuum(2).unwrap();
    assert!(paired.interval_entropy(0, 1).unwrap() < TOLERANCE);

    let bell = MajoranaState::from_matrix(2, translated_bell_covariance(2)).unwrap();
    assert!((bell.interval_entropy(0, 1).unwrap() - std::f64::consts::LN_2).abs() < TOLERANCE);
    assert!(bell.interval_entropy(0, 2).unwrap() < TOLERANCE);
}

#[test]
fn pure_state_interval_entropy_equals_its_complement() {
    let state = MajoranaState::from_matrix(4, translated_bell_covariance(4)).unwrap();
    let interval = state.interval_entropy(0, 1).unwrap();
    let complement = state.interval_entropy(1, 3).unwrap();
    assert!((interval - complement).abs() < TOLERANCE);
}

#[test]
fn wick_parity_correlation_has_the_expected_sign_and_translation() {
    let state = MajoranaState::from_matrix(4, translated_bell_covariance(4)).unwrap();
    let first = state.connected_parity_correlation(0, 1).unwrap();
    let translated = state.connected_parity_correlation(2, 3).unwrap();

    assert!((first + 1.0).abs() < TOLERANCE);
    assert!((translated - first).abs() < TOLERANCE);
}

fn translated_bell_covariance(width: usize) -> DMatrix<f64> {
    assert!(width % 2 == 0);
    let mut matrix = DMatrix::zeros(2 * width, 2 * width);
    for first_site in (0..width).step_by(2) {
        set_pair(&mut matrix, 2 * first_site, 2 * (first_site + 1), 1.0);
        set_pair(
            &mut matrix,
            2 * first_site + 1,
            2 * (first_site + 1) + 1,
            1.0,
        );
    }
    matrix
}

fn set_pair(matrix: &mut DMatrix<f64>, a: usize, b: usize, value: f64) {
    matrix[(a, b)] = value;
    matrix[(b, a)] = -value;
}
