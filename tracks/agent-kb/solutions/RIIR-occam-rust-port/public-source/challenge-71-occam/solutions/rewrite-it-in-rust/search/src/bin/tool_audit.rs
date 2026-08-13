use std::{
    fs::{self, File},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    thread,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

use clap::Parser;
use occam71_rust::{
    DEFAULT_LIMITS, OccamError, compare_circuits_exhaustively, parse_mapped_blif, parse_netlist,
    sha256_hex,
};
use serde::Serialize;

#[derive(Debug, Parser)]
#[command(name = "tool-audit")]
struct Cli {
    #[arg(long)]
    yosys: PathBuf,
    #[arg(long)]
    yosys_abc: PathBuf,
    #[arg(long)]
    espresso: PathBuf,
    #[arg(long)]
    espresso_source_commit: String,
    #[arg(long)]
    output: PathBuf,
}

#[derive(Serialize)]
struct Audit {
    schema_version: u32,
    tools: Vec<ToolRecord>,
}

#[derive(Serialize)]
struct ToolRecord {
    tool: String,
    version_output: String,
    executable_sha256: String,
    command: Vec<String>,
    input_sha256: String,
    output_sha256: String,
    output_normalization: String,
    observed_matches: usize,
    observed_total: usize,
    full_domain_mismatches: Option<usize>,
    full_domain_cases: Option<usize>,
}

fn main() {
    if let Err(error) = run() {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), OccamError> {
    let cli = Cli::parse();
    for (name, path) in [
        ("yosys", &cli.yosys),
        ("yosys-abc", &cli.yosys_abc),
        ("espresso", &cli.espresso),
    ] {
        if !path.is_file() {
            return Err(OccamError::Validation(format!(
                "{name} executable is missing: {}",
                path.display()
            )));
        }
    }
    if cli.espresso_source_commit.len() != 40
        || !cli
            .espresso_source_commit
            .bytes()
            .all(|byte| byte.is_ascii_hexdigit())
    {
        return Err(OccamError::Validation(
            "Espresso source commit must be a forty-digit hexadecimal hash".into(),
        ));
    }

    let temporary = AuditDirectory::new()?;
    let yosys = audit_yosys(&cli.yosys, &temporary.path)?;
    let abc = audit_yosys_abc(&cli.yosys_abc, &temporary.path)?;
    let espresso = audit_espresso(&cli.espresso, &cli.espresso_source_commit, &temporary.path)?;
    let audit = Audit {
        schema_version: 2,
        tools: vec![yosys, abc, espresso],
    };
    let encoded = serde_json::to_string_pretty(&audit)
        .map(|value| format!("{value}\n"))
        .map_err(|error| OccamError::Validation(format!("audit JSON encoding failed: {error}")))?;
    write_atomic(&cli.output, encoded.as_bytes())
}

fn audit_yosys(program: &Path, directory: &Path) -> Result<ToolRecord, OccamError> {
    let version = run_command(program, &["-V"], directory, "yosys-version")?;
    require_success("yosys version", &version)?;
    let input = "\
module top(input a, input b, output o);
  assign o = a ^ b;
endmodule
";
    fs::write(directory.join("fixture.v"), input).map_err(|source| OccamError::WriteFile {
        path: directory.join("fixture.v"),
        source,
    })?;
    let script = "read_verilog fixture.v; hierarchy -top top; proc; opt; techmap; opt; abc; clean; write_blif yosys.blif";
    let flow = run_command(program, &["-q", "-p", script], directory, "yosys-flow")?;
    require_success("yosys synthesis", &flow)?;
    let output = read_bounded(&directory.join("yosys.blif"))?;
    let mapped =
        parse_mapped_blif(std::str::from_utf8(&output).map_err(|error| {
            OccamError::Validation(format!("Yosys BLIF is not UTF-8: {error}"))
        })?)?;
    let candidate = parse_netlist(&mapped.into_official_netlist()?)?;
    let reference = parse_netlist("INPUTS 2\nw1 = XOR x1 x2\nOUTPUTS w1\n")?;
    let (cases, mismatches) =
        compare_circuits_exhaustively(&reference, &candidate, 8, &DEFAULT_LIMITS)?;
    if mismatches != 0 {
        return Err(OccamError::Validation(format!(
            "Rust rejected Yosys output on {mismatches}/{cases} full-domain rows"
        )));
    }
    Ok(ToolRecord {
        tool: "yosys".into(),
        version_output: bounded_version(&version),
        executable_sha256: executable_hash(program)?,
        command: vec!["yosys".into(), "-q".into(), "-p".into(), script.into()],
        input_sha256: sha256_hex(input.as_bytes()),
        output_sha256: sha256_hex(&output),
        output_normalization: "none".into(),
        observed_matches: cases - mismatches,
        observed_total: cases,
        full_domain_mismatches: Some(mismatches),
        full_domain_cases: Some(cases),
    })
}

fn audit_yosys_abc(program: &Path, directory: &Path) -> Result<ToolRecord, OccamError> {
    let version = run_command(program, &["-q", "version"], directory, "abc-version")?;
    require_success("yosys ABC version", &version)?;
    let input = "\
.model reference
.inputs i0 i1
.outputs o0
.names i0 i1 n0
10 1
01 1
.names n0 o0
1 1
.end
";
    fs::write(directory.join("abc-input.blif"), input).map_err(|source| OccamError::WriteFile {
        path: directory.join("abc-input.blif"),
        source,
    })?;
    let command = "read_blif abc-input.blif; strash; dc2; write_blif abc-output.blif; cec abc-input.blif abc-output.blif";
    let flow = run_command(program, &["-q", command], directory, "abc-flow")?;
    require_success("yosys ABC optimization", &flow)?;
    let output = read_bounded(&directory.join("abc-output.blif"))?;
    let output_source = std::str::from_utf8(&output)
        .map_err(|error| OccamError::Validation(format!("Yosys ABC BLIF is not UTF-8: {error}")))?;
    let mapped = parse_mapped_blif(output_source)?;
    let candidate = parse_netlist(&mapped.into_official_netlist()?)?;
    let reference = parse_netlist("INPUTS 2\nw1 = XOR x1 x2\nOUTPUTS w1\n")?;
    let (cases, mismatches) =
        compare_circuits_exhaustively(&reference, &candidate, 8, &DEFAULT_LIMITS)?;
    if mismatches != 0 {
        return Err(OccamError::Validation(format!(
            "Rust rejected Yosys ABC output on {mismatches}/{cases} full-domain rows"
        )));
    }
    Ok(ToolRecord {
        tool: "yosys-abc".into(),
        version_output: bounded_version(&version),
        executable_sha256: executable_hash(program)?,
        command: vec!["yosys-abc".into(), "-q".into(), command.into()],
        input_sha256: sha256_hex(input.as_bytes()),
        output_sha256: sha256_hex(&normalize_abc_blif_for_hash(output_source)?),
        output_normalization: "strip one leading ABC timestamp banner comment".into(),
        observed_matches: cases - mismatches,
        observed_total: cases,
        full_domain_mismatches: Some(mismatches),
        full_domain_cases: Some(cases),
    })
}

fn audit_espresso(
    program: &Path,
    source_commit: &str,
    directory: &Path,
) -> Result<ToolRecord, OccamError> {
    let input = "\
.i 2
.o 1
.type fd
00 0
01 1
1- -
.e
";
    fs::write(directory.join("partial.pla"), input).map_err(|source| OccamError::WriteFile {
        path: directory.join("partial.pla"),
        source,
    })?;
    let flow = run_command_with_stdin(
        program,
        &[],
        directory,
        "espresso-flow",
        Some(&directory.join("partial.pla")),
    )?;
    require_success("Espresso minimization", &flow)?;
    let output = flow.stdout;
    let pla =
        Pla::parse(std::str::from_utf8(&output).map_err(|error| {
            OccamError::Validation(format!("Espresso PLA is not UTF-8: {error}"))
        })?)?;
    let observed = [([false, false], [false]), ([false, true], [true])];
    let matches = observed
        .iter()
        .filter(|(input, expected)| pla.evaluate(input) == Some(expected.to_vec()))
        .count();
    if matches != observed.len() {
        return Err(OccamError::Validation(format!(
            "Rust parsed Espresso output fits only {matches}/{} observed rows",
            observed.len()
        )));
    }
    Ok(ToolRecord {
        tool: "espresso".into(),
        version_output: format!(
            "CHIPS Alliance Espresso source commit {} (executable exposes no version flag)",
            source_commit.to_ascii_lowercase()
        ),
        executable_sha256: executable_hash(program)?,
        command: vec!["espresso".into()],
        input_sha256: sha256_hex(input.as_bytes()),
        output_sha256: sha256_hex(&output),
        output_normalization: "none".into(),
        observed_matches: matches,
        observed_total: observed.len(),
        full_domain_mismatches: None,
        full_domain_cases: None,
    })
}

fn normalize_abc_blif_for_hash(source: &str) -> Result<Vec<u8>, OccamError> {
    let (banner, body) = source.split_once('\n').ok_or_else(|| {
        OccamError::Validation("Yosys ABC BLIF is missing its banner line".into())
    })?;
    if !banner.starts_with("# Benchmark ") || !banner.contains(" written by ABC on ") {
        return Err(OccamError::Validation(format!(
            "unexpected Yosys ABC BLIF banner: {banner}"
        )));
    }
    Ok(body.as_bytes().to_vec())
}

struct Pla {
    input_width: usize,
    output_width: usize,
    cubes: Vec<(Vec<u8>, Vec<u8>)>,
}

impl Pla {
    fn parse(source: &str) -> Result<Self, OccamError> {
        let mut input_width = None;
        let mut output_width = None;
        let mut cubes = Vec::new();
        for (index, raw) in source.lines().enumerate() {
            let line = raw.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            if let Some(value) = line.strip_prefix(".i ") {
                input_width = Some(parse_width(value, index + 1)?);
            } else if let Some(value) = line.strip_prefix(".o ") {
                output_width = Some(parse_width(value, index + 1)?);
            } else if line.starts_with('.') {
                if !matches!(
                    line.split_whitespace().next(),
                    Some(".type" | ".p" | ".ilb" | ".ob" | ".e")
                ) {
                    return Err(OccamError::Validation(format!(
                        "unsupported PLA directive at line {}: {line}",
                        index + 1
                    )));
                }
            } else {
                let fields = line.split_whitespace().collect::<Vec<_>>();
                if fields.len() != 2 {
                    return Err(OccamError::Validation(format!(
                        "invalid PLA cube at line {}",
                        index + 1
                    )));
                }
                cubes.push((fields[0].as_bytes().to_vec(), fields[1].as_bytes().to_vec()));
            }
        }
        let input_width = input_width
            .ok_or_else(|| OccamError::Validation("Espresso PLA is missing .i".into()))?;
        let output_width = output_width
            .ok_or_else(|| OccamError::Validation("Espresso PLA is missing .o".into()))?;
        for (inputs, outputs) in &cubes {
            if inputs.len() != input_width
                || outputs.len() != output_width
                || !inputs.iter().all(|byte| matches!(byte, b'0' | b'1' | b'-'))
                || !outputs
                    .iter()
                    .all(|byte| matches!(byte, b'0' | b'1' | b'-'))
            {
                return Err(OccamError::Validation(
                    "Espresso PLA contains an invalid cube width or symbol".into(),
                ));
            }
        }
        Ok(Self {
            input_width,
            output_width,
            cubes,
        })
    }

    fn evaluate(&self, input: &[bool]) -> Option<Vec<bool>> {
        if input.len() != self.input_width {
            return None;
        }
        let matching = self
            .cubes
            .iter()
            .filter(|(cube, _)| {
                cube.iter()
                    .zip(input)
                    .all(|(symbol, bit)| *symbol == b'-' || (*symbol == b'1') == *bit)
            })
            .collect::<Vec<_>>();
        let mut result = Vec::with_capacity(self.output_width);
        for output in 0..self.output_width {
            if matching.iter().any(|(_, values)| values[output] == b'1') {
                result.push(true);
            } else if matching.iter().any(|(_, values)| values[output] == b'-') {
                return None;
            } else {
                result.push(false);
            }
        }
        Some(result)
    }
}

fn parse_width(value: &str, line: usize) -> Result<usize, OccamError> {
    value
        .trim()
        .parse::<usize>()
        .map_err(|_| OccamError::Validation(format!("invalid PLA width at line {line}: {value}")))
}

struct CommandOutput {
    success: bool,
    stdout: Vec<u8>,
    stderr: Vec<u8>,
}

fn run_command(
    program: &Path,
    arguments: &[&str],
    directory: &Path,
    label: &str,
) -> Result<CommandOutput, OccamError> {
    run_command_with_stdin(program, arguments, directory, label, None)
}

fn run_command_with_stdin(
    program: &Path,
    arguments: &[&str],
    directory: &Path,
    label: &str,
    stdin_path: Option<&Path>,
) -> Result<CommandOutput, OccamError> {
    let stdout_path = directory.join(format!("{label}.stdout"));
    let stderr_path = directory.join(format!("{label}.stderr"));
    let stdout = File::create(&stdout_path).map_err(|source| OccamError::WriteFile {
        path: stdout_path.clone(),
        source,
    })?;
    let stderr = File::create(&stderr_path).map_err(|source| OccamError::WriteFile {
        path: stderr_path.clone(),
        source,
    })?;
    let stdin = match stdin_path {
        Some(path) => Stdio::from(File::open(path).map_err(|source| OccamError::ReadFile {
            path: path.to_owned(),
            source,
        })?),
        None => Stdio::null(),
    };
    let mut child = Command::new(program)
        .args(arguments)
        .current_dir(directory)
        .stdin(stdin)
        .stdout(Stdio::from(stdout))
        .stderr(Stdio::from(stderr))
        .spawn()
        .map_err(|error| {
            OccamError::Validation(format!("failed to spawn {}: {error}", program.display()))
        })?;
    let started = Instant::now();
    let status = loop {
        if let Some(status) = child
            .try_wait()
            .map_err(|error| OccamError::Validation(format!("tool wait failed: {error}")))?
        {
            break status;
        }
        if started.elapsed() >= Duration::from_secs(30) {
            let _ = child.kill();
            let _ = child.wait();
            return Err(OccamError::Validation(format!(
                "{label} exceeded the 30-second audit timeout"
            )));
        }
        thread::sleep(Duration::from_millis(10));
    };
    Ok(CommandOutput {
        success: status.success(),
        stdout: read_bounded(&stdout_path)?,
        stderr: read_bounded(&stderr_path)?,
    })
}

fn require_success(label: &str, output: &CommandOutput) -> Result<(), OccamError> {
    if output.success {
        return Ok(());
    }
    Err(OccamError::Validation(format!(
        "{label} failed: {}{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    )))
}

fn bounded_version(output: &CommandOutput) -> String {
    let combined = format!(
        "{}{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    combined.chars().take(4_096).collect::<String>()
}

fn read_bounded(path: &Path) -> Result<Vec<u8>, OccamError> {
    let metadata = fs::metadata(path).map_err(|source| OccamError::ReadFile {
        path: path.to_owned(),
        source,
    })?;
    if metadata.len() > 4 * 1024 * 1024 {
        return Err(OccamError::ResourceLimit {
            resource: "tool audit output bytes",
            requested: usize::try_from(metadata.len()).unwrap_or(usize::MAX),
            limit: 4 * 1024 * 1024,
        });
    }
    fs::read(path).map_err(|source| OccamError::ReadFile {
        path: path.to_owned(),
        source,
    })
}

fn executable_hash(path: &Path) -> Result<String, OccamError> {
    fs::read(path)
        .map(|bytes| sha256_hex(&bytes))
        .map_err(|source| OccamError::ReadFile {
            path: path.to_owned(),
            source,
        })
}

fn write_atomic(path: &Path, bytes: &[u8]) -> Result<(), OccamError> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|source| OccamError::WriteFile {
            path: parent.to_owned(),
            source,
        })?;
    }
    let temporary = path.with_extension(format!("{}.tmp", std::process::id()));
    fs::write(&temporary, bytes).map_err(|source| OccamError::WriteFile {
        path: temporary.clone(),
        source,
    })?;
    fs::rename(&temporary, path).map_err(|source| OccamError::WriteFile {
        path: path.to_owned(),
        source,
    })
}

struct AuditDirectory {
    path: PathBuf,
}

impl AuditDirectory {
    fn new() -> Result<Self, OccamError> {
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|error| OccamError::Validation(format!("system clock error: {error}")))?
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "occam71-tool-audit-{}-{timestamp}",
            std::process::id()
        ));
        fs::create_dir(&path).map_err(|source| OccamError::WriteFile {
            path: path.clone(),
            source,
        })?;
        Ok(Self { path })
    }
}

impl Drop for AuditDirectory {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.path);
    }
}

#[cfg(test)]
mod tests {
    use super::normalize_abc_blif_for_hash;

    #[test]
    fn abc_hash_normalization_removes_only_the_timestamp_banner() {
        let body = ".model reference\n.inputs i0\n.outputs o0\n.end\n";
        let first = format!("# Benchmark \"reference\" written by ABC on Monday\n{body}");
        let second = format!("# Benchmark \"reference\" written by ABC on Tuesday\n{body}");
        assert_eq!(
            normalize_abc_blif_for_hash(&first).unwrap(),
            body.as_bytes()
        );
        assert_eq!(
            normalize_abc_blif_for_hash(&first).unwrap(),
            normalize_abc_blif_for_hash(&second).unwrap()
        );
        assert!(normalize_abc_blif_for_hash(body).is_err());
    }
}
