use occam71_rust::{
    BinaryOp, DEFAULT_LIMITS, Expr, ExprSemantics, compile_expression, decode_lsb, evaluate,
    parse_netlist,
};

fn bits(value: u64, width: usize) -> Vec<bool> {
    (0..width).map(|bit| value & (1u64 << bit) != 0).collect()
}

fn operator_fixture_expressions() -> Vec<Expr> {
    let mut expressions = vec![
        Expr::x(),
        Expr::y(),
        Expr::constant(0),
        Expr::constant(1),
        Expr::square(Expr::x()),
        Expr::shift_left(Expr::x(), 1),
        Expr::shift_left(Expr::x(), 2),
        Expr::shift_left(Expr::x(), 3),
    ];
    for operation in [
        BinaryOp::Add,
        BinaryOp::Subtract,
        BinaryOp::AbsDiff,
        BinaryOp::Multiply,
        BinaryOp::BitXor,
        BinaryOp::BitAnd,
        BinaryOp::BitOr,
        BinaryOp::Min,
        BinaryOp::Max,
    ] {
        expressions.push(Expr::binary(operation, Expr::x(), Expr::y()));
    }
    expressions.push(Expr::binary(
        BinaryOp::Add,
        Expr::square(Expr::x()),
        Expr::square(Expr::y()),
    ));
    expressions
}

fn assert_expression_circuit_equivalent(expression: &Expr, semantics: ExprSemantics) {
    let synthesized = compile_expression(expression, semantics, &DEFAULT_LIMITS).unwrap();
    let circuit = parse_netlist(&synthesized.netlist).unwrap();
    assert_eq!(circuit.input_count, semantics.operand_bits * 2);
    assert_eq!(circuit.outputs.len(), semantics.output_bits);
    assert_eq!(circuit.gates.len(), synthesized.gate_count);

    let bound = 1u64 << semantics.operand_bits;
    for x in 0..bound {
        for y in 0..bound {
            let mut input = bits(x, semantics.operand_bits);
            input.extend(bits(y, semantics.operand_bits));
            let actual = decode_lsb(&evaluate(&circuit, &input).unwrap()).unwrap();
            let expected = expression.evaluate(x, y, semantics).unwrap();
            assert_eq!(
                actual, expected,
                "{expression} width={semantics:?} x={x} y={y}"
            );
        }
    }
}

#[test]
fn every_operator_compiles_to_equivalent_official_circuit() {
    for expression in operator_fixture_expressions() {
        for operand_bits in 1..=3 {
            let semantics = ExprSemantics::new(operand_bits, operand_bits * 2 + 1).unwrap();
            assert_expression_circuit_equivalent(&expression, semantics);
        }
    }
}

#[test]
fn repeated_subexpressions_are_structurally_shared() {
    let x = Expr::x();
    let repeated = Expr::binary(BinaryOp::BitXor, Expr::square(x.clone()), Expr::square(x));
    let semantics = ExprSemantics::new(4, 8).unwrap();
    let synthesized = compile_expression(&repeated, semantics, &DEFAULT_LIMITS).unwrap();
    let circuit = parse_netlist(&synthesized.netlist).unwrap();

    assert_eq!(circuit.gates.len(), 1);
    assert_expression_circuit_equivalent(&repeated, semantics);
}

#[test]
fn official_expression_gate_counts_have_stable_upper_bounds() {
    let fixtures = [
        (
            Expr::binary(BinaryOp::Add, Expr::x(), Expr::y()),
            ExprSemantics::new(8, 9).unwrap(),
            60,
        ),
        (
            Expr::abs_diff(Expr::x(), Expr::y()),
            ExprSemantics::new(7, 7).unwrap(),
            90,
        ),
        (
            Expr::binary(BinaryOp::Multiply, Expr::x(), Expr::y()),
            ExprSemantics::new(6, 12).unwrap(),
            240,
        ),
        (
            Expr::binary(
                BinaryOp::Add,
                Expr::square(Expr::x()),
                Expr::square(Expr::y()),
            ),
            ExprSemantics::new(5, 11).unwrap(),
            260,
        ),
    ];

    for (expression, semantics, maximum) in fixtures {
        let synthesized = compile_expression(&expression, semantics, &DEFAULT_LIMITS).unwrap();
        assert!(
            synthesized.gate_count <= maximum,
            "{expression}: {} > {maximum}",
            synthesized.gate_count
        );
        assert_expression_circuit_equivalent(&expression, semantics);
    }
}
