use std::{
    collections::{BTreeMap, HashMap, HashSet, VecDeque},
    fs,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    thread,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

use crate::{OccamError, sha256_hex};

use super::{
    ExperimentConfig, OracleTask, ResearchTools, TrialBudget, TrialKey, TrialRecord, TrialStatus,
    expected_trial_keys, load_experiment_config, official_and_synthetic_tasks, peak_rss_bytes,
    runner::{failure_record, run_trial_with_tools},
    split_task,
};

pub fn run_measured_trial(
    config_path: &Path,
    tasks_path: &Path,
    key: TrialKey,
    output_path: &Path,
    abc_binary: Option<PathBuf>,
) -> Result<TrialRecord, OccamError> {
    validate_task_manifest(tasks_path)?;
    let (config, config_sha256) = load_config_and_hash(config_path)?;
    let tasks = official_and_synthetic_tasks()?;
    let task_ids = tasks.iter().map(|task| task.id.clone()).collect::<Vec<_>>();
    let expected = expected_trial_keys(&task_ids, &config)?;
    if expected.binary_search(&key).is_err() {
        return Err(OccamError::Validation(format!(
            "trial key is outside the fixed experiment protocol: {key:?}"
        )));
    }
    let task = tasks
        .iter()
        .find(|task| task.id == key.task)
        .ok_or_else(|| OccamError::Validation(format!("unknown trial task {}", key.task)))?;
    let fraction = f64::from(key.fraction_basis_points) / 100_000.0;
    let split = split_task(task, fraction, key.seed, config.experiment_seed)?;
    let started_unix_micros = unix_micros()?;
    let started = Instant::now();
    let budget = TrialBudget {
        timeout: Duration::from_millis(config.trial_timeout_millis),
        ..TrialBudget::default()
    };
    let tools = ResearchTools {
        abc: abc_binary,
        ..ResearchTools::default()
    };
    let mut record = run_trial_with_tools(task, &split, key, &config_sha256, tools, budget)?;
    record.runtime_micros = elapsed_micros(started);
    record.peak_rss_bytes = peak_rss_bytes()?;
    record.host_identifier = environment_identifier();
    record.process_id = std::process::id();
    record.started_unix_micros = started_unix_micros;
    write_record_atomic(output_path, &record)?;
    Ok(record)
}

pub fn run_isolated_experiment(
    executable: &Path,
    config_path: &Path,
    tasks_path: &Path,
    raw_measured_path: &Path,
    abc_binary: Option<&Path>,
    jobs: usize,
) -> Result<Vec<TrialRecord>, OccamError> {
    if jobs == 0 {
        return Err(OccamError::Validation(
            "experiment jobs must be positive".into(),
        ));
    }
    validate_task_manifest(tasks_path)?;
    let (config, config_sha256) = load_config_and_hash(config_path)?;
    let tasks = official_and_synthetic_tasks()?;
    let task_ids = tasks.iter().map(|task| task.id.clone()).collect::<Vec<_>>();
    let expected = expected_trial_keys(&task_ids, &config)?;
    let expected_set = expected.iter().cloned().collect::<HashSet<_>>();
    let mut records = load_existing_records(raw_measured_path, &expected_set, &config_sha256)?;
    let mut missing = expected
        .into_iter()
        .filter(|key| !records.contains_key(key))
        .collect::<VecDeque<_>>();
    let task_map = tasks
        .iter()
        .map(|task| (task.id.as_str(), task))
        .collect::<HashMap<_, _>>();
    let temporary = ExperimentDirectory::new()?;
    let mut active = Vec::<ActiveTrial>::new();
    let timeout =
        Duration::from_millis(config.trial_timeout_millis).saturating_add(Duration::from_secs(2));

    while !missing.is_empty() || !active.is_empty() {
        while active.len() < jobs {
            let Some(key) = missing.pop_front() else {
                break;
            };
            let task = task_map.get(key.task.as_str()).ok_or_else(|| {
                OccamError::Validation(format!("unknown trial task {}", key.task))
            })?;
            let (observed_rows, held_out_rows) = split_counts(task, &key, &config)?;
            let key_json = serde_json::to_string(&key).map_err(|error| {
                OccamError::Validation(format!("trial key JSON encoding failed: {error}"))
            })?;
            let key_hash = sha256_hex(key_json.as_bytes());
            let output = temporary.path.join(format!("{key_hash}.json"));
            let mut command = Command::new(executable);
            command
                .arg("experiment-trial")
                .arg("--config")
                .arg(config_path)
                .arg("--tasks")
                .arg(tasks_path)
                .arg("--key-json")
                .arg(key_json)
                .arg("--output")
                .arg(&output)
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null());
            if let Some(abc) = abc_binary {
                command.arg("--abc").arg(abc);
            }
            let child = command.spawn().map_err(|error| {
                OccamError::Validation(format!("failed to spawn isolated trial process: {error}"))
            })?;
            active.push(ActiveTrial {
                key,
                child,
                output,
                started: Instant::now(),
                started_unix_micros: unix_micros()?,
                observed_rows,
                held_out_rows,
            });
        }

        let mut completed_any = false;
        let mut index = 0usize;
        while index < active.len() {
            let status = active[index].child.try_wait().map_err(|error| {
                OccamError::Validation(format!("isolated trial wait failed: {error}"))
            })?;
            let expired = active[index].started.elapsed() >= timeout;
            if status.is_none() && !expired {
                index += 1;
                continue;
            }

            completed_any = true;
            let mut state = active.swap_remove(index);
            let record = if expired && status.is_none() {
                let child_id = state.child.id();
                let _ = state.child.kill();
                let _ = state.child.wait();
                measured_parent_failure(
                    state,
                    &config_sha256,
                    TrialStatus::Timeout,
                    format!(
                        "parent terminated isolated trial after {} milliseconds",
                        timeout.as_millis()
                    ),
                    child_id,
                )?
            } else if status.is_some_and(|status| status.success()) {
                load_child_record(&state.output, &state.key, &config_sha256)?
            } else {
                let child_id = state.child.id();
                measured_parent_failure(
                    state,
                    &config_sha256,
                    TrialStatus::Error,
                    format!("isolated trial process exited with status {status:?}"),
                    child_id,
                )?
            };
            records.insert(record.key.clone(), record);
            write_records_atomic(raw_measured_path, records.values())?;
        }
        if !completed_any && !active.is_empty() {
            thread::sleep(Duration::from_millis(10));
        }
    }

    if records.len() != expected_set.len() {
        return Err(OccamError::Validation(format!(
            "isolated experiment produced {} rows, expected {}",
            records.len(),
            expected_set.len()
        )));
    }
    Ok(records.into_values().collect())
}

struct ActiveTrial {
    key: TrialKey,
    child: Child,
    output: PathBuf,
    started: Instant,
    started_unix_micros: u64,
    observed_rows: usize,
    held_out_rows: usize,
}

fn measured_parent_failure(
    state: ActiveTrial,
    config_sha256: &str,
    status: TrialStatus,
    detail: String,
    child_id: u32,
) -> Result<TrialRecord, OccamError> {
    let mut record = failure_record(
        state.key,
        config_sha256,
        state.observed_rows,
        state.held_out_rows,
        status,
        detail,
    );
    record.runtime_micros = elapsed_micros(state.started);
    record.peak_rss_bytes = peak_rss_bytes()?;
    record.host_identifier = environment_identifier();
    record.process_id = child_id;
    record.started_unix_micros = state.started_unix_micros;
    Ok(record)
}

fn load_child_record(
    path: &Path,
    expected_key: &TrialKey,
    config_sha256: &str,
) -> Result<TrialRecord, OccamError> {
    let source = fs::read(path).map_err(|source| OccamError::ReadFile {
        path: path.to_owned(),
        source,
    })?;
    let record: TrialRecord = serde_json::from_slice(&source)
        .map_err(|error| OccamError::Validation(format!("invalid child trial JSON: {error}")))?;
    validate_measured_record(&record, expected_key, config_sha256)?;
    Ok(record)
}

fn load_existing_records(
    path: &Path,
    expected: &HashSet<TrialKey>,
    config_sha256: &str,
) -> Result<BTreeMap<TrialKey, TrialRecord>, OccamError> {
    if !path.exists() {
        return Ok(BTreeMap::new());
    }
    let source = fs::read_to_string(path).map_err(|source| OccamError::ReadFile {
        path: path.to_owned(),
        source,
    })?;
    let mut records = BTreeMap::new();
    for (line_index, line) in source.lines().enumerate() {
        if line.trim().is_empty() {
            continue;
        }
        let record: TrialRecord = serde_json::from_str(line).map_err(|error| {
            OccamError::Validation(format!(
                "invalid measured trial JSON at line {}: {error}",
                line_index + 1
            ))
        })?;
        if !expected.contains(&record.key) {
            return Err(OccamError::Validation(format!(
                "measured trial file contains unknown key {:?}",
                record.key
            )));
        }
        validate_measured_record(&record, &record.key, config_sha256)?;
        let key = record.key.clone();
        if records.insert(key.clone(), record).is_some() {
            return Err(OccamError::Validation(format!(
                "measured trial file contains duplicate key {key:?}"
            )));
        }
    }
    Ok(records)
}

fn validate_measured_record(
    record: &TrialRecord,
    expected_key: &TrialKey,
    config_sha256: &str,
) -> Result<(), OccamError> {
    if record.schema_version != 1
        || &record.key != expected_key
        || record.config_sha256 != config_sha256
        || record.runtime_micros == 0
        || record.peak_rss_bytes == 0
        || record.host_identifier.is_empty()
        || record.process_id == 0
        || record.started_unix_micros == 0
    {
        return Err(OccamError::Validation(format!(
            "invalid measured trial record for {expected_key:?}"
        )));
    }
    Ok(())
}

fn split_counts(
    task: &OracleTask,
    key: &TrialKey,
    config: &ExperimentConfig,
) -> Result<(usize, usize), OccamError> {
    let fraction = f64::from(key.fraction_basis_points) / 100_000.0;
    let split = split_task(task, fraction, key.seed, config.experiment_seed)?;
    Ok((split.observed_indices.len(), split.held_out_indices.len()))
}

fn load_config_and_hash(path: &Path) -> Result<(ExperimentConfig, String), OccamError> {
    let source = fs::read(path).map_err(|source| OccamError::ReadFile {
        path: path.to_owned(),
        source,
    })?;
    let hash = sha256_hex(&source);
    Ok((load_experiment_config(path)?, hash))
}

fn validate_task_manifest(path: &Path) -> Result<(), OccamError> {
    let source = fs::read_to_string(path).map_err(|source| OccamError::ReadFile {
        path: path.to_owned(),
        source,
    })?;
    let supplied: serde_json::Value = serde_json::from_str(&source)
        .map_err(|error| OccamError::Validation(format!("invalid task manifest JSON: {error}")))?;
    let compiled: serde_json::Value = serde_json::from_str(include_str!(
        "../../../experiments/occam-generalization/tasks.json"
    ))
    .expect("compiled task manifest must be valid JSON");
    if supplied != compiled {
        return Err(OccamError::Validation(
            "task manifest differs from the compiled evaluator-only definitions".into(),
        ));
    }
    Ok(())
}

fn write_record_atomic(path: &Path, record: &TrialRecord) -> Result<(), OccamError> {
    let mut encoded = serde_json::to_string(record)
        .map_err(|error| OccamError::Validation(format!("trial JSON encoding failed: {error}")))?;
    encoded.push('\n');
    write_atomic(path, encoded.as_bytes())
}

fn write_records_atomic<'a>(
    path: &Path,
    records: impl Iterator<Item = &'a TrialRecord>,
) -> Result<(), OccamError> {
    let mut output = String::new();
    for record in records {
        output.push_str(&serde_json::to_string(record).map_err(|error| {
            OccamError::Validation(format!("trial JSON encoding failed: {error}"))
        })?);
        output.push('\n');
    }
    write_atomic(path, output.as_bytes())
}

fn write_atomic(path: &Path, bytes: &[u8]) -> Result<(), OccamError> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|source| OccamError::WriteFile {
            path: parent.to_owned(),
            source,
        })?;
    }
    let temporary = path.with_extension(format!("{}.tmp", std::process::id()));
    fs::write(&temporary, bytes).map_err(|source| OccamError::WriteFile {
        path: temporary.clone(),
        source,
    })?;
    fs::rename(&temporary, path).map_err(|source| OccamError::WriteFile {
        path: path.to_owned(),
        source,
    })
}

fn elapsed_micros(started: Instant) -> u64 {
    u64::try_from(started.elapsed().as_micros())
        .unwrap_or(u64::MAX)
        .max(1)
}

fn unix_micros() -> Result<u64, OccamError> {
    let duration = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|error| {
            OccamError::Validation(format!("system clock is before epoch: {error}"))
        })?;
    u64::try_from(duration.as_micros()).map_err(|_| OccamError::ArithmeticOverflow {
        context: "trial start timestamp",
    })
}

fn environment_identifier() -> String {
    let host = std::env::var("HOSTNAME")
        .or_else(|_| std::env::var("COMPUTERNAME"))
        .unwrap_or_else(|_| "unknown-host".into());
    let material = format!(
        "{}|{}|{}",
        std::env::consts::OS,
        std::env::consts::ARCH,
        host
    );
    let hash = sha256_hex(material.as_bytes());
    format!(
        "{}-{}-{}",
        std::env::consts::OS,
        std::env::consts::ARCH,
        &hash[..16]
    )
}

struct ExperimentDirectory {
    path: PathBuf,
}

impl ExperimentDirectory {
    fn new() -> Result<Self, OccamError> {
        let path = std::env::temp_dir().join(format!(
            "occam71-isolated-{}-{}",
            std::process::id(),
            unix_micros()?
        ));
        fs::create_dir(&path).map_err(|source| OccamError::WriteFile {
            path: path.clone(),
            source,
        })?;
        Ok(Self { path })
    }
}

impl Drop for ExperimentDirectory {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.path);
    }
}
