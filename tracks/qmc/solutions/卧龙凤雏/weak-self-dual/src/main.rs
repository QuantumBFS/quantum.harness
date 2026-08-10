use anyhow::{bail, Context, Result};
use clap::{Parser, Subcommand};
use rayon::prelude::*;
use serde::de::DeserializeOwned;
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::fs;
use std::fs::File;
use std::io::{BufReader, BufWriter, Read, Write};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{Instant, SystemTime, UNIX_EPOCH};
use weak_self_dual::config::RunConfig;
use weak_self_dual::oracles::{
    clean_positive_trajectory, compare_covariance_to_dense, compare_gauge_equivalent_trajectories,
};
use weak_self_dual::rng::derive_seed;
use weak_self_dual::sampler::estimate_stream;
use weak_self_dual::schema::{
    OracleArtifact, RunManifest, SeedRecord, StreamArtifact, SCHEMA_VERSION,
};

#[derive(Debug, Parser)]
#[command(about = "Born-correlated weak self-dual central-charge benchmark")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Debug, Subcommand)]
enum Commands {
    Oracles {
        #[arg(long)]
        config: PathBuf,
        #[arg(long)]
        output: PathBuf,
        #[arg(long)]
        manifest: PathBuf,
    },
    Simulate {
        #[arg(long)]
        config: PathBuf,
        #[arg(long)]
        output_dir: PathBuf,
        #[arg(long)]
        manifest: PathBuf,
    },
}

fn main() -> Result<()> {
    match Cli::parse().command {
        Commands::Oracles {
            config,
            output,
            manifest,
        } => run_oracles(&config, &output, &manifest),
        Commands::Simulate {
            config,
            output_dir,
            manifest,
        } => run_simulation(&config, &output_dir, &manifest),
    }
}

fn run_oracles(config_path: &Path, output_path: &Path, manifest_path: &Path) -> Result<()> {
    let config = load_config(config_path)?;
    let start = Instant::now();
    let artifact = OracleArtifact {
        schema_version: SCHEMA_VERSION,
        config: config.clone(),
        born_enumeration: compare_covariance_to_dense(2, 2, config.beta)?,
        gauge_equivalence: compare_gauge_equivalent_trajectories(2, 2, config.beta)?,
        clean_positive: clean_positive_trajectory(2, 2, config.beta)?,
        elapsed_s: start.elapsed().as_secs_f64(),
    };
    write_json_atomic(output_path, &artifact)?;
    let mut manifest = load_or_initialize_manifest(config_path, &config, manifest_path)?;
    manifest.commands.push(format!(
        "weak-self-dual oracles --config {} --output {} --manifest {}",
        config_path.display(),
        output_path.display(),
        manifest_path.display()
    ));
    manifest
        .artifact_sha256
        .insert("oracles".to_string(), sha256_file(output_path)?);
    manifest.oracle_elapsed_s = Some(artifact.elapsed_s);
    manifest.updated_at = unix_timestamp()?;
    write_json_atomic(manifest_path, &manifest)?;
    eprintln!(
        "oracles trajectories={} probability_error={:.3e} covariance_error={:.3e}",
        artifact.born_enumeration.trajectories,
        artifact.born_enumeration.max_probability_error,
        artifact.born_enumeration.max_covariance_error
    );
    Ok(())
}

fn run_simulation(config_path: &Path, output_dir: &Path, manifest_path: &Path) -> Result<()> {
    let config = load_config(config_path)?;
    let streams_dir = output_dir.join("streams");
    fs::create_dir_all(&streams_dir)
        .with_context(|| format!("failed to create {}", streams_dir.display()))?;
    let start = Instant::now();
    let jobs: Vec<(usize, usize)> = config
        .widths
        .iter()
        .flat_map(|&width| {
            (0..config.sampling.streams_per_width).map(move |stream| (width, stream))
        })
        .collect();
    let mut missing = Vec::new();
    for &(width, stream) in &jobs {
        let path = stream_path(&streams_dir, width, stream);
        if path.exists() {
            validate_stream_artifact(&path, &config, width, stream).with_context(|| {
                format!(
                    "existing stream artifact {} is incompatible",
                    path.display()
                )
            })?;
            eprintln!(
                "reusing width={width} stream={stream} from {}",
                path.display()
            );
        } else {
            missing.push((width, stream));
        }
    }
    std::io::stderr().flush()?;
    let did_work = !missing.is_empty();
    let results: Vec<Result<()>> = missing
        .par_iter()
        .map(|&(width, stream)| {
            let stream_start = Instant::now();
            let estimate = estimate_stream(&config, width, stream)?;
            let artifact = StreamArtifact {
                schema_version: SCHEMA_VERSION,
                config: config.clone(),
                estimate,
                elapsed_s: stream_start.elapsed().as_secs_f64(),
            };
            let path = stream_path(&streams_dir, width, stream);
            write_json_atomic(&path, &artifact)?;
            eprintln!(
                "completed width={width} stream={stream} blocks={} elapsed_s={:.3}",
                artifact.estimate.blocks.len(),
                artifact.elapsed_s
            );
            Ok(())
        })
        .collect();
    for result in results {
        result?;
    }

    let mut manifest = load_or_initialize_manifest(config_path, &config, manifest_path)?;
    manifest.commands.push(format!(
        "weak-self-dual simulate --config {} --output-dir {} --manifest {}",
        config_path.display(),
        output_dir.display(),
        manifest_path.display()
    ));
    manifest.completed_streams.clear();
    for &(width, stream) in &jobs {
        let path = stream_path(&streams_dir, width, stream);
        validate_stream_artifact(&path, &config, width, stream)?;
        let key = stream_key(width, stream);
        manifest.completed_streams.push(key.clone());
        manifest.artifact_sha256.insert(key, sha256_file(&path)?);
    }
    let blocks_path = output_dir.join("blocks.csv");
    write_blocks_csv(&blocks_path, &streams_dir, &config, &jobs)?;
    manifest
        .artifact_sha256
        .insert("raw-blocks-csv".to_string(), sha256_file(&blocks_path)?);
    if did_work {
        manifest.simulation_elapsed_s =
            Some(manifest.simulation_elapsed_s.unwrap_or(0.0) + start.elapsed().as_secs_f64());
    }
    manifest.updated_at = unix_timestamp()?;
    manifest.completed_at = Some(manifest.updated_at.clone());
    write_json_atomic(manifest_path, &manifest)?;
    Ok(())
}

fn load_config(path: &Path) -> Result<RunConfig> {
    let config = RunConfig::load(path)?;
    config.validate()?;
    Ok(config)
}

fn validate_stream_artifact(
    path: &Path,
    config: &RunConfig,
    width: usize,
    stream: usize,
) -> Result<StreamArtifact> {
    let artifact: StreamArtifact = read_json(path)?;
    if artifact.schema_version != SCHEMA_VERSION
        || !artifact.config.compatible_with(config)
        || artifact.estimate.width != width
        || artifact.estimate.stream != stream
        || artifact.estimate.seed != derive_seed(config.base_seed, width, stream, 0)
    {
        bail!("stream artifact metadata does not match the requested run");
    }
    Ok(artifact)
}

fn write_blocks_csv(
    path: &Path,
    streams_dir: &Path,
    config: &RunConfig,
    jobs: &[(usize, usize)],
) -> Result<()> {
    let temporary = temporary_path(path);
    let file = File::create(&temporary)
        .with_context(|| format!("failed to create {}", temporary.display()))?;
    let mut writer = BufWriter::new(file);
    writeln!(
        writer,
        "width,stream,seed,block_index,gamma,electric_count,magnetic_count,\
         faces_per_species,min_probability,max_invariant_error"
    )?;
    for &(width, stream) in jobs {
        let artifact = validate_stream_artifact(
            &stream_path(streams_dir, width, stream),
            config,
            width,
            stream,
        )?;
        for block in artifact.estimate.blocks {
            writeln!(
                writer,
                "{width},{stream},{},{},{:.17},{},{},{},{:.17},{:.17}",
                artifact.estimate.seed,
                block.block_index,
                block.gamma,
                block.electric_count,
                block.magnetic_count,
                block.faces_per_species,
                block.min_probability,
                block.max_invariant_error
            )?;
        }
    }
    writer.flush()?;
    writer.get_ref().sync_all()?;
    fs::rename(&temporary, path)
        .with_context(|| format!("failed to replace {}", path.display()))?;
    Ok(())
}

fn load_or_initialize_manifest(
    config_path: &Path,
    config: &RunConfig,
    manifest_path: &Path,
) -> Result<RunManifest> {
    if manifest_path.exists() {
        let manifest: RunManifest = read_json(manifest_path)?;
        if manifest.schema_version != SCHEMA_VERSION || !manifest.config.compatible_with(config) {
            bail!(
                "existing manifest {} is incompatible",
                manifest_path.display()
            );
        }
        return Ok(manifest);
    }
    let timestamp = unix_timestamp()?;
    let mut seeds = Vec::new();
    for &width in &config.widths {
        for stream in 0..config.sampling.streams_per_width {
            seeds.push(SeedRecord {
                width,
                stream,
                purpose: 0,
                seed: derive_seed(config.base_seed, width, stream, 0),
            });
        }
    }
    Ok(RunManifest {
        schema_version: SCHEMA_VERSION,
        config: config.clone(),
        config_path: config_path.display().to_string(),
        commands: Vec::new(),
        rust_version: rust_version()?,
        cargo_lock_sha256: sha256_file(
            &PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("Cargo.lock"),
        )?,
        python_version: None,
        python_requirements_sha256: None,
        started_at: timestamp.clone(),
        updated_at: timestamp,
        completed_at: None,
        thread_count: rayon::current_num_threads(),
        seeds,
        completed_streams: Vec::new(),
        artifact_sha256: BTreeMap::new(),
        oracle_elapsed_s: None,
        simulation_elapsed_s: None,
        analysis_elapsed_s: None,
        total_elapsed_s: None,
    })
}

fn stream_key(width: usize, stream: usize) -> String {
    format!("stream-L{width:02}-{stream:03}")
}

fn stream_path(streams_dir: &Path, width: usize, stream: usize) -> PathBuf {
    streams_dir.join(format!("{}.json", stream_key(width, stream)))
}

fn read_json<T: DeserializeOwned>(path: &Path) -> Result<T> {
    let file = File::open(path).with_context(|| format!("failed to open {}", path.display()))?;
    serde_json::from_reader(BufReader::new(file))
        .with_context(|| format!("failed to parse JSON {}", path.display()))
}

fn write_json_atomic<T: Serialize>(path: &Path, value: &T) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("failed to create {}", parent.display()))?;
    }
    let temporary = temporary_path(path);
    let file = File::create(&temporary)
        .with_context(|| format!("failed to create {}", temporary.display()))?;
    let mut writer = BufWriter::new(file);
    serde_json::to_writer_pretty(&mut writer, value)?;
    writer.write_all(b"\n")?;
    writer.flush()?;
    writer.get_ref().sync_all()?;
    fs::rename(&temporary, path)
        .with_context(|| format!("failed to replace {}", path.display()))?;
    Ok(())
}

fn temporary_path(path: &Path) -> PathBuf {
    let mut name = path.as_os_str().to_os_string();
    name.push(".tmp");
    PathBuf::from(name)
}

fn sha256_file(path: &Path) -> Result<String> {
    let mut file =
        File::open(path).with_context(|| format!("failed to open {}", path.display()))?;
    let mut hasher = Sha256::new();
    let mut buffer = [0_u8; 64 * 1024];
    loop {
        let count = file.read(&mut buffer)?;
        if count == 0 {
            break;
        }
        hasher.update(&buffer[..count]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

fn rust_version() -> Result<String> {
    let output = Command::new("rustc")
        .arg("--version")
        .output()
        .context("failed to execute rustc --version")?;
    if !output.status.success() {
        bail!("rustc --version exited with {}", output.status);
    }
    Ok(String::from_utf8(output.stdout)?.trim().to_string())
}

fn unix_timestamp() -> Result<String> {
    let seconds = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .context("system clock is before the Unix epoch")?
        .as_secs();
    Ok(format!("unix:{seconds}"))
}
