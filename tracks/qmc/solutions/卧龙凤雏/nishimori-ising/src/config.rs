use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::fs;
use std::path::Path;

pub const ANTIFERROMAGNETIC_PROBABILITY: f64 = 0.109_221_2;
pub const NISHIMORI_K: f64 = 1.049_360_476_302_568_35;
pub const PRODUCTION_WIDTHS: [usize; 6] = [4, 6, 8, 10, 12, 14];

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RunConfig {
    pub widths: Vec<usize>,
    pub antiferromagnetic_probability: f64,
    pub nishimori_k: f64,
    pub base_seed: u64,
    pub production_gates: bool,
    pub disorder: DisorderConfig,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DisorderConfig {
    pub replicas: usize,
    pub burn_in_rows: usize,
    pub measurement_rows: usize,
    pub block_rows: usize,
    pub identity_delta_k: f64,
    pub identity_rows: usize,
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

        if !fixed_float(
            self.antiferromagnetic_probability,
            ANTIFERROMAGNETIC_PROBABILITY,
        ) {
            bail!(
                "antiferromagnetic_probability must equal \
                 {ANTIFERROMAGNETIC_PROBABILITY:.7}"
            );
        }
        if !fixed_float(self.nishimori_k, NISHIMORI_K) {
            bail!("nishimori_k must equal {NISHIMORI_K:.17}");
        }

        let disorder = &self.disorder;
        if disorder.replicas == 0 {
            bail!("disorder.replicas must be positive");
        }
        if disorder.measurement_rows == 0
            || disorder.block_rows == 0
            || disorder.measurement_rows % disorder.block_rows != 0
        {
            bail!("measurement_rows must contain complete nonempty blocks");
        }
        if disorder.identity_rows == 0 {
            bail!("disorder.identity_rows must be positive");
        }
        if !disorder.identity_delta_k.is_finite() || disorder.identity_delta_k <= 0.0 {
            bail!("disorder.identity_delta_k must be finite and positive");
        }

        if self.production_gates {
            if self.widths != PRODUCTION_WIDTHS {
                bail!("production run requires widths {PRODUCTION_WIDTHS:?}");
            }
            if disorder.replicas != 8
                || disorder.burn_in_rows != 4_096
                || disorder.measurement_rows != 1_048_576
                || disorder.block_rows != 16_384
            {
                bail!(
                    "production sampling requires 8 replicas, 4,096 burn-in rows, \
                     1,048,576 measurement rows, and 16,384-row blocks"
                );
            }
        }
        Ok(())
    }

    pub fn compatible_with(&self, other: &Self) -> bool {
        self.widths == other.widths
            && fixed_float(
                self.antiferromagnetic_probability,
                other.antiferromagnetic_probability,
            )
            && fixed_float(self.nishimori_k, other.nishimori_k)
            && self.base_seed == other.base_seed
            && self.production_gates == other.production_gates
            && self.disorder.replicas == other.disorder.replicas
            && self.disorder.burn_in_rows == other.disorder.burn_in_rows
            && self.disorder.measurement_rows == other.disorder.measurement_rows
            && self.disorder.block_rows == other.disorder.block_rows
            && fixed_float(
                self.disorder.identity_delta_k,
                other.disorder.identity_delta_k,
            )
            && self.disorder.identity_rows == other.disorder.identity_rows
    }
}

fn fixed_float(value: f64, expected: f64) -> bool {
    if !value.is_finite() || !expected.is_finite() {
        return false;
    }
    let scale = value.abs().max(expected.abs()).max(f64::MIN_POSITIVE);
    (value - expected).abs() <= 16.0 * f64::EPSILON * scale
}
