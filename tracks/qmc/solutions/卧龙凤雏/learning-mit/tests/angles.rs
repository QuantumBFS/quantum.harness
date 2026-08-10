use learning_mit::angles::{kw_dual, GateCouplings};
use num_complex::Complex64;

const TOLERANCE: f64 = 1.0e-12;

#[test]
fn x_plus_z_is_real_self_dual() {
    let couplings = GateCouplings::from_pi_units(0.25, 0.0).unwrap();
    let expected = (1.0_f64 + 2.0_f64.sqrt()).ln();

    assert!((couplings.j - expected).abs() < TOLERANCE);
    assert!((couplings.j_dual - expected).abs() < TOLERANCE);
    assert!(couplings.phi_dual.abs() < TOLERANCE);
}

#[test]
fn xy_line_matches_closed_form_and_branch() {
    let phi_pi = 0.25;
    let couplings = GateCouplings::from_pi_units(0.5, phi_pi).unwrap();
    let phi = std::f64::consts::PI * phi_pi;

    assert!(couplings.j.abs() < TOLERANCE);
    assert!((couplings.j_dual + (phi / 2.0).tan().ln()).abs() < TOLERANCE);
    assert!((couplings.phi_dual + std::f64::consts::FRAC_PI_2).abs() < TOLERANCE);
}

#[test]
fn kw_map_obeys_its_defining_relation_and_conjugation() {
    let z = Complex64::new(0.73, 0.41);
    let dual = kw_dual(z).unwrap();
    let residual = (-dual).exp() - (z * 0.5).tanh();
    assert!(residual.norm() < TOLERANCE);

    let conjugate_dual = kw_dual(z.conj()).unwrap();
    assert!((conjugate_dual - dual.conj()).norm() < TOLERANCE);
}

#[test]
fn approved_scan_points_have_finite_couplings() {
    let xy_phi_pi = [0.18, 0.21, 0.24, 0.25, 0.27, 0.30];
    let generic_phi_pi = [0.06, 0.10, 0.14, 0.18, 0.22, 0.26, 0.30, 0.34];

    for phi_pi in xy_phi_pi {
        assert_finite(GateCouplings::from_pi_units(0.5, phi_pi).unwrap());
    }
    for phi_pi in generic_phi_pi {
        assert_finite(GateCouplings::from_pi_units(0.45, phi_pi).unwrap());
    }
}

#[test]
fn singular_x_endpoint_is_rejected() {
    let error = GateCouplings::from_pi_units(0.0, 0.1).unwrap_err();
    assert!(error.to_string().contains("singular"));
}

fn assert_finite(couplings: GateCouplings) {
    for value in [
        couplings.theta,
        couplings.phi,
        couplings.j,
        couplings.j_dual,
        couplings.phi_dual,
    ] {
        assert!(value.is_finite(), "non-finite coupling: {value}");
    }
}
