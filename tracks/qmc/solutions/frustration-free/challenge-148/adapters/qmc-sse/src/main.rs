mod graph;
mod local_lock;
mod request;
mod secure_fs;
mod simulation;
mod storage;

use anyhow::{Result, bail};
use clap::Parser;
use graph::Graph;
use request::Request;
use serde::Serialize;
use std::path::PathBuf;

#[derive(Debug, Parser)]
#[command(name = "qmc-sse")]
struct Arguments {
    #[arg(
        long,
        value_name = "PATH",
        requires = "output_directory",
        conflicts_with_all = ["request_fd", "output_directory_fd"]
    )]
    request: Option<PathBuf>,
    #[arg(
        long,
        value_name = "PATH",
        requires = "request",
        conflicts_with_all = ["request_fd", "output_directory_fd"]
    )]
    output_directory: Option<PathBuf>,
    #[arg(
        long,
        value_name = "FD",
        requires = "output_directory_fd",
        conflicts_with_all = ["request", "output_directory"]
    )]
    request_fd: Option<i32>,
    #[arg(
        long,
        value_name = "FD",
        requires = "request_fd",
        conflicts_with_all = ["request", "output_directory"]
    )]
    output_directory_fd: Option<i32>,
    #[arg(
        long,
        conflicts_with_all = [
            "request",
            "output_directory",
            "request_fd",
            "output_directory_fd"
        ]
    )]
    build_info: bool,
}

#[derive(Serialize)]
struct BuildInfo {
    adapter: &'static str,
    build_hash: &'static str,
    codegen_units: &'static str,
    compiler: &'static str,
    encoded_rustflags: &'static str,
    features: &'static str,
    lto: &'static str,
    panic: &'static str,
    profile: &'static str,
    qmc_revision: &'static str,
    rng: &'static str,
    source_hash: &'static str,
    seed_derivation: &'static str,
    sweep_semantics: &'static str,
    target: &'static str,
}

fn run() -> Result<()> {
    let arguments = Arguments::parse();
    if arguments.build_info {
        let info = BuildInfo {
            adapter: "QMC_SSE",
            build_hash: env!("QMC_SSE_BUILD_HASH"),
            codegen_units: env!("QMC_SSE_CODEGEN_UNITS"),
            compiler: env!("QMC_SSE_COMPILER"),
            encoded_rustflags: env!("QMC_SSE_ENCODED_RUSTFLAGS"),
            features: env!("QMC_SSE_FEATURES"),
            lto: env!("QMC_SSE_LTO"),
            panic: env!("QMC_SSE_PANIC"),
            profile: env!("QMC_SSE_PROFILE"),
            qmc_revision: env!("QMC_SSE_QMC_REVISION"),
            rng: "rand-0.9.5-SmallRng-Xoshiro256PlusPlus",
            source_hash: env!("QMC_SSE_SOURCE_HASH"),
            seed_derivation: "sha256:qmc-sse-seed-v1||u64be",
            sweep_semantics: "one diagonal update followed by cluster_attempts_per_sweep=N cluster-update attempts; QMC_SSE does not expose cluster size",
            target: env!("QMC_SSE_TARGET"),
        };
        println!("{}", serde_json::to_string(&info)?);
        return Ok(());
    }

    match (
        arguments.request,
        arguments.output_directory,
        arguments.request_fd,
        arguments.output_directory_fd,
    ) {
        (Some(request_path), Some(output_directory), None, None) => {
            let request = Request::load(&request_path)?;
            let graph = Graph::load(&request.graph_path, &request.graph_sha256)?;
            storage::publish(&output_directory, &request, &graph)
        }
        (None, None, Some(request_fd), Some(output_directory_fd)) => {
            let request = Request::load_inherited_fd(request_fd)?;
            let graph = Graph::load(&request.graph_path, &request.graph_sha256)?;
            storage::publish_inherited(output_directory_fd, &request, &graph)
        }
        _ => bail!(
            "exactly one launch mode is required: \
             --request PATH --output-directory PATH or \
             --request-fd FD --output-directory-fd FD"
        ),
    }
}

fn main() {
    if let Err(error) = run() {
        eprintln!("qmc-sse: {error:#}");
        std::process::exit(2);
    }
}
