use std::time::Duration;

use occam71_rust::{
    DEFAULT_LIMITS, PeepholeConfig, WindowConfig, compare_circuits_exhaustively, extract_windows,
    optimize_peepholes, parse_netlist, rewrite_with_candidate,
};

#[test]
fn peephole_replaces_a_known_redundant_window() {
    let original = parse_netlist(include_str!("fixtures/redundant-xor.txt")).unwrap();
    let result =
        optimize_peepholes(&original, &PeepholeConfig::for_tests(), &DEFAULT_LIMITS).unwrap();

    assert!(result.circuit.gates.len() < original.gates.len());
    assert_eq!(result.report.whole_circuit_mismatches, 0);
    assert!(result.report.accepted_replacements >= 1);
    assert_eq!(
        compare_circuits_exhaustively(&original, &result.circuit, 20, &DEFAULT_LIMITS)
            .unwrap()
            .1,
        0
    );
}

#[test]
fn peephole_timeout_is_typed_and_report_bytes_are_stable() {
    let original = parse_netlist(include_str!("fixtures/redundant-xor.txt")).unwrap();
    let config = PeepholeConfig {
        per_window_timeout: Duration::ZERO,
        global_timeout: Duration::from_secs(1),
        ..PeepholeConfig::for_tests()
    };
    let first = optimize_peepholes(&original, &config, &DEFAULT_LIMITS).unwrap();
    let second = optimize_peepholes(&original, &config, &DEFAULT_LIMITS).unwrap();

    assert_eq!(first.circuit, original);
    assert_eq!(first, second);
    assert!(
        first
            .report
            .attempts
            .iter()
            .all(|attempt| !attempt.accepted)
    );
    assert_eq!(
        first.report.to_json_pretty().unwrap(),
        second.report.to_json_pretty().unwrap()
    );
}

#[test]
fn rewrite_rejects_bad_shapes_and_equivalence_check_catches_bad_logic() {
    let original = parse_netlist(include_str!("fixtures/redundant-xor.txt")).unwrap();
    let window = extract_windows(
        &original,
        WindowConfig {
            min_gates: 5,
            max_gates: 5,
            max_inputs: 4,
            max_outputs: 2,
        },
    )
    .unwrap()
    .into_iter()
    .find(|window| window.gate_indices.len() == 5)
    .unwrap();

    let wrong_inputs = parse_netlist("INPUTS 1\nOUTPUTS x1\n").unwrap();
    assert!(rewrite_with_candidate(&original, &window, &wrong_inputs, &DEFAULT_LIMITS).is_err());
    let extra_output = parse_netlist("INPUTS 2\nOUTPUTS x1 x2\n").unwrap();
    assert!(rewrite_with_candidate(&original, &window, &extra_output, &DEFAULT_LIMITS).is_err());

    let inequivalent = parse_netlist("INPUTS 2\nw1 = AND x1 x2\nOUTPUTS w1\n").unwrap();
    let (rewritten, _) =
        rewrite_with_candidate(&original, &window, &inequivalent, &DEFAULT_LIMITS).unwrap();
    assert!(
        compare_circuits_exhaustively(&original, &rewritten, 20, &DEFAULT_LIMITS)
            .unwrap()
            .1
            > 0
    );

    let (non_improving, _) =
        rewrite_with_candidate(&original, &window, &original, &DEFAULT_LIMITS).unwrap();
    assert!(non_improving.gates.len() >= original.gates.len());
}
