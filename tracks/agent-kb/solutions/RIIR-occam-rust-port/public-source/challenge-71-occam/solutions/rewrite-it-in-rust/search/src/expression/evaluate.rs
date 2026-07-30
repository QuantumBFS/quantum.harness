use serde::{Deserialize, Serialize};

use crate::{BinaryOp, Dataset, Expr, ExprSemantics, OccamError, learning::decode_lsb};

#[derive(Clone, Debug, Deserialize, Eq, Hash, Ord, PartialEq, PartialOrd, Serialize)]
pub struct SemanticKey(pub Vec<u64>);

pub fn evaluate_rows(
    expression: &Expr,
    dataset: &Dataset,
    semantics: ExprSemantics,
) -> Result<SemanticKey, OccamError> {
    let expected_input_width =
        semantics
            .operand_bits
            .checked_mul(2)
            .ok_or(OccamError::ArithmeticOverflow {
                context: "expression input width",
            })?;
    if dataset.input_width != expected_input_width {
        return Err(OccamError::Validation(format!(
            "expression dataset input width {} does not match expected width {expected_input_width}",
            dataset.input_width
        )));
    }
    if dataset.output_width != semantics.output_bits {
        return Err(OccamError::Validation(format!(
            "expression dataset output width {} does not match declared width {}",
            dataset.output_width, semantics.output_bits
        )));
    }

    let mut values = Vec::with_capacity(dataset.samples.len());
    for (index, sample) in dataset.samples.iter().enumerate() {
        if sample.input.len() != expected_input_width {
            return Err(OccamError::Validation(format!(
                "expression sample {} input width {} does not match expected width {expected_input_width}",
                index + 1,
                sample.input.len()
            )));
        }
        let x = decode_lsb(&sample.input[..semantics.operand_bits])?;
        let y = decode_lsb(&sample.input[semantics.operand_bits..])?;
        values.push(expression.evaluate(x, y, semantics)?);
    }
    Ok(SemanticKey(values))
}

impl Expr {
    pub fn evaluate(&self, x: u64, y: u64, semantics: ExprSemantics) -> Result<u64, OccamError> {
        if x > semantics.operand_mask() || y > semantics.operand_mask() {
            return Err(OccamError::Validation(format!(
                "expression operands {x} and {y} must fit in {} bits",
                semantics.operand_bits
            )));
        }
        evaluate_inner(self, x, y, semantics)
    }
}

fn evaluate_inner(
    expression: &Expr,
    x: u64,
    y: u64,
    semantics: ExprSemantics,
) -> Result<u64, OccamError> {
    let mask = semantics.output_mask();
    let value = match expression {
        Expr::X => x,
        Expr::Y => y,
        Expr::Constant(value) => {
            if *value > mask {
                return Err(OccamError::Validation(format!(
                    "expression constant {value} must fit in {} bits",
                    semantics.output_bits
                )));
            }
            *value
        }
        Expr::Square(value) => {
            let value = evaluate_inner(value, x, y, semantics)?;
            ((value as u128 * value as u128) & mask as u128) as u64
        }
        Expr::ShiftLeft { value, amount } => {
            if !(1..=3).contains(amount) {
                return Err(OccamError::Validation(format!(
                    "expression shift amount must be in 1..=3, got {amount}"
                )));
            }
            let value = evaluate_inner(value, x, y, semantics)?;
            ((value as u128) << amount) as u64 & mask
        }
        Expr::Binary { op, lhs, rhs } => {
            let lhs = evaluate_inner(lhs, x, y, semantics)?;
            let rhs = evaluate_inner(rhs, x, y, semantics)?;
            match op {
                BinaryOp::Add => ((lhs as u128 + rhs as u128) & mask as u128) as u64,
                BinaryOp::Subtract => lhs.wrapping_sub(rhs) & mask,
                BinaryOp::AbsDiff => lhs.abs_diff(rhs),
                BinaryOp::Multiply => ((lhs as u128 * rhs as u128) & mask as u128) as u64,
                BinaryOp::BitXor => lhs ^ rhs,
                BinaryOp::BitAnd => lhs & rhs,
                BinaryOp::BitOr => lhs | rhs,
                BinaryOp::Min => lhs.min(rhs),
                BinaryOp::Max => lhs.max(rhs),
            }
        }
    };
    Ok(value & mask)
}
