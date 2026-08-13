use crate::{
    OccamError, ResourceLimits,
    limits::{checked_add, checked_mul},
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) struct DatasetShape {
    pub input_width: usize,
    pub output_width: usize,
    pub sample_count: usize,
}

pub(crate) fn scan_dataset(
    source: &[u8],
    limits: &ResourceLimits,
    mut visit_row: impl FnMut(usize, &[u8], &[u8]) -> Result<(), OccamError>,
) -> Result<DatasetShape, OccamError> {
    limits.require(
        "dataset source bytes",
        source.len(),
        limits.max_source_bytes,
    )?;
    if source.is_empty() {
        return Err(OccamError::Validation("dataset is empty".into()));
    }
    let mut lines = source.split(|byte| *byte == b'\n');
    let header = trim_ascii(lines.next().unwrap_or_default());
    if header != b"input,output" {
        return Err(OccamError::parse(
            "dataset",
            1,
            format!(
                "expected header input,output; got {}",
                String::from_utf8_lossy(header)
            ),
        ));
    }

    let mut widths = None;
    let mut sample_count = 0usize;
    for (index, raw_line) in lines.enumerate() {
        let line_number = index + 2;
        let line = trim_ascii(raw_line);
        if line.is_empty() {
            continue;
        }
        let mut fields = line.split(|byte| *byte == b',');
        let input = fields.next().unwrap_or_default();
        let output = fields.next().ok_or_else(|| {
            OccamError::parse("dataset", line_number, "expected exactly two CSV fields")
        })?;
        if fields.next().is_some() {
            return Err(OccamError::parse(
                "dataset",
                line_number,
                "expected exactly two CSV fields",
            ));
        }
        validate_bits(input, line_number, "input")?;
        validate_bits(output, line_number, "output")?;
        let row_widths = (input.len(), output.len());
        if row_widths.0 == 0 || row_widths.1 == 0 {
            return Err(OccamError::parse(
                "dataset",
                line_number,
                "input and output bitstrings must be non-empty",
            ));
        }
        if let Some(expected_widths) = widths {
            if row_widths != expected_widths {
                return Err(OccamError::parse(
                    "dataset",
                    line_number,
                    format!(
                        "inconsistent widths: expected input {}, output {}; got input {}, output {}",
                        expected_widths.0, expected_widths.1, row_widths.0, row_widths.1
                    ),
                ));
            }
        } else {
            limits.require("dataset input width", row_widths.0, limits.max_input_width)?;
            limits.require(
                "dataset output width",
                row_widths.1,
                limits.max_output_width,
            )?;
            widths = Some(row_widths);
        }
        let next_sample_count = checked_add(sample_count, 1, "dataset sample count")?;
        limits.require("dataset samples", next_sample_count, limits.max_samples)?;
        let row_bits = checked_add(row_widths.0, row_widths.1, "dataset bits per sample")?;
        let dataset_bits = checked_mul(row_bits, next_sample_count, "total dataset bits")?;
        limits.require("dataset bits", dataset_bits, limits.max_dataset_bits)?;
        visit_row(line_number, input, output)?;
        sample_count = next_sample_count;
    }

    let (input_width, output_width) =
        widths.ok_or_else(|| OccamError::Validation("dataset has no samples".into()))?;
    Ok(DatasetShape {
        input_width,
        output_width,
        sample_count,
    })
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

fn validate_bits(value: &[u8], line: usize, field: &str) -> Result<(), OccamError> {
    for byte in value {
        if *byte != b'0' && *byte != b'1' {
            let invalid = if byte.is_ascii() {
                format!("character {:?}", char::from(*byte))
            } else {
                format!("byte 0x{byte:02x}")
            };
            return Err(OccamError::parse(
                "dataset",
                line,
                format!("{field} contains non-bit {invalid}"),
            ));
        }
    }
    Ok(())
}
