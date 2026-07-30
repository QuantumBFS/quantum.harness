use std::{collections::HashSet, path::Path};

use serde::{Deserialize, Serialize};

use crate::{OccamError, VerificationMetrics};

#[derive(Clone, Copy, Debug, Deserialize, Eq, Hash, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum ResearchMethod {
    LegacyRegistry,
    MdlEnumerator,
    AbcDontCare,
    Robdd,
    SatCegis,
    GrammarEvolution,
    Memorization,
    OracleExpression,
}

impl ResearchMethod {
    pub const AUTOMATIC: [Self; 7] = [
        Self::LegacyRegistry,
        Self::MdlEnumerator,
        Self::AbcDontCare,
        Self::Robdd,
        Self::SatCegis,
        Self::GrammarEvolution,
        Self::Memorization,
    ];
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ExperimentConfig {
    pub schema_version: u32,
    pub fractions: Vec<f64>,
    pub seeds: Vec<u64>,
    pub methods: Vec<ResearchMethod>,
    pub trial_timeout_millis: u64,
    pub experiment_seed: u64,
}

#[derive(Clone, Debug, Deserialize, Eq, Hash, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(deny_unknown_fields)]
pub struct TrialKey {
    pub task: String,
    pub fraction_basis_points: u32,
    pub seed: u64,
    pub method: ResearchMethod,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum TrialStatus {
    Success,
    NoHypothesis,
    Unsupported,
    Timeout,
    ResourceLimit,
    Error,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct TrialRecord {
    pub schema_version: u32,
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
    pub runtime_micros: u64,
    pub peak_rss_bytes: u64,
    #[serde(default)]
    pub host_identifier: String,
    #[serde(default)]
    pub process_id: u32,
    #[serde(default)]
    pub started_unix_micros: u64,
    pub hypothesis_sha256: Option<String>,
    pub detail: String,
}

pub fn load_experiment_config(path: &Path) -> Result<ExperimentConfig, OccamError> {
    let source = std::fs::read_to_string(path).map_err(|source| OccamError::ReadFile {
        path: path.to_owned(),
        source,
    })?;
    let config: ExperimentConfig = serde_json::from_str(&source)
        .map_err(|error| OccamError::Validation(format!("invalid experiment config: {error}")))?;
    validate_config(&config)?;
    Ok(config)
}

pub fn expected_trial_keys(
    task_ids: &[String],
    config: &ExperimentConfig,
) -> Result<Vec<TrialKey>, OccamError> {
    validate_config(config)?;
    let mut keys = Vec::new();
    for task in task_ids {
        for fraction in &config.fractions {
            let fraction_basis_points = (fraction * 100_000.0).round() as u32;
            for seed in &config.seeds {
                for method in &config.methods {
                    keys.push(TrialKey {
                        task: task.clone(),
                        fraction_basis_points,
                        seed: *seed,
                        method: *method,
                    });
                }
            }
        }
    }
    keys.sort();
    let unique = keys.iter().collect::<HashSet<_>>();
    if unique.len() != keys.len() {
        return Err(OccamError::Validation(
            "experiment trial keys are not unique".into(),
        ));
    }
    Ok(keys)
}

fn validate_config(config: &ExperimentConfig) -> Result<(), OccamError> {
    let dimensions_are_supported = (config.fractions.len() == 8 && config.seeds.len() == 20)
        || (config.fractions.len() == 1 && config.seeds.len() == 1);
    if config.schema_version != 1
        || !dimensions_are_supported
        || config.methods.len() != 8
        || config.trial_timeout_millis == 0
    {
        return Err(OccamError::Validation(
            "experiment config does not match the full or smoke protocol".into(),
        ));
    }
    if config
        .fractions
        .iter()
        .any(|fraction| !fraction.is_finite() || *fraction <= 0.0 || *fraction >= 1.0)
        || config.seeds.iter().collect::<HashSet<_>>().len() != config.seeds.len()
        || config.methods.iter().collect::<HashSet<_>>().len() != config.methods.len()
    {
        return Err(OccamError::Validation(
            "experiment config contains invalid or duplicate values".into(),
        ));
    }
    Ok(())
}
