use assert_cmd::Command;
use learning_mit::angles::GateCouplings;
use learning_mit::circuit::{apply_forced_gate, BoundarySector, GenericCircuit};
use learning_mit::gaussian::MajoranaState;
use learning_mit::oracles::{class_d_block_residual, compare_dense_to_gaussian};
use learning_mit::oracles::{negative_control_oracle, physical_limit_oracle};
use std::fs;
use weak_self_dual::covariance::CovarianceState;
use weak_self_dual::network::{BoundarySector as ReferenceSector, SelfDualNetwork};

#[test]
fn dense_enumeration_matches_generic_gaussian_trajectories() {
    let couplings = GateCouplings::from_pi_units(0.45, 0.18).unwrap();
    let comparison = compare_dense_to_gaussian(2, 2, couplings, BoundarySector::vacuum()).unwrap();

    assert!(comparison.max_joint_probability_error < 1.0e-11);
    assert!(comparison.max_covariance_error < 1.0e-10);
    assert!(comparison.max_entropy_error < 1.0e-10);
    assert!((comparison.total_probability - 1.0).abs() < 1.0e-12);
}

#[test]
fn real_self_dual_limit_matches_the_frozen_sampler_kernel() {
    let width = 4;
    let couplings = GateCouplings::from_pi_units(0.25, 0.0).unwrap();
    let generic = GenericCircuit::new(width, couplings, BoundarySector::vacuum()).unwrap();
    let reference = SelfDualNetwork::new(
        width,
        couplings.j,
        ReferenceSector {
            wilson_loop: 1,
            fermion_parity: 1,
        },
    )
    .unwrap();
    let generic_schedule = generic
        .onsite_gates()
        .iter()
        .chain(generic.bond_gates())
        .copied()
        .collect::<Vec<_>>();
    let reference_schedule = reference
        .onsite_measurements()
        .iter()
        .chain(reference.bond_measurements())
        .copied()
        .collect::<Vec<_>>();
    let mut generic_state = MajoranaState::paired_vacuum(width).unwrap();
    let mut reference_state = CovarianceState::paired_vacuum(width).unwrap();
    let mut max_probability_error = 0.0_f64;
    let mut max_covariance_error = 0.0_f64;

    for period in 0..3 {
        for (gate_index, (&gate, &measurement)) in
            generic_schedule.iter().zip(&reference_schedule).enumerate()
        {
            let outcome = if (period + gate_index) % 3 == 0 {
                -1
            } else {
                1
            };
            let generic_probability = generic_state
                .outcome_probability(gate.measurement, outcome)
                .unwrap();
            let reference_probability = reference_state
                .outcome_probability(measurement, outcome)
                .unwrap();
            max_probability_error =
                max_probability_error.max((generic_probability - reference_probability).abs());
            apply_forced_gate(&mut generic_state, gate, outcome).unwrap();
            reference_state.apply_outcome(measurement, outcome).unwrap();
            max_covariance_error = max_covariance_error
                .max((generic_state.matrix() - reference_state.matrix()).amax());
        }
    }
    assert!(
        max_probability_error < 1.0e-12,
        "max probability error = {max_probability_error:.6e}"
    );
    assert!(
        max_covariance_error < 1.0e-11,
        "max covariance error = {max_covariance_error:.6e}"
    );
}

#[test]
fn xy_transfer_decomposes_but_generic_diii_cut_does_not() {
    let xy = GateCouplings::from_pi_units(0.5, 0.25).unwrap();
    let generic = GateCouplings::from_pi_units(0.45, 0.18).unwrap();

    assert!(class_d_block_residual(xy).unwrap() < 1.0e-12);
    assert!(class_d_block_residual(generic).unwrap() > 1.0e-3);
}

#[test]
fn x_and_y_physical_limits_pass_predeclared_checks() {
    let oracle = physical_limit_oracle().unwrap();
    assert!(oracle.y_swap_residual < 1.0e-12);
    assert!(
        oracle.y_min_volume_law_fraction > 0.99,
        "Y fractions: {:?}",
        oracle.y_volume_law_fractions
    );
    assert!(
        oracle.x_entropy_density_decreases,
        "X densities: {:?}",
        oracle.x_entropy_densities
    );
}

#[test]
fn iid_signs_are_distinguishable_from_conditional_born_sampling() {
    let oracle = negative_control_oracle(122).unwrap();
    assert!(oracle.z_score > oracle.required_z_score);
    assert!(oracle.passed);
}

#[test]
fn oracles_cli_writes_a_passing_machine_readable_artifact() {
    let run_dir = tempfile::tempdir().unwrap();
    Command::cargo_bin("learning-mit")
        .unwrap()
        .args([
            "oracles",
            "--config",
            "configs/test.toml",
            "--run-dir",
            run_dir.path().to_str().unwrap(),
        ])
        .assert()
        .success();

    let artifact: serde_json::Value =
        serde_json::from_slice(&fs::read(run_dir.path().join("raw/oracles.json")).unwrap())
            .unwrap();
    assert_eq!(artifact["required_pass"], true);
}
