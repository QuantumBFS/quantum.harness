use std::{collections::HashSet, fs, path::Path};

use serde::{Deserialize, Serialize};

use crate::{OccamError, VerificationMetrics};

use super::{ResearchMethod, TrialKey, TrialRecord, TrialStatus};

pub const SEMANTIC_PROJECTION_EXCLUDED_FIELDS: [&str; 5] = [
    "runtime_micros",
    "peak_rss_bytes",
    "host_identifier",
    "process_id",
    "started_unix_micros",
];

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticTrialRecord {
    pub schema_version: u32,
    pub measured_schema_version: u32,
    pub key: TrialKey,
    pub config_sha256: String,
    pub status: TrialStatus,
    pub observed_rows: usize,
    pub held_out_rows: usize,
    pub training: Option<VerificationMetrics>,
    pub held_out: Option<VerificationMetrics>,
    pub full_domain: Option<VerificationMetrics>,
    pub semantic_recovery: bool,
    pub expression: Option<String>,
    pub description_length: Option<usize>,
    pub gate_count: Option<usize>,
    pub minimum_unique: Option<bool>,
    pub hypothesis_sha256: Option<String>,
    pub detail: String,
}

impl SemanticTrialRecord {
    pub fn method(&self) -> ResearchMethod {
        self.key.method
    }
}

pub fn semantic_projection(record: &TrialRecord) -> SemanticTrialRecord {
    SemanticTrialRecord {
        schema_version: 2,
        measured_schema_version: record.schema_version,
        key: record.key.clone(),
        config_sha256: record.config_sha256.clone(),
        status: record.status,
        observed_rows: record.observed_rows,
        held_out_rows: record.held_out_rows,
        training: record.training.clone(),
        held_out: record.held_out.clone(),
        full_domain: record.full_domain.clone(),
        semantic_recovery: record.semantic_recovery,
        expression: record.expression.clone(),
        description_length: record.description_length,
        gate_count: record.gate_count,
        minimum_unique: record.minimum_unique,
        hypothesis_sha256: record.hypothesis_sha256.clone(),
        detail: record.detail.clone(),
    }
}

pub fn render_semantic_jsonl(records: &[TrialRecord]) -> Result<String, OccamError> {
    let mut projected = records.iter().map(semantic_projection).collect::<Vec<_>>();
    projected.sort_by(|lhs, rhs| lhs.key.cmp(&rhs.key));
    let unique = projected
        .iter()
        .map(|record| &record.key)
        .collect::<HashSet<_>>();
    if unique.len() != projected.len() {
        return Err(OccamError::Validation(
            "semantic projection contains duplicate trial keys".into(),
        ));
    }
    let mut output = String::new();
    for record in projected {
        output.push_str(&serde_json::to_string(&record).map_err(|error| {
            OccamError::Validation(format!("semantic JSON encoding failed: {error}"))
        })?);
        output.push('\n');
    }
    Ok(output)
}

pub fn write_semantic_jsonl(path: &Path, records: &[TrialRecord]) -> Result<(), OccamError> {
    let output = render_semantic_jsonl(records)?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|source| OccamError::WriteFile {
            path: parent.to_owned(),
            source,
        })?;
    }
    let temporary = path.with_extension(format!("{}.tmp", std::process::id()));
    fs::write(&temporary, output).map_err(|source| OccamError::WriteFile {
        path: temporary.clone(),
        source,
    })?;
    fs::rename(&temporary, path).map_err(|source| OccamError::WriteFile {
        path: path.to_owned(),
        source,
    })
}
