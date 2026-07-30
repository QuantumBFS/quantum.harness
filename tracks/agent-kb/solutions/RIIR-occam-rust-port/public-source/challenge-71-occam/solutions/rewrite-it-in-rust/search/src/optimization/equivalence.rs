use std::collections::{HashMap, HashSet, VecDeque};

use crate::{Circuit, GateOp, OccamError, Operand, Source};

pub(super) fn window_is_convex(circuit: &Circuit, gate_indices: &[usize]) -> bool {
    let internal = gate_indices.iter().copied().collect::<HashSet<_>>();
    if internal.len() != gate_indices.len()
        || gate_indices
            .iter()
            .any(|index| *index >= circuit.gates.len())
    {
        return false;
    }
    let mut fanouts = vec![Vec::new(); circuit.gates.len()];
    for (consumer, gate) in circuit.gates.iter().enumerate() {
        for operand in [gate.lhs, gate.rhs] {
            if let Source::Wire(producer) = operand.source {
                fanouts[producer].push(consumer);
            }
        }
    }
    for start in gate_indices {
        let mut queue = VecDeque::from([(*start, false)]);
        let mut seen = HashSet::new();
        while let Some((current, left_window)) = queue.pop_front() {
            if !seen.insert((current, left_window)) {
                continue;
            }
            for next in &fanouts[current] {
                let next_is_internal = internal.contains(next);
                let left_window = left_window || !next_is_internal;
                if next_is_internal && left_window {
                    return false;
                }
                queue.push_back((*next, left_window));
            }
        }
    }
    true
}

pub(super) fn evaluate_window(
    circuit: &Circuit,
    gate_indices: &[usize],
    boundary_inputs: &[Source],
    boundary_outputs: &[Source],
    assignment: usize,
) -> Result<Vec<bool>, OccamError> {
    let mut values = HashMap::new();
    for (bit, source) in boundary_inputs.iter().enumerate() {
        values.insert(*source, assignment & (1usize << bit) != 0);
    }
    for index in gate_indices {
        let gate = circuit.gates.get(*index).ok_or_else(|| {
            OccamError::Validation(format!("window gate index {index} is out of range"))
        })?;
        let lhs = operand_value(gate.lhs, &values)?;
        let rhs = operand_value(gate.rhs, &values)?;
        values.insert(Source::Wire(*index), gate.op.apply(lhs, rhs));
    }
    boundary_outputs
        .iter()
        .map(|source| {
            values.get(source).copied().ok_or_else(|| {
                OccamError::Validation(format!("window output {source:?} was not evaluated"))
            })
        })
        .collect()
}

fn operand_value(operand: Operand, values: &HashMap<Source, bool>) -> Result<bool, OccamError> {
    let value = values.get(&operand.source).copied().ok_or_else(|| {
        OccamError::Validation(format!(
            "window operand {:?} is absent from its boundary",
            operand.source
        ))
    })?;
    Ok(value ^ operand.inverted)
}

pub(super) fn operation_name(operation: GateOp) -> &'static str {
    match operation {
        GateOp::And => "AND",
        GateOp::Or => "OR",
        GateOp::Xor => "XOR",
        GateOp::Nand => "NAND",
        GateOp::Nor => "NOR",
        GateOp::Xnor => "XNOR",
    }
}
