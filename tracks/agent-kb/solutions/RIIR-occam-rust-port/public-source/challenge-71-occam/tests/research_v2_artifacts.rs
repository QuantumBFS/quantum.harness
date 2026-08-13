use std::{
    collections::{BTreeMap, HashSet},
    fs,
    path::{Component, Path, PathBuf},
};

use occam71_rust::{
    SEMANTIC_PROJECTION_EXCLUDED_FIELDS, SemanticTrialRecord, TrialRecord, TrialStatus,
    expected_trial_keys, load_experiment_config, official_and_synthetic_tasks, semantic_projection,
    sha256_hex,
};
use serde::Deserialize;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Manifest {
    schema_version: u32,
    source_commit: String,
    trial_rows: usize,
    files: BTreeMap<String, String>,
    projection: Projection,
    external: BTreeMap<String, String>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Projection {
    schema_version: u32,
    excluded_fields: Vec<String>,
}

fn workspace_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_owned()
}

fn research_root() -> PathBuf {
    workspace_root().join("experiments/occam-generalization-v2")
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

#[test]
fn measured_and_semantic_v2_evidence_is_complete_linked_and_nonzero() {
    let root = research_root();
    let config = load_experiment_config(&root.join("config.json")).unwrap();
    let tasks = official_and_synthetic_tasks().unwrap();
    let task_ids = tasks.iter().map(|task| task.id.clone()).collect::<Vec<_>>();
    let expected = expected_trial_keys(&task_ids, &config)
        .unwrap()
        .into_iter()
        .collect::<HashSet<_>>();
    assert_eq!(expected.len(), 20_480);

    let measured = fs::read_to_string(root.join("raw-measured.jsonl"))
        .unwrap()
        .lines()
        .map(|line| serde_json::from_str::<TrialRecord>(line).unwrap())
        .collect::<Vec<_>>();
    let semantic = fs::read_to_string(root.join("semantic.jsonl"))
        .unwrap()
        .lines()
        .map(|line| serde_json::from_str::<SemanticTrialRecord>(line).unwrap())
        .collect::<Vec<_>>();
    assert_eq!(measured.len(), expected.len());
    assert_eq!(semantic.len(), expected.len());

    let measured_by_key = measured
        .iter()
        .map(|record| (record.key.clone(), record))
        .collect::<BTreeMap<_, _>>();
    let semantic_by_key = semantic
        .iter()
        .map(|record| (record.key.clone(), record))
        .collect::<BTreeMap<_, _>>();
    assert_eq!(
        measured_by_key.keys().cloned().collect::<HashSet<_>>(),
        expected
    );
    assert_eq!(
        semantic_by_key.keys().cloned().collect::<HashSet<_>>(),
        expected
    );
    for (key, measured) in &measured_by_key {
        assert!(measured.runtime_micros > 0, "{key:?}");
        assert!(measured.peak_rss_bytes > 0, "{key:?}");
        assert!(!measured.host_identifier.is_empty(), "{key:?}");
        assert!(measured.process_id > 0, "{key:?}");
        assert!(measured.started_unix_micros > 0, "{key:?}");
        assert_ne!(measured.status, TrialStatus::Timeout, "{key:?}");
        assert_eq!(
            semantic_by_key[key],
            &semantic_projection(measured),
            "{key:?}"
        );
    }

    let aggregate: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(root.join("aggregate.json")).unwrap()).unwrap();
    assert_eq!(aggregate["schema_version"], 2);
    assert_eq!(aggregate["trial_rows"], 20_480);
    assert_eq!(aggregate["group_rows"], 1_024);
    let groups = aggregate["groups"].as_array().unwrap();
    assert_eq!(groups.len(), 1_024);
    for group in groups {
        assert_eq!(group["missing_trials"], 0);
        if group["statuses"]["success"].as_u64().unwrap() > 0 {
            assert!(group["median_runtime_micros"].as_f64().unwrap() > 0.0);
            assert!(group["median_peak_rss_bytes"].as_f64().unwrap() > 0.0);
        }
    }

    let report = fs::read_to_string(root.join("report.md")).unwrap();
    assert!(report.contains("distinct learner implementations"));
    assert!(report.contains("positive measurements"));
    assert!(!report.contains("normalized to zero"));

    let manifest: Manifest =
        serde_json::from_str(&fs::read_to_string(root.join("manifest.json")).unwrap()).unwrap();
    assert_eq!(manifest.schema_version, 2);
    assert_eq!(manifest.source_commit.len(), 40);
    assert_eq!(manifest.trial_rows, 20_480);
    assert_eq!(manifest.projection.schema_version, 2);
    assert_eq!(
        manifest.projection.excluded_fields,
        SEMANTIC_PROJECTION_EXCLUDED_FIELDS.map(str::to_owned)
    );
    for (relative, expected_hash) in &manifest.files {
        assert_eq!(
            sha256_hex(&fs::read(checked_relative(&root, relative)).unwrap()),
            *expected_hash,
            "{relative}"
        );
    }
    assert_eq!(
        manifest.external["independent_tool_audit_sha256"],
        sha256_hex(&fs::read(root.join("tool-audit.json")).unwrap())
    );
}
