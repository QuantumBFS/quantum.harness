use serde::{Deserialize, Serialize};

use crate::OccamError;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AttemptStatus {
    Sat,
    Unsat,
    Timeout,
    ResourceLimit,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SynthesisStatus {
    Sat,
    NoCircuitWithinBound,
    Timeout,
    ResourceLimit,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct SynthesisAttempt {
    pub gate_bound: usize,
    pub status: AttemptStatus,
    pub variables: usize,
    pub clauses: usize,
    pub literals: usize,
    pub elapsed_ms: u64,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct VerificationEvidence {
    pub reparsed_netlist: bool,
    pub scalar_exact_matches: usize,
    pub scalar_correct_bits: usize,
    pub packed_exact_matches: usize,
    pub packed_correct_bits: usize,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct SynthesisCertificate {
    pub schema_version: u32,
    pub solver: String,
    pub encoding: String,
    pub status: SynthesisStatus,
    pub status_detail: String,
    pub problem_sha256: String,
    pub input_width: usize,
    pub output_width: usize,
    pub truth_table_rows: usize,
    pub maximum_gate_bound: usize,
    pub timeout_ms: u64,
    pub attempts: Vec<SynthesisAttempt>,
    pub minimal_gate_count: Option<usize>,
    pub netlist_sha256: Option<String>,
    pub netlist: Option<String>,
    pub verification: Option<VerificationEvidence>,
}

impl SynthesisCertificate {
    pub fn to_json_pretty(&self) -> Result<String, OccamError> {
        serde_json::to_string_pretty(self)
            .map(|json| format!("{json}\n"))
            .map_err(|error| {
                OccamError::Validation(format!(
                    "synthesis certificate JSON encoding failed: {error}"
                ))
            })
    }
}
