use crate::{
    Circuit, Expr, ExprSemantics, MdlSearchConfig, OccamError, ResourceLimits, SearchTermination,
    TestInputs, VerificationMetrics, compile_expression, decode_lsb, evaluate_with_limits,
    parse_commitment, parse_dataset_with_limits, parse_netlist_with_limits,
    parse_packed_dataset_with_limits, parse_test_inputs_with_limits, prediction_csv_from_circuit,
    search_mdl, sha256_hex, verify_prepacked_with_limits, verify_with_limits,
};

use super::report::MdlLearningReport;

#[derive(Clone, Copy, Debug)]
pub struct MdlLearnRequest<'a> {
    pub training_source: &'a str,
    pub test_inputs_source: &'a str,
    pub commitment_source: Option<&'a str>,
    pub config: &'a MdlSearchConfig,
    pub limits: &'a ResourceLimits,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct MdlLearnResult {
    pub circuit: String,
    pub prediction_csv: String,
    pub test_inputs: TestInputs,
    pub report: MdlLearningReport,
}

pub fn learn_mdl(request: MdlLearnRequest<'_>) -> Result<MdlLearnResult, OccamError> {
    let training = parse_dataset_with_limits(request.training_source, request.limits)?;
    if !training.input_width.is_multiple_of(2) {
        return Err(OccamError::Validation(format!(
            "MDL training input width {} must be even",
            training.input_width
        )));
    }
    let semantics = ExprSemantics::new(training.input_width / 2, training.output_width)?;
    let search_result = search_mdl(&training, request.config)?;
    if search_result.report.termination != SearchTermination::Found {
        return Err(OccamError::Validation(format!(
            "MDL search did not find a consistent expression: {:?}",
            search_result.report.termination
        )));
    }
    let expression = search_result.expression.ok_or_else(|| {
        OccamError::Validation("MDL search reported success without an expression".into())
    })?;
    let description_cost = search_result.report.description_cost.ok_or_else(|| {
        OccamError::Validation("MDL search report omitted the selected description cost".into())
    })?;
    let minimum_unique = search_result.report.minimum_unique.ok_or_else(|| {
        OccamError::Validation("MDL search report omitted minimum uniqueness".into())
    })?;
    let equal_cost_expression_count = search_result
        .report
        .equal_cost_expression_count
        .ok_or_else(|| {
            OccamError::Validation(
                "MDL search report omitted the equal-cost expression count".into(),
            )
        })?;

    let synthesized = compile_expression(&expression, semantics, request.limits)?;
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
        exhaustively_compare(&circuit, &expression, semantics, request.limits)?;
    if exhaustive_mismatches != 0 {
        return Err(OccamError::Validation(format!(
            "compiled expression circuit has {exhaustive_mismatches} mismatches over \
             {exhaustive_cases} exhaustive cases"
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

    let report = MdlLearningReport {
        schema_version: 2,
        learner: "mdl-enumerator".into(),
        expression: expression.to_string(),
        description_cost,
        minimum_unique,
        equal_cost_expression_count,
        search: search_result.report,
        operand_bits: semantics.operand_bits,
        input_width: training.input_width,
        output_width: training.output_width,
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
    Ok(MdlLearnResult {
        circuit: synthesized.netlist,
        prediction_csv,
        test_inputs,
        report,
    })
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
    circuit: &Circuit,
    expression: &Expr,
    semantics: ExprSemantics,
    limits: &ResourceLimits,
) -> Result<(usize, usize), OccamError> {
    let shift = u32::try_from(circuit.input_count).map_err(|_| OccamError::ArithmeticOverflow {
        context: "MDL exhaustive domain shift",
    })?;
    let cases = 1usize
        .checked_shl(shift)
        .ok_or(OccamError::ArithmeticOverflow {
            context: "MDL exhaustive domain size",
        })?;
    limits.require("exhaustive cases", cases, limits.max_samples)?;

    let mut mismatches = 0usize;
    let mut input = vec![false; circuit.input_count];
    for packed_input in 0..cases {
        for (bit, value) in input.iter_mut().enumerate() {
            *value = packed_input & (1usize << bit) != 0;
        }
        let actual = decode_lsb(&evaluate_with_limits(circuit, &input, limits)?)?;
        let x = decode_lsb(&input[..semantics.operand_bits])?;
        let y = decode_lsb(&input[semantics.operand_bits..])?;
        if actual != expression.evaluate(x, y, semantics)? {
            mismatches += 1;
        }
    }
    Ok((cases, mismatches))
}
