use crate::config::RunConfig;
use crate::oracles::{CleanOracle, GaugeOracleComparison, OracleComparison};
use crate::sampler::StreamEstimate;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const SCHEMA_VERSION: u32 = 3;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StreamArtifact {
    pub schema_version: u32,
    pub config: RunConfig,
    pub estimate: StreamEstimate,
    pub elapsed_s: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct OracleArtifact {
    pub schema_version: u32,
    pub config: RunConfig,
    pub born_enumeration: OracleComparison,
    pub gauge_equivalence: GaugeOracleComparison,
    pub clean_positive: CleanOracle,
    pub elapsed_s: f64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SeedRecord {
    pub width: usize,
    pub stream: usize,
    pub purpose: u64,
    pub seed: u64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RunManifest {
    pub schema_version: u32,
    pub config: RunConfig,
    pub config_path: String,
    pub commands: Vec<String>,
    pub rust_version: String,
    pub cargo_lock_sha256: String,
    pub python_version: Option<String>,
    pub python_requirements_sha256: Option<String>,
    pub started_at: String,
    pub updated_at: String,
    pub completed_at: Option<String>,
    pub thread_count: usize,
    pub seeds: Vec<SeedRecord>,
    pub completed_streams: Vec<String>,
    pub artifact_sha256: BTreeMap<String, String>,
    pub oracle_elapsed_s: Option<f64>,
    pub simulation_elapsed_s: Option<f64>,
    pub analysis_elapsed_s: Option<f64>,
    pub total_elapsed_s: Option<f64>,
}
