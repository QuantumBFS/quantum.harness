//! Conversion from monitored-circuit angles to complex Ising couplings.

use std::f64::consts::PI;

use anyhow::{bail, Result};
use num_complex::Complex64;

/// Real and dual couplings associated with one pair of measurement angles.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct GateCouplings {
    pub theta: f64,
    pub phi: f64,
    pub j: f64,
    pub j_dual: f64,
    pub phi_dual: f64,
}

impl GateCouplings {
    /// Convert angles expressed in units of pi into direct and dual couplings.
    pub fn from_pi_units(theta_pi: f64, phi_pi: f64) -> Result<Self> {
        if !theta_pi.is_finite() || !phi_pi.is_finite() {
            bail!("measurement angles must be finite");
        }

        let theta = PI * theta_pi;
        let phi = PI * phi_pi;
        let cosine = theta.cos().clamp(-1.0, 1.0);
        if cosine.abs() == 1.0 {
            bail!("singular X endpoint is not a finite production coupling");
        }

        let j = cosine.atanh();
        let dual = kw_dual(Complex64::new(j, phi))?;
        Ok(Self {
            theta,
            phi,
            j,
            j_dual: dual.re,
            phi_dual: normalize_log_branch(dual.im),
        })
    }
}

/// Apply `exp(-z_dual) = tanh(z / 2)` on the principal logarithm branch.
pub fn kw_dual(z: Complex64) -> Result<Complex64> {
    if !z.re.is_finite() || !z.im.is_finite() {
        bail!("complex Kramers-Wannier input is non-finite");
    }

    let value = -(z * 0.5).tanh().ln();
    if !value.re.is_finite() || !value.im.is_finite() {
        bail!("complex Kramers-Wannier map is non-finite");
    }
    Ok(Complex64::new(value.re, normalize_log_branch(value.im)))
}

fn normalize_log_branch(angle: f64) -> f64 {
    let normalized = (angle + PI).rem_euclid(2.0 * PI) - PI;
    if normalized == -PI && angle > 0.0 {
        PI
    } else {
        normalized
    }
}
