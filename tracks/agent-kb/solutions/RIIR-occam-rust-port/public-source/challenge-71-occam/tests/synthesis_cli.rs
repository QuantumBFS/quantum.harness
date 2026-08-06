use std::{
    fs,
    path::{Path, PathBuf},
    process::Command,
};

fn fixture(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures")
        .join(name)
}

fn paths(case: &str) -> (PathBuf, PathBuf) {
    let prefix =
        std::env::temp_dir().join(format!("occam71-synthesis-{}-{case}", std::process::id()));
    (prefix.with_extension("txt"), prefix.with_extension("json"))
}

fn synthesize(
    dataset: &Path,
    max_gates: &str,
    timeout_seconds: &str,
    output: &Path,
    certificate: &Path,
) -> std::process::Output {
    Command::new(env!("CARGO_BIN_EXE_occam71_rust"))
        .args([
            "synthesize",
            "--dataset",
            dataset.to_str().unwrap(),
            "--max-gates",
            max_gates,
            "--timeout-seconds",
            timeout_seconds,
            "--output",
            output.to_str().unwrap(),
            "--certificate",
            certificate.to_str().unwrap(),
        ])
        .output()
        .unwrap()
}

fn cleanup(paths: &[&Path]) {
    for path in paths {
        if path.exists() {
            fs::remove_file(path).unwrap();
        }
    }
}

#[test]
fn writes_minimal_netlist_and_certificate() {
    let (netlist, certificate) = paths("sat");
    cleanup(&[&netlist, &certificate]);
    let output = synthesize(
        &fixture("half-adder.csv"),
        "2",
        "30",
        &netlist,
        &certificate,
    );
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(String::from_utf8_lossy(&output.stdout).contains("status:           sat"));
    assert!(fs::read_to_string(&netlist).unwrap().contains("OUTPUTS"));
    let json: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(&certificate).unwrap()).unwrap();
    assert_eq!(json["status"], "sat");
    assert_eq!(json["minimal_gate_count"], 2);
    cleanup(&[&netlist, &certificate]);
}

#[test]
fn distinguishes_incomplete_bound_and_timeout() {
    for (case, gates, timeout, status) in [
        ("bound", "1", "30", "no_circuit_within_bound"),
        ("timeout", "2", "0", "timeout"),
    ] {
        let (netlist, certificate) = paths(case);
        cleanup(&[&netlist, &certificate]);
        let output = synthesize(
            &fixture("half-adder.csv"),
            gates,
            timeout,
            &netlist,
            &certificate,
        );
        assert!(output.status.success(), "{case}");
        assert!(!netlist.exists(), "{case}");
        let json: serde_json::Value =
            serde_json::from_str(&fs::read_to_string(&certificate).unwrap()).unwrap();
        assert_eq!(json["status"], status, "{case}");
        cleanup(&[&netlist, &certificate]);
    }
}

#[test]
fn rejects_malformed_incomplete_dataset() {
    let malformed = std::env::temp_dir().join(format!(
        "occam71-synthesis-{}-malformed.csv",
        std::process::id()
    ));
    fs::write(&malformed, "input,output\n00,0\n01,1\n").unwrap();
    let (netlist, certificate) = paths("malformed");
    cleanup(&[&netlist, &certificate]);
    let output = synthesize(&malformed, "2", "30", &netlist, &certificate);
    assert!(!output.status.success());
    assert!(String::from_utf8_lossy(&output.stderr).contains("complete truth table"));
    assert!(!netlist.exists());
    assert!(!certificate.exists());
    cleanup(&[&malformed, &netlist, &certificate]);
}
