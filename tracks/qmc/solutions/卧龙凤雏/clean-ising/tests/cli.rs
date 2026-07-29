use assert_cmd::cargo::cargo_bin_cmd;
use clean_ising::output::read_jsonl_prefix;
use predicates::str::contains;
use serde_json::Value;

#[test]
fn exact_cli_writes_parseable_records_and_manifest() {
    let dir = tempfile::tempdir().unwrap();
    let raw = dir.path().join("exact.jsonl");
    let manifest = dir.path().join("manifest.json");
    cargo_bin_cmd!("clean-ising")
        .args([
            "exact",
            "--config",
            "configs/test.toml",
            "--output",
            raw.to_str().unwrap(),
            "--manifest",
            manifest.to_str().unwrap(),
        ])
        .assert()
        .success();
    let lines = std::fs::read_to_string(raw).unwrap();
    assert_eq!(lines.lines().count(), 2);
    let value: Value = serde_json::from_str(&std::fs::read_to_string(manifest).unwrap()).unwrap();
    assert_eq!(value["schema_version"], 1);
    assert_eq!(value["config"]["production_gates"], false);
}

#[test]
fn complete_jsonl_prefix_survives_a_partial_final_record() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("partial.jsonl");
    std::fs::write(&path, "{\"value\":1}\n{\"value\":2}\n{\"value\":").unwrap();
    let (records, complete): (Vec<Value>, bool) = read_jsonl_prefix(&path).unwrap();
    assert_eq!(records.len(), 2);
    assert_eq!(records[0]["value"], 1);
    assert!(!complete);
}

#[test]
fn invalid_grid_interval_reports_the_broken_contract() {
    let dir = tempfile::tempdir().unwrap();
    let config = dir.path().join("invalid.toml");
    let text = std::fs::read_to_string("configs/test.toml")
        .unwrap()
        .replace("grid_intervals = 4", "grid_intervals = 6");
    std::fs::write(&config, text).unwrap();
    cargo_bin_cmd!("clean-ising")
        .args([
            "exact",
            "--config",
            config.to_str().unwrap(),
            "--output",
            dir.path().join("exact.jsonl").to_str().unwrap(),
            "--manifest",
            dir.path().join("manifest.json").to_str().unwrap(),
        ])
        .assert()
        .failure()
        .stderr(contains("divisible by four"));
}
