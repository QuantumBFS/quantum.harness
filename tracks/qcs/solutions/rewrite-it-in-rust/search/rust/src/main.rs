use std::{
    fs,
    path::PathBuf,
    time::{Duration, Instant},
};

use clap::{Parser, Subcommand, ValueEnum};
use occam71_rust::{
    ArithmeticOperation, BenchmarkBackend, DEFAULT_LIMITS, LearnRequest, OccamError,
    SynthesisLimits, SynthesisProblem, SynthesisStatus, generate_dataset, learn_instance,
    load_written_instance, pack_dataset, parse_dataset, parse_netlist, parse_packed_dataset,
    ripple_carry_adder, run_benchmark, shift_add_multiplier, synthesize_minimal, verify,
    verify_prepacked, write_instance_artifacts, write_manifest,
};

#[derive(Debug, Parser)]
#[command(name = "occam71-rust", about = "Rust verifier for #71 Occam's Circuit")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// Verify a circuit against an input/output dataset.
    Verify {
        #[arg(long)]
        dataset: PathBuf,
        #[arg(long)]
        circuit: PathBuf,
        #[arg(long, value_enum, default_value_t = Backend::CrossCheck)]
        backend: Backend,
    },
    /// Generate a format-compatible ripple-carry adder.
    GenerateAdder {
        #[arg(long, value_parser = parse_positive_bits)]
        bits: usize,
        #[arg(long)]
        output: Option<PathBuf>,
    },
    /// Generate a format-compatible shift-and-add multiplier.
    GenerateMultiplier {
        #[arg(long, value_parser = parse_positive_bits)]
        bits: usize,
        #[arg(long)]
        output: Option<PathBuf>,
    },
    /// Generate a deterministic disclosed arithmetic dataset.
    GenerateDataset {
        #[arg(long, value_enum)]
        operation: DatasetOperation,
        #[arg(long, value_parser = parse_dataset_bits)]
        bits: usize,
        #[arg(long, value_parser = parse_positive_usize)]
        samples: usize,
        #[arg(long)]
        seed: u64,
        #[arg(long)]
        output: Option<PathBuf>,
    },
    /// Benchmark one verification backend after parsing the input files.
    Benchmark {
        #[arg(long, value_enum)]
        backend: BenchmarkBackendArgument,
        #[arg(long)]
        dataset: PathBuf,
        #[arg(long)]
        circuit: PathBuf,
        #[arg(long, default_value_t = 5)]
        warmup: usize,
        #[arg(long, value_parser = parse_positive_usize, default_value_t = 30)]
        iterations: usize,
        #[arg(long, value_parser = parse_positive_usize, default_value_t = 5)]
        batches: usize,
        #[arg(long)]
        json: PathBuf,
    },
    /// Exactly synthesize a smallest bounded circuit from a complete truth table.
    Synthesize {
        #[arg(long)]
        dataset: PathBuf,
        #[arg(long)]
        max_gates: usize,
        #[arg(long, default_value_t = 60)]
        timeout_seconds: u64,
        #[arg(long)]
        output: PathBuf,
        #[arg(long)]
        certificate: PathBuf,
    },
    /// Learn one hidden arithmetic family and write validated submission artifacts.
    Learn {
        #[arg(long)]
        instance: String,
        #[arg(long)]
        train: PathBuf,
        #[arg(long)]
        test_inputs: PathBuf,
        #[arg(long)]
        commitment: PathBuf,
        #[arg(long)]
        output_dir: PathBuf,
    },
    /// Recompute and write the aggregate A-D solution manifest.
    WriteManifest {
        #[arg(long)]
        output_dir: PathBuf,
    },
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, ValueEnum)]
enum Backend {
    Scalar,
    Packed,
    PackedLegacy,
    CrossCheck,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, ValueEnum)]
enum DatasetOperation {
    Add,
    Multiply,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, ValueEnum)]
enum BenchmarkBackendArgument {
    Scalar,
    Packed,
    PackedReference,
    PackedInterpreted,
    Compiled,
}

impl From<BenchmarkBackendArgument> for BenchmarkBackend {
    fn from(value: BenchmarkBackendArgument) -> Self {
        match value {
            BenchmarkBackendArgument::Scalar => Self::Scalar,
            BenchmarkBackendArgument::Packed => Self::Packed,
            BenchmarkBackendArgument::PackedReference => Self::PackedReference,
            BenchmarkBackendArgument::PackedInterpreted => Self::PackedInterpreted,
            BenchmarkBackendArgument::Compiled => Self::Compiled,
        }
    }
}

impl From<DatasetOperation> for ArithmeticOperation {
    fn from(value: DatasetOperation) -> Self {
        match value {
            DatasetOperation::Add => Self::Add,
            DatasetOperation::Multiply => Self::Multiply,
        }
    }
}

impl Backend {
    fn label(self) -> &'static str {
        match self {
            Self::Scalar => "scalar",
            Self::Packed => "packed",
            Self::PackedLegacy => "packed-legacy",
            Self::CrossCheck => "cross-check",
        }
    }
}

fn parse_positive_bits(value: &str) -> Result<usize, String> {
    parse_positive_usize(value)
}

fn parse_dataset_bits(value: &str) -> Result<usize, String> {
    let bits = parse_positive_usize(value)?;
    if bits > 32 {
        return Err("dataset bit width must not exceed 32".into());
    }
    Ok(bits)
}

fn parse_positive_usize(value: &str) -> Result<usize, String> {
    let bits = value
        .parse::<usize>()
        .map_err(|_| format!("{value:?} is not a positive integer"))?;
    if bits == 0 {
        return Err("bit width must be at least 1".into());
    }
    Ok(bits)
}

fn read(path: &PathBuf) -> Result<String, OccamError> {
    let metadata = fs::metadata(path).map_err(|source| OccamError::ReadFile {
        path: path.clone(),
        source,
    })?;
    if metadata.len() > DEFAULT_LIMITS.max_source_bytes as u64 {
        return Err(OccamError::ResourceLimit {
            resource: "input file bytes",
            requested: usize::try_from(metadata.len()).unwrap_or(usize::MAX),
            limit: DEFAULT_LIMITS.max_source_bytes,
        });
    }
    fs::read_to_string(path).map_err(|source| OccamError::ReadFile {
        path: path.clone(),
        source,
    })
}

fn run() -> Result<(), OccamError> {
    match Cli::parse().command {
        Command::Verify {
            dataset,
            circuit,
            backend,
        } => {
            let circuit = parse_netlist(&read(&circuit)?)?;
            let dataset_source = read(&dataset)?;
            let metrics = match backend {
                Backend::Scalar => verify(&circuit, &parse_dataset(&dataset_source)?)?,
                Backend::Packed => {
                    verify_prepacked(&circuit, &parse_packed_dataset(&dataset_source)?)?
                }
                Backend::PackedLegacy => {
                    let scalar_dataset = parse_dataset(&dataset_source)?;
                    verify_prepacked(&circuit, &pack_dataset(&scalar_dataset)?)?
                }
                Backend::CrossCheck => {
                    let scalar = verify(&circuit, &parse_dataset(&dataset_source)?)?;
                    let packed =
                        verify_prepacked(&circuit, &parse_packed_dataset(&dataset_source)?)?;
                    if scalar != packed {
                        return Err(OccamError::Validation(format!(
                            "backend mismatch: scalar {scalar:?}, packed {packed:?}"
                        )));
                    }
                    scalar
                }
            };
            println!("backend:          {}", backend.label());
            println!("gates:            {}", metrics.gate_count);
            println!("samples:          {}", metrics.samples);
            println!("exact matches:    {}", metrics.exact_matches);
            println!("exact-match acc:  {:.6}", metrics.exact_match_accuracy());
            println!("correct bits:     {}", metrics.correct_bits);
            println!("total bits:       {}", metrics.total_bits);
            println!("bit accuracy:     {:.6}", metrics.bit_accuracy());
        }
        Command::GenerateAdder { bits, output } => {
            write_generated(ripple_carry_adder(bits)?, output)?;
        }
        Command::GenerateMultiplier { bits, output } => {
            write_generated(shift_add_multiplier(bits)?, output)?;
        }
        Command::GenerateDataset {
            operation,
            bits,
            samples,
            seed,
            output,
        } => {
            write_generated(
                generate_dataset(operation.into(), bits, samples, seed)?,
                output,
            )?;
        }
        Command::Benchmark {
            backend,
            dataset,
            circuit,
            warmup,
            iterations,
            batches,
            json,
        } => {
            let parse_started = Instant::now();
            let parsed_circuit = parse_netlist(&read(&circuit)?)?;
            let circuit_parse_duration = parse_started.elapsed();
            let dataset_source = read(&dataset)?;
            let report = run_benchmark(
                backend.into(),
                &parsed_circuit,
                &dataset_source,
                warmup,
                iterations,
                batches,
                circuit_parse_duration,
                circuit.display().to_string(),
                dataset.display().to_string(),
            )?;
            let encoded = serde_json::to_string_pretty(&report).map_err(|error| {
                OccamError::Validation(format!("JSON encoding failed: {error}"))
            })?;
            fs::write(&json, format!("{encoded}\n")).map_err(|source| OccamError::WriteFile {
                path: json.clone(),
                source,
            })?;
            print_benchmark_summary(&report);
            println!("json:             {}", json.display());
        }
        Command::Synthesize {
            dataset,
            max_gates,
            timeout_seconds,
            output,
            certificate,
        } => {
            let parsed_dataset = parse_dataset(&read(&dataset)?)?;
            let limits = SynthesisLimits {
                max_gates,
                timeout: Duration::from_secs(timeout_seconds),
                ..SynthesisLimits::default()
            };
            let problem = SynthesisProblem::from_dataset_with_limits(&parsed_dataset, &limits)?;
            let result = synthesize_minimal(&problem, &limits)?;
            write_text(&certificate, &result.to_json_pretty()?)?;
            if let Some(netlist) = &result.netlist {
                write_text(&output, netlist)?;
            }
            println!("status:           {}", synthesis_status_name(result.status));
            println!("attempts:         {}", result.attempts.len());
            if let Some(gates) = result.minimal_gate_count {
                println!("minimal gates:    {gates}");
                println!("netlist:          {}", output.display());
            } else {
                println!("detail:           {}", result.status_detail);
            }
            println!("certificate:      {}", certificate.display());
        }
        Command::Learn {
            instance,
            train,
            test_inputs,
            commitment,
            output_dir,
        } => {
            let training_source = read(&train)?;
            let test_inputs_source = read(&test_inputs)?;
            let commitment_source = read(&commitment)?;
            let result = learn_instance(LearnRequest {
                instance: &instance,
                training_source: &training_source,
                test_inputs_source: &test_inputs_source,
                commitment_source: Some(&commitment_source),
                limits: &DEFAULT_LIMITS,
            })?;
            let written = write_instance_artifacts(&output_dir, &instance, &result)?;
            println!("instance:         {instance}");
            println!("selected family:  {}", result.report.selected_family);
            println!("gates:            {}", result.report.gate_count);
            println!(
                "training scalar:  {}/{}",
                result.report.training_scalar.exact_matches, result.report.training_scalar.samples
            );
            println!(
                "training packed:  {}/{}",
                result.report.training_packed.exact_matches, result.report.training_packed.samples
            );
            println!(
                "exhaustive:       {}/{}",
                result.report.exhaustive_cases - result.report.exhaustive_mismatches,
                result.report.exhaustive_cases
            );
            println!("prediction rows:  {}", result.report.prediction_rows);
            println!("prediction SHA:   {}", result.report.prediction_sha256);
            println!("commitment:       match");
            println!("circuit:          {}", written.circuit_path.display());
            println!("predictions:      {}", written.prediction_path.display());
            println!("report:           {}", written.report_path.display());
        }
        Command::WriteManifest { output_dir } => {
            let instances = ["mystery-A", "mystery-B", "mystery-C", "mystery-D"]
                .into_iter()
                .map(|instance| load_written_instance(&output_dir, instance, &DEFAULT_LIMITS))
                .collect::<Result<Vec<_>, _>>()?;
            let path = write_manifest(&output_dir, &instances)?;
            println!("instances:        {}", instances.len());
            println!("manifest:         {}", path.display());
        }
    }
    Ok(())
}

fn synthesis_status_name(status: SynthesisStatus) -> &'static str {
    match status {
        SynthesisStatus::Sat => "sat",
        SynthesisStatus::NoCircuitWithinBound => "no-circuit-within-bound",
        SynthesisStatus::Timeout => "timeout",
        SynthesisStatus::ResourceLimit => "resource-limit",
    }
}

fn print_benchmark_summary(report: &occam71_rust::BenchmarkReport) {
    println!("backend:          {}", report.backend);
    println!("samples:          {}", report.samples);
    println!("gates:            {}", report.gates);
    println!("parse:            {:.3} ms", report.parse_ns as f64 / 1e6);
    if let Some(packing_ns) = report.packing_ns {
        println!("packing:          {:.3} ms", packing_ns as f64 / 1e6);
    }
    println!(
        "median evaluate:  {:.3} ms",
        report.evaluation.median_ns as f64 / 1e6
    );
    println!(
        "one-shot:         {:.3} ms",
        report.one_shot_ns as f64 / 1e6
    );
    println!(
        "samples/s:        {:.3}",
        report.samples_per_second_at_median
    );
}

fn write_generated(netlist: String, output: Option<PathBuf>) -> Result<(), OccamError> {
    if let Some(path) = output {
        fs::write(&path, netlist).map_err(|source| OccamError::WriteFile { path, source })?;
    } else {
        print!("{netlist}");
    }
    Ok(())
}

fn write_text(path: &PathBuf, contents: &str) -> Result<(), OccamError> {
    fs::write(path, contents).map_err(|source| OccamError::WriteFile {
        path: path.clone(),
        source,
    })
}

fn main() {
    if let Err(error) = run() {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
