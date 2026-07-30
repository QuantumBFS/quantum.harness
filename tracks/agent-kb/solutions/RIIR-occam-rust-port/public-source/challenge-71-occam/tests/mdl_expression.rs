use occam71_rust::{
    BinaryOp, Dataset, Expr, ExprSemantics, Sample, SemanticKey, evaluate_rows, parse_expression,
};

#[test]
fn expression_semantics_are_fixed_width_not_natural_width_filtered() {
    let semantics = ExprSemantics::new(3, 4).unwrap();
    let add = Expr::binary(BinaryOp::Add, Expr::x(), Expr::y());
    let multiply = Expr::binary(BinaryOp::Multiply, Expr::x(), Expr::y());

    assert_eq!(add.evaluate(7, 7, semantics).unwrap(), 14);
    assert_eq!(multiply.evaluate(7, 7, semantics).unwrap(), 1);
}

#[test]
fn official_expressions_have_declared_description_costs() {
    let x = Expr::x();
    let y = Expr::y();

    assert_eq!(
        Expr::binary(BinaryOp::Add, x.clone(), y.clone()).description_cost(),
        3
    );
    assert_eq!(Expr::abs_diff(x.clone(), y.clone()).description_cost(), 4);
    assert_eq!(
        Expr::binary(BinaryOp::Multiply, x.clone(), y.clone()).description_cost(),
        3
    );
    assert_eq!(
        Expr::binary(BinaryOp::Add, Expr::square(x), Expr::square(y)).description_cost(),
        5
    );
}

#[test]
fn expression_validation_rejects_invalid_widths_constants_and_shifts() {
    assert!(ExprSemantics::new(0, 1).is_err());
    assert!(ExprSemantics::new(32, 1).is_err());
    assert!(ExprSemantics::new(1, 0).is_err());
    assert!(ExprSemantics::new(1, 64).is_err());

    let semantics = ExprSemantics::new(3, 4).unwrap();
    assert!(Expr::constant(16).evaluate(0, 0, semantics).is_err());
    assert!(
        Expr::shift_left(Expr::x(), 0)
            .evaluate(1, 0, semantics)
            .is_err()
    );
    assert!(
        Expr::shift_left(Expr::x(), 4)
            .evaluate(1, 0, semantics)
            .is_err()
    );
    assert!(Expr::x().evaluate(8, 0, semantics).is_err());
    assert!(Expr::y().evaluate(0, 8, semantics).is_err());
}

#[test]
fn every_binary_operator_matches_the_independent_reference() {
    let semantics = ExprSemantics::new(3, 5).unwrap();
    let mask = (1u64 << semantics.output_bits) - 1;
    let operations = [
        BinaryOp::Add,
        BinaryOp::Subtract,
        BinaryOp::AbsDiff,
        BinaryOp::Multiply,
        BinaryOp::BitXor,
        BinaryOp::BitAnd,
        BinaryOp::BitOr,
        BinaryOp::Min,
        BinaryOp::Max,
    ];

    for operation in operations {
        let expression = Expr::binary(operation, Expr::x(), Expr::y());
        for x in 0u64..8 {
            for y in 0u64..8 {
                let expected = match operation {
                    BinaryOp::Add => ((x as u128 + y as u128) & mask as u128) as u64,
                    BinaryOp::Subtract => x.wrapping_sub(y) & mask,
                    BinaryOp::AbsDiff => x.abs_diff(y),
                    BinaryOp::Multiply => ((x as u128 * y as u128) & mask as u128) as u64,
                    BinaryOp::BitXor => x ^ y,
                    BinaryOp::BitAnd => x & y,
                    BinaryOp::BitOr => x | y,
                    BinaryOp::Min => x.min(y),
                    BinaryOp::Max => x.max(y),
                };
                assert_eq!(
                    expression.evaluate(x, y, semantics).unwrap(),
                    expected,
                    "{operation:?} x={x} y={y}"
                );
            }
        }
    }
}

#[test]
fn unary_operators_wrap_to_the_declared_output_width() {
    let semantics = ExprSemantics::new(3, 4).unwrap();

    assert_eq!(
        Expr::square(Expr::x()).evaluate(7, 0, semantics).unwrap(),
        1
    );
    assert_eq!(
        Expr::shift_left(Expr::x(), 2)
            .evaluate(7, 0, semantics)
            .unwrap(),
        12
    );
}

#[test]
fn canonicalization_removes_structural_duplicates() {
    let x = Expr::x();
    let y = Expr::y();
    let xy = Expr::binary(BinaryOp::Add, x.clone(), y.clone())
        .canonicalize()
        .unwrap();
    let yx = Expr::binary(BinaryOp::Add, y, x).canonicalize().unwrap();

    assert_eq!(xy, yx);
    assert_eq!(xy.to_string(), "(x + y)");
    assert_eq!(
        Expr::binary(BinaryOp::BitXor, Expr::x(), Expr::x())
            .canonicalize()
            .unwrap(),
        Expr::constant(0)
    );
    assert_eq!(
        Expr::binary(BinaryOp::Multiply, Expr::x(), Expr::x())
            .canonicalize()
            .unwrap(),
        Expr::square(Expr::x())
    );
}

#[test]
fn canonicalization_applies_safe_identities() {
    let x = Expr::x();

    for expression in [
        Expr::binary(BinaryOp::Add, x.clone(), Expr::constant(0)),
        Expr::binary(BinaryOp::Subtract, x.clone(), Expr::constant(0)),
        Expr::binary(BinaryOp::BitXor, x.clone(), Expr::constant(0)),
        Expr::binary(BinaryOp::BitAnd, x.clone(), x.clone()),
        Expr::binary(BinaryOp::BitOr, x.clone(), Expr::constant(0)),
        Expr::binary(BinaryOp::Min, x.clone(), x.clone()),
        Expr::binary(BinaryOp::Max, x.clone(), x.clone()),
        Expr::binary(BinaryOp::Multiply, x.clone(), Expr::constant(1)),
    ] {
        assert_eq!(expression.canonicalize().unwrap(), x);
    }

    for expression in [
        Expr::binary(BinaryOp::BitAnd, x.clone(), Expr::constant(0)),
        Expr::binary(BinaryOp::Multiply, x.clone(), Expr::constant(0)),
        Expr::abs_diff(x.clone(), x.clone()),
        Expr::shift_left(Expr::constant(0), 1),
    ] {
        assert_eq!(expression.canonicalize().unwrap(), Expr::constant(0));
    }
}

#[test]
fn semantic_keys_depend_only_on_observed_input_behavior() {
    let dataset = Dataset {
        input_width: 4,
        output_width: 3,
        samples: vec![
            Sample {
                input: vec![false, false, false, false],
                expected: vec![false; 3],
            },
            Sample {
                input: vec![true, false, false, true],
                expected: vec![false; 3],
            },
        ],
    };
    let semantics = ExprSemantics::new(2, 3).unwrap();

    assert_eq!(
        evaluate_rows(
            &Expr::binary(BinaryOp::Add, Expr::x(), Expr::y()),
            &dataset,
            semantics
        )
        .unwrap(),
        SemanticKey(vec![0, 3])
    );
    assert!(
        evaluate_rows(
            &Expr::x(),
            &Dataset {
                input_width: 3,
                ..dataset.clone()
            },
            semantics
        )
        .is_err()
    );
}

#[test]
fn stable_display_is_unambiguous() {
    let expression = Expr::binary(
        BinaryOp::BitXor,
        Expr::binary(BinaryOp::Add, Expr::x(), Expr::y()),
        Expr::shift_left(Expr::square(Expr::x()), 2),
    );
    assert_eq!(
        expression.to_string(),
        "((x + y) XOR shift_left(square(x), 2))"
    );
    assert_eq!(
        Expr::abs_diff(Expr::x(), Expr::y()).to_string(),
        "abs(x - y)"
    );
}

#[test]
fn stable_expression_syntax_parses_without_task_specific_cases() {
    for source in [
        "x",
        "1",
        "(x + y)",
        "abs(x - y)",
        "(x * y)",
        "(square(x) + square(y))",
        "((x + y) XOR x)",
        "(shift_left(x, 1) + y)",
        "(max(x, y) - min(x, y))",
    ] {
        let parsed = parse_expression(source).unwrap();
        assert_eq!(
            parse_expression(&parsed.to_string()).unwrap(),
            parsed,
            "{source}"
        );
    }
    for invalid in [" x", "(x+y)", "shift_left(x, 0)", "(x + y"] {
        assert!(parse_expression(invalid).is_err(), "{invalid}");
    }
}
