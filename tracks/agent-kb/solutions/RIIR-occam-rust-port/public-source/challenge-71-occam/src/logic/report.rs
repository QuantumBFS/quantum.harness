use std::{path::PathBuf, time::Duration};

use serde::{Deserialize, Serialize};

use crate::{OccamError, sha256_hex};

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ExternalCommandLimits {
    pub timeout: Duration,
    pub max_stdout_bytes: usize,
    pub max_stderr_bytes: usize,
}

impl Default for ExternalCommandLimits {
    fn default() -> Self {
        Self {
            timeout: Duration::from_secs(60),
            max_stdout_bytes: 4 * 1024 * 1024,
            max_stderr_bytes: 4 * 1024 * 1024,
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct AbcOptimizationConfig {
    pub genlib_path: PathBuf,
    pub flow_names: Vec<String>,
    pub command_limits: ExternalCommandLimits,
    pub max_exhaustive_inputs: usize,
}

impl Default for AbcOptimizationConfig {
    fn default() -> Self {
        Self {
            genlib_path: PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .parent()
                .unwrap()
                .join("tools/abc/occam.genlib"),
            flow_names: super::abc::FLOW_NAMES
                .iter()
                .map(|name| (*name).to_owned())
                .collect(),
            command_limits: ExternalCommandLimits::default(),
            max_exhaustive_inputs: 20,
        }
    }
}

impl AbcOptimizationConfig {
    pub fn for_tests() -> Self {
        Self {
            flow_names: vec!["resyn".into()],
            command_limits: ExternalCommandLimits {
                timeout: Duration::from_secs(20),
                max_stdout_bytes: 1024 * 1024,
                max_stderr_bytes: 1024 * 1024,
            },
            ..Self::default()
        }
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct AbcFlowReport {
    pub name: String,
    pub accepted: bool,
    pub status: String,
    pub abc_cec_equivalent: bool,
    pub rust_exhaustive_cases: Option<usize>,
    pub rust_exhaustive_mismatches: Option<usize>,
    pub official_gate_count: Option<usize>,
    pub circuit_sha256: Option<String>,
    pub stdout_sha256: String,
    pub stderr_sha256: String,
    pub diagnostic_tail: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct AbcPortfolioReport {
    pub schema_version: u32,
    pub baseline_gate_count: usize,
    pub accepted_candidates: usize,
    pub selected_flow: Option<String>,
    pub selected_gate_count: Option<usize>,
    pub selected_circuit_sha256: Option<String>,
    pub flows: Vec<AbcFlowReport>,
}

impl AbcPortfolioReport {
    pub fn to_json_pretty(&self) -> Result<String, OccamError> {
        serde_json::to_string_pretty(self)
            .map(|encoded| format!("{encoded}\n"))
            .map_err(|error| OccamError::Validation(format!("JSON encoding failed: {error}")))
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct AbcCandidate {
    pub flow_name: String,
    pub netlist: String,
    pub official_gate_count: usize,
    pub circuit_sha256: String,
    pub rust_exhaustive_cases: usize,
    pub rust_exhaustive_mismatches: usize,
}

impl AbcCandidate {
    pub(super) fn new(
        flow_name: String,
        netlist: String,
        official_gate_count: usize,
        rust_exhaustive_cases: usize,
        rust_exhaustive_mismatches: usize,
    ) -> Self {
        let circuit_sha256 = sha256_hex(netlist.as_bytes());
        Self {
            flow_name,
            netlist,
            official_gate_count,
            circuit_sha256,
            rust_exhaustive_cases,
            rust_exhaustive_mismatches,
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct AbcOptimizationResult {
    pub report: AbcPortfolioReport,
    pub candidates: Vec<AbcCandidate>,
}

impl AbcOptimizationResult {
    pub fn best_candidate(&self) -> Option<&AbcCandidate> {
        self.candidates.first()
    }
}
