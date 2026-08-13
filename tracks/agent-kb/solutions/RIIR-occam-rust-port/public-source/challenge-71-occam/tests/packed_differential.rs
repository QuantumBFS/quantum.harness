use occam71_rust::{
    Dataset, Sample, evaluate, pack_dataset, parse_netlist, verify, verify_packed,
    verify_prepacked_interpreted, verify_prepacked_reference,
};

struct SplitMix64(u64);

impl SplitMix64 {
    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9e3779b97f4a7c15);
        let mut value = self.0;
        value = (value ^ (value >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
        value = (value ^ (value >> 27)).wrapping_mul(0x94d049bb133111eb);
        value ^ (value >> 31)
    }

    fn index(&mut self, limit: usize) -> usize {
        (self.next() as usize) % limit
    }

    fn bit(&mut self) -> bool {
        self.next() & 1 != 0
    }
}

fn random_operand(rng: &mut SplitMix64, inputs: usize, wires: usize) -> String {
    let source = rng.index(inputs + wires);
    let name = if source < inputs {
        format!("x{}", source + 1)
    } else {
        format!("w{}", source - inputs + 1)
    };
    if rng.bit() { format!("~{name}") } else { name }
}

fn random_netlist(rng: &mut SplitMix64, inputs: usize, gates: usize, outputs: usize) -> String {
    const OPS: [&str; 6] = ["AND", "OR", "XOR", "NAND", "NOR", "XNOR"];
    let mut source = format!("INPUTS {inputs}\n");
    for wire in 0..gates {
        let lhs = random_operand(rng, inputs, wire);
        let rhs = random_operand(rng, inputs, wire);
        let op = OPS[rng.index(OPS.len())];
        source.push_str(&format!("w{} = {op} {lhs} {rhs}\n", wire + 1));
    }
    let output_names: Vec<_> = (0..outputs)
        .map(|_| random_operand(rng, inputs, gates))
        .collect();
    source.push_str(&format!("OUTPUTS {}\n", output_names.join(" ")));
    source
}

fn random_dataset(
    rng: &mut SplitMix64,
    circuit: &occam71_rust::Circuit,
    samples: usize,
) -> Dataset {
    let rows = (0..samples)
        .map(|sample_index| {
            let input: Vec<_> = (0..circuit.input_count).map(|_| rng.bit()).collect();
            let mut expected = evaluate(circuit, &input).unwrap();
            if sample_index % 7 == 0 {
                let bit = rng.index(expected.len());
                expected[bit] = !expected[bit];
            }
            Sample { input, expected }
        })
        .collect();
    Dataset {
        input_width: circuit.input_count,
        output_width: circuit.outputs.len(),
        samples: rows,
    }
}

#[test]
fn randomized_metrics_match_at_every_word_boundary() {
    let mut rng = SplitMix64(0x1150_0710_cafe_babe);
    for samples in [1, 63, 64, 65, 127, 128, 129] {
        for _case in 0..20 {
            let circuit = parse_netlist(&random_netlist(&mut rng, 4, 20, 3)).unwrap();
            let dataset = random_dataset(&mut rng, &circuit, samples);
            let packed = pack_dataset(&dataset).unwrap();
            let reference = verify_prepacked_reference(&circuit, &packed).unwrap();
            let flat = verify_prepacked_interpreted(&circuit, &packed).unwrap();
            assert_eq!(
                verify_packed(&circuit, &dataset).unwrap(),
                verify(&circuit, &dataset).unwrap(),
                "sample count {samples}"
            );
            assert_eq!(
                reference,
                verify(&circuit, &dataset).unwrap(),
                "reference sample count {samples}"
            );
            assert_eq!(
                flat,
                verify(&circuit, &dataset).unwrap(),
                "flat interpreted sample count {samples}"
            );
        }
    }
}
