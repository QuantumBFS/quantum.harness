use std::fmt;

use crate::{BinaryOp, Expr, OccamError};

impl Expr {
    pub fn canonicalize(&self) -> Result<Self, OccamError> {
        canonicalize(self.clone())
    }
}

fn canonicalize(expression: Expr) -> Result<Expr, OccamError> {
    match expression {
        Expr::X | Expr::Y | Expr::Constant(_) => Ok(expression),
        Expr::Square(value) => {
            let value = canonicalize(*value)?;
            Ok(match value {
                Expr::Constant(0) => Expr::constant(0),
                Expr::Constant(1) => Expr::constant(1),
                value => Expr::square(value),
            })
        }
        Expr::ShiftLeft { value, amount } => {
            if !(1..=3).contains(&amount) {
                return Err(OccamError::Validation(format!(
                    "expression shift amount must be in 1..=3, got {amount}"
                )));
            }
            let value = canonicalize(*value)?;
            Ok(if value == Expr::constant(0) {
                Expr::constant(0)
            } else {
                Expr::shift_left(value, amount)
            })
        }
        Expr::Binary { op, lhs, rhs } => {
            let mut lhs = canonicalize(*lhs)?;
            let mut rhs = canonicalize(*rhs)?;
            if is_commutative(op) && rhs < lhs {
                std::mem::swap(&mut lhs, &mut rhs);
            }
            simplify_binary(op, lhs, rhs)
        }
    }
}

fn simplify_binary(op: BinaryOp, lhs: Expr, rhs: Expr) -> Result<Expr, OccamError> {
    let zero = Expr::constant(0);
    let one = Expr::constant(1);
    let simplified = match op {
        BinaryOp::Add if lhs == zero => rhs,
        BinaryOp::Add if rhs == zero => lhs,
        BinaryOp::Subtract if rhs == zero => lhs,
        BinaryOp::Subtract if lhs == rhs => zero,
        BinaryOp::AbsDiff if lhs == rhs => zero,
        BinaryOp::Multiply if lhs == zero || rhs == zero => zero,
        BinaryOp::Multiply if lhs == one => rhs,
        BinaryOp::Multiply if rhs == one => lhs,
        BinaryOp::Multiply if lhs == rhs => Expr::square(lhs),
        BinaryOp::BitXor if lhs == zero => rhs,
        BinaryOp::BitXor if rhs == zero => lhs,
        BinaryOp::BitXor if lhs == rhs => zero,
        BinaryOp::BitAnd if lhs == zero || rhs == zero => zero,
        BinaryOp::BitAnd if lhs == rhs => lhs,
        BinaryOp::BitOr if lhs == zero => rhs,
        BinaryOp::BitOr if rhs == zero => lhs,
        BinaryOp::BitOr if lhs == rhs => lhs,
        BinaryOp::Min | BinaryOp::Max if lhs == rhs => lhs,
        _ => Expr::binary(op, lhs, rhs),
    };
    simplified.checked_description_cost()?;
    Ok(simplified)
}

fn is_commutative(op: BinaryOp) -> bool {
    matches!(
        op,
        BinaryOp::Add
            | BinaryOp::AbsDiff
            | BinaryOp::Multiply
            | BinaryOp::BitXor
            | BinaryOp::BitAnd
            | BinaryOp::BitOr
            | BinaryOp::Min
            | BinaryOp::Max
    )
}

impl fmt::Display for Expr {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::X => formatter.write_str("x"),
            Self::Y => formatter.write_str("y"),
            Self::Constant(value) => write!(formatter, "{value}"),
            Self::Square(value) => write!(formatter, "square({value})"),
            Self::ShiftLeft { value, amount } => {
                write!(formatter, "shift_left({value}, {amount})")
            }
            Self::Binary {
                op: BinaryOp::AbsDiff,
                lhs,
                rhs,
            } => write!(formatter, "abs({lhs} - {rhs})"),
            Self::Binary { op, lhs, rhs } => {
                let operator = match op {
                    BinaryOp::Add => "+",
                    BinaryOp::Subtract => "-",
                    BinaryOp::Multiply => "*",
                    BinaryOp::BitXor => "XOR",
                    BinaryOp::BitAnd => "AND",
                    BinaryOp::BitOr => "OR",
                    BinaryOp::Min => "min",
                    BinaryOp::Max => "max",
                    BinaryOp::AbsDiff => unreachable!(),
                };
                if matches!(op, BinaryOp::Min | BinaryOp::Max) {
                    write!(formatter, "{operator}({lhs}, {rhs})")
                } else {
                    write!(formatter, "({lhs} {operator} {rhs})")
                }
            }
        }
    }
}
