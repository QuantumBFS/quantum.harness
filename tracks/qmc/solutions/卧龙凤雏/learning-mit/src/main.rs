use anyhow::Result;
use clap::{Parser, Subcommand};
use learning_mit::circuit::SamplingMode;
use learning_mit::config::RunConfig;
use learning_mit::oracles::write_oracle_artifact;
use learning_mit::runner::{
    run_benchmark, run_negative_control, run_requested_tasks, run_simulation,
};
use std::path::PathBuf;

#[derive(Debug, Parser)]
#[command(about = "Learning-induced Majorana metal-insulator transition")]
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
        run_dir: PathBuf,
    },
    Benchmark {
        #[arg(long)]
        config: PathBuf,
        #[arg(long)]
        run_dir: PathBuf,
    },
    Simulate {
        #[arg(long)]
        config: PathBuf,
        #[arg(long)]
        run_dir: PathBuf,
        #[arg(long)]
        task_request: Option<PathBuf>,
    },
    NegativeControl {
        #[arg(long)]
        config: PathBuf,
        #[arg(long)]
        run_dir: PathBuf,
    },
}

fn main() -> Result<()> {
    match Cli::parse().command {
        Commands::Oracles { config, run_dir } => {
            let config = RunConfig::load(&config)?;
            let artifact = write_oracle_artifact(&config, &run_dir)?;
            println!("scientific oracles passed: {}", artifact.display());
            Ok(())
        }
        Commands::Benchmark { config, run_dir } => {
            let forecast = run_benchmark(&config, &run_dir)?;
            println!(
                "benchmark forecast: {:.3} seconds for configured grid",
                forecast.forecast_seconds
            );
            Ok(())
        }
        Commands::NegativeControl { config, run_dir } => {
            run_negative_control(&config, &run_dir)?;
            println!("nonphysical IID negative control completed");
            Ok(())
        }
        Commands::Simulate {
            config,
            run_dir,
            task_request,
        } => {
            let manifest = if let Some(request) = task_request {
                run_requested_tasks(&config, &run_dir, &request)?
            } else {
                run_simulation(&config, &run_dir, SamplingMode::Born)?
            };
            println!(
                "simulation ledger: {} tasks, {:.3} seconds",
                manifest.tasks.len(),
                manifest.elapsed_s
            );
            Ok(())
        }
    }
}
