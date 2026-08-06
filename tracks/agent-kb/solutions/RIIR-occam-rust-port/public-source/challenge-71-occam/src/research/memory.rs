use std::time::Instant;

use crate::{CircuitBuilder, DEFAULT_LIMITS, GateOp, ResourceLimits, Signal};

use super::{
    LearnedHypothesis, LearnerFailure, ObservedTask, ResearchLearner, ResearchMethod, TrialBudget,
};

pub struct MemorizationLearner;

impl ResearchLearner for MemorizationLearner {
    fn method(&self) -> ResearchMethod {
        ResearchMethod::Memorization
    }

    fn fit(
        &self,
        observed: &ObservedTask,
        _seed: u64,
        budget: &TrialBudget,
    ) -> Result<LearnedHypothesis, LearnerFailure> {
        let rows = normalized_rows(observed)?;
        let limits = ResourceLimits {
            max_gates: budget.max_gates,
            ..DEFAULT_LIMITS
        };
        let mut builder =
            CircuitBuilder::new(observed.input_width, &limits).map_err(classify_builder_failure)?;
        let deadline = Instant::now() + budget.timeout;
        let outputs = (0..observed.output_width)
            .map(|output| {
                compile_trie(
                    &mut builder,
                    &rows,
                    0,
                    observed.input_width,
                    output,
                    deadline,
                )
            })
            .collect::<Result<Vec<_>, _>>()?;
        let circuit = builder.finish(&outputs).map_err(classify_builder_failure)?;
        Ok(LearnedHypothesis::Circuit {
            netlist: circuit.netlist,
            description_length: Some(circuit.gate_count),
            minimum_unique: None,
            detail: format!(
                "explicit zero-default decision trie over {} distinct observed rows",
                rows.len()
            ),
        })
    }
}

type Row = (Vec<bool>, Vec<bool>);

fn normalized_rows(observed: &ObservedTask) -> Result<Vec<Row>, LearnerFailure> {
    if observed.input_width == 0 || observed.output_width == 0 || observed.samples.is_empty() {
        return Err(LearnerFailure::NoHypothesis(
            "memorization requires non-empty, positive-width observations".into(),
        ));
    }
    let mut rows = observed
        .samples
        .iter()
        .map(|sample| {
            if sample.input.len() != observed.input_width
                || sample.expected.len() != observed.output_width
            {
                return Err(LearnerFailure::ToolError(
                    "observed row width does not match the task".into(),
                ));
            }
            Ok((sample.input.clone(), sample.expected.clone()))
        })
        .collect::<Result<Vec<_>, _>>()?;
    rows.sort();
    let mut unique = Vec::<Row>::with_capacity(rows.len());
    for row in rows {
        if let Some(previous) = unique.last()
            && previous.0 == row.0
        {
            if previous.1 != row.1 {
                return Err(LearnerFailure::NoHypothesis(
                    "duplicate observed input has conflicting outputs".into(),
                ));
            }
            continue;
        }
        unique.push(row);
    }
    Ok(unique)
}

fn compile_trie(
    builder: &mut CircuitBuilder<'_>,
    rows: &[Row],
    depth: usize,
    input_width: usize,
    output: usize,
    deadline: Instant,
) -> Result<Signal, LearnerFailure> {
    if Instant::now() >= deadline {
        return Err(LearnerFailure::Timeout(
            "memorization trie construction exceeded the trial timeout".into(),
        ));
    }
    if rows.is_empty() || rows.iter().all(|row| !row.1[output]) {
        return builder.zero().map_err(classify_builder_failure);
    }
    if depth == input_width {
        return if rows[0].1[output] {
            builder.one()
        } else {
            builder.zero()
        }
        .map_err(classify_builder_failure);
    }

    let split = rows.partition_point(|row| !row.0[depth]);
    let low = compile_trie(
        builder,
        &rows[..split],
        depth + 1,
        input_width,
        output,
        deadline,
    )?;
    let high = compile_trie(
        builder,
        &rows[split..],
        depth + 1,
        input_width,
        output,
        deadline,
    )?;
    let variable = Signal::input(depth);
    let when_high = builder
        .binary(GateOp::And, variable, high)
        .map_err(classify_builder_failure)?;
    let when_low = builder
        .binary(GateOp::And, variable.inverted(), low)
        .map_err(classify_builder_failure)?;
    builder
        .binary(GateOp::Or, when_high, when_low)
        .map_err(classify_builder_failure)
}

fn classify_builder_failure(error: crate::OccamError) -> LearnerFailure {
    match error {
        crate::OccamError::ResourceLimit { .. } | crate::OccamError::ArithmeticOverflow { .. } => {
            LearnerFailure::ResourceLimit(error.to_string())
        }
        _ => LearnerFailure::ToolError(error.to_string()),
    }
}
