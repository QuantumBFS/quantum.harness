use std::{
    collections::{BTreeMap, HashSet},
    fs,
    path::{Component, Path, PathBuf},
};

use occam71_rust::{
    AnySolutionManifest, LearningReport, MdlLearningReport, ResearchSolutionManifest,
    parse_commitment, parse_dataset, parse_netlist, parse_packed_dataset, parse_test_inputs,
    sha256_hex, verify, verify_prepacked,
};
use serde::Deserialize;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct RootedResearchManifest {
    schema_version: u32,
    protocol: String,
    trial_rows: usize,
    raw_matrix_sha256: String,
    study_manifest_path: String,
    study_manifest_sha256: String,
    official_mdl_reports: BTreeMap<String, MdlReportReference>,
    limitations: Vec<String>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct MdlReportReference {
    report_path: String,
    report_sha256: String,
    expression: String,
    description_cost: usize,
    minimum_unique: bool,
    compiled_gate_count: usize,
}

fn workspace_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_owned()
}

fn solution_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("solutions/rewrite-it-in-rust")
}

fn checked_relative(root: &Path, relative: &str) -> PathBuf {
    let path = Path::new(relative);
    assert!(!path.is_absolute(), "{relative}");
    assert!(
        path.components()
            .all(|component| matches!(component, Component::Normal(_))),
        "{relative}"
    );
    root.join(path)
}

fn require_research_manifest(source: &str) -> ResearchSolutionManifest {
    match AnySolutionManifest::from_json(source).unwrap() {
        AnySolutionManifest::V2(manifest) => manifest,
        AnySolutionManifest::V1(_) => panic!("release solution manifest must use schema 2"),
    }
}

#[test]
fn committed_solution_is_complete_hash_locked_and_perfect() {
    let solution = solution_root();
    let manifest_source = fs::read_to_string(solution.join("manifest.json")).unwrap();
    let manifest = require_research_manifest(&manifest_source);
    assert_eq!(manifest.schema_version, 2);
    assert_eq!(manifest.solution, "rewrite-it-in-rust");
    assert_eq!(manifest.learner, "mdl-enumerator");
    assert_eq!(manifest.baseline_tag, "v0.2.0");
    assert_eq!(manifest.instances.len(), 4);
    assert_eq!(
        sha256_hex(
            &fs::read(checked_relative(
                &solution,
                &manifest.optimization_report_path
            ))
            .unwrap()
        ),
        manifest.optimization_report_sha256
    );
    let rooted_research_source = fs::read(checked_relative(
        &solution,
        &manifest.research_manifest_path,
    ))
    .unwrap();
    assert_eq!(
        sha256_hex(&rooted_research_source),
        manifest.research_manifest_sha256
    );
    let rooted: RootedResearchManifest = serde_json::from_slice(&rooted_research_source).unwrap();
    assert_eq!(rooted.schema_version, 1);
    assert_eq!(
        rooted.protocol,
        "16 tasks × 8 fractions × 20 seeds × 8 methods"
    );
    assert_eq!(rooted.trial_rows, 20_480);
    assert_eq!(rooted.raw_matrix_sha256.len(), 64);
    assert_eq!(rooted.official_mdl_reports.len(), 4);
    assert!(
        rooted
            .limitations
            .iter()
            .any(|claim| claim.contains("No universal learner"))
    );
    assert_eq!(
        sha256_hex(&fs::read(checked_relative(&solution, &rooted.study_manifest_path)).unwrap()),
        rooted.study_manifest_sha256
    );

    let expected_names = ["mystery-A", "mystery-B", "mystery-C", "mystery-D"];
    let names: Vec<_> = manifest
        .instances
        .iter()
        .map(|instance| instance.instance.as_str())
        .collect();
    assert_eq!(names, expected_names);
    assert_eq!(
        names.iter().copied().collect::<HashSet<_>>().len(),
        expected_names.len()
    );

    let vendor = workspace_root().join("vendor/occam-circuit/datasets");
    let has_official_data = vendor.is_dir();
    for instance in &manifest.instances {
        let mdl_reference = &rooted.official_mdl_reports[&instance.instance];
        let mdl_source = fs::read(checked_relative(&solution, &mdl_reference.report_path)).unwrap();
        assert_eq!(sha256_hex(&mdl_source), mdl_reference.report_sha256);
        let mdl: MdlLearningReport = serde_json::from_slice(&mdl_source).unwrap();
        assert_eq!(mdl.schema_version, 2);
        assert_eq!(mdl.learner, "mdl-enumerator");
        assert_eq!(mdl.expression, mdl_reference.expression);
        assert_eq!(mdl.description_cost, mdl_reference.description_cost);
        assert_eq!(mdl.minimum_unique, mdl_reference.minimum_unique);
        assert_eq!(mdl.gate_count, mdl_reference.compiled_gate_count);
        assert_eq!(mdl.exhaustive_mismatches, 0);
        assert_eq!(mdl.commitment_matches, Some(true));
        assert_eq!(mdl.prediction_sha256, instance.prediction_sha256);

        let circuit_path = checked_relative(&solution, &instance.circuit_path);
        let prediction_path = checked_relative(&solution, &instance.prediction_path);
        let report_path = checked_relative(&solution, &instance.report_path);
        let circuit_source = fs::read_to_string(&circuit_path).unwrap();
        let prediction_source = fs::read_to_string(&prediction_path).unwrap();
        let report_source = fs::read_to_string(&report_path).unwrap();
        assert_eq!(
            sha256_hex(circuit_source.as_bytes()),
            instance.circuit_sha256,
            "{} circuit",
            instance.instance
        );
        assert_eq!(
            sha256_hex(prediction_source.as_bytes()),
            instance.prediction_sha256,
            "{} prediction",
            instance.instance
        );
        assert_eq!(
            sha256_hex(report_source.as_bytes()),
            instance.report_sha256,
            "{} report",
            instance.instance
        );
        assert_eq!(
            instance.prediction_sha256, instance.expected_commitment_sha256,
            "{} commitment",
            instance.instance
        );

        let report: LearningReport = serde_json::from_str(&report_source).unwrap();
        assert_eq!(report.schema_version, 1);
        assert_eq!(report.instance, instance.instance);
        assert_eq!(report.selected_family, instance.family);
        assert_eq!(report.gate_count, instance.gate_count);
        assert_eq!(report.circuit_sha256, instance.circuit_sha256);
        assert_eq!(report.prediction_sha256, instance.prediction_sha256);
        assert_eq!(report.commitment_matches, Some(true));
        assert_eq!(report.exhaustive_mismatches, 0);
        assert_eq!(report.training_scalar, report.training_packed);
        assert_eq!(
            report.training_scalar.exact_matches,
            report.training_scalar.samples
        );

        let circuit = parse_netlist(&circuit_source).unwrap();
        assert_eq!(circuit.gates.len(), instance.gate_count);
        let prediction = parse_dataset(&prediction_source).unwrap();
        let prediction_scalar = verify(&circuit, &prediction).unwrap();
        let prediction_packed =
            verify_prepacked(&circuit, &parse_packed_dataset(&prediction_source).unwrap()).unwrap();
        assert_eq!(prediction_scalar, prediction_packed);
        assert_eq!(prediction_scalar.samples, instance.prediction_rows);
        assert_eq!(
            prediction_scalar.exact_matches, prediction_scalar.samples,
            "{} predicted rows",
            instance.instance
        );

        if has_official_data {
            let official = vendor.join(&instance.instance);
            let training_source = fs::read_to_string(official.join("train.csv")).unwrap();
            let training_scalar =
                verify(&circuit, &parse_dataset(&training_source).unwrap()).unwrap();
            let training_packed =
                verify_prepacked(&circuit, &parse_packed_dataset(&training_source).unwrap())
                    .unwrap();
            assert_eq!(training_scalar, training_packed);
            assert_eq!(training_scalar, report.training_scalar);
            assert_eq!(training_scalar.samples, instance.training_rows);

            let official_inputs =
                parse_test_inputs(&fs::read_to_string(official.join("test_inputs.csv")).unwrap())
                    .unwrap();
            assert_eq!(official_inputs.rows.len(), prediction.samples.len());
            for (expected_input, predicted) in official_inputs.rows.iter().zip(&prediction.samples)
            {
                assert_eq!(expected_input, &predicted.input, "{}", instance.instance);
            }
            let expected_commitment =
                parse_commitment(&fs::read_to_string(official.join("commitment.sha256")).unwrap())
                    .unwrap();
            assert_eq!(expected_commitment, instance.prediction_sha256);
        }
        eprintln!(
            "{}: {} gates, {} training rows, {} predictions, {} exhaustive cases",
            instance.instance,
            instance.gate_count,
            instance.training_rows,
            instance.prediction_rows,
            report.exhaustive_cases
        );
    }
}
