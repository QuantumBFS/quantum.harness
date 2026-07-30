use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::fs;
use std::path::Path;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RunConfig {
    pub base_seed: u64,
    pub production_gates: bool,
    pub invariant_tolerance: f64,
    pub runtime: RuntimeBudget,
    pub stages: Vec<StageConfig>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RuntimeBudget {
    pub target_seconds: u64,
    pub ordinary_stop_seconds: u64,
    pub hard_stop_seconds: u64,
    pub finalize_reserve_seconds: u64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StageConfig {
    pub name: String,
    pub theta_pi: f64,
    pub phi_pi: Vec<f64>,
    pub widths: Vec<usize>,
    pub streams: usize,
    pub burn_in_layers_per_width: usize,
    pub measurement_layers_per_width: usize,
    pub block_layers_per_width: usize,
}

impl RunConfig {
    pub fn load(path: &Path) -> Result<Self> {
        let text = fs::read_to_string(path)
            .with_context(|| format!("failed to read configuration {}", path.display()))?;
        let config: Self = toml::from_str(&text)
            .with_context(|| format!("failed to parse TOML configuration {}", path.display()))?;
        config.validate()?;
        Ok(config)
    }

    pub fn validate(&self) -> Result<()> {
        if !self.invariant_tolerance.is_finite() || self.invariant_tolerance <= 0.0 {
            bail!("invariant_tolerance must be finite and positive");
        }
        self.runtime.validate(self.production_gates)?;
        if self.stages.is_empty() {
            bail!("at least one simulation stage is required");
        }
        let mut names = HashSet::new();
        for stage in &self.stages {
            stage.validate()?;
            if !names.insert(stage.name.as_str()) {
                bail!("stage names must be unique; duplicate {}", stage.name);
            }
        }
        Ok(())
    }

    pub fn compatible_with(&self, other: &Self) -> bool {
        self == other
    }
}

impl RuntimeBudget {
    fn validate(&self, production_gates: bool) -> Result<()> {
        if self.target_seconds == 0
            || self.ordinary_stop_seconds == 0
            || self.hard_stop_seconds == 0
            || self.finalize_reserve_seconds == 0
        {
            bail!("runtime budget values must be positive");
        }
        if self.ordinary_stop_seconds >= self.hard_stop_seconds {
            bail!("ordinary stop must precede the hard stop");
        }
        if self.target_seconds > self.hard_stop_seconds + self.finalize_reserve_seconds {
            bail!("target runtime exceeds the total runtime limit");
        }
        if production_gates
            && (self.target_seconds != 3600
                || self.ordinary_stop_seconds != 3300
                || self.hard_stop_seconds != 5100
                || self.finalize_reserve_seconds != 300)
        {
            bail!("production runtime must equal the 3600/3300/5100/300 contract");
        }
        Ok(())
    }
}

impl StageConfig {
    fn validate(&self) -> Result<()> {
        if self.name.trim().is_empty() {
            bail!("stage name must not be empty");
        }
        if !self.theta_pi.is_finite() || !(0.0..=0.5).contains(&self.theta_pi) {
            bail!("theta_pi must lie in the first-octant interval [0, 0.5]");
        }
        if self.phi_pi.is_empty()
            || self
                .phi_pi
                .iter()
                .any(|value| !value.is_finite() || !(0.0..=0.5).contains(value))
        {
            bail!("phi_pi values must be finite and lie in [0, 0.5]");
        }
        if self.phi_pi.windows(2).any(|pair| pair[0] >= pair[1]) {
            bail!("phi_pi values must be strictly increasing");
        }
        if self.widths.is_empty() {
            bail!("stage widths must not be empty");
        }
        if self
            .widths
            .iter()
            .any(|width| *width < 2 || *width % 2 != 0)
        {
            bail!("every width must be even and at least 2");
        }
        if self.widths.windows(2).any(|pair| pair[0] >= pair[1]) {
            bail!("stage widths must be strictly increasing");
        }
        if self.streams == 0 {
            bail!("stage streams must be positive");
        }
        if self.measurement_layers_per_width == 0
            || self.block_layers_per_width == 0
            || self.measurement_layers_per_width % self.block_layers_per_width != 0
        {
            bail!("measurement layers must contain complete blocks");
        }
        if self.burn_in_layers_per_width >= self.measurement_layers_per_width {
            bail!("burn-in multiplier must be smaller than measurement multiplier");
        }
        Ok(())
    }
}
