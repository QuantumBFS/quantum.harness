use std::collections::HashSet;

use crate::{
    DEFAULT_LIMITS, OccamError, ResourceLimits,
    limits::{checked_add, checked_mul},
};

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct TestInputs {
    pub input_width: usize,
    pub rows: Vec<Vec<bool>>,
}

pub fn decode_lsb(bits: &[bool]) -> Result<u64, OccamError> {
    if bits.len() > u64::BITS as usize {
        return Err(OccamError::Validation(format!(
            "cannot decode {} bits into u64",
            bits.len()
        )));
    }
    Ok(bits
        .iter()
        .enumerate()
        .fold(0u64, |value, (bit, set)| value | (u64::from(*set) << bit)))
}

pub fn encode_lsb(value: u64, width: usize) -> Result<Vec<bool>, OccamError> {
    if width == 0 || width > u64::BITS as usize {
        return Err(OccamError::Validation(format!(
            "encoded bit width must be in 1..=64, got {width}"
        )));
    }
    if width < u64::BITS as usize && value >= (1u64 << width) {
        return Err(OccamError::Validation(format!(
            "value {value} does not fit in {width} bits"
        )));
    }
    Ok((0..width).map(|bit| value & (1u64 << bit) != 0).collect())
}

pub fn parse_test_inputs(source: &str) -> Result<TestInputs, OccamError> {
    parse_test_inputs_with_limits(source, &DEFAULT_LIMITS)
}

pub fn parse_test_inputs_with_limits(
    source: &str,
    limits: &ResourceLimits,
) -> Result<TestInputs, OccamError> {
    limits.require(
        "test input source bytes",
        source.len(),
        limits.max_source_bytes,
    )?;
    if source.is_empty() {
        return Err(OccamError::Validation("test input dataset is empty".into()));
    }

    let mut lines = source.as_bytes().split(|byte| *byte == b'\n');
    let header = trim_ascii(lines.next().unwrap_or_default());
    if header != b"input" {
        return Err(OccamError::parse(
            "test inputs",
            1,
            format!(
                "expected header input; got {}",
                String::from_utf8_lossy(header)
            ),
        ));
    }

    let mut input_width = None;
    let mut rows = Vec::new();
    let mut seen = HashSet::<Vec<u8>>::new();
    for (index, raw_line) in lines.enumerate() {
        let line_number = index + 2;
        let input = trim_ascii(raw_line);
        if input.is_empty() {
            continue;
        }
        if input.contains(&b',') {
            return Err(OccamError::parse(
                "test inputs",
                line_number,
                "expected exactly one CSV field",
            ));
        }
        validate_bits(input, line_number)?;
        if let Some(expected) = input_width {
            if input.len() != expected {
                return Err(OccamError::parse(
                    "test inputs",
                    line_number,
                    format!(
                        "inconsistent input width: expected {expected}, got {}",
                        input.len()
                    ),
                ));
            }
        } else {
            limits.require("test input width", input.len(), limits.max_input_width)?;
            input_width = Some(input.len());
        }
        if !seen.insert(input.to_vec()) {
            return Err(OccamError::parse(
                "test inputs",
                line_number,
                "duplicate input row",
            ));
        }
        let next_rows = checked_add(rows.len(), 1, "test input row count")?;
        limits.require("test input rows", next_rows, limits.max_samples)?;
        let dataset_bits = checked_mul(input.len(), next_rows, "test input dataset bits")?;
        limits.require("test input bits", dataset_bits, limits.max_dataset_bits)?;
        rows.push(input.iter().map(|byte| *byte == b'1').collect());
    }

    let input_width =
        input_width.ok_or_else(|| OccamError::Validation("test inputs have no rows".into()))?;
    Ok(TestInputs { input_width, rows })
}

pub fn parse_commitment(source: &str) -> Result<String, OccamError> {
    let fields: Vec<_> = source.split_ascii_whitespace().collect();
    if fields.len() != 2 || fields[1] != "test_outputs.csv" {
        return Err(OccamError::Validation(
            "commitment must contain '<lowercase-sha256>  test_outputs.csv'".into(),
        ));
    }
    let digest = fields[0];
    if digest.len() != 64
        || !digest
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return Err(OccamError::Validation(
            "commitment SHA-256 must be exactly 64 lowercase hexadecimal characters".into(),
        ));
    }
    Ok(digest.to_owned())
}

fn trim_ascii(mut value: &[u8]) -> &[u8] {
    while value.first().is_some_and(|byte| byte.is_ascii_whitespace()) {
        value = &value[1..];
    }
    while value.last().is_some_and(|byte| byte.is_ascii_whitespace()) {
        value = &value[..value.len() - 1];
    }
    value
}

fn validate_bits(value: &[u8], line: usize) -> Result<(), OccamError> {
    if value.is_empty() {
        return Err(OccamError::parse(
            "test inputs",
            line,
            "input bitstring must be non-empty",
        ));
    }
    for byte in value {
        if *byte != b'0' && *byte != b'1' {
            let invalid = if byte.is_ascii() {
                format!("character {:?}", char::from(*byte))
            } else {
                format!("byte 0x{byte:02x}")
            };
            return Err(OccamError::parse(
                "test inputs",
                line,
                format!("input contains non-bit {invalid}"),
            ));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn enforces_test_input_limits() {
        let mut limits = DEFAULT_LIMITS;
        limits.max_input_width = 1;
        assert!(matches!(
            parse_test_inputs_with_limits("input\n00\n", &limits),
            Err(OccamError::ResourceLimit {
                resource: "test input width",
                ..
            })
        ));

        let mut limits = DEFAULT_LIMITS;
        limits.max_samples = 1;
        assert!(matches!(
            parse_test_inputs_with_limits("input\n0\n1\n", &limits),
            Err(OccamError::ResourceLimit {
                resource: "test input rows",
                ..
            })
        ));

        let mut limits = DEFAULT_LIMITS;
        limits.max_source_bytes = 3;
        assert!(matches!(
            parse_test_inputs_with_limits("input\n0\n", &limits),
            Err(OccamError::ResourceLimit {
                resource: "test input source bytes",
                ..
            })
        ));
    }
}
