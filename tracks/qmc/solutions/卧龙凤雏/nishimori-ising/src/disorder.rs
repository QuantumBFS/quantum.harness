use anyhow::{bail, Result};
use rand_xoshiro::rand_core::Rng;
use rand_xoshiro::Xoshiro256PlusPlus;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DisorderRow {
    pub horizontal: Vec<i8>,
    pub vertical: Vec<i8>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct DisorderView<'a> {
    pub horizontal: &'a [i8],
    pub vertical: &'a [i8],
}

impl DisorderRow {
    pub fn max_width(&self) -> usize {
        self.horizontal.len().min(self.vertical.len())
    }

    pub fn view(&self, width: usize) -> Result<DisorderView<'_>> {
        validate_bonds(&self.horizontal)?;
        validate_bonds(&self.vertical)?;
        if width == 0 || self.horizontal.len() < width || self.vertical.len() < width {
            bail!(
                "disorder row has horizontal/vertical lengths {}/{} but width {width} was requested",
                self.horizontal.len(),
                self.vertical.len()
            );
        }
        Ok(DisorderView {
            horizontal: &self.horizontal[..width],
            vertical: &self.vertical[..width],
        })
    }
}

pub fn sample_row(
    max_width: usize,
    antiferromagnetic_probability: f64,
    rng: &mut Xoshiro256PlusPlus,
) -> Result<DisorderRow> {
    if max_width == 0 {
        bail!("maximum disorder width must be positive");
    }
    if !antiferromagnetic_probability.is_finite()
        || !(0.0..=1.0).contains(&antiferromagnetic_probability)
    {
        bail!("antiferromagnetic probability must lie in [0, 1]");
    }

    // Generate site-paired bonds so each stored row has one canonical
    // maximum-width sequence from which every simulated width takes a prefix.
    let mut horizontal = Vec::with_capacity(max_width);
    let mut vertical = Vec::with_capacity(max_width);
    for _ in 0..max_width {
        horizontal.push(sample_bond(antiferromagnetic_probability, rng));
        vertical.push(sample_bond(antiferromagnetic_probability, rng));
    }
    Ok(DisorderRow {
        horizontal,
        vertical,
    })
}

fn sample_bond(probability: f64, rng: &mut Xoshiro256PlusPlus) -> i8 {
    const SCALE: f64 = 1.0 / ((1_u64 << 53) as f64);
    let uniform = ((rng.next_u64() >> 11) as f64) * SCALE;
    if uniform < probability {
        -1
    } else {
        1
    }
}

fn validate_bonds(bonds: &[i8]) -> Result<()> {
    if bonds.iter().any(|&bond| bond != -1 && bond != 1) {
        bail!("every disorder bond must be either -1 or +1");
    }
    Ok(())
}
