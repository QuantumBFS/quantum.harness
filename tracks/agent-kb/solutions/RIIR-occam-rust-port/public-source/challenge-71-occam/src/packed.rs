use crate::{
    Circuit, CompiledCircuit, DEFAULT_LIMITS, Dataset, OccamError, Operand, ResourceLimits, Source,
    VerificationMetrics,
    dataset_scan::{DatasetShape, scan_dataset},
    limits::{checked_add, checked_mul},
    verify_compiled_prepacked_with_limits,
};

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PackedDataset {
    sample_count: usize,
    input_width: usize,
    output_width: usize,
    input_words: Vec<u64>,
    expected_words: Vec<u64>,
    block_count: usize,
    tail_mask: u64,
}

impl PackedDataset {
    pub fn sample_count(&self) -> usize {
        self.sample_count
    }

    pub fn input_width(&self) -> usize {
        self.input_width
    }

    pub fn output_width(&self) -> usize {
        self.output_width
    }

    pub fn block_count(&self) -> usize {
        self.block_count
    }

    pub fn input_column(&self, index: usize) -> Option<&[u64]> {
        column(&self.input_words, self.block_count, index)
    }

    pub fn expected_column(&self, index: usize) -> Option<&[u64]> {
        column(&self.expected_words, self.block_count, index)
    }

    pub(crate) fn valid_mask(&self, block: usize) -> u64 {
        if block == self.block_count - 1 {
            self.tail_mask
        } else {
            u64::MAX
        }
    }
}

fn column(words: &[u64], block_count: usize, index: usize) -> Option<&[u64]> {
    let start = index.checked_mul(block_count)?;
    let end = start.checked_add(block_count)?;
    words.get(start..end)
}

fn zeroed_words(count: usize, context: &str) -> Result<Vec<u64>, OccamError> {
    let mut words = Vec::new();
    words.try_reserve_exact(count).map_err(|error| {
        OccamError::Validation(format!(
            "cannot allocate {context} ({count} words): {error}"
        ))
    })?;
    words.resize(count, 0);
    Ok(words)
}

fn allocate_packed(
    shape: DatasetShape,
    limits: &ResourceLimits,
) -> Result<PackedDataset, OccamError> {
    let block_count = shape.sample_count.div_ceil(64);
    let remainder = shape.sample_count % 64;
    let tail_mask = if remainder == 0 {
        u64::MAX
    } else {
        (1u64 << remainder) - 1
    };
    let input_word_count = checked_mul(shape.input_width, block_count, "packed input word count")?;
    let expected_word_count =
        checked_mul(shape.output_width, block_count, "packed output word count")?;
    let total_words = checked_add(
        input_word_count,
        expected_word_count,
        "packed dataset word count",
    )?;
    limits.require("packed dataset words", total_words, limits.max_packed_words)?;
    Ok(PackedDataset {
        sample_count: shape.sample_count,
        input_width: shape.input_width,
        output_width: shape.output_width,
        input_words: zeroed_words(input_word_count, "packed inputs")?,
        expected_words: zeroed_words(expected_word_count, "packed outputs")?,
        block_count,
        tail_mask,
    })
}

pub fn pack_dataset(dataset: &Dataset) -> Result<PackedDataset, OccamError> {
    pack_dataset_with_limits(dataset, &DEFAULT_LIMITS)
}

pub fn pack_dataset_with_limits(
    dataset: &Dataset,
    limits: &ResourceLimits,
) -> Result<PackedDataset, OccamError> {
    let sample_count = dataset.samples.len();
    if sample_count == 0 {
        return Err(OccamError::Validation("dataset has no samples".into()));
    }
    limits.require("dataset samples", sample_count, limits.max_samples)?;
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
    let row_bits = checked_add(
        dataset.input_width,
        dataset.output_width,
        "dataset bits per sample",
    )?;
    let dataset_bits = checked_mul(row_bits, sample_count, "total dataset bits")?;
    limits.require("dataset bits", dataset_bits, limits.max_dataset_bits)?;
    let mut packed = allocate_packed(
        DatasetShape {
            input_width: dataset.input_width,
            output_width: dataset.output_width,
            sample_count,
        },
        limits,
    )?;
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
        let block = sample_index / 64;
        let bit = sample_index % 64;
        for (column_index, value) in sample.input.iter().enumerate() {
            packed.input_words[column_index * packed.block_count + block] |=
                u64::from(*value) << bit;
        }
        for (column_index, value) in sample.expected.iter().enumerate() {
            packed.expected_words[column_index * packed.block_count + block] |=
                u64::from(*value) << bit;
        }
    }
    Ok(packed)
}

pub fn parse_packed_dataset(source: impl AsRef<[u8]>) -> Result<PackedDataset, OccamError> {
    parse_packed_dataset_with_limits(source, &DEFAULT_LIMITS)
}

pub fn parse_packed_dataset_with_limits(
    source: impl AsRef<[u8]>,
    limits: &ResourceLimits,
) -> Result<PackedDataset, OccamError> {
    let source = source.as_ref();
    let shape = scan_dataset(source, limits, |_line, _input, _expected| Ok(()))?;
    let mut packed = allocate_packed(shape, limits)?;
    let mut sample_index = 0usize;
    let second_shape = scan_dataset(source, limits, |_line, input, expected| {
        let block = sample_index / 64;
        let bit = sample_index % 64;
        for (column_index, value) in input.iter().enumerate() {
            packed.input_words[column_index * packed.block_count + block] |=
                u64::from(*value == b'1') << bit;
        }
        for (column_index, value) in expected.iter().enumerate() {
            packed.expected_words[column_index * packed.block_count + block] |=
                u64::from(*value == b'1') << bit;
        }
        sample_index += 1;
        Ok(())
    })?;
    debug_assert_eq!(shape, second_shape);
    Ok(packed)
}

pub fn verify_packed(
    circuit: &Circuit,
    dataset: &Dataset,
) -> Result<VerificationMetrics, OccamError> {
    verify_prepacked(circuit, &pack_dataset(dataset)?)
}

pub fn verify_prepacked(
    circuit: &Circuit,
    dataset: &PackedDataset,
) -> Result<VerificationMetrics, OccamError> {
    verify_prepacked_with_limits(circuit, dataset, &DEFAULT_LIMITS)
}

pub fn verify_prepacked_with_limits(
    circuit: &Circuit,
    dataset: &PackedDataset,
    limits: &ResourceLimits,
) -> Result<VerificationMetrics, OccamError> {
    let compiled = CompiledCircuit::new_with_limits(circuit, limits)?;
    verify_compiled_prepacked_with_limits(&compiled, dataset, limits)
}

#[doc(hidden)]
pub fn verify_prepacked_interpreted(
    circuit: &Circuit,
    dataset: &PackedDataset,
) -> Result<VerificationMetrics, OccamError> {
    verify_prepacked_interpreted_with_limits(circuit, dataset, &DEFAULT_LIMITS)
}

#[doc(hidden)]
pub fn verify_prepacked_interpreted_with_limits(
    circuit: &Circuit,
    dataset: &PackedDataset,
    limits: &ResourceLimits,
) -> Result<VerificationMetrics, OccamError> {
    validate_verification_dimensions(circuit, dataset, limits)?;
    let wire_word_count = checked_mul(
        circuit.wire_count,
        dataset.block_count,
        "packed wire word count",
    )?;
    limits.require(
        "packed wire words",
        wire_word_count,
        limits.max_packed_words,
    )?;
    let mut wires = zeroed_words(wire_word_count, "packed wires")?;
    for gate in &circuit.gates {
        for block in 0..dataset.block_count {
            let lhs = resolve_flat_word(gate.lhs, block, dataset, &wires)?;
            let rhs = resolve_flat_word(gate.rhs, block, dataset, &wires)?;
            let offset = gate
                .output
                .checked_mul(dataset.block_count)
                .and_then(|base| base.checked_add(block))
                .ok_or(OccamError::ArithmeticOverflow {
                    context: "packed wire offset",
                })?;
            let output = wires.get_mut(offset).ok_or_else(|| {
                OccamError::Validation(format!(
                    "wire column {}, block {block} is missing",
                    gate.output
                ))
            })?;
            *output = gate.op.apply_word(lhs, rhs);
        }
    }
    collect_metrics(circuit, dataset, |operand, block| {
        resolve_flat_word(operand, block, dataset, &wires)
    })
}

#[doc(hidden)]
pub fn verify_prepacked_reference(
    circuit: &Circuit,
    dataset: &PackedDataset,
) -> Result<VerificationMetrics, OccamError> {
    validate_verification_dimensions(circuit, dataset, &DEFAULT_LIMITS)?;
    let wire_word_count = checked_mul(
        circuit.wire_count,
        dataset.block_count,
        "reference packed wire word count",
    )?;
    DEFAULT_LIMITS.require(
        "packed wire words",
        wire_word_count,
        DEFAULT_LIMITS.max_packed_words,
    )?;
    let mut wires = Vec::new();
    wires
        .try_reserve_exact(circuit.wire_count)
        .map_err(|error| {
            OccamError::Validation(format!(
                "cannot allocate reference packed wire columns: {error}"
            ))
        })?;
    for _ in 0..circuit.wire_count {
        wires.push(zeroed_words(
            dataset.block_count,
            "reference packed wire column",
        )?);
    }
    for gate in &circuit.gates {
        for block in 0..dataset.block_count {
            let lhs = resolve_nested_word(gate.lhs, block, dataset, &wires)?;
            let rhs = resolve_nested_word(gate.rhs, block, dataset, &wires)?;
            let output = wires
                .get_mut(gate.output)
                .and_then(|wire| wire.get_mut(block))
                .ok_or_else(|| {
                    OccamError::Validation(format!(
                        "wire column {}, block {block} is missing",
                        gate.output
                    ))
                })?;
            *output = gate.op.apply_word(lhs, rhs);
        }
    }
    collect_metrics(circuit, dataset, |operand, block| {
        resolve_nested_word(operand, block, dataset, &wires)
    })
}

fn validate_verification_dimensions(
    circuit: &Circuit,
    dataset: &PackedDataset,
    limits: &ResourceLimits,
) -> Result<(), OccamError> {
    if circuit.input_count != dataset.input_width() {
        return Err(OccamError::Validation(format!(
            "dataset input width {} does not match circuit INPUTS {}",
            dataset.input_width(),
            circuit.input_count
        )));
    }
    if circuit.outputs.len() != dataset.output_width() {
        return Err(OccamError::Validation(format!(
            "circuit has {} outputs, dataset has {}",
            circuit.outputs.len(),
            dataset.output_width()
        )));
    }
    if circuit.wire_count != circuit.gates.len() {
        return Err(OccamError::Validation(format!(
            "circuit wire count {} does not match gate count {}",
            circuit.wire_count,
            circuit.gates.len()
        )));
    }
    limits.require("circuit inputs", circuit.input_count, limits.max_inputs)?;
    limits.require("circuit gates", circuit.gates.len(), limits.max_gates)?;
    limits.require("circuit outputs", circuit.outputs.len(), limits.max_outputs)?;
    limits.require("dataset samples", dataset.sample_count, limits.max_samples)?;
    Ok(())
}

fn collect_metrics(
    circuit: &Circuit,
    dataset: &PackedDataset,
    resolve: impl Fn(Operand, usize) -> Result<u64, OccamError>,
) -> Result<VerificationMetrics, OccamError> {
    let mut mismatches = zeroed_words(dataset.block_count, "packed mismatch blocks")?;
    let mut correct_bits = 0usize;
    for (output_index, operand) in circuit.outputs.iter().enumerate() {
        let expected = dataset.expected_column(output_index).ok_or_else(|| {
            OccamError::Validation(format!("packed output column {output_index} is missing"))
        })?;
        for block in 0..dataset.block_count {
            let mask = dataset.valid_mask(block);
            let predicted = resolve(*operand, block)?;
            let different = (predicted ^ expected[block]) & mask;
            correct_bits = checked_add(
                correct_bits,
                ((!different) & mask).count_ones() as usize,
                "correct verification bits",
            )?;
            mismatches[block] |= different;
        }
    }
    let exact_matches = mismatches
        .iter()
        .enumerate()
        .map(|(block, different)| {
            let mask = dataset.valid_mask(block);
            (mask.count_ones() - (different & mask).count_ones()) as usize
        })
        .sum();

    Ok(VerificationMetrics {
        samples: dataset.sample_count,
        gate_count: circuit.gates.len(),
        exact_matches,
        correct_bits,
        total_bits: checked_mul(
            dataset.sample_count,
            dataset.output_width(),
            "verification bit count",
        )?,
    })
}

fn resolve_flat_word(
    operand: Operand,
    block: usize,
    dataset: &PackedDataset,
    wires: &[u64],
) -> Result<u64, OccamError> {
    let value = match operand.source {
        Source::Input(index) => dataset
            .input_column(index)
            .and_then(|column| column.get(block))
            .copied()
            .ok_or_else(|| {
                OccamError::Validation(format!(
                    "packed input column {index}, block {block} is missing"
                ))
            })?,
        Source::Wire(index) => index
            .checked_mul(dataset.block_count)
            .and_then(|base| base.checked_add(block))
            .and_then(|offset| wires.get(offset))
            .copied()
            .ok_or_else(|| {
                OccamError::Validation(format!("wire column {index}, block {block} is missing"))
            })?,
    };
    Ok(if operand.inverted { !value } else { value })
}

fn resolve_nested_word(
    operand: Operand,
    block: usize,
    dataset: &PackedDataset,
    wires: &[Vec<u64>],
) -> Result<u64, OccamError> {
    let value = match operand.source {
        Source::Input(index) => dataset
            .input_column(index)
            .and_then(|column| column.get(block))
            .copied()
            .ok_or_else(|| {
                OccamError::Validation(format!(
                    "packed input column {index}, block {block} is missing"
                ))
            })?,
        Source::Wire(index) => wires
            .get(index)
            .and_then(|wire| wire.get(block))
            .copied()
            .ok_or_else(|| {
                OccamError::Validation(format!("wire column {index}, block {block} is missing"))
            })?,
    };
    Ok(if operand.inverted { !value } else { value })
}

#[cfg(test)]
mod tests {
    use crate::{Sample, parse_netlist, verify};

    use super::*;

    fn boundary_dataset(samples: usize) -> Dataset {
        Dataset {
            input_width: 2,
            output_width: 3,
            samples: (0..samples)
                .map(|index| {
                    let lhs = index % 2 != 0;
                    let rhs = index % 3 == 0;
                    Sample {
                        input: vec![lhs, rhs],
                        expected: vec![lhs ^ rhs, !lhs, rhs],
                    }
                })
                .collect(),
        }
    }

    #[test]
    fn matches_scalar_at_word_boundaries() {
        let circuit = parse_netlist("INPUTS 2\nw1 = XOR x1 x2\nOUTPUTS w1 ~x1 x2").unwrap();
        for samples in [1, 63, 64, 65, 127, 128, 129] {
            let dataset = boundary_dataset(samples);
            assert_eq!(
                verify_packed(&circuit, &dataset).unwrap(),
                verify(&circuit, &dataset).unwrap(),
                "sample count {samples}"
            );
        }
    }

    #[test]
    fn complement_gate_padding_never_counts_as_samples() {
        let circuit = parse_netlist("INPUTS 2\nw1 = NAND x1 x2\nOUTPUTS ~w1").unwrap();
        for samples in [1, 63, 65, 129] {
            let dataset = Dataset {
                input_width: 2,
                output_width: 1,
                samples: (0..samples)
                    .map(|index| Sample {
                        input: vec![index % 2 == 0, index % 3 == 0],
                        expected: vec![index % 5 == 0],
                    })
                    .collect(),
            };
            assert_eq!(
                verify_packed(&circuit, &dataset).unwrap(),
                verify(&circuit, &dataset).unwrap()
            );
        }
    }

    #[test]
    fn flat_wire_arena_obeys_word_limit() {
        let circuit = parse_netlist("INPUTS 2\nw1 = XOR x1 x2\nOUTPUTS w1 ~x1 x2").unwrap();
        let packed = pack_dataset(&boundary_dataset(65)).unwrap();
        let mut limits = DEFAULT_LIMITS;
        limits.max_packed_words = 1;
        assert!(matches!(
            verify_prepacked_interpreted_with_limits(&circuit, &packed, &limits),
            Err(OccamError::ResourceLimit {
                resource: "packed wire words",
                ..
            })
        ));
    }
}
