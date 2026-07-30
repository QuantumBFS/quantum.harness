#![no_main]

use libfuzzer_sys::fuzz_target;
use occam71_rust::{CompiledCircuit, parse_netlist};

fuzz_target!(|data: &[u8]| {
    if let Ok(source) = std::str::from_utf8(data)
        && let Ok(circuit) = parse_netlist(source)
    {
        assert_eq!(circuit.wire_count, circuit.gates.len());
        assert!(circuit.input_count > 0);
        assert!(!circuit.outputs.is_empty());
        CompiledCircuit::new(&circuit).unwrap();
    }
});
