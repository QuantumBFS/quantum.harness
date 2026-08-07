use crate::config::RunConfig;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const SCHEMA_VERSION: u32 = 1;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RunStatus {
    Running,
    XyReproducedDiiiCandidate,
    XyReproducedDiiiInconclusive,
    ValidationFailed,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TaskState {
    Pending,
    Running,
    Completed,
    Skipped,
    Failed,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TaskRecord {
    pub key: String,
    pub state: TaskState,
    pub elapsed_s: f64,
    pub reserve_reason: Option<String>,
    pub artifact: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SeedRecord {
    pub stage: usize,
    pub angle: usize,
    pub width: usize,
    pub stream: usize,
    pub purpose: u64,
    pub seed: u64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RunManifest {
    pub schema_version: u32,
    pub status: RunStatus,
    pub config: RunConfig,
    pub git_commit: String,
    pub started_at: String,
    pub updated_at: String,
    pub completed_at: Option<String>,
    pub elapsed_s: f64,
    pub tasks: Vec<TaskRecord>,
    pub seeds: Vec<SeedRecord>,
    pub artifact_sha256: BTreeMap<String, String>,
}
