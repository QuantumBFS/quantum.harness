use std::{path::PathBuf, process::Command};

#[test]
fn standalone_submission_source_matches_production() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_owned();
    let output = Command::new(root.join("scripts/update-occam71-submission-snapshot"))
        .arg("--check")
        .current_dir(&root)
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );

    let manifest = root.join("challenge-71-occam/solutions/rewrite-it-in-rust/search/Cargo.toml");
    let output = Command::new("cargo")
        .args(["check", "--locked", "--manifest-path"])
        .arg(manifest)
        .current_dir(&root)
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
}
