use std::{collections::HashSet, fs, path::PathBuf};

use occam71_rust::{
    DEFAULT_LIMITS, Expr, ExprSemantics, MdlSearchConfig, SearchTermination, compile_expression,
    decode_lsb, evaluate_with_limits, parse_dataset, parse_expression, parse_netlist, search_mdl,
};
use serde::Deserialize;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Fixture {
    schema_version: u32,
    operand_bits: usize,
    tasks: Vec<Task>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Task {
    id: String,
    output_bits: usize,
    oracle: String,
}

fn load_fixture() -> Fixture {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/mdl-tasks.json");
    serde_json::from_str(&fs::read_to_string(path).unwrap()).unwrap()
}

fn bits(value: u64, width: usize) -> String {
    (0..width)
        .map(|bit| if value & (1u64 << bit) == 0 { '0' } else { '1' })
        .collect()
}

fn deterministic_training(
    expression: &Expr,
    semantics: ExprSemantics,
    numerator: usize,
    denominator: usize,
) -> String {
    let mut source = String::from("input,output\n");
    let bound = 1u64 << semantics.operand_bits;
    for x in 0..bound {
        for y in 0..bound {
            let packed = (x as usize) | ((y as usize) << semantics.operand_bits);
            let rank = (packed * 73 + 19) % (bound as usize * bound as usize);
            if rank * denominator >= numerator * bound as usize * bound as usize {
                continue;
            }
            source.push_str(&bits(x, semantics.operand_bits));
            source.push_str(&bits(y, semantics.operand_bits));
            source.push(',');
            source.push_str(&bits(
                expression.evaluate(x, y, semantics).unwrap(),
                semantics.output_bits,
            ));
            source.push('\n');
        }
    }
    source
}

fn equivalent_over_domain(lhs: &Expr, rhs: &Expr, semantics: ExprSemantics) -> bool {
    let bound = 1u64 << semantics.operand_bits;
    (0..bound).all(|x| {
        (0..bound).all(|y| {
            lhs.evaluate(x, y, semantics).unwrap() == rhs.evaluate(x, y, semantics).unwrap()
        })
    })
}

fn circuit_matches_expression(expression: &Expr, oracle: &Expr, semantics: ExprSemantics) -> bool {
    let compiled = compile_expression(expression, semantics, &DEFAULT_LIMITS).unwrap();
    let circuit = parse_netlist(&compiled.netlist).unwrap();
    let bound = 1u64 << semantics.operand_bits;
    let mut input = vec![false; semantics.operand_bits * 2];
    for x in 0..bound {
        for y in 0..bound {
            for bit in 0..semantics.operand_bits {
                input[bit] = x & (1u64 << bit) != 0;
                input[semantics.operand_bits + bit] = y & (1u64 << bit) != 0;
            }
            let actual =
                decode_lsb(&evaluate_with_limits(&circuit, &input, &DEFAULT_LIMITS).unwrap())
                    .unwrap();
            if actual != oracle.evaluate(x, y, semantics).unwrap() {
                return false;
            }
        }
    }
    true
}

#[test]
fn generic_mdl_recovers_twelve_unseen_synthetic_functions() {
    let fixture = load_fixture();
    assert_eq!(fixture.schema_version, 1);
    assert_eq!(fixture.tasks.len(), 12);
    assert_eq!(
        fixture
            .tasks
            .iter()
            .map(|task| task.id.as_str())
            .collect::<HashSet<_>>()
            .len(),
        fixture.tasks.len()
    );

    let mut default_recovered = 0usize;
    let mut outcomes = Vec::new();
    for task in &fixture.tasks {
        let semantics = ExprSemantics::new(fixture.operand_bits, task.output_bits).unwrap();
        let oracle = parse_expression(&task.oracle).unwrap();
        let training_source = deterministic_training(&oracle, semantics, 3, 4);
        let training = parse_dataset(&training_source).unwrap();
        assert_eq!(training.samples.len(), 192);

        let first = search_mdl(&training, &MdlSearchConfig::default()).unwrap();
        let recovered = first.expression.as_ref().is_some_and(|expression| {
            equivalent_over_domain(expression, &oracle, semantics)
                && circuit_matches_expression(expression, &oracle, semantics)
        });
        if recovered {
            default_recovered += 1;
            outcomes.push((task.id.clone(), first.report.termination, true));
            continue;
        }

        let extended = MdlSearchConfig {
            max_description_cost: 9,
            timeout_millis: 60_000,
            ..MdlSearchConfig::default()
        };
        let second = search_mdl(&training, &extended).unwrap();
        let recovered = second.expression.as_ref().is_some_and(|expression| {
            equivalent_over_domain(expression, &oracle, semantics)
                && circuit_matches_expression(expression, &oracle, semantics)
        });
        outcomes.push((task.id.clone(), second.report.termination, recovered));
    }

    assert!(
        default_recovered >= 10,
        "only {default_recovered}/12 recovered at default bounds: {outcomes:?}"
    );
    assert!(
        outcomes.iter().all(|(_, _, recovered)| *recovered),
        "extended-bound failures: {outcomes:?}"
    );
}

#[test]
fn random_and_permuted_labels_do_not_create_false_recovery_claims() {
    let random_source = {
        let mut source = String::from("input,output\n");
        for packed in 0..64u64 {
            let x = packed & 7;
            let y = packed >> 3;
            let label = (packed * 11 + (packed >> 2) * 7 + 5) & 15;
            source.push_str(&bits(x, 3));
            source.push_str(&bits(y, 3));
            source.push(',');
            source.push_str(&bits(label, 4));
            source.push('\n');
        }
        source
    };
    let config = MdlSearchConfig {
        max_description_cost: 4,
        timeout_millis: 5_000,
        ..MdlSearchConfig::for_tests()
    };
    let random = search_mdl(&parse_dataset(&random_source).unwrap(), &config).unwrap();
    assert_ne!(random.report.termination, SearchTermination::Found);

    let add = parse_expression("(x + y)").unwrap();
    let semantics = ExprSemantics::new(3, 4).unwrap();
    let mut permuted_source = String::from("input,output\n");
    for packed in 0..64u64 {
        let x = packed & 7;
        let y = packed >> 3;
        let permuted = (packed * 29 + 7) & 63;
        let permuted_x = permuted & 7;
        let permuted_y = permuted >> 3;
        permuted_source.push_str(&bits(x, 3));
        permuted_source.push_str(&bits(y, 3));
        permuted_source.push(',');
        permuted_source.push_str(&bits(
            add.evaluate(permuted_x, permuted_y, semantics).unwrap(),
            4,
        ));
        permuted_source.push('\n');
    }
    let permuted = search_mdl(&parse_dataset(&permuted_source).unwrap(), &config).unwrap();
    assert!(
        permuted
            .expression
            .as_ref()
            .is_none_or(|expression| !equivalent_over_domain(expression, &add, semantics))
    );
}
