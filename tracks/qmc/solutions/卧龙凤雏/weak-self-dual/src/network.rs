use crate::covariance::Measurement;
use anyhow::{bail, Result};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct BoundarySector {
    pub wilson_loop: i8,
    pub fermion_parity: i8,
}

impl BoundarySector {
    pub const fn vacuum() -> Self {
        Self {
            wilson_loop: 1,
            fermion_parity: 1,
        }
    }

    fn validate(self) -> Result<()> {
        if !matches!(self.wilson_loop, -1 | 1) || !matches!(self.fermion_parity, -1 | 1) {
            bail!("boundary-sector quantum numbers must be +1 or -1");
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct LayerOutcomes {
    pub onsite: Vec<i8>,
    pub bond: Vec<i8>,
}

impl LayerOutcomes {
    pub fn all_positive(width: usize) -> Self {
        Self {
            onsite: vec![1; width],
            bond: vec![1; width],
        }
    }

    pub fn translated_one_majorana(&self) -> Self {
        let mut edges = self.interleaved();
        edges.rotate_left(1);
        Self::from_interleaved(&edges)
    }

    fn validate(&self, width: usize) -> Result<()> {
        if self.onsite.len() != width || self.bond.len() != width {
            bail!("layer outcome lengths must equal the cylinder width");
        }
        if self
            .onsite
            .iter()
            .chain(&self.bond)
            .any(|&sign| !matches!(sign, -1 | 1))
        {
            bail!("layer outcomes must be +1 or -1");
        }
        Ok(())
    }

    fn interleaved(&self) -> Vec<i8> {
        let mut edges = Vec::with_capacity(self.onsite.len() + self.bond.len());
        for (&onsite, &bond) in self.onsite.iter().zip(&self.bond) {
            edges.push(onsite);
            edges.push(bond);
        }
        edges
    }

    fn from_interleaved(edges: &[i8]) -> Self {
        let mut onsite = Vec::with_capacity(edges.len() / 2);
        let mut bond = Vec::with_capacity(edges.len() / 2);
        for pair in edges.chunks_exact(2) {
            onsite.push(pair[0]);
            bond.push(pair[1]);
        }
        Self { onsite, bond }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct VortexCounts {
    pub electric: usize,
    pub magnetic: usize,
    pub faces_per_species: usize,
}

#[derive(Debug, Clone)]
pub struct SelfDualNetwork {
    width: usize,
    sector: BoundarySector,
    onsite: Vec<Measurement>,
    bond: Vec<Measurement>,
}

impl SelfDualNetwork {
    pub fn vacuum(width: usize, beta: f64) -> Result<Self> {
        Self::new(width, beta, BoundarySector::vacuum())
    }

    pub fn new(width: usize, beta: f64, sector: BoundarySector) -> Result<Self> {
        if width < 2 || width % 2 != 0 {
            bail!("self-dual network width must be even and at least 2");
        }
        if !beta.is_finite() || beta < 0.0 {
            bail!("self-dual network beta must be finite and non-negative");
        }
        sector.validate()?;
        let onsite = (0..width)
            .map(|site| Measurement {
                a: 2 * site,
                b: 2 * site + 1,
                observable_sign: 1,
                beta,
            })
            .collect();
        let bond = (0..width)
            .map(|site| {
                let wraps = site + 1 == width;
                Measurement {
                    a: 2 * site + 1,
                    b: 2 * ((site + 1) % width),
                    observable_sign: if wraps {
                        -sector.wilson_loop * sector.fermion_parity
                    } else {
                        1
                    },
                    beta,
                }
            })
            .collect();
        Ok(Self {
            width,
            sector,
            onsite,
            bond,
        })
    }

    pub fn width(&self) -> usize {
        self.width
    }

    pub fn sector(&self) -> BoundarySector {
        self.sector
    }

    pub fn onsite_measurements(&self) -> &[Measurement] {
        &self.onsite
    }

    pub fn bond_measurements(&self) -> &[Measurement] {
        &self.bond
    }

    pub fn vortices_between(
        &self,
        previous: &LayerOutcomes,
        current: &LayerOutcomes,
    ) -> Result<VortexCounts> {
        previous.validate(self.width)?;
        current.validate(self.width)?;
        let previous_edges = previous.interleaved();
        let current_edges = current.interleaved();
        let face_count = previous_edges.len();
        let mut electric = 0;
        let mut magnetic = 0;
        for index in 0..face_count {
            let next = (index + 1) % face_count;
            let flux = previous_edges[index]
                * previous_edges[next]
                * current_edges[next]
                * current_edges[index];
            if flux == -1 {
                if index % 2 == 0 {
                    electric += 1;
                } else {
                    magnetic += 1;
                }
            }
        }
        Ok(VortexCounts {
            electric,
            magnetic,
            faces_per_species: self.width,
        })
    }
}
