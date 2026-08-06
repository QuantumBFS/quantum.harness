use serde::{Deserialize, Serialize};

use crate::OccamError;

const MAX_OPERAND_BITS: usize = 31;
const MAX_OUTPUT_BITS: usize = 63;

#[derive(Clone, Copy, Debug, Deserialize, Eq, Hash, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum BinaryOp {
    Add,
    Subtract,
    AbsDiff,
    Multiply,
    BitXor,
    BitAnd,
    BitOr,
    Min,
    Max,
}

#[derive(Clone, Debug, Deserialize, Eq, Hash, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(tag = "op", content = "args", rename_all = "kebab-case")]
pub enum Expr {
    X,
    Y,
    Constant(u64),
    Square(Box<Expr>),
    ShiftLeft {
        value: Box<Expr>,
        amount: u8,
    },
    Binary {
        op: BinaryOp,
        lhs: Box<Expr>,
        rhs: Box<Expr>,
    },
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ExprSemantics {
    pub operand_bits: usize,
    pub output_bits: usize,
}

impl ExprSemantics {
    pub fn new(operand_bits: usize, output_bits: usize) -> Result<Self, OccamError> {
        if !(1..=MAX_OPERAND_BITS).contains(&operand_bits) {
            return Err(OccamError::Validation(format!(
                "expression operand width must be in 1..={MAX_OPERAND_BITS}, got {operand_bits}"
            )));
        }
        if !(1..=MAX_OUTPUT_BITS).contains(&output_bits) {
            return Err(OccamError::Validation(format!(
                "expression output width must be in 1..={MAX_OUTPUT_BITS}, got {output_bits}"
            )));
        }
        Ok(Self {
            operand_bits,
            output_bits,
        })
    }

    pub(crate) fn operand_mask(self) -> u64 {
        (1u64 << self.operand_bits) - 1
    }

    pub(crate) fn output_mask(self) -> u64 {
        (1u64 << self.output_bits) - 1
    }
}

impl Expr {
    pub fn x() -> Self {
        Self::X
    }

    pub fn y() -> Self {
        Self::Y
    }

    pub fn constant(value: u64) -> Self {
        Self::Constant(value)
    }

    pub fn square(value: Self) -> Self {
        Self::Square(Box::new(value))
    }

    pub fn shift_left(value: Self, amount: u8) -> Self {
        Self::ShiftLeft {
            value: Box::new(value),
            amount,
        }
    }

    pub fn binary(op: BinaryOp, lhs: Self, rhs: Self) -> Self {
        Self::Binary {
            op,
            lhs: Box::new(lhs),
            rhs: Box::new(rhs),
        }
    }

    pub fn abs_diff(lhs: Self, rhs: Self) -> Self {
        Self::binary(BinaryOp::AbsDiff, lhs, rhs)
    }

    pub fn description_cost(&self) -> usize {
        self.checked_description_cost().unwrap_or(usize::MAX)
    }

    pub fn checked_description_cost(&self) -> Result<usize, OccamError> {
        match self {
            Self::X | Self::Y | Self::Constant(_) => Ok(1),
            Self::Square(value) | Self::ShiftLeft { value, .. } => value
                .checked_description_cost()?
                .checked_add(1)
                .ok_or(OccamError::ArithmeticOverflow {
                    context: "expression description cost",
                }),
            Self::Binary { op, lhs, rhs } => {
                let operator_cost = if *op == BinaryOp::AbsDiff { 2 } else { 1 };
                lhs.checked_description_cost()?
                    .checked_add(rhs.checked_description_cost()?)
                    .and_then(|cost| cost.checked_add(operator_cost))
                    .ok_or(OccamError::ArithmeticOverflow {
                        context: "expression description cost",
                    })
            }
        }
    }
}
