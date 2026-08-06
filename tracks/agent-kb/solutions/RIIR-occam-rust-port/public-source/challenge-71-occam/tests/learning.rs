use std::{fs, path::PathBuf};

use occam71_rust::{
    ArithmeticFamily, CircuitBuilder, DEFAULT_LIMITS, Dataset, GateOp, LearnRequest, Sample,
    Signal, decode_lsb, encode_lsb, evaluate, infer_unique_family, learn_instance,
    parse_commitment, parse_dataset, parse_netlist, parse_test_inputs, prediction_csv_from_circuit,
    score_candidates, sha256_hex, synthesize_family, write_instance_artifacts, write_manifest,
};

fn bits(value: u64, width: usize) -> Vec<bool> {
    (0..width).map(|bit| value & (1u64 << bit) != 0).collect()
}

fn sample(family: ArithmeticFamily, operand_bits: usize, x: u64, y: u64) -> Sample {
    let mut input = bits(x, operand_bits);
    input.extend(bits(y, operand_bits));
    Sample {
        input,
        expected: bits(
            family.evaluate(x, y, operand_bits).unwrap(),
            family.output_width(operand_bits).unwrap(),
        ),
    }
}

#[test]
fn parses_lsb_first_test_inputs_and_commitment() {
    let inputs = parse_test_inputs("input\n1001\n0110\n").unwrap();
    assert_eq!(inputs.input_width, 4);
    assert_eq!(inputs.rows.len(), 2);
    assert_eq!(inputs.rows[0], vec![true, false, false, true]);

    let hash = "51e3f026def41778ecd0d7dcaee9f970b9937488e6716891932b73824c16d4c7";
    assert_eq!(
        parse_commitment(&format!("{hash}  test_outputs.csv\n")).unwrap(),
        hash
    );
}

#[test]
fn lsb_conversion_round_trips() {
    for width in 1..=16 {
        for value in [0, 1, (1u64 << width) - 1, (1u64 << width) / 3] {
            assert_eq!(
                decode_lsb(&encode_lsb(value, width).unwrap()).unwrap(),
                value
            );
        }
    }
    assert!(encode_lsb(8, 3).is_err());
    assert!(decode_lsb(&[true; 65]).is_err());
}

#[test]
fn family_widths_and_boundary_values_are_checked() {
    assert_eq!(ArithmeticFamily::Add.output_width(8).unwrap(), 9);
    assert_eq!(ArithmeticFamily::AbsDiff.output_width(8).unwrap(), 8);
    assert_eq!(ArithmeticFamily::Multiply.output_width(8).unwrap(), 16);
    assert_eq!(ArithmeticFamily::SumOfSquares.output_width(5).unwrap(), 11);
    assert_eq!(ArithmeticFamily::AbsDiff.evaluate(0, 255, 8).unwrap(), 255);
    assert_eq!(
        ArithmeticFamily::Multiply.evaluate(255, 255, 8).unwrap(),
        65_025
    );
    assert_eq!(
        ArithmeticFamily::SumOfSquares.evaluate(31, 31, 5).unwrap(),
        1_922
    );
    assert!(ArithmeticFamily::Add.output_width(0).is_err());
    assert!(ArithmeticFamily::Add.output_width(32).is_err());
}

#[test]
fn training_rows_identify_each_supported_family() {
    for family in ArithmeticFamily::ALL {
        let operand_bits = 4;
        let output_width = family.output_width(operand_bits).unwrap();
        let samples = [(0, 0), (1, 3), (7, 2), (15, 15), (9, 4)]
            .into_iter()
            .map(|(x, y)| sample(family, operand_bits, x, y))
            .collect();
        let scores = score_candidates(&Dataset {
            input_width: operand_bits * 2,
            output_width,
            samples,
        })
        .unwrap();
        let perfect: Vec<_> = scores
            .iter()
            .filter(|score| score.mismatches == 0)
            .collect();
        assert_eq!(perfect.len(), 1, "{family:?}: {scores:?}");
        assert_eq!(perfect[0].family, family);
    }
}

#[test]
fn candidate_scores_record_first_one_based_mismatch() {
    let mut wrong = sample(ArithmeticFamily::Add, 3, 1, 2);
    wrong.expected[0] ^= true;
    let dataset = Dataset {
        input_width: 6,
        output_width: 4,
        samples: vec![sample(ArithmeticFamily::Add, 3, 0, 0), wrong],
    };
    let scores = score_candidates(&dataset).unwrap();
    let add = scores
        .iter()
        .find(|score| score.family == ArithmeticFamily::Add)
        .unwrap();
    assert_eq!(add.evaluated_rows, 2);
    assert_eq!(add.exact_matches, 1);
    assert_eq!(add.mismatches, 1);
    assert_eq!(add.first_mismatch_row, Some(2));
}

#[test]
fn strict_input_and_family_validation_rejects_bad_data() {
    for source in [
        "input\n",
        "inputs\n0\n",
        "input\n\n",
        "input\n01\n0\n",
        "input\n01\n01\n",
        "input\n0x\n",
        "input\n0,1\n",
    ] {
        assert!(parse_test_inputs(source).is_err(), "{source:?}");
    }

    for commitment in [
        "",
        "ABCDEF test_outputs.csv",
        "51e3f026def41778ecd0d7dcaee9f970b9937488e6716891932b73824c16d4c7",
        "51e3f026def41778ecd0d7dcaee9f970b9937488e6716891932b73824c16d4c7 other.csv",
        "51E3F026DEF41778ECD0D7DCAEE9F970B9937488E6716891932B73824C16D4C7 test_outputs.csv",
    ] {
        assert!(parse_commitment(commitment).is_err(), "{commitment:?}");
    }

    assert!(
        score_candidates(&Dataset {
            input_width: 3,
            output_width: 1,
            samples: vec![Sample {
                input: vec![false; 3],
                expected: vec![false],
            }],
        })
        .is_err()
    );
}

#[test]
fn canonical_builder_simplifies_and_hash_cons_gates() {
    let mut builder = CircuitBuilder::new(2, &DEFAULT_LIMITS).unwrap();
    let a = Signal::input(0);
    let b = Signal::input(1);
    assert_eq!(builder.binary(GateOp::And, a, a).unwrap(), a);
    assert_eq!(
        builder.binary(GateOp::Xor, a, a).unwrap(),
        builder.zero().unwrap()
    );
    assert_eq!(
        builder.binary(GateOp::Or, a, a.inverted()).unwrap(),
        builder.one().unwrap()
    );
    let first = builder.binary(GateOp::Xor, a, b).unwrap();
    let second = builder.binary(GateOp::Xor, b, a).unwrap();
    assert_eq!(first, second);
    let synthesized = builder.finish(&[first]).unwrap();
    assert_eq!(synthesized.gate_count, 1);
    assert_eq!(parse_netlist(&synthesized.netlist).unwrap().gates.len(), 1);
}

#[test]
fn family_circuits_are_exhaustively_correct_at_small_widths() {
    for family in ArithmeticFamily::ALL {
        for operand_bits in 1..=4 {
            let first = synthesize_family(family, operand_bits).unwrap();
            let second = synthesize_family(family, operand_bits).unwrap();
            assert_eq!(first, second);
            let circuit = parse_netlist(&first.netlist).unwrap();
            let bound = 1u64 << operand_bits;
            for x in 0..bound {
                for y in 0..bound {
                    let mut input = bits(x, operand_bits);
                    input.extend(bits(y, operand_bits));
                    let actual = decode_lsb(&evaluate(&circuit, &input).unwrap()).unwrap();
                    assert_eq!(
                        actual,
                        family.evaluate(x, y, operand_bits).unwrap(),
                        "{family:?} width={operand_bits} x={x} y={y}"
                    );
                }
            }
        }
    }
}

#[test]
fn optimized_multiplier_is_smaller_than_shift_add_reference() {
    let optimized = synthesize_family(ArithmeticFamily::Multiply, 4).unwrap();
    let legacy = occam71_rust::shift_add_multiplier(4).unwrap();
    assert!(
        optimized.gate_count < parse_netlist(&legacy).unwrap().gates.len(),
        "optimized={} legacy={}",
        optimized.gate_count,
        parse_netlist(&legacy).unwrap().gates.len()
    );
}

fn dataset_source(family: ArithmeticFamily, operand_bits: usize) -> String {
    let output_width = family.output_width(operand_bits).unwrap();
    let bound = 1u64 << operand_bits;
    let mut source = String::from("input,output\n");
    for x in 0..bound {
        for y in 0..bound {
            let input: String = bits(x, operand_bits)
                .into_iter()
                .chain(bits(y, operand_bits))
                .map(|value| if value { '1' } else { '0' })
                .collect();
            let output: String = bits(family.evaluate(x, y, operand_bits).unwrap(), output_width)
                .into_iter()
                .map(|value| if value { '1' } else { '0' })
                .collect();
            source.push_str(&format!("{input},{output}\n"));
        }
    }
    source
}

#[test]
fn learner_requires_one_unique_zero_error_family() {
    let ambiguous = parse_dataset("input,output\n00,00\n").unwrap();
    let error = infer_unique_family(&ambiguous).unwrap_err().to_string();
    assert!(error.contains("ambiguous"), "{error}");
}

#[test]
fn predictions_come_from_reparsed_circuit() {
    let training = dataset_source(ArithmeticFamily::Add, 3);
    let test_inputs = "input\n100010\n111111\n";
    let result = learn_instance(LearnRequest {
        instance: "synthetic-add",
        training_source: &training,
        test_inputs_source: test_inputs,
        commitment_source: None,
        limits: &DEFAULT_LIMITS,
    })
    .unwrap();
    let circuit = parse_netlist(&result.circuit).unwrap();
    let expected =
        prediction_csv_from_circuit(&circuit, &result.test_inputs, &DEFAULT_LIMITS).unwrap();
    assert_eq!(result.prediction_csv, expected);
    assert_eq!(result.report.selected_family, ArithmeticFamily::Add);
    assert_eq!(result.report.training_scalar, result.report.training_packed);
    assert_eq!(result.report.training_scalar.exact_matches, 64);
    assert_eq!(result.report.exhaustive_cases, 64);
    assert_eq!(result.report.exhaustive_mismatches, 0);
    assert_eq!(
        result.report.prediction_sha256,
        sha256_hex(result.prediction_csv.as_bytes())
    );
    let second = learn_instance(LearnRequest {
        instance: "synthetic-add",
        training_source: &training,
        test_inputs_source: test_inputs,
        commitment_source: None,
        limits: &DEFAULT_LIMITS,
    })
    .unwrap();
    assert_eq!(
        result.report.to_json_pretty().unwrap(),
        second.report.to_json_pretty().unwrap()
    );
}

#[test]
fn learner_rejects_a_wrong_commitment() {
    let training = dataset_source(ArithmeticFamily::AbsDiff, 2);
    let wrong =
        "0000000000000000000000000000000000000000000000000000000000000000  test_outputs.csv\n";
    let error = learn_instance(LearnRequest {
        instance: "synthetic-difference",
        training_source: &training,
        test_inputs_source: "input\n0000\n1010\n",
        commitment_source: Some(wrong),
        limits: &DEFAULT_LIMITS,
    })
    .unwrap_err()
    .to_string();
    assert!(error.contains("commitment mismatch"), "{error}");
}

#[test]
fn validated_artifacts_and_manifest_are_stable() {
    let training = dataset_source(ArithmeticFamily::Add, 2);
    let test_inputs = "input\n1000\n0111\n";
    let unsigned = learn_instance(LearnRequest {
        instance: "mystery-Z",
        training_source: &training,
        test_inputs_source: test_inputs,
        commitment_source: None,
        limits: &DEFAULT_LIMITS,
    })
    .unwrap();
    let commitment = format!("{}  test_outputs.csv\n", unsigned.report.prediction_sha256);
    let result = learn_instance(LearnRequest {
        instance: "mystery-Z",
        training_source: &training,
        test_inputs_source: test_inputs,
        commitment_source: Some(&commitment),
        limits: &DEFAULT_LIMITS,
    })
    .unwrap();

    let root =
        std::env::temp_dir().join(format!("occam71-learning-artifacts-{}", std::process::id()));
    if root.exists() {
        fs::remove_dir_all(&root).unwrap();
    }
    let written = write_instance_artifacts(&root, "mystery-Z", &result).unwrap();
    let manifest = write_manifest(&root, std::slice::from_ref(&written)).unwrap();
    assert_eq!(
        fs::read_to_string(&written.circuit_path).unwrap(),
        result.circuit
    );
    assert_eq!(
        fs::read_to_string(&written.prediction_path).unwrap(),
        result.prediction_csv
    );
    assert_eq!(
        fs::read_to_string(&written.report_path).unwrap(),
        result.report.to_json_pretty().unwrap()
    );
    let first_manifest = fs::read_to_string(&manifest).unwrap();
    write_manifest(&root, &[written]).unwrap();
    assert_eq!(fs::read_to_string(&manifest).unwrap(), first_manifest);
    fs::remove_dir_all(root).unwrap();
}

#[test]
fn official_instances_recover_expected_families_and_commitments() {
    let vendor = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .join("vendor/occam-circuit/datasets");
    if !vendor.is_dir() {
        eprintln!("official data absent; run ./scripts/fetch-occam-data.sh");
        return;
    }
    for (name, family, expected_hash) in [
        (
            "mystery-A",
            ArithmeticFamily::Add,
            "51e3f026def41778ecd0d7dcaee9f970b9937488e6716891932b73824c16d4c7",
        ),
        (
            "mystery-B",
            ArithmeticFamily::AbsDiff,
            "e2c9d0e23ee36bfc0f12d7f39fdfe2ca5a8abe8eb194fec56500733694b75c28",
        ),
        (
            "mystery-C",
            ArithmeticFamily::Multiply,
            "c7b37413844bf0b10ebad0010046469f500354a22cc2ba95cbe42709f8e8337d",
        ),
        (
            "mystery-D",
            ArithmeticFamily::SumOfSquares,
            "b445a717483303fa3c5d8a1f7abe81888b267b7c472121c9c464fa9766808580",
        ),
    ] {
        let root = vendor.join(name);
        let training = fs::read_to_string(root.join("train.csv")).unwrap();
        let inputs = fs::read_to_string(root.join("test_inputs.csv")).unwrap();
        let commitment = fs::read_to_string(root.join("commitment.sha256")).unwrap();
        let result = learn_instance(LearnRequest {
            instance: name,
            training_source: &training,
            test_inputs_source: &inputs,
            commitment_source: Some(&commitment),
            limits: &DEFAULT_LIMITS,
        })
        .unwrap();
        assert_eq!(result.report.selected_family, family, "{name}");
        assert_eq!(
            result.report.training_scalar.exact_matches, result.report.training_scalar.samples,
            "{name}"
        );
        assert_eq!(result.report.training_scalar, result.report.training_packed);
        assert_eq!(result.report.exhaustive_mismatches, 0, "{name}");
        assert_eq!(result.report.prediction_sha256, expected_hash, "{name}");
        assert_eq!(result.report.commitment_matches, Some(true), "{name}");
        eprintln!(
            "{name}: family={family:?} gates={} exhaustive={}",
            result.report.gate_count, result.report.exhaustive_cases
        );
    }
}
