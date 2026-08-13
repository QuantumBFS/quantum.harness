use std::collections::HashSet;

use occam71_rust::{WindowConfig, extract_windows, parse_netlist};

#[test]
fn extracted_windows_are_convex_and_have_complete_boundaries() {
    let circuit = parse_netlist(include_str!("fixtures/window-shared.txt")).unwrap();
    let windows = extract_windows(
        &circuit,
        WindowConfig {
            min_gates: 4,
            max_gates: 8,
            max_inputs: 8,
            max_outputs: 4,
        },
    )
    .unwrap();

    assert!(!windows.is_empty());
    let mut identities = HashSet::new();
    for window in windows {
        assert!(window.is_convex(&circuit));
        assert!(window.boundary_inputs.len() <= 8);
        assert!(window.boundary_outputs.len() <= 4);
        assert_eq!(
            window.truth_table.samples.len(),
            1 << window.boundary_inputs.len()
        );
        assert_eq!(window.identity_sha256.len(), 64);
        assert!(identities.insert(window.identity_sha256));
    }
}

#[test]
fn window_extraction_is_byte_stable_and_rejects_bad_limits() {
    let circuit = parse_netlist(include_str!("fixtures/window-shared.txt")).unwrap();
    let config = WindowConfig::for_tests();
    assert_eq!(
        extract_windows(&circuit, config).unwrap(),
        extract_windows(&circuit, config).unwrap()
    );
    assert!(
        extract_windows(
            &circuit,
            WindowConfig {
                min_gates: 0,
                ..config
            }
        )
        .is_err()
    );
}
