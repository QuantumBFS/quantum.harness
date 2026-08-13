use std::{fs, path::PathBuf, process::Command};

fn fixture(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures")
        .join(name)
}

#[test]
fn verifies_two_bit_adder_fixture() {
    for backend in ["scalar", "packed", "cross-check"] {
        let output = Command::new(env!("CARGO_BIN_EXE_occam71_rust"))
            .args([
                "verify",
                "--backend",
                backend,
                "--circuit",
                fixture("add-n2.txt").to_str().unwrap(),
                "--dataset",
                fixture("add-n2.csv").to_str().unwrap(),
            ])
            .output()
            .unwrap();
        assert!(output.status.success());
        let stdout = String::from_utf8(output.stdout).unwrap();
        assert!(stdout.contains(&format!("backend:          {backend}")));
        assert!(stdout.contains("gates:            7"));
        assert!(stdout.contains("samples:          16"));
        assert!(stdout.contains("exact-match acc:  1.000000"));
        assert!(stdout.contains("bit accuracy:     1.000000"));
    }
}

#[test]
fn reports_missing_file_with_context() {
    let output = Command::new(env!("CARGO_BIN_EXE_occam71_rust"))
        .args([
            "verify",
            "--circuit",
            "does-not-exist.txt",
            "--dataset",
            fixture("add-n2.csv").to_str().unwrap(),
        ])
        .output()
        .unwrap();
    assert!(!output.status.success());
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("does-not-exist.txt"));
}

#[test]
fn rejects_zero_width_generator_request() {
    let output = Command::new(env!("CARGO_BIN_EXE_occam71_rust"))
        .args(["generate-adder", "--bits", "0"])
        .output()
        .unwrap();
    assert!(!output.status.success());
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("--bits"));
}

#[test]
fn generates_dataset_accepted_by_both_backends() {
    let temporary = std::env::temp_dir().join(format!(
        "occam71-generated-{}-{}.csv",
        std::process::id(),
        std::thread::current().name().unwrap_or("cli")
    ));
    let generated = Command::new(env!("CARGO_BIN_EXE_occam71_rust"))
        .args([
            "generate-dataset",
            "--operation",
            "add",
            "--bits",
            "2",
            "--samples",
            "65",
            "--seed",
            "115",
            "--output",
            temporary.to_str().unwrap(),
        ])
        .output()
        .unwrap();
    assert!(generated.status.success());

    for backend in ["scalar", "packed"] {
        let verified = Command::new(env!("CARGO_BIN_EXE_occam71_rust"))
            .args([
                "verify",
                "--backend",
                backend,
                "--circuit",
                fixture("add-n2.txt").to_str().unwrap(),
                "--dataset",
                temporary.to_str().unwrap(),
            ])
            .output()
            .unwrap();
        assert!(verified.status.success(), "{backend}");
        assert!(
            String::from_utf8(verified.stdout)
                .unwrap()
                .contains("exact-match acc:  1.000000")
        );
    }
    fs::remove_file(temporary).unwrap();
}
