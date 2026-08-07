use std::time::Duration;

use occam71_rust::{
    ArithmeticFamily, AttemptStatus, InverseSpec, SynthesisLimits, SynthesisStatus,
    build_relation_problem, parse_netlist, synthesize_minimal_relation, verify_inverse_relation,
};

fn limits(max_gates: usize, timeout_seconds: u64) -> SynthesisLimits {
    SynthesisLimits {
        max_gates,
        timeout: Duration::from_secs(timeout_seconds),
        ..SynthesisLimits::default()
    }
}

fn assert_verified_sat(family: ArithmeticFamily, max_gates: usize) {
    let spec = InverseSpec::new(family, 2).unwrap();
    let problem = build_relation_problem(spec).unwrap();
    let certificate = synthesize_minimal_relation(&problem, &limits(max_gates, 60)).unwrap();
    eprintln!("{}", certificate.to_json_pretty().unwrap());
    assert_eq!(
        certificate.status,
        SynthesisStatus::Sat,
        "{family:?}: {}",
        certificate.status_detail
    );
    let gate_count = certificate.minimal_gate_count.unwrap();
    assert_eq!(certificate.attempts[gate_count].status, AttemptStatus::Sat);
    assert!(
        certificate.attempts[..gate_count]
            .iter()
            .all(|attempt| attempt.status == AttemptStatus::Unsat)
    );
    let circuit = parse_netlist(certificate.netlist.as_deref().unwrap()).unwrap();
    let verified = verify_inverse_relation(&circuit, spec).unwrap();
    assert_eq!(verified.mismatches, 0);
}

#[test]
fn n2_linear_controls_are_recovered_by_relation_search() {
    assert_verified_sat(ArithmeticFamily::Add, 8);
    assert_verified_sat(ArithmeticFamily::AbsDiff, 8);
}

#[test]
fn n1_multiply_relation_search_produces_a_verified_result() {
    let spec = InverseSpec::new(ArithmeticFamily::Multiply, 1).unwrap();
    let problem = build_relation_problem(spec).unwrap();
    let certificate = synthesize_minimal_relation(&problem, &limits(4, 10)).unwrap();
    assert_eq!(certificate.status, SynthesisStatus::Sat);
    let circuit = parse_netlist(certificate.netlist.as_deref().unwrap()).unwrap();
    assert_eq!(
        verify_inverse_relation(&circuit, spec).unwrap().mismatches,
        0
    );
}

#[test]
#[ignore = "bounded research run; invoke explicitly and report SAT or timeout without upgrading the claim"]
fn n2_multiply_relation_search_records_its_budgeted_outcome() {
    let spec = InverseSpec::new(ArithmeticFamily::Multiply, 2).unwrap();
    let problem = build_relation_problem(spec).unwrap();
    let certificate = synthesize_minimal_relation(&problem, &limits(12, 20)).unwrap();
    eprintln!("{}", certificate.to_json_pretty().unwrap());
    match certificate.status {
        SynthesisStatus::Sat => {
            let circuit = parse_netlist(certificate.netlist.as_deref().unwrap()).unwrap();
            assert_eq!(
                verify_inverse_relation(&circuit, spec).unwrap().mismatches,
                0
            );
        }
        SynthesisStatus::Timeout => {
            assert_eq!(
                certificate.attempts.last().unwrap().status,
                AttemptStatus::Timeout
            );
            assert!(
                certificate.attempts[..certificate.attempts.len() - 1]
                    .iter()
                    .all(|attempt| attempt.status == AttemptStatus::Unsat)
            );
        }
        status => panic!("unexpected bounded multiply outcome: {status:?}"),
    }
}
