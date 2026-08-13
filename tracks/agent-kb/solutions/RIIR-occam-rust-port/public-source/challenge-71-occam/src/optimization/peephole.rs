use std::time::{Duration, Instant};

use crate::{
    AttemptStatus, Circuit, OccamError, ResourceLimits, SynthesisLimits, SynthesisProblem,
    SynthesisStatus, compare_circuits_exhaustively, parse_netlist_with_limits, sha256_hex,
    synthesize_minimal,
};

use super::{
    CircuitWindow, PeepholeAttemptReport, PeepholeBoundReport, PeepholeOptimizationReport,
    PeepholeOptimizationResult, WindowConfig, extract_windows, rewrite_with_candidate,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PeepholeConfig {
    pub window: WindowConfig,
    pub per_window_timeout: Duration,
    pub global_timeout: Duration,
    pub max_attempts: usize,
    pub max_exhaustive_inputs: usize,
}

impl Default for PeepholeConfig {
    fn default() -> Self {
        Self {
            window: WindowConfig::default(),
            per_window_timeout: Duration::from_secs(5),
            global_timeout: Duration::from_secs(600),
            max_attempts: 10_000,
            max_exhaustive_inputs: 20,
        }
    }
}

impl PeepholeConfig {
    pub fn for_tests() -> Self {
        Self {
            window: WindowConfig {
                min_gates: 3,
                max_gates: 5,
                max_inputs: 4,
                max_outputs: 2,
            },
            per_window_timeout: Duration::from_secs(5),
            global_timeout: Duration::from_secs(30),
            max_attempts: 100,
            max_exhaustive_inputs: 12,
        }
    }
}

pub fn optimize_peepholes(
    original: &Circuit,
    config: &PeepholeConfig,
    limits: &ResourceLimits,
) -> Result<PeepholeOptimizationResult, OccamError> {
    validate_config(config)?;
    let started = Instant::now();
    let mut current = original.clone();
    let mut current_netlist = render_existing(original);
    let mut attempts = Vec::new();
    let mut accepted_replacements = 0usize;
    let mut termination = "fixed-point".to_owned();

    'fixed_point: loop {
        let windows = extract_windows(&current, config.window)?;
        for window in windows {
            if attempts.len() >= config.max_attempts {
                termination = "attempt-limit".into();
                break 'fixed_point;
            }
            if started.elapsed() >= config.global_timeout {
                termination = "global-timeout".into();
                break 'fixed_point;
            }
            let remaining = config.global_timeout.saturating_sub(started.elapsed());
            let timeout = config.per_window_timeout.min(remaining);
            let (attempt, replacement) = synthesize_window(&window, timeout, config, limits)?;
            if let Some(replacement) = replacement {
                match rewrite_with_candidate(&current, &window, &replacement, limits) {
                    Ok((candidate, netlist)) => {
                        let (cases, mismatches) = compare_circuits_exhaustively(
                            &current,
                            &candidate,
                            config.max_exhaustive_inputs,
                            limits,
                        )?;
                        let improved = candidate.gates.len() < current.gates.len();
                        let mut attempt = attempt;
                        attempt.candidate_whole_gates = Some(candidate.gates.len());
                        attempt.whole_circuit_mismatches = Some(mismatches);
                        attempt.accepted = improved && mismatches == 0;
                        if attempt.accepted {
                            current = candidate;
                            current_netlist = netlist;
                            accepted_replacements = accepted_replacements.checked_add(1).ok_or(
                                OccamError::ArithmeticOverflow {
                                    context: "accepted peephole replacements",
                                },
                            )?;
                            attempts.push(attempt);
                            continue 'fixed_point;
                        }
                        debug_assert!(cases > 0);
                        attempts.push(attempt);
                    }
                    Err(error) => {
                        let mut attempt = attempt;
                        attempt.status = format!("splice-rejected: {error}");
                        attempts.push(attempt);
                    }
                }
            } else {
                attempts.push(attempt);
            }
        }
        break;
    }
    let (whole_circuit_cases, whole_circuit_mismatches) =
        compare_circuits_exhaustively(original, &current, config.max_exhaustive_inputs, limits)?;
    if whole_circuit_mismatches != 0 {
        return Err(OccamError::Validation(format!(
            "peephole result has {whole_circuit_mismatches} whole-circuit mismatches"
        )));
    }
    let report = PeepholeOptimizationReport {
        schema_version: 1,
        window_config: config.window,
        baseline_gate_count: original.gates.len(),
        final_gate_count: current.gates.len(),
        attempted_windows: attempts.len(),
        accepted_replacements,
        termination,
        whole_circuit_cases,
        whole_circuit_mismatches,
        final_circuit_sha256: sha256_hex(current_netlist.as_bytes()),
        attempts,
    };
    Ok(PeepholeOptimizationResult {
        circuit: current,
        netlist: current_netlist,
        report,
    })
}

fn synthesize_window(
    window: &CircuitWindow,
    timeout: Duration,
    config: &PeepholeConfig,
    limits: &ResourceLimits,
) -> Result<(PeepholeAttemptReport, Option<Circuit>), OccamError> {
    let maximum_gate_bound =
        window
            .gate_indices
            .len()
            .checked_sub(1)
            .ok_or(OccamError::ArithmeticOverflow {
                context: "peephole synthesis gate bound",
            })?;
    let synthesis_limits = SynthesisLimits {
        max_inputs: config.window.max_inputs,
        max_outputs: config.window.max_outputs,
        max_truth_rows: 1usize << config.window.max_inputs,
        max_gates: maximum_gate_bound,
        timeout,
        ..SynthesisLimits::default()
    };
    let problem =
        SynthesisProblem::from_dataset_with_limits(&window.truth_table, &synthesis_limits)?;
    let certificate = synthesize_minimal(&problem, &synthesis_limits)?;
    let status = synthesis_status(certificate.status).to_owned();
    let candidate_window_gates = certificate.minimal_gate_count;
    let bounds = certificate
        .attempts
        .iter()
        .map(|attempt| PeepholeBoundReport {
            gate_bound: attempt.gate_bound,
            status: attempt_status(attempt.status).into(),
            variables: attempt.variables,
            clauses: attempt.clauses,
            literals: attempt.literals,
        })
        .collect();
    let attempt = PeepholeAttemptReport {
        window_identity_sha256: window.identity_sha256.clone(),
        original_window_gates: window.gate_indices.len(),
        boundary_inputs: window.boundary_inputs.len(),
        boundary_outputs: window.boundary_outputs.len(),
        status,
        candidate_window_gates,
        candidate_whole_gates: None,
        whole_circuit_mismatches: None,
        accepted: false,
        bounds,
    };
    let replacement = certificate
        .netlist
        .as_deref()
        .map(|netlist| parse_netlist_with_limits(netlist, limits))
        .transpose()?;
    Ok((attempt, replacement))
}

fn validate_config(config: &PeepholeConfig) -> Result<(), OccamError> {
    if config.global_timeout.is_zero()
        || config.max_attempts == 0
        || config.max_exhaustive_inputs == 0
    {
        return Err(OccamError::Validation(
            "peephole global timeout and limits must be positive".into(),
        ));
    }
    Ok(())
}

fn attempt_status(status: AttemptStatus) -> &'static str {
    match status {
        AttemptStatus::Sat => "sat",
        AttemptStatus::Unsat => "unsat",
        AttemptStatus::Timeout => "timeout",
        AttemptStatus::ResourceLimit => "resource-limit",
    }
}

fn synthesis_status(status: SynthesisStatus) -> &'static str {
    match status {
        SynthesisStatus::Sat => "sat",
        SynthesisStatus::NoCircuitWithinBound => "no-circuit-within-bound",
        SynthesisStatus::Timeout => "timeout",
        SynthesisStatus::ResourceLimit => "resource-limit",
    }
}

fn render_existing(circuit: &Circuit) -> String {
    let mut source = format!("INPUTS {}\n", circuit.input_count);
    for gate in &circuit.gates {
        source.push_str(&format!(
            "w{} = {} {} {}\n",
            gate.output + 1,
            gate_name(gate.op),
            operand_name(gate.lhs),
            operand_name(gate.rhs)
        ));
    }
    source.push_str("OUTPUTS");
    for output in &circuit.outputs {
        source.push(' ');
        source.push_str(&operand_name(*output));
    }
    source.push('\n');
    source
}

fn gate_name(operation: crate::GateOp) -> &'static str {
    match operation {
        crate::GateOp::And => "AND",
        crate::GateOp::Or => "OR",
        crate::GateOp::Xor => "XOR",
        crate::GateOp::Nand => "NAND",
        crate::GateOp::Nor => "NOR",
        crate::GateOp::Xnor => "XNOR",
    }
}

fn operand_name(operand: crate::Operand) -> String {
    let name = match operand.source {
        crate::Source::Input(index) => format!("x{}", index + 1),
        crate::Source::Wire(index) => format!("w{}", index + 1),
    };
    if operand.inverted {
        format!("~{name}")
    } else {
        name
    }
}
