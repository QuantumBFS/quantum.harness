use std::collections::{HashMap, HashSet};

use crate::{
    Circuit, CircuitBuilder, CircuitWindow, OccamError, Operand, ResourceLimits, Signal, Source,
    parse_netlist_with_limits,
};

pub fn rewrite_with_candidate(
    original: &Circuit,
    window: &CircuitWindow,
    replacement: &Circuit,
    limits: &ResourceLimits,
) -> Result<(Circuit, String), OccamError> {
    if replacement.input_count != window.boundary_inputs.len() {
        return Err(OccamError::Validation(format!(
            "replacement input count {} does not match window boundary {}",
            replacement.input_count,
            window.boundary_inputs.len()
        )));
    }
    if replacement.outputs.len() != window.boundary_outputs.len() {
        return Err(OccamError::Validation(format!(
            "replacement output count {} does not match window boundary {}",
            replacement.outputs.len(),
            window.boundary_outputs.len()
        )));
    }
    let internal = window.gate_indices.iter().copied().collect::<HashSet<_>>();
    if internal.len() != window.gate_indices.len() || internal.is_empty() {
        return Err(OccamError::Validation(
            "replacement window gate set is empty or duplicated".into(),
        ));
    }
    let insertion = *window.gate_indices.first().unwrap();
    if window
        .boundary_inputs
        .iter()
        .any(|source| matches!(source, Source::Wire(index) if *index >= insertion))
    {
        return Err(OccamError::Validation(
            "replacement boundary input is unavailable at insertion point".into(),
        ));
    }

    let mut builder = CircuitBuilder::new(original.input_count, limits)?;
    let mut mapping = (0..original.input_count)
        .map(|index| (Source::Input(index), Signal::input(index)))
        .collect::<HashMap<_, _>>();
    for index in 0..original.gates.len() {
        if index == insertion {
            let available = mapping.clone();
            splice_candidate(&mut builder, &available, &mut mapping, window, replacement)?;
        }
        if internal.contains(&index) {
            continue;
        }
        let gate = &original.gates[index];
        let lhs = remap_operand(gate.lhs, &mapping)?;
        let rhs = remap_operand(gate.rhs, &mapping)?;
        let output = builder.binary(gate.op, lhs, rhs)?;
        mapping.insert(Source::Wire(index), output);
    }
    let outputs = original
        .outputs
        .iter()
        .map(|operand| remap_operand(*operand, &mapping))
        .collect::<Result<Vec<_>, _>>()?;
    let synthesized = builder.finish(&outputs)?;
    let reparsed = parse_netlist_with_limits(&synthesized.netlist, limits)?;
    Ok((reparsed, synthesized.netlist))
}

fn splice_candidate(
    builder: &mut CircuitBuilder<'_>,
    original_mapping: &HashMap<Source, Signal>,
    whole_mapping: &mut HashMap<Source, Signal>,
    window: &CircuitWindow,
    replacement: &Circuit,
) -> Result<(), OccamError> {
    let mut local_mapping = window
        .boundary_inputs
        .iter()
        .enumerate()
        .map(|(index, original_source)| {
            original_mapping
                .get(original_source)
                .copied()
                .map(|signal| (Source::Input(index), signal))
                .ok_or_else(|| {
                    OccamError::Validation(format!(
                        "replacement boundary input {original_source:?} has no whole-circuit mapping"
                    ))
                })
        })
        .collect::<Result<HashMap<_, _>, _>>()?;
    for (index, gate) in replacement.gates.iter().enumerate() {
        if gate.output != index {
            return Err(OccamError::Validation(
                "replacement circuit wires must be dense".into(),
            ));
        }
        let lhs = remap_operand(gate.lhs, &local_mapping)?;
        let rhs = remap_operand(gate.rhs, &local_mapping)?;
        let output = builder.binary(gate.op, lhs, rhs)?;
        local_mapping.insert(Source::Wire(index), output);
    }
    for (original_output, replacement_output) in
        window.boundary_outputs.iter().zip(&replacement.outputs)
    {
        whole_mapping.insert(
            *original_output,
            remap_operand(*replacement_output, &local_mapping)?,
        );
    }
    Ok(())
}

fn remap_operand(
    operand: Operand,
    mapping: &HashMap<Source, Signal>,
) -> Result<Signal, OccamError> {
    let signal = mapping.get(&operand.source).copied().ok_or_else(|| {
        OccamError::Validation(format!(
            "rewritten operand {:?} has no source mapping",
            operand.source
        ))
    })?;
    Ok(if operand.inverted {
        signal.inverted()
    } else {
        signal
    })
}
