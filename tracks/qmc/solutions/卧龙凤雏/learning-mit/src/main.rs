use anyhow::{bail, Result};
use clap::{Parser, Subcommand};
use learning_mit::config::RunConfig;
use learning_mit::oracles::write_oracle_artifact;
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
        Commands::Benchmark { config, run_dir } | Commands::NegativeControl { config, run_dir } => {
            let _ = (config, run_dir);
            bail!("runner is unavailable before the Gaussian core is validated")
        }
        Commands::Simulate {
            config,
            run_dir,
            task_request,
        } => {
            let _ = (config, run_dir, task_request);
            bail!("runner is unavailable before the Gaussian core is validated")
        }
    }
}
