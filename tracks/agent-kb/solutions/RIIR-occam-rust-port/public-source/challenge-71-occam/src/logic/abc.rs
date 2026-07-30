use std::{
    fs::{self, File},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::atomic::{AtomicU64, Ordering},
    thread,
    time::{Duration, Instant},
};

use crate::{
    Circuit, OccamError, ResourceLimits, circuit_to_blif, evaluate_with_limits, parse_mapped_blif,
    parse_netlist_with_limits, sha256_hex,
};

use super::report::{
    AbcCandidate, AbcFlowReport, AbcOptimizationConfig, AbcOptimizationResult, AbcPortfolioReport,
    ExternalCommandLimits,
};

const FLOWS: &[(&str, &str)] = &[
    (
        "resyn",
        "balance; rewrite; rewrite -z; balance; rewrite -z; balance",
    ),
    (
        "resyn2",
        "balance; rewrite; refactor; balance; rewrite; rewrite -z; balance; refactor -z; rewrite -z; balance",
    ),
    (
        "resyn3",
        "balance; resub; resub -K 6; balance; resub -z; resub -z -K 6; balance; resub -z -K 5; balance",
    ),
    (
        "compress",
        "balance -l; rewrite -l; rewrite -z -l; balance -l; rewrite -z -l; balance -l",
    ),
    (
        "compress2",
        "balance -l; rewrite -l; refactor -l; balance -l; rewrite -l; rewrite -z -l; balance -l; refactor -z -l; rewrite -z -l; balance -l",
    ),
    (
        "resyn2rs",
        "balance; resub -K 6; rewrite; resub -K 6 -N 2; refactor; resub -K 8; balance; resub -K 8 -N 2; rewrite; resub -K 10; rewrite -z; resub -K 10 -N 2; balance",
    ),
    ("dc2", "dc2"),
];

pub(super) const FLOW_NAMES: &[&str] = &[
    "resyn",
    "resyn2",
    "resyn3",
    "compress",
    "compress2",
    "resyn2rs",
    "dc2",
];

static TEMPORARY_COUNTER: AtomicU64 = AtomicU64::new(0);

pub fn optimize_with_abc(
    original: &Circuit,
    abc_binary: &Path,
    config: &AbcOptimizationConfig,
    limits: &ResourceLimits,
) -> Result<AbcOptimizationResult, OccamError> {
    validate_config(abc_binary, config)?;
    let abc_binary = absolute_existing_path(abc_binary, "ABC executable")?;
    let genlib_path = absolute_existing_path(&config.genlib_path, "ABC GENLIB")?;
    let original_blif = circuit_to_blif(original, "original")?;
    let mut flows = Vec::with_capacity(config.flow_names.len());
    let mut candidates = Vec::new();
    for name in &config.flow_names {
        let commands = flow_commands(name).unwrap();
        match run_flow(
            original,
            &original_blif,
            &abc_binary,
            &genlib_path,
            name,
            commands,
            config,
            limits,
        ) {
            Ok((report, candidate)) => {
                flows.push(report);
                if let Some(candidate) = candidate {
                    candidates.push(candidate);
                }
            }
            Err(error) => flows.push(failed_flow(name, error.to_string())),
        }
    }
    candidates.sort_by(|lhs, rhs| {
        (lhs.official_gate_count, &lhs.flow_name, &lhs.circuit_sha256).cmp(&(
            rhs.official_gate_count,
            &rhs.flow_name,
            &rhs.circuit_sha256,
        ))
    });
    let selected = candidates.first();
    let report = AbcPortfolioReport {
        schema_version: 1,
        baseline_gate_count: original.gates.len(),
        accepted_candidates: candidates.len(),
        selected_flow: selected.map(|candidate| candidate.flow_name.clone()),
        selected_gate_count: selected.map(|candidate| candidate.official_gate_count),
        selected_circuit_sha256: selected.map(|candidate| candidate.circuit_sha256.clone()),
        flows,
    };
    Ok(AbcOptimizationResult { report, candidates })
}

pub(crate) fn synthesize_partial_with_abc(
    pla: &str,
    abc_binary: &Path,
    genlib_path: &Path,
    command_limits: &ExternalCommandLimits,
    limits: &ResourceLimits,
) -> Result<String, OccamError> {
    let abc_binary = absolute_existing_path(abc_binary, "ABC executable")?;
    let genlib_path = absolute_existing_path(genlib_path, "ABC GENLIB")?;
    limits.require(
        "partial PLA source bytes",
        pla.len(),
        limits.max_source_bytes,
    )?;
    let temporary = TemporaryDirectory::new("occam71-partial-abc")?;
    fs::write(temporary.path.join("observed.pla"), pla).map_err(|source| {
        OccamError::WriteFile {
            path: temporary.path.join("observed.pla"),
            source,
        }
    })?;
    fs::copy(genlib_path, temporary.path.join("occam.genlib")).map_err(|source| {
        OccamError::WriteFile {
            path: temporary.path.join("occam.genlib"),
            source,
        }
    })?;
    let script = "\
read_pla observed.pla
espresso
strash
dc2
read_library occam.genlib
map -a
write_blif hypothesis.blif
quit
";
    fs::write(temporary.path.join("flow.abc"), script).map_err(|source| OccamError::WriteFile {
        path: temporary.path.join("flow.abc"),
        source,
    })?;
    let process = run_bounded_command(
        &abc_binary,
        &["-f", "flow.abc"],
        &temporary.path,
        command_limits,
    )?;
    if !process.success {
        let detail = format!(
            "{}\n{}",
            String::from_utf8_lossy(&process.stdout),
            String::from_utf8_lossy(&process.stderr)
        );
        return Err(OccamError::Validation(format!(
            "partial ABC process failed: {}",
            bounded_tail(&detail, 4_096)
        )));
    }
    let mapped_source = read_bounded(
        &temporary.path.join("hypothesis.blif"),
        limits.max_source_bytes,
    )?;
    let mapped_text = std::str::from_utf8(&mapped_source)
        .map_err(|error| OccamError::Validation(format!("mapped BLIF is not UTF-8: {error}")))?;
    let mapped = parse_mapped_blif(mapped_text)?;
    let netlist = mapped.into_official_netlist()?;
    parse_netlist_with_limits(&netlist, limits)?;
    Ok(netlist)
}

fn absolute_existing_path(path: &Path, label: &str) -> Result<PathBuf, OccamError> {
    fs::canonicalize(path).map_err(|error| {
        OccamError::Validation(format!(
            "cannot resolve {label} {}: {error}",
            path.display()
        ))
    })
}

pub fn compare_circuits_exhaustively(
    lhs: &Circuit,
    rhs: &Circuit,
    max_inputs: usize,
    limits: &ResourceLimits,
) -> Result<(usize, usize), OccamError> {
    if lhs.input_count != rhs.input_count || lhs.outputs.len() != rhs.outputs.len() {
        return Err(OccamError::Validation(format!(
            "circuit shapes differ: lhs {} inputs/{} outputs, rhs {} inputs/{} outputs",
            lhs.input_count,
            lhs.outputs.len(),
            rhs.input_count,
            rhs.outputs.len()
        )));
    }
    if lhs.input_count > max_inputs {
        return Err(OccamError::Validation(format!(
            "exhaustive circuit comparison supports at most {max_inputs} inputs, got {}",
            lhs.input_count
        )));
    }
    let shift = u32::try_from(lhs.input_count).map_err(|_| OccamError::ArithmeticOverflow {
        context: "circuit equivalence shift",
    })?;
    let cases = 1usize
        .checked_shl(shift)
        .ok_or(OccamError::ArithmeticOverflow {
            context: "circuit equivalence cases",
        })?;
    limits.require("exhaustive cases", cases, limits.max_samples)?;
    let mut input = vec![false; lhs.input_count];
    let mut mismatches = 0usize;
    for packed in 0..cases {
        for (bit, value) in input.iter_mut().enumerate() {
            *value = packed & (1usize << bit) != 0;
        }
        if evaluate_with_limits(lhs, &input, limits)? != evaluate_with_limits(rhs, &input, limits)?
        {
            mismatches = mismatches
                .checked_add(1)
                .ok_or(OccamError::ArithmeticOverflow {
                    context: "circuit equivalence mismatches",
                })?;
        }
    }
    Ok((cases, mismatches))
}

#[allow(clippy::too_many_arguments)]
fn run_flow(
    original: &Circuit,
    original_blif: &str,
    abc_binary: &Path,
    genlib_path: &Path,
    name: &str,
    commands: &str,
    config: &AbcOptimizationConfig,
    limits: &ResourceLimits,
) -> Result<(AbcFlowReport, Option<AbcCandidate>), OccamError> {
    let temporary = TemporaryDirectory::new("occam71-abc")?;
    fs::write(temporary.path.join("original.blif"), original_blif).map_err(|source| {
        OccamError::WriteFile {
            path: temporary.path.join("original.blif"),
            source,
        }
    })?;
    fs::copy(genlib_path, temporary.path.join("occam.genlib")).map_err(|source| {
        OccamError::WriteFile {
            path: temporary.path.join("occam.genlib"),
            source,
        }
    })?;
    let script = format!(
        "\
read_blif original.blif
strash
{commands}
read_library occam.genlib
map -a
write_blif candidate.blif
cec original.blif candidate.blif
quit
"
    );
    fs::write(temporary.path.join("flow.abc"), script).map_err(|source| OccamError::WriteFile {
        path: temporary.path.join("flow.abc"),
        source,
    })?;
    let process = run_bounded_command(
        abc_binary,
        &["-f", "flow.abc"],
        &temporary.path,
        &config.command_limits,
    )?;
    let stdout = normalize_abc_output(&process.stdout);
    let stderr = normalize_abc_output(&process.stderr);
    let stdout_sha256 = sha256_hex(stdout.as_bytes());
    let stderr_sha256 = sha256_hex(stderr.as_bytes());
    let combined = format!("{stdout}\n{stderr}");
    let diagnostic_tail = bounded_tail(&combined, 4_096);
    if !process.success {
        return Ok((
            AbcFlowReport {
                name: name.to_owned(),
                accepted: false,
                status: "process-failed".into(),
                abc_cec_equivalent: false,
                rust_exhaustive_cases: None,
                rust_exhaustive_mismatches: None,
                official_gate_count: None,
                circuit_sha256: None,
                stdout_sha256,
                stderr_sha256,
                diagnostic_tail,
            },
            None,
        ));
    }
    let abc_cec_equivalent = combined.contains("Networks are equivalent");
    if !abc_cec_equivalent {
        return Ok((
            AbcFlowReport {
                name: name.to_owned(),
                accepted: false,
                status: "cec-failed".into(),
                abc_cec_equivalent: false,
                rust_exhaustive_cases: None,
                rust_exhaustive_mismatches: None,
                official_gate_count: None,
                circuit_sha256: None,
                stdout_sha256,
                stderr_sha256,
                diagnostic_tail,
            },
            None,
        ));
    }
    let mapped_path = temporary.path.join("candidate.blif");
    let mapped_source = read_bounded(&mapped_path, limits.max_source_bytes)?;
    let mapped_text = std::str::from_utf8(&mapped_source)
        .map_err(|error| OccamError::Validation(format!("mapped BLIF is not UTF-8: {error}")))?;
    let mapped = parse_mapped_blif(mapped_text)?;
    let netlist = mapped.into_official_netlist()?;
    let candidate_circuit = parse_netlist_with_limits(&netlist, limits)?;
    let (cases, mismatches) = compare_circuits_exhaustively(
        original,
        &candidate_circuit,
        config.max_exhaustive_inputs,
        limits,
    )?;
    let circuit_sha256 = sha256_hex(netlist.as_bytes());
    let accepted = mismatches == 0;
    let report = AbcFlowReport {
        name: name.to_owned(),
        accepted,
        status: if accepted {
            "accepted".into()
        } else {
            "rust-mismatch".into()
        },
        abc_cec_equivalent,
        rust_exhaustive_cases: Some(cases),
        rust_exhaustive_mismatches: Some(mismatches),
        official_gate_count: Some(candidate_circuit.gates.len()),
        circuit_sha256: Some(circuit_sha256),
        stdout_sha256,
        stderr_sha256,
        diagnostic_tail,
    };
    let candidate = accepted.then(|| {
        AbcCandidate::new(
            name.to_owned(),
            netlist,
            candidate_circuit.gates.len(),
            cases,
            mismatches,
        )
    });
    Ok((report, candidate))
}

fn normalize_abc_output(bytes: &[u8]) -> String {
    let decoded = String::from_utf8_lossy(bytes);
    let mut normalized = String::new();
    for line in decoded.lines() {
        if let Some(time) = line.find("Time =") {
            normalized.push_str(&line[..time]);
            normalized.push_str("Time = <normalized>");
        } else {
            normalized.push_str(line);
        }
        normalized.push('\n');
    }
    normalized
}

fn validate_config(abc_binary: &Path, config: &AbcOptimizationConfig) -> Result<(), OccamError> {
    if !abc_binary.is_file() {
        return Err(OccamError::Validation(format!(
            "ABC executable is absent: {}",
            abc_binary.display()
        )));
    }
    if !config.genlib_path.is_file() {
        return Err(OccamError::Validation(format!(
            "ABC GENLIB is absent: {}",
            config.genlib_path.display()
        )));
    }
    if config.flow_names.is_empty() {
        return Err(OccamError::Validation(
            "ABC flow selection must not be empty".into(),
        ));
    }
    for name in &config.flow_names {
        if flow_commands(name).is_none() {
            return Err(OccamError::Validation(format!("unknown ABC flow {name:?}")));
        }
    }
    if config.max_exhaustive_inputs == 0
        || config.command_limits.timeout.is_zero()
        || config.command_limits.max_stdout_bytes == 0
        || config.command_limits.max_stderr_bytes == 0
    {
        return Err(OccamError::Validation(
            "ABC process and equivalence limits must be positive".into(),
        ));
    }
    Ok(())
}

fn flow_commands(name: &str) -> Option<&'static str> {
    FLOWS
        .iter()
        .find_map(|(candidate, commands)| (*candidate == name).then_some(*commands))
}

fn failed_flow(name: &str, detail: String) -> AbcFlowReport {
    AbcFlowReport {
        name: name.to_owned(),
        accepted: false,
        status: "validation-failed".into(),
        abc_cec_equivalent: false,
        rust_exhaustive_cases: None,
        rust_exhaustive_mismatches: None,
        official_gate_count: None,
        circuit_sha256: None,
        stdout_sha256: sha256_hex(&[]),
        stderr_sha256: sha256_hex(detail.as_bytes()),
        diagnostic_tail: bounded_tail(&detail, 4_096),
    }
}

struct ProcessResult {
    success: bool,
    stdout: Vec<u8>,
    stderr: Vec<u8>,
}

fn run_bounded_command(
    program: &Path,
    arguments: &[&str],
    current_dir: &Path,
    limits: &ExternalCommandLimits,
) -> Result<ProcessResult, OccamError> {
    let stdout_path = current_dir.join("stdout.log");
    let stderr_path = current_dir.join("stderr.log");
    let stdout = File::create(&stdout_path).map_err(|source| OccamError::WriteFile {
        path: stdout_path.clone(),
        source,
    })?;
    let stderr = File::create(&stderr_path).map_err(|source| OccamError::WriteFile {
        path: stderr_path.clone(),
        source,
    })?;
    let mut child = Command::new(program)
        .args(arguments)
        .current_dir(current_dir)
        .stdin(Stdio::null())
        .stdout(Stdio::from(stdout))
        .stderr(Stdio::from(stderr))
        .spawn()
        .map_err(|error| {
            OccamError::Validation(format!(
                "failed to spawn bounded command {}: {error}",
                program.display()
            ))
        })?;
    let started = Instant::now();
    let status = loop {
        if let Some(status) = child
            .try_wait()
            .map_err(|error| OccamError::Validation(format!("command wait failed: {error}")))?
        {
            break status;
        }
        let stdout_bytes = file_size(&stdout_path)?;
        let stderr_bytes = file_size(&stderr_path)?;
        if stdout_bytes > limits.max_stdout_bytes || stderr_bytes > limits.max_stderr_bytes {
            let _ = child.kill();
            let _ = child.wait();
            return Err(OccamError::ResourceLimit {
                resource: "external command output bytes",
                requested: stdout_bytes.max(stderr_bytes),
                limit: limits.max_stdout_bytes.max(limits.max_stderr_bytes),
            });
        }
        if started.elapsed() >= limits.timeout {
            let _ = child.kill();
            let _ = child.wait();
            return Err(OccamError::Validation(format!(
                "external command timed out after {} milliseconds",
                limits.timeout.as_millis()
            )));
        }
        thread::sleep(Duration::from_millis(10));
    };
    let stdout = read_bounded(&stdout_path, limits.max_stdout_bytes)?;
    let stderr = read_bounded(&stderr_path, limits.max_stderr_bytes)?;
    Ok(ProcessResult {
        success: status.success(),
        stdout,
        stderr,
    })
}

fn file_size(path: &Path) -> Result<usize, OccamError> {
    let bytes = fs::metadata(path)
        .map_err(|source| OccamError::ReadFile {
            path: path.to_owned(),
            source,
        })?
        .len();
    usize::try_from(bytes).map_err(|_| OccamError::ArithmeticOverflow {
        context: "external command output size",
    })
}

fn read_bounded(path: &Path, max_bytes: usize) -> Result<Vec<u8>, OccamError> {
    let bytes = file_size(path)?;
    if bytes > max_bytes {
        return Err(OccamError::ResourceLimit {
            resource: "external command file bytes",
            requested: bytes,
            limit: max_bytes,
        });
    }
    fs::read(path).map_err(|source| OccamError::ReadFile {
        path: path.to_owned(),
        source,
    })
}

fn bounded_tail(value: &str, max_bytes: usize) -> String {
    if value.len() <= max_bytes {
        return value.to_owned();
    }
    let mut start = value.len() - max_bytes;
    while !value.is_char_boundary(start) {
        start += 1;
    }
    value[start..].to_owned()
}

struct TemporaryDirectory {
    path: PathBuf,
}

impl TemporaryDirectory {
    fn new(prefix: &str) -> Result<Self, OccamError> {
        let counter = TEMPORARY_COUNTER.fetch_add(1, Ordering::Relaxed);
        let path = std::env::temp_dir().join(format!("{prefix}-{}-{counter}", std::process::id()));
        fs::create_dir(&path).map_err(|source| OccamError::WriteFile {
            path: path.clone(),
            source,
        })?;
        Ok(Self { path })
    }
}

impl Drop for TemporaryDirectory {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.path);
    }
}
