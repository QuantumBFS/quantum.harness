//! Resumable, budget-aware execution and atomic artifact persistence.

use crate::circuit::SamplingMode;
use crate::config::{RunConfig, RuntimeBudget, StageConfig};
use crate::oracles::negative_control_oracle;
use crate::rng::derive_seed;
use crate::sampler::{estimate_stream, StreamEstimate};
use crate::schema::{RunManifest, RunStatus, SeedRecord, TaskRecord, TaskState, SCHEMA_VERSION};
use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::fs::{self, File};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::{Instant, SystemTime, UNIX_EPOCH};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ReserveReason {
    None,
    CrossingPrecisionInsufficient,
    LargestWidthIncomplete,
    AnisotropyNearlyStable,
    RequiredOracleRerun,
}

impl ReserveReason {
    fn label(self) -> Option<String> {
        match self {
            Self::None => None,
            Self::CrossingPrecisionInsufficient => {
                Some("crossing_precision_insufficient".to_owned())
            }
            Self::LargestWidthIncomplete => Some("largest_width_incomplete".to_owned()),
            Self::AnisotropyNearlyStable => Some("anisotropy_nearly_stable".to_owned()),
            Self::RequiredOracleRerun => Some("required_oracle_rerun".to_owned()),
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RuntimeDecision {
    Continue,
    OrdinaryStop,
    ReserveAllowed,
    HardStop,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct RuntimePolicy {
    ordinary_stop_seconds: u64,
    hard_stop_seconds: u64,
}

impl RuntimePolicy {
    pub const fn production() -> Self {
        Self {
            ordinary_stop_seconds: 3_300,
            hard_stop_seconds: 5_100,
        }
    }

    pub fn from_budget(budget: &RuntimeBudget) -> Self {
        Self {
            ordinary_stop_seconds: budget.ordinary_stop_seconds,
            hard_stop_seconds: budget.hard_stop_seconds,
        }
    }

    pub fn decision(self, elapsed_seconds: u64, reason: ReserveReason) -> RuntimeDecision {
        if elapsed_seconds >= self.hard_stop_seconds {
            RuntimeDecision::HardStop
        } else if elapsed_seconds < self.ordinary_stop_seconds {
            RuntimeDecision::Continue
        } else if reason == ReserveReason::None {
            RuntimeDecision::OrdinaryStop
        } else {
            RuntimeDecision::ReserveAllowed
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
struct StreamArtifact {
    schema_version: u32,
    stage_name: String,
    theta_pi: f64,
    phi_pi: f64,
    stage_config: StageConfig,
    estimate: StreamEstimate,
}

#[derive(Clone, Copy, Debug)]
struct TaskCoordinate {
    stage: usize,
    angle: usize,
    width: usize,
    stream: usize,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
struct RefinementRequest {
    schema_version: u32,
    status: String,
    stage: String,
    theta_pi: f64,
    phi_pi: Vec<f64>,
    widths: Vec<usize>,
    streams: usize,
    burn_in_layers_per_width: usize,
    measurement_layers_per_width: usize,
    block_layers_per_width: usize,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct BenchmarkArtifact {
    pub schema_version: u32,
    pub width: usize,
    pub streams: usize,
    pub elapsed_seconds: f64,
    pub benchmark_gate_updates: u64,
    pub configured_gate_updates: u64,
    pub forecast_seconds: f64,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
struct NegativeControlArtifact {
    schema_version: u32,
    is_physical: bool,
    control: crate::oracles::NegativeControlOracle,
}

pub fn run_simulation(
    config_path: &Path,
    run_dir: &Path,
    mode: SamplingMode,
) -> Result<RunManifest> {
    let config = RunConfig::load(config_path)?;
    if config.production_gates {
        require_passing_oracles(run_dir)?;
    }
    run_coordinates(
        &config,
        run_dir,
        mode,
        scheduled_coordinates(&config),
        ReserveReason::None,
    )
}

pub fn run_requested_tasks(
    config_path: &Path,
    run_dir: &Path,
    request_path: &Path,
) -> Result<RunManifest> {
    let base_config = RunConfig::load(config_path)?;
    let manifest_path = run_dir.join("manifest.json");
    let mut manifest: RunManifest = serde_json::from_slice(
        &fs::read(&manifest_path).context("refinement requires an existing manifest")?,
    )?;
    if manifest.schema_version != SCHEMA_VERSION {
        bail!("existing manifest schema version is incompatible");
    }
    let relative = request_path
        .strip_prefix(run_dir)
        .map_err(|_| anyhow::anyhow!("refinement request must be inside the run directory"))?
        .to_string_lossy()
        .replace('\\', "/");
    let expected_hash = manifest
        .artifact_sha256
        .get(&relative)
        .ok_or_else(|| anyhow::anyhow!("refinement request lacks a manifest SHA-256"))?;
    let actual_hash = sha256_file(request_path)?;
    if &actual_hash != expected_hash {
        bail!("refinement request SHA-256 does not match the manifest");
    }
    let request: RefinementRequest = serde_json::from_slice(&fs::read(request_path)?)?;
    if request.schema_version != SCHEMA_VERSION {
        bail!("refinement request schema version is incompatible");
    }
    if request.status == "inconclusive" {
        if !request.phi_pi.is_empty() {
            bail!("inconclusive refinement request must have no angles");
        }
        return Ok(manifest);
    }
    if request.status != "bracketed" {
        bail!("refinement request status must be bracketed or inconclusive");
    }

    let refinement = StageConfig {
        name: request.stage,
        theta_pi: request.theta_pi,
        phi_pi: request.phi_pi,
        widths: request.widths,
        streams: request.streams,
        burn_in_layers_per_width: request.burn_in_layers_per_width,
        measurement_layers_per_width: request.measurement_layers_per_width,
        block_layers_per_width: request.block_layers_per_width,
    };
    let mut extended = base_config.clone();
    extended.stages.push(refinement);
    extended.validate()?;

    if manifest.config == base_config {
        manifest.config = extended.clone();
    } else if manifest.config != extended {
        bail!("existing manifest is incompatible with the refinement request");
    }
    let stage_index = extended.stages.len() - 1;
    let refinement_coordinates = scheduled_coordinates_for_stage(&extended, stage_index);
    for &coordinate in &refinement_coordinates {
        let key = task_key(&extended, coordinate);
        if !manifest.tasks.iter().any(|task| task.key == key) {
            manifest.tasks.push(TaskRecord {
                key,
                state: TaskState::Pending,
                elapsed_s: 0.0,
                reserve_reason: None,
                artifact: None,
            });
        }
    }
    manifest.updated_at = timestamp();
    atomic_json(&manifest_path, &manifest)?;
    run_coordinates(
        &extended,
        run_dir,
        SamplingMode::Born,
        refinement_coordinates,
        ReserveReason::LargestWidthIncomplete,
    )
}

pub fn run_benchmark(config_path: &Path, run_dir: &Path) -> Result<BenchmarkArtifact> {
    let config = RunConfig::load(config_path)?;
    let mut benchmark_config = config.clone();
    benchmark_config.production_gates = false;
    benchmark_config.stages = vec![StageConfig {
        name: "microbenchmark".to_owned(),
        theta_pi: config.stages[0].theta_pi,
        phi_pi: vec![config.stages[0].phi_pi[0]],
        widths: vec![16],
        streams: 2,
        burn_in_layers_per_width: 1,
        measurement_layers_per_width: 2,
        block_layers_per_width: 1,
    }];
    benchmark_config.validate()?;

    let started = Instant::now();
    for stream in 0..2 {
        estimate_stream(&benchmark_config, 0, 0, 16, stream, SamplingMode::Born)?;
    }
    let elapsed_seconds = started.elapsed().as_secs_f64();
    let benchmark_gate_updates = configured_gate_updates(&benchmark_config);
    let configured_gate_updates = configured_gate_updates(&config);
    let forecast_seconds =
        elapsed_seconds * configured_gate_updates as f64 / benchmark_gate_updates as f64;
    let artifact = BenchmarkArtifact {
        schema_version: SCHEMA_VERSION,
        width: 16,
        streams: 2,
        elapsed_seconds,
        benchmark_gate_updates,
        configured_gate_updates,
        forecast_seconds,
    };
    atomic_json(&run_dir.join("raw/benchmark.json"), &artifact)?;
    Ok(artifact)
}

pub fn run_negative_control(config_path: &Path, run_dir: &Path) -> Result<()> {
    let config = RunConfig::load(config_path)?;
    let artifact = NegativeControlArtifact {
        schema_version: SCHEMA_VERSION,
        is_physical: false,
        control: negative_control_oracle(config.base_seed)?,
    };
    atomic_json(&run_dir.join("raw/negative-control.json"), &artifact)
}

fn run_coordinates(
    config: &RunConfig,
    run_dir: &Path,
    mode: SamplingMode,
    coordinates: Vec<TaskCoordinate>,
    reserve_reason: ReserveReason,
) -> Result<RunManifest> {
    fs::create_dir_all(run_dir.join("raw/streams"))?;
    let manifest_path = run_dir.join("manifest.json");
    let mut manifest = load_or_initialize_manifest(config, &manifest_path, &coordinates)?;
    let oracle_path = run_dir.join("raw/oracles.json");
    if oracle_path.exists() {
        manifest
            .artifact_sha256
            .insert("raw/oracles.json".to_owned(), sha256_file(&oracle_path)?);
    }
    let started = Instant::now();
    let policy = RuntimePolicy::from_budget(&config.runtime);

    for coordinate in coordinates {
        let key = task_key(config, coordinate);
        if task_state(&manifest, &key) == Some(TaskState::Completed) {
            validate_reusable_stream(config, run_dir, &manifest, coordinate, mode)?;
            continue;
        }

        let decision = policy.decision(started.elapsed().as_secs(), reserve_reason);
        let task_reserve_reason = match decision {
            RuntimeDecision::Continue => ReserveReason::None,
            RuntimeDecision::ReserveAllowed => reserve_reason,
            RuntimeDecision::OrdinaryStop | RuntimeDecision::HardStop => break,
        };
        set_task_state(&mut manifest, &key, TaskState::Running);
        manifest.updated_at = timestamp();
        atomic_json(&manifest_path, &manifest)?;

        let estimate = estimate_stream(
            config,
            coordinate.stage,
            coordinate.angle,
            coordinate.width,
            coordinate.stream,
            mode,
        )
        .with_context(|| format!("stream task {key} failed"))?;
        let stage = &config.stages[coordinate.stage];
        let artifact = StreamArtifact {
            schema_version: SCHEMA_VERSION,
            stage_name: stage.name.clone(),
            theta_pi: stage.theta_pi,
            phi_pi: stage.phi_pi[coordinate.angle],
            stage_config: stage.clone(),
            estimate,
        };
        let relative = stream_relative_path(config, coordinate);
        let absolute = run_dir.join(&relative);
        atomic_json(&absolute, &artifact)?;
        let hash = sha256_file(&absolute)?;

        manifest.artifact_sha256.insert(relative.clone(), hash);
        if !manifest.seeds.iter().any(|record| {
            record.stage == coordinate.stage
                && record.angle == coordinate.angle
                && record.width == coordinate.width
                && record.stream == coordinate.stream
        }) {
            manifest.seeds.push(SeedRecord {
                stage: coordinate.stage,
                angle: coordinate.angle,
                width: coordinate.width,
                stream: coordinate.stream,
                purpose: 0x424f_524e,
                seed: artifact.estimate.seed,
            });
        }
        complete_task(
            &mut manifest,
            &key,
            started.elapsed().as_secs_f64(),
            task_reserve_reason,
            &relative,
        );
        manifest.elapsed_s = started.elapsed().as_secs_f64();
        manifest.updated_at = timestamp();
        atomic_json(&manifest_path, &manifest)?;
    }

    let csv_path = run_dir.join("raw/blocks.csv");
    write_blocks_csv(config, run_dir, &manifest, mode, &csv_path)?;
    manifest
        .artifact_sha256
        .insert("raw/blocks.csv".to_owned(), sha256_file(&csv_path)?);
    manifest.elapsed_s = started.elapsed().as_secs_f64();
    manifest.updated_at = timestamp();
    atomic_json(&manifest_path, &manifest)?;
    Ok(manifest)
}

fn scheduled_coordinates(config: &RunConfig) -> Vec<TaskCoordinate> {
    let mut coordinates = Vec::new();
    for stage_index in 0..config.stages.len() {
        coordinates.extend(scheduled_coordinates_for_stage(config, stage_index));
    }
    coordinates
}

fn configured_gate_updates(config: &RunConfig) -> u64 {
    config
        .stages
        .iter()
        .map(|stage| {
            stage
                .widths
                .iter()
                .map(|&width| {
                    stage.phi_pi.len() as u64
                        * stage.streams as u64
                        * (stage.burn_in_layers_per_width + stage.measurement_layers_per_width)
                            as u64
                        * width as u64
                        * (2 * width) as u64
                })
                .sum::<u64>()
        })
        .sum()
}

fn scheduled_coordinates_for_stage(config: &RunConfig, stage_index: usize) -> Vec<TaskCoordinate> {
    let stage = &config.stages[stage_index];
    let angle_order = if stage.name.contains("diii") && stage.phi_pi.len() > 1 {
        let mut order = vec![0, stage.phi_pi.len() - 1];
        order.extend(1..stage.phi_pi.len() - 1);
        order
    } else {
        (0..stage.phi_pi.len()).collect()
    };
    let mut coordinates = Vec::new();
    for angle in angle_order {
        for &width in &stage.widths {
            for stream in 0..stage.streams {
                coordinates.push(TaskCoordinate {
                    stage: stage_index,
                    angle,
                    width,
                    stream,
                });
            }
        }
    }
    coordinates
}

fn load_or_initialize_manifest(
    config: &RunConfig,
    path: &Path,
    coordinates: &[TaskCoordinate],
) -> Result<RunManifest> {
    if path.exists() {
        let bytes = fs::read(path)?;
        let manifest: RunManifest =
            serde_json::from_slice(&bytes).context("failed to parse existing manifest")?;
        if manifest.schema_version != SCHEMA_VERSION {
            bail!("existing manifest schema version is incompatible");
        }
        if !manifest.config.compatible_with(config) {
            bail!("existing manifest configuration differs from the requested run");
        }
        return Ok(manifest);
    }

    let tasks = coordinates
        .iter()
        .map(|&coordinate| TaskRecord {
            key: task_key(config, coordinate),
            state: TaskState::Pending,
            elapsed_s: 0.0,
            reserve_reason: None,
            artifact: None,
        })
        .collect();
    let now = timestamp();
    let manifest = RunManifest {
        schema_version: SCHEMA_VERSION,
        status: RunStatus::Running,
        config: config.clone(),
        git_commit: option_env!("GIT_COMMIT").unwrap_or("unknown").to_owned(),
        started_at: now.clone(),
        updated_at: now,
        completed_at: None,
        elapsed_s: 0.0,
        tasks,
        seeds: Vec::new(),
        artifact_sha256: BTreeMap::new(),
    };
    atomic_json(path, &manifest)?;
    Ok(manifest)
}

fn validate_reusable_stream(
    config: &RunConfig,
    run_dir: &Path,
    manifest: &RunManifest,
    coordinate: TaskCoordinate,
    mode: SamplingMode,
) -> Result<StreamArtifact> {
    let relative = stream_relative_path(config, coordinate);
    let expected_hash = manifest
        .artifact_sha256
        .get(&relative)
        .ok_or_else(|| anyhow::anyhow!("completed stream lacks a manifest SHA-256"))?;
    let absolute = run_dir.join(&relative);
    let actual_hash = sha256_file(&absolute)?;
    if &actual_hash != expected_hash {
        bail!("stream artifact SHA-256 mismatch for {relative}");
    }
    let artifact: StreamArtifact = serde_json::from_slice(&fs::read(&absolute)?)?;
    let stage = &config.stages[coordinate.stage];
    let expected_seed = derive_seed(
        config.base_seed,
        coordinate.stage as u64,
        coordinate.angle,
        coordinate.width,
        coordinate.stream,
        0x424f_524e,
    );
    if artifact.schema_version != SCHEMA_VERSION
        || artifact.stage_config != *stage
        || artifact.stage_name != stage.name
        || artifact.theta_pi != stage.theta_pi
        || artifact.phi_pi != stage.phi_pi[coordinate.angle]
        || artifact.estimate.stage_index != coordinate.stage
        || artifact.estimate.angle_index != coordinate.angle
        || artifact.estimate.width != coordinate.width
        || artifact.estimate.stream != coordinate.stream
        || artifact.estimate.seed != expected_seed
        || artifact.estimate.mode != mode
        || artifact.estimate.is_physical != mode.is_physical()
        || artifact
            .estimate
            .blocks
            .iter()
            .enumerate()
            .any(|(index, block)| block.block_index != index)
    {
        bail!("completed stream metadata failed resume validation for {relative}");
    }
    Ok(artifact)
}

fn write_blocks_csv(
    config: &RunConfig,
    run_dir: &Path,
    manifest: &RunManifest,
    mode: SamplingMode,
    path: &Path,
) -> Result<()> {
    let mut text = String::from(
        "stage,theta_pi,phi_pi,width,stream,block_index,gamma,half_chain_entropy,\
         min_probability,max_antisymmetry_error,max_purity_error,mode,is_physical,\
         entropy_arc_json,spatial_correlations_json,lyapunov_json\n",
    );
    for coordinate in scheduled_coordinates(config) {
        let key = task_key(config, coordinate);
        if task_state(manifest, &key) != Some(TaskState::Completed) {
            continue;
        }
        let artifact = validate_reusable_stream(config, run_dir, manifest, coordinate, mode)?;
        for block in artifact.estimate.blocks {
            let fields = [
                csv_quote(&artifact.stage_name),
                artifact.theta_pi.to_string(),
                artifact.phi_pi.to_string(),
                coordinate.width.to_string(),
                coordinate.stream.to_string(),
                block.block_index.to_string(),
                block.gamma.to_string(),
                block.half_chain_entropy.to_string(),
                block.min_probability.to_string(),
                block.max_antisymmetry_error.to_string(),
                block.max_purity_error.to_string(),
                csv_quote(&format!("{:?}", mode).to_lowercase()),
                mode.is_physical().to_string(),
                csv_quote(&serde_json::to_string(&block.entropy_arc)?),
                csv_quote(&serde_json::to_string(&block.spatial_correlations)?),
                csv_quote(&serde_json::to_string(&block.lyapunov)?),
            ];
            text.push_str(&fields.join(","));
            text.push('\n');
        }
    }
    atomic_bytes(path, text.as_bytes())
}

fn task_key(config: &RunConfig, coordinate: TaskCoordinate) -> String {
    format!(
        "{}-a{:02}-L{:02}-s{:03}",
        config.stages[coordinate.stage].name, coordinate.angle, coordinate.width, coordinate.stream
    )
}

fn stream_relative_path(config: &RunConfig, coordinate: TaskCoordinate) -> String {
    format!("raw/streams/{}.json", task_key(config, coordinate))
}

fn task_state(manifest: &RunManifest, key: &str) -> Option<TaskState> {
    manifest
        .tasks
        .iter()
        .find(|task| task.key == key)
        .map(|task| task.state.clone())
}

fn set_task_state(manifest: &mut RunManifest, key: &str, state: TaskState) {
    if let Some(task) = manifest.tasks.iter_mut().find(|task| task.key == key) {
        task.state = state;
    }
}

fn complete_task(
    manifest: &mut RunManifest,
    key: &str,
    elapsed_s: f64,
    reserve_reason: ReserveReason,
    artifact: &str,
) {
    if let Some(task) = manifest.tasks.iter_mut().find(|task| task.key == key) {
        task.state = TaskState::Completed;
        task.elapsed_s = elapsed_s;
        task.reserve_reason = reserve_reason.label();
        task.artifact = Some(artifact.to_owned());
    }
}

fn atomic_json<T: Serialize>(path: &Path, value: &T) -> Result<()> {
    atomic_bytes(path, &serde_json::to_vec_pretty(value)?)
}

fn atomic_bytes(path: &Path, bytes: &[u8]) -> Result<()> {
    let parent = path
        .parent()
        .ok_or_else(|| anyhow::anyhow!("artifact path has no parent"))?;
    fs::create_dir_all(parent)?;
    let file_name = path
        .file_name()
        .ok_or_else(|| anyhow::anyhow!("artifact path has no file name"))?
        .to_string_lossy();
    let temporary: PathBuf = parent.join(format!(".{file_name}.tmp"));
    let mut file = File::create(&temporary)?;
    file.write_all(bytes)?;
    file.sync_all()?;
    drop(file);
    fs::rename(&temporary, path)?;
    Ok(())
}

fn sha256_file(path: &Path) -> Result<String> {
    let bytes =
        fs::read(path).with_context(|| format!("failed to read artifact {}", path.display()))?;
    Ok(format!("{:x}", Sha256::digest(bytes)))
}

fn csv_quote(value: &str) -> String {
    format!("\"{}\"", value.replace('"', "\"\""))
}

fn timestamp() -> String {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs().to_string())
        .unwrap_or_else(|_| "0".to_owned())
}

fn require_passing_oracles(run_dir: &Path) -> Result<()> {
    let path = run_dir.join("raw/oracles.json");
    let artifact: serde_json::Value = serde_json::from_slice(
        &fs::read(&path)
            .context("production simulation requires approved raw/oracles.json first")?,
    )
    .context("failed to parse required scientific oracles artifact")?;
    if artifact
        .get("required_pass")
        .and_then(|value| value.as_bool())
        != Some(true)
    {
        bail!("production simulation requires all scientific oracles to pass");
    }
    Ok(())
}
