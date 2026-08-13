use std::collections::{BTreeSet, HashMap, HashSet};

use serde::{Deserialize, Serialize};

use crate::{
    Circuit, DEFAULT_LIMITS, Dataset, OccamError, Operand, Sample, Source, parse_netlist,
    sha256_hex, verify,
};

use super::equivalence::{evaluate_window, operation_name, window_is_convex};

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct WindowConfig {
    pub min_gates: usize,
    pub max_gates: usize,
    pub max_inputs: usize,
    pub max_outputs: usize,
}

impl Default for WindowConfig {
    fn default() -> Self {
        Self {
            min_gates: 4,
            max_gates: 8,
            max_inputs: 8,
            max_outputs: 4,
        }
    }
}

impl WindowConfig {
    pub fn for_tests() -> Self {
        Self {
            min_gates: 2,
            max_gates: 6,
            max_inputs: 6,
            max_outputs: 4,
        }
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct CircuitWindow {
    pub gate_indices: Vec<usize>,
    pub boundary_inputs: Vec<Source>,
    pub boundary_outputs: Vec<Source>,
    pub truth_table: Dataset,
    pub identity_sha256: String,
}

impl CircuitWindow {
    pub fn is_convex(&self, circuit: &Circuit) -> bool {
        window_is_convex(circuit, &self.gate_indices)
    }
}

pub fn extract_windows(
    circuit: &Circuit,
    config: WindowConfig,
) -> Result<Vec<CircuitWindow>, OccamError> {
    validate_config(config)?;
    let mut identities = BTreeSet::new();
    let mut windows = Vec::new();
    for sink in 0..circuit.gates.len() {
        let mut internal = BTreeSet::from([sink]);
        loop {
            if internal.len() >= config.min_gates {
                let indices = internal.iter().copied().collect::<Vec<_>>();
                if identities.insert(indices.clone())
                    && let Some(window) = build_window(circuit, indices, config)?
                {
                    windows.push(window);
                }
            }
            if internal.len() >= config.max_gates {
                break;
            }
            let mut frontier = BTreeSet::new();
            for index in &internal {
                let gate = &circuit.gates[*index];
                for operand in [gate.lhs, gate.rhs] {
                    if let Source::Wire(producer) = operand.source
                        && !internal.contains(&producer)
                    {
                        frontier.insert(producer);
                    }
                }
            }
            let Some(next) = frontier.into_iter().next_back() else {
                break;
            };
            internal.insert(next);
        }
    }
    windows.sort_by(|lhs, rhs| {
        (&lhs.gate_indices, &lhs.identity_sha256).cmp(&(&rhs.gate_indices, &rhs.identity_sha256))
    });
    Ok(windows)
}

fn validate_config(config: WindowConfig) -> Result<(), OccamError> {
    if config.min_gates == 0
        || config.max_gates < config.min_gates
        || config.max_inputs == 0
        || config.max_outputs == 0
        || config.max_inputs >= usize::BITS as usize
    {
        return Err(OccamError::Validation(format!(
            "invalid window configuration {config:?}"
        )));
    }
    Ok(())
}

fn build_window(
    circuit: &Circuit,
    gate_indices: Vec<usize>,
    config: WindowConfig,
) -> Result<Option<CircuitWindow>, OccamError> {
    if !window_is_convex(circuit, &gate_indices) {
        return Ok(None);
    }
    let internal = gate_indices.iter().copied().collect::<HashSet<_>>();
    let mut boundary_inputs = BTreeSet::new();
    for index in &gate_indices {
        for operand in [circuit.gates[*index].lhs, circuit.gates[*index].rhs] {
            if !matches!(operand.source, Source::Wire(wire) if internal.contains(&wire)) {
                boundary_inputs.insert(operand.source);
            }
        }
    }
    let mut boundary_outputs = BTreeSet::new();
    for index in &gate_indices {
        let source = Source::Wire(*index);
        let external_gate_consumer = circuit.gates.iter().enumerate().any(|(consumer, gate)| {
            !internal.contains(&consumer)
                && [gate.lhs, gate.rhs]
                    .iter()
                    .any(|operand| operand.source == source)
        });
        let final_output = circuit
            .outputs
            .iter()
            .any(|operand| operand.source == source);
        if external_gate_consumer || final_output {
            boundary_outputs.insert(source);
        }
    }
    if boundary_inputs.len() > config.max_inputs
        || boundary_outputs.is_empty()
        || boundary_outputs.len() > config.max_outputs
    {
        return Ok(None);
    }
    let boundary_inputs = boundary_inputs.into_iter().collect::<Vec<_>>();
    let boundary_outputs = boundary_outputs.into_iter().collect::<Vec<_>>();
    let cases = 1usize
        .checked_shl(u32::try_from(boundary_inputs.len()).map_err(|_| {
            OccamError::ArithmeticOverflow {
                context: "window truth-table shift",
            }
        })?)
        .ok_or(OccamError::ArithmeticOverflow {
            context: "window truth-table cases",
        })?;
    DEFAULT_LIMITS.require(
        "window truth-table cases",
        cases,
        DEFAULT_LIMITS.max_samples,
    )?;
    let mut samples = Vec::with_capacity(cases);
    for assignment in 0..cases {
        let input = (0..boundary_inputs.len())
            .map(|bit| assignment & (1usize << bit) != 0)
            .collect();
        let expected = evaluate_window(
            circuit,
            &gate_indices,
            &boundary_inputs,
            &boundary_outputs,
            assignment,
        )?;
        samples.push(Sample { input, expected });
    }
    let truth_table = Dataset {
        input_width: boundary_inputs.len(),
        output_width: boundary_outputs.len(),
        samples,
    };
    verify_local_truth_table(
        circuit,
        &gate_indices,
        &boundary_inputs,
        &boundary_outputs,
        &truth_table,
    )?;
    let identity_sha256 = window_identity(
        &gate_indices,
        &boundary_inputs,
        &boundary_outputs,
        &truth_table,
    );
    Ok(Some(CircuitWindow {
        gate_indices,
        boundary_inputs,
        boundary_outputs,
        truth_table,
        identity_sha256,
    }))
}

fn verify_local_truth_table(
    circuit: &Circuit,
    gate_indices: &[usize],
    boundary_inputs: &[Source],
    boundary_outputs: &[Source],
    truth_table: &Dataset,
) -> Result<(), OccamError> {
    let local = parse_netlist(&local_netlist(
        circuit,
        gate_indices,
        boundary_inputs,
        boundary_outputs,
    )?)?;
    let metrics = verify(&local, truth_table)?;
    if metrics.exact_matches != metrics.samples {
        return Err(OccamError::Validation(format!(
            "extracted local circuit matched only {}/{} truth-table rows",
            metrics.exact_matches, metrics.samples
        )));
    }
    Ok(())
}

fn local_netlist(
    circuit: &Circuit,
    gate_indices: &[usize],
    boundary_inputs: &[Source],
    boundary_outputs: &[Source],
) -> Result<String, OccamError> {
    let mut mapping = boundary_inputs
        .iter()
        .enumerate()
        .map(|(index, source)| {
            (
                *source,
                Operand {
                    source: Source::Input(index),
                    inverted: false,
                },
            )
        })
        .collect::<HashMap<_, _>>();
    let mut source = format!("INPUTS {}\n", boundary_inputs.len());
    for (local_index, original_index) in gate_indices.iter().enumerate() {
        let gate = &circuit.gates[*original_index];
        let lhs = remap_operand(gate.lhs, &mapping)?;
        let rhs = remap_operand(gate.rhs, &mapping)?;
        source.push_str(&format!(
            "w{} = {} {} {}\n",
            local_index + 1,
            operation_name(gate.op),
            render_operand(lhs),
            render_operand(rhs)
        ));
        mapping.insert(
            Source::Wire(*original_index),
            Operand {
                source: Source::Wire(local_index),
                inverted: false,
            },
        );
    }
    source.push_str("OUTPUTS");
    for output in boundary_outputs {
        let operand = mapping.get(output).copied().ok_or_else(|| {
            OccamError::Validation(format!("local output {output:?} has no mapping"))
        })?;
        source.push(' ');
        source.push_str(&render_operand(operand));
    }
    source.push('\n');
    Ok(source)
}

fn remap_operand(
    operand: Operand,
    mapping: &HashMap<Source, Operand>,
) -> Result<Operand, OccamError> {
    let mut remapped = mapping.get(&operand.source).copied().ok_or_else(|| {
        OccamError::Validation(format!("local operand {:?} has no mapping", operand.source))
    })?;
    remapped.inverted ^= operand.inverted;
    Ok(remapped)
}

fn render_operand(operand: Operand) -> String {
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

fn window_identity(
    gate_indices: &[usize],
    boundary_inputs: &[Source],
    boundary_outputs: &[Source],
    truth_table: &Dataset,
) -> String {
    let mut canonical = String::new();
    canonical.push_str("occam71-window-v1\n");
    canonical.push_str(&format!("gates={gate_indices:?}\n"));
    canonical.push_str(&format!("inputs={boundary_inputs:?}\n"));
    canonical.push_str(&format!("outputs={boundary_outputs:?}\n"));
    for sample in &truth_table.samples {
        for bit in &sample.input {
            canonical.push(if *bit { '1' } else { '0' });
        }
        canonical.push(',');
        for bit in &sample.expected {
            canonical.push(if *bit { '1' } else { '0' });
        }
        canonical.push('\n');
    }
    sha256_hex(canonical.as_bytes())
}
