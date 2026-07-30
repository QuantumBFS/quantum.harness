use assert_cmd::Command;
use learning_mit::circuit::SamplingMode;
use learning_mit::runner::{
    run_requested_tasks, run_simulation, ReserveReason, RuntimeDecision, RuntimePolicy,
};
use sha2::{Digest, Sha256};
use std::fs;
use std::path::Path;

#[test]
fn reserve_requires_a_predeclared_scientific_reason() {
    let policy = RuntimePolicy::production();
    assert_eq!(
        policy.decision(3_400, ReserveReason::None),
        RuntimeDecision::OrdinaryStop
    );
    assert_eq!(
        policy.decision(3_400, ReserveReason::LargestWidthIncomplete),
        RuntimeDecision::ReserveAllowed
    );
    assert_eq!(
        policy.decision(5_100, ReserveReason::LargestWidthIncomplete),
        RuntimeDecision::HardStop
    );
}

#[test]
fn production_simulation_requires_passing_oracles_first() {
    let run_dir = tempfile::tempdir().unwrap();
    let error = run_simulation(
        Path::new("configs/production.toml"),
        run_dir.path(),
        SamplingMode::Born,
    )
    .unwrap_err();
    assert!(error.to_string().contains("oracles"));
}

#[test]
fn simulation_resume_reuses_streams_and_rebuilds_identical_csv() {
    let run_dir = tempfile::tempdir().unwrap();
    let config = Path::new("configs/test.toml");
    let first = run_simulation(config, run_dir.path(), SamplingMode::Born).unwrap();
    assert_eq!(first.tasks.len(), 4);
    assert!(first
        .tasks
        .iter()
        .all(|task| task.state == learning_mit::schema::TaskState::Completed));

    let csv_path = run_dir.path().join("raw/blocks.csv");
    let before_csv = fs::read(&csv_path).unwrap();
    let stream_path = first
        .artifact_sha256
        .keys()
        .find(|path| path.starts_with("raw/streams/"))
        .unwrap();
    let before_stream = fs::read(run_dir.path().join(stream_path)).unwrap();

    let second = run_simulation(config, run_dir.path(), SamplingMode::Born).unwrap();
    assert_eq!(fs::read(csv_path).unwrap(), before_csv);
    assert_eq!(
        fs::read(run_dir.path().join(stream_path)).unwrap(),
        before_stream
    );
    assert_eq!(first.seeds, second.seeds);
}

#[test]
fn resume_rejects_a_corrupt_completed_stream() {
    let run_dir = tempfile::tempdir().unwrap();
    let config = Path::new("configs/test.toml");
    let manifest = run_simulation(config, run_dir.path(), SamplingMode::Born).unwrap();
    let stream_path = manifest
        .artifact_sha256
        .keys()
        .find(|path| path.starts_with("raw/streams/"))
        .unwrap();
    let absolute = run_dir.path().join(stream_path);
    let mut bytes = fs::read(&absolute).unwrap();
    bytes.push(b' ');
    fs::write(absolute, bytes).unwrap();

    let error = run_simulation(config, run_dir.path(), SamplingMode::Born).unwrap_err();
    assert!(error.to_string().contains("SHA-256"));
}

#[test]
fn refinement_request_requires_its_manifest_hash_and_runs_only_requested_tasks() {
    let run_dir = tempfile::tempdir().unwrap();
    let config = Path::new("configs/test.toml");
    run_simulation(config, run_dir.path(), SamplingMode::Born).unwrap();
    let processed = run_dir.path().join("processed");
    fs::create_dir_all(&processed).unwrap();
    let request_path = processed.join("refinement_request.json");
    let request = serde_json::json!({
        "schema_version": 1,
        "status": "bracketed",
        "stage": "diii-refine",
        "theta_pi": 0.45,
        "phi_pi": [0.18, 0.20, 0.22],
        "widths": [2, 4],
        "streams": 1,
        "burn_in_layers_per_width": 1,
        "measurement_layers_per_width": 2,
        "block_layers_per_width": 1
    });
    let bytes = serde_json::to_vec_pretty(&request).unwrap();
    fs::write(&request_path, &bytes).unwrap();

    let missing_hash = run_requested_tasks(config, run_dir.path(), &request_path).unwrap_err();
    assert!(missing_hash.to_string().contains("SHA-256"));

    let manifest_path = run_dir.path().join("manifest.json");
    let mut manifest: serde_json::Value =
        serde_json::from_slice(&fs::read(&manifest_path).unwrap()).unwrap();
    manifest["artifact_sha256"]["processed/refinement_request.json"] =
        serde_json::Value::String(format!("{:x}", Sha256::digest(&bytes)));
    fs::write(
        &manifest_path,
        serde_json::to_vec_pretty(&manifest).unwrap(),
    )
    .unwrap();

    let completed = run_requested_tasks(config, run_dir.path(), &request_path).unwrap();
    assert_eq!(completed.tasks.len(), 10);
    assert!(completed
        .tasks
        .iter()
        .filter(|task| task.key.starts_with("diii-refine"))
        .all(|task| task.state == learning_mit::schema::TaskState::Completed));
}

#[test]
fn remaining_runner_commands_write_their_declared_artifacts() {
    for (command, artifact) in [
        ("benchmark", "raw/benchmark.json"),
        ("negative-control", "raw/negative-control.json"),
    ] {
        let run_dir = tempfile::tempdir().unwrap();
        Command::cargo_bin("learning-mit")
            .unwrap()
            .args([
                command,
                "--config",
                "configs/test.toml",
                "--run-dir",
                run_dir.path().to_str().unwrap(),
            ])
            .assert()
            .success();
        assert!(run_dir.path().join(artifact).is_file());
    }
}
