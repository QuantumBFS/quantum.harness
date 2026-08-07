use crate::{
    ArithmeticFamily, CandidateScore, Dataset, OccamError, ResourceLimits, TestInputs,
    VerificationMetrics, decode_lsb, evaluate_with_limits, parse_commitment,
    parse_dataset_with_limits, parse_netlist_with_limits, parse_packed_dataset_with_limits,
    parse_test_inputs_with_limits, prediction_csv_from_circuit, score_candidates, sha256_hex,
    synthesize_family_with_limits, verify_prepacked_with_limits, verify_with_limits,
};

use super::report::LearningReport;

#[derive(Clone, Copy, Debug)]
pub struct LearnRequest<'a> {
    pub instance: &'a str,
    pub training_source: &'a str,
    pub test_inputs_source: &'a str,
    pub commitment_source: Option<&'a str>,
    pub limits: &'a ResourceLimits,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct LearnResult {
    pub circuit: String,
    pub prediction_csv: String,
    pub test_inputs: TestInputs,
    pub report: LearningReport,
}

pub fn learn_instance(request: LearnRequest<'_>) -> Result<LearnResult, OccamError> {
    if request.instance.is_empty() || request.instance.chars().any(char::is_control) {
        return Err(OccamError::Validation(
            "learning instance name must be non-empty and contain no control characters".into(),
        ));
    }
    let training = parse_dataset_with_limits(request.training_source, request.limits)?;
    let (family, candidate_scores) = infer_unique_family(&training)?;
    let operand_bits = training.input_width / 2;
    let synthesized = synthesize_family_with_limits(family, operand_bits, request.limits)?;
    let circuit = parse_netlist_with_limits(&synthesized.netlist, request.limits)?;
    let training_scalar = verify_with_limits(&circuit, &training, request.limits)?;
    let packed =
        parse_packed_dataset_with_limits(request.training_source.as_bytes(), request.limits)?;
    let training_packed = verify_prepacked_with_limits(&circuit, &packed, request.limits)?;
    require_perfect_training(&training_scalar, "scalar")?;
    require_perfect_training(&training_packed, "packed")?;
    if training_scalar != training_packed {
        return Err(OccamError::Validation(format!(
            "training backend mismatch: scalar {training_scalar:?}, packed {training_packed:?}"
        )));
    }
    let (exhaustive_cases, exhaustive_mismatches) =
        exhaustively_compare(&circuit, family, operand_bits, request.limits)?;
    if exhaustive_mismatches != 0 {
        return Err(OccamError::Validation(format!(
            "synthesized circuit has {exhaustive_mismatches} mismatches over {exhaustive_cases} exhaustive cases"
        )));
    }

    let test_inputs = parse_test_inputs_with_limits(request.test_inputs_source, request.limits)?;
    if test_inputs.input_width != training.input_width {
        return Err(OccamError::Validation(format!(
            "test input width {} does not match training input width {}",
            test_inputs.input_width, training.input_width
        )));
    }
    let prediction_csv = prediction_csv_from_circuit(&circuit, &test_inputs, request.limits)?;
    let prediction_sha256 = sha256_hex(prediction_csv.as_bytes());
    let expected_commitment_sha256 = request
        .commitment_source
        .map(parse_commitment)
        .transpose()?;
    let commitment_matches = expected_commitment_sha256
        .as_ref()
        .map(|expected| expected == &prediction_sha256);
    if let Some(expected) = expected_commitment_sha256.as_ref()
        && expected != &prediction_sha256
    {
        return Err(OccamError::Validation(format!(
            "prediction commitment mismatch: expected {expected}, got {prediction_sha256}"
        )));
    }

    let report = LearningReport {
        schema_version: 1,
        instance: request.instance.to_owned(),
        selected_family: family,
        operand_bits,
        input_width: training.input_width,
        output_width: training.output_width,
        candidate_scores,
        gate_count: circuit.gates.len(),
        circuit_sha256: sha256_hex(synthesized.netlist.as_bytes()),
        training_scalar,
        training_packed,
        exhaustive_cases,
        exhaustive_mismatches,
        prediction_rows: test_inputs.rows.len(),
        prediction_sha256,
        expected_commitment_sha256,
        commitment_matches,
    };
    Ok(LearnResult {
        circuit: synthesized.netlist,
        prediction_csv,
        test_inputs,
        report,
    })
}

pub fn infer_unique_family(
    dataset: &Dataset,
) -> Result<(ArithmeticFamily, Vec<CandidateScore>), OccamError> {
    let scores = score_candidates(dataset)?;
    let perfect: Vec<_> = scores
        .iter()
        .filter(|score| score.mismatches == 0)
        .map(|score| score.family)
        .collect();
    match perfect.as_slice() {
        [family] => Ok((*family, scores)),
        [] => Err(OccamError::Validation(format!(
            "no zero-error arithmetic family matches the training data: {scores:?}"
        ))),
        _ => Err(OccamError::Validation(format!(
            "ambiguous training data: zero-error arithmetic families {perfect:?}"
        ))),
    }
}

fn require_perfect_training(
    metrics: &VerificationMetrics,
    backend: &str,
) -> Result<(), OccamError> {
    if metrics.exact_matches != metrics.samples {
        return Err(OccamError::Validation(format!(
            "{backend} training verification matched only {}/{} rows",
            metrics.exact_matches, metrics.samples
        )));
    }
    Ok(())
}

fn exhaustively_compare(
    circuit: &crate::Circuit,
    family: ArithmeticFamily,
    operand_bits: usize,
    limits: &ResourceLimits,
) -> Result<(usize, usize), OccamError> {
    let shift = u32::try_from(circuit.input_count).map_err(|_| OccamError::ArithmeticOverflow {
        context: "exhaustive domain shift",
    })?;
    let cases = 1usize
        .checked_shl(shift)
        .ok_or(OccamError::ArithmeticOverflow {
            context: "exhaustive domain size",
        })?;
    limits.require("exhaustive cases", cases, limits.max_samples)?;
    let operand_mask = (1u64 << operand_bits) - 1;
    let mut mismatches = 0usize;
    let mut input = vec![false; circuit.input_count];
    for packed_input in 0..cases {
        for (bit, value) in input.iter_mut().enumerate() {
            *value = packed_input & (1usize << bit) != 0;
        }
        let actual = decode_lsb(&evaluate_with_limits(circuit, &input, limits)?)?;
        let packed_input = packed_input as u64;
        let x = packed_input & operand_mask;
        let y = (packed_input >> operand_bits) & operand_mask;
        if actual != family.evaluate(x, y, operand_bits)? {
            mismatches += 1;
        }
    }
    Ok((cases, mismatches))
}
