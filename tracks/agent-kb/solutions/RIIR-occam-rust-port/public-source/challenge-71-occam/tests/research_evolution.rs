use occam71_rust::{
    EvolutionConfig, GrammarEvolutionLearner, ObservedTask, ResearchLearner, Sample, TrialBudget,
    evolve,
};

fn complete_small_xor() -> ObservedTask {
    ObservedTask {
        id: "xor".into(),
        input_width: 2,
        output_width: 1,
        samples: vec![
            Sample {
                input: vec![false, false],
                expected: vec![false],
            },
            Sample {
                input: vec![false, true],
                expected: vec![true],
            },
            Sample {
                input: vec![true, false],
                expected: vec![true],
            },
            Sample {
                input: vec![true, true],
                expected: vec![false],
            },
        ],
    }
}

#[test]
fn evolution_is_seeded_and_recovers_xor() {
    let task = complete_small_xor();
    let first = evolve(&task, 42, EvolutionConfig::for_tests()).unwrap();
    let second = evolve(&task, 42, EvolutionConfig::for_tests()).unwrap();
    assert_eq!(first, second);
    assert_eq!(first.best_expression.to_string(), "(x XOR y)");
    assert_eq!(first.best_row_mismatches, 0);
}

#[test]
fn evolution_adapter_returns_the_independent_best_expression() {
    let learned = GrammarEvolutionLearner::new(EvolutionConfig::for_tests())
        .fit(&complete_small_xor(), 42, &TrialBudget::default())
        .unwrap();
    let text = format!("{learned:?}");
    assert!(text.contains("BitXor"));
}

#[test]
fn evolution_source_does_not_call_mdl_search() {
    assert!(!include_str!("../src/research/evolution.rs").contains("search_mdl"));
}
