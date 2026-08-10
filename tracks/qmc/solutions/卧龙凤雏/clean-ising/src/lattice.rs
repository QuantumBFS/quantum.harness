use rand_xoshiro::rand_core::Rng;
use rand_xoshiro::Xoshiro256PlusPlus;

#[derive(Debug, Clone)]
pub struct IsingLattice {
    pub(crate) l: usize,
    pub(crate) m: usize,
    pub(crate) spins: Vec<i8>,
    pub(crate) energy: i64,
    pub(crate) marks: Vec<u32>,
    pub(crate) mark_epoch: u32,
    pub(crate) stack: Vec<usize>,
    pub(crate) cluster: Vec<usize>,
}

impl IsingLattice {
    pub fn all_up(l: usize, m: usize) -> Self {
        Self::from_spins(
            l,
            m,
            vec![1; l.checked_mul(m).expect("lattice size overflow")],
        )
    }

    pub fn random(l: usize, m: usize, rng: &mut Xoshiro256PlusPlus) -> Self {
        validate_shape(l, m);
        let spins = (0..l * m)
            .map(|_| if rng.next_u64() >> 63 == 0 { -1 } else { 1 })
            .collect();
        Self::from_spins(l, m, spins)
    }

    pub fn from_spins(l: usize, m: usize, spins: Vec<i8>) -> Self {
        validate_shape(l, m);
        assert_eq!(spins.len(), l * m, "spin count must equal L*M");
        assert!(
            spins.iter().all(|&spin| spin == -1 || spin == 1),
            "Ising spins must be -1 or +1"
        );
        let mut lattice = Self {
            l,
            m,
            spins,
            energy: 0,
            marks: vec![0; l * m],
            mark_epoch: 0,
            stack: Vec::with_capacity(l * m),
            cluster: Vec::with_capacity(l * m),
        };
        lattice.energy = lattice.recompute_energy();
        lattice
    }

    pub fn neighbors(&self, index: usize) -> [usize; 4] {
        assert!(index < self.site_count(), "site index out of bounds");
        let x = index % self.l;
        let y = index / self.l;
        [
            self.index((x + 1) % self.l, y),
            self.index((x + self.l - 1) % self.l, y),
            self.index(x, (y + 1) % self.m),
            self.index(x, (y + self.m - 1) % self.m),
        ]
    }

    pub fn energy(&self) -> i64 {
        self.energy
    }

    pub fn recompute_energy(&self) -> i64 {
        let mut bonds = 0_i64;
        for y in 0..self.m {
            for x in 0..self.l {
                let i = self.index(x, y);
                let right = self.index((x + 1) % self.l, y);
                let down = self.index(x, (y + 1) % self.m);
                bonds += i64::from(self.spins[i] * self.spins[right]);
                bonds += i64::from(self.spins[i] * self.spins[down]);
            }
        }
        -bonds
    }

    pub fn site_count(&self) -> usize {
        self.spins.len()
    }

    pub fn width(&self) -> usize {
        self.l
    }

    pub fn length(&self) -> usize {
        self.m
    }

    pub fn spins(&self) -> &[i8] {
        &self.spins
    }

    fn index(&self, x: usize, y: usize) -> usize {
        y * self.l + x
    }
}

fn validate_shape(l: usize, m: usize) {
    assert!(l >= 2 && m >= 2, "lattice dimensions must be at least 2");
    assert!(l % 2 == 0, "standard lattice width must be even");
    l.checked_mul(m).expect("lattice size overflow");
}
