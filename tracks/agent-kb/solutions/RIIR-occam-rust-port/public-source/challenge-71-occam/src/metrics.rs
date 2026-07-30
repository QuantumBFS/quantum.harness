use crate::{
    Circuit, DEFAULT_LIMITS, Dataset, OccamError, ResourceLimits, evaluate_with_limits,
    limits::{checked_add, checked_mul},
};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct VerificationMetrics {
    pub samples: usize,
    pub gate_count: usize,
    pub exact_matches: usize,
    pub correct_bits: usize,
    pub total_bits: usize,
}

impl VerificationMetrics {
    pub fn exact_match_accuracy(&self) -> f64 {
        self.exact_matches as f64 / self.samples as f64
    }

    pub fn bit_accuracy(&self) -> f64 {
        self.correct_bits as f64 / self.total_bits as f64
    }
}

pub fn verify(circuit: &Circuit, dataset: &Dataset) -> Result<VerificationMetrics, OccamError> {
    verify_with_limits(circuit, dataset, &DEFAULT_LIMITS)
}

pub fn verify_with_limits(
    circuit: &Circuit,
    dataset: &Dataset,
    limits: &ResourceLimits,
) -> Result<VerificationMetrics, OccamError> {
    if circuit.input_count != dataset.input_width {
        return Err(OccamError::Validation(format!(
            "dataset input width {} does not match circuit INPUTS {}",
            dataset.input_width, circuit.input_count
        )));
    }
    if circuit.outputs.len() != dataset.output_width {
        return Err(OccamError::Validation(format!(
            "circuit has {} outputs, dataset has {}",
            circuit.outputs.len(),
            dataset.output_width
        )));
    }
    limits.require(
        "dataset input width",
        dataset.input_width,
        limits.max_input_width,
    )?;
    limits.require(
        "dataset output width",
        dataset.output_width,
        limits.max_output_width,
    )?;
    limits.require("dataset samples", dataset.samples.len(), limits.max_samples)?;
    let row_bits = checked_add(
        dataset.input_width,
        dataset.output_width,
        "dataset bits per sample",
    )?;
    let dataset_bits = checked_mul(row_bits, dataset.samples.len(), "total dataset bits")?;
    limits.require("dataset bits", dataset_bits, limits.max_dataset_bits)?;

    let mut exact_matches = 0;
    let mut correct_bits = 0;
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
        let predicted = evaluate_with_limits(circuit, &sample.input, limits)?;
        if predicted == sample.expected {
            exact_matches += 1;
        }
        correct_bits = checked_add(
            correct_bits,
            predicted
                .iter()
                .zip(&sample.expected)
                .filter(|(predicted, expected)| predicted == expected)
                .count(),
            "scalar correct bit count",
        )?;
    }

    Ok(VerificationMetrics {
        samples: dataset.samples.len(),
        gate_count: circuit.gates.len(),
        exact_matches,
        correct_bits,
        total_bits: checked_mul(
            dataset.samples.len(),
            dataset.output_width,
            "verification bit count",
        )?,
    })
}

#[cfg(test)]
mod tests {
    use crate::{parse_dataset, parse_netlist};

    use super::*;

    #[test]
    fn counts_exact_matches_and_correct_bits() {
        let circuit = parse_netlist("INPUTS 2\nw1 = XOR x1 x2\nOUTPUTS w1").unwrap();
        let dataset = parse_dataset("input,output\n00,0\n01,1\n10,0\n11,0").unwrap();
        let metrics = verify(&circuit, &dataset).unwrap();
        assert_eq!(metrics.samples, 4);
        assert_eq!(metrics.gate_count, 1);
        assert_eq!(metrics.exact_matches, 3);
        assert_eq!(metrics.correct_bits, 3);
        assert_eq!(metrics.total_bits, 4);
        assert_eq!(metrics.exact_match_accuracy(), 0.75);
        assert_eq!(metrics.bit_accuracy(), 0.75);
    }

    #[test]
    fn rejects_input_and_output_width_mismatches() {
        let circuit = parse_netlist("INPUTS 2\nOUTPUTS x1").unwrap();
        let bad_input = parse_dataset("input,output\n0,0").unwrap();
        let bad_output = parse_dataset("input,output\n00,00").unwrap();
        assert!(verify(&circuit, &bad_input).is_err());
        assert!(verify(&circuit, &bad_output).is_err());
    }

    #[test]
    fn rejects_inconsistent_public_dataset_rows() {
        let circuit = parse_netlist("INPUTS 2\nOUTPUTS x1").unwrap();
        let mut dataset = parse_dataset("input,output\n00,0").unwrap();
        dataset.samples[0].expected.clear();
        assert!(verify(&circuit, &dataset).is_err());
    }
}
