use crate::config::ExactConfig;
use anyhow::{bail, Result};

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct EigenResult {
    pub lambda: f64,
    pub iterations: usize,
    pub relative_change: f64,
    pub residual: f64,
}

pub fn apply_transfer(l: usize, k: f64, input: &[f64], output: &mut [f64]) -> Result<()> {
    let dimension = dimension(l)?;
    if input.len() != dimension || output.len() != dimension {
        bail!(
            "transfer vectors must both have length 2^L = {dimension}; got {} and {}",
            input.len(),
            output.len()
        );
    }
    if !k.is_finite() || k < 0.0 {
        bail!("K must be finite and nonnegative");
    }
    if input.iter().any(|value| !value.is_finite()) {
        bail!("transfer input contains a non-finite value");
    }
    let diagonal = horizontal_diagonal(l, k, dimension);
    apply_with_diagonal(l, k, &diagonal, input, output);
    Ok(())
}

pub fn dominant_eigenpair(l: usize, k: f64, config: &ExactConfig) -> Result<EigenResult> {
    let dimension = dimension(l)?;
    if !k.is_finite() || k < 0.0 {
        bail!("K must be finite and nonnegative");
    }
    if config.max_iterations == 0
        || !config.eigenvalue_tolerance.is_finite()
        || config.eigenvalue_tolerance <= 0.0
        || !config.residual_tolerance.is_finite()
        || config.residual_tolerance <= 0.0
    {
        bail!("invalid exact eigensolver configuration");
    }

    let diagonal = horizontal_diagonal(l, k, dimension);
    let initial = 1.0 / (dimension as f64).sqrt();
    let mut vector = vec![initial; dimension];
    let mut output = vec![0.0; dimension];
    let mut previous_lambda: Option<f64> = None;
    let mut last_relative_change = f64::INFINITY;
    let mut last_residual = f64::INFINITY;
    let mut last_lambda = f64::NAN;

    for iteration in 1..=config.max_iterations {
        apply_with_diagonal(l, k, &diagonal, &vector, &mut output);
        let norm = l2_norm(&output);
        if !norm.is_finite() || norm == 0.0 {
            bail!("transfer iteration produced invalid norm {norm}");
        }
        for value in &mut output {
            *value /= norm;
        }
        std::mem::swap(&mut vector, &mut output);

        apply_with_diagonal(l, k, &diagonal, &vector, &mut output);
        let lambda = dot(&vector, &output);
        if !lambda.is_finite() || lambda <= 0.0 {
            bail!("transfer iteration produced invalid eigenvalue {lambda}");
        }
        last_relative_change = previous_lambda
            .map(|previous| (lambda - previous).abs() / lambda.abs().max(1.0))
            .unwrap_or(f64::INFINITY);
        let residual_norm = vector
            .iter()
            .zip(output.iter())
            .map(|(x, tx)| {
                let difference = tx - lambda * x;
                difference * difference
            })
            .sum::<f64>()
            .sqrt();
        last_residual = residual_norm / lambda.abs();
        last_lambda = lambda;

        if last_relative_change <= config.eigenvalue_tolerance
            && last_residual <= config.residual_tolerance
        {
            return Ok(EigenResult {
                lambda,
                iterations: iteration,
                relative_change: last_relative_change,
                residual: last_residual,
            });
        }
        previous_lambda = Some(lambda);
    }

    bail!(
        "dominant eigenpair did not converge after {} iterations: \
         lambda={last_lambda:.16e}, relative_change={last_relative_change:.3e}, \
         relative_residual={last_residual:.3e}",
        config.max_iterations
    )
}

fn dimension(l: usize) -> Result<usize> {
    if l < 2 {
        bail!("transfer width L must be at least 2");
    }
    1_usize
        .checked_shl(l as u32)
        .ok_or_else(|| anyhow::anyhow!("transfer width L={l} is too large"))
}

fn horizontal_diagonal(l: usize, k: f64, dimension: usize) -> Vec<f64> {
    (0..dimension)
        .map(|state| {
            let horizontal_sum: i32 = (0..l)
                .map(|bit| {
                    let next = (bit + 1) % l;
                    spin(state, bit) * spin(state, next)
                })
                .sum();
            (0.5 * k * f64::from(horizontal_sum)).exp()
        })
        .collect()
}

fn apply_with_diagonal(l: usize, k: f64, diagonal: &[f64], input: &[f64], output: &mut [f64]) {
    for ((destination, source), factor) in output.iter_mut().zip(input.iter()).zip(diagonal.iter())
    {
        *destination = factor * source;
    }

    let same = k.exp();
    let different = (-k).exp();
    for bit in 0..l {
        let stride = 1_usize << bit;
        let block = stride << 1;
        for base in (0..output.len()).step_by(block) {
            for offset in 0..stride {
                let i0 = base + offset;
                let i1 = i0 + stride;
                let v0 = output[i0];
                let v1 = output[i1];
                output[i0] = same * v0 + different * v1;
                output[i1] = different * v0 + same * v1;
            }
        }
    }

    for (value, factor) in output.iter_mut().zip(diagonal.iter()) {
        *value *= factor;
    }
}

fn spin(state: usize, bit: usize) -> i32 {
    if state & (1_usize << bit) == 0 {
        -1
    } else {
        1
    }
}

fn dot(left: &[f64], right: &[f64]) -> f64 {
    left.iter().zip(right).map(|(x, y)| x * y).sum()
}

fn l2_norm(vector: &[f64]) -> f64 {
    dot(vector, vector).sqrt()
}
