use occam71_rust::{
    BddOrder, LearnedHypothesis, MemorizationLearner, ObservedTask, ResearchLearner, RobddLearner,
    Sample, TrialBudget, build_robdd, parse_netlist, verify,
};

fn observed_xor() -> ObservedTask {
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

fn learned_circuit(hypothesis: LearnedHypothesis) -> String {
    match hypothesis {
        LearnedHypothesis::Circuit { netlist, .. } => netlist,
        LearnedHypothesis::Expression { .. } => panic!("expected a learned circuit"),
    }
}

#[test]
fn memorization_is_a_real_training_consistent_trie() {
    let observed = ObservedTask {
        id: "partial-memory".into(),
        input_width: 2,
        output_width: 1,
        samples: vec![
            Sample {
                input: vec![false, true],
                expected: vec![true],
            },
            Sample {
                input: vec![true, false],
                expected: vec![true],
            },
        ],
    };
    let netlist = learned_circuit(
        MemorizationLearner
            .fit(&observed, 0, &TrialBudget::default())
            .unwrap(),
    );
    let circuit = parse_netlist(&netlist).unwrap();
    let training = verify(&circuit, &observed.dataset()).unwrap();
    assert_eq!(training.exact_matches, training.samples);
    assert!(!circuit.gates.is_empty());

    let missing_rows = ObservedTask {
        id: "missing".into(),
        input_width: 2,
        output_width: 1,
        samples: vec![
            Sample {
                input: vec![false, false],
                expected: vec![false],
            },
            Sample {
                input: vec![true, true],
                expected: vec![false],
            },
        ],
    };
    let completion = verify(&circuit, &missing_rows.dataset()).unwrap();
    assert_eq!(completion.exact_matches, completion.samples);
}

#[test]
fn robdd_reduces_and_compiles_a_complete_boolean_function() {
    let observed = observed_xor();
    let budget = TrialBudget::default();
    for order in BddOrder::ALL {
        let result = build_robdd(&observed, order, &budget).unwrap();
        let circuit = parse_netlist(&result.netlist).unwrap();
        let metrics = verify(&circuit, &observed.dataset()).unwrap();
        assert_eq!(metrics.exact_matches, metrics.samples, "{order:?}");
        assert!(circuit.gates.len() <= 3, "{order:?}");
    }

    let selected = learned_circuit(RobddLearner.fit(&observed, 0, &budget).unwrap());
    let selected_circuit = parse_netlist(&selected).unwrap();
    assert!(selected_circuit.gates.len() <= 3);
}

#[test]
fn circuit_baselines_do_not_share_the_old_zero_default_shortcut() {
    let adapters = include_str!("../src/research/adapters.rs");
    assert!(!adapters.contains("ZeroDefaultMemory"));
    assert!(!adapters.contains("ResearchMethod::AbcDontCare\n            | ResearchMethod::Robdd"));
}
