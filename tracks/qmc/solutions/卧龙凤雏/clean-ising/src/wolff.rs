use crate::lattice::IsingLattice;
use rand_xoshiro::rand_core::Rng;
use rand_xoshiro::Xoshiro256PlusPlus;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SweepStats {
    pub updates: usize,
    pub total_flipped: usize,
    pub max_cluster_size: usize,
}

pub fn wolff_update(lattice: &mut IsingLattice, k: f64, rng: &mut Xoshiro256PlusPlus) -> usize {
    assert!(
        k.is_finite() && k >= 0.0,
        "K must be finite and nonnegative"
    );
    begin_cluster(lattice);
    let epoch = lattice.mark_epoch;
    let seed = uniform_index(rng, lattice.site_count());
    let target_spin = lattice.spins[seed];
    lattice.marks[seed] = epoch;
    lattice.stack.push(seed);
    lattice.cluster.push(seed);

    let p_add = 1.0 - (-2.0 * k).exp();
    while let Some(site) = lattice.stack.pop() {
        for neighbor in lattice.neighbors(site) {
            if lattice.marks[neighbor] != epoch
                && lattice.spins[neighbor] == target_spin
                && uniform_unit(rng) < p_add
            {
                lattice.marks[neighbor] = epoch;
                lattice.stack.push(neighbor);
                lattice.cluster.push(neighbor);
            }
        }
    }

    let mut delta_energy = 0_i64;
    for &site in &lattice.cluster {
        for neighbor in lattice.neighbors(site) {
            if lattice.marks[neighbor] != epoch {
                delta_energy += 2 * i64::from(lattice.spins[site] * lattice.spins[neighbor]);
            }
        }
    }
    for &site in &lattice.cluster {
        lattice.spins[site] = -lattice.spins[site];
    }
    lattice.energy += delta_energy;
    lattice.cluster.len()
}

pub fn effective_sweep(
    lattice: &mut IsingLattice,
    k: f64,
    rng: &mut Xoshiro256PlusPlus,
) -> SweepStats {
    let target = lattice.site_count();
    let mut stats = SweepStats {
        updates: 0,
        total_flipped: 0,
        max_cluster_size: 0,
    };
    while stats.total_flipped < target {
        let cluster_size = wolff_update(lattice, k, rng);
        stats.updates += 1;
        stats.total_flipped += cluster_size;
        stats.max_cluster_size = stats.max_cluster_size.max(cluster_size);
    }
    stats
}

pub fn fixed_cluster_sweep(
    lattice: &mut IsingLattice,
    k: f64,
    rng: &mut Xoshiro256PlusPlus,
    updates: usize,
) -> SweepStats {
    assert!(
        updates > 0,
        "fixed cluster sweep requires at least one update"
    );
    let mut stats = SweepStats {
        updates: 0,
        total_flipped: 0,
        max_cluster_size: 0,
    };
    for _ in 0..updates {
        let cluster_size = wolff_update(lattice, k, rng);
        stats.updates += 1;
        stats.total_flipped += cluster_size;
        stats.max_cluster_size = stats.max_cluster_size.max(cluster_size);
    }
    stats
}

fn begin_cluster(lattice: &mut IsingLattice) {
    lattice.mark_epoch = lattice.mark_epoch.wrapping_add(1);
    if lattice.mark_epoch == 0 {
        lattice.marks.fill(0);
        lattice.mark_epoch = 1;
    }
    lattice.stack.clear();
    lattice.cluster.clear();
}

fn uniform_index(rng: &mut Xoshiro256PlusPlus, upper: usize) -> usize {
    ((u128::from(rng.next_u64()) * upper as u128) >> 64) as usize
}

fn uniform_unit(rng: &mut Xoshiro256PlusPlus) -> f64 {
    const SCALE: f64 = 1.0 / ((1_u64 << 53) as f64);
    ((rng.next_u64() >> 11) as f64) * SCALE
}
