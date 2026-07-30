use std::time::Instant;

use crate::{
    Dataset, SynthesisLimits, SynthesisProblem, SynthesisStatus, evaluate, parse_netlist,
    synthesize_minimal,
};

use super::{
    LearnedHypothesis, LearnerFailure, ObservedTask, ResearchLearner, ResearchMethod, TrialBudget,
};

const MAX_CNF_VARIABLES: usize = 50_000;
const MAX_CNF_CLAUSES: usize = 500_000;
const MAX_CNF_LITERALS: usize = 2_000_000;
const MAX_EIGHT_INPUT_GATES: usize = 3;

pub struct SatCegisLearner;

impl ResearchLearner for SatCegisLearner {
    fn method(&self) -> ResearchMethod {
        ResearchMethod::SatCegis
    }

    fn fit(
        &self,
        observed: &ObservedTask,
        _seed: u64,
        budget: &TrialBudget,
    ) -> Result<LearnedHypothesis, LearnerFailure> {
        if observed.input_width > 8 {
            return Err(LearnerFailure::Unsupported(
                "SAT/CEGIS requires at most eight learner-visible input bits".into(),
            ));
        }
        if budget.timeout.is_zero() {
            return Err(LearnerFailure::Timeout(
                "SAT/CEGIS has a zero timeout".into(),
            ));
        }
        let normalized = normalize_dataset(observed)?;
        let started = Instant::now();
        let mut constraints = vec![normalized.samples[0].clone()];
        let mut iterations = 0usize;
        loop {
            iterations += 1;
            let remaining = budget.timeout.saturating_sub(started.elapsed());
            if remaining.is_zero() {
                return Err(LearnerFailure::Timeout(
                    "SAT/CEGIS exceeded the trial timeout".into(),
                ));
            }
            let limits = SynthesisLimits {
                max_gates: budget.max_gates.min(if observed.input_width == 8 {
                    MAX_EIGHT_INPUT_GATES
                } else {
                    12
                }),
                max_cnf_variables: budget.max_nodes.min(MAX_CNF_VARIABLES),
                max_cnf_clauses: budget.max_nodes.saturating_mul(10).min(MAX_CNF_CLAUSES),
                max_cnf_literals: budget.max_nodes.saturating_mul(50).min(MAX_CNF_LITERALS),
                timeout: remaining,
                ..SynthesisLimits::default()
            };
            let constraint_dataset = Dataset {
                input_width: normalized.input_width,
                output_width: normalized.output_width,
                samples: constraints.clone(),
            };
            let problem =
                SynthesisProblem::from_partial_dataset_with_limits(&constraint_dataset, &limits)
                    .map_err(classify_synthesis_failure)?;
            let certificate =
                synthesize_minimal(&problem, &limits).map_err(classify_synthesis_failure)?;
            match certificate.status {
                SynthesisStatus::Sat => {
                    let netlist = certificate.netlist.ok_or_else(|| {
                        LearnerFailure::ToolError(
                            "SAT certificate reported success without a netlist".into(),
                        )
                    })?;
                    let circuit = parse_netlist(&netlist).map_err(classify_synthesis_failure)?;
                    let counterexample = normalized.samples.iter().find(|sample| {
                        evaluate(&circuit, &sample.input)
                            .map(|actual| actual != sample.expected)
                            .unwrap_or(true)
                    });
                    if let Some(counterexample) = counterexample {
                        if constraints
                            .iter()
                            .any(|sample| sample.input == counterexample.input)
                        {
                            return Err(LearnerFailure::ToolError(
                                "SAT candidate violates an existing CEGIS constraint".into(),
                            ));
                        }
                        constraints.push(counterexample.clone());
                        constraints.sort_by(|lhs, rhs| lhs.input.cmp(&rhs.input));
                        continue;
                    }
                    return Ok(LearnedHypothesis::Circuit {
                        netlist,
                        description_length: certificate.minimal_gate_count,
                        minimum_unique: Some(true),
                        detail: format!(
                            "bounded SAT/CEGIS converged in {iterations} iterations with {} constraints",
                            constraints.len()
                        ),
                    });
                }
                SynthesisStatus::NoCircuitWithinBound => {
                    return Err(LearnerFailure::NoHypothesis(certificate.status_detail));
                }
                SynthesisStatus::Timeout => {
                    return Err(LearnerFailure::Timeout(certificate.status_detail));
                }
                SynthesisStatus::ResourceLimit => {
                    return Err(LearnerFailure::ResourceLimit(certificate.status_detail));
                }
            }
        }
    }
}

fn normalize_dataset(observed: &ObservedTask) -> Result<Dataset, LearnerFailure> {
    let limits = SynthesisLimits::default();
    let problem = SynthesisProblem::from_partial_dataset_with_limits(&observed.dataset(), &limits)
        .map_err(classify_synthesis_failure)?;
    Ok(Dataset {
        input_width: problem.input_width,
        output_width: problem.output_width,
        samples: problem
            .rows
            .into_iter()
            .map(|row| crate::Sample {
                input: row.input,
                expected: row.expected,
            })
            .collect(),
    })
}

fn classify_synthesis_failure(error: crate::OccamError) -> LearnerFailure {
    match error {
        crate::OccamError::ResourceLimit { .. } | crate::OccamError::ArithmeticOverflow { .. } => {
            LearnerFailure::ResourceLimit(error.to_string())
        }
        _ => LearnerFailure::ToolError(error.to_string()),
    }
}
