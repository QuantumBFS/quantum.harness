use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::fs;
use std::path::Path;

pub const SELF_DUAL_THETA: f64 = std::f64::consts::FRAC_PI_4;
pub const SELF_DUAL_BETA: f64 = 0.881_373_587_019_543;
pub const TARGET_CENTRAL_CHARGE: f64 = 0.447;
pub const PRODUCTION_WIDTHS: [usize; 13] = [6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30];

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RunConfig {
    pub widths: Vec<usize>,
    pub theta: f64,
    pub beta: f64,
    pub base_seed: u64,
    pub production_gates: bool,
    #[serde(default)]
    pub refinement_level: usize,
    pub sampling: SamplingConfig,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SamplingConfig {
    pub streams_per_width: usize,
    pub burn_in_layers_per_width: usize,
    pub measurement_layers_per_width: usize,
    pub block_layers_per_width: usize,
    pub stabilize_every_layers: usize,
    pub invariant_tolerance: f64,
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
        for &width in &self.widths {
            if width < 2 || width % 2 != 0 {
                bail!("every width must be even and at least 2; found {width}");
            }
            if !seen.insert(width) {
                bail!("widths must be unique; duplicate {width}");
            }
        }
        if self.widths.windows(2).any(|pair| pair[0] >= pair[1]) {
            bail!("widths must be strictly increasing");
        }
        if !fixed_float(self.theta, SELF_DUAL_THETA) {
            bail!("theta must equal pi/4");
        }
        if !fixed_float(self.beta, SELF_DUAL_BETA) {
            bail!("beta must equal ln(1+sqrt(2))");
        }

        let sampling = &self.sampling;
        if sampling.streams_per_width == 0 {
            bail!("sampling.streams_per_width must be positive");
        }
        if sampling.measurement_layers_per_width == 0
            || sampling.block_layers_per_width == 0
            || sampling.measurement_layers_per_width % sampling.block_layers_per_width != 0
        {
            bail!("measurement layers must contain complete blocks");
        }
        if sampling.burn_in_layers_per_width >= sampling.measurement_layers_per_width {
            bail!("burn-in multiplier must be smaller than measurement multiplier");
        }
        if sampling.stabilize_every_layers == 0 {
            bail!("sampling.stabilize_every_layers must be positive");
        }
        if !sampling.invariant_tolerance.is_finite() || sampling.invariant_tolerance <= 0.0 {
            bail!("sampling.invariant_tolerance must be finite and positive");
        }

        if self.production_gates {
            self.validate_production_contract()?;
        }
        Ok(())
    }

    fn validate_production_contract(&self) -> Result<()> {
        let sampling = &self.sampling;
        match self.refinement_level {
            0 => {
                if self.widths != PRODUCTION_WIDTHS
                    || sampling.streams_per_width != 8
                    || sampling.burn_in_layers_per_width != 20
                    || sampling.measurement_layers_per_width != 100
                    || sampling.block_layers_per_width != 5
                {
                    bail!("production refinement level 0 does not match the frozen contract");
                }
            }
            1 => {
                let mut expected = PRODUCTION_WIDTHS.to_vec();
                expected.push(32);
                if self.widths != expected
                    || sampling.streams_per_width != 16
                    || sampling.burn_in_layers_per_width != 20
                    || sampling.measurement_layers_per_width != 200
                    || sampling.block_layers_per_width != 5
                {
                    bail!("production refinement level 1 does not match the frozen contract");
                }
            }
            level => bail!("unsupported production refinement level {level}"),
        }
        if sampling.stabilize_every_layers != 4
            || !fixed_float(sampling.invariant_tolerance, 1.0e-9)
        {
            bail!("production stabilization contract does not match");
        }
        Ok(())
    }

    pub fn compatible_with(&self, other: &Self) -> bool {
        self == other
    }
}

fn fixed_float(value: f64, expected: f64) -> bool {
    value.is_finite()
        && expected.is_finite()
        && (value - expected).abs()
            <= 16.0 * f64::EPSILON * value.abs().max(expected.abs()).max(1.0)
}
