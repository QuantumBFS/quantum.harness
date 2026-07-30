use std::{
    collections::{BTreeMap, HashSet},
    fs,
    path::{Component, Path, PathBuf},
};

use occam71_rust::{
    TrialRecord, TrialStatus, expected_trial_keys, load_experiment_config,
    official_and_synthetic_tasks, sha256_hex,
};
use serde::Deserialize;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct ResearchManifest {
    schema_version: u32,
    source_commit: String,
    trial_rows: usize,
    files: BTreeMap<String, String>,
    external: BTreeMap<String, String>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Aggregate {
    schema_version: u32,
    trial_rows: usize,
    group_rows: usize,
    correlations: Correlations,
    groups: Vec<Group>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Correlations {
    gate_count_vs_held_out_exact_spearman: f64,
    description_length_vs_gate_count_spearman: f64,
    paired_trials: usize,
}

#[derive(Debug, Deserialize)]
struct Group {
    expected_trials: usize,
    missing_trials: usize,
    statuses: BTreeMap<String, usize>,
    wilson95_low: f64,
    wilson95_high: f64,
}

fn workspace_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_owned()
}

fn research_root() -> PathBuf {
    workspace_root().join("experiments/occam-generalization")
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
fn committed_research_matrix_is_complete_and_hash_locked() {
    let root = research_root();
    let config = load_experiment_config(&root.join("config.json")).unwrap();
    let tasks = official_and_synthetic_tasks().unwrap();
    let task_ids = tasks.iter().map(|task| task.id.clone()).collect::<Vec<_>>();
    let expected = expected_trial_keys(&task_ids, &config)
        .unwrap()
        .into_iter()
        .collect::<HashSet<_>>();
    assert_eq!(expected.len(), 20_480);

    let raw = fs::read_to_string(root.join("raw.jsonl")).unwrap();
    let records = raw
        .lines()
        .map(|line| serde_json::from_str::<TrialRecord>(line).unwrap())
        .collect::<Vec<_>>();
    assert_eq!(records.len(), 20_480);
    let actual = records
        .iter()
        .map(|record| record.key.clone())
        .collect::<HashSet<_>>();
    assert_eq!(actual, expected);

    let config_hash = sha256_hex(&fs::read(root.join("config.json")).unwrap());
    for record in &records {
        assert_eq!(record.schema_version, 1);
        assert_eq!(record.config_sha256, config_hash);
        assert_eq!(
            record.observed_rows + record.held_out_rows,
            tasks
                .iter()
                .find(|task| task.id == record.key.task)
                .unwrap()
                .full_domain()
                .samples
                .len()
        );
        assert_eq!(record.runtime_micros, 0);
        assert_eq!(record.peak_rss_bytes, 0);
        match record.status {
            TrialStatus::Success => {
                let training = record.training.as_ref().unwrap();
                let held_out = record.held_out.as_ref().unwrap();
                let full_domain = record.full_domain.as_ref().unwrap();
                assert_eq!(training.samples, record.observed_rows);
                assert_eq!(training.exact_matches, training.samples);
                assert_eq!(held_out.samples, record.held_out_rows);
                assert_eq!(
                    full_domain.samples,
                    record.observed_rows + record.held_out_rows
                );
                assert_eq!(
                    record.semantic_recovery,
                    full_domain.exact_matches == full_domain.samples
                );
                assert!(record.hypothesis_sha256.is_some());
            }
            _ => {
                assert!(record.training.is_none());
                assert!(record.held_out.is_none());
                assert!(record.full_domain.is_none());
                assert!(!record.semantic_recovery);
            }
        }
    }

    let aggregate: Aggregate =
        serde_json::from_str(&fs::read_to_string(root.join("aggregate.json")).unwrap()).unwrap();
    assert_eq!(aggregate.schema_version, 1);
    assert_eq!(aggregate.trial_rows, records.len());
    assert_eq!(aggregate.group_rows, 1_024);
    assert_eq!(aggregate.groups.len(), aggregate.group_rows);
    assert_eq!(aggregate.correlations.paired_trials, 8_380);
    assert!(
        aggregate
            .correlations
            .gate_count_vs_held_out_exact_spearman
            .is_finite()
    );
    assert!(
        aggregate
            .correlations
            .description_length_vs_gate_count_spearman
            .is_finite()
    );
    for group in &aggregate.groups {
        assert_eq!(group.expected_trials, 20);
        assert_eq!(group.missing_trials, 0);
        assert_eq!(group.statuses.values().sum::<usize>(), 20);
        assert!((0.0..=1.0).contains(&group.wilson95_low));
        assert!((0.0..=1.0).contains(&group.wilson95_high));
        assert!(group.wilson95_low <= group.wilson95_high);
    }

    let report = fs::read_to_string(root.join("report.md")).unwrap();
    assert!(report.contains("20,480 trial records"));
    assert!(report.contains("conservative zero completion"));
    assert!(report.contains("must not be interpreted as performance measurements"));
    assert!(report.contains("not a universal learning law"));

    for figure in [
        "figures/gates-vs-accuracy.svg",
        "figures/fraction-vs-recovery.svg",
        "figures/description-vs-gates.svg",
    ] {
        let source = fs::read_to_string(root.join(figure)).unwrap();
        assert!(source.starts_with("<svg"));
        assert!(source.len() > 1_000, "{figure}");
    }

    let manifest: ResearchManifest =
        serde_json::from_str(&fs::read_to_string(root.join("manifest.json")).unwrap()).unwrap();
    assert_eq!(manifest.schema_version, 1);
    assert_eq!(manifest.source_commit.len(), 40);
    assert_eq!(manifest.trial_rows, records.len());
    assert_eq!(manifest.files.len(), 10);
    for (relative, expected_hash) in &manifest.files {
        assert_eq!(
            sha256_hex(&fs::read(checked_relative(&root, relative)).unwrap()),
            *expected_hash,
            "{relative}"
        );
    }
    assert_eq!(
        manifest.external["abc_lock_sha256"],
        sha256_hex(&fs::read(workspace_root().join("tools/abc/LOCK.json")).unwrap())
    );
    assert_eq!(
        manifest.external["optimization_report_sha256"],
        sha256_hex(
            &fs::read(
                PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                    .join("solutions/rewrite-it-in-rust/optimization/report.json")
            )
            .unwrap()
        )
    );
}
