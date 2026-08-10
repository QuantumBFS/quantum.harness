//! Stabilized complex transfer evolution and Lyapunov spectra.

use anyhow::{bail, Result};
use nalgebra::DMatrix;
use num_complex::Complex64;

#[derive(Clone, Debug)]
pub struct LyapunovAccumulator {
    dimension: usize,
    qr_every: usize,
    completed_layers: usize,
    layers_since_qr: usize,
    basis: DMatrix<Complex64>,
    log_norms: Vec<f64>,
}

impl LyapunovAccumulator {
    pub fn new(dimension: usize, qr_every: usize) -> Result<Self> {
        if dimension == 0 {
            bail!("Lyapunov dimension must be positive");
        }
        if qr_every == 0 {
            bail!("Lyapunov QR interval must be positive");
        }
        Ok(Self {
            dimension,
            qr_every,
            completed_layers: 0,
            layers_since_qr: 0,
            basis: DMatrix::identity(dimension, dimension),
            log_norms: vec![0.0; dimension],
        })
    }

    pub fn push(&mut self, gate: &DMatrix<Complex64>) -> Result<()> {
        if gate.nrows() != self.dimension || gate.ncols() != self.dimension {
            bail!("transfer gate shape differs from the Lyapunov dimension");
        }
        if gate
            .iter()
            .any(|value| !value.re.is_finite() || !value.im.is_finite())
        {
            bail!("transfer gate contains non-finite values");
        }

        self.basis = gate * &self.basis;
        self.completed_layers += 1;
        self.layers_since_qr += 1;
        if self.layers_since_qr == self.qr_every {
            self.reorthogonalize()?;
        }
        Ok(())
    }

    pub fn completed_layers(&self) -> usize {
        self.completed_layers
    }

    pub fn spectrum(&self) -> Result<Vec<f64>> {
        if self.completed_layers == 0 {
            bail!("Lyapunov spectrum requires at least one completed layer");
        }
        let mut finalized = self.clone();
        if finalized.layers_since_qr > 0 {
            finalized.reorthogonalize()?;
        }
        let scale = finalized.completed_layers as f64;
        let mut values = finalized
            .log_norms
            .into_iter()
            .map(|value| value / scale)
            .collect::<Vec<_>>();
        values.sort_by(|left, right| right.total_cmp(left));
        Ok(values)
    }

    fn reorthogonalize(&mut self) -> Result<()> {
        let decomposition = self.basis.clone().qr();
        let mut q = decomposition.q();
        let r = decomposition.r();
        for index in 0..self.dimension {
            let diagonal = r[(index, index)];
            let norm = diagonal.norm();
            if !norm.is_finite() || norm <= 0.0 {
                bail!("Lyapunov QR produced a singular diagonal");
            }
            self.log_norms[index] += norm.ln();
            let phase = diagonal / norm;
            for row in 0..self.dimension {
                q[(row, index)] *= phase;
            }
        }
        self.basis = q;
        self.layers_since_qr = 0;
        Ok(())
    }
}

pub fn temporal_gap(exponents: &[f64]) -> Result<f64> {
    if exponents.len() < 2 {
        bail!("temporal gap requires at least two exponents");
    }
    let gap = exponents[0] - exponents[1];
    if !gap.is_finite() || gap <= 0.0 {
        bail!("temporal gap is not positive");
    }
    Ok(gap)
}
