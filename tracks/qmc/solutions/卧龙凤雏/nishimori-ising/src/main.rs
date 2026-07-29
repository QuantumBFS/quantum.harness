use anyhow::{bail, Context, Result};
use clap::{Parser, Subcommand};
use clean_ising::config::CRITICAL_K;
use clean_ising::output::{read_json, sha256_file, write_json_atomic};
use nishimori_ising::config::RunConfig;
use nishimori_ising::lyapunov::estimate_replica;
use nishimori_ising::oracles::{clean_transfer_oracle, nishimori_energy_identity};
use nishimori_ising::rng::derive_seed;
use nishimori_ising::schema::{
    OracleArtifact, ReplicaArtifact, RunManifest, SeedRecord, SCHEMA_VERSION,
};
use rayon::prelude::*;
use std::collections::BTreeMap;
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

#[derive(Debug, Parser)]
#[command(about = "Quenched random-bond Ising Nishimori central-charge benchmark")]
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
    let clean_transfer = clean_transfer_oracle(&[4, 6, 8, 10], CRITICAL_K, 512, 128)?;
    let identity_width = config.widths.last().copied().unwrap_or(4).min(6);
    let identity = nishimori_energy_identity(
        identity_width,
        config.antiferromagnetic_probability,
        config.nishimori_k,
        config.disorder.identity_delta_k,
        derive_seed(config.base_seed, 0, 1),
        config.disorder.burn_in_rows,
        config.disorder.identity_rows,
    )?;
    let artifact = OracleArtifact {
        schema_version: SCHEMA_VERSION,
        config: config.clone(),
        clean_transfer,
        nishimori_energy_identity: identity,
        elapsed_s: start.elapsed().as_secs_f64(),
    };
    write_json_atomic(output_path, &artifact)?;

    let mut manifest = load_or_initialize_manifest(config_path, &config, manifest_path)?;
    manifest.commands.push(command_contract_oracles(
        config_path,
        output_path,
        manifest_path,
    ));
    manifest
        .artifact_sha256
        .insert("oracles".to_string(), sha256_file(output_path)?);
    manifest.oracle_elapsed_s = Some(artifact.elapsed_s);
    manifest.updated_at = unix_timestamp()?;
    write_json_atomic(manifest_path, &manifest)?;
    eprintln!(
        "oracles clean_widths=4 identity_L={} identity_error={:.3e} elapsed_s={:.3}",
        identity_width, artifact.nishimori_energy_identity.absolute_error, artifact.elapsed_s
    );
    Ok(())
}

fn run_simulation(config_path: &Path, output_dir: &Path, manifest_path: &Path) -> Result<()> {
    let config = load_config(config_path)?;
    fs::create_dir_all(output_dir)
        .with_context(|| format!("failed to create {}", output_dir.display()))?;
    let start = Instant::now();

    let mut missing = Vec::new();
    for replica in 0..config.disorder.replicas {
        let path = replica_path(output_dir, replica);
        if path.exists() {
            validate_replica_artifact(&path, &config, replica)?;
            eprintln!("reusing replica {replica} from {}", path.display());
        } else {
            missing.push(replica);
        }
    }
    let did_work = !missing.is_empty();
    std::io::stderr().flush()?;

    let results: Vec<Result<usize>> = missing
        .par_iter()
        .map(|&replica| {
            let replica_start = Instant::now();
            let estimate = estimate_replica(&config, replica)?;
            let artifact = ReplicaArtifact {
                schema_version: SCHEMA_VERSION,
                config: config.clone(),
                estimate,
                elapsed_s: replica_start.elapsed().as_secs_f64(),
            };
            let path = replica_path(output_dir, replica);
            write_json_atomic(&path, &artifact)?;
            eprintln!(
                "completed replica {replica} blocks={} elapsed_s={:.3}",
                artifact.estimate.blocks.len(),
                artifact.elapsed_s
            );
            Ok(replica)
        })
        .collect();
    for result in results {
        result?;
    }

    let mut manifest = load_or_initialize_manifest(config_path, &config, manifest_path)?;
    manifest.commands.push(command_contract_simulate(
        config_path,
        output_dir,
        manifest_path,
    ));
    manifest.completed_replicas.clear();
    for replica in 0..config.disorder.replicas {
        let path = replica_path(output_dir, replica);
        validate_replica_artifact(&path, &config, replica)?;
        manifest.completed_replicas.push(replica);
        manifest
            .artifact_sha256
            .insert(format!("replica-{replica:03}"), sha256_file(&path)?);
    }
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

fn validate_replica_artifact(path: &Path, config: &RunConfig, replica: usize) -> Result<()> {
    let artifact: ReplicaArtifact = read_json(path)?;
    if artifact.schema_version != SCHEMA_VERSION
        || !artifact.config.compatible_with(config)
        || artifact.estimate.replica != replica
        || artifact.estimate.seed != derive_seed(config.base_seed, replica, 0)
        || artifact.estimate.widths != config.widths
    {
        bail!(
            "existing replica artifact {} is incompatible with the requested run",
            path.display()
        );
    }
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
                "existing manifest {} is incompatible with the requested run",
                manifest_path.display()
            );
        }
        return Ok(manifest);
    }

    let timestamp = unix_timestamp()?;
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
        seeds: (0..config.disorder.replicas)
            .map(|replica| SeedRecord {
                replica,
                stream: 0,
                seed: derive_seed(config.base_seed, replica, 0),
            })
            .collect(),
        completed_replicas: Vec::new(),
        artifact_sha256: BTreeMap::new(),
        oracle_elapsed_s: None,
        simulation_elapsed_s: None,
        analysis_elapsed_s: None,
        total_elapsed_s: None,
    })
}

fn replica_path(output_dir: &Path, replica: usize) -> PathBuf {
    output_dir.join(format!("replica-{replica:03}.json"))
}

fn command_contract_oracles(config: &Path, output: &Path, manifest: &Path) -> String {
    format!(
        "nishimori-ising oracles --config {} --output {} --manifest {}",
        config.display(),
        output.display(),
        manifest.display()
    )
}

fn command_contract_simulate(config: &Path, output_dir: &Path, manifest: &Path) -> String {
    format!(
        "nishimori-ising simulate --config {} --output-dir {} --manifest {}",
        config.display(),
        output_dir.display(),
        manifest.display()
    )
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
