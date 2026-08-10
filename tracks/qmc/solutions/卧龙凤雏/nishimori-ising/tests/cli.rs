use assert_cmd::cargo::cargo_bin_cmd;
use nishimori_ising::schema::{RunManifest, SCHEMA_VERSION};
use predicates::str::contains;

fn tiny_config(directory: &std::path::Path) -> std::path::PathBuf {
    let path = directory.join("tiny.toml");
    let text = std::fs::read_to_string("configs/test.toml")
        .unwrap()
        .replace("widths = [4, 6, 8, 10, 12, 14]", "widths = [4]")
        .replace("replicas = 8", "replicas = 1")
        .replace("burn_in_rows = 32", "burn_in_rows = 4")
        .replace("measurement_rows = 64", "measurement_rows = 8")
        .replace("block_rows = 16", "block_rows = 4")
        .replace("identity_rows = 128", "identity_rows = 16");
    std::fs::write(&path, text).unwrap();
    path
}

#[test]
fn cli_writes_oracles_resumable_replica_and_manifest() {
    let directory = tempfile::tempdir().unwrap();
    let config = tiny_config(directory.path());
    let raw = directory.path().join("raw");
    let replicas = raw.join("replicas");
    let oracles = raw.join("oracles.json");
    let manifest = directory.path().join("manifest.json");

    cargo_bin_cmd!("nishimori-ising")
        .args([
            "oracles",
            "--config",
            config.to_str().unwrap(),
            "--output",
            oracles.to_str().unwrap(),
            "--manifest",
            manifest.to_str().unwrap(),
        ])
        .assert()
        .success();
    cargo_bin_cmd!("nishimori-ising")
        .args([
            "simulate",
            "--config",
            config.to_str().unwrap(),
            "--output-dir",
            replicas.to_str().unwrap(),
            "--manifest",
            manifest.to_str().unwrap(),
        ])
        .assert()
        .success();

    let parsed: RunManifest =
        serde_json::from_str(&std::fs::read_to_string(&manifest).unwrap()).unwrap();
    assert_eq!(parsed.schema_version, SCHEMA_VERSION);
    assert_eq!(parsed.completed_replicas, vec![0]);
    assert!(parsed.artifact_sha256.contains_key("oracles"));
    assert!(parsed.artifact_sha256.contains_key("replica-000"));

    let replica_path = replicas.join("replica-000.json");
    let before = std::fs::read(&replica_path).unwrap();
    cargo_bin_cmd!("nishimori-ising")
        .args([
            "simulate",
            "--config",
            config.to_str().unwrap(),
            "--output-dir",
            replicas.to_str().unwrap(),
            "--manifest",
            manifest.to_str().unwrap(),
        ])
        .assert()
        .success()
        .stderr(contains("reusing replica 0"));
    assert_eq!(before, std::fs::read(replica_path).unwrap());
}

#[test]
fn malformed_existing_replica_is_rejected_instead_of_overwritten() {
    let directory = tempfile::tempdir().unwrap();
    let config = tiny_config(directory.path());
    let replicas = directory.path().join("replicas");
    std::fs::create_dir_all(&replicas).unwrap();
    std::fs::write(replicas.join("replica-000.json"), "{}\n").unwrap();

    cargo_bin_cmd!("nishimori-ising")
        .args([
            "simulate",
            "--config",
            config.to_str().unwrap(),
            "--output-dir",
            replicas.to_str().unwrap(),
            "--manifest",
            directory.path().join("manifest.json").to_str().unwrap(),
        ])
        .assert()
        .failure()
        .stderr(contains("failed to parse JSON"));
}
