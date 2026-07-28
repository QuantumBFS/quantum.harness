use crate::{
    Circuit, DEFAULT_LIMITS, GateOp, OccamError, Operand, PackedDataset, ResourceLimits, Source,
    VerificationMetrics,
    limits::{checked_add, checked_mul},
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct CompiledOperand {
    column: usize,
    inversion_mask: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct CompiledGate {
    op: GateOp,
    lhs: CompiledOperand,
    rhs: CompiledOperand,
    output_column: usize,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CompiledCircuit {
    input_count: usize,
    gate_count: usize,
    output_count: usize,
    column_count: usize,
    gates: Vec<CompiledGate>,
    outputs: Vec<CompiledOperand>,
}

impl CompiledCircuit {
    pub fn new(circuit: &Circuit) -> Result<Self, OccamError> {
        Self::new_with_limits(circuit, &DEFAULT_LIMITS)
    }

    pub fn new_with_limits(circuit: &Circuit, limits: &ResourceLimits) -> Result<Self, OccamError> {
        limits.require("circuit inputs", circuit.input_count, limits.max_inputs)?;
        limits.require("circuit gates", circuit.gates.len(), limits.max_gates)?;
        limits.require("circuit outputs", circuit.outputs.len(), limits.max_outputs)?;
        if circuit.wire_count != circuit.gates.len() {
            return Err(OccamError::Validation(format!(
                "circuit wire count {} does not match gate count {}",
                circuit.wire_count,
                circuit.gates.len()
            )));
        }
        let column_count = checked_add(
            circuit.input_count,
            circuit.wire_count,
            "compiled circuit column count",
        )?;
        let mut gates = Vec::new();
        gates
            .try_reserve_exact(circuit.gates.len())
            .map_err(|error| {
                OccamError::Validation(format!("cannot allocate compiled gates: {error}"))
            })?;
        for (gate_index, gate) in circuit.gates.iter().enumerate() {
            if gate.output != gate_index {
                return Err(OccamError::Validation(format!(
                    "gate {gate_index} writes non-dense wire {}",
                    gate.output
                )));
            }
            gates.push(CompiledGate {
                op: gate.op,
                lhs: compile_operand(gate.lhs, circuit.input_count, gate_index)?,
                rhs: compile_operand(gate.rhs, circuit.input_count, gate_index)?,
                output_column: checked_add(
                    circuit.input_count,
                    gate.output,
                    "compiled gate output column",
                )?,
            });
        }
        let outputs = circuit
            .outputs
            .iter()
            .map(|operand| compile_operand(*operand, circuit.input_count, circuit.wire_count))
            .collect::<Result<Vec<_>, _>>()?;
        Ok(Self {
            input_count: circuit.input_count,
            gate_count: circuit.gates.len(),
            output_count: circuit.outputs.len(),
            column_count,
            gates,
            outputs,
        })
    }

    pub fn input_count(&self) -> usize {
        self.input_count
    }

    pub fn gate_count(&self) -> usize {
        self.gate_count
    }

    pub fn output_count(&self) -> usize {
        self.output_count
    }
}

fn compile_operand(
    operand: Operand,
    input_count: usize,
    available_wires: usize,
) -> Result<CompiledOperand, OccamError> {
    let column = match operand.source {
        Source::Input(index) if index < input_count => index,
        Source::Input(index) => {
            return Err(OccamError::Validation(format!(
                "input column {index} is out of range for {input_count} inputs"
            )));
        }
        Source::Wire(index) if index < available_wires => {
            checked_add(input_count, index, "compiled wire operand column")?
        }
        Source::Wire(index) => {
            return Err(OccamError::Validation(format!(
                "wire column {index} is unavailable with {available_wires} prior wires"
            )));
        }
    };
    Ok(CompiledOperand {
        column,
        inversion_mask: if operand.inverted { u64::MAX } else { 0 },
    })
}

pub fn verify_compiled_prepacked(
    circuit: &CompiledCircuit,
    dataset: &PackedDataset,
) -> Result<VerificationMetrics, OccamError> {
    verify_compiled_prepacked_with_limits(circuit, dataset, &DEFAULT_LIMITS)
}

pub fn verify_compiled_prepacked_with_limits(
    circuit: &CompiledCircuit,
    dataset: &PackedDataset,
    limits: &ResourceLimits,
) -> Result<VerificationMetrics, OccamError> {
    if circuit.input_count != dataset.input_width() {
        return Err(OccamError::Validation(format!(
            "dataset input width {} does not match compiled circuit inputs {}",
            dataset.input_width(),
            circuit.input_count
        )));
    }
    if circuit.output_count != dataset.output_width() {
        return Err(OccamError::Validation(format!(
            "compiled circuit has {} outputs, dataset has {}",
            circuit.output_count,
            dataset.output_width()
        )));
    }
    limits.require(
        "dataset samples",
        dataset.sample_count(),
        limits.max_samples,
    )?;
    let value_word_count = checked_mul(
        circuit.column_count,
        dataset.block_count(),
        "compiled value word count",
    )?;
    limits.require(
        "compiled value words",
        value_word_count,
        limits.max_packed_words,
    )?;
    let mut values = zeroed_words(value_word_count, "compiled values")?;
    for input_index in 0..circuit.input_count {
        let source = dataset.input_column(input_index).ok_or_else(|| {
            OccamError::Validation(format!("packed input column {input_index} is missing"))
        })?;
        let start = checked_mul(
            input_index,
            dataset.block_count(),
            "compiled input column offset",
        )?;
        let end = checked_add(start, dataset.block_count(), "compiled input column end")?;
        values[start..end].copy_from_slice(source);
    }

    for gate in &circuit.gates {
        let lhs_start = checked_mul(
            gate.lhs.column,
            dataset.block_count(),
            "compiled left operand offset",
        )?;
        let rhs_start = checked_mul(
            gate.rhs.column,
            dataset.block_count(),
            "compiled right operand offset",
        )?;
        let output_start = checked_mul(
            gate.output_column,
            dataset.block_count(),
            "compiled output offset",
        )?;
        for block in 0..dataset.block_count() {
            let lhs = values[lhs_start + block] ^ gate.lhs.inversion_mask;
            let rhs = values[rhs_start + block] ^ gate.rhs.inversion_mask;
            values[output_start + block] = gate.op.apply_word(lhs, rhs);
        }
    }

    let mut mismatches = zeroed_words(dataset.block_count(), "compiled mismatch blocks")?;
    let mut correct_bits = 0usize;
    for (output_index, output) in circuit.outputs.iter().enumerate() {
        let expected = dataset.expected_column(output_index).ok_or_else(|| {
            OccamError::Validation(format!("packed output column {output_index} is missing"))
        })?;
        let output_start = checked_mul(
            output.column,
            dataset.block_count(),
            "compiled result column offset",
        )?;
        for block in 0..dataset.block_count() {
            let mask = dataset.valid_mask(block);
            let predicted = values[output_start + block] ^ output.inversion_mask;
            let different = (predicted ^ expected[block]) & mask;
            correct_bits = checked_add(
                correct_bits,
                ((!different) & mask).count_ones() as usize,
                "compiled correct bit count",
            )?;
            mismatches[block] |= different;
        }
    }
    let exact_matches = mismatches
        .iter()
        .enumerate()
        .map(|(block, different)| {
            let mask = dataset.valid_mask(block);
            (mask.count_ones() - (different & mask).count_ones()) as usize
        })
        .sum();
    Ok(VerificationMetrics {
        samples: dataset.sample_count(),
        gate_count: circuit.gate_count,
        exact_matches,
        correct_bits,
        total_bits: checked_mul(
            dataset.sample_count(),
            dataset.output_width(),
            "compiled verification bit count",
        )?,
    })
}

fn zeroed_words(count: usize, context: &str) -> Result<Vec<u64>, OccamError> {
    let mut words = Vec::new();
    words.try_reserve_exact(count).map_err(|error| {
        OccamError::Validation(format!(
            "cannot allocate {context} ({count} words): {error}"
        ))
    })?;
    words.resize(count, 0);
    Ok(words)
}

#[cfg(test)]
mod tests {
    use crate::{parse_netlist, ripple_carry_adder};

    use super::*;

    #[test]
    fn rejects_non_dense_and_forward_wire_references() {
        let mut circuit = parse_netlist(&ripple_carry_adder(2).unwrap()).unwrap();
        circuit.gates[0].output = 1;
        assert!(CompiledCircuit::new(&circuit).is_err());

        let mut circuit = parse_netlist(&ripple_carry_adder(2).unwrap()).unwrap();
        circuit.gates[0].lhs.source = Source::Wire(0);
        assert!(CompiledCircuit::new(&circuit).is_err());
    }
}
