use crate::config::RunConfig;
use serde::{Deserialize, Serialize};

pub const SCHEMA_VERSION: u32 = 1;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ExactRecord {
    pub schema_version: u32,
    pub l: usize,
    pub k: f64,
    pub boundary_conditions: String,
    pub lambda0: f64,
    pub g_exact: f64,
    pub iterations: usize,
    pub relative_change: f64,
    pub residual: f64,
    pub elapsed_s: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct McBlockRecord {
    pub schema_version: u32,
    pub l: usize,
    pub m: usize,
    pub k_index: usize,
    pub k: f64,
    pub replica: usize,
    pub seed: u64,
    pub thermal_sweeps: usize,
    pub measurement_sweeps: usize,
    pub block_index: usize,
    pub block_sweeps: usize,
    pub energy_sum: i64,
    pub energy_squared_sum: i64,
    pub measurement_count: usize,
    pub mean_cluster_size: f64,
    pub max_cluster_size: usize,
    pub cumulative_elapsed_s: f64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SeedRecord {
    pub l: usize,
    pub k_index: usize,
    pub replica: usize,
    pub seed: u64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RunManifest {
    pub schema_version: u32,
    pub config: RunConfig,
    pub config_path: String,
    pub exact_command: String,
    pub mc_command: String,
    pub rust_version: String,
    pub cargo_lock_sha256: String,
    pub python_version: Option<String>,
    pub python_requirements_sha256: Option<String>,
    pub started_at: String,
    pub completed_at: Option<String>,
    pub thread_count: usize,
    pub seeds: Vec<SeedRecord>,
    pub exact_elapsed_s: Option<f64>,
    pub mc_elapsed_s: Option<f64>,
    pub total_elapsed_s: Option<f64>,
}
