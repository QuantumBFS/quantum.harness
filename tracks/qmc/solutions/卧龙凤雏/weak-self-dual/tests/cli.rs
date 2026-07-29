use assert_cmd::Command;
use predicates::prelude::*;
use std::fs;
use std::path::{Path, PathBuf};
use tempfile::TempDir;

struct TestRun {
    root: TempDir,
    config: PathBuf,
    raw: PathBuf,
    manifest: PathBuf,
}

impl TestRun {
    fn new() -> Self {
        let root = tempfile::tempdir().unwrap();
        let config = root.path().join("test.toml");
        fs::copy(
            Path::new(env!("CARGO_MANIFEST_DIR")).join("configs/test.toml"),
            &config,
        )
        .unwrap();
        Self {
            raw: root.path().join("raw"),
            manifest: root.path().join("manifest.json"),
            root,
            config,
        }
    }

    fn simulate(&self) -> Command {
        let mut command = Command::cargo_bin("weak-self-dual").unwrap();
        command
            .arg("simulate")
            .arg("--config")
            .arg(&self.config)
            .arg("--output-dir")
            .arg(&self.raw)
            .arg("--manifest")
            .arg(&self.manifest);
        command
    }

    fn oracles(&self) -> Command {
        let mut command = Command::cargo_bin("weak-self-dual").unwrap();
        command
            .arg("oracles")
            .arg("--config")
            .arg(&self.config)
            .arg("--output")
            .arg(self.root.path().join("oracles.json"))
            .arg("--manifest")
            .arg(&self.manifest);
        command
    }
}

#[test]
fn cli_writes_oracles_streams_csv_and_manifest() {
    let run = TestRun::new();
    run.oracles().assert().success();
    run.simulate().assert().success();
    assert!(run.root.path().join("oracles.json").exists());
    assert!(run.raw.join("streams/stream-L02-000.json").exists());
    assert!(run.raw.join("streams/stream-L04-000.json").exists());
    assert!(run.raw.join("blocks.csv").exists());
    assert!(run.manifest.exists());
}

#[test]
fn compatible_stream_artifacts_are_reused_byte_for_byte() {
    let run = TestRun::new();
    run.simulate().assert().success();
    let path = run.raw.join("streams/stream-L02-000.json");
    let before = fs::read(&path).unwrap();
    run.simulate()
        .assert()
        .success()
        .stderr(predicate::str::contains("reusing"));
    assert_eq!(before, fs::read(path).unwrap());
}

#[test]
fn incompatible_existing_stream_is_rejected() {
    let run = TestRun::new();
    run.simulate().assert().success();
    fs::write(
        run.raw.join("streams/stream-L02-000.json"),
        br#"{"schema_version":999}"#,
    )
    .unwrap();
    run.simulate()
        .assert()
        .failure()
        .stderr(predicate::str::contains("incompatible"));
}

#[test]
fn runner_rejects_a_missing_configuration_before_creating_output() {
    let mut command = Command::new("bash");
    command
        .arg(Path::new(env!("CARGO_MANIFEST_DIR")).join("run.sh"))
        .arg("configs/does-not-exist.toml");
    command
        .assert()
        .failure()
        .code(2)
        .stderr(predicate::str::contains("configuration not found"));
}
