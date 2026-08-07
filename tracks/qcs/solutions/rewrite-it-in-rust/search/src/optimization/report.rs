use serde::{Deserialize, Serialize};

use crate::{Circuit, OccamError};

use super::WindowConfig;

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct PeepholeBoundReport {
    pub gate_bound: usize,
    pub status: String,
    pub variables: usize,
    pub clauses: usize,
    pub literals: usize,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct PeepholeAttemptReport {
    pub window_identity_sha256: String,
    pub original_window_gates: usize,
    pub boundary_inputs: usize,
    pub boundary_outputs: usize,
    pub status: String,
    pub candidate_window_gates: Option<usize>,
    pub candidate_whole_gates: Option<usize>,
    pub whole_circuit_mismatches: Option<usize>,
    pub accepted: bool,
    pub bounds: Vec<PeepholeBoundReport>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct PeepholeOptimizationReport {
    pub schema_version: u32,
    pub window_config: WindowConfig,
    pub baseline_gate_count: usize,
    pub final_gate_count: usize,
    pub attempted_windows: usize,
    pub accepted_replacements: usize,
    pub termination: String,
    pub whole_circuit_cases: usize,
    pub whole_circuit_mismatches: usize,
    pub final_circuit_sha256: String,
    pub attempts: Vec<PeepholeAttemptReport>,
}

impl PeepholeOptimizationReport {
    pub fn to_json_pretty(&self) -> Result<String, OccamError> {
        serde_json::to_string_pretty(self)
            .map(|encoded| format!("{encoded}\n"))
            .map_err(|error| OccamError::Validation(format!("JSON encoding failed: {error}")))
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PeepholeOptimizationResult {
    pub circuit: Circuit,
    pub netlist: String,
    pub report: PeepholeOptimizationReport,
}
