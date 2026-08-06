use std::path::PathBuf;

use crate::{
    DEFAULT_LIMITS, ExternalCommandLimits, ResourceLimits, logic::synthesize_partial_with_abc,
    parse_netlist, verify,
};

use super::{
    LearnedHypothesis, LearnerFailure, ObservedTask, ResearchLearner, ResearchMethod, TrialBudget,
};

const MAX_OBSERVED_ROWS: usize = 512;

pub struct AbcDontCareLearner {
    abc_binary: Option<PathBuf>,
    genlib_path: PathBuf,
}

impl AbcDontCareLearner {
    pub fn new(abc_binary: Option<PathBuf>) -> Self {
        Self {
            abc_binary,
            genlib_path: PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .parent()
                .expect("crate must be inside the workspace")
                .join("tools/abc/occam.genlib"),
        }
    }

    pub fn with_genlib(abc_binary: Option<PathBuf>, genlib_path: PathBuf) -> Self {
        Self {
            abc_binary,
            genlib_path,
        }
    }
}

impl ResearchLearner for AbcDontCareLearner {
    fn method(&self) -> ResearchMethod {
        ResearchMethod::AbcDontCare
    }

    fn fit(
        &self,
        observed: &ObservedTask,
        _seed: u64,
        budget: &TrialBudget,
    ) -> Result<LearnedHypothesis, LearnerFailure> {
        let abc_binary = self.abc_binary.as_ref().ok_or_else(|| {
            LearnerFailure::Unsupported(
                "ABC don't-care learning requires the checksum-pinned ABC executable".into(),
            )
        })?;
        if budget.timeout.is_zero() {
            return Err(LearnerFailure::Timeout(
                "ABC don't-care learning has a zero timeout".into(),
            ));
        }
        if observed.samples.len() > MAX_OBSERVED_ROWS {
            return Err(LearnerFailure::ResourceLimit(format!(
                "ABC partial-PLA baseline supports at most {MAX_OBSERVED_ROWS} observed rows, got {}",
                observed.samples.len()
            )));
        }
        let pla = render_partial_pla(observed)?;
        let limits = ResourceLimits {
            max_gates: budget.max_gates,
            ..DEFAULT_LIMITS
        };
        let command_limits = ExternalCommandLimits {
            timeout: budget.timeout,
            ..ExternalCommandLimits::default()
        };
        let netlist = synthesize_partial_with_abc(
            &pla,
            abc_binary,
            &self.genlib_path,
            &command_limits,
            &limits,
        )
        .map_err(classify_abc_failure)?;
        let circuit = parse_netlist(&netlist).map_err(classify_abc_failure)?;
        let metrics = verify(&circuit, &observed.dataset()).map_err(classify_abc_failure)?;
        if metrics.exact_matches != metrics.samples {
            return Err(LearnerFailure::ToolError(format!(
                "ABC hypothesis fits only {}/{} observed rows",
                metrics.exact_matches, metrics.samples
            )));
        }
        Ok(LearnedHypothesis::Circuit {
            netlist,
            description_length: Some(circuit.gates.len()),
            minimum_unique: None,
            detail: format!(
                "checksum-pinned ABC partial-PLA flow over {} observed rows",
                observed.samples.len()
            ),
        })
    }
}

pub fn render_partial_pla(observed: &ObservedTask) -> Result<String, LearnerFailure> {
    let rows = normalized_rows(observed)?;
    let mut output = format!(
        ".i {}\n.o {}\n",
        observed.input_width, observed.output_width
    );
    output.push_str(".ilb");
    for input in 0..observed.input_width {
        output.push_str(&format!(" i{input}"));
    }
    output.push('\n');
    output.push_str(".ob");
    for bit in 0..observed.output_width {
        output.push_str(&format!(" o{bit}"));
    }
    output.push_str("\n.type fd\n");
    let mut prefix = String::with_capacity(observed.input_width);
    emit_partitioned_cubes(
        &rows,
        0,
        observed.input_width,
        observed.output_width,
        &mut prefix,
        &mut output,
    );
    output.push_str(".e\n");
    Ok(output)
}

type Row = (Vec<bool>, Vec<bool>);

fn emit_partitioned_cubes(
    rows: &[Row],
    depth: usize,
    input_width: usize,
    output_width: usize,
    prefix: &mut String,
    output: &mut String,
) {
    if rows.is_empty() {
        output.push_str(prefix);
        output.extend(std::iter::repeat_n('-', input_width - depth));
        output.push(' ');
        output.extend(std::iter::repeat_n('-', output_width));
        output.push('\n');
        return;
    }
    if depth == input_width {
        output.push_str(prefix);
        output.push(' ');
        output.extend(rows[0].1.iter().map(|bit| if *bit { '1' } else { '0' }));
        output.push('\n');
        return;
    }
    let split = rows.partition_point(|row| !row.0[depth]);
    prefix.push('0');
    emit_partitioned_cubes(
        &rows[..split],
        depth + 1,
        input_width,
        output_width,
        prefix,
        output,
    );
    prefix.pop();
    prefix.push('1');
    emit_partitioned_cubes(
        &rows[split..],
        depth + 1,
        input_width,
        output_width,
        prefix,
        output,
    );
    prefix.pop();
}

fn normalized_rows(observed: &ObservedTask) -> Result<Vec<Row>, LearnerFailure> {
    if observed.input_width == 0 || observed.output_width == 0 || observed.samples.is_empty() {
        return Err(LearnerFailure::NoHypothesis(
            "ABC requires non-empty, positive-width observations".into(),
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

fn classify_abc_failure(error: crate::OccamError) -> LearnerFailure {
    match error {
        crate::OccamError::ResourceLimit { .. } | crate::OccamError::ArithmeticOverflow { .. } => {
            LearnerFailure::ResourceLimit(error.to_string())
        }
        error if error.to_string().contains("timed out") => {
            LearnerFailure::Timeout(error.to_string())
        }
        _ => LearnerFailure::ToolError(error.to_string()),
    }
}
