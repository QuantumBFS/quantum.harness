use std::{fs, path::PathBuf};

use occam71_rust::{parse_netlist, sha256_hex};

fn solution_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_owned()
}

#[test]
fn standalone_snapshot_verifies_every_release_claim_root() {
    let root = solution_root();
    let manifest: serde_json::Value =
        serde_json::from_slice(&fs::read(root.join("manifest.json")).unwrap()).unwrap();
    assert_eq!(manifest["schema_version"], 2);
    assert_eq!(manifest["learner"], "mdl-enumerator");
    assert_eq!(manifest["baseline_tag"], "v0.2.0");

    for instance in manifest["instances"].as_array().unwrap() {
        let circuit_path = instance["circuit_path"].as_str().unwrap();
        let prediction_path = instance["prediction_path"].as_str().unwrap();
        let report_path = instance["report_path"].as_str().unwrap();
        let circuit = fs::read(root.join(circuit_path)).unwrap();
        let prediction = fs::read(root.join(prediction_path)).unwrap();
        let report = fs::read(root.join(report_path)).unwrap();
        assert_eq!(sha256_hex(&circuit), instance["circuit_sha256"]);
        assert_eq!(sha256_hex(&prediction), instance["prediction_sha256"]);
        assert_eq!(
            instance["prediction_sha256"],
            instance["expected_commitment_sha256"]
        );
        assert_eq!(sha256_hex(&report), instance["report_sha256"]);
        assert_eq!(
            parse_netlist(std::str::from_utf8(&circuit).unwrap())
                .unwrap()
                .gates
                .len(),
            instance["gate_count"].as_u64().unwrap() as usize
        );
    }

    for prefix in ["optimization_report", "research_manifest"] {
        let path = manifest[format!("{prefix}_path")].as_str().unwrap();
        let expected = manifest[format!("{prefix}_sha256")].as_str().unwrap();
        assert_eq!(sha256_hex(&fs::read(root.join(path)).unwrap()), expected);
    }

    let rooted: serde_json::Value =
        serde_json::from_slice(&fs::read(root.join("research-manifest.json")).unwrap()).unwrap();
    assert_eq!(rooted["trial_rows"], 20_480);
    assert_eq!(
        sha256_hex(
            &fs::read(root.join(rooted["study_manifest_path"].as_str().unwrap())).unwrap()
        ),
        rooted["study_manifest_sha256"].as_str().unwrap()
    );
    for reference in rooted["official_mdl_reports"]
        .as_object()
        .unwrap()
        .values()
    {
        let report = fs::read(root.join(reference["report_path"].as_str().unwrap())).unwrap();
        assert_eq!(
            sha256_hex(&report),
            reference["report_sha256"].as_str().unwrap()
        );
        let report: serde_json::Value = serde_json::from_slice(&report).unwrap();
        assert_eq!(report["schema_version"], 2);
        assert_eq!(report["learner"], "mdl-enumerator");
        assert_eq!(report["exhaustive_mismatches"], 0);
        assert_eq!(report["commitment_matches"], true);
    }

    let study: serde_json::Value =
        serde_json::from_slice(&fs::read(root.join("research/manifest.json")).unwrap()).unwrap();
    assert_eq!(
        study["files"]["raw.jsonl"],
        rooted["raw_matrix_sha256"]
    );
    for (relative, expected) in study["files"].as_object().unwrap() {
        if relative == "raw.jsonl" {
            continue;
        }
        assert_eq!(
            sha256_hex(&fs::read(root.join("research").join(relative)).unwrap()),
            expected.as_str().unwrap(),
            "{relative}"
        );
    }
}
