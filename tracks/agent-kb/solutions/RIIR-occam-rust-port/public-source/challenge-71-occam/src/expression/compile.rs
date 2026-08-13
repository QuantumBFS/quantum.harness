use std::collections::HashMap;

use crate::{
    BinaryOp, CircuitBuilder, Expr, ExprSemantics, GateOp, OccamError, ResourceLimits, Signal,
    SynthesizedCircuit, limits::checked_mul,
};

pub fn compile_expression(
    expression: &Expr,
    semantics: ExprSemantics,
    limits: &ResourceLimits,
) -> Result<SynthesizedCircuit, OccamError> {
    let input_count = checked_mul(semantics.operand_bits, 2, "expression compiler input width")?;
    limits.require("circuit inputs", input_count, limits.max_inputs)?;
    limits.require("circuit outputs", semantics.output_bits, limits.max_outputs)?;
    let mut compiler = BitVectorCompiler::new(input_count, semantics, limits)?;
    let expression = expression.canonicalize()?;
    let outputs = compiler.compile(&expression)?;
    compiler.builder.finish(&outputs)
}

struct BitVectorCompiler<'a> {
    builder: CircuitBuilder<'a>,
    semantics: ExprSemantics,
    x: Vec<Signal>,
    y: Vec<Signal>,
    memo: HashMap<Expr, Vec<Signal>>,
}

impl<'a> BitVectorCompiler<'a> {
    fn new(
        input_count: usize,
        semantics: ExprSemantics,
        limits: &'a ResourceLimits,
    ) -> Result<Self, OccamError> {
        let builder = CircuitBuilder::new(input_count, limits)?;
        let mut x = Vec::with_capacity(semantics.output_bits);
        let mut y = Vec::with_capacity(semantics.output_bits);
        for bit in 0..semantics.output_bits {
            if bit < semantics.operand_bits {
                x.push(Signal::input(bit));
                y.push(Signal::input(semantics.operand_bits + bit));
            } else {
                x.push(builder.zero()?);
                y.push(builder.zero()?);
            }
        }
        Ok(Self {
            builder,
            semantics,
            x,
            y,
            memo: HashMap::new(),
        })
    }

    fn compile(&mut self, expression: &Expr) -> Result<Vec<Signal>, OccamError> {
        if let Some(signals) = self.memo.get(expression) {
            return Ok(signals.clone());
        }
        let result = match expression {
            Expr::X => self.x.clone(),
            Expr::Y => self.y.clone(),
            Expr::Constant(value) => self.constant(*value)?,
            Expr::Square(value) => {
                let value = self.compile(value)?;
                self.multiply(&value, &value)?
            }
            Expr::ShiftLeft { value, amount } => {
                if !(1..=3).contains(amount) {
                    return Err(OccamError::Validation(format!(
                        "expression shift amount must be in 1..=3, got {amount}"
                    )));
                }
                let value = self.compile(value)?;
                self.shift_left(&value, usize::from(*amount))?
            }
            Expr::Binary { op, lhs, rhs } => {
                let lhs = self.compile(lhs)?;
                let rhs = self.compile(rhs)?;
                match op {
                    BinaryOp::Add => self.add(&lhs, &rhs)?,
                    BinaryOp::Subtract => self.subtract(&lhs, &rhs)?.0,
                    BinaryOp::AbsDiff => self.abs_diff(&lhs, &rhs)?,
                    BinaryOp::Multiply => self.multiply(&lhs, &rhs)?,
                    BinaryOp::BitXor => self.bitwise(GateOp::Xor, &lhs, &rhs)?,
                    BinaryOp::BitAnd => self.bitwise(GateOp::And, &lhs, &rhs)?,
                    BinaryOp::BitOr => self.bitwise(GateOp::Or, &lhs, &rhs)?,
                    BinaryOp::Min => self.min_max(&lhs, &rhs, false)?,
                    BinaryOp::Max => self.min_max(&lhs, &rhs, true)?,
                }
            }
        };
        debug_assert_eq!(result.len(), self.semantics.output_bits);
        self.memo.insert(expression.clone(), result.clone());
        Ok(result)
    }

    fn constant(&self, value: u64) -> Result<Vec<Signal>, OccamError> {
        if value > self.semantics.output_mask() {
            return Err(OccamError::Validation(format!(
                "expression constant {value} must fit in {} bits",
                self.semantics.output_bits
            )));
        }
        (0..self.semantics.output_bits)
            .map(|bit| {
                if value & (1u64 << bit) == 0 {
                    self.builder.zero()
                } else {
                    self.builder.one()
                }
            })
            .collect()
    }

    fn bitwise(
        &mut self,
        operation: GateOp,
        lhs: &[Signal],
        rhs: &[Signal],
    ) -> Result<Vec<Signal>, OccamError> {
        lhs.iter()
            .zip(rhs)
            .map(|(lhs, rhs)| self.builder.binary(operation, *lhs, *rhs))
            .collect()
    }

    fn add(&mut self, lhs: &[Signal], rhs: &[Signal]) -> Result<Vec<Signal>, OccamError> {
        let mut carry = self.builder.zero()?;
        let mut result = Vec::with_capacity(self.semantics.output_bits);
        for (lhs, rhs) in lhs.iter().zip(rhs) {
            let (sum, next_carry) = self.full_adder(*lhs, *rhs, carry)?;
            result.push(sum);
            carry = next_carry;
        }
        Ok(result)
    }

    fn subtract(
        &mut self,
        lhs: &[Signal],
        rhs: &[Signal],
    ) -> Result<(Vec<Signal>, Signal), OccamError> {
        let mut borrow = self.builder.zero()?;
        let mut difference = Vec::with_capacity(self.semantics.output_bits);
        for (lhs, rhs) in lhs.iter().zip(rhs) {
            let propagate = self.builder.binary(GateOp::Xor, *lhs, *rhs)?;
            difference.push(self.builder.binary(GateOp::Xor, propagate, borrow)?);
            let generated = self.builder.binary(GateOp::And, lhs.inverted(), *rhs)?;
            let propagated = self
                .builder
                .binary(GateOp::And, propagate.inverted(), borrow)?;
            borrow = self.builder.binary(GateOp::Or, generated, propagated)?;
        }
        Ok((difference, borrow))
    }

    fn abs_diff(&mut self, lhs: &[Signal], rhs: &[Signal]) -> Result<Vec<Signal>, OccamError> {
        let (difference, borrow) = self.subtract(lhs, rhs)?;
        let mut carry = borrow;
        let mut result = Vec::with_capacity(self.semantics.output_bits);
        for bit in difference {
            let toggled = self.builder.binary(GateOp::Xor, bit, borrow)?;
            result.push(self.builder.binary(GateOp::Xor, toggled, carry)?);
            carry = self.builder.binary(GateOp::And, toggled, carry)?;
        }
        Ok(result)
    }

    fn min_max(
        &mut self,
        lhs: &[Signal],
        rhs: &[Signal],
        maximum: bool,
    ) -> Result<Vec<Signal>, OccamError> {
        let (_, lhs_is_less) = self.subtract(lhs, rhs)?;
        if maximum {
            self.select(lhs_is_less, rhs, lhs)
        } else {
            self.select(lhs_is_less, lhs, rhs)
        }
    }

    fn select(
        &mut self,
        condition: Signal,
        when_true: &[Signal],
        when_false: &[Signal],
    ) -> Result<Vec<Signal>, OccamError> {
        let mut result = Vec::with_capacity(self.semantics.output_bits);
        for (when_true, when_false) in when_true.iter().zip(when_false) {
            let difference = self.builder.binary(GateOp::Xor, *when_true, *when_false)?;
            let selected = self.builder.binary(GateOp::And, condition, difference)?;
            result.push(self.builder.binary(GateOp::Xor, *when_false, selected)?);
        }
        Ok(result)
    }

    fn shift_left(&self, value: &[Signal], amount: usize) -> Result<Vec<Signal>, OccamError> {
        let mut result = Vec::with_capacity(self.semantics.output_bits);
        for bit in 0..self.semantics.output_bits {
            if bit < amount {
                result.push(self.builder.zero()?);
            } else {
                result.push(value[bit - amount]);
            }
        }
        Ok(result)
    }

    fn multiply(&mut self, lhs: &[Signal], rhs: &[Signal]) -> Result<Vec<Signal>, OccamError> {
        let width = self.semantics.output_bits;
        let column_count = width.checked_add(1).ok_or(OccamError::ArithmeticOverflow {
            context: "expression multiplication columns",
        })?;
        let mut columns = vec![Vec::new(); column_count];
        for (lhs_index, lhs_signal) in lhs.iter().enumerate() {
            for (rhs_index, rhs_signal) in rhs.iter().enumerate() {
                let column =
                    lhs_index
                        .checked_add(rhs_index)
                        .ok_or(OccamError::ArithmeticOverflow {
                            context: "expression multiplication column",
                        })?;
                if column < width {
                    columns[column].push(self.builder.binary(
                        GateOp::And,
                        *lhs_signal,
                        *rhs_signal,
                    )?);
                }
            }
        }
        self.compress_columns(columns)
    }

    fn compress_columns(
        &mut self,
        mut columns: Vec<Vec<Signal>>,
    ) -> Result<Vec<Signal>, OccamError> {
        let width = self.semantics.output_bits;
        let mut outputs = Vec::with_capacity(width);
        for column in 0..width {
            while columns[column].len() > 2 {
                let third = columns[column].pop().unwrap();
                let second = columns[column].pop().unwrap();
                let first = columns[column].pop().unwrap();
                let (sum, carry) = self.full_adder(first, second, third)?;
                columns[column].push(sum);
                columns[column + 1].push(carry);
            }
            match columns[column].as_slice() {
                [] => outputs.push(self.builder.zero()?),
                [only] => outputs.push(*only),
                [first, second] => {
                    let (sum, carry) = self.half_adder(*first, *second)?;
                    outputs.push(sum);
                    columns[column + 1].push(carry);
                }
                _ => unreachable!(),
            }
        }
        Ok(outputs)
    }

    fn half_adder(&mut self, lhs: Signal, rhs: Signal) -> Result<(Signal, Signal), OccamError> {
        Ok((
            self.builder.binary(GateOp::Xor, lhs, rhs)?,
            self.builder.binary(GateOp::And, lhs, rhs)?,
        ))
    }

    fn full_adder(
        &mut self,
        lhs: Signal,
        rhs: Signal,
        carry: Signal,
    ) -> Result<(Signal, Signal), OccamError> {
        let propagate = self.builder.binary(GateOp::Xor, lhs, rhs)?;
        let sum = self.builder.binary(GateOp::Xor, propagate, carry)?;
        let generated = self.builder.binary(GateOp::And, lhs, rhs)?;
        let carried = self.builder.binary(GateOp::And, propagate, carry)?;
        Ok((sum, self.builder.binary(GateOp::Or, generated, carried)?))
    }
}
