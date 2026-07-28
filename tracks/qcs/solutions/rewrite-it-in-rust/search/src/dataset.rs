use crate::{DEFAULT_LIMITS, OccamError, ResourceLimits, dataset_scan::scan_dataset};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Sample {
    pub input: Vec<bool>,
    pub expected: Vec<bool>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Dataset {
    pub input_width: usize,
    pub output_width: usize,
    pub samples: Vec<Sample>,
}

pub fn parse_dataset(source: &str) -> Result<Dataset, OccamError> {
    parse_dataset_with_limits(source, &DEFAULT_LIMITS)
}

pub fn parse_dataset_with_limits(
    source: &str,
    limits: &ResourceLimits,
) -> Result<Dataset, OccamError> {
    let mut samples = Vec::new();
    let shape = scan_dataset(source.as_bytes(), limits, |_line, input, expected| {
        samples.push(Sample {
            input: input.iter().map(|value| *value == b'1').collect(),
            expected: expected.iter().map(|value| *value == b'1').collect(),
        });
        Ok(())
    })?;
    Ok(Dataset {
        input_width: shape.input_width,
        output_width: shape.output_width,
        samples,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_and_preserves_character_order() {
        let dataset = parse_dataset("input,output\n1010,011\n").unwrap();
        assert_eq!(dataset.input_width, 4);
        assert_eq!(dataset.output_width, 3);
        assert_eq!(dataset.samples[0].input, vec![true, false, true, false]);
        assert_eq!(dataset.samples[0].expected, vec![false, true, true]);
    }

    #[test]
    fn rejects_bad_header() {
        assert!(
            parse_dataset("x,y\n0,1")
                .unwrap_err()
                .to_string()
                .contains("header")
        );
    }

    #[test]
    fn rejects_non_bits() {
        assert!(
            parse_dataset("input,output\n0x,1")
                .unwrap_err()
                .to_string()
                .contains("non-bit")
        );
    }

    #[test]
    fn rejects_wrong_field_count() {
        assert!(parse_dataset("input,output\n0").is_err());
        assert!(parse_dataset("input,output\n0,1,1").is_err());
    }

    #[test]
    fn rejects_inconsistent_widths() {
        assert!(parse_dataset("input,output\n00,1\n0,1").is_err());
        assert!(parse_dataset("input,output\n00,1\n00,11").is_err());
    }

    #[test]
    fn rejects_empty_dataset() {
        assert!(parse_dataset("input,output\n").is_err());
    }

    #[test]
    fn accepts_crlf_and_blank_lines() {
        let dataset = parse_dataset("input,output\r\n\r\n  01,10  \r\n\r\n11,00\r\n").unwrap();
        assert_eq!(dataset.input_width, 2);
        assert_eq!(dataset.output_width, 2);
        assert_eq!(dataset.samples.len(), 2);
    }

    #[test]
    fn rejects_empty_bitstrings() {
        assert!(
            parse_dataset("input,output\n,1")
                .unwrap_err()
                .to_string()
                .contains("non-empty")
        );
        assert!(
            parse_dataset("input,output\n1,")
                .unwrap_err()
                .to_string()
                .contains("non-empty")
        );
    }

    #[test]
    fn enforces_width_sample_and_source_limits() {
        let mut limits = DEFAULT_LIMITS;
        limits.max_input_width = 1;
        assert!(matches!(
            parse_dataset_with_limits("input,output\n00,1", &limits),
            Err(OccamError::ResourceLimit {
                resource: "dataset input width",
                ..
            })
        ));

        let mut limits = DEFAULT_LIMITS;
        limits.max_samples = 1;
        assert!(matches!(
            parse_dataset_with_limits("input,output\n0,1\n1,0", &limits),
            Err(OccamError::ResourceLimit {
                resource: "dataset samples",
                ..
            })
        ));

        let mut limits = DEFAULT_LIMITS;
        limits.max_source_bytes = 3;
        assert!(matches!(
            parse_dataset_with_limits("input,output\n0,1", &limits),
            Err(OccamError::ResourceLimit {
                resource: "dataset source bytes",
                ..
            })
        ));
    }
}
