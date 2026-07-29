use crate::disorder::DisorderRow;
use anyhow::{bail, Result};

pub fn apply_transfer(
    width: usize,
    k: f64,
    row: &DisorderRow,
    input: &[f64],
    output: &mut [f64],
) -> Result<()> {
    let dimension = dimension(width)?;
    if input.len() != dimension || output.len() != dimension {
        bail!(
            "transfer vectors must both have length 2^L = {dimension}; got {} and {}",
            input.len(),
            output.len()
        );
    }
    if !k.is_finite() {
        bail!("K must be finite");
    }
    if input.iter().any(|value| !value.is_finite()) {
        bail!("transfer input contains a non-finite value");
    }
    let bonds = row.view(width)?;

    output.copy_from_slice(input);
    for (bit, &bond) in bonds.vertical.iter().enumerate() {
        let aligned = (k * f64::from(bond)).exp();
        let opposed = (-k * f64::from(bond)).exp();
        let stride = 1_usize << bit;
        let block = stride << 1;
        for base in (0..dimension).step_by(block) {
            for offset in 0..stride {
                let i0 = base + offset;
                let i1 = i0 + stride;
                let v0 = output[i0];
                let v1 = output[i1];
                output[i0] = aligned * v0 + opposed * v1;
                output[i1] = opposed * v0 + aligned * v1;
            }
        }
    }

    for (state, value) in output.iter_mut().enumerate() {
        let horizontal_energy: i32 = (0..width)
            .map(|site| {
                let neighbor = (site + 1) % width;
                i32::from(bonds.horizontal[site]) * spin(state, site) * spin(state, neighbor)
            })
            .sum();
        *value *= (k * f64::from(horizontal_energy)).exp();
    }
    Ok(())
}

fn dimension(width: usize) -> Result<usize> {
    if width < 2 {
        bail!("transfer width L must be at least 2");
    }
    1_usize
        .checked_shl(width as u32)
        .ok_or_else(|| anyhow::anyhow!("transfer width L={width} is too large"))
}

fn spin(state: usize, bit: usize) -> i32 {
    if state & (1_usize << bit) == 0 {
        -1
    } else {
        1
    }
}
