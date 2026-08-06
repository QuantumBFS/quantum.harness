use occam71_rust::{
    ResearchMethod, SemanticTrialRecord, TrialKey, TrialRecord, TrialStatus, VerificationMetrics,
    render_semantic_jsonl, semantic_projection,
};

fn fixture_record() -> TrialRecord {
    let metrics = VerificationMetrics {
        samples: 1,
        gate_count: 1,
        exact_matches: 1,
        correct_bits: 1,
        total_bits: 1,
    };
    TrialRecord {
        schema_version: 1,
        key: TrialKey {
            task: "xor".into(),
            fraction_basis_points: 500,
            seed: 0,
            method: ResearchMethod::Robdd,
        },
        config_sha256: "a".repeat(64),
        status: TrialStatus::Success,
        observed_rows: 1,
        held_out_rows: 1,
        training: Some(metrics.clone()),
        held_out: Some(metrics.clone()),
        full_domain: Some(metrics),
        semantic_recovery: true,
        expression: None,
        description_length: Some(1),
        gate_count: Some(1),
        minimum_unique: None,
        runtime_micros: 77,
        peak_rss_bytes: 8 * 1024 * 1024,
        host_identifier: "macos-aarch64-deadbeef".into(),
        process_id: 123,
        started_unix_micros: 456,
        hypothesis_sha256: Some("b".repeat(64)),
        detail: "test".into(),
    }
}

#[test]
fn measurements_change_without_changing_semantic_projection() {
    let first = fixture_record();
    let mut second = first.clone();
    second.runtime_micros += 77;
    second.peak_rss_bytes += 4096;
    second.host_identifier = "linux-x86_64-cafebabe".into();
    second.process_id += 1;
    second.started_unix_micros += 1;
    assert_eq!(semantic_projection(&first), semantic_projection(&second));
}

#[test]
fn projection_is_sorted_complete_and_excludes_only_measurement_identity() {
    let first = fixture_record();
    let mut second = first.clone();
    second.key.seed = 1;
    let jsonl = render_semantic_jsonl(&[second, first]).unwrap();
    assert!(!jsonl.contains("runtime_micros"));
    assert!(!jsonl.contains("peak_rss_bytes"));
    assert!(!jsonl.contains("host_identifier"));
    assert!(!jsonl.contains("process_id"));
    assert!(!jsonl.contains("started_unix_micros"));
    let rows = jsonl
        .lines()
        .map(|line| serde_json::from_str::<SemanticTrialRecord>(line).unwrap())
        .collect::<Vec<_>>();
    assert_eq!(rows.len(), 2);
    assert_eq!(rows[0].key.seed, 0);
    assert_eq!(rows[1].key.seed, 1);
    assert!(rows.iter().all(|row| row.schema_version == 2));
    assert!(rows.iter().all(|row| row.hypothesis_sha256.is_some()));
}
