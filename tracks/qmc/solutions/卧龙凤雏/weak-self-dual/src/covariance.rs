use anyhow::{bail, Result};
use nalgebra::DMatrix;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Measurement {
    pub a: usize,
    pub b: usize,
    pub observable_sign: i8,
    pub beta: f64,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct UpdateStats {
    pub probability: f64,
    pub surprise: f64,
    pub pre_measurement_parity: f64,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct InvariantErrors {
    pub antisymmetry: f64,
    pub purity: f64,
}

#[derive(Debug, Clone)]
pub struct CovarianceState {
    width: usize,
    matrix: DMatrix<f64>,
}

impl CovarianceState {
    pub fn paired_vacuum(width: usize) -> Result<Self> {
        if width == 0 {
            bail!("Gaussian width must be positive");
        }
        let dimension = 2 * width;
        let mut matrix = DMatrix::zeros(dimension, dimension);
        for site in 0..width {
            set_antisymmetric(&mut matrix, 2 * site, 2 * site + 1, 1.0);
        }
        Ok(Self { width, matrix })
    }

    pub fn width(&self) -> usize {
        self.width
    }

    pub fn matrix(&self) -> &DMatrix<f64> {
        &self.matrix
    }

    pub fn parity_expectation(&self, a: usize, b: usize, observable_sign: i8) -> Result<f64> {
        self.validate_indices_and_sign(a, b, observable_sign)?;
        Ok(observable_sign as f64 * self.matrix[(a, b)])
    }

    pub fn outcome_probability(&self, measurement: Measurement, outcome: i8) -> Result<f64> {
        self.validate_measurement(measurement, outcome)?;
        let parity =
            self.parity_expectation(measurement.a, measurement.b, measurement.observable_sign)?;
        let raw = 0.5 * (1.0 + outcome as f64 * measurement.beta.tanh() * parity);
        let tolerance = 64.0 * f64::EPSILON;
        if !raw.is_finite() || raw < -tolerance || raw > 1.0 + tolerance {
            bail!("Born probability is outside [0,1]: {raw}");
        }
        Ok(raw.clamp(0.0, 1.0))
    }

    pub fn apply_outcome(&mut self, measurement: Measurement, outcome: i8) -> Result<UpdateStats> {
        let probability = self.outcome_probability(measurement, outcome)?;
        if probability <= 0.0 {
            bail!("cannot apply a zero-probability measurement outcome");
        }

        let old = self.matrix.clone();
        let a = measurement.a;
        let b = measurement.b;
        let t = measurement.beta.tanh();
        let q = outcome as f64 * measurement.observable_sign as f64 * t;
        let denominator = 1.0 + q * old[(a, b)];
        if !denominator.is_finite() || denominator <= 0.0 {
            bail!("Gaussian update has invalid denominator {denominator}");
        }
        let attenuation = (1.0 - t * t).max(0.0).sqrt();
        let dimension = old.nrows();
        let mut next = DMatrix::zeros(dimension, dimension);

        set_antisymmetric(&mut next, a, b, (old[(a, b)] + q) / denominator);
        for j in 0..dimension {
            if j == a || j == b {
                continue;
            }
            set_antisymmetric(&mut next, a, j, attenuation * old[(a, j)] / denominator);
            set_antisymmetric(&mut next, b, j, attenuation * old[(b, j)] / denominator);
        }
        for i in 0..dimension {
            if i == a || i == b {
                continue;
            }
            for j in (i + 1)..dimension {
                if j == a || j == b {
                    continue;
                }
                let correction =
                    q * (old[(i, a)] * old[(b, j)] - old[(i, b)] * old[(a, j)]) / denominator;
                set_antisymmetric(&mut next, i, j, old[(i, j)] + correction);
            }
        }
        self.matrix = next;
        Ok(UpdateStats {
            probability,
            surprise: -probability.ln(),
            pre_measurement_parity: measurement.observable_sign as f64 * old[(a, b)],
        })
    }

    pub fn invariant_errors(&self) -> InvariantErrors {
        let dimension = self.matrix.nrows();
        let antisymmetry = (&self.matrix + self.matrix.transpose())
            .iter()
            .fold(0.0_f64, |largest, value| largest.max(value.abs()));
        let mut purity_matrix = &self.matrix * &self.matrix;
        for index in 0..dimension {
            purity_matrix[(index, index)] += 1.0;
        }
        let purity = purity_matrix
            .iter()
            .fold(0.0_f64, |largest, value| largest.max(value.abs()));
        InvariantErrors {
            antisymmetry,
            purity,
        }
    }

    pub fn stabilize(&mut self) -> Result<()> {
        antisymmetrize(&mut self.matrix);
        for _ in 0..4 {
            let inverse =
                self.matrix.clone().try_inverse().ok_or_else(|| {
                    anyhow::anyhow!("covariance stabilization matrix is singular")
                })?;
            self.matrix = 0.5 * (&self.matrix + inverse.transpose());
        }
        antisymmetrize(&mut self.matrix);
        Ok(())
    }

    fn validate_measurement(&self, measurement: Measurement, outcome: i8) -> Result<()> {
        self.validate_indices_and_sign(measurement.a, measurement.b, measurement.observable_sign)?;
        if outcome != -1 && outcome != 1 {
            bail!("measurement outcome must be +1 or -1");
        }
        if !measurement.beta.is_finite() || measurement.beta < 0.0 {
            bail!("measurement beta must be finite and non-negative");
        }
        Ok(())
    }

    fn validate_indices_and_sign(&self, a: usize, b: usize, sign: i8) -> Result<()> {
        if a == b {
            bail!("Majorana measurement indices must be distinct");
        }
        if a >= self.matrix.nrows() || b >= self.matrix.nrows() {
            bail!("Majorana measurement index is outside the covariance matrix");
        }
        if sign != -1 && sign != 1 {
            bail!("observable sign must be +1 or -1");
        }
        Ok(())
    }
}

fn set_antisymmetric(matrix: &mut DMatrix<f64>, a: usize, b: usize, value: f64) {
    matrix[(a, b)] = value;
    matrix[(b, a)] = -value;
}

fn antisymmetrize(matrix: &mut DMatrix<f64>) {
    *matrix = 0.5 * (&*matrix - matrix.transpose());
}
