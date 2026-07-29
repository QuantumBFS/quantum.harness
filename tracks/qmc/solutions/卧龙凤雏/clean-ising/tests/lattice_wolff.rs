use clean_ising::lattice::IsingLattice;
use clean_ising::rng::make_rng;
use clean_ising::wolff::{effective_sweep, wolff_update};

#[test]
fn periodic_neighbors_wrap_both_axes() {
    let lattice = IsingLattice::all_up(4, 6);
    assert_eq!(lattice.neighbors(0), [1, 3, 4, 20]);
}

#[test]
fn all_up_energy_counts_each_right_and_down_bond_once() {
    let lattice = IsingLattice::all_up(4, 6);
    assert_eq!(lattice.site_count(), 24);
    assert_eq!(lattice.energy(), -48);
    assert_eq!(lattice.energy(), lattice.recompute_energy());
}

#[test]
fn wolff_updates_preserve_incremental_energy() {
    let mut rng = make_rng(17);
    let mut lattice = IsingLattice::random(6, 8, &mut rng);
    for _ in 0..200 {
        wolff_update(&mut lattice, 0.440_686_793_509_771_47, &mut rng);
        assert_eq!(lattice.energy(), lattice.recompute_energy());
    }
}

#[test]
fn effective_sweep_flips_at_least_one_lattice_volume() {
    let mut rng = make_rng(23);
    let mut lattice = IsingLattice::random(6, 8, &mut rng);
    let stats = effective_sweep(&mut lattice, 0.2, &mut rng);
    assert!(stats.total_flipped >= lattice.site_count());
    assert!(stats.updates > 0);
    assert!((1..=lattice.site_count()).contains(&stats.max_cluster_size));
}
