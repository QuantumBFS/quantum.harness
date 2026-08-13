use occam71_rust::{Dataset, Sample, pack_dataset};

fn dataset(samples: usize) -> Dataset {
    Dataset {
        input_width: 3,
        output_width: 2,
        samples: (0..samples)
            .map(|index| Sample {
                input: vec![index % 2 == 0, index % 3 == 0, index % 5 == 0],
                expected: vec![index % 7 == 0, index % 11 == 0],
            })
            .collect(),
    }
}

fn reference_column(dataset: &Dataset, input: bool, column: usize) -> Vec<u64> {
    let mut words = vec![0; dataset.samples.len().div_ceil(64)];
    for (sample_index, sample) in dataset.samples.iter().enumerate() {
        let value = if input {
            sample.input[column]
        } else {
            sample.expected[column]
        };
        words[sample_index / 64] |= u64::from(value) << (sample_index % 64);
    }
    words
}

#[test]
fn flat_columns_match_reference_at_word_boundaries() {
    for sample_count in [1, 63, 64, 65, 129] {
        let scalar = dataset(sample_count);
        let packed = pack_dataset(&scalar).unwrap();
        assert_eq!(packed.sample_count(), sample_count);
        assert_eq!(packed.input_width(), scalar.input_width);
        assert_eq!(packed.output_width(), scalar.output_width);
        assert_eq!(packed.block_count(), sample_count.div_ceil(64));
        for column in 0..scalar.input_width {
            assert_eq!(
                packed.input_column(column).unwrap(),
                reference_column(&scalar, true, column)
            );
        }
        for column in 0..scalar.output_width {
            assert_eq!(
                packed.expected_column(column).unwrap(),
                reference_column(&scalar, false, column)
            );
        }
        assert!(packed.input_column(scalar.input_width).is_none());
        assert!(packed.expected_column(scalar.output_width).is_none());
    }
}

#[test]
fn rejects_structurally_inconsistent_scalar_rows() {
    let mut scalar = dataset(1);
    scalar.samples[0].input.pop();
    assert!(
        pack_dataset(&scalar)
            .unwrap_err()
            .to_string()
            .contains("input width")
    );

    let mut scalar = dataset(1);
    scalar.samples[0].expected.push(false);
    assert!(
        pack_dataset(&scalar)
            .unwrap_err()
            .to_string()
            .contains("output width")
    );
}
