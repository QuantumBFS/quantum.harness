use std::{path::PathBuf, time::Duration};

use occam71_rust::{
    AbcDontCareLearner, LearnedHypothesis, LearnerFailure, ObservedTask, ResearchLearner, Sample,
    SatCegisLearner, TrialBudget, parse_netlist, render_partial_pla, verify,
};

fn complete_xor() -> ObservedTask {
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

fn pinned_abc() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .join("target/tools/abc/e76768b9d34f9dc67cb6608efecd55db271ff849/abc")
}

fn assert_fits(learned: LearnedHypothesis, observed: &ObservedTask) {
    let LearnedHypothesis::Circuit { netlist, .. } = learned else {
        panic!("logic baseline must return a circuit");
    };
    let circuit = parse_netlist(&netlist).unwrap();
    let metrics = verify(&circuit, &observed.dataset()).unwrap();
    assert_eq!(metrics.exact_matches, metrics.samples);
}

#[test]
fn abc_and_sat_fit_complete_two_bit_xor() {
    let observed = complete_xor();
    let budget = TrialBudget {
        timeout: Duration::from_secs(20),
        max_gates: 4,
        max_nodes: 250_000,
    };
    assert!(pinned_abc().is_file(), "run ./scripts/fetch-abc.sh");
    assert_fits(
        AbcDontCareLearner::new(Some(pinned_abc()))
            .fit(&observed, 11, &budget)
            .unwrap(),
        &observed,
    );
    assert_fits(
        SatCegisLearner.fit(&observed, 11, &budget).unwrap(),
        &observed,
    );
}

#[test]
fn partial_pla_declares_unobserved_subspaces_as_dont_cares() {
    let observed = ObservedTask {
        id: "partial".into(),
        input_width: 2,
        output_width: 1,
        samples: vec![Sample {
            input: vec![false, true],
            expected: vec![true],
        }],
    };
    let pla = render_partial_pla(&observed).unwrap();
    assert!(pla.contains(".type fd"));
    assert!(pla.contains("01 1"));
    assert!(pla.contains("00 -"));
    assert!(pla.contains("1- -"));

    let budget = TrialBudget {
        timeout: Duration::from_secs(20),
        max_gates: 4,
        max_nodes: 250_000,
    };
    assert_fits(
        AbcDontCareLearner::new(Some(pinned_abc()))
            .fit(&observed, 0, &budget)
            .unwrap(),
        &observed,
    );
}

#[test]
fn abc_missing_and_failed_processes_are_typed() {
    let observed = complete_xor();
    let budget = TrialBudget::default();
    let missing = AbcDontCareLearner::new(None)
        .fit(&observed, 0, &budget)
        .unwrap_err();
    assert!(matches!(missing, LearnerFailure::Unsupported(_)));

    let failed = AbcDontCareLearner::new(Some(PathBuf::from("/usr/bin/false")))
        .fit(&observed, 0, &budget)
        .unwrap_err();
    assert!(matches!(failed, LearnerFailure::ToolError(_)));
}

#[test]
fn sat_cegis_preserves_width_timeout_and_resource_failures() {
    let wide = ObservedTask {
        id: "wide".into(),
        input_width: 9,
        output_width: 1,
        samples: vec![Sample {
            input: vec![false; 9],
            expected: vec![false],
        }],
    };
    assert!(matches!(
        SatCegisLearner
            .fit(&wide, 0, &TrialBudget::default())
            .unwrap_err(),
        LearnerFailure::Unsupported(_)
    ));

    let timed_out = TrialBudget {
        timeout: Duration::ZERO,
        ..TrialBudget::default()
    };
    assert!(matches!(
        SatCegisLearner
            .fit(&complete_xor(), 0, &timed_out)
            .unwrap_err(),
        LearnerFailure::Timeout(_)
    ));

    let constrained = TrialBudget {
        max_nodes: 1,
        ..TrialBudget::default()
    };
    assert!(matches!(
        SatCegisLearner
            .fit(&complete_xor(), 0, &constrained)
            .unwrap_err(),
        LearnerFailure::ResourceLimit(_)
    ));
}
