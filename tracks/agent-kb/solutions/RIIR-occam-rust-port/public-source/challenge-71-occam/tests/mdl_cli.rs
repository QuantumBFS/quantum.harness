use std::{
    fs,
    path::{Path, PathBuf},
    process::Command,
};

fn command() -> Command {
    Command::new(env!("CARGO_BIN_EXE_occam71_rust"))
}

fn temporary_root(case: &str) -> PathBuf {
    std::env::temp_dir().join(format!("occam71-mdl-cli-{}-{case}", std::process::id()))
}

fn bits(value: u64, width: usize) -> String {
    (0..width)
        .map(|bit| if value & (1u64 << bit) == 0 { '0' } else { '1' })
        .collect()
}

fn write_addition_fixture(root: &Path) {
    fs::create_dir_all(root).unwrap();
    let mut training = String::from("input,output\n");
    for x in 0..4 {
        for y in 0..4 {
            training.push_str(&bits(x, 2));
            training.push_str(&bits(y, 2));
            training.push(',');
            training.push_str(&bits(x + y, 3));
            training.push('\n');
        }
    }
    fs::write(root.join("train.csv"), training).unwrap();
    fs::write(root.join("test_inputs.csv"), "input\n0000\n1010\n1111\n").unwrap();
}

#[test]
fn learn_mdl_help_exposes_search_limits_and_outputs() {
    let output = command().args(["learn-mdl", "--help"]).output().unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let stdout = String::from_utf8(output.stdout).unwrap();
    for required in [
        "--train",
        "--test-inputs",
        "--commitment",
        "--max-description-cost",
        "--timeout-seconds",
        "--circuit",
        "--predictions",
        "--report",
    ] {
        assert!(stdout.contains(required), "{required}: {stdout}");
    }
}

#[test]
fn learn_mdl_writes_reparseable_verified_artifacts() {
    let root = temporary_root("success");
    if root.exists() {
        fs::remove_dir_all(&root).unwrap();
    }
    write_addition_fixture(&root);
    let circuit = root.join("out/circuit.txt");
    let predictions = root.join("out/test_outputs.csv");
    let report = root.join("out/report.json");
    let output = command()
        .args([
            "learn-mdl",
            "--train",
            root.join("train.csv").to_str().unwrap(),
            "--test-inputs",
            root.join("test_inputs.csv").to_str().unwrap(),
            "--max-description-cost",
            "4",
            "--timeout-seconds",
            "5",
            "--circuit",
            circuit.to_str().unwrap(),
            "--predictions",
            predictions.to_str().unwrap(),
            "--report",
            report.to_str().unwrap(),
        ])
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains("expression:        (x + y)"), "{stdout}");
    assert!(
        stdout.contains("commitment:       not supplied"),
        "{stdout}"
    );
    occam71_rust::parse_netlist(&fs::read_to_string(&circuit).unwrap()).unwrap();
    occam71_rust::parse_dataset(&fs::read_to_string(&predictions).unwrap()).unwrap();
    let report_value: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(&report).unwrap()).unwrap();
    assert_eq!(report_value["schema_version"], 2);
    assert_eq!(report_value["expression"], "(x + y)");
    assert_eq!(report_value["exhaustive_mismatches"], 0);
    fs::remove_dir_all(root).unwrap();
}

#[test]
fn learn_mdl_rejects_commitment_before_writing_final_artifacts() {
    let root = temporary_root("commitment");
    if root.exists() {
        fs::remove_dir_all(&root).unwrap();
    }
    write_addition_fixture(&root);
    fs::write(
        root.join("wrong.sha256"),
        "0000000000000000000000000000000000000000000000000000000000000000  test_outputs.csv\n",
    )
    .unwrap();
    let circuit = root.join("out/circuit.txt");
    let predictions = root.join("out/test_outputs.csv");
    let report = root.join("out/report.json");
    let output = command()
        .args([
            "learn-mdl",
            "--train",
            root.join("train.csv").to_str().unwrap(),
            "--test-inputs",
            root.join("test_inputs.csv").to_str().unwrap(),
            "--commitment",
            root.join("wrong.sha256").to_str().unwrap(),
            "--circuit",
            circuit.to_str().unwrap(),
            "--predictions",
            predictions.to_str().unwrap(),
            "--report",
            report.to_str().unwrap(),
        ])
        .output()
        .unwrap();
    assert!(!output.status.success());
    assert!(String::from_utf8_lossy(&output.stderr).contains("commitment mismatch"));
    assert!(!circuit.exists());
    assert!(!predictions.exists());
    assert!(!report.exists());
    fs::remove_dir_all(root).unwrap();
}
