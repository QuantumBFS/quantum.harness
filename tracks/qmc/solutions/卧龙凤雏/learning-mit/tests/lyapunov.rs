use learning_mit::circuit::{single_particle_gate, AppliedGate};
use learning_mit::gaussian::{MajoranaState, MeasurementGate};
use learning_mit::lyapunov::{temporal_gap, LyapunovAccumulator};
use nalgebra::{DMatrix, DVector};
use num_complex::Complex64;

#[test]
fn diagonal_transfer_recovers_known_exponents() {
    let mut accumulator = LyapunovAccumulator::new(2, 1).unwrap();
    let gate = DMatrix::from_diagonal(&DVector::from_vec(vec![
        Complex64::new(2.0, 0.0),
        Complex64::new(0.5, 0.0),
    ]));
    for _ in 0..10 {
        accumulator.push(&gate).unwrap();
    }

    let values = accumulator.spectrum().unwrap();
    assert!((values[0] - 2.0_f64.ln()).abs() < 1.0e-12);
    assert!((values[1] + 2.0_f64.ln()).abs() < 1.0e-12);
}

#[test]
fn temporal_gap_requires_two_separated_exponents() {
    assert!((temporal_gap(&[0.7, 0.2]).unwrap() - 0.5).abs() < 1.0e-15);
    assert!(temporal_gap(&[0.2, 0.2]).is_err());
    assert!(temporal_gap(&[0.2]).is_err());
}

#[test]
fn unitary_single_particle_gate_induces_the_covariance_rotation() {
    let angle = 0.37;
    let applied = AppliedGate {
        measurement: MeasurementGate {
            a: 1,
            b: 2,
            observable_sign: 1,
            strength: 0.0,
        },
        outcome: 1,
        probability: 0.5,
        conditional_entropy: std::f64::consts::LN_2,
        rotation: angle,
    };
    let gate = single_particle_gate(6, &applied).unwrap();
    assert!(gate.iter().all(|value| value.im.abs() < 1.0e-14));

    let initial = MajoranaState::paired_vacuum(3).unwrap();
    let expected =
        gate.map(|value| value.re) * initial.matrix() * gate.map(|value| value.re).transpose();
    let mut actual = initial;
    actual.apply_rotation(1, 2, angle).unwrap();
    assert!((&expected - actual.matrix()).amax() < 1.0e-12);
}

#[test]
fn forced_transfer_gate_is_complex_orthogonal() {
    let applied = AppliedGate {
        measurement: MeasurementGate {
            a: 0,
            b: 3,
            observable_sign: -1,
            strength: 0.61,
        },
        outcome: -1,
        probability: 0.4,
        conditional_entropy: 0.67,
        rotation: -0.29,
    };
    let gate = single_particle_gate(4, &applied).unwrap();
    let residual = &gate * gate.transpose() - DMatrix::<Complex64>::identity(4, 4);
    assert!(
        residual
            .iter()
            .map(|value| value.norm())
            .fold(0.0_f64, f64::max)
            < 1.0e-12
    );
}
