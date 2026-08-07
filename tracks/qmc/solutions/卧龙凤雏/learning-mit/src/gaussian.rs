//! Pure Gaussian Majorana states represented by real covariance matrices.

use anyhow::{bail, Result};
use nalgebra::DMatrix;
use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
pub struct MeasurementGate {
    pub a: usize,
    pub b: usize,
    pub observable_sign: i8,
    pub strength: f64,
}

#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
pub struct UpdateStats {
    pub probability: f64,
    pub surprise: f64,
    pub pre_measurement_parity: f64,
}

#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
pub struct InvariantErrors {
    pub antisymmetry: f64,
    pub purity: f64,
}

#[derive(Clone, Debug)]
pub struct MajoranaState {
    width: usize,
    matrix: DMatrix<f64>,
}

impl MajoranaState {
    pub fn paired_vacuum(width: usize) -> Result<Self> {
        if width == 0 {
            bail!("Gaussian width must be positive");
        }

        let mut matrix = DMatrix::zeros(2 * width, 2 * width);
        for site in 0..width {
            set_antisymmetric(&mut matrix, 2 * site, 2 * site + 1, 1.0);
        }
        Ok(Self { width, matrix })
    }

    pub fn from_matrix(width: usize, matrix: DMatrix<f64>) -> Result<Self> {
        if width == 0 || matrix.nrows() != 2 * width || matrix.ncols() != 2 * width {
            bail!("covariance matrix shape must be 2L by 2L");
        }
        if matrix.iter().any(|value| !value.is_finite()) {
            bail!("covariance matrix entries must be finite");
        }
        Ok(Self { width, matrix })
    }

    pub fn width(&self) -> usize {
        self.width
    }

    pub fn matrix(&self) -> &DMatrix<f64> {
        &self.matrix
    }

    pub fn parity_expectation(&self, gate: MeasurementGate) -> Result<f64> {
        self.validate_indices_and_sign(gate.a, gate.b, gate.observable_sign)?;
        Ok(gate.observable_sign as f64 * self.matrix[(gate.a, gate.b)])
    }

    pub fn outcome_probability(&self, gate: MeasurementGate, outcome: i8) -> Result<f64> {
        self.validate_measurement(gate, outcome)?;
        let parity = self.parity_expectation(gate)?;
        let raw = 0.5 * (1.0 + outcome as f64 * gate.strength.tanh() * parity);
        let tolerance = 64.0 * f64::EPSILON;
        if !raw.is_finite() || raw < -tolerance || raw > 1.0 + tolerance {
            bail!("Born probability is outside [0,1]: {raw}");
        }
        Ok(raw.clamp(0.0, 1.0))
    }

    pub fn apply_measurement(&mut self, gate: MeasurementGate, outcome: i8) -> Result<UpdateStats> {
        let probability = self.outcome_probability(gate, outcome)?;
        if probability <= 0.0 {
            bail!("cannot apply a zero-probability measurement outcome");
        }

        let old = self.matrix.clone();
        let t = gate.strength.tanh();
        let q = outcome as f64 * gate.observable_sign as f64 * t;
        let denominator = 1.0 + q * old[(gate.a, gate.b)];
        if !denominator.is_finite() || denominator <= 0.0 {
            bail!("Gaussian update has invalid denominator {denominator}");
        }

        let attenuation = (1.0 - t * t).max(0.0).sqrt();
        let dimension = old.nrows();
        let mut next = DMatrix::zeros(dimension, dimension);
        set_antisymmetric(
            &mut next,
            gate.a,
            gate.b,
            (old[(gate.a, gate.b)] + q) / denominator,
        );

        for j in 0..dimension {
            if j == gate.a || j == gate.b {
                continue;
            }
            set_antisymmetric(
                &mut next,
                gate.a,
                j,
                attenuation * old[(gate.a, j)] / denominator,
            );
            set_antisymmetric(
                &mut next,
                gate.b,
                j,
                attenuation * old[(gate.b, j)] / denominator,
            );
        }

        for i in 0..dimension {
            if i == gate.a || i == gate.b {
                continue;
            }
            for j in (i + 1)..dimension {
                if j == gate.a || j == gate.b {
                    continue;
                }
                let correction = q
                    * (old[(i, gate.a)] * old[(gate.b, j)] - old[(i, gate.b)] * old[(gate.a, j)])
                    / denominator;
                set_antisymmetric(&mut next, i, j, old[(i, j)] + correction);
            }
        }

        antisymmetrize(&mut next);
        self.matrix = next;
        Ok(UpdateStats {
            probability,
            surprise: -probability.ln(),
            pre_measurement_parity: gate.observable_sign as f64 * old[(gate.a, gate.b)],
        })
    }

    pub fn apply_rotation(&mut self, a: usize, b: usize, angle: f64) -> Result<()> {
        self.validate_indices(a, b)?;
        if !angle.is_finite() {
            bail!("rotation angle must be finite");
        }

        let dimension = self.matrix.nrows();
        let mut rotation = DMatrix::identity(dimension, dimension);
        rotation[(a, a)] = angle.cos();
        rotation[(a, b)] = -angle.sin();
        rotation[(b, a)] = angle.sin();
        rotation[(b, b)] = angle.cos();
        self.matrix = &rotation * &self.matrix * rotation.transpose();
        antisymmetrize(&mut self.matrix);
        Ok(())
    }

    pub fn interval_entropy(&self, first_site: usize, sites: usize) -> Result<f64> {
        if sites == 0 || first_site >= self.width || first_site + sites > self.width {
            bail!("entropy interval must be a non-empty subset of the chain");
        }

        let dimension = 2 * sites;
        let first = 2 * first_site;
        let restricted = self
            .matrix
            .view((first, first), (dimension, dimension))
            .into_owned();
        let singular_values = restricted.svd(false, false).singular_values;
        let mut entropy = 0.0;

        for pair in singular_values.as_slice().chunks_exact(2) {
            let nu = (0.5 * (pair[0] + pair[1])).clamp(0.0, 1.0);
            entropy += binary_mode_entropy(nu);
        }
        Ok(entropy)
    }

    pub fn connected_parity_correlation(&self, left: usize, right: usize) -> Result<f64> {
        if left >= self.width || right >= self.width {
            bail!("parity-correlation site is outside the chain");
        }
        if left == right {
            bail!("connected parity correlation requires distinct sites");
        }

        let a = 2 * left;
        let b = a + 1;
        let c = 2 * right;
        let d = c + 1;
        Ok(self.matrix[(a, d)] * self.matrix[(b, c)] - self.matrix[(a, c)] * self.matrix[(b, d)])
    }

    pub fn invariant_errors(&self) -> InvariantErrors {
        let antisymmetry = (&self.matrix + self.matrix.transpose()).amax();
        let mut purity_residual = &self.matrix * &self.matrix;
        for index in 0..purity_residual.nrows() {
            purity_residual[(index, index)] += 1.0;
        }
        InvariantErrors {
            antisymmetry,
            purity: purity_residual.amax(),
        }
    }

    pub(crate) fn recondition_pure(&mut self) -> Result<()> {
        let decomposition = self.matrix.clone().svd(true, true);
        let left = decomposition
            .u
            .ok_or_else(|| anyhow::anyhow!("pure-state reconditioning omitted the left vectors"))?;
        let right_transpose = decomposition.v_t.ok_or_else(|| {
            anyhow::anyhow!("pure-state reconditioning omitted the right vectors")
        })?;
        self.matrix = left * right_transpose;
        antisymmetrize(&mut self.matrix);
        Ok(())
    }

    fn validate_measurement(&self, gate: MeasurementGate, outcome: i8) -> Result<()> {
        self.validate_indices_and_sign(gate.a, gate.b, gate.observable_sign)?;
        if outcome != -1 && outcome != 1 {
            bail!("measurement outcome must be +1 or -1");
        }
        if !gate.strength.is_finite() || gate.strength < 0.0 {
            bail!("measurement strength must be finite and non-negative");
        }
        Ok(())
    }

    fn validate_indices_and_sign(&self, a: usize, b: usize, sign: i8) -> Result<()> {
        self.validate_indices(a, b)?;
        if sign != -1 && sign != 1 {
            bail!("observable sign must be +1 or -1");
        }
        Ok(())
    }

    fn validate_indices(&self, a: usize, b: usize) -> Result<()> {
        if a == b {
            bail!("Majorana indices must be distinct");
        }
        if a >= self.matrix.nrows() || b >= self.matrix.nrows() {
            bail!("Majorana index is outside the covariance matrix");
        }
        Ok(())
    }
}

fn binary_mode_entropy(nu: f64) -> f64 {
    let positive = 0.5 * (1.0 + nu);
    let negative = 0.5 * (1.0 - nu);
    let positive_term = if positive > 0.0 {
        -positive * positive.ln()
    } else {
        0.0
    };
    let negative_term = if negative > 0.0 {
        -negative * negative.ln()
    } else {
        0.0
    };
    positive_term + negative_term
}

fn set_antisymmetric(matrix: &mut DMatrix<f64>, a: usize, b: usize, value: f64) {
    matrix[(a, b)] = value;
    matrix[(b, a)] = -value;
}

fn antisymmetrize(matrix: &mut DMatrix<f64>) {
    *matrix = 0.5 * (&*matrix - matrix.transpose());
}
