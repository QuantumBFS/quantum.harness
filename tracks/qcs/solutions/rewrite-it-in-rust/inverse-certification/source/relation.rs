use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};

use crate::{
    OccamError, RelationProblem, build_relation_problem, parse_netlist, verify_inverse_relation,
};

use super::{
    AttemptStatus, SynthesisAttempt, SynthesisLimits, SynthesisStatus,
    cnf::encode_relation,
    solver::{
        CanonicalSolve, TimedSolve, elapsed_ms, render_netlist, sha256_hex, solve_with_timeout,
    },
};

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct RelationVerificationEvidence {
    pub reparsed_netlist: bool,
    pub rows: usize,
    pub valid_rows: usize,
    pub invalid_rows: usize,
    pub mismatches: usize,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct RelationSynthesisCertificate {
    pub schema_version: u32,
    pub solver: String,
    pub encoding: String,
    pub status: SynthesisStatus,
    pub status_detail: String,
    pub problem_sha256: String,
    pub input_width: usize,
    pub output_width: usize,
    pub relation_rows: usize,
    pub maximum_gate_bound: usize,
    pub timeout_ms: u64,
    pub attempts: Vec<SynthesisAttempt>,
    pub minimal_gate_count: Option<usize>,
    pub netlist_sha256: Option<String>,
    pub netlist: Option<String>,
    pub verification: Option<RelationVerificationEvidence>,
}

impl RelationSynthesisCertificate {
    pub fn to_json_pretty(&self) -> Result<String, OccamError> {
        serde_json::to_string_pretty(self)
            .map(|json| format!("{json}\n"))
            .map_err(|error| {
                OccamError::Validation(format!(
                    "relation synthesis certificate JSON encoding failed: {error}"
                ))
            })
    }
}

pub fn synthesize_minimal_relation(
    problem: &RelationProblem,
    limits: &SynthesisLimits,
) -> Result<RelationSynthesisCertificate, OccamError> {
    validate_problem(problem, limits)?;
    let started = Instant::now();
    let mut attempts = Vec::new();

    for gate_bound in 0..=limits.max_gates {
        if started.elapsed() >= limits.timeout {
            attempts.push(empty_attempt(gate_bound, AttemptStatus::Timeout));
            return Ok(base_certificate(
                problem,
                limits,
                SynthesisStatus::Timeout,
                format!(
                    "timeout reached before relation gate bound {gate_bound}; no larger bound was attempted"
                ),
                attempts,
            ));
        }

        let attempt_started = Instant::now();
        let encoded = match encode_relation(problem, gate_bound, limits) {
            Ok(encoded) => encoded,
            Err(OccamError::ResourceLimit {
                resource,
                requested,
                limit,
            }) => {
                let mut attempt = empty_attempt(gate_bound, AttemptStatus::ResourceLimit);
                attempt.elapsed_ms = elapsed_ms(attempt_started.elapsed());
                attempts.push(attempt);
                return Ok(base_certificate(
                    problem,
                    limits,
                    SynthesisStatus::ResourceLimit,
                    format!(
                        "{resource} resource limit exceeded at relation gate bound {gate_bound}: requested {requested}, limit {limit}"
                    ),
                    attempts,
                ));
            }
            Err(error) => return Err(error),
        };
        let statistics = encoded.statistics;
        let remaining = limits.timeout.saturating_sub(started.elapsed());
        let solved = solve_with_timeout(encoded, remaining)?;
        let elapsed = elapsed_ms(attempt_started.elapsed());

        match solved {
            TimedSolve::Timeout => {
                attempts.push(SynthesisAttempt {
                    gate_bound,
                    status: AttemptStatus::Timeout,
                    variables: statistics.variables,
                    clauses: statistics.clauses,
                    literals: statistics.literals,
                    elapsed_ms: elapsed,
                });
                return Ok(base_certificate(
                    problem,
                    limits,
                    SynthesisStatus::Timeout,
                    format!(
                        "wall-clock timeout reached at relation gate bound {gate_bound}; no larger bound was attempted"
                    ),
                    attempts,
                ));
            }
            TimedSolve::Completed(CanonicalSolve::Unsat) => {
                attempts.push(SynthesisAttempt {
                    gate_bound,
                    status: AttemptStatus::Unsat,
                    variables: statistics.variables,
                    clauses: statistics.clauses,
                    literals: statistics.literals,
                    elapsed_ms: elapsed,
                });
            }
            TimedSolve::Completed(CanonicalSolve::Sat { circuit }) => {
                let netlist = render_netlist(&circuit);
                let reparsed = parse_netlist(&netlist)?;
                if reparsed != circuit {
                    return Err(OccamError::Validation(
                        "reparsed relation circuit differs from extracted SAT circuit".into(),
                    ));
                }
                let verified = verify_inverse_relation(&reparsed, problem.spec)?;
                if verified.mismatches != 0 || circuit.gates.len() != gate_bound {
                    return Err(OccamError::Validation(format!(
                        "independent relation verification rejected gate bound {gate_bound}: {} mismatches, {} extracted gates",
                        verified.mismatches,
                        circuit.gates.len()
                    )));
                }
                attempts.push(SynthesisAttempt {
                    gate_bound,
                    status: AttemptStatus::Sat,
                    variables: statistics.variables,
                    clauses: statistics.clauses,
                    literals: statistics.literals,
                    elapsed_ms: elapsed,
                });
                let mut certificate = base_certificate(
                    problem,
                    limits,
                    SynthesisStatus::Sat,
                    if gate_bound == 0 {
                        "relation bound 0 was SAT; no UNSAT proof object is attached".into()
                    } else {
                        format!(
                            "relation bounds 0 through {} returned UNSAT in-process and bound {gate_bound} was SAT; this record is not a DRAT/LRAT proof object",
                            gate_bound - 1
                        )
                    },
                    attempts,
                );
                certificate.minimal_gate_count = Some(gate_bound);
                certificate.netlist_sha256 = Some(sha256_hex(netlist.as_bytes()));
                certificate.netlist = Some(netlist);
                certificate.verification = Some(RelationVerificationEvidence {
                    reparsed_netlist: true,
                    rows: verified.rows,
                    valid_rows: verified.valid_rows,
                    invalid_rows: verified.invalid_rows,
                    mismatches: verified.mismatches,
                });
                return Ok(certificate);
            }
        }
    }

    Ok(base_certificate(
        problem,
        limits,
        SynthesisStatus::NoCircuitWithinBound,
        format!(
            "all relation bounds from 0 through {} returned UNSAT in-process; this is neither a proof for larger circuits nor a DRAT/LRAT certificate",
            limits.max_gates
        ),
        attempts,
    ))
}

fn validate_problem(problem: &RelationProblem, limits: &SynthesisLimits) -> Result<(), OccamError> {
    if problem != &build_relation_problem(problem.spec)? {
        return Err(OccamError::Validation(
            "relation synthesis requires the canonical complete inverse relation".into(),
        ));
    }
    require(
        "relation synthesis inputs",
        problem.input_width,
        limits.max_inputs,
    )?;
    require(
        "relation synthesis outputs",
        problem.output_width,
        limits.max_outputs,
    )?;
    require(
        "relation synthesis rows",
        problem.rows.len(),
        limits.max_truth_rows,
    )?;
    Ok(())
}

fn require(resource: &'static str, requested: usize, limit: usize) -> Result<(), OccamError> {
    if requested > limit {
        return Err(OccamError::ResourceLimit {
            resource,
            requested,
            limit,
        });
    }
    Ok(())
}

fn base_certificate(
    problem: &RelationProblem,
    limits: &SynthesisLimits,
    status: SynthesisStatus,
    status_detail: String,
    attempts: Vec<SynthesisAttempt>,
) -> RelationSynthesisCertificate {
    RelationSynthesisCertificate {
        schema_version: 1,
        solver: "varisat-0.2.2".into(),
        encoding: "fanin2-six-op-relation-forbidden-tuples-v1".into(),
        status,
        status_detail,
        problem_sha256: sha256_hex(&canonical_bytes(problem)),
        input_width: problem.input_width,
        output_width: problem.output_width,
        relation_rows: problem.rows.len(),
        maximum_gate_bound: limits.max_gates,
        timeout_ms: duration_ms(limits.timeout),
        attempts,
        minimal_gate_count: None,
        netlist_sha256: None,
        netlist: None,
        verification: None,
    }
}

fn empty_attempt(gate_bound: usize, status: AttemptStatus) -> SynthesisAttempt {
    SynthesisAttempt {
        gate_bound,
        status,
        variables: 0,
        clauses: 0,
        literals: 0,
        elapsed_ms: 0,
    }
}

fn canonical_bytes(problem: &RelationProblem) -> Vec<u8> {
    let mut bytes = format!(
        "occam71-inverse-relation-v1\nfamily={}\noperand_bits={}\ninputs={}\noutputs={}\n",
        problem.spec.family, problem.spec.operand_bits, problem.input_width, problem.output_width
    )
    .into_bytes();
    for row in &problem.rows {
        for bit in &row.input {
            bytes.push(if *bit { b'1' } else { b'0' });
        }
        bytes.push(b':');
        for output in &row.accepted_outputs {
            for bit in output {
                bytes.push(if *bit { b'1' } else { b'0' });
            }
            bytes.push(b'|');
        }
        bytes.push(b'\n');
    }
    bytes
}

fn duration_ms(duration: Duration) -> u64 {
    duration.as_millis().try_into().unwrap_or(u64::MAX)
}
