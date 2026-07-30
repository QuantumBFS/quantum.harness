use learning_mit::angles::GateCouplings;
use learning_mit::circuit::{BoundarySector, GenericCircuit, SamplingMode};
use learning_mit::config::RunConfig;
use learning_mit::gaussian::MajoranaState;
use learning_mit::rng::make_rng;
use learning_mit::sampler::estimate_stream;
use std::path::Path;

#[test]
fn one_period_has_exactly_two_measurement_rows() {
    let circuit = fixture_circuit(4);
    let mut state = MajoranaState::paired_vacuum(4).unwrap();
    let mut rng = make_rng(7);
    let sample = circuit
        .sample_period(&mut state, &mut rng, SamplingMode::Born)
        .unwrap();

    assert_eq!(sample.onsite.len(), 4);
    assert_eq!(sample.bond.len(), 4);
    assert_eq!(sample.conditional_entropy_terms, 8);
    assert_eq!(sample.applied_gates.len(), 8);
    assert!(sample.min_probability > 0.0);
}

#[test]
fn fixed_seed_replays_the_complete_period() {
    assert_eq!(run_fixture(122), run_fixture(122));
}

#[test]
fn wraparound_bond_carries_the_boundary_sector_sign() {
    let circuit = fixture_circuit(4);
    assert_eq!(
        circuit
            .bond_gates()
            .last()
            .unwrap()
            .measurement
            .observable_sign,
        -1
    );
    assert!(circuit
        .bond_gates()
        .iter()
        .take(3)
        .all(|gate| gate.measurement.observable_sign == 1));
}

#[test]
fn stream_estimator_returns_complete_blocks_and_tags_iid_as_diagnostic() {
    let config = RunConfig::load(Path::new("configs/test.toml")).unwrap();
    let born = estimate_stream(&config, 0, 0, 2, 0, SamplingMode::Born).unwrap();
    let iid = estimate_stream(&config, 0, 0, 2, 0, SamplingMode::IidDiagnostic).unwrap();

    assert_eq!(born.blocks.len(), 2);
    assert!(born.is_physical);
    assert!(!iid.is_physical);
    assert!(born
        .blocks
        .iter()
        .all(|block| block.min_probability > 0.0 && block.min_probability <= 1.0));
}

fn fixture_circuit(width: usize) -> GenericCircuit {
    let couplings = GateCouplings::from_pi_units(0.5, 0.25).unwrap();
    GenericCircuit::new(width, couplings, BoundarySector::vacuum()).unwrap()
}

fn run_fixture(seed: u64) -> (learning_mit::circuit::PeriodSample, Vec<f64>) {
    let circuit = fixture_circuit(4);
    let mut state = MajoranaState::paired_vacuum(4).unwrap();
    let mut rng = make_rng(seed);
    let sample = circuit
        .sample_period(&mut state, &mut rng, SamplingMode::Born)
        .unwrap();
    (sample, state.matrix().iter().copied().collect())
}
