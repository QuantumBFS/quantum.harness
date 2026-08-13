use occam71_rust::{
    BinaryOp, Dataset, Expr, MdlSearchConfig, Sample, SearchTermination, search_mdl,
};

fn bits(value: u64, width: usize) -> Vec<bool> {
    (0..width).map(|bit| value & (1u64 << bit) != 0).collect()
}

fn dataset_from_fn(
    operand_bits: usize,
    output_bits: usize,
    function: impl Fn(u64, u64) -> u64,
) -> Dataset {
    let bound = 1u64 << operand_bits;
    let mut samples = Vec::new();
    for x in 0..bound {
        for y in 0..bound {
            let mut input = bits(x, operand_bits);
            input.extend(bits(y, operand_bits));
            samples.push(Sample {
                input,
                expected: bits(function(x, y), output_bits),
            });
        }
    }
    Dataset {
        input_width: operand_bits * 2,
        output_width: output_bits,
        samples,
    }
}

#[test]
fn mdl_search_compares_candidates_without_natural_width_filtering() {
    let dataset = dataset_from_fn(3, 4, |x, y| x + y);
    let result = search_mdl(&dataset, &MdlSearchConfig::for_tests()).unwrap();

    assert_eq!(result.expression.unwrap().to_string(), "(x + y)");
    assert_eq!(result.report.termination, SearchTermination::Found);
    assert_eq!(result.report.description_cost, Some(3));
    assert!(result.report.evaluated_expressions > 4);
    assert!(result.report.retained_semantic_classes > 1);
}

#[test]
fn mdl_search_recovers_multiplication_at_the_same_declared_width() {
    let dataset = dataset_from_fn(2, 5, |x, y| x * y);
    let result = search_mdl(&dataset, &MdlSearchConfig::for_tests()).unwrap();

    assert_eq!(result.expression.unwrap().to_string(), "(x * y)");
    assert_eq!(result.report.description_cost, Some(3));
}

#[test]
fn mdl_search_reports_equal_cost_observational_ambiguity() {
    let dataset = Dataset {
        input_width: 4,
        output_width: 3,
        samples: vec![Sample {
            input: vec![false; 4],
            expected: vec![false; 3],
        }],
    };
    let result = search_mdl(&dataset, &MdlSearchConfig::for_tests()).unwrap();

    assert_eq!(result.report.description_cost, Some(1));
    assert_eq!(result.report.minimum_unique, Some(false));
    assert!(result.report.equal_cost_expression_count.unwrap() >= 3);
    assert_eq!(result.report.alternatives, vec!["0", "x", "y"]);
}

#[test]
fn search_termination_is_typed_and_never_falls_back() {
    let dataset = dataset_from_fn(2, 5, |x, y| x * y);

    let mut cost_limited = MdlSearchConfig::for_tests();
    cost_limited.max_description_cost = 2;
    let result = search_mdl(&dataset, &cost_limited).unwrap();
    assert!(result.expression.is_none());
    assert_eq!(result.report.termination, SearchTermination::CostExhausted);

    let mut expression_limited = MdlSearchConfig::for_tests();
    expression_limited.max_generated_expressions = 2;
    let result = search_mdl(&dataset, &expression_limited).unwrap();
    assert!(result.expression.is_none());
    assert_eq!(
        result.report.termination,
        SearchTermination::ExpressionLimit
    );

    let mut semantic_limited = MdlSearchConfig::for_tests();
    semantic_limited.max_semantic_classes = 1;
    let result = search_mdl(&dataset, &semantic_limited).unwrap();
    assert!(result.expression.is_none());
    assert_eq!(
        result.report.termination,
        SearchTermination::SemanticClassLimit
    );

    let mut timed_out = MdlSearchConfig::for_tests();
    timed_out.timeout_millis = 0;
    let result = search_mdl(&dataset, &timed_out).unwrap();
    assert!(result.expression.is_none());
    assert_eq!(result.report.termination, SearchTermination::Timeout);
}

#[test]
fn search_reports_are_byte_stable() {
    let dataset = dataset_from_fn(2, 3, |x, y| x.abs_diff(y));
    let config = MdlSearchConfig::for_tests();
    let first = search_mdl(&dataset, &config).unwrap();
    let second = search_mdl(&dataset, &config).unwrap();

    assert_eq!(first, second);
    assert_eq!(
        serde_json::to_string_pretty(&first.report).unwrap(),
        serde_json::to_string_pretty(&second.report).unwrap()
    );
    assert_eq!(
        first.expression.unwrap(),
        Expr::abs_diff(Expr::x(), Expr::y()).canonicalize().unwrap()
    );
}

#[test]
fn custom_operator_sets_are_respected() {
    let dataset = dataset_from_fn(2, 3, |x, y| x ^ y);
    let mut config = MdlSearchConfig::for_tests();
    config.enabled_binary_ops = vec![BinaryOp::Add];
    config.enable_square = false;
    config.shift_amounts.clear();
    let result = search_mdl(&dataset, &config).unwrap();

    assert!(result.expression.is_none());
    assert_eq!(result.report.termination, SearchTermination::CostExhausted);
}
