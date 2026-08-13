use crate::{BinaryOp, Expr, OccamError};

pub fn parse_expression(source: &str) -> Result<Expr, OccamError> {
    if source.is_empty() || source.trim() != source {
        return Err(invalid(
            source,
            "expression must use exact stable whitespace",
        ));
    }
    parse_inner(source)?.canonicalize()
}

fn parse_inner(source: &str) -> Result<Expr, OccamError> {
    match source {
        "x" => return Ok(Expr::x()),
        "y" => return Ok(Expr::y()),
        _ => {}
    }
    if source.bytes().all(|byte| byte.is_ascii_digit()) {
        if source.len() > 1 && source.starts_with('0') {
            return Err(invalid(
                source,
                "integer constants may not have leading zeroes",
            ));
        }
        let value = source
            .parse::<u64>()
            .map_err(|_| invalid(source, "integer constant is outside u64"))?;
        return Ok(Expr::constant(value));
    }
    if let Some(arguments) = call_arguments(source, "square")? {
        return Ok(Expr::square(parse_inner(arguments)?));
    }
    if let Some(arguments) = call_arguments(source, "shift_left")? {
        let (value, amount) = split_call_arguments(arguments)?;
        let amount = amount
            .parse::<u8>()
            .map_err(|_| invalid(source, "shift amount must be an unsigned byte"))?;
        return Ok(Expr::shift_left(parse_inner(value)?, amount));
    }
    if let Some(arguments) = call_arguments(source, "abs")? {
        let (lhs, rhs) = split_top_level_once(arguments, " - ")?
            .ok_or_else(|| invalid(source, "abs requires exactly one top-level subtraction"))?;
        return Ok(Expr::abs_diff(parse_inner(lhs)?, parse_inner(rhs)?));
    }
    for (name, operation) in [("min", BinaryOp::Min), ("max", BinaryOp::Max)] {
        if let Some(arguments) = call_arguments(source, name)? {
            let (lhs, rhs) = split_call_arguments(arguments)?;
            return Ok(Expr::binary(
                operation,
                parse_inner(lhs)?,
                parse_inner(rhs)?,
            ));
        }
    }
    if source.starts_with('(') && source.ends_with(')') && encloses_complete_expression(source)? {
        let inner = &source[1..source.len() - 1];
        let operators = [
            (" + ", BinaryOp::Add),
            (" - ", BinaryOp::Subtract),
            (" * ", BinaryOp::Multiply),
            (" XOR ", BinaryOp::BitXor),
            (" AND ", BinaryOp::BitAnd),
            (" OR ", BinaryOp::BitOr),
        ];
        let mut found = None;
        for (separator, operation) in operators {
            if let Some((lhs, rhs)) = split_top_level_once(inner, separator)? {
                if found.is_some() {
                    return Err(invalid(
                        source,
                        "parenthesized expression has multiple top-level operators",
                    ));
                }
                found = Some((operation, lhs, rhs));
            }
        }
        if let Some((operation, lhs, rhs)) = found {
            return Ok(Expr::binary(
                operation,
                parse_inner(lhs)?,
                parse_inner(rhs)?,
            ));
        }
    }
    Err(invalid(
        source,
        "expression does not match the stable grammar",
    ))
}

fn call_arguments<'a>(source: &'a str, name: &str) -> Result<Option<&'a str>, OccamError> {
    let Some(remainder) = source.strip_prefix(name) else {
        return Ok(None);
    };
    if !remainder.starts_with('(')
        || !remainder.ends_with(')')
        || !encloses_complete_expression(remainder)?
    {
        return Err(invalid(source, "malformed function call"));
    }
    Ok(Some(&remainder[1..remainder.len() - 1]))
}

fn split_call_arguments(source: &str) -> Result<(&str, &str), OccamError> {
    split_top_level_once(source, ", ")?
        .ok_or_else(|| invalid(source, "function requires exactly two arguments"))
}

fn split_top_level_once<'a>(
    source: &'a str,
    separator: &str,
) -> Result<Option<(&'a str, &'a str)>, OccamError> {
    let bytes = source.as_bytes();
    let separator_bytes = separator.as_bytes();
    let mut depth = 0usize;
    let mut found = None;
    let mut index = 0usize;
    while index < bytes.len() {
        match bytes[index] {
            b'(' => {
                depth = depth
                    .checked_add(1)
                    .ok_or_else(|| invalid(source, "nesting overflow"))?
            }
            b')' => {
                depth = depth
                    .checked_sub(1)
                    .ok_or_else(|| invalid(source, "unmatched closing parenthesis"))?;
            }
            _ => {}
        }
        if depth == 0 && bytes[index..].starts_with(separator_bytes) {
            if found.is_some() {
                return Err(invalid(source, "multiple top-level separators"));
            }
            found = Some(index);
            index += separator_bytes.len();
            continue;
        }
        index += 1;
    }
    if depth != 0 {
        return Err(invalid(source, "unclosed parenthesis"));
    }
    let Some(index) = found else {
        return Ok(None);
    };
    let lhs = &source[..index];
    let rhs = &source[index + separator.len()..];
    if lhs.is_empty() || rhs.is_empty() {
        return Err(invalid(source, "operator operands must be non-empty"));
    }
    Ok(Some((lhs, rhs)))
}

fn encloses_complete_expression(source: &str) -> Result<bool, OccamError> {
    let bytes = source.as_bytes();
    if bytes.first() != Some(&b'(') || bytes.last() != Some(&b')') {
        return Ok(false);
    }
    let mut depth = 0usize;
    for (index, byte) in bytes.iter().enumerate() {
        match byte {
            b'(' => {
                depth = depth
                    .checked_add(1)
                    .ok_or_else(|| invalid(source, "nesting overflow"))?
            }
            b')' => {
                depth = depth
                    .checked_sub(1)
                    .ok_or_else(|| invalid(source, "unmatched closing parenthesis"))?;
                if depth == 0 && index + 1 != bytes.len() {
                    return Ok(false);
                }
            }
            _ => {}
        }
    }
    if depth != 0 {
        return Err(invalid(source, "unclosed parenthesis"));
    }
    Ok(true)
}

fn invalid(source: &str, detail: &str) -> OccamError {
    OccamError::Validation(format!("invalid expression {source:?}: {detail}"))
}
