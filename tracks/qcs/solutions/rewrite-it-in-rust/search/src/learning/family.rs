use std::fmt;

use serde::{Deserialize, Serialize};

use crate::{Dataset, OccamError, learning::inputs::decode_lsb};

const MAX_OPERAND_BITS: usize = 31;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum ArithmeticFamily {
    Add,
    AbsDiff,
    Multiply,
    SumOfSquares,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct CandidateScore {
    pub family: ArithmeticFamily,
    pub evaluated_rows: usize,
    pub exact_matches: usize,
    pub mismatches: usize,
    pub first_mismatch_row: Option<usize>,
}

impl ArithmeticFamily {
    pub const ALL: [Self; 4] = [Self::Add, Self::AbsDiff, Self::Multiply, Self::SumOfSquares];

    pub fn output_width(self, operand_bits: usize) -> Result<usize, OccamError> {
        validate_operand_bits(operand_bits)?;
        Ok(match self {
            Self::Add => operand_bits + 1,
            Self::AbsDiff => operand_bits,
            Self::Multiply => operand_bits * 2,
            Self::SumOfSquares => operand_bits * 2 + 1,
        })
    }

    pub fn evaluate(self, x: u64, y: u64, operand_bits: usize) -> Result<u64, OccamError> {
        validate_operand_bits(operand_bits)?;
        let upper_bound = (1u64 << operand_bits) - 1;
        if x > upper_bound || y > upper_bound {
            return Err(OccamError::Validation(format!(
                "operands {x} and {y} must fit in {operand_bits} bits"
            )));
        }
        match self {
            Self::Add => x.checked_add(y),
            Self::AbsDiff => Some(x.abs_diff(y)),
            Self::Multiply => x.checked_mul(y),
            Self::SumOfSquares => x.checked_mul(x).and_then(|x_squared| {
                y.checked_mul(y)
                    .and_then(|y_squared| x_squared.checked_add(y_squared))
            }),
        }
        .ok_or(OccamError::ArithmeticOverflow {
            context: "arithmetic family evaluation",
        })
    }
}

impl fmt::Display for ArithmeticFamily {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            Self::Add => "add",
            Self::AbsDiff => "abs-diff",
            Self::Multiply => "multiply",
            Self::SumOfSquares => "sum-of-squares",
        })
    }
}

pub fn score_candidates(dataset: &Dataset) -> Result<Vec<CandidateScore>, OccamError> {
    if dataset.input_width == 0 || !dataset.input_width.is_multiple_of(2) {
        return Err(OccamError::Validation(format!(
            "training input width {} must be positive and even",
            dataset.input_width
        )));
    }
    if dataset.samples.is_empty() {
        return Err(OccamError::Validation(
            "training dataset has no samples".into(),
        ));
    }
    let operand_bits = dataset.input_width / 2;
    validate_operand_bits(operand_bits)?;
    let compatible: Vec<_> = ArithmeticFamily::ALL
        .into_iter()
        .filter(|family| {
            family
                .output_width(operand_bits)
                .is_ok_and(|width| width == dataset.output_width)
        })
        .collect();
    if compatible.is_empty() {
        return Err(OccamError::Validation(format!(
            "no arithmetic candidate supports input width {} and output width {}",
            dataset.input_width, dataset.output_width
        )));
    }

    let mut scores = Vec::with_capacity(compatible.len());
    for family in compatible {
        let mut exact_matches = 0usize;
        let mut first_mismatch_row = None;
        for (index, sample) in dataset.samples.iter().enumerate() {
            if sample.input.len() != dataset.input_width {
                return Err(OccamError::Validation(format!(
                    "sample {} input width {} does not match dataset input width {}",
                    index + 1,
                    sample.input.len(),
                    dataset.input_width
                )));
            }
            if sample.expected.len() != dataset.output_width {
                return Err(OccamError::Validation(format!(
                    "sample {} output width {} does not match dataset output width {}",
                    index + 1,
                    sample.expected.len(),
                    dataset.output_width
                )));
            }
            let x = decode_lsb(&sample.input[..operand_bits])?;
            let y = decode_lsb(&sample.input[operand_bits..])?;
            let predicted = family.evaluate(x, y, operand_bits)?;
            let expected = decode_lsb(&sample.expected)?;
            if predicted == expected {
                exact_matches += 1;
            } else if first_mismatch_row.is_none() {
                first_mismatch_row = Some(index + 1);
            }
        }
        scores.push(CandidateScore {
            family,
            evaluated_rows: dataset.samples.len(),
            exact_matches,
            mismatches: dataset.samples.len() - exact_matches,
            first_mismatch_row,
        });
    }
    Ok(scores)
}

fn validate_operand_bits(operand_bits: usize) -> Result<(), OccamError> {
    if operand_bits == 0 || operand_bits > MAX_OPERAND_BITS {
        return Err(OccamError::Validation(format!(
            "operand width must be in 1..={MAX_OPERAND_BITS}, got {operand_bits}"
        )));
    }
    Ok(())
}
