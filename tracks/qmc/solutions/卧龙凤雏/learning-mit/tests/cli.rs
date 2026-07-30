use assert_cmd::Command;
use predicates::str::contains;
use std::path::Path;

#[test]
fn command_help_exposes_the_complete_pipeline_surface() {
    Command::cargo_bin("learning-mit")
        .unwrap()
        .arg("--help")
        .assert()
        .success()
        .stdout(contains("oracles"))
        .stdout(contains("benchmark"))
        .stdout(contains("simulate"))
        .stdout(contains("negative-control"));
}

#[test]
fn repository_orchestration_files_declare_both_analysis_passes() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let script = std::fs::read_to_string(root.join("run.sh")).unwrap();
    assert!(script.contains("--phase-only"));
    assert!(script.contains("--task-request"));
    assert!(script.contains("--final"));
    assert!(root.join("Makefile").is_file());
    assert!(root.join("README.md").is_file());
}
