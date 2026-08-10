use weak_self_dual::config::SELF_DUAL_BETA;
use weak_self_dual::network::BoundarySector;
use weak_self_dual::oracles::{
    clean_positive_trajectory, compare_covariance_to_dense, compare_gauge_equivalent_trajectories,
    enumerate_dense_trajectories,
};

#[test]
fn enumerated_born_distribution_normalizes() {
    let trajectories =
        enumerate_dense_trajectories(2, 1, SELF_DUAL_BETA, BoundarySector::vacuum()).unwrap();
    assert_eq!(trajectories.len(), 16);
    let total: f64 = trajectories.iter().map(|row| row.probability).sum();
    assert!((total - 1.0).abs() < 1.0e-12);
}

#[test]
fn all_positive_clean_path_matches_dense_evolution() {
    let oracle = clean_positive_trajectory(2, 3, SELF_DUAL_BETA).unwrap();
    assert!(oracle.max_covariance_error < 1.0e-10);
    assert!(oracle.total_surprise.is_finite());
}

#[test]
fn gaussian_and_dense_trajectory_probabilities_match() {
    let comparison = compare_covariance_to_dense(2, 2, SELF_DUAL_BETA).unwrap();
    assert!(comparison.max_probability_error < 1.0e-11);
    assert!(comparison.max_parity_error < 1.0e-10);
    assert!(comparison.max_covariance_error < 1.0e-10);
}

#[test]
fn gauge_equivalent_covariance_trajectories_match() {
    let comparison = compare_gauge_equivalent_trajectories(2, 2, SELF_DUAL_BETA).unwrap();
    assert!(comparison.max_probability_error < 1.0e-11);
    assert!(comparison.max_observable_error < 1.0e-10);
}
