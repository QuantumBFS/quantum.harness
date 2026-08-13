use occam71_rust::{
    Circuit, CompiledCircuit, Dataset, GateOp, Operand, Sample, Source, evaluate, pack_dataset,
    parse_dataset, parse_netlist, parse_packed_dataset, verify, verify_compiled_prepacked,
    verify_prepacked, verify_prepacked_interpreted,
};
use proptest::{
    collection::vec,
    prelude::*,
    test_runner::{FileFailurePersistence, RngSeed},
};

type GateSpec = (u8, u16, bool, u16, bool);
type OutputSpec = (u16, bool);
type CaseSpec = (usize, Vec<GateSpec>, Vec<OutputSpec>, usize, u64);

fn sample_count_strategy() -> impl Strategy<Value = usize> {
    prop_oneof![
        3 => Just(1),
        3 => Just(63),
        3 => Just(64),
        3 => Just(65),
        3 => Just(127),
        3 => Just(128),
        3 => Just(129),
        2 => 1usize..130,
    ]
}

fn case_strategy() -> impl Strategy<Value = CaseSpec> {
    (
        1usize..=8,
        vec(
            (
                0u8..6,
                any::<u16>(),
                any::<bool>(),
                any::<u16>(),
                any::<bool>(),
            ),
            0..=40,
        ),
        vec((any::<u16>(), any::<bool>()), 1..=6),
        sample_count_strategy(),
        any::<u64>(),
    )
}

fn operand_name(raw: u16, inverted: bool, inputs: usize, wires: usize) -> String {
    let index = usize::from(raw) % (inputs + wires);
    let name = if index < inputs {
        format!("x{}", index + 1)
    } else {
        format!("w{}", index - inputs + 1)
    };
    if inverted { format!("~{name}") } else { name }
}

fn netlist_from_spec(inputs: usize, gates: &[GateSpec], outputs: &[OutputSpec]) -> String {
    const OPS: [&str; 6] = ["AND", "OR", "XOR", "NAND", "NOR", "XNOR"];
    let mut source = format!("INPUTS {inputs}\n");
    for (gate_index, (operation, lhs, lhs_inverted, rhs, rhs_inverted)) in gates.iter().enumerate()
    {
        source.push_str(&format!(
            "w{} = {} {} {}\n",
            gate_index + 1,
            OPS[usize::from(*operation)],
            operand_name(*lhs, *lhs_inverted, inputs, gate_index),
            operand_name(*rhs, *rhs_inverted, inputs, gate_index),
        ));
    }
    let outputs = outputs
        .iter()
        .map(|(raw, inverted)| operand_name(*raw, *inverted, inputs, gates.len()))
        .collect::<Vec<_>>()
        .join(" ");
    source.push_str(&format!("OUTPUTS {outputs}\n"));
    source
}

fn operand_text(operand: Operand) -> String {
    let name = match operand.source {
        Source::Input(index) => format!("x{}", index + 1),
        Source::Wire(index) => format!("w{}", index + 1),
    };
    if operand.inverted {
        format!("~{name}")
    } else {
        name
    }
}

fn operation_text(operation: GateOp) -> &'static str {
    match operation {
        GateOp::And => "AND",
        GateOp::Or => "OR",
        GateOp::Xor => "XOR",
        GateOp::Nand => "NAND",
        GateOp::Nor => "NOR",
        GateOp::Xnor => "XNOR",
    }
}

fn format_circuit(circuit: &Circuit) -> String {
    let mut source = format!("INPUTS {}\n", circuit.input_count);
    for gate in &circuit.gates {
        source.push_str(&format!(
            "w{} = {} {} {}\n",
            gate.output + 1,
            operation_text(gate.op),
            operand_text(gate.lhs),
            operand_text(gate.rhs)
        ));
    }
    source.push_str(&format!(
        "OUTPUTS {}\n",
        circuit
            .outputs
            .iter()
            .copied()
            .map(operand_text)
            .collect::<Vec<_>>()
            .join(" ")
    ));
    source
}

fn splitmix64(state: &mut u64) -> u64 {
    *state = state.wrapping_add(0x9e3779b97f4a7c15);
    let mut value = *state;
    value = (value ^ (value >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94d049bb133111eb);
    value ^ (value >> 31)
}

fn dataset_for(circuit: &Circuit, samples: usize, mut seed: u64) -> Dataset {
    let samples = (0..samples)
        .map(|sample_index| {
            let input = (0..circuit.input_count)
                .map(|_| splitmix64(&mut seed) & 1 != 0)
                .collect::<Vec<_>>();
            let mut expected = evaluate(circuit, &input).unwrap();
            if (sample_index as u64).wrapping_add(seed).is_multiple_of(11) {
                let bit = (splitmix64(&mut seed) as usize) % expected.len();
                expected[bit] = !expected[bit];
            }
            Sample { input, expected }
        })
        .collect();
    Dataset {
        input_width: circuit.input_count,
        output_width: circuit.outputs.len(),
        samples,
    }
}

fn format_dataset(dataset: &Dataset) -> String {
    let mut source = String::from("input,output\n");
    for sample in &dataset.samples {
        for value in &sample.input {
            source.push(if *value { '1' } else { '0' });
        }
        source.push(',');
        for value in &sample.expected {
            source.push(if *value { '1' } else { '0' });
        }
        source.push('\n');
    }
    source
}

proptest! {
    #![proptest_config(ProptestConfig {
        cases: 1_000,
        failure_persistence: Some(Box::new(
            FileFailurePersistence::Direct(
                "challenge-71-occam/proptest-regressions/properties.txt"
            )
        )),
        rng_seed: RngSeed::Fixed(0x1150_0710_cafe_babe),
        ..ProptestConfig::default()
    })]

    #[test]
    fn all_backends_and_round_trips_agree(
        (inputs, gate_specs, output_specs, samples, seed) in case_strategy()
    ) {
        let source = netlist_from_spec(inputs, &gate_specs, &output_specs);
        let circuit = parse_netlist(&source).unwrap();
        let reparsed = parse_netlist(&format_circuit(&circuit)).unwrap();
        prop_assert_eq!(&reparsed, &circuit);

        let dataset = dataset_for(&circuit, samples, seed);
        let dataset_source = format_dataset(&dataset);
        let reparsed_dataset = parse_dataset(&dataset_source).unwrap();
        prop_assert_eq!(&reparsed_dataset, &dataset);

        let legacy_packed = pack_dataset(&dataset).unwrap();
        let direct_packed = parse_packed_dataset(&dataset_source).unwrap();
        prop_assert_eq!(&direct_packed, &legacy_packed);

        let scalar = verify(&circuit, &dataset).unwrap();
        let interpreted = verify_prepacked_interpreted(&circuit, &direct_packed).unwrap();
        let compiled = CompiledCircuit::new(&circuit).unwrap();
        let compiled_metrics = verify_compiled_prepacked(&compiled, &direct_packed).unwrap();
        let default_packed = verify_prepacked(&circuit, &direct_packed).unwrap();
        prop_assert_eq!(&interpreted, &scalar);
        prop_assert_eq!(&compiled_metrics, &scalar);
        prop_assert_eq!(&default_packed, &scalar);
    }
}
