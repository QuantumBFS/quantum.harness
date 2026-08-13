use std::{
    hint::black_box,
    process::Command,
    time::{Duration, Instant},
};

use serde::{Deserialize, Serialize};

use crate::{
    Circuit, CompiledCircuit, Dataset, OccamError, PackedDataset, VerificationMetrics,
    pack_dataset, parse_dataset, parse_packed_dataset, verify, verify_compiled_prepacked,
    verify_prepacked_interpreted, verify_prepacked_reference,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum BenchmarkBackend {
    Scalar,
    Packed,
    PackedReference,
    PackedInterpreted,
    Compiled,
}

impl BenchmarkBackend {
    pub fn label(self) -> &'static str {
        match self {
            Self::Scalar => "scalar",
            Self::Packed => "packed",
            Self::PackedReference => "packed-reference",
            Self::PackedInterpreted => "packed-interpreted",
            Self::Compiled => "compiled",
        }
    }
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct TimingStatistics {
    pub minimum_ns: u64,
    pub mean_ns: f64,
    pub median_ns: u64,
    pub p95_ns: u64,
    pub standard_deviation_ns: f64,
    pub median_absolute_deviation_ns: u64,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct BenchmarkReport {
    pub schema_version: u32,
    pub backend: String,
    pub circuit_path: String,
    pub dataset_path: String,
    pub samples: usize,
    pub gates: usize,
    pub input_width: usize,
    pub output_width: usize,
    pub warmup_iterations: usize,
    pub measured_iterations: usize,
    pub batch_count: usize,
    pub raw_iterations_ns: Vec<u64>,
    pub batch_medians_ns: Vec<u64>,
    pub measurement_order: String,
    pub parse_ns: u64,
    pub packing_ns: Option<u64>,
    pub circuit_parse_ns: u64,
    pub scalar_dataset_parse_ns: u64,
    pub legacy_pack_ns: u64,
    pub direct_packed_parse_ns: u64,
    pub compilation_ns: u64,
    pub one_shot_ns: u64,
    pub scalar_dataset_parse_iterations_ns: Vec<u64>,
    pub legacy_pack_iterations_ns: Vec<u64>,
    pub direct_packed_parse_iterations_ns: Vec<u64>,
    pub compilation_iterations_ns: Vec<u64>,
    pub scalar_dataset_parse: TimingStatistics,
    pub legacy_pack: TimingStatistics,
    pub direct_packed_parse: TimingStatistics,
    pub compilation: TimingStatistics,
    pub evaluation: TimingStatistics,
    pub samples_per_second_at_median: f64,
    pub gate_evaluations_per_second_at_median: f64,
    pub exact_matches: usize,
    pub correct_bits: usize,
    pub total_bits: usize,
    pub rustc: String,
    pub operating_system: String,
    pub architecture: String,
}

#[allow(clippy::too_many_arguments)]
pub fn run_benchmark(
    backend: BenchmarkBackend,
    circuit: &Circuit,
    dataset_source: &str,
    warmups: usize,
    iterations: usize,
    batches: usize,
    circuit_parse_duration: Duration,
    circuit_path: String,
    dataset_path: String,
) -> Result<BenchmarkReport, OccamError> {
    if iterations == 0 || batches == 0 {
        return Err(OccamError::Validation(
            "benchmark iterations and batches must be positive".into(),
        ));
    }

    let (dataset, legacy_packed, first_scalar_parse, first_legacy_pack) =
        parse_and_pack_legacy(dataset_source)?;
    let (direct_packed, first_direct_parse) = parse_direct(dataset_source)?;
    if direct_packed != legacy_packed {
        return Err(OccamError::Validation(
            "direct packed parser disagrees with scalar parse plus pack".into(),
        ));
    }

    let (compiled, first_compilation) = compile_circuit(circuit)?;

    let mut scalar_parse_durations = vec![first_scalar_parse];
    let mut legacy_pack_durations = vec![first_legacy_pack];
    let mut direct_parse_durations = vec![first_direct_parse];
    let mut compilation_durations = vec![first_compilation];
    for repetition in 1..5 {
        if repetition % 2 == 1 {
            let (direct, duration) = parse_direct(dataset_source)?;
            black_box(direct);
            direct_parse_durations.push(duration);
            let (scalar, packed, parse_duration, pack_duration) =
                parse_and_pack_legacy(dataset_source)?;
            black_box((scalar, packed));
            scalar_parse_durations.push(parse_duration);
            legacy_pack_durations.push(pack_duration);
        } else {
            let (scalar, packed, parse_duration, pack_duration) =
                parse_and_pack_legacy(dataset_source)?;
            black_box((scalar, packed));
            scalar_parse_durations.push(parse_duration);
            legacy_pack_durations.push(pack_duration);
            let (direct, duration) = parse_direct(dataset_source)?;
            black_box(direct);
            direct_parse_durations.push(duration);
        }
        let (candidate, duration) = compile_circuit(circuit)?;
        black_box(candidate);
        compilation_durations.push(duration);
    }
    let scalar_parse_statistics = statistics(&scalar_parse_durations)?;
    let legacy_pack_statistics = statistics(&legacy_pack_durations)?;
    let direct_parse_statistics = statistics(&direct_parse_durations)?;
    let compilation_statistics = statistics(&compilation_durations)?;
    let scalar_dataset_parse_duration = Duration::from_nanos(scalar_parse_statistics.median_ns);
    let legacy_pack_duration = Duration::from_nanos(legacy_pack_statistics.median_ns);
    let direct_packed_parse_duration = Duration::from_nanos(direct_parse_statistics.median_ns);
    let compilation_duration = Duration::from_nanos(compilation_statistics.median_ns);

    let scalar_metrics = verify(circuit, &dataset)?;
    let interpreted_metrics = verify_prepacked_interpreted(circuit, &direct_packed)?;
    let compiled_metrics = verify_compiled_prepacked(&compiled, &direct_packed)?;
    if scalar_metrics != interpreted_metrics || scalar_metrics != compiled_metrics {
        return Err(OccamError::Validation(format!(
            "benchmark preflight mismatch: scalar {scalar_metrics:?}, interpreted \
             {interpreted_metrics:?}, compiled {compiled_metrics:?}"
        )));
    }

    let (durations, batch_medians, metrics) = match backend {
        BenchmarkBackend::Scalar => {
            let (durations, medians, metrics) =
                measure_batches(batches, warmups, iterations, || verify(circuit, &dataset))?;
            (durations, medians, metrics)
        }
        BenchmarkBackend::Packed => {
            let compiled = CompiledCircuit::new(circuit)?;
            let (durations, medians, metrics) =
                measure_batches(batches, warmups, iterations, || {
                    verify_compiled_prepacked(&compiled, &direct_packed)
                })?;
            (durations, medians, metrics)
        }
        BenchmarkBackend::PackedReference => {
            let (durations, medians, metrics) =
                measure_batches(batches, warmups, iterations, || {
                    verify_prepacked_reference(circuit, &legacy_packed)
                })?;
            (durations, medians, metrics)
        }
        BenchmarkBackend::PackedInterpreted => {
            let (durations, medians, metrics) =
                measure_batches(batches, warmups, iterations, || {
                    verify_prepacked_interpreted(circuit, &direct_packed)
                })?;
            (durations, medians, metrics)
        }
        BenchmarkBackend::Compiled => {
            let (durations, medians, metrics) =
                measure_batches(batches, warmups, iterations, || {
                    verify_compiled_prepacked(&compiled, &direct_packed)
                })?;
            (durations, medians, metrics)
        }
    };

    let statistics = statistics(&durations)?;
    let median_seconds = statistics.median_ns as f64 / 1_000_000_000.0;
    let samples_per_second = dataset.samples.len() as f64 / median_seconds;
    let gate_evaluations_per_second =
        dataset.samples.len() as f64 * circuit.gates.len() as f64 / median_seconds;
    let (parse_duration, packing_duration, compile_for_backend) = match backend {
        BenchmarkBackend::Scalar => (
            circuit_parse_duration.saturating_add(scalar_dataset_parse_duration),
            None,
            Duration::ZERO,
        ),
        BenchmarkBackend::Packed | BenchmarkBackend::Compiled => (
            circuit_parse_duration.saturating_add(direct_packed_parse_duration),
            Some(direct_packed_parse_duration.saturating_add(compilation_duration)),
            compilation_duration,
        ),
        BenchmarkBackend::PackedInterpreted => (
            circuit_parse_duration.saturating_add(direct_packed_parse_duration),
            Some(direct_packed_parse_duration),
            Duration::ZERO,
        ),
        BenchmarkBackend::PackedReference => (
            circuit_parse_duration.saturating_add(scalar_dataset_parse_duration),
            Some(legacy_pack_duration),
            legacy_pack_duration,
        ),
    };
    let one_shot_ns = duration_ns(parse_duration)
        .saturating_add(duration_ns(compile_for_backend))
        .saturating_add(statistics.median_ns);

    Ok(BenchmarkReport {
        schema_version: 3,
        backend: backend.label().into(),
        circuit_path,
        dataset_path,
        samples: dataset.samples.len(),
        gates: circuit.gates.len(),
        input_width: dataset.input_width,
        output_width: dataset.output_width,
        warmup_iterations: warmups,
        measured_iterations: iterations,
        batch_count: batches,
        raw_iterations_ns: durations.iter().copied().map(duration_ns).collect(),
        batch_medians_ns: batch_medians,
        measurement_order: "backend-isolated; invocation order controlled by external driver"
            .into(),
        parse_ns: duration_ns(parse_duration),
        packing_ns: packing_duration.map(duration_ns),
        circuit_parse_ns: duration_ns(circuit_parse_duration),
        scalar_dataset_parse_ns: duration_ns(scalar_dataset_parse_duration),
        legacy_pack_ns: duration_ns(legacy_pack_duration),
        direct_packed_parse_ns: duration_ns(direct_packed_parse_duration),
        compilation_ns: duration_ns(compilation_duration),
        one_shot_ns,
        scalar_dataset_parse_iterations_ns: scalar_parse_durations
            .iter()
            .copied()
            .map(duration_ns)
            .collect(),
        legacy_pack_iterations_ns: legacy_pack_durations
            .iter()
            .copied()
            .map(duration_ns)
            .collect(),
        direct_packed_parse_iterations_ns: direct_parse_durations
            .iter()
            .copied()
            .map(duration_ns)
            .collect(),
        compilation_iterations_ns: compilation_durations
            .iter()
            .copied()
            .map(duration_ns)
            .collect(),
        scalar_dataset_parse: scalar_parse_statistics,
        legacy_pack: legacy_pack_statistics,
        direct_packed_parse: direct_parse_statistics,
        compilation: compilation_statistics,
        evaluation: statistics,
        samples_per_second_at_median: samples_per_second,
        gate_evaluations_per_second_at_median: gate_evaluations_per_second,
        exact_matches: metrics.exact_matches,
        correct_bits: metrics.correct_bits,
        total_bits: metrics.total_bits,
        rustc: command_output("rustc", &["--version"]),
        operating_system: operating_system(),
        architecture: std::env::consts::ARCH.into(),
    })
}

fn parse_and_pack_legacy(
    source: &str,
) -> Result<(Dataset, PackedDataset, Duration, Duration), OccamError> {
    let parse_started = Instant::now();
    let dataset = parse_dataset(source)?;
    let parse_duration = parse_started.elapsed();
    let pack_started = Instant::now();
    let packed = pack_dataset(&dataset)?;
    let pack_duration = pack_started.elapsed();
    Ok((dataset, packed, parse_duration, pack_duration))
}

fn parse_direct(source: &str) -> Result<(PackedDataset, Duration), OccamError> {
    let started = Instant::now();
    let packed = parse_packed_dataset(source)?;
    Ok((packed, started.elapsed()))
}

fn compile_circuit(circuit: &Circuit) -> Result<(CompiledCircuit, Duration), OccamError> {
    let started = Instant::now();
    let compiled = CompiledCircuit::new(circuit)?;
    Ok((compiled, started.elapsed()))
}

fn measure_batches(
    batches: usize,
    warmups: usize,
    iterations: usize,
    mut operation: impl FnMut() -> Result<VerificationMetrics, OccamError>,
) -> Result<(Vec<Duration>, Vec<u64>, VerificationMetrics), OccamError> {
    let capacity = batches
        .checked_mul(iterations)
        .ok_or_else(|| OccamError::Validation("benchmark size overflow".into()))?;
    let mut durations = Vec::with_capacity(capacity);
    let mut medians = Vec::with_capacity(batches);
    let mut last_metrics = None;
    for _ in 0..batches {
        for _ in 0..warmups {
            black_box(operation()?);
        }
        let batch_start = durations.len();
        for _ in 0..iterations {
            let started = Instant::now();
            let metrics = operation()?;
            durations.push(started.elapsed());
            black_box(&metrics);
            last_metrics = Some(metrics);
        }
        medians.push(statistics(&durations[batch_start..])?.median_ns);
    }
    Ok((
        durations,
        medians,
        last_metrics.expect("iterations and batches are non-zero"),
    ))
}

fn statistics(durations: &[Duration]) -> Result<TimingStatistics, OccamError> {
    if durations.is_empty() {
        return Err(OccamError::Validation(
            "cannot calculate statistics without measurements".into(),
        ));
    }
    let mut nanos: Vec<_> = durations.iter().copied().map(duration_ns).collect();
    nanos.sort_unstable();
    let total: u128 = nanos.iter().map(|value| u128::from(*value)).sum();
    let median = median_sorted(&nanos);
    let p95_index = (nanos.len() * 95).div_ceil(100).saturating_sub(1);
    let mean = total as f64 / nanos.len() as f64;
    let variance = nanos
        .iter()
        .map(|value| {
            let delta = *value as f64 - mean;
            delta * delta
        })
        .sum::<f64>()
        / nanos.len() as f64;
    let mut deviations: Vec<_> = nanos.iter().map(|value| value.abs_diff(median)).collect();
    deviations.sort_unstable();
    Ok(TimingStatistics {
        minimum_ns: nanos[0],
        mean_ns: mean,
        median_ns: median,
        p95_ns: nanos[p95_index],
        standard_deviation_ns: variance.sqrt(),
        median_absolute_deviation_ns: median_sorted(&deviations),
    })
}

fn median_sorted(values: &[u64]) -> u64 {
    if values.len().is_multiple_of(2) {
        let upper = u128::from(values[values.len() / 2]);
        let lower = u128::from(values[values.len() / 2 - 1]);
        ((lower + upper) / 2).try_into().unwrap_or(u64::MAX)
    } else {
        values[values.len() / 2]
    }
}

fn duration_ns(duration: Duration) -> u64 {
    duration.as_nanos().try_into().unwrap_or(u64::MAX)
}

fn command_output(program: &str, arguments: &[&str]) -> String {
    Command::new(program)
        .args(arguments)
        .output()
        .ok()
        .filter(|output| output.status.success())
        .map(|output| String::from_utf8_lossy(&output.stdout).trim().to_owned())
        .unwrap_or_else(|| "unknown".into())
}

fn operating_system() -> String {
    if cfg!(target_os = "macos") {
        let version = command_output("sw_vers", &["-productVersion"]);
        format!("macOS {version}")
    } else {
        format!(
            "{} {}",
            std::env::consts::OS,
            command_output("uname", &["-r"])
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn calculates_known_statistics() {
        let values = [1, 9, 3, 7, 5].map(Duration::from_nanos).to_vec();
        let result = statistics(&values).unwrap();
        assert_eq!(result.minimum_ns, 1);
        assert_eq!(result.mean_ns, 5.0);
        assert_eq!(result.median_ns, 5);
        assert_eq!(result.p95_ns, 9);
        assert_eq!(result.standard_deviation_ns, 8.0f64.sqrt());
        assert_eq!(result.median_absolute_deviation_ns, 2);
    }

    #[test]
    fn rejects_empty_statistics() {
        assert!(statistics(&[]).is_err());
    }

    #[test]
    fn averages_middle_values_for_even_sample_count() {
        let values = [1, 3, 7, 9].map(Duration::from_nanos).to_vec();
        let result = statistics(&values).unwrap();
        assert_eq!(result.median_ns, 5);
        assert_eq!(result.median_absolute_deviation_ns, 3);
    }
}
