use crate::{Circuit, DEFAULT_LIMITS, OccamError, Operand, ResourceLimits, Source};

pub fn evaluate(circuit: &Circuit, input: &[bool]) -> Result<Vec<bool>, OccamError> {
    evaluate_with_limits(circuit, input, &DEFAULT_LIMITS)
}

pub fn evaluate_with_limits(
    circuit: &Circuit,
    input: &[bool],
    limits: &ResourceLimits,
) -> Result<Vec<bool>, OccamError> {
    if input.len() != circuit.input_count {
        return Err(OccamError::Validation(format!(
            "input width {} does not match circuit INPUTS {}",
            input.len(),
            circuit.input_count
        )));
    }
    if circuit.wire_count != circuit.gates.len() {
        return Err(OccamError::Validation(format!(
            "circuit wire count {} does not match gate count {}",
            circuit.wire_count,
            circuit.gates.len()
        )));
    }
    limits.require("circuit inputs", circuit.input_count, limits.max_inputs)?;
    limits.require("circuit gates", circuit.gates.len(), limits.max_gates)?;
    limits.require("circuit outputs", circuit.outputs.len(), limits.max_outputs)?;
    let mut wires = Vec::new();
    wires
        .try_reserve_exact(circuit.wire_count)
        .map_err(|error| {
            OccamError::Validation(format!("cannot allocate scalar wires: {error}"))
        })?;
    wires.resize(circuit.wire_count, false);
    for (gate_index, gate) in circuit.gates.iter().enumerate() {
        if gate.output != gate_index {
            return Err(OccamError::Validation(format!(
                "gate {gate_index} writes non-dense wire {}",
                gate.output
            )));
        }
        let lhs = resolve(gate.lhs, input, &wires, gate_index)?;
        let rhs = resolve(gate.rhs, input, &wires, gate_index)?;
        wires[gate.output] = gate.op.apply(lhs, rhs);
    }
    circuit
        .outputs
        .iter()
        .map(|operand| resolve(*operand, input, &wires, circuit.wire_count))
        .collect()
}

fn resolve(
    operand: Operand,
    inputs: &[bool],
    wires: &[bool],
    available_wires: usize,
) -> Result<bool, OccamError> {
    let value = match operand.source {
        Source::Input(index) => inputs.get(index).copied().ok_or_else(|| {
            OccamError::Validation(format!("input column {index} is out of range"))
        })?,
        Source::Wire(index) if index < available_wires => {
            wires.get(index).copied().ok_or_else(|| {
                OccamError::Validation(format!("wire column {index} is out of range"))
            })?
        }
        Source::Wire(index) => {
            return Err(OccamError::Validation(format!(
                "wire column {index} is unavailable with {available_wires} prior wires"
            )));
        }
    };
    Ok(value ^ operand.inverted)
}

#[cfg(test)]
mod tests {
    use crate::parse_netlist;

    use super::*;

    #[test]
    fn evaluates_all_gate_truth_tables() {
        for (name, expected) in [
            ("AND", [false, false, false, true]),
            ("OR", [false, true, true, true]),
            ("XOR", [false, true, true, false]),
            ("NAND", [true, true, true, false]),
            ("NOR", [true, false, false, false]),
            ("XNOR", [true, false, false, true]),
        ] {
            let circuit =
                parse_netlist(&format!("INPUTS 2\nw1 = {name} x1 x2\nOUTPUTS w1")).unwrap();
            let actual = [[false, false], [false, true], [true, false], [true, true]]
                .map(|input| evaluate(&circuit, &input).unwrap()[0]);
            assert_eq!(actual, expected, "{name}");
        }
    }

    #[test]
    fn applies_free_inversion_and_preserves_output_order() {
        let circuit = parse_netlist("INPUTS 2\nw1 = AND ~x1 x2\nOUTPUTS x2 ~w1 x1").unwrap();
        assert_eq!(
            evaluate(&circuit, &[false, true]).unwrap(),
            [true, false, false]
        );
    }

    #[test]
    fn rejects_input_width_mismatch() {
        let circuit = parse_netlist("INPUTS 2\nOUTPUTS x1").unwrap();
        assert!(evaluate(&circuit, &[true]).is_err());
    }

    #[test]
    fn rejects_invalid_public_circuit_without_panicking() {
        let mut circuit = parse_netlist("INPUTS 1\nw1 = XOR x1 x1\nOUTPUTS w1").unwrap();
        circuit.gates[0].lhs.source = Source::Input(usize::MAX);
        assert!(evaluate(&circuit, &[false]).is_err());

        let mut circuit = parse_netlist("INPUTS 1\nw1 = XOR x1 x1\nOUTPUTS w1").unwrap();
        circuit.gates[0].rhs.source = Source::Wire(usize::MAX);
        assert!(evaluate(&circuit, &[false]).is_err());
    }
}
