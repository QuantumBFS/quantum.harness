use std::time::Duration;

use crate::{Dataset, OccamError};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SynthesisLimits {
    pub max_inputs: usize,
    pub max_outputs: usize,
    pub max_truth_rows: usize,
    pub max_gates: usize,
    pub max_cnf_variables: usize,
    pub max_cnf_clauses: usize,
    pub max_cnf_literals: usize,
    pub timeout: Duration,
}

impl Default for SynthesisLimits {
    fn default() -> Self {
        Self {
            max_inputs: 8,
            max_outputs: 8,
            max_truth_rows: 256,
            max_gates: 16,
            max_cnf_variables: 2_000_000,
            max_cnf_clauses: 10_000_000,
            max_cnf_literals: 50_000_000,
            timeout: Duration::from_secs(60),
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct TruthRow {
    pub input: Vec<bool>,
    pub expected: Vec<bool>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SynthesisProblem {
    pub input_width: usize,
    pub output_width: usize,
    pub rows: Vec<TruthRow>,
}

impl SynthesisProblem {
    pub fn from_dataset(dataset: &Dataset) -> Result<Self, OccamError> {
        Self::from_dataset_with_limits(dataset, &SynthesisLimits::default())
    }

    pub fn from_dataset_with_limits(
        dataset: &Dataset,
        limits: &SynthesisLimits,
    ) -> Result<Self, OccamError> {
        let problem = Self::from_partial_dataset_with_limits(dataset, limits)?;
        let row_count = 1usize
            .checked_shl(dataset.input_width.try_into().map_err(|_| {
                OccamError::ArithmeticOverflow {
                    context: "complete truth-table row count",
                }
            })?)
            .ok_or(OccamError::ArithmeticOverflow {
                context: "complete truth-table row count",
            })?;
        require(
            "synthesis truth-table rows",
            row_count,
            limits.max_truth_rows,
        )?;
        if problem.rows.len() != row_count {
            return Err(OccamError::Validation(format!(
                "synthesis requires a complete truth table with {row_count} rows, found {}",
                problem.rows.len()
            )));
        }
        Ok(problem)
    }

    pub fn from_partial_dataset_with_limits(
        dataset: &Dataset,
        limits: &SynthesisLimits,
    ) -> Result<Self, OccamError> {
        require("synthesis inputs", dataset.input_width, limits.max_inputs)?;
        require(
            "synthesis outputs",
            dataset.output_width,
            limits.max_outputs,
        )?;
        if dataset.input_width == 0 {
            return Err(OccamError::Validation(
                "synthesis requires at least one input".into(),
            ));
        }
        if dataset.output_width == 0 {
            return Err(OccamError::Validation(
                "synthesis requires at least one output".into(),
            ));
        }
        require(
            "synthesis constraint rows",
            dataset.samples.len(),
            limits.max_truth_rows,
        )?;
        if dataset.samples.is_empty() {
            return Err(OccamError::Validation(
                "synthesis requires at least one constraint row".into(),
            ));
        }

        let mut rows = Vec::with_capacity(dataset.samples.len());
        for (sample_index, sample) in dataset.samples.iter().enumerate() {
            if sample.input.len() != dataset.input_width {
                return Err(OccamError::Validation(format!(
                    "sample {} input width {} does not match dataset input width {}",
                    sample_index + 1,
                    sample.input.len(),
                    dataset.input_width
                )));
            }
            if sample.expected.len() != dataset.output_width {
                return Err(OccamError::Validation(format!(
                    "sample {} output width {} does not match dataset output width {}",
                    sample_index + 1,
                    sample.expected.len(),
                    dataset.output_width
                )));
            }
            let assignment = sample
                .input
                .iter()
                .fold(0usize, |index, bit| (index << 1) | usize::from(*bit));
            rows.push((assignment, sample.input.clone(), sample.expected.clone()));
        }
        rows.sort_by_key(|row| row.0);
        for pair in rows.windows(2) {
            if pair[0].0 == pair[1].0 {
                let kind = if pair[0].2 == pair[1].2 {
                    "duplicate"
                } else {
                    "conflicting duplicate"
                };
                return Err(OccamError::Validation(format!(
                    "{kind} synthesis input assignment {}",
                    pair[0].0
                )));
            }
        }
        let rows = rows
            .into_iter()
            .map(|(_, input, expected)| TruthRow { input, expected })
            .collect();

        Ok(Self {
            input_width: dataset.input_width,
            output_width: dataset.output_width,
            rows,
        })
    }

    pub(crate) fn canonical_bytes(&self) -> Vec<u8> {
        let mut bytes = format!(
            "occam71-synthesis-v1\ninputs={}\noutputs={}\n",
            self.input_width, self.output_width
        )
        .into_bytes();
        for row in &self.rows {
            for bit in &row.input {
                bytes.push(if *bit { b'1' } else { b'0' });
            }
            bytes.push(b',');
            for bit in &row.expected {
                bytes.push(if *bit { b'1' } else { b'0' });
            }
            bytes.push(b'\n');
        }
        bytes
    }
}

fn require(resource: &'static str, requested: usize, limit: usize) -> Result<(), OccamError> {
    if requested > limit {
        return Err(OccamError::ResourceLimit {
            resource,
            requested,
            limit,
        });
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use crate::{Dataset, Sample, parse_dataset};

    use super::*;

    #[test]
    fn canonicalizes_complete_half_adder() {
        let dataset = parse_dataset("input,output\n11,01\n00,00\n10,10\n01,10\n").unwrap();
        let problem = SynthesisProblem::from_dataset(&dataset).unwrap();
        assert_eq!(problem.rows[0].input, [false, false]);
        assert_eq!(problem.rows[0].expected, [false, false]);
        assert_eq!(problem.rows[3].input, [true, true]);
        assert_eq!(problem.rows[3].expected, [false, true]);
    }

    #[test]
    fn accepts_complete_two_bit_adder() {
        let mut samples = Vec::new();
        for assignment in 0..16usize {
            let a = ((assignment >> 3) & 1) * 2 + ((assignment >> 2) & 1);
            let b = ((assignment >> 1) & 1) * 2 + (assignment & 1);
            let sum = a + b;
            samples.push(Sample {
                input: (0..4)
                    .map(|column| (assignment >> (3 - column)) & 1 == 1)
                    .collect(),
                expected: (0..3)
                    .map(|column| (sum >> (2 - column)) & 1 == 1)
                    .collect(),
            });
        }
        let dataset = Dataset {
            input_width: 4,
            output_width: 3,
            samples,
        };
        assert_eq!(
            SynthesisProblem::from_dataset(&dataset).unwrap().rows.len(),
            16
        );
    }

    #[test]
    fn rejects_partial_duplicate_conflicting_and_malformed_tables() {
        let partial = parse_dataset("input,output\n00,0\n01,1\n").unwrap();
        assert!(
            SynthesisProblem::from_dataset(&partial)
                .unwrap_err()
                .to_string()
                .contains("complete")
        );

        let duplicate = parse_dataset("input,output\n00,0\n00,0\n10,1\n11,0\n").unwrap();
        assert!(
            SynthesisProblem::from_dataset(&duplicate)
                .unwrap_err()
                .to_string()
                .contains("duplicate")
        );

        let conflicting = parse_dataset("input,output\n00,0\n00,1\n10,1\n11,0\n").unwrap();
        assert!(
            SynthesisProblem::from_dataset(&conflicting)
                .unwrap_err()
                .to_string()
                .contains("conflicting")
        );

        let mut malformed = parse_dataset("input,output\n0,0\n1,1\n").unwrap();
        malformed.samples[1].expected.clear();
        assert!(
            SynthesisProblem::from_dataset(&malformed)
                .unwrap_err()
                .to_string()
                .contains("output width")
        );
    }

    #[test]
    fn canonicalizes_partial_constraint_tables_for_cegis() {
        let dataset = parse_dataset("input,output\n11,0\n01,1\n").unwrap();
        let problem = SynthesisProblem::from_partial_dataset_with_limits(
            &dataset,
            &SynthesisLimits::default(),
        )
        .unwrap();
        assert_eq!(problem.rows.len(), 2);
        assert_eq!(problem.rows[0].input, [false, true]);
        assert_eq!(problem.rows[1].input, [true, true]);
    }

    #[test]
    fn rejects_oversized_problem() {
        let dataset = parse_dataset("input,output\n0,0\n1,1\n").unwrap();
        let limits = SynthesisLimits {
            max_inputs: 0,
            ..SynthesisLimits::default()
        };
        assert!(matches!(
            SynthesisProblem::from_dataset_with_limits(&dataset, &limits),
            Err(OccamError::ResourceLimit {
                resource: "synthesis inputs",
                ..
            })
        ));
    }
}
