mod common;

use std::fs;

use occam71_rust::{
    VerificationMetrics, parse_dataset, parse_netlist, parse_packed_dataset, verify,
    verify_prepacked,
};

#[test]
fn all_manifest_cases_match_scalar_and_packed_oracles() {
    let vendor = common::vendor_root();
    if !vendor.join("verify.jl").exists() {
        eprintln!("official data is missing; run ./scripts/fetch-occam-data.sh");
        return;
    }
    for case in common::load_manifest().cases {
        let source = common::materialize_circuit(&case, &vendor);
        let circuit = parse_netlist(&source).unwrap();
        let dataset_source = fs::read_to_string(vendor.join(&case.dataset)).unwrap();
        let dataset = parse_dataset(&dataset_source).unwrap();
        let scalar = verify(&circuit, &dataset).unwrap();
        let packed =
            verify_prepacked(&circuit, &parse_packed_dataset(&dataset_source).unwrap()).unwrap();
        assert_eq!(packed, scalar, "backend mismatch for {}", case.name);
        assert_eq!(
            scalar,
            VerificationMetrics {
                samples: case.samples,
                gate_count: case.gates,
                exact_matches: case.exact_matches,
                correct_bits: case.correct_bits,
                total_bits: case.total_bits,
            },
            "oracle mismatch for {}",
            case.name
        );
    }
}
