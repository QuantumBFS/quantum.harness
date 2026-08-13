use std::{fs, path::PathBuf, process::Command};

fn workspace_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("crate is a workspace member")
        .to_owned()
}

#[test]
fn package_cli_locks_and_snapshot_are_v050() {
    assert_eq!(env!("CARGO_PKG_VERSION"), "0.5.0");
    let output = Command::new(env!("CARGO_BIN_EXE_occam71_rust"))
        .arg("--version")
        .output()
        .expect("run occam71_rust --version");
    assert!(output.status.success());
    assert_eq!(
        String::from_utf8(output.stdout).unwrap().trim(),
        "occam71-rust 0.5.0"
    );

    let root = workspace_root();
    for relative in [
        "Cargo.lock",
        "fuzz/Cargo.lock",
        "challenge-71-occam/solutions/rewrite-it-in-rust/search/Cargo.toml",
        "challenge-71-occam/solutions/rewrite-it-in-rust/search/Cargo.lock",
    ] {
        let source = fs::read_to_string(root.join(relative)).unwrap();
        assert!(
            source.contains("version = \"0.5.0\""),
            "{relative} does not contain 0.5.0"
        );
    }
}
