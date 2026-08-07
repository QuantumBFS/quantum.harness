use std::{fs, path::PathBuf};

use occam71_rust::{
    ArithmeticFamily, InverseSpec, RelationSynthesisCertificate, RelationUnsatProofArtifact,
    SynthesisStatus, parse_netlist, sha256_hex, verify_inverse_relation,
};

fn repository_file(path: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .join(path)
}

fn check_artifact(directory: &str, family: ArithmeticFamily, expected_gates: usize) {
    let root = repository_file(directory);
    let certificate: RelationSynthesisCertificate =
        serde_json::from_str(&fs::read_to_string(root.join("certificate.json")).unwrap()).unwrap();
    let proof: RelationUnsatProofArtifact =
        serde_json::from_str(&fs::read_to_string(root.join("proof-manifest.json")).unwrap())
            .unwrap();
    assert_eq!(certificate.status, SynthesisStatus::Sat);
    assert_eq!(certificate.minimal_gate_count, Some(expected_gates));
    assert_eq!(proof.gate_bound + 1, expected_gates);

    let netlist = fs::read_to_string(root.join("circuit.txt")).unwrap();
    assert_eq!(certificate.netlist.as_deref(), Some(netlist.as_str()));
    assert_eq!(
        certificate.netlist_sha256.as_deref(),
        Some(sha256_hex(netlist.as_bytes()).as_str())
    );
    let circuit = parse_netlist(&netlist).unwrap();
    let spec = InverseSpec::new(family, 2).unwrap();
    assert_eq!(
        verify_inverse_relation(&circuit, spec).unwrap().mismatches,
        0
    );

    let cnf = fs::read(root.join("k-minus-1.cnf")).unwrap();
    let drat = fs::read(root.join("k-minus-1.drat")).unwrap();
    assert_eq!(proof.cnf_sha256, sha256_hex(&cnf));
    assert_eq!(proof.drat_sha256, sha256_hex(&drat));
}

#[test]
fn checked_in_n2_control_minima_have_consistent_circuits_and_proof_hashes() {
    check_artifact(
        "docs/inverse-certification/add-n2",
        ArithmeticFamily::Add,
        5,
    );
    check_artifact(
        "docs/inverse-certification/abs-diff-n2",
        ArithmeticFamily::AbsDiff,
        1,
    );
}

#[test]
fn checked_in_n2_multiply_has_an_eight_gate_witness_and_seven_gate_proof() {
    let root = repository_file("docs/inverse-certification/multiply-n2-symmetry");
    let netlist = fs::read_to_string(root.join("circuit.txt")).unwrap();
    let circuit = parse_netlist(&netlist).unwrap();
    assert_eq!(circuit.gates.len(), 8);

    let evidence = verify_inverse_relation(
        &circuit,
        InverseSpec::new(ArithmeticFamily::Multiply, 2).unwrap(),
    )
    .unwrap();
    assert_eq!(evidence.rows, 16);
    assert_eq!(evidence.valid_rows, 7);
    assert_eq!(evidence.invalid_rows, 9);
    assert_eq!(evidence.mismatches, 0);

    let proof: RelationUnsatProofArtifact =
        serde_json::from_str(&fs::read_to_string(root.join("proof-manifest.json")).unwrap())
            .unwrap();
    assert_eq!(proof.gate_bound, 7);
    let cnf = fs::read(root.join("k-minus-1.cnf")).unwrap();
    let drat = fs::read(root.join("k-minus-1.drat")).unwrap();
    assert_eq!(proof.cnf_sha256, sha256_hex(&cnf));
    assert_eq!(proof.drat_sha256, sha256_hex(&drat));
}
