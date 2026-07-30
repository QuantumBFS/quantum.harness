use std::{fs, path::PathBuf};

use occam71_rust::{
    DEFAULT_LIMITS, MdlLearnRequest, MdlSearchConfig, SearchTermination, decode_lsb, learn_mdl,
    parse_netlist, prediction_csv_from_circuit, sha256_hex,
};

fn bits(value: u64, width: usize) -> String {
    (0..width)
        .map(|bit| if value & (1u64 << bit) == 0 { '0' } else { '1' })
        .collect()
}

fn dataset_source(
    operand_bits: usize,
    output_bits: usize,
    function: impl Fn(u64, u64) -> u64,
) -> String {
    let mut source = String::from("input,output\n");
    let bound = 1u64 << operand_bits;
    for x in 0..bound {
        for y in 0..bound {
            source.push_str(&bits(x, operand_bits));
            source.push_str(&bits(y, operand_bits));
            source.push(',');
            source.push_str(&bits(function(x, y), output_bits));
            source.push('\n');
        }
    }
    source
}

#[test]
fn mdl_learner_recovers_addition_without_legacy_family_api() {
    let training = dataset_source(3, 4, |x, y| x + y);
    let config = MdlSearchConfig::for_tests();
    let result = learn_mdl(MdlLearnRequest {
        training_source: &training,
        test_inputs_source: "input\n100010\n111111\n",
        commitment_source: None,
        config: &config,
        limits: &DEFAULT_LIMITS,
    })
    .unwrap();

    assert_eq!(result.report.learner, "mdl-enumerator");
    assert_eq!(result.report.expression, "(x + y)");
    assert_eq!(result.report.description_cost, 3);
    assert_eq!(result.report.search.termination, SearchTermination::Found);
    assert_eq!(result.report.training_scalar.exact_matches, 64);
    assert_eq!(result.report.training_scalar, result.report.training_packed);
    assert_eq!(result.report.exhaustive_cases, 64);
    assert_eq!(result.report.exhaustive_mismatches, 0);

    let circuit = parse_netlist(&result.circuit).unwrap();
    assert_eq!(
        result.prediction_csv,
        prediction_csv_from_circuit(&circuit, &result.test_inputs, &DEFAULT_LIMITS).unwrap()
    );
    assert_eq!(
        result.report.prediction_sha256,
        sha256_hex(result.prediction_csv.as_bytes())
    );
}

#[test]
fn mdl_learning_reports_are_byte_stable() {
    let training = dataset_source(2, 3, |x, y| x.abs_diff(y));
    let config = MdlSearchConfig::for_tests();
    let request = || MdlLearnRequest {
        training_source: &training,
        test_inputs_source: "input\n0000\n1010\n",
        commitment_source: None,
        config: &config,
        limits: &DEFAULT_LIMITS,
    };
    let first = learn_mdl(request()).unwrap();
    let second = learn_mdl(request()).unwrap();

    assert_eq!(first, second);
    assert_eq!(
        first.report.to_json_pretty().unwrap(),
        second.report.to_json_pretty().unwrap()
    );
    let output = first
        .prediction_csv
        .lines()
        .nth(1)
        .unwrap()
        .split(',')
        .nth(1)
        .unwrap()
        .chars()
        .map(|bit| bit == '1')
        .collect::<Vec<_>>();
    assert_eq!(decode_lsb(&output).unwrap(), 0);
}

#[test]
fn commitment_remains_a_post_hoc_integrity_check() {
    let training = dataset_source(2, 3, |x, y| x + y);
    let config = MdlSearchConfig::for_tests();
    let wrong =
        "0000000000000000000000000000000000000000000000000000000000000000  test_outputs.csv\n";
    let error = learn_mdl(MdlLearnRequest {
        training_source: &training,
        test_inputs_source: "input\n0000\n1010\n",
        commitment_source: Some(wrong),
        config: &config,
        limits: &DEFAULT_LIMITS,
    })
    .unwrap_err()
    .to_string();

    assert!(error.contains("commitment mismatch"), "{error}");
}

#[test]
fn mdl_sources_do_not_import_fixed_official_families() {
    let crate_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let mut files = vec![crate_root.join("src/learning/mdl.rs")];
    for entry in fs::read_dir(crate_root.join("src/expression")).unwrap() {
        let path = entry.unwrap().path();
        if path.extension().is_some_and(|extension| extension == "rs") {
            files.push(path);
        }
    }

    for path in files {
        let source = fs::read_to_string(&path).unwrap();
        for forbidden in [
            "use crate::ArithmeticFamily",
            "ArithmeticFamily::",
            "synthesize_family",
            "mystery-A",
            "mystery-B",
            "mystery-C",
            "mystery-D",
        ] {
            assert!(
                !source.contains(forbidden),
                "{} contains {forbidden:?}",
                path.display()
            );
        }
    }
}
