use occam71_rust::{
    ArithmeticOperation, CompiledCircuit, generate_dataset, parse_dataset, parse_netlist,
    parse_packed_dataset, ripple_carry_adder, shift_add_multiplier, verify,
    verify_compiled_prepacked, verify_prepacked, verify_prepacked_interpreted,
};

#[test]
fn compiled_matches_interpreted_and_scalar_across_boundaries() {
    for samples in [1, 63, 64, 65, 127, 128, 129, 1_000] {
        for (operation, bits, netlist) in [
            (ArithmeticOperation::Add, 8, ripple_carry_adder(8).unwrap()),
            (
                ArithmeticOperation::Multiply,
                4,
                shift_add_multiplier(4).unwrap(),
            ),
        ] {
            let source = generate_dataset(operation, bits, samples, 115 + samples as u64).unwrap();
            let circuit = parse_netlist(&netlist).unwrap();
            let scalar = parse_dataset(&source).unwrap();
            let packed = parse_packed_dataset(&source).unwrap();
            let compiled = CompiledCircuit::new(&circuit).unwrap();
            let scalar_metrics = verify(&circuit, &scalar).unwrap();
            assert_eq!(
                verify_prepacked_interpreted(&circuit, &packed).unwrap(),
                scalar_metrics
            );
            assert_eq!(
                verify_compiled_prepacked(&compiled, &packed).unwrap(),
                scalar_metrics
            );
            assert_eq!(verify_prepacked(&circuit, &packed).unwrap(), scalar_metrics);
        }
    }
}
