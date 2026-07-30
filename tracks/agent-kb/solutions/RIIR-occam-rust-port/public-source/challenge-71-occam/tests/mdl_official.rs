use std::{collections::BTreeMap, fs, path::PathBuf};

use occam71_rust::{
    ArithmeticFamily, DEFAULT_LIMITS, MdlLearnRequest, MdlSearchConfig, learn_mdl, parse_dataset,
    score_candidates,
};

fn workspace_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_owned()
}

#[test]
fn generic_mdl_recovers_official_semantics_independently_of_labels() {
    let data_root = workspace_root().join("vendor/occam-circuit/datasets");
    if !data_root.is_dir() {
        eprintln!("official data absent; run ./scripts/fetch-occam-data.sh");
        return;
    }
    let expected = [
        ("mystery-A", "(x + y)", ArithmeticFamily::Add),
        ("mystery-B", "abs(x - y)", ArithmeticFamily::AbsDiff),
        ("mystery-C", "(x * y)", ArithmeticFamily::Multiply),
        (
            "mystery-D",
            "(square(x) + square(y))",
            ArithmeticFamily::SumOfSquares,
        ),
    ];
    let labels = ["alpha", "beta", "gamma", "delta"];
    let config = MdlSearchConfig::default();
    let mut reports = BTreeMap::new();

    for ((instance, expression, omitted_family), label) in expected.into_iter().zip(labels) {
        let root = data_root.join(instance);
        let training_source = fs::read_to_string(root.join("train.csv")).unwrap();
        let test_inputs_source = fs::read_to_string(root.join("test_inputs.csv")).unwrap();
        let commitment_source = fs::read_to_string(root.join("commitment.sha256")).unwrap();
        let request = || MdlLearnRequest {
            training_source: &training_source,
            test_inputs_source: &test_inputs_source,
            commitment_source: Some(&commitment_source),
            config: &config,
            limits: &DEFAULT_LIMITS,
        };
        let official = learn_mdl(request()).unwrap();
        let renamed = learn_mdl(request()).unwrap();
        assert_eq!(official, renamed, "renamed label {label}");
        assert_eq!(official.report.expression, expression);
        assert_eq!(official.report.exhaustive_mismatches, 0);
        assert_eq!(official.report.commitment_matches, Some(true));
        reports.insert(instance, official.report);

        let training = parse_dataset(&training_source).unwrap();
        let remaining_zero_error = score_candidates(&training)
            .unwrap()
            .into_iter()
            .filter(|score| score.family != omitted_family && score.mismatches == 0)
            .count();
        assert_eq!(
            remaining_zero_error, 0,
            "legacy registry should fail after omitting {omitted_family}"
        );
    }

    assert_eq!(reports.len(), 4);
}
