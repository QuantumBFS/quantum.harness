use std::{fs, path::PathBuf, time::Duration};

use occam71_rust::{
    AttemptStatus, SynthesisCertificate, SynthesisLimits, SynthesisProblem, SynthesisStatus,
    parse_dataset, parse_netlist, synthesize_minimal, verify, verify_packed,
};

fn fixture(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures")
        .join(name)
}

fn repository_file(path: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .join(path)
}

#[test]
fn checked_in_half_adder_certificate_records_minimality_and_verification() {
    let dataset_source = fs::read_to_string(fixture("half-adder.csv")).unwrap();
    let dataset = parse_dataset(&dataset_source).unwrap();
    let problem = SynthesisProblem::from_dataset(&dataset).unwrap();
    let generated = synthesize_minimal(
        &problem,
        &SynthesisLimits {
            max_gates: 2,
            timeout: Duration::from_secs(30),
            ..SynthesisLimits::default()
        },
    )
    .unwrap();
    assert_eq!(generated.status, SynthesisStatus::Sat);
    assert_eq!(
        generated
            .attempts
            .iter()
            .map(|attempt| attempt.status)
            .collect::<Vec<_>>(),
        [
            AttemptStatus::Unsat,
            AttemptStatus::Unsat,
            AttemptStatus::Sat
        ]
    );

    let checked_in: SynthesisCertificate = serde_json::from_str(
        &fs::read_to_string(repository_file(
            "docs/synthesis/half-adder-certificate.json",
        ))
        .unwrap(),
    )
    .unwrap();
    let checked_netlist =
        fs::read_to_string(repository_file("docs/synthesis/half-adder.txt")).unwrap();
    assert_eq!(checked_in.status, SynthesisStatus::Sat);
    assert_eq!(checked_in.minimal_gate_count, Some(2));
    assert_eq!(checked_in.problem_sha256, generated.problem_sha256);
    assert_eq!(checked_in.netlist_sha256, generated.netlist_sha256);
    assert_eq!(
        checked_in.netlist.as_deref(),
        Some(checked_netlist.as_str())
    );
    assert_eq!(generated.netlist.as_deref(), Some(checked_netlist.as_str()));

    let circuit = parse_netlist(&checked_netlist).unwrap();
    let scalar = verify(&circuit, &dataset).unwrap();
    let packed = verify_packed(&circuit, &dataset).unwrap();
    assert_eq!(scalar, packed);
    assert_eq!(scalar.gate_count, 2);
    assert_eq!(scalar.exact_matches, 4);
    assert_eq!(scalar.correct_bits, 8);
}

#[test]
fn two_bit_adder_certificate_matches_the_official_bit_order_fixture() {
    let dataset = parse_dataset(&fs::read_to_string(fixture("add-n2.csv")).unwrap()).unwrap();
    let problem = SynthesisProblem::from_dataset(&dataset).unwrap();
    let problem_identity = synthesize_minimal(
        &problem,
        &SynthesisLimits {
            max_gates: 0,
            timeout: Duration::from_secs(30),
            ..SynthesisLimits::default()
        },
    )
    .unwrap();
    let checked_in: SynthesisCertificate = serde_json::from_str(
        &fs::read_to_string(repository_file(
            "docs/synthesis/two-bit-adder-certificate.json",
        ))
        .unwrap(),
    )
    .unwrap();
    assert_eq!(checked_in.status, SynthesisStatus::Timeout);
    assert_eq!(checked_in.problem_sha256, problem_identity.problem_sha256);
    assert_eq!(
        checked_in
            .attempts
            .iter()
            .map(|attempt| (attempt.gate_bound, attempt.status))
            .collect::<Vec<_>>(),
        [
            (0, AttemptStatus::Unsat),
            (1, AttemptStatus::Unsat),
            (2, AttemptStatus::Unsat),
            (3, AttemptStatus::Unsat),
            (4, AttemptStatus::Unsat),
            (5, AttemptStatus::Unsat),
            (6, AttemptStatus::Timeout),
        ]
    );
    assert!(checked_in.netlist.is_none());
    assert!(checked_in.verification.is_none());
}
