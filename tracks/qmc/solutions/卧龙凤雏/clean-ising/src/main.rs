use anyhow::{bail, Context, Result};
use clap::{Parser, Subcommand};
use clean_ising::config::RunConfig;
use clean_ising::mc::run_all_chains;
use clean_ising::output::{read_json, sha256_file, write_json_atomic, write_jsonl};
use clean_ising::rng::derive_seed;
use clean_ising::schema::{ExactRecord, RunManifest, SeedRecord, SCHEMA_VERSION};
use clean_ising::transfer::dominant_eigenpair;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

#[derive(Debug, Parser)]
#[command(about = "Clean square-lattice Ising central-charge benchmark")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Debug, Subcommand)]
enum Commands {
    Exact {
        #[arg(long)]
        config: PathBuf,
        #[arg(long)]
        output: PathBuf,
        #[arg(long)]
        manifest: PathBuf,
    },
    Mc {
        #[arg(long)]
        config: PathBuf,
        #[arg(long)]
        output: PathBuf,
        #[arg(long)]
        manifest: PathBuf,
    },
}

fn main() -> Result<()> {
    match Cli::parse().command {
        Commands::Exact {
            config,
            output,
            manifest,
        } => run_exact(&config, &output, &manifest),
        Commands::Mc {
            config,
            output,
            manifest,
        } => run_mc(&config, &output, &manifest),
    }
}

fn run_exact(config_path: &Path, output_path: &Path, manifest_path: &Path) -> Result<()> {
    let config = RunConfig::load(config_path)?;
    config.validate()?;
    let total_start = Instant::now();
    let mut records = Vec::with_capacity(config.widths.len());
    for &l in &config.widths {
        let start = Instant::now();
        let eigen = dominant_eigenpair(l, config.critical_k, &config.exact)?;
        records.push(ExactRecord {
            schema_version: SCHEMA_VERSION,
            l,
            k: config.critical_k,
            boundary_conditions: "periodic-cylinder".to_string(),
            lambda0: eigen.lambda,
            g_exact: -eigen.lambda.ln(),
            iterations: eigen.iterations,
            relative_change: eigen.relative_change,
            residual: eigen.residual,
            elapsed_s: start.elapsed().as_secs_f64(),
        });
        eprintln!(
            "exact L={l} lambda0={:.12e} residual={:.3e} elapsed_s={:.3}",
            eigen.lambda,
            eigen.residual,
            start.elapsed().as_secs_f64()
        );
        std::io::stderr().flush()?;
    }
    write_jsonl(output_path, &records)?;
    let manifest = RunManifest {
        schema_version: SCHEMA_VERSION,
        config,
        config_path: config_path.display().to_string(),
        exact_command: command_contract("exact", config_path, output_path, manifest_path),
        mc_command: String::new(),
        rust_version: rust_version()?,
        cargo_lock_sha256: sha256_file(
            &PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("Cargo.lock"),
        )?,
        python_version: None,
        python_requirements_sha256: None,
        started_at: unix_timestamp()?,
        completed_at: None,
        thread_count: rayon::current_num_threads(),
        seeds: Vec::new(),
        exact_elapsed_s: Some(total_start.elapsed().as_secs_f64()),
        mc_elapsed_s: None,
        total_elapsed_s: None,
    };
    write_json_atomic(manifest_path, &manifest)
}

fn run_mc(config_path: &Path, output_path: &Path, manifest_path: &Path) -> Result<()> {
    let config = RunConfig::load(config_path)?;
    config.validate()?;
    let mut manifest: RunManifest = read_json(manifest_path)?;
    if manifest.schema_version != SCHEMA_VERSION || manifest.config != config {
        bail!("existing manifest does not match the Monte Carlo configuration");
    }

    let start = Instant::now();
    eprintln!(
        "mc starting widths={} grid_points={} replicas={} threads={}",
        config.widths.len(),
        config.mc.grid_intervals + 1,
        config.mc.replicas,
        rayon::current_num_threads()
    );
    std::io::stderr().flush()?;
    let records = run_all_chains(&config)?;
    write_jsonl(output_path, &records)?;
    for &l in &config.widths {
        let blocks = records.iter().filter(|record| record.l == l).count();
        eprintln!(
            "mc L={l} blocks={blocks} elapsed_s={:.3}",
            start.elapsed().as_secs_f64()
        );
        std::io::stderr().flush()?;
    }

    manifest.mc_command = command_contract("mc", config_path, output_path, manifest_path);
    manifest.seeds = seed_table(&config);
    manifest.mc_elapsed_s = Some(start.elapsed().as_secs_f64());
    manifest.completed_at = Some(unix_timestamp()?);
    write_json_atomic(manifest_path, &manifest)
}

fn seed_table(config: &RunConfig) -> Vec<SeedRecord> {
    let mut seeds = Vec::new();
    for &l in &config.widths {
        for k_index in 0..=config.mc.grid_intervals {
            for replica in 0..config.mc.replicas {
                seeds.push(SeedRecord {
                    l,
                    k_index,
                    replica,
                    seed: derive_seed(config.base_seed, l, k_index, replica),
                });
            }
        }
    }
    seeds
}

fn command_contract(subcommand: &str, config: &Path, output: &Path, manifest: &Path) -> String {
    format!(
        "clean-ising {subcommand} --config {} --output {} --manifest {}",
        config.display(),
        output.display(),
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
