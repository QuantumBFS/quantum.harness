use std::{
    fs::{self, File},
    io::Write,
    path::{Path, PathBuf},
    time::{Duration, Instant},
};

use clap::{Parser, Subcommand, ValueEnum};
use occam71_rust::{
    AbcOptimizationConfig, AbcPortfolioReport, ArithmeticOperation, BenchmarkBackend,
    DEFAULT_LIMITS, LearnRequest, MdlLearnRequest, MdlSearchConfig, OccamError, PeepholeConfig,
    PeepholeOptimizationReport, SynthesisLimits, SynthesisProblem, SynthesisStatus, TrialKey,
    WindowConfig, compare_circuits_exhaustively, generate_dataset, learn_instance, learn_mdl,
    load_written_instance, optimize_peepholes, optimize_with_abc, pack_dataset, parse_dataset,
    parse_netlist, parse_packed_dataset, render_semantic_jsonl, ripple_carry_adder, run_benchmark,
    run_isolated_experiment, run_measured_trial, sha256_hex, shift_add_multiplier,
    synthesize_minimal, verify, verify_prepacked, write_instance_artifacts, write_manifest,
    write_semantic_jsonl,
};
use serde::Serialize;

#[derive(Debug, Parser)]
#[command(
    name = "occam71-rust",
    version,
    about = "Rust verifier for #71 Occam's Circuit"
)]
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
    /// Learn a minimum-description expression and write its verified artifacts.
    LearnMdl {
        #[arg(long)]
        train: PathBuf,
        #[arg(long)]
        test_inputs: PathBuf,
        #[arg(long)]
        commitment: Option<PathBuf>,
        #[arg(long, value_parser = parse_positive_usize, default_value_t = 8)]
        max_description_cost: usize,
        #[arg(long, value_parser = parse_positive_u64, default_value_t = 30)]
        timeout_seconds: u64,
        #[arg(long)]
        circuit: PathBuf,
        #[arg(long)]
        predictions: PathBuf,
        #[arg(long)]
        report: PathBuf,
    },
    /// Optimize one official circuit with the pinned ABC portfolio.
    OptimizeCircuit {
        #[arg(long)]
        circuit: PathBuf,
        #[arg(long)]
        abc: PathBuf,
        #[arg(long)]
        output: PathBuf,
        #[arg(long)]
        report: PathBuf,
        #[arg(long, default_value_t = false)]
        abc_only: bool,
    },
    /// Run exactly one measured Occam research trial.
    ExperimentTrial {
        #[arg(long)]
        config: PathBuf,
        #[arg(long)]
        tasks: PathBuf,
        #[arg(long)]
        key_json: String,
        #[arg(long)]
        output: PathBuf,
        #[arg(long)]
        abc: Option<PathBuf>,
    },
    /// Run the complete isolated Occam generalization matrix.
    ExperimentRun {
        #[arg(long)]
        config: PathBuf,
        #[arg(long)]
        tasks: PathBuf,
        #[arg(long = "raw-measured", alias = "raw")]
        raw_measured: PathBuf,
        #[arg(long)]
        semantic: Option<PathBuf>,
        #[arg(long)]
        abc: Option<PathBuf>,
        #[arg(long, value_parser = parse_positive_usize, default_value_t = 1)]
        jobs: usize,
        #[arg(long = "check-semantic", alias = "check", default_value_t = false)]
        check_semantic: bool,
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

fn parse_positive_u64(value: &str) -> Result<u64, String> {
    let parsed = value
        .parse::<u64>()
        .map_err(|_| format!("{value:?} is not a positive integer"))?;
    if parsed == 0 {
        return Err("value must be at least 1".into());
    }
    Ok(parsed)
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
        Command::LearnMdl {
            train,
            test_inputs,
            commitment,
            max_description_cost,
            timeout_seconds,
            circuit,
            predictions,
            report,
        } => {
            let training_source = read(&train)?;
            let test_inputs_source = read(&test_inputs)?;
            let commitment_source = commitment.as_ref().map(read).transpose()?;
            let timeout_millis =
                timeout_seconds
                    .checked_mul(1_000)
                    .ok_or(OccamError::ArithmeticOverflow {
                        context: "MDL CLI timeout milliseconds",
                    })?;
            let config = MdlSearchConfig {
                max_description_cost,
                timeout_millis,
                ..MdlSearchConfig::default()
            };
            let result = learn_mdl(MdlLearnRequest {
                training_source: &training_source,
                test_inputs_source: &test_inputs_source,
                commitment_source: commitment_source.as_deref(),
                config: &config,
                limits: &DEFAULT_LIMITS,
            })?;
            let report_json = result.report.to_json_pretty()?;
            write_atomic_bundle([
                (&circuit, result.circuit.as_str()),
                (&predictions, result.prediction_csv.as_str()),
                (&report, report_json.as_str()),
            ])?;
            println!("expression:        {}", result.report.expression);
            println!("description cost:  {}", result.report.description_cost);
            println!("gates:             {}", result.report.gate_count);
            println!(
                "training scalar:   {}/{}",
                result.report.training_scalar.exact_matches, result.report.training_scalar.samples
            );
            println!(
                "training packed:   {}/{}",
                result.report.training_packed.exact_matches, result.report.training_packed.samples
            );
            println!(
                "exhaustive:        {}/{}",
                result.report.exhaustive_cases - result.report.exhaustive_mismatches,
                result.report.exhaustive_cases
            );
            println!("prediction rows:   {}", result.report.prediction_rows);
            println!("prediction SHA:    {}", result.report.prediction_sha256);
            println!(
                "commitment:       {}",
                if result.report.commitment_matches == Some(true) {
                    "match"
                } else {
                    "not supplied"
                }
            );
            println!("circuit:           {}", circuit.display());
            println!("predictions:       {}", predictions.display());
            println!("report:            {}", report.display());
        }
        Command::OptimizeCircuit {
            circuit,
            abc,
            output,
            report,
            abc_only,
        } => {
            let parsed = parse_netlist(&read(&circuit)?)?;
            let abc_result = optimize_with_abc(
                &parsed,
                &abc,
                &AbcOptimizationConfig::default(),
                &DEFAULT_LIMITS,
            )?;
            if abc_only {
                write_text(&report, &abc_result.report.to_json_pretty()?)?;
                let best = abc_result.best_candidate();
                let improved = best
                    .is_some_and(|candidate| candidate.official_gate_count < parsed.gates.len());
                let status = if improved {
                    let candidate = best.unwrap();
                    write_text(&output, &candidate.netlist)?;
                    "improved"
                } else if best.is_some() {
                    "unchanged"
                } else {
                    "failed"
                };
                print_optimization_summary(
                    status,
                    parsed.gates.len(),
                    best.map(|candidate| candidate.official_gate_count),
                    best.map(|candidate| candidate.flow_name.as_str()),
                    &report,
                );
                return Ok(());
            }

            let peephole_config = PeepholeConfig {
                window: WindowConfig {
                    min_gates: 3,
                    max_gates: 3,
                    max_inputs: 4,
                    max_outputs: 2,
                },
                per_window_timeout: Duration::from_secs(5),
                global_timeout: Duration::from_secs(60),
                max_attempts: 64,
                max_exhaustive_inputs: 20,
            };
            let original_peephole = optimize_peepholes(&parsed, &peephole_config, &DEFAULT_LIMITS)?;
            let abc_circuit = abc_result
                .best_candidate()
                .map(|candidate| parse_netlist(&candidate.netlist))
                .transpose()?
                .unwrap_or_else(|| parsed.clone());
            let abc_peephole = optimize_peepholes(&abc_circuit, &peephole_config, &DEFAULT_LIMITS)?;

            let original_source = read(&circuit)?;
            let mut choices = vec![
                (
                    "baseline",
                    parsed.gates.len(),
                    original_source,
                    parsed.clone(),
                ),
                (
                    "peephole-baseline",
                    original_peephole.circuit.gates.len(),
                    original_peephole.netlist.clone(),
                    original_peephole.circuit.clone(),
                ),
                (
                    "peephole-abc",
                    abc_peephole.circuit.gates.len(),
                    abc_peephole.netlist.clone(),
                    abc_peephole.circuit.clone(),
                ),
            ];
            if let Some(candidate) = abc_result.best_candidate() {
                choices.push((
                    "abc",
                    candidate.official_gate_count,
                    candidate.netlist.clone(),
                    abc_circuit,
                ));
            }
            choices.sort_by(|lhs, rhs| (lhs.1, lhs.0).cmp(&(rhs.1, rhs.0)));
            let (selected_source, selected_gates, selected_netlist, selected_circuit) =
                choices.remove(0);
            let (cases, mismatches) =
                compare_circuits_exhaustively(&parsed, &selected_circuit, 20, &DEFAULT_LIMITS)?;
            if selected_gates > parsed.gates.len() || mismatches != 0 {
                return Err(OccamError::Validation(format!(
                    "combined optimization selected {selected_gates} gates with {mismatches} mismatches"
                )));
            }
            write_text(&output, &selected_netlist)?;
            let combined = CombinedOptimizationReport {
                schema_version: 1,
                baseline_gate_count: parsed.gates.len(),
                abc: abc_result.report,
                peephole_baseline: original_peephole.report,
                peephole_abc: abc_peephole.report,
                selected_source: selected_source.into(),
                selected_gate_count: selected_gates,
                selected_circuit_sha256: sha256_hex(selected_netlist.as_bytes()),
                exhaustive_cases: cases,
                exhaustive_mismatches: mismatches,
            };
            let report_json = serde_json::to_string_pretty(&combined)
                .map(|encoded| format!("{encoded}\n"))
                .map_err(|error| {
                    OccamError::Validation(format!("JSON encoding failed: {error}"))
                })?;
            write_text(&report, &report_json)?;
            let status = if selected_gates < parsed.gates.len() {
                "improved"
            } else {
                "unchanged"
            };
            print_optimization_summary(
                status,
                parsed.gates.len(),
                Some(selected_gates),
                Some(selected_source),
                &report,
            );
        }
        Command::ExperimentTrial {
            config,
            tasks,
            key_json,
            output,
            abc,
        } => {
            let key: TrialKey = serde_json::from_str(&key_json).map_err(|error| {
                OccamError::Validation(format!("invalid trial key JSON: {error}"))
            })?;
            let record = run_measured_trial(&config, &tasks, key, &output, abc)?;
            println!("status:           {:?}", record.status);
            println!("runtime micros:   {}", record.runtime_micros);
            println!("peak RSS bytes:   {}", record.peak_rss_bytes);
            println!("record:           {}", output.display());
        }
        Command::ExperimentRun {
            config,
            tasks,
            raw_measured,
            semantic,
            abc,
            jobs,
            check_semantic,
        } => {
            if check_semantic && semantic.is_none() {
                return Err(OccamError::Validation(
                    "--check-semantic requires --semantic".into(),
                ));
            }
            let executable = std::env::current_exe().map_err(|error| {
                OccamError::Validation(format!("cannot resolve current executable: {error}"))
            })?;
            let records = run_isolated_experiment(
                &executable,
                &config,
                &tasks,
                &raw_measured,
                abc.as_deref(),
                jobs,
            )?;
            println!("trials:           {}", records.len());
            println!("jobs requested:   {jobs}");
            println!("raw measured:     {}", raw_measured.display());
            if let Some(semantic) = semantic {
                if check_semantic {
                    let expected =
                        fs::read_to_string(&semantic).map_err(|source| OccamError::ReadFile {
                            path: semantic.clone(),
                            source,
                        })?;
                    let actual = render_semantic_jsonl(&records)?;
                    if actual != expected {
                        return Err(OccamError::Validation(
                            "regenerated semantic JSONL differs".into(),
                        ));
                    }
                    println!("status:           semantic projection reproducible");
                } else {
                    write_semantic_jsonl(&semantic, &records)?;
                }
                println!("semantic target:  {}", semantic.display());
            }
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

#[derive(Serialize)]
struct CombinedOptimizationReport {
    schema_version: u32,
    baseline_gate_count: usize,
    abc: AbcPortfolioReport,
    peephole_baseline: PeepholeOptimizationReport,
    peephole_abc: PeepholeOptimizationReport,
    selected_source: String,
    selected_gate_count: usize,
    selected_circuit_sha256: String,
    exhaustive_cases: usize,
    exhaustive_mismatches: usize,
}

fn print_optimization_summary(
    status: &str,
    baseline_gates: usize,
    candidate_gates: Option<usize>,
    flow: Option<&str>,
    report: &Path,
) {
    println!("status:           {status}");
    println!("baseline gates:   {baseline_gates}");
    if let Some(candidate_gates) = candidate_gates {
        println!("candidate gates:  {candidate_gates}");
    }
    if let Some(flow) = flow {
        println!("flow:             {flow}");
    }
    println!("report:           {}", report.display());
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

fn write_atomic_bundle(writes: [(&PathBuf, &str); 3]) -> Result<(), OccamError> {
    for index in 0..writes.len() {
        for other in index + 1..writes.len() {
            if writes[index].0 == writes[other].0 {
                return Err(OccamError::Validation(format!(
                    "MDL artifact paths must be distinct: {}",
                    writes[index].0.display()
                )));
            }
        }
    }
    for (path, _) in &writes {
        let parent = path.parent().unwrap_or_else(|| Path::new("."));
        fs::create_dir_all(parent).map_err(|source| OccamError::WriteFile {
            path: parent.to_owned(),
            source,
        })?;
    }
    let temporary_paths = writes
        .iter()
        .map(|(path, _)| temporary_path(path))
        .collect::<Vec<_>>();
    let result = (|| {
        for ((_, contents), temporary) in writes.iter().zip(&temporary_paths) {
            let mut file = File::create(temporary).map_err(|source| OccamError::WriteFile {
                path: temporary.clone(),
                source,
            })?;
            file.write_all(contents.as_bytes())
                .and_then(|()| file.sync_all())
                .map_err(|source| OccamError::WriteFile {
                    path: temporary.clone(),
                    source,
                })?;
        }
        for ((path, _), temporary) in writes.iter().zip(&temporary_paths) {
            fs::rename(temporary, path).map_err(|source| OccamError::WriteFile {
                path: (*path).clone(),
                source,
            })?;
        }
        Ok(())
    })();
    if result.is_err() {
        for temporary in temporary_paths {
            let _ = fs::remove_file(temporary);
        }
    }
    result
}

fn temporary_path(path: &Path) -> PathBuf {
    let file_name = path.file_name().and_then(|name| name.to_str()).unwrap();
    path.with_file_name(format!(
        ".{file_name}.{}.tmp-occam71-mdl",
        std::process::id()
    ))
}

fn main() {
    if let Err(error) = run() {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
