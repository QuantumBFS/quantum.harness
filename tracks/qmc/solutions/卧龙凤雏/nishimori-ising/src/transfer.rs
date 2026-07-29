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

    apply_horizontal_diagonal(width, k, bonds.horizontal, output);
    Ok(())
}

fn apply_horizontal_diagonal(width: usize, k: f64, bonds: &[i8], output: &mut [f64]) {
    // The horizontal energy assumes only width+1 possible values. Cache their
    // exponentials, then traverse spin states in Gray-code order. One flipped
    // spin changes exactly its two adjacent bond products, reducing this stage
    // from O(L 2^L) to O(2^L) without changing the transfer operator.
    let mut exponentials = [0.0; usize::BITS as usize + 1];
    for (index, destination) in exponentials.iter_mut().enumerate().take(width + 1) {
        let energy = 2 * index as i32 - width as i32;
        *destination = (k * f64::from(energy)).exp();
    }

    let mut products = [0_i32; usize::BITS as usize];
    for (destination, &bond) in products.iter_mut().zip(bonds) {
        *destination = i32::from(bond);
    }
    let mut energy: i32 = products[..width].iter().sum();
    let mut gray_state = 0_usize;
    output[gray_state] *= exponentials[energy_index(energy, width)];
    for step in 1..output.len() {
        let flipped = step.trailing_zeros() as usize;
        let previous_bond = (flipped + width - 1) % width;
        energy -= 2 * (products[previous_bond] + products[flipped]);
        products[previous_bond] = -products[previous_bond];
        products[flipped] = -products[flipped];
        gray_state ^= 1_usize << flipped;
        output[gray_state] *= exponentials[energy_index(energy, width)];
    }
}

fn energy_index(energy: i32, width: usize) -> usize {
    ((energy + width as i32) / 2) as usize
}

fn dimension(width: usize) -> Result<usize> {
    if width < 2 {
        bail!("transfer width L must be at least 2");
    }
    1_usize
        .checked_shl(width as u32)
        .ok_or_else(|| anyhow::anyhow!("transfer width L={width} is too large"))
}
