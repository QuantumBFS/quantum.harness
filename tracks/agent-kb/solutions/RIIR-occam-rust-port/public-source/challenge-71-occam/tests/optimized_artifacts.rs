use std::{collections::BTreeMap, fs, path::PathBuf};

use occam71_rust::{parse_netlist, sha256_hex};
use serde::Deserialize;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Baseline {
    schema_version: u32,
    source_tag: String,
    source_commit: String,
    gate_counts: BTreeMap<String, usize>,
    circuit_sha256: BTreeMap<String, String>,
}

#[derive(Debug, Deserialize)]
struct Aggregate {
    schema_version: u32,
    baseline: String,
    abc_commit: String,
    processing_order: Vec<String>,
    instances: BTreeMap<String, serde_json::Value>,
}

fn solution_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("solutions/rewrite-it-in-rust")
}

#[test]
fn committed_optimization_strictly_improves_the_frozen_baseline() {
    let root = solution_root();
    let optimization = root.join("optimization");
    let baseline: Baseline =
        serde_json::from_str(&fs::read_to_string(optimization.join("baseline.json")).unwrap())
            .unwrap();
    let aggregate: Aggregate =
        serde_json::from_str(&fs::read_to_string(optimization.join("report.json")).unwrap())
            .unwrap();
    assert_eq!(baseline.schema_version, 1);
    assert_eq!(baseline.source_tag, "v0.2.0");
    assert_eq!(
        baseline.source_commit,
        "fc58c3a013c480ecbd12469b76266376d406fc99"
    );
    assert_eq!(baseline.circuit_sha256.len(), 4);
    assert_eq!(aggregate.schema_version, 1);
    assert_eq!(aggregate.baseline, "baseline.json");
    assert_eq!(
        aggregate.abc_commit,
        "e76768b9d34f9dc67cb6608efecd55db271ff849"
    );
    assert_eq!(
        aggregate.processing_order,
        ["mystery-B", "mystery-D", "mystery-C", "mystery-A"]
    );

    let mut strict_improvement = false;
    for instance in ["mystery-A", "mystery-B", "mystery-C", "mystery-D"] {
        let baseline_gates = baseline.gate_counts[instance];
        let circuit_bytes = fs::read(root.join(format!("circuits/{instance}.txt"))).unwrap();
        let circuit = parse_netlist(std::str::from_utf8(&circuit_bytes).unwrap()).unwrap();
        assert!(circuit.gates.len() <= baseline_gates);
        strict_improvement |= circuit.gates.len() < baseline_gates;

        let report = &aggregate.instances[instance];
        assert_eq!(report["baseline_gate_count"], baseline_gates);
        assert_eq!(report["selected_gate_count"], circuit.gates.len());
        assert_eq!(report["exhaustive_mismatches"], 0);
        assert_eq!(
            report["selected_circuit_sha256"],
            sha256_hex(&circuit_bytes)
        );
        assert!(
            report["abc"]["flows"]
                .as_array()
                .is_some_and(|flows| !flows.is_empty())
        );
        assert!(
            report["peephole_baseline"]["attempted_windows"]
                .as_u64()
                .is_some()
        );
        assert!(
            report["peephole_abc"]["attempted_windows"]
                .as_u64()
                .is_some()
        );

        let prediction =
            fs::read(root.join(format!("predictions/{instance}/test_outputs.csv"))).unwrap();
        let expected = fs::read_to_string(
            PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .parent()
                .unwrap()
                .join(format!(
                    "vendor/occam-circuit/datasets/{instance}/commitment.sha256"
                )),
        )
        .unwrap();
        assert_eq!(
            sha256_hex(&prediction),
            expected.split_whitespace().next().unwrap()
        );
    }
    assert!(strict_improvement);
}
