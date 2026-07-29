use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::fs;
use std::path::Path;

pub const CRITICAL_K: f64 = 0.440_686_793_509_771_47;
const PRODUCTION_WIDTHS: [usize; 6] = [4, 6, 8, 10, 12, 16];

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RunConfig {
    pub widths: Vec<usize>,
    pub aspect_ratio: usize,
    pub critical_k: f64,
    pub base_seed: u64,
    pub production_gates: bool,
    pub exact: ExactConfig,
    pub mc: McConfig,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ExactConfig {
    pub max_iterations: usize,
    pub eigenvalue_tolerance: f64,
    pub residual_tolerance: f64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct McConfig {
    pub replicas: usize,
    pub grid_intervals: usize,
    pub thermal_sweeps: usize,
    pub measurement_sweeps: usize,
    pub block_sweeps: usize,
}

impl RunConfig {
    pub fn load(path: &Path) -> Result<Self> {
        let text = fs::read_to_string(path)
            .with_context(|| format!("failed to read configuration {}", path.display()))?;
        toml::from_str(&text)
            .with_context(|| format!("failed to parse TOML configuration {}", path.display()))
    }

    pub fn validate(&self) -> Result<()> {
        if self.widths.is_empty() {
            bail!("widths must not be empty");
        }
        let mut seen = HashSet::new();
        for &l in &self.widths {
            if l < 2 || l % 2 != 0 {
                bail!("every width must be even and at least 2; found {l}");
            }
            if !seen.insert(l) {
                bail!("widths must be unique; duplicate {l}");
            }
        }
        if self.aspect_ratio == 0 {
            bail!("aspect_ratio must be positive");
        }
        if !self.critical_k.is_finite() || (self.critical_k - CRITICAL_K).abs() > 1.0e-15 {
            bail!("critical_k must equal {CRITICAL_K:.17}");
        }
        if self.exact.max_iterations == 0 {
            bail!("exact.max_iterations must be positive");
        }
        if !self.exact.eigenvalue_tolerance.is_finite()
            || self.exact.eigenvalue_tolerance <= 0.0
            || !self.exact.residual_tolerance.is_finite()
            || self.exact.residual_tolerance <= 0.0
        {
            bail!("exact tolerances must be finite and positive");
        }
        if self.mc.replicas == 0 {
            bail!("mc.replicas must be positive");
        }
        if self.mc.grid_intervals == 0 || self.mc.grid_intervals % 4 != 0 {
            bail!("mc.grid_intervals must be positive and divisible by four");
        }
        if self.mc.block_sweeps == 0
            || self.mc.measurement_sweeps == 0
            || self.mc.measurement_sweeps % self.mc.block_sweeps != 0
        {
            bail!("measurement_sweeps must contain complete nonempty blocks");
        }
        if self.production_gates {
            if self.widths != PRODUCTION_WIDTHS {
                bail!("production run requires widths {PRODUCTION_WIDTHS:?}");
            }
            if self.aspect_ratio != 8 {
                bail!("production run requires aspect_ratio = 8");
            }
            if self.mc.replicas != 4 {
                bail!("production run requires four replicas");
            }
            if self.mc.grid_intervals != 32
                || self.mc.thermal_sweeps != 200
                || self.mc.measurement_sweeps != 800
                || self.mc.block_sweeps != 20
            {
                bail!(
                    "production sampling requires 32 intervals, 200 thermal sweeps, \
                     800 measurement sweeps, and 20-sweep blocks"
                );
            }
        }
        Ok(())
    }
}

impl ExactConfig {
    pub fn strict_for_test() -> Self {
        Self {
            max_iterations: 10_000,
            eigenvalue_tolerance: 1.0e-13,
            residual_tolerance: 1.0e-11,
        }
    }
}
