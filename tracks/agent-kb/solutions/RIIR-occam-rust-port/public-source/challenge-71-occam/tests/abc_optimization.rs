use std::{fs, path::PathBuf, process::Command};

use occam71_rust::{AbcOptimizationConfig, DEFAULT_LIMITS, optimize_with_abc, parse_netlist};

fn workspace_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_owned()
}

fn abc_binary_or_skip() -> Option<PathBuf> {
    let commit = "e76768b9d34f9dc67cb6608efecd55db271ff849";
    let path = workspace_root().join(format!("target/tools/abc/{commit}/abc"));
    path.is_file().then_some(path)
}

#[test]
fn abc_portfolio_returns_only_equivalent_official_candidates() {
    let Some(abc) = abc_binary_or_skip() else {
        eprintln!("pinned ABC absent; run ./scripts/fetch-abc.sh");
        return;
    };
    let original = parse_netlist(include_str!("fixtures/add-n2.txt")).unwrap();
    let result = optimize_with_abc(
        &original,
        &abc,
        &AbcOptimizationConfig::for_tests(),
        &DEFAULT_LIMITS,
    )
    .unwrap();

    assert!(!result.report.flows.is_empty());
    assert!(result.report.flows.iter().any(|flow| flow.accepted));
    for flow in result.report.flows.iter().filter(|flow| flow.accepted) {
        assert!(flow.abc_cec_equivalent);
        assert_eq!(flow.rust_exhaustive_mismatches, Some(0));
        assert!(flow.official_gate_count.is_some());
    }
    for candidate in &result.candidates {
        let reparsed = parse_netlist(&candidate.netlist).unwrap();
        assert_eq!(reparsed.gates.len(), candidate.official_gate_count);
        assert_eq!(candidate.rust_exhaustive_mismatches, 0);
    }
}

#[test]
fn abc_portfolio_reports_are_stable_for_a_fixed_flow() {
    let Some(abc) = abc_binary_or_skip() else {
        return;
    };
    let original = parse_netlist(include_str!("fixtures/add-n2.txt")).unwrap();
    let config = AbcOptimizationConfig::for_tests();
    let first = optimize_with_abc(&original, &abc, &config, &DEFAULT_LIMITS).unwrap();
    let second = optimize_with_abc(&original, &abc, &config, &DEFAULT_LIMITS).unwrap();

    assert_eq!(
        first.report.to_json_pretty().unwrap(),
        second.report.to_json_pretty().unwrap()
    );
}

#[test]
fn abc_only_cli_writes_a_report_and_never_worsens_the_input() {
    let Some(abc) = abc_binary_or_skip() else {
        return;
    };
    let temporary = std::env::temp_dir().join(format!("occam71-abc-cli-{}", std::process::id()));
    if temporary.exists() {
        fs::remove_dir_all(&temporary).unwrap();
    }
    fs::create_dir_all(&temporary).unwrap();
    let circuit = temporary.join("input.txt");
    let output = temporary.join("output.txt");
    let report = temporary.join("report.json");
    fs::write(&circuit, include_str!("fixtures/add-n2.txt")).unwrap();
    let result = Command::new(env!("CARGO_BIN_EXE_occam71_rust"))
        .args([
            "optimize-circuit",
            "--circuit",
            circuit.to_str().unwrap(),
            "--abc",
            abc.to_str().unwrap(),
            "--output",
            output.to_str().unwrap(),
            "--report",
            report.to_str().unwrap(),
            "--abc-only",
        ])
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );
    assert!(report.is_file());
    let stdout = String::from_utf8(result.stdout).unwrap();
    assert!(stdout.contains("status:"), "{stdout}");
    assert!(stdout.contains("baseline gates:"), "{stdout}");
    assert!(stdout.contains("candidate gates:"), "{stdout}");
    assert!(stdout.contains("flow:"), "{stdout}");
    assert!(stdout.contains("report:"), "{stdout}");
    if output.is_file() {
        let original = parse_netlist(include_str!("fixtures/add-n2.txt")).unwrap();
        let candidate = parse_netlist(&fs::read_to_string(output).unwrap()).unwrap();
        assert!(candidate.gates.len() < original.gates.len());
    }
    fs::remove_dir_all(temporary).unwrap();
}
