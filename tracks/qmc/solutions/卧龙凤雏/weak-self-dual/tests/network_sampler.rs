use weak_self_dual::config::SELF_DUAL_BETA;
use weak_self_dual::network::{BoundarySector, LayerOutcomes, SelfDualNetwork};

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
