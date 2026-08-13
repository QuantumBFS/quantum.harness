use std::{
    sync::mpsc,
    thread,
    time::{Duration, Instant},
};

use sha2::{Digest, Sha256};
use varisat::{Lit, Solver};

use crate::{
    Circuit, Dataset, Gate, GateOp, OccamError, Operand, Sample, Source, pack_dataset,
    parse_netlist, verify, verify_prepacked,
};

use super::{
    AttemptStatus, SynthesisAttempt, SynthesisCertificate, SynthesisLimits, SynthesisProblem,
    SynthesisStatus, VerificationEvidence,
    cnf::{EncodedSynthesis, GATE_OPERATIONS, GateEncoding, OutputEncoding, encode},
};

pub fn synthesize_minimal(
    problem: &SynthesisProblem,
    limits: &SynthesisLimits,
) -> Result<SynthesisCertificate, OccamError> {
    validate_problem(problem, limits)?;
    let started = Instant::now();
    let mut attempts = Vec::new();

    for gate_bound in 0..=limits.max_gates {
        if timed_out(started.elapsed(), limits.timeout) {
            attempts.push(SynthesisAttempt {
                gate_bound,
                status: AttemptStatus::Timeout,
                variables: 0,
                clauses: 0,
                literals: 0,
                elapsed_ms: 0,
            });
            return Ok(base_certificate(
                problem,
                limits,
                SynthesisStatus::Timeout,
                format!(
                    "timeout reached before solving gate bound {gate_bound}; no larger bound was attempted"
                ),
                attempts,
            ));
        }

        let attempt_started = Instant::now();
        let encoded = match encode(problem, gate_bound, limits) {
            Ok(encoded) => encoded,
            Err(OccamError::ResourceLimit {
                resource,
                requested,
                limit,
            }) => {
                attempts.push(SynthesisAttempt {
                    gate_bound,
                    status: AttemptStatus::ResourceLimit,
                    variables: 0,
                    clauses: 0,
                    literals: 0,
                    elapsed_ms: elapsed_ms(attempt_started.elapsed()),
                });
                return Ok(base_certificate(
                    problem,
                    limits,
                    SynthesisStatus::ResourceLimit,
                    format!(
                        "{resource} resource limit exceeded at gate bound {gate_bound}: requested {requested}, limit {limit}"
                    ),
                    attempts,
                ));
            }
            Err(error) => return Err(error),
        };
        let statistics = encoded.statistics;
        let remaining = limits.timeout.saturating_sub(started.elapsed());
        let solved = solve_with_timeout(encoded, remaining)?;
        let elapsed = attempt_started.elapsed();
        if matches!(solved, TimedSolve::Timeout) {
            attempts.push(SynthesisAttempt {
                gate_bound,
                status: AttemptStatus::Timeout,
                variables: statistics.variables,
                clauses: statistics.clauses,
                literals: statistics.literals,
                elapsed_ms: elapsed_ms(elapsed),
            });
            return Ok(base_certificate(
                problem,
                limits,
                SynthesisStatus::Timeout,
                format!(
                    "wall-clock timeout reached while solving gate bound {gate_bound}; no larger bound was attempted"
                ),
                attempts,
            ));
        }

        match solved {
            TimedSolve::Timeout => unreachable!("timeout returned above"),
            TimedSolve::Completed(CanonicalSolve::Unsat) => attempts.push(SynthesisAttempt {
                gate_bound,
                status: AttemptStatus::Unsat,
                variables: statistics.variables,
                clauses: statistics.clauses,
                literals: statistics.literals,
                elapsed_ms: elapsed_ms(elapsed),
            }),
            TimedSolve::Completed(CanonicalSolve::Sat { circuit }) => {
                let (netlist, verification) = independently_verify(problem, circuit, gate_bound)?;
                attempts.push(SynthesisAttempt {
                    gate_bound,
                    status: AttemptStatus::Sat,
                    variables: statistics.variables,
                    clauses: statistics.clauses,
                    literals: statistics.literals,
                    elapsed_ms: elapsed_ms(elapsed),
                });
                let detail = if gate_bound == 0 {
                    "gate bound 0 was SAT".to_owned()
                } else {
                    format!(
                        "bounds 0 through {} were UNSAT and bound {gate_bound} was SAT",
                        gate_bound - 1
                    )
                };
                let mut certificate =
                    base_certificate(problem, limits, SynthesisStatus::Sat, detail, attempts);
                certificate.minimal_gate_count = Some(gate_bound);
                certificate.netlist_sha256 = Some(sha256_hex(netlist.as_bytes()));
                certificate.netlist = Some(netlist);
                certificate.verification = Some(verification);
                return Ok(certificate);
            }
        }
    }

    Ok(base_certificate(
        problem,
        limits,
        SynthesisStatus::NoCircuitWithinBound,
        format!(
            "all gate bounds from 0 through {} were UNSAT; this is not a proof for larger circuits",
            limits.max_gates
        ),
        attempts,
    ))
}

enum CanonicalSolve {
    Sat { circuit: Circuit },
    Unsat,
}

enum TimedSolve {
    Completed(CanonicalSolve),
    Timeout,
}

fn solve_with_timeout(
    encoded: EncodedSynthesis,
    timeout: Duration,
) -> Result<TimedSolve, OccamError> {
    let (sender, receiver) = mpsc::sync_channel(1);
    thread::Builder::new()
        .name("occam71-sat".into())
        .spawn(move || {
            let _ = sender.send(solve_canonical(encoded));
        })
        .map_err(|error| {
            OccamError::Validation(format!("failed to start SAT solver worker: {error}"))
        })?;
    match receiver.recv_timeout(timeout) {
        Ok(Ok(result)) => Ok(TimedSolve::Completed(result)),
        Ok(Err(error)) => Err(error),
        Err(mpsc::RecvTimeoutError::Timeout) => Ok(TimedSolve::Timeout),
        Err(mpsc::RecvTimeoutError::Disconnected) => Err(OccamError::Validation(
            "SAT solver worker terminated without a result".into(),
        )),
    }
}

fn solve_canonical(encoded: EncodedSynthesis) -> Result<CanonicalSolve, OccamError> {
    let EncodedSynthesis {
        formula,
        gates,
        outputs,
        ..
    } = encoded;
    let mut solver = Solver::new();
    solver.add_formula(&formula);
    let satisfiable = solver
        .solve()
        .map_err(|error| OccamError::Validation(format!("SAT solver failed: {error}")))?;
    if !satisfiable {
        return Ok(CanonicalSolve::Unsat);
    }

    let mut assumptions = Vec::new();
    for selectors in selector_groups(&gates, &outputs) {
        let mut selected = None;
        for selector in selectors {
            let mut trial = assumptions.clone();
            trial.push(selector);
            solver.assume(&trial);
            let satisfiable = solver.solve().map_err(|error| {
                OccamError::Validation(format!("SAT canonicalization failed: {error}"))
            })?;
            if satisfiable {
                selected = Some(selector);
                assumptions.push(selector);
                break;
            }
        }
        if selected.is_none() {
            return Err(OccamError::Validation(
                "SAT model lost an exactly-one selector during canonicalization".into(),
            ));
        }
    }
    solver.assume(&assumptions);
    if !solver
        .solve()
        .map_err(|error| OccamError::Validation(format!("SAT model extraction failed: {error}")))?
    {
        return Err(OccamError::Validation(
            "canonical SAT assumptions unexpectedly became UNSAT".into(),
        ));
    }
    let model = solver
        .model()
        .ok_or_else(|| OccamError::Validation("SAT solver returned SAT without a model".into()))?;
    let circuit = extract_circuit(&gates, &outputs, &model)?;
    Ok(CanonicalSolve::Sat { circuit })
}

fn selector_groups(gates: &[GateEncoding], outputs: &[OutputEncoding]) -> Vec<Vec<Lit>> {
    let mut groups = Vec::with_capacity(gates.len() * 3 + outputs.len());
    for gate in gates {
        groups.push(gate.operations.clone());
        groups.push(gate.lhs_selectors.clone());
        groups.push(gate.rhs_selectors.clone());
    }
    groups.extend(outputs.iter().map(|output| output.selectors.clone()));
    groups
}

fn extract_circuit(
    gates: &[GateEncoding],
    outputs: &[OutputEncoding],
    model: &[Lit],
) -> Result<Circuit, OccamError> {
    let mut extracted_gates = Vec::with_capacity(gates.len());
    for (gate_index, gate) in gates.iter().enumerate() {
        let operation_index = selected_index(&gate.operations, model, "gate operation")?;
        let lhs_index = selected_index(&gate.lhs_selectors, model, "gate lhs")?;
        let rhs_index = selected_index(&gate.rhs_selectors, model, "gate rhs")?;
        extracted_gates.push(Gate {
            output: gate_index,
            op: GATE_OPERATIONS[operation_index],
            lhs: candidate_operand(gate.candidates[lhs_index]),
            rhs: candidate_operand(gate.candidates[rhs_index]),
        });
    }
    let extracted_outputs = outputs
        .iter()
        .map(|output| {
            let index = selected_index(&output.selectors, model, "circuit output")?;
            Ok(candidate_operand(output.candidates[index]))
        })
        .collect::<Result<Vec<_>, OccamError>>()?;
    let input_count = gates
        .first()
        .and_then(|gate| {
            gate.candidates
                .iter()
                .filter_map(|candidate| match candidate.source {
                    Source::Input(index) => Some(index + 1),
                    Source::Wire(_) => None,
                })
                .max()
        })
        .or_else(|| {
            outputs.first().and_then(|output| {
                output
                    .candidates
                    .iter()
                    .filter_map(|candidate| match candidate.source {
                        Source::Input(index) => Some(index + 1),
                        Source::Wire(_) => None,
                    })
                    .max()
            })
        })
        .ok_or_else(|| OccamError::Validation("synthesis circuit has no inputs".into()))?;
    Ok(Circuit {
        input_count,
        wire_count: extracted_gates.len(),
        gates: extracted_gates,
        outputs: extracted_outputs,
    })
}

fn selected_index(selectors: &[Lit], model: &[Lit], context: &str) -> Result<usize, OccamError> {
    let selected = selectors
        .iter()
        .enumerate()
        .filter(|(_, selector)| model_value(model, **selector))
        .map(|(index, _)| index)
        .collect::<Vec<_>>();
    match selected.as_slice() {
        [index] => Ok(*index),
        _ => Err(OccamError::Validation(format!(
            "SAT model selected {} values for {context}, expected exactly one",
            selected.len()
        ))),
    }
}

fn model_value(model: &[Lit], variable: Lit) -> bool {
    model
        .iter()
        .find(|literal| literal.index() == variable.index())
        .is_some_and(|literal| literal.is_positive())
}

fn candidate_operand(candidate: super::cnf::LiteralCandidate) -> Operand {
    Operand {
        source: candidate.source,
        inverted: candidate.inverted,
    }
}

fn independently_verify(
    problem: &SynthesisProblem,
    circuit: Circuit,
    gate_bound: usize,
) -> Result<(String, VerificationEvidence), OccamError> {
    if circuit.gates.len() != gate_bound {
        return Err(OccamError::Validation(format!(
            "extracted circuit has {} gates, expected bound {gate_bound}",
            circuit.gates.len()
        )));
    }
    let netlist = render_netlist(&circuit);
    let reparsed = parse_netlist(&netlist)?;
    if reparsed != circuit {
        return Err(OccamError::Validation(
            "reparsed synthesized netlist differs from extracted circuit".into(),
        ));
    }
    let dataset = problem_dataset(problem);
    let scalar = verify(&reparsed, &dataset)?;
    let packed = verify_prepacked(&reparsed, &pack_dataset(&dataset)?)?;
    let expected_bits = problem.rows.len().checked_mul(problem.output_width).ok_or(
        OccamError::ArithmeticOverflow {
            context: "synthesis verification bit count",
        },
    )?;
    if scalar.exact_matches != problem.rows.len()
        || scalar.correct_bits != expected_bits
        || packed != scalar
    {
        return Err(OccamError::Validation(format!(
            "independent verification rejected synthesized circuit: scalar {scalar:?}, packed {packed:?}"
        )));
    }
    Ok((
        netlist,
        VerificationEvidence {
            reparsed_netlist: true,
            scalar_exact_matches: scalar.exact_matches,
            scalar_correct_bits: scalar.correct_bits,
            packed_exact_matches: packed.exact_matches,
            packed_correct_bits: packed.correct_bits,
        },
    ))
}

fn problem_dataset(problem: &SynthesisProblem) -> Dataset {
    Dataset {
        input_width: problem.input_width,
        output_width: problem.output_width,
        samples: problem
            .rows
            .iter()
            .map(|row| Sample {
                input: row.input.clone(),
                expected: row.expected.clone(),
            })
            .collect(),
    }
}

fn validate_problem(
    problem: &SynthesisProblem,
    limits: &SynthesisLimits,
) -> Result<(), OccamError> {
    let dataset = problem_dataset(problem);
    let canonical = SynthesisProblem::from_partial_dataset_with_limits(&dataset, limits)?;
    if &canonical != problem {
        return Err(OccamError::Validation(
            "SynthesisProblem rows are not in canonical input order".into(),
        ));
    }
    Ok(())
}

fn render_netlist(circuit: &Circuit) -> String {
    let mut netlist = format!("INPUTS {}\n", circuit.input_count);
    for gate in &circuit.gates {
        netlist.push_str(&format!(
            "w{} = {} {} {}\n",
            gate.output + 1,
            operation_name(gate.op),
            operand_name(gate.lhs),
            operand_name(gate.rhs)
        ));
    }
    netlist.push_str("OUTPUTS");
    for output in &circuit.outputs {
        netlist.push(' ');
        netlist.push_str(&operand_name(*output));
    }
    netlist.push('\n');
    netlist
}

fn operation_name(operation: GateOp) -> &'static str {
    match operation {
        GateOp::And => "AND",
        GateOp::Or => "OR",
        GateOp::Xor => "XOR",
        GateOp::Nand => "NAND",
        GateOp::Nor => "NOR",
        GateOp::Xnor => "XNOR",
    }
}

fn operand_name(operand: Operand) -> String {
    let prefix = if operand.inverted { "~" } else { "" };
    match operand.source {
        Source::Input(index) => format!("{prefix}x{}", index + 1),
        Source::Wire(index) => format!("{prefix}w{}", index + 1),
    }
}

fn base_certificate(
    problem: &SynthesisProblem,
    limits: &SynthesisLimits,
    status: SynthesisStatus,
    status_detail: String,
    attempts: Vec<SynthesisAttempt>,
) -> SynthesisCertificate {
    SynthesisCertificate {
        schema_version: 1,
        solver: "varisat 0.2.2".into(),
        encoding: "universal-dag-cnf-v1".into(),
        status,
        status_detail,
        problem_sha256: sha256_hex(&problem.canonical_bytes()),
        input_width: problem.input_width,
        output_width: problem.output_width,
        truth_table_rows: problem.rows.len(),
        maximum_gate_bound: limits.max_gates,
        timeout_ms: elapsed_ms(limits.timeout),
        attempts,
        minimal_gate_count: None,
        netlist_sha256: None,
        netlist: None,
        verification: None,
    }
}

fn sha256_hex(bytes: &[u8]) -> String {
    let digest = Sha256::digest(bytes);
    digest.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn timed_out(elapsed: Duration, timeout: Duration) -> bool {
    elapsed >= timeout
}

fn elapsed_ms(duration: Duration) -> u64 {
    u64::try_from(duration.as_millis()).unwrap_or(u64::MAX)
}

#[cfg(test)]
mod tests {
    use crate::parse_dataset;

    use super::*;

    #[test]
    fn proves_half_adder_minimal_at_two_gates() {
        let dataset = parse_dataset("input,output\n00,00\n01,10\n10,10\n11,01\n").unwrap();
        let problem = SynthesisProblem::from_dataset(&dataset).unwrap();
        let limits = SynthesisLimits {
            max_gates: 2,
            ..SynthesisLimits::default()
        };
        let certificate = synthesize_minimal(&problem, &limits).unwrap();
        assert_eq!(certificate.status, SynthesisStatus::Sat);
        assert_eq!(
            certificate
                .attempts
                .iter()
                .map(|attempt| attempt.status)
                .collect::<Vec<_>>(),
            [
                AttemptStatus::Unsat,
                AttemptStatus::Unsat,
                AttemptStatus::Sat
            ]
        );
        assert_eq!(certificate.minimal_gate_count, Some(2));
        assert!(certificate.verification.is_some());
    }

    #[test]
    fn distinguishes_bound_exhaustion_timeout_and_resource_limit() {
        let dataset = parse_dataset("input,output\n00,00\n01,10\n10,10\n11,01\n").unwrap();
        let problem = SynthesisProblem::from_dataset(&dataset).unwrap();

        let bounded = synthesize_minimal(
            &problem,
            &SynthesisLimits {
                max_gates: 1,
                ..SynthesisLimits::default()
            },
        )
        .unwrap();
        assert_eq!(bounded.status, SynthesisStatus::NoCircuitWithinBound);

        let timeout = synthesize_minimal(
            &problem,
            &SynthesisLimits {
                max_gates: 2,
                timeout: Duration::ZERO,
                ..SynthesisLimits::default()
            },
        )
        .unwrap();
        assert_eq!(timeout.status, SynthesisStatus::Timeout);

        let limited = synthesize_minimal(
            &problem,
            &SynthesisLimits {
                max_gates: 2,
                max_cnf_variables: 0,
                ..SynthesisLimits::default()
            },
        )
        .unwrap();
        assert_eq!(limited.status, SynthesisStatus::ResourceLimit);
    }

    #[test]
    fn certificate_json_is_stably_ordered() {
        let dataset = parse_dataset("input,output\n0,0\n1,1\n").unwrap();
        let problem = SynthesisProblem::from_dataset(&dataset).unwrap();
        let certificate = synthesize_minimal(
            &problem,
            &SynthesisLimits {
                max_gates: 0,
                ..SynthesisLimits::default()
            },
        )
        .unwrap();
        let first = certificate.to_json_pretty().unwrap();
        let second = certificate.to_json_pretty().unwrap();
        assert_eq!(first, second);
        assert!(first.find("\"schema_version\"").unwrap() < first.find("\"status\"").unwrap());
    }
}
