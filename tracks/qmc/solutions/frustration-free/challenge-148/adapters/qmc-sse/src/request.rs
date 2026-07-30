use crate::secure_fs::{duplicate_inherited_file, open_absolute_file, read_regular_file};
use anyhow::{Context, Result, bail, ensure};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub schema_version: String,
    pub adapter: String,
    pub graph_path: PathBuf,
    pub graph_sha256: String,
    pub beta: f64,
    pub coupling: f64,
    pub field: f64,
    pub seed: u64,
    pub thermalization_sweeps: u64,
    pub retained_samples: u64,
    pub thinning: u64,
    pub serial_measurement_stride_samples: u64,
    pub bin_length: u64,
    pub checkpoint_bins: u64,
    pub expected_source_hash: String,
    pub expected_build_hash: String,
}

pub fn is_sha256(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

pub fn canonical_bytes<T: Serialize>(value: &T) -> Result<Vec<u8>> {
    let value = serde_json::to_value(value).context("canonical JSON conversion failed")?;
    serde_json::to_vec(&value).context("canonical JSON serialization failed")
}

pub fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

impl Request {
    pub fn load(path: &Path) -> Result<Self> {
        let descriptor = open_absolute_file(path)
            .with_context(|| format!("cannot securely open request {}", path.display()))?;
        Self::load_file(descriptor)
    }

    pub fn load_inherited_fd(descriptor: i32) -> Result<Self> {
        let descriptor = duplicate_inherited_file(descriptor, "request")?;
        Self::load_file(descriptor)
    }

    fn load_file(descriptor: std::fs::File) -> Result<Self> {
        let bytes = read_regular_file(descriptor, "request")?;
        let request: Self = serde_json::from_slice(&bytes).context("invalid request JSON")?;
        request.validate()?;
        Ok(request)
    }

    fn validate(&self) -> Result<()> {
        ensure!(
            self.schema_version == "qmc-request-v1",
            "unsupported request schema"
        );
        ensure!(
            self.adapter == "QMC_SSE",
            "adapter mismatch: expected QMC_SSE"
        );
        ensure!(
            self.beta.is_finite() && self.beta > 0.0,
            "beta must be finite and positive"
        );
        ensure!(
            self.coupling.is_finite() && self.coupling >= 0.0,
            "coupling must be finite and nonnegative"
        );
        ensure!(
            self.field.is_finite() && self.field > 0.0,
            "field must be finite and positive"
        );
        ensure!(
            self.retained_samples > 0,
            "retained_samples must be positive"
        );
        ensure!(self.bin_length > 0, "bin_length must be positive");
        ensure!(self.thinning > 0, "thinning must be positive");
        ensure!(
            self.serial_measurement_stride_samples == 1,
            "serial_measurement_stride_samples must be one"
        );
        ensure!(self.checkpoint_bins > 0, "checkpoint_bins must be positive");
        ensure!(
            self.retained_samples.is_multiple_of(self.bin_length),
            "retained_samples must be divisible by bin_length"
        );
        for (name, hash) in [
            ("graph_sha256", &self.graph_sha256),
            ("expected_source_hash", &self.expected_source_hash),
            ("expected_build_hash", &self.expected_build_hash),
        ] {
            if !is_sha256(hash) {
                bail!("{name} must be a lowercase SHA256");
            }
        }
        ensure!(
            self.expected_source_hash == env!("QMC_SSE_SOURCE_HASH"),
            "stale source hash"
        );
        ensure!(
            self.expected_build_hash == env!("QMC_SSE_BUILD_HASH"),
            "stale build hash"
        );
        Ok(())
    }

    pub fn hash(&self) -> Result<String> {
        Ok(sha256(&canonical_bytes(self)?))
    }

    pub fn total_bins(&self) -> u64 {
        self.retained_samples / self.bin_length
    }

    pub fn updates_through_bin(&self, completed_bins: u64) -> Result<u64> {
        let retained_updates = completed_bins
            .checked_mul(self.bin_length)
            .and_then(|value| value.checked_mul(self.thinning))
            .context("replay update count overflow")?;
        self.thermalization_sweeps
            .checked_add(retained_updates)
            .context("replay update count overflow")
    }
}
