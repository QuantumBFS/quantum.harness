#![no_main]

use libfuzzer_sys::fuzz_target;
use occam71_rust::{
    CompiledCircuit, parse_dataset, parse_netlist, parse_packed_dataset, verify,
    verify_compiled_prepacked, verify_prepacked_interpreted,
};

const SEPARATOR: &[u8] = b"\n---DATA---\n";

fuzz_target!(|data: &[u8]| {
    let Some(separator) = data
        .windows(SEPARATOR.len())
        .position(|window| window == SEPARATOR)
    else {
        return;
    };
    let circuit = std::str::from_utf8(&data[..separator]);
    let dataset = std::str::from_utf8(&data[separator + SEPARATOR.len()..]);
    let (Ok(circuit_source), Ok(dataset_source)) = (circuit, dataset) else {
        return;
    };
    let (Ok(circuit), Ok(dataset), Ok(packed)) = (
        parse_netlist(circuit_source),
        parse_dataset(dataset_source),
        parse_packed_dataset(dataset_source),
    ) else {
        return;
    };
    if circuit.input_count != dataset.input_width || circuit.outputs.len() != dataset.output_width {
        return;
    }
    let scalar = verify(&circuit, &dataset).unwrap();
    let interpreted = verify_prepacked_interpreted(&circuit, &packed).unwrap();
    let compiled = CompiledCircuit::new(&circuit).unwrap();
    let compiled = verify_compiled_prepacked(&compiled, &packed).unwrap();
    assert_eq!(scalar, interpreted);
    assert_eq!(scalar, compiled);
});
