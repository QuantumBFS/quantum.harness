mod common;

use common::{CircuitSource, load_manifest};

#[test]
fn manifest_is_versioned_unique_and_internally_consistent() {
    let manifest = load_manifest();
    assert_eq!(manifest.cases.len(), 3);
    assert!(
        manifest
            .cases
            .iter()
            .any(|case| { matches!(case.circuit, CircuitSource::OfficialFile { .. }) })
    );
    assert!(
        manifest
            .cases
            .iter()
            .any(|case| { matches!(case.circuit, CircuitSource::GeneratedAdder { .. }) })
    );
    assert!(
        manifest
            .cases
            .iter()
            .any(|case| { matches!(case.circuit, CircuitSource::GeneratedMultiplier { .. }) })
    );
}
