use std::fs;

use occam71_rust::{
    ArithmeticOperation, DEFAULT_LIMITS, OccamError, generate_dataset, pack_dataset, parse_dataset,
    parse_packed_dataset, parse_packed_dataset_with_limits,
};

fn assert_matches_legacy(source: &str) {
    let scalar = parse_dataset(source).unwrap();
    let legacy = pack_dataset(&scalar).unwrap();
    let direct_string = parse_packed_dataset(source).unwrap();
    let direct_bytes = parse_packed_dataset(source.as_bytes()).unwrap();
    assert_eq!(direct_string, legacy);
    assert_eq!(direct_bytes, legacy);
}

#[test]
fn direct_parser_matches_legacy_on_fixed_and_generated_inputs() {
    assert_matches_legacy(include_str!("fixtures/add-n2.csv"));
    for samples in [1, 63, 64, 65, 127, 128, 129, 1_000] {
        for seed in [0, 71, 115, u64::MAX] {
            let add = generate_dataset(ArithmeticOperation::Add, 8, samples, seed).unwrap();
            assert_matches_legacy(&add);
            let multiply =
                generate_dataset(ArithmeticOperation::Multiply, 4, samples, seed).unwrap();
            assert_matches_legacy(&multiply);
        }
    }
}

#[test]
fn direct_and_scalar_parsers_reject_invalid_corpus_identically() {
    let invalid = [
        "",
        "x,y\n0,1",
        "input,output\n",
        "input,output\n0",
        "input,output\n0,1,0",
        "input,output\n,1",
        "input,output\n1,",
        "input,output\n0x,1",
        "input,output\n0,2",
        "input,output\n00,1\n0,1",
        "input,output\n0,1\n0,11",
    ];
    for source in invalid {
        let expected_error = parse_dataset(source).unwrap_err().to_string();
        assert_eq!(
            parse_packed_dataset(source).unwrap_err().to_string(),
            expected_error,
            "string source {source:?}"
        );
        assert_eq!(
            parse_packed_dataset(source.as_bytes())
                .unwrap_err()
                .to_string(),
            expected_error,
            "byte source {source:?}"
        );
    }
}

#[test]
fn direct_parser_accepts_raw_crlf_and_rejects_non_utf8() {
    let crlf = b"input,output\r\n\r\n  01,10  \r\n\r\n11,00\r\n";
    let direct = parse_packed_dataset(crlf).unwrap();
    let scalar = parse_dataset(std::str::from_utf8(crlf).unwrap()).unwrap();
    assert_eq!(direct, pack_dataset(&scalar).unwrap());

    let error = parse_packed_dataset(b"input,output\n0,\xff\n")
        .unwrap_err()
        .to_string();
    assert!(
        error.contains("non-bit"),
        "unexpected non-UTF-8 error: {error}"
    );
}

#[test]
fn byte_and_string_limit_errors_are_identical() {
    let source = "input,output\n0,1\n1,0\n";
    let mut limits = DEFAULT_LIMITS;
    limits.max_samples = 1;
    assert_eq!(
        parse_packed_dataset_with_limits(source, &limits)
            .unwrap_err()
            .to_string(),
        parse_packed_dataset_with_limits(source.as_bytes(), &limits)
            .unwrap_err()
            .to_string(),
        "source {source:?}"
    );
}

#[test]
fn direct_parser_obeys_limits_before_packed_allocation() {
    let source = "input,output\n0,1\n1,0\n";
    let mut limits = DEFAULT_LIMITS;
    limits.max_samples = 1;
    assert!(matches!(
        parse_packed_dataset_with_limits(source, &limits),
        Err(OccamError::ResourceLimit {
            resource: "dataset samples",
            ..
        })
    ));

    let mut limits = DEFAULT_LIMITS;
    limits.max_packed_words = 1;
    assert!(matches!(
        parse_packed_dataset_with_limits(source, &limits),
        Err(OccamError::ResourceLimit {
            resource: "packed dataset words",
            ..
        })
    ));
}

#[test]
fn direct_parser_matches_official_dataset_when_available() {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../vendor/occam-circuit/datasets/mystery-A/train.csv");
    if path.exists() {
        let source = fs::read(path).unwrap();
        let text = std::str::from_utf8(&source).unwrap();
        assert_matches_legacy(text);
        assert_eq!(
            parse_packed_dataset(&source).unwrap(),
            pack_dataset(&parse_dataset(text).unwrap()).unwrap()
        );
    }
}

#[test]
#[ignore = "explicit 1M-row ingestion regression"]
fn parses_one_million_rows_without_scalar_materialization() {
    let source = generate_dataset(ArithmeticOperation::Add, 8, 1_000_000, 115).unwrap();
    let packed = parse_packed_dataset(&source).unwrap();
    assert_eq!(packed.sample_count(), 1_000_000);
    assert_eq!(packed.input_width(), 16);
    assert_eq!(packed.output_width(), 9);
}
