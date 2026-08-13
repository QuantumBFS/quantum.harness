use std::{
    fs,
    path::{Path, PathBuf},
    process::{Command, Output},
};

fn workspace_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_owned()
}

fn official_case(name: &str) -> PathBuf {
    workspace_root()
        .join("vendor/occam-circuit/datasets")
        .join(name)
}

fn temporary_root(case: &str) -> PathBuf {
    std::env::temp_dir().join(format!(
        "occam71-learning-cli-{}-{case}",
        std::process::id()
    ))
}

fn clean(path: &Path) {
    if path.exists() {
        fs::remove_dir_all(path).unwrap();
    }
}

fn run_learn(instance: &str, case_root: &Path, commitment: &Path, output_root: &Path) -> Output {
    Command::new(env!("CARGO_BIN_EXE_occam71_rust"))
        .args([
            "learn",
            "--instance",
            instance,
            "--train",
            case_root.join("train.csv").to_str().unwrap(),
            "--test-inputs",
            case_root.join("test_inputs.csv").to_str().unwrap(),
            "--commitment",
            commitment.to_str().unwrap(),
            "--output-dir",
            output_root.to_str().unwrap(),
        ])
        .output()
        .unwrap()
}

#[test]
fn learn_help_lists_required_paths() {
    let output = Command::new(env!("CARGO_BIN_EXE_occam71_rust"))
        .args(["learn", "--help"])
        .output()
        .unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    for flag in [
        "--instance",
        "--train",
        "--test-inputs",
        "--commitment",
        "--output-dir",
    ] {
        assert!(stdout.contains(flag), "missing {flag}");
    }
}

#[test]
fn learn_writes_a_reparseable_official_solution() {
    let case_root = official_case("mystery-A");
    if !case_root.is_dir() {
        eprintln!("official data absent; run ./scripts/fetch-occam-data.sh");
        return;
    }
    let output_root = temporary_root("success");
    clean(&output_root);
    let output = run_learn(
        "mystery-A",
        &case_root,
        &case_root.join("commitment.sha256"),
        &output_root,
    );
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains("selected family:  add"));
    assert!(stdout.contains("commitment:       match"));
    let circuit = output_root.join("circuits/mystery-A.txt");
    let prediction = output_root.join("predictions/mystery-A/test_outputs.csv");
    let report = output_root.join("reports/mystery-A.json");
    assert!(circuit.is_file());
    assert!(prediction.is_file());
    assert!(report.is_file());
    occam71_rust::parse_netlist(&fs::read_to_string(circuit).unwrap()).unwrap();
    occam71_rust::parse_dataset(&fs::read_to_string(prediction).unwrap()).unwrap();
    clean(&output_root);
}

#[test]
fn learn_rejects_wrong_commitment_without_final_artifacts() {
    let case_root = official_case("mystery-B");
    if !case_root.is_dir() {
        eprintln!("official data absent; run ./scripts/fetch-occam-data.sh");
        return;
    }
    let output_root = temporary_root("wrong");
    clean(&output_root);
    fs::create_dir_all(&output_root).unwrap();
    let wrong = output_root.join("wrong.sha256");
    fs::write(
        &wrong,
        "0000000000000000000000000000000000000000000000000000000000000000  test_outputs.csv\n",
    )
    .unwrap();
    let output = run_learn("mystery-B", &case_root, &wrong, &output_root);
    assert!(!output.status.success());
    assert!(String::from_utf8_lossy(&output.stderr).contains("commitment mismatch"));
    assert!(!output_root.join("circuits/mystery-B.txt").exists());
    assert!(
        !output_root
            .join("predictions/mystery-B/test_outputs.csv")
            .exists()
    );
    assert!(!output_root.join("reports/mystery-B.json").exists());
    clean(&output_root);
}

#[test]
fn write_manifest_requires_all_four_validated_instances() {
    let output_root = temporary_root("manifest-incomplete");
    clean(&output_root);
    fs::create_dir_all(&output_root).unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_occam71_rust"))
        .args([
            "write-manifest",
            "--output-dir",
            output_root.to_str().unwrap(),
        ])
        .output()
        .unwrap();
    assert!(!output.status.success());
    assert!(String::from_utf8_lossy(&output.stderr).contains("mystery-A"));
    assert!(!output_root.join("manifest.json").exists());
    clean(&output_root);
}
