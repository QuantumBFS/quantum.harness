use weak_self_dual::config::{RunConfig, SamplingConfig, SELF_DUAL_BETA, SELF_DUAL_THETA};
use weak_self_dual::network::{BoundarySector, LayerOutcomes, SelfDualNetwork};
use weak_self_dual::sampler::estimate_stream;

fn tiny_config(width: usize, burn_in: usize, measurement: usize, block: usize) -> RunConfig {
    RunConfig {
        widths: vec![width],
        theta: SELF_DUAL_THETA,
        beta: SELF_DUAL_BETA,
        base_seed: 122_447,
        production_gates: false,
        refinement_level: 0,
        sampling: SamplingConfig {
            streams_per_width: 2,
            burn_in_layers_per_width: burn_in,
            measurement_layers_per_width: measurement,
            block_layers_per_width: block,
            stabilize_every_layers: 1,
            invariant_tolerance: 1.0e-9,
        },
    }
}

#[test]
fn one_period_measures_each_onsite_and_bond_pair_once() {
    let network = SelfDualNetwork::vacuum(4, SELF_DUAL_BETA).unwrap();
    assert_eq!(network.onsite_measurements().len(), 4);
    assert_eq!(network.bond_measurements().len(), 4);
    let onsite = network.onsite_measurements()[0];
    assert_eq!((onsite.a, onsite.b), (0, 1));
    let bond = network.bond_measurements()[0];
    assert_eq!((bond.a, bond.b), (1, 2));
}

#[test]
fn vacuum_boundary_bilinear_has_minus_wilson_parity_sign() {
    let network = SelfDualNetwork::vacuum(4, SELF_DUAL_BETA).unwrap();
    let boundary = network.bond_measurements().last().unwrap();
    assert_eq!((boundary.a, boundary.b), (7, 0));
    assert_eq!(boundary.observable_sign, -1);
    assert_eq!(network.sector(), BoundarySector::vacuum());
}

#[test]
fn all_positive_spacetime_tile_has_no_vortices() {
    let network = SelfDualNetwork::vacuum(4, SELF_DUAL_BETA).unwrap();
    let first = LayerOutcomes::all_positive(4);
    let second = LayerOutcomes::all_positive(4);
    let counts = network.vortices_between(&first, &second).unwrap();
    assert_eq!(counts.electric, 0);
    assert_eq!(counts.magnetic, 0);
    assert_eq!(counts.faces_per_species, 4);
}

#[test]
fn one_flipped_edge_creates_adjacent_electric_and_magnetic_vortices() {
    let network = SelfDualNetwork::vacuum(4, SELF_DUAL_BETA).unwrap();
    let first = LayerOutcomes::all_positive(4);
    let mut second = LayerOutcomes::all_positive(4);
    second.onsite[0] = -1;
    let counts = network.vortices_between(&first, &second).unwrap();
    assert_eq!(counts.electric, 1);
    assert_eq!(counts.magnetic, 1);
}

#[test]
fn one_majorana_translation_exchanges_vortex_species() {
    let network = SelfDualNetwork::vacuum(4, SELF_DUAL_BETA).unwrap();
    let first = LayerOutcomes {
        onsite: vec![-1, 1, 1, 1],
        bond: vec![1, -1, 1, 1],
    };
    let second = LayerOutcomes::all_positive(4);
    let original = network.vortices_between(&first, &second).unwrap();
    let translated = network
        .vortices_between(
            &first.translated_one_majorana(),
            &second.translated_one_majorana(),
        )
        .unwrap();
    assert_eq!(original.electric, translated.magnetic);
    assert_eq!(original.magnetic, translated.electric);
}

#[test]
fn gamma_is_born_surprise_per_complete_layer() {
    let config = tiny_config(2, 0, 4, 2);
    let estimate = estimate_stream(&config, 2, 0).unwrap();
    assert_eq!(estimate.blocks.len(), 2);
    assert!(estimate
        .blocks
        .iter()
        .all(|block| block.gamma.is_finite() && block.gamma > 0.0));
}

#[test]
fn stream_replay_is_exact() {
    let config = tiny_config(2, 2, 8, 2);
    assert_eq!(
        estimate_stream(&config, 2, 1).unwrap(),
        estimate_stream(&config, 2, 1).unwrap()
    );
}

#[test]
fn sampler_records_finite_invariants_and_vortex_denominators() {
    let config = tiny_config(2, 2, 8, 2);
    let estimate = estimate_stream(&config, 2, 0).unwrap();
    assert!(estimate
        .blocks
        .iter()
        .all(|block| block.max_invariant_error <= 1.0e-9));
    assert!(estimate
        .blocks
        .iter()
        .all(|block| block.faces_per_species > 0));
}
