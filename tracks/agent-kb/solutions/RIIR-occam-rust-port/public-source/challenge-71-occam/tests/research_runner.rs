use std::{fs, path::PathBuf, process::Command};

use occam71_rust::{
    ResearchMethod, ResearchTools, TrialBudget, TrialKey, TrialRecord, TrialStatus,
    official_and_synthetic_tasks, peak_rss_bytes, run_trial_with_tools, split_task,
};

fn workspace_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_owned()
}

#[test]
fn peak_rss_is_positive_and_byte_normalized() {
    let bytes = peak_rss_bytes().unwrap();
    assert!(bytes > 1024 * 1024, "{bytes}");
}

#[test]
fn isolated_trial_writes_real_measurements_atomically() {
    let root = workspace_root();
    let temporary =
        std::env::temp_dir().join(format!("occam71-measured-trial-{}", std::process::id()));
    if temporary.exists() {
        fs::remove_dir_all(&temporary).unwrap();
    }
    fs::create_dir_all(&temporary).unwrap();
    let output = temporary.join("trial.json");
    let key =
        r#"{"task":"mystery-A","fraction_basis_points":500,"seed":0,"method":"oracle-expression"}"#;
    let result = Command::new(env!("CARGO_BIN_EXE_occam71_rust"))
        .args([
            "experiment-trial",
            "--config",
            root.join("experiments/occam-generalization/config.json")
                .to_str()
                .unwrap(),
            "--tasks",
            root.join("experiments/occam-generalization/tasks.json")
                .to_str()
                .unwrap(),
            "--key-json",
            key,
            "--output",
            output.to_str().unwrap(),
        ])
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );
    let record: TrialRecord = serde_json::from_slice(&fs::read(&output).unwrap()).unwrap();
    assert!(record.runtime_micros > 0);
    assert!(record.peak_rss_bytes > 1024 * 1024);
    assert!(record.process_id > 0);
    assert!(!record.host_identifier.is_empty());
    assert!(record.started_unix_micros > 0);
    assert!(!temporary.read_dir().unwrap().any(|entry| {
        entry
            .unwrap()
            .file_name()
            .to_string_lossy()
            .contains(".tmp")
    }));
    fs::remove_dir_all(temporary).unwrap();
}

#[test]
fn evaluator_resource_limits_remain_typed_trial_rows() {
    let tasks = official_and_synthetic_tasks().unwrap();
    let task = tasks.iter().find(|task| task.id == "mystery-A").unwrap();
    let split = split_task(task, 0.40, 0, 8_147_115).unwrap();
    let record = run_trial_with_tools(
        task,
        &split,
        TrialKey {
            task: task.id.clone(),
            fraction_basis_points: 40_000,
            seed: 0,
            method: ResearchMethod::Memorization,
        },
        &"a".repeat(64),
        ResearchTools::default(),
        TrialBudget::default(),
    )
    .unwrap();
    assert_eq!(record.status, TrialStatus::ResourceLimit);
    assert!(record.detail.contains("compiled value words"));
}
