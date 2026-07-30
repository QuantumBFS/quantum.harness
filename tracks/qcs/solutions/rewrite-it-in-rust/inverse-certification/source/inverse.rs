use crate::{
    ArithmeticFamily, Circuit, CircuitBuilder, DEFAULT_LIMITS, OccamError, ResourceLimits, Signal,
    evaluate_with_limits,
    learning::{decode_lsb, encode_lsb},
    limits::{checked_add, checked_mul},
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct InverseSpec {
    pub family: ArithmeticFamily,
    pub operand_bits: usize,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct InverseWitness {
    pub x: u64,
    pub y: u64,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RelationRow {
    pub input: Vec<bool>,
    pub accepted_outputs: Vec<Vec<bool>>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RelationProblem {
    pub spec: InverseSpec,
    pub input_width: usize,
    pub output_width: usize,
    pub rows: Vec<RelationRow>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct InverseVerification {
    pub rows: usize,
    pub valid_rows: usize,
    pub invalid_rows: usize,
    pub mismatches: usize,
    pub first_mismatch: Option<InverseMismatch>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct InverseMismatch {
    pub input_value: u64,
    pub output_bits: Vec<bool>,
    pub reason: String,
}

impl InverseSpec {
    pub fn new(family: ArithmeticFamily, operand_bits: usize) -> Result<Self, OccamError> {
        if operand_bits == 0 {
            return Err(OccamError::Validation(
                "inverse operand width must be positive".into(),
            ));
        }
        family.output_width(operand_bits)?;
        checked_mul(operand_bits, 2, "inverse output operand bits")?;
        Ok(Self {
            family,
            operand_bits,
        })
    }

    pub fn input_width(self) -> Result<usize, OccamError> {
        self.family.output_width(self.operand_bits)
    }

    pub fn output_width(self) -> Result<usize, OccamError> {
        checked_add(
            checked_mul(self.operand_bits, 2, "inverse output operand bits")?,
            1,
            "inverse output width",
        )
    }

    pub fn input_row_count(self) -> Result<usize, OccamError> {
        row_count(self.input_width()?)
    }

    pub fn operand_upper_bound(self) -> Result<u64, OccamError> {
        if self.operand_bits >= u64::BITS as usize {
            return Err(OccamError::Validation(format!(
                "inverse operand width {} is too large for exhaustive u64 evaluation",
                self.operand_bits
            )));
        }
        Ok((1u64 << self.operand_bits) - 1)
    }
}

pub fn canonical_preimage(
    spec: InverseSpec,
    target: u64,
) -> Result<Option<InverseWitness>, OccamError> {
    let upper_bound = spec.operand_upper_bound()?;
    for x in 0..=upper_bound {
        for y in 0..=upper_bound {
            if spec.family.evaluate(x, y, spec.operand_bits)? == target {
                return Ok(Some(InverseWitness { x, y }));
            }
        }
    }
    Ok(None)
}

pub fn accepted_outputs(spec: InverseSpec, target: u64) -> Result<Vec<Vec<bool>>, OccamError> {
    let upper_bound = spec.operand_upper_bound()?;
    let mut accepted = Vec::new();
    for x in 0..=upper_bound {
        for y in 0..=upper_bound {
            if spec.family.evaluate(x, y, spec.operand_bits)? == target {
                accepted.push(render_inverse_output(spec, Some(InverseWitness { x, y }))?);
            }
        }
    }
    if accepted.is_empty() {
        accepted.push(render_inverse_output(spec, None)?);
    }
    Ok(accepted)
}

pub fn build_relation_problem(spec: InverseSpec) -> Result<RelationProblem, OccamError> {
    let input_width = spec.input_width()?;
    let output_width = spec.output_width()?;
    let rows = (0..spec.input_row_count()?)
        .map(|target| {
            let target = u64::try_from(target).map_err(|_| OccamError::ArithmeticOverflow {
                context: "inverse target index",
            })?;
            Ok(RelationRow {
                input: encode_lsb(target, input_width)?,
                accepted_outputs: accepted_outputs(spec, target)?,
            })
        })
        .collect::<Result<Vec<_>, OccamError>>()?;
    Ok(RelationProblem {
        spec,
        input_width,
        output_width,
        rows,
    })
}

pub fn synthesize_reference_inverse(
    spec: InverseSpec,
) -> Result<crate::SynthesizedCircuit, OccamError> {
    synthesize_reference_inverse_with_limits(spec, &DEFAULT_LIMITS)
}

pub fn synthesize_reference_inverse_with_limits(
    spec: InverseSpec,
    limits: &ResourceLimits,
) -> Result<crate::SynthesizedCircuit, OccamError> {
    let input_width = spec.input_width()?;
    let output_width = spec.output_width()?;
    limits.require("inverse inputs", input_width, limits.max_inputs)?;
    limits.require("inverse outputs", output_width, limits.max_outputs)?;
    limits.require(
        "inverse truth rows",
        spec.input_row_count()?,
        limits.max_samples,
    )?;

    let mut truth_columns = vec![Vec::with_capacity(spec.input_row_count()?); output_width];
    for target in 0..spec.input_row_count()? {
        let target = u64::try_from(target).map_err(|_| OccamError::ArithmeticOverflow {
            context: "inverse target index",
        })?;
        let output = render_inverse_output(spec, canonical_preimage(spec, target)?)?;
        for (column, bit) in truth_columns.iter_mut().zip(output) {
            column.push(bit);
        }
    }

    let mut builder = CircuitBuilder::new(input_width, limits)?;
    let outputs = truth_columns
        .iter()
        .map(|column| synthesize_truth_column(&mut builder, input_width, column))
        .collect::<Result<Vec<_>, OccamError>>()?;
    builder.finish(&outputs)
}

pub fn verify_inverse_relation(
    circuit: &Circuit,
    spec: InverseSpec,
) -> Result<InverseVerification, OccamError> {
    verify_inverse_relation_with_limits(circuit, spec, &DEFAULT_LIMITS)
}

pub fn verify_inverse_relation_with_limits(
    circuit: &Circuit,
    spec: InverseSpec,
    limits: &ResourceLimits,
) -> Result<InverseVerification, OccamError> {
    let input_width = spec.input_width()?;
    let output_width = spec.output_width()?;
    if circuit.input_count != input_width {
        return Err(OccamError::Validation(format!(
            "inverse circuit INPUTS {} does not match expected input width {input_width}",
            circuit.input_count
        )));
    }
    if circuit.outputs.len() != output_width {
        return Err(OccamError::Validation(format!(
            "inverse circuit output width {} does not match expected output width {output_width}",
            circuit.outputs.len()
        )));
    }

    let mut verified = InverseVerification {
        rows: 0,
        valid_rows: 0,
        invalid_rows: 0,
        mismatches: 0,
        first_mismatch: None,
    };
    for target in 0..spec.input_row_count()? {
        let target = u64::try_from(target).map_err(|_| OccamError::ArithmeticOverflow {
            context: "inverse target index",
        })?;
        let input = encode_lsb(target, input_width)?;
        let output = evaluate_with_limits(circuit, &input, limits)?;
        verified.rows += 1;
        match explain_inverse_output(spec, target, &output)? {
            Ok(()) => {
                if output[output_width - 1] {
                    verified.valid_rows += 1;
                } else {
                    verified.invalid_rows += 1;
                }
            }
            Err(reason) => {
                verified.mismatches += 1;
                if verified.first_mismatch.is_none() {
                    verified.first_mismatch = Some(InverseMismatch {
                        input_value: target,
                        output_bits: output,
                        reason,
                    });
                }
            }
        }
    }
    Ok(verified)
}

fn explain_inverse_output(
    spec: InverseSpec,
    target: u64,
    output: &[bool],
) -> Result<Result<(), String>, OccamError> {
    let output_width = spec.output_width()?;
    if output.len() != output_width {
        return Ok(Err(format!(
            "output width {} does not match expected width {output_width}",
            output.len()
        )));
    }
    let x = decode_lsb(&output[..spec.operand_bits])?;
    let y = decode_lsb(&output[spec.operand_bits..2 * spec.operand_bits])?;
    let valid = output[output_width - 1];
    let has_preimage = canonical_preimage(spec, target)?.is_some();
    if valid {
        let actual = spec.family.evaluate(x, y, spec.operand_bits)?;
        if actual == target {
            Ok(Ok(()))
        } else {
            Ok(Err(format!(
                "valid output ({x}, {y}) maps to {actual}, not target {target}"
            )))
        }
    } else if has_preimage {
        Ok(Err(format!(
            "invalid output claims no preimage for reachable target {target}"
        )))
    } else {
        Ok(Ok(()))
    }
}

fn render_inverse_output(
    spec: InverseSpec,
    witness: Option<InverseWitness>,
) -> Result<Vec<bool>, OccamError> {
    let mut bits = Vec::with_capacity(spec.output_width()?);
    match witness {
        Some(InverseWitness { x, y }) => {
            bits.extend(encode_lsb(x, spec.operand_bits)?);
            bits.extend(encode_lsb(y, spec.operand_bits)?);
            bits.push(true);
        }
        None => {
            bits.extend(std::iter::repeat_n(false, spec.operand_bits * 2));
            bits.push(false);
        }
    }
    Ok(bits)
}

fn synthesize_truth_column(
    builder: &mut CircuitBuilder<'_>,
    input_width: usize,
    truth: &[bool],
) -> Result<Signal, OccamError> {
    let expected_rows = row_count(input_width)?;
    if truth.len() != expected_rows {
        return Err(OccamError::Validation(format!(
            "truth column has {} rows, expected {expected_rows}",
            truth.len()
        )));
    }
    if truth.iter().all(|bit| !*bit) {
        return builder.zero();
    }
    if truth.iter().all(|bit| *bit) {
        return builder.one();
    }
    let mut terms = Vec::new();
    for (assignment, bit) in truth.iter().enumerate() {
        if *bit {
            terms.push(synthesize_minterm(builder, input_width, assignment)?);
        }
    }
    or_all(builder, &terms)
}

fn synthesize_minterm(
    builder: &mut CircuitBuilder<'_>,
    input_width: usize,
    assignment: usize,
) -> Result<Signal, OccamError> {
    let mut literals = Vec::with_capacity(input_width);
    for bit in 0..input_width {
        let set = assignment & (1usize << bit) != 0;
        let signal = Signal::input(bit);
        literals.push(if set { signal } else { signal.inverted() });
    }
    and_all(builder, &literals)
}

fn and_all(builder: &mut CircuitBuilder<'_>, signals: &[Signal]) -> Result<Signal, OccamError> {
    let Some((first, rest)) = signals.split_first() else {
        return builder.one();
    };
    let mut combined = *first;
    for signal in rest {
        combined = builder.binary(crate::GateOp::And, combined, *signal)?;
    }
    Ok(combined)
}

fn or_all(builder: &mut CircuitBuilder<'_>, signals: &[Signal]) -> Result<Signal, OccamError> {
    let Some((first, rest)) = signals.split_first() else {
        return builder.zero();
    };
    let mut combined = *first;
    for signal in rest {
        combined = builder.binary(crate::GateOp::Or, combined, *signal)?;
    }
    Ok(combined)
}

fn row_count(width: usize) -> Result<usize, OccamError> {
    if width >= usize::BITS as usize {
        return Err(OccamError::Validation(format!(
            "truth-table width {width} is too large for exhaustive enumeration"
        )));
    }
    1usize
        .checked_shl(
            width
                .try_into()
                .map_err(|_| OccamError::ArithmeticOverflow {
                    context: "inverse truth-table row count",
                })?,
        )
        .ok_or(OccamError::ArithmeticOverflow {
            context: "inverse truth-table row count",
        })
}

#[cfg(test)]
mod tests {
    use crate::parse_netlist;

    use super::*;

    #[test]
    fn add_relation_keeps_all_preimages_and_unreachable_invalid_row() {
        let spec = InverseSpec::new(ArithmeticFamily::Add, 2).unwrap();
        assert_eq!(accepted_outputs(spec, 3).unwrap().len(), 4);

        let unreachable = accepted_outputs(spec, 7).unwrap();
        assert_eq!(unreachable.len(), 1);
        assert!(!unreachable[0][spec.output_width().unwrap() - 1]);
    }

    #[test]
    fn verifier_rejects_invalid_for_reachable_target() {
        let spec = InverseSpec::new(ArithmeticFamily::Add, 1).unwrap();
        let circuit = parse_netlist("INPUTS 2\nw1 = XOR x1 x1\nOUTPUTS w1 w1 w1\n").unwrap();
        let verified = verify_inverse_relation(&circuit, spec).unwrap();
        assert!(verified.mismatches > 0);
        assert!(
            verified
                .first_mismatch
                .unwrap()
                .reason
                .contains("reachable")
        );
    }
}
