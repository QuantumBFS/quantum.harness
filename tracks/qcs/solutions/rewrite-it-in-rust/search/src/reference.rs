use crate::{
    ArithmeticFamily, CircuitBuilder, DEFAULT_LIMITS, GateOp, OccamError, ResourceLimits, Signal,
    SynthesizedCircuit,
    limits::{checked_add, checked_mul, checked_sub},
};

struct Builder {
    input_count: usize,
    next_wire: usize,
    lines: Vec<String>,
    joined_bytes: usize,
    max_bytes: usize,
}

pub fn synthesize_family(
    family: ArithmeticFamily,
    operand_bits: usize,
) -> Result<SynthesizedCircuit, OccamError> {
    synthesize_family_with_limits(family, operand_bits, &DEFAULT_LIMITS)
}

pub fn synthesize_family_with_limits(
    family: ArithmeticFamily,
    operand_bits: usize,
    limits: &ResourceLimits,
) -> Result<SynthesizedCircuit, OccamError> {
    let input_count = checked_mul(operand_bits, 2, "family synthesis input count")?;
    let output_count = family.output_width(operand_bits)?;
    limits.require("circuit inputs", input_count, limits.max_inputs)?;
    limits.require("circuit outputs", output_count, limits.max_outputs)?;
    let mut builder = CircuitBuilder::new(input_count, limits)?;
    let lhs: Vec<_> = (0..operand_bits).map(Signal::input).collect();
    let rhs: Vec<_> = (operand_bits..input_count).map(Signal::input).collect();
    let outputs = match family {
        ArithmeticFamily::Add => synthesize_add(&mut builder, &lhs, &rhs)?,
        ArithmeticFamily::AbsDiff => synthesize_abs_diff(&mut builder, &lhs, &rhs)?,
        ArithmeticFamily::Multiply => synthesize_product(&mut builder, &lhs, &rhs, output_count)?,
        ArithmeticFamily::SumOfSquares => {
            synthesize_sum_of_squares(&mut builder, &lhs, &rhs, output_count)?
        }
    };
    debug_assert_eq!(outputs.len(), output_count);
    builder.finish(&outputs)
}

fn synthesize_add(
    builder: &mut CircuitBuilder<'_>,
    lhs: &[Signal],
    rhs: &[Signal],
) -> Result<Vec<Signal>, OccamError> {
    debug_assert_eq!(lhs.len(), rhs.len());
    let mut outputs = Vec::with_capacity(lhs.len() + 1);
    let (sum, mut carry) = half_adder(builder, lhs[0], rhs[0])?;
    outputs.push(sum);
    for index in 1..lhs.len() {
        let (sum, next_carry) = full_adder(builder, lhs[index], rhs[index], carry)?;
        outputs.push(sum);
        carry = next_carry;
    }
    outputs.push(carry);
    Ok(outputs)
}

fn synthesize_abs_diff(
    builder: &mut CircuitBuilder<'_>,
    lhs: &[Signal],
    rhs: &[Signal],
) -> Result<Vec<Signal>, OccamError> {
    debug_assert_eq!(lhs.len(), rhs.len());
    let mut borrow = builder.zero()?;
    let mut difference = Vec::with_capacity(lhs.len());
    for index in 0..lhs.len() {
        let propagate = builder.binary(GateOp::Xor, lhs[index], rhs[index])?;
        difference.push(builder.binary(GateOp::Xor, propagate, borrow)?);
        let generated = builder.binary(GateOp::And, lhs[index].inverted(), rhs[index])?;
        let propagated = builder.binary(GateOp::And, propagate.inverted(), borrow)?;
        borrow = builder.binary(GateOp::Or, generated, propagated)?;
    }

    let mut carry = borrow;
    let mut outputs = Vec::with_capacity(lhs.len());
    for bit in difference {
        let toggled = builder.binary(GateOp::Xor, bit, borrow)?;
        outputs.push(builder.binary(GateOp::Xor, toggled, carry)?);
        carry = builder.binary(GateOp::And, toggled, carry)?;
    }
    Ok(outputs)
}

fn synthesize_product(
    builder: &mut CircuitBuilder<'_>,
    lhs: &[Signal],
    rhs: &[Signal],
    width: usize,
) -> Result<Vec<Signal>, OccamError> {
    let mut columns = vec![Vec::new(); width + 1];
    for (lhs_index, lhs_signal) in lhs.iter().enumerate() {
        for (rhs_index, rhs_signal) in rhs.iter().enumerate() {
            columns[lhs_index + rhs_index].push(builder.binary(
                GateOp::And,
                *lhs_signal,
                *rhs_signal,
            )?);
        }
    }
    compress_columns(builder, columns, width)
}

fn synthesize_sum_of_squares(
    builder: &mut CircuitBuilder<'_>,
    lhs: &[Signal],
    rhs: &[Signal],
    width: usize,
) -> Result<Vec<Signal>, OccamError> {
    let mut columns = vec![Vec::new(); width + 1];
    for operand in [lhs, rhs] {
        for (first_index, first) in operand.iter().enumerate() {
            for (second_index, second) in operand.iter().enumerate() {
                columns[first_index + second_index].push(builder.binary(
                    GateOp::And,
                    *first,
                    *second,
                )?);
            }
        }
    }
    compress_columns(builder, columns, width)
}

fn compress_columns(
    builder: &mut CircuitBuilder<'_>,
    mut columns: Vec<Vec<Signal>>,
    width: usize,
) -> Result<Vec<Signal>, OccamError> {
    debug_assert!(columns.len() > width);
    let mut outputs = Vec::with_capacity(width);
    for column in 0..width {
        while columns[column].len() > 2 {
            let third = columns[column].pop().unwrap();
            let second = columns[column].pop().unwrap();
            let first = columns[column].pop().unwrap();
            let (sum, carry) = full_adder(builder, first, second, third)?;
            columns[column].push(sum);
            columns[column + 1].push(carry);
        }
        match columns[column].as_slice() {
            [] => outputs.push(builder.zero()?),
            [only] => outputs.push(*only),
            [first, second] => {
                let (sum, carry) = half_adder(builder, *first, *second)?;
                outputs.push(sum);
                columns[column + 1].push(carry);
            }
            _ => unreachable!(),
        }
    }
    Ok(outputs)
}

fn half_adder(
    builder: &mut CircuitBuilder<'_>,
    lhs: Signal,
    rhs: Signal,
) -> Result<(Signal, Signal), OccamError> {
    Ok((
        builder.binary(GateOp::Xor, lhs, rhs)?,
        builder.binary(GateOp::And, lhs, rhs)?,
    ))
}

fn full_adder(
    builder: &mut CircuitBuilder<'_>,
    lhs: Signal,
    rhs: Signal,
    carry: Signal,
) -> Result<(Signal, Signal), OccamError> {
    let propagate = builder.binary(GateOp::Xor, lhs, rhs)?;
    let sum = builder.binary(GateOp::Xor, propagate, carry)?;
    let generated = builder.binary(GateOp::And, lhs, rhs)?;
    let carried = builder.binary(GateOp::And, propagate, carry)?;
    Ok((sum, builder.binary(GateOp::Or, generated, carried)?))
}

impl Builder {
    fn new(input_count: usize, max_bytes: usize) -> Result<Self, OccamError> {
        let header = format!("INPUTS {input_count}");
        let joined_bytes = header.len();
        if joined_bytes > max_bytes {
            return Err(OccamError::ResourceLimit {
                resource: "generated bytes",
                requested: joined_bytes,
                limit: max_bytes,
            });
        }
        Ok(Self {
            input_count,
            next_wire: 1,
            lines: vec![header],
            joined_bytes,
            max_bytes,
        })
    }

    fn gate(&mut self, op: &str, lhs: &str, rhs: &str) -> Result<String, OccamError> {
        let output = format!("w{}", self.next_wire);
        self.next_wire = checked_add(self.next_wire, 1, "generated wire identifier")?;
        self.push_line(format!("{output} = {op} {lhs} {rhs}"))?;
        Ok(output)
    }

    fn finish(mut self, outputs: &[String]) -> Result<String, OccamError> {
        debug_assert!(self.input_count > 0);
        self.push_line(format!("OUTPUTS {}", outputs.join(" ")))?;
        self.push_line(String::new())?;
        Ok(self.lines.join("\n"))
    }

    fn push_line(&mut self, line: String) -> Result<(), OccamError> {
        let separator = usize::from(!self.lines.is_empty());
        let next_bytes = checked_add(
            checked_add(self.joined_bytes, separator, "generated circuit bytes")?,
            line.len(),
            "generated circuit bytes",
        )?;
        if next_bytes > self.max_bytes {
            return Err(OccamError::ResourceLimit {
                resource: "generated bytes",
                requested: next_bytes,
                limit: self.max_bytes,
            });
        }
        self.lines.push(line);
        self.joined_bytes = next_bytes;
        Ok(())
    }
}

pub fn ripple_carry_adder(bits: usize) -> Result<String, OccamError> {
    ripple_carry_adder_with_limits(bits, &DEFAULT_LIMITS)
}

pub fn ripple_carry_adder_with_limits(
    bits: usize,
    limits: &ResourceLimits,
) -> Result<String, OccamError> {
    if bits == 0 {
        return Err(OccamError::Validation(
            "adder width must be positive".into(),
        ));
    }
    let input_count = checked_mul(bits, 2, "adder input count")?;
    let output_count = checked_add(bits, 1, "adder output count")?;
    let gate_count = checked_sub(
        checked_mul(bits, 5, "adder gate count")?,
        3,
        "adder gate count",
    )?;
    check_circuit_limits(input_count, gate_count, output_count, limits)?;
    let max_bytes = limits.max_generated_bytes.min(limits.max_source_bytes);
    let mut builder = Builder::new(input_count, max_bytes)?;
    let mut outputs = Vec::with_capacity(output_count);

    let first_x = "x1".to_owned();
    let first_y = format!("x{}", bits + 1);
    outputs.push(builder.gate("XOR", &first_x, &first_y)?);
    let mut carry = builder.gate("AND", &first_x, &first_y)?;

    for bit in 1..bits {
        let x = format!("x{}", bit + 1);
        let y = format!("x{}", bits + bit + 1);
        let propagate = builder.gate("XOR", &x, &y)?;
        outputs.push(builder.gate("XOR", &propagate, &carry)?);
        let generated = builder.gate("AND", &x, &y)?;
        let propagated = builder.gate("AND", &propagate, &carry)?;
        carry = builder.gate("OR", &generated, &propagated)?;
    }
    outputs.push(carry);
    builder.finish(&outputs)
}

pub fn shift_add_multiplier(bits: usize) -> Result<String, OccamError> {
    shift_add_multiplier_with_limits(bits, &DEFAULT_LIMITS)
}

pub fn shift_add_multiplier_with_limits(
    bits: usize,
    limits: &ResourceLimits,
) -> Result<String, OccamError> {
    if bits == 0 {
        return Err(OccamError::Validation(
            "multiplier width must be positive".into(),
        ));
    }
    let width = checked_mul(bits, 2, "multiplier width")?;
    let bits_squared = checked_mul(bits, bits, "multiplier partial products")?;
    let add_gate_count = checked_sub(
        checked_mul(width, 5, "multiplier vector-adder gate count")?,
        3,
        "multiplier vector-adder gate count",
    )?;
    let repeated_adders = checked_mul(
        bits - 1,
        add_gate_count,
        "multiplier repeated-adder gate count",
    )?;
    let gate_count = checked_add(
        checked_add(1, bits_squared, "multiplier gate count")?,
        repeated_adders,
        "multiplier gate count",
    )?;
    check_circuit_limits(width, gate_count, width, limits)?;
    let max_bytes = limits.max_generated_bytes.min(limits.max_source_bytes);
    let mut builder = Builder::new(width, max_bytes)?;
    let zero = builder.gate("XOR", "x1", "x1")?;
    let mut partials = vec![vec![String::new(); bits]; bits];
    for (x_bit, row) in partials.iter_mut().enumerate() {
        for (y_bit, cell) in row.iter_mut().enumerate() {
            *cell = builder.gate(
                "AND",
                &format!("x{}", x_bit + 1),
                &format!("x{}", bits + y_bit + 1),
            )?;
        }
    }

    let mut accumulated = vec![zero.clone(); width];
    accumulated[..bits].clone_from_slice(&partials[0]);
    for (y_bit, partial_row) in partials.iter().enumerate().skip(1) {
        let mut shifted = vec![zero.clone(); width];
        shifted[y_bit..(bits + y_bit)].clone_from_slice(partial_row);
        accumulated = add_vectors(&mut builder, &accumulated, &shifted)?;
    }
    builder.finish(&accumulated)
}

fn check_circuit_limits(
    inputs: usize,
    gates: usize,
    outputs: usize,
    limits: &ResourceLimits,
) -> Result<(), OccamError> {
    limits.require("circuit inputs", inputs, limits.max_inputs)?;
    limits.require("circuit gates", gates, limits.max_gates)?;
    limits.require("circuit outputs", outputs, limits.max_outputs)?;
    Ok(())
}

fn add_vectors(
    builder: &mut Builder,
    lhs: &[String],
    rhs: &[String],
) -> Result<Vec<String>, OccamError> {
    debug_assert_eq!(lhs.len(), rhs.len());
    let mut result = Vec::with_capacity(lhs.len());
    result.push(builder.gate("XOR", &lhs[0], &rhs[0])?);
    let mut carry = builder.gate("AND", &lhs[0], &rhs[0])?;
    for index in 1..lhs.len() {
        let propagate = builder.gate("XOR", &lhs[index], &rhs[index])?;
        result.push(builder.gate("XOR", &propagate, &carry)?);
        let generated = builder.gate("AND", &lhs[index], &rhs[index])?;
        let propagated = builder.gate("AND", &propagate, &carry)?;
        carry = builder.gate("OR", &generated, &propagated)?;
    }
    Ok(result)
}

#[cfg(test)]
mod tests {
    use crate::{evaluate, parse_netlist};

    use super::*;

    fn lsb_bits(value: usize, width: usize) -> Vec<bool> {
        (0..width).map(|bit| value & (1 << bit) != 0).collect()
    }

    #[test]
    fn generates_correct_four_bit_adder() {
        let circuit = parse_netlist(&ripple_carry_adder(4).unwrap()).unwrap();
        assert_eq!(circuit.gates.len(), 17);
        for x in 0..16 {
            for y in 0..16 {
                let mut input = lsb_bits(x, 4);
                input.extend(lsb_bits(y, 4));
                assert_eq!(evaluate(&circuit, &input).unwrap(), lsb_bits(x + y, 5));
            }
        }
    }

    #[test]
    fn generates_correct_four_bit_multiplier() {
        let circuit = parse_netlist(&shift_add_multiplier(4).unwrap()).unwrap();
        assert_eq!(circuit.gates.len(), 128);
        for x in 0..16 {
            for y in 0..16 {
                let mut input = lsb_bits(x, 4);
                input.extend(lsb_bits(y, 4));
                assert_eq!(evaluate(&circuit, &input).unwrap(), lsb_bits(x * y, 8));
            }
        }
    }

    #[test]
    fn reference_generators_enforce_limits_and_overflow() {
        let mut limits = DEFAULT_LIMITS;
        limits.max_gates = 1;
        assert!(matches!(
            ripple_carry_adder_with_limits(1, &limits),
            Err(OccamError::ResourceLimit {
                resource: "circuit gates",
                ..
            })
        ));
        assert!(matches!(
            shift_add_multiplier_with_limits(usize::MAX, &DEFAULT_LIMITS),
            Err(OccamError::ArithmeticOverflow { .. })
        ));
    }
}
