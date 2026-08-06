use std::{path::PathBuf, process::Command};

#[test]
fn generated_evidence_reports_are_current() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("crate is a workspace member")
        .to_owned();
    for (script, arguments) in [
        ("render-oracle-report", vec!["--check"]),
        (
            "render-benchmark-report",
            vec!["--check", "--profile", "apple-m4"],
        ),
        (
            "render-ingestion-report",
            vec![
                "--check",
                "--results",
                "benchmarks/experiments/2026-07-28-direct-ingestion-apple-m4",
                "--output",
                "benchmarks/experiments/2026-07-28-direct-ingestion-apple-m4/report.md",
            ],
        ),
        (
            "render-occam-research",
            vec![
                "--raw",
                "experiments/occam-generalization/raw.jsonl",
                "--output",
                "experiments/occam-generalization",
                "--check",
            ],
        ),
        ("root-occam-research-evidence", vec!["--check"]),
    ] {
        let output = Command::new(root.join("scripts").join(script))
            .args(arguments)
            .current_dir(&root)
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{script} failed:\n{}{}",
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        );
    }
}
