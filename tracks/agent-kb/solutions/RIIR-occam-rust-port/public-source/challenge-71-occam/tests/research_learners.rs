use occam71_rust::{ResearchMethod, ResearchTools, default_adapters};

#[test]
fn every_automatic_method_has_exactly_one_adapter() {
    let adapters = default_adapters(ResearchTools::default());
    assert_eq!(ResearchMethod::AUTOMATIC.len(), 7);
    assert_eq!(adapters.len(), ResearchMethod::AUTOMATIC.len());

    for method in ResearchMethod::AUTOMATIC {
        assert_eq!(
            adapters
                .iter()
                .filter(|adapter| adapter.method() == method)
                .count(),
            1,
            "{method:?} must have exactly one adapter"
        );
    }
}

#[test]
fn oracle_is_not_an_automatic_adapter() {
    assert!(!ResearchMethod::AUTOMATIC.contains(&ResearchMethod::OracleExpression));

    let learner_api = include_str!("../src/research/learner.rs");
    let adapters = include_str!("../src/research/adapters.rs");
    assert!(!learner_api.contains("OracleTask"));
    assert!(!adapters.contains("OracleTask"));
}
