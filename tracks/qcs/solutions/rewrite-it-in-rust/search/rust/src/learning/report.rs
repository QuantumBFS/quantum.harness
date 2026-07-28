use std::{
    collections::HashSet,
    fs::{self, File},
    io::Write,
    path::{Path, PathBuf},
};

use serde::{Deserialize, Serialize};

use crate::{
    ArithmeticFamily, CandidateScore, OccamError, ResourceLimits, VerificationMetrics,
    learning::{learner::LearnResult, prediction::sha256_hex},
};

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct LearningReport {
    pub schema_version: u32,
    pub instance: String,
    pub selected_family: ArithmeticFamily,
    pub operand_bits: usize,
    pub input_width: usize,
    pub output_width: usize,
    pub candidate_scores: Vec<CandidateScore>,
    pub gate_count: usize,
    pub circuit_sha256: String,
    pub training_scalar: VerificationMetrics,
    pub training_packed: VerificationMetrics,
    pub exhaustive_cases: usize,
    pub exhaustive_mismatches: usize,
    pub prediction_rows: usize,
    pub prediction_sha256: String,
    pub expected_commitment_sha256: Option<String>,
    pub commitment_matches: Option<bool>,
}

impl LearningReport {
    pub fn to_json_pretty(&self) -> Result<String, OccamError> {
        pretty_json(self)
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Manifest {
    pub schema_version: u32,
    pub solution: String,
    pub instances: Vec<ManifestInstance>,
}

impl Manifest {
    pub fn to_json_pretty(&self) -> Result<String, OccamError> {
        pretty_json(self)
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ManifestInstance {
    pub instance: String,
    pub family: ArithmeticFamily,
    pub gate_count: usize,
    pub training_rows: usize,
    pub prediction_rows: usize,
    pub circuit_path: String,
    pub circuit_sha256: String,
    pub prediction_path: String,
    pub prediction_sha256: String,
    pub expected_commitment_sha256: String,
    pub report_path: String,
    pub report_sha256: String,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct WrittenInstance {
    pub manifest_entry: ManifestInstance,
    pub circuit_path: PathBuf,
    pub prediction_path: PathBuf,
    pub report_path: PathBuf,
}

pub fn write_instance_artifacts(
    output_root: &Path,
    instance: &str,
    result: &LearnResult,
) -> Result<WrittenInstance, OccamError> {
    validate_instance_name(instance)?;
    if result.report.instance != instance {
        return Err(OccamError::Validation(format!(
            "result instance {} does not match requested artifact name {instance}",
            result.report.instance
        )));
    }
    let expected_commitment = result
        .report
        .expected_commitment_sha256
        .clone()
        .ok_or_else(|| {
            OccamError::Validation(
                "submission artifacts require an expected commitment SHA-256".into(),
            )
        })?;
    if result.report.commitment_matches != Some(true) {
        return Err(OccamError::Validation(
            "submission artifacts require a successful commitment check".into(),
        ));
    }
    let report_json = result.report.to_json_pretty()?;
    let circuit_path = output_root.join("circuits").join(format!("{instance}.txt"));
    let prediction_path = output_root
        .join("predictions")
        .join(instance)
        .join("test_outputs.csv");
    let report_path = output_root.join("reports").join(format!("{instance}.json"));
    for parent in [
        circuit_path.parent().unwrap(),
        prediction_path.parent().unwrap(),
        report_path.parent().unwrap(),
    ] {
        create_dir_all(parent)?;
    }

    let writes = [
        (&circuit_path, result.circuit.as_bytes()),
        (&prediction_path, result.prediction_csv.as_bytes()),
        (&report_path, report_json.as_bytes()),
    ];
    let temporary_paths: Vec<_> = writes
        .iter()
        .map(|(path, _)| temporary_path(path))
        .collect();
    let write_result = (|| {
        for ((_, contents), temporary) in writes.iter().zip(&temporary_paths) {
            write_synced(temporary, contents)?;
        }
        for ((final_path, _), temporary) in writes.iter().zip(&temporary_paths) {
            fs::rename(temporary, final_path).map_err(|source| OccamError::WriteFile {
                path: (*final_path).clone(),
                source,
            })?;
        }
        Ok(())
    })();
    if write_result.is_err() {
        for temporary in &temporary_paths {
            let _ = fs::remove_file(temporary);
        }
    }
    write_result?;

    let manifest_entry = ManifestInstance {
        instance: instance.to_owned(),
        family: result.report.selected_family,
        gate_count: result.report.gate_count,
        training_rows: result.report.training_scalar.samples,
        prediction_rows: result.report.prediction_rows,
        circuit_path: format!("circuits/{instance}.txt"),
        circuit_sha256: sha256_hex(result.circuit.as_bytes()),
        prediction_path: format!("predictions/{instance}/test_outputs.csv"),
        prediction_sha256: sha256_hex(result.prediction_csv.as_bytes()),
        expected_commitment_sha256: expected_commitment,
        report_path: format!("reports/{instance}.json"),
        report_sha256: sha256_hex(report_json.as_bytes()),
    };
    Ok(WrittenInstance {
        manifest_entry,
        circuit_path,
        prediction_path,
        report_path,
    })
}

pub fn write_manifest(
    output_root: &Path,
    instances: &[WrittenInstance],
) -> Result<PathBuf, OccamError> {
    if instances.is_empty() {
        return Err(OccamError::Validation(
            "cannot write an empty solution manifest".into(),
        ));
    }
    let mut entries: Vec<_> = instances
        .iter()
        .map(|instance| instance.manifest_entry.clone())
        .collect();
    entries.sort_by(|lhs, rhs| lhs.instance.cmp(&rhs.instance));
    let mut names = HashSet::new();
    for entry in &entries {
        if !names.insert(&entry.instance) {
            return Err(OccamError::Validation(format!(
                "duplicate manifest instance {}",
                entry.instance
            )));
        }
    }
    let manifest = Manifest {
        schema_version: 1,
        solution: "rewrite-it-in-rust".into(),
        instances: entries,
    };
    create_dir_all(output_root)?;
    let path = output_root.join("manifest.json");
    let temporary = temporary_path(&path);
    let encoded = manifest.to_json_pretty()?;
    let result = write_synced(&temporary, encoded.as_bytes()).and_then(|()| {
        fs::rename(&temporary, &path).map_err(|source| OccamError::WriteFile {
            path: path.clone(),
            source,
        })
    });
    if result.is_err() {
        let _ = fs::remove_file(&temporary);
    }
    result?;
    Ok(path)
}

pub fn load_written_instance(
    output_root: &Path,
    instance: &str,
    limits: &ResourceLimits,
) -> Result<WrittenInstance, OccamError> {
    validate_instance_name(instance)?;
    let circuit_path = output_root.join("circuits").join(format!("{instance}.txt"));
    let prediction_path = output_root
        .join("predictions")
        .join(instance)
        .join("test_outputs.csv");
    let report_path = output_root.join("reports").join(format!("{instance}.json"));
    let circuit = read_bounded(&circuit_path, limits)?;
    let prediction = read_bounded(&prediction_path, limits)?;
    let report_bytes = read_bounded(&report_path, limits)?;
    let report: LearningReport = serde_json::from_slice(&report_bytes).map_err(|error| {
        OccamError::Validation(format!(
            "failed to parse learning report {}: {error}",
            report_path.display()
        ))
    })?;
    if report.schema_version != 1 {
        return Err(OccamError::Validation(format!(
            "unsupported learning report schema {} for {instance}",
            report.schema_version
        )));
    }
    if report.instance != instance {
        return Err(OccamError::Validation(format!(
            "report instance {} does not match {instance}",
            report.instance
        )));
    }
    let circuit_sha256 = sha256_hex(&circuit);
    if circuit_sha256 != report.circuit_sha256 {
        return Err(OccamError::Validation(format!(
            "{instance} circuit hash mismatch: report {}, actual {circuit_sha256}",
            report.circuit_sha256
        )));
    }
    let prediction_sha256 = sha256_hex(&prediction);
    if prediction_sha256 != report.prediction_sha256 {
        return Err(OccamError::Validation(format!(
            "{instance} prediction hash mismatch: report {}, actual {prediction_sha256}",
            report.prediction_sha256
        )));
    }
    let expected_commitment_sha256 =
        report.expected_commitment_sha256.clone().ok_or_else(|| {
            OccamError::Validation(format!(
                "{instance} report has no expected commitment SHA-256"
            ))
        })?;
    if report.commitment_matches != Some(true) || prediction_sha256 != expected_commitment_sha256 {
        return Err(OccamError::Validation(format!(
            "{instance} report does not prove a matching prediction commitment"
        )));
    }
    let manifest_entry = ManifestInstance {
        instance: instance.to_owned(),
        family: report.selected_family,
        gate_count: report.gate_count,
        training_rows: report.training_scalar.samples,
        prediction_rows: report.prediction_rows,
        circuit_path: format!("circuits/{instance}.txt"),
        circuit_sha256,
        prediction_path: format!("predictions/{instance}/test_outputs.csv"),
        prediction_sha256,
        expected_commitment_sha256,
        report_path: format!("reports/{instance}.json"),
        report_sha256: sha256_hex(&report_bytes),
    };
    Ok(WrittenInstance {
        manifest_entry,
        circuit_path,
        prediction_path,
        report_path,
    })
}

fn validate_instance_name(instance: &str) -> Result<(), OccamError> {
    let suffix = instance.strip_prefix("mystery-").ok_or_else(|| {
        OccamError::Validation(format!(
            "instance name {instance:?} must match mystery-[A-Z]"
        ))
    })?;
    if suffix.len() != 1 || !suffix.as_bytes()[0].is_ascii_uppercase() {
        return Err(OccamError::Validation(format!(
            "instance name {instance:?} must match mystery-[A-Z]"
        )));
    }
    Ok(())
}

fn pretty_json(value: &impl Serialize) -> Result<String, OccamError> {
    serde_json::to_string_pretty(value)
        .map(|encoded| format!("{encoded}\n"))
        .map_err(|error| OccamError::Validation(format!("JSON encoding failed: {error}")))
}

fn temporary_path(path: &Path) -> PathBuf {
    let file_name = path.file_name().and_then(|name| name.to_str()).unwrap();
    path.with_file_name(format!(".{file_name}.{}.tmp-occam71", std::process::id()))
}

fn create_dir_all(path: &Path) -> Result<(), OccamError> {
    fs::create_dir_all(path).map_err(|source| OccamError::WriteFile {
        path: path.to_owned(),
        source,
    })
}

fn read_bounded(path: &Path, limits: &ResourceLimits) -> Result<Vec<u8>, OccamError> {
    let metadata = fs::metadata(path).map_err(|source| OccamError::ReadFile {
        path: path.to_owned(),
        source,
    })?;
    if metadata.len() > limits.max_source_bytes as u64 {
        return Err(OccamError::ResourceLimit {
            resource: "solution artifact bytes",
            requested: usize::try_from(metadata.len()).unwrap_or(usize::MAX),
            limit: limits.max_source_bytes,
        });
    }
    fs::read(path).map_err(|source| OccamError::ReadFile {
        path: path.to_owned(),
        source,
    })
}

fn write_synced(path: &Path, contents: &[u8]) -> Result<(), OccamError> {
    let mut file = File::create(path).map_err(|source| OccamError::WriteFile {
        path: path.to_owned(),
        source,
    })?;
    file.write_all(contents)
        .and_then(|()| file.sync_all())
        .map_err(|source| OccamError::WriteFile {
            path: path.to_owned(),
            source,
        })
}
