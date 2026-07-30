from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

_MIN_CHAIN_LENGTH = 8
_WINDOW_MULTIPLIER = 5.0
_OBSERVABLES = ("energy", "transverse_magnetization", "m2", "m4")


def _finite_chain(samples: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    values = np.asarray(samples, dtype=np.float64)
    if values.ndim != 1:
        raise ValueError("autocorrelation samples must be one-dimensional")
    if values.size < _MIN_CHAIN_LENGTH:
        raise ValueError(f"autocorrelation chain requires at least {_MIN_CHAIN_LENGTH} values")
    if not np.all(np.isfinite(values)):
        raise ValueError("autocorrelation chain must be finite")
    centered = values - values.mean()
    variance = float(np.dot(centered, centered) / values.size)
    if not math.isfinite(variance) or variance <= 0.0:
        raise ValueError("autocorrelation chain must not be constant")
    return values


def _integrated_time_from_autocorrelation(
    autocorrelation: npt.NDArray[np.float64],
) -> float:
    rho = np.asarray(autocorrelation, dtype=np.float64)
    if (
        rho.ndim != 1
        or rho.size < 2
        or not np.all(np.isfinite(rho))
        or not math.isclose(float(rho[0]), 1.0, rel_tol=1e-12, abs_tol=1e-12)
    ):
        raise ValueError("normalized autocorrelation sequence is invalid")
    tau = -0.5
    accepted = 0
    for even_lag in range(0, rho.size - 1, 2):
        gamma = float(rho[even_lag] + rho[even_lag + 1])
        if gamma <= 0.0:
            break
        tau += gamma
        accepted += 1
        endpoint = even_lag + 1
        if endpoint >= _WINDOW_MULTIPLIER * tau:
            break
    if accepted == 0 or not math.isfinite(tau) or tau <= 0.0:
        raise ValueError("integrated autocorrelation estimate is invalid")
    return tau


def integrated_autocorrelation_time(samples: npt.NDArray[np.float64]) -> float:
    """Estimate τ_int with the actual Geyer IPS and a window cap.

    Under ``τ_int = 1/2 + Σ_{t>=1} ρ(t)``, define
    ``Γ_k = ρ(2k) + ρ(2k+1)`` beginning with ``ρ(0)+ρ(1)`` and compute
    ``τ_int = -1/2 + Σ Γ_k`` over the initial positive Γ sequence. The positive
    sequence is additionally capped when its pair endpoint reaches the
    Sokal-style self-consistent window ``lag >= 5 * τ_int``. The finite-chain
    denominator ``N-lag`` avoids circular/biased large-lag covariance.
    """

    values = _finite_chain(samples)
    centered = values - values.mean()
    count = centered.size
    fft_size = 1 << (2 * count - 1).bit_length()
    spectrum = np.fft.rfft(centered, n=fft_size)
    autocovariance = np.fft.irfft(spectrum * np.conjugate(spectrum), n=fft_size)[:count]
    autocovariance /= np.arange(count, 0, -1, dtype=np.float64)
    if not np.all(np.isfinite(autocovariance)):
        raise ValueError("autocovariance estimate is not finite")
    rho = autocovariance / autocovariance[0]

    return _integrated_time_from_autocorrelation(rho)


def agreement_z_score(
    mean_a: float, error_a: float, mean_b: float, error_b: float
) -> float:
    values = (mean_a, error_a, mean_b, error_b)
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("agreement inputs must be finite")
    if error_a < 0.0 or error_b < 0.0:
        raise ValueError("agreement errors must be non-negative")
    combined = math.hypot(error_a, error_b)
    if combined <= 0.0:
        raise ValueError("agreement requires a positive combined error")
    return abs(mean_a - mean_b) / combined


def summarize_chain(
    samples: npt.NDArray[np.float64],
    *,
    bin_length: int,
    minimum_bin_tau: float = 10.0,
) -> dict[str, float]:
    values = _finite_chain(samples)
    if not isinstance(bin_length, int) or isinstance(bin_length, bool) or bin_length < 1:
        raise ValueError("bin_length must be a positive integer")
    if not math.isfinite(minimum_bin_tau) or minimum_bin_tau <= 0.0:
        raise ValueError("minimum_bin_tau must be finite and positive")
    tau = integrated_autocorrelation_time(values)
    if bin_length < minimum_bin_tau * tau:
        raise ValueError(
            f"bin length must be at least {minimum_bin_tau:g} "
            "integrated autocorrelation times"
        )
    effective_count = values.size / (2.0 * tau)
    standard_error = float(values.std(ddof=1) / math.sqrt(effective_count))
    if not math.isfinite(standard_error) or standard_error <= 0.0:
        raise ValueError("chain standard error must be finite and positive")
    return {
        "mean": float(values.mean()),
        "standard_error": standard_error,
        "tau_int": tau,
        "effective_sample_count": effective_count,
        "bin_count": float(values.size),
    }


def jackknife_binder(
    m2_bin_means: npt.NDArray[np.float64],
    m4_bin_means: npt.NDArray[np.float64],
) -> dict[str, Any]:
    m2 = _finite_chain(m2_bin_means)
    m4 = _finite_chain(m4_bin_means)
    if m2.shape != m4.shape:
        raise ValueError("m2 and m4 chains must have the same shape")
    if np.any(m4 <= 0.0):
        raise ValueError("m4 bin means must be positive")
    count = m2.size
    total_m2 = float(m2.sum())
    total_m4 = float(m4.sum())
    leave_m2 = (total_m2 - m2) / (count - 1)
    leave_m4 = (total_m4 - m4) / (count - 1)
    leave_ratio = leave_m2**2 / leave_m4
    jackknife_error = math.sqrt(
        (count - 1) / count * float(np.sum((leave_ratio - leave_ratio.mean()) ** 2))
    )
    raw_plugin = float(m2.mean() ** 2 / m4.mean())
    pseudo_values = count * raw_plugin - (count - 1) * leave_ratio
    bias_corrected = float(pseudo_values.mean())
    if not math.isfinite(jackknife_error) or jackknife_error <= 0.0:
        raise ValueError("Binder jackknife error must be finite and positive")
    return {
        "mean": bias_corrected,
        "raw_plugin_mean": raw_plugin,
        "standard_error": jackknife_error,
        "leave_one_out": leave_ratio.tolist(),
    }


def _parse_sse_bin(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema_version") != "qmc-sse-bin-v1":
        raise ValueError("expected qmc-sse-bin-v1 record")
    if value.get("adapter") != "QMC_SSE":
        raise ValueError("QMC_SSE bin adapter mismatch")
    return value


def _parse_ltfim_bin(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema_version") != "qmc-ltfim-bin-v1":
        raise ValueError("expected qmc-ltfim-bin-v1 record")
    if value.get("adapter") != "QMC_LTFIM":
        raise ValueError("QMC_LTFIM bin adapter mismatch")
    return value


def _load_bin_records(path: Path, parser: Any) -> list[dict[str, Any]]:
    files = sorted(Path(path).glob("*.ndjson"))
    if not files:
        raise ValueError("no immutable bin files found")
    records = []
    for bin_path in files:
        payload = bin_path.read_bytes()
        if not payload.endswith(b"\n") or payload.count(b"\n") != 1:
            raise ValueError("bin object must contain one newline-terminated JSON record")
        records.append(parser(json.loads(payload)))
    records.sort(key=lambda record: record["bin_index"])
    return records


def summarize_bin_records(
    records: list[dict[str, Any]],
    *,
    analysis_bin_length_samples: int,
    serial_measurement_stride_samples: int,
    minimum_analysis_bin_tau_ratio: float = 10.0,
) -> dict[str, Any]:
    if len(records) < 2 * _MIN_CHAIN_LENGTH:
        raise ValueError("at least 16 bins are required for chain and half diagnostics")
    indices = [record["bin_index"] for record in records]
    if indices != list(range(len(records))):
        raise ValueError("bin indices must be contiguous and start at zero")
    sample_counts = [record["sample_count"] for record in records]
    if any(count != analysis_bin_length_samples for count in sample_counts):
        raise ValueError("every immutable bin must have the pre-registered bin length")
    if (
        not isinstance(serial_measurement_stride_samples, int)
        or isinstance(serial_measurement_stride_samples, bool)
        or serial_measurement_stride_samples < 1
        or analysis_bin_length_samples % serial_measurement_stride_samples != 0
    ):
        raise ValueError("serial measurement stride must exactly divide analysis bins")
    if (
        not math.isfinite(minimum_analysis_bin_tau_ratio)
        or minimum_analysis_bin_tau_ratio <= 0.0
    ):
        raise ValueError("minimum analysis-bin tau ratio must be finite and positive")
    serial_per_bin = analysis_bin_length_samples // serial_measurement_stride_samples
    for record in records:
        if (
            record.get("serial_measurement_stride_samples")
            != serial_measurement_stride_samples
        ):
            raise ValueError("serial measurement stride mismatch")
        observations = record.get("serial_observations")
        if not isinstance(observations, dict) or set(observations) != set(_OBSERVABLES):
            raise ValueError("serial observations must contain every primitive observable")
        for name in _OBSERVABLES:
            if len(observations[name]) != serial_per_bin:
                raise ValueError("serial observation count does not match declared cadence")

    analysis_bins = {
        name: np.asarray(
            [record[f"{name}_sum"] / record["sample_count"] for record in records],
            dtype=np.float64,
        )
        for name in _OBSERVABLES
    }
    serial_chains = {
        name: np.asarray(
            [
                value
                for record in records
                for value in record["serial_observations"][name]
            ],
            dtype=np.float64,
        )
        for name in _OBSERVABLES
    }

    def analysis_summary(values: npt.NDArray[np.float64]) -> dict[str, float]:
        values = _finite_chain(values)
        error = float(values.std(ddof=1) / math.sqrt(values.size))
        if not math.isfinite(error) or error <= 0.0:
            raise ValueError("analysis-bin standard error must be finite and positive")
        return {"mean": float(values.mean()), "standard_error": error}

    def tau_samples(values: npt.NDArray[np.float64]) -> float:
        return (
            integrated_autocorrelation_time(values)
            * serial_measurement_stride_samples
        )

    def enforce_tau(tau: float, name: str) -> None:
        if (
            analysis_bin_length_samples
            < minimum_analysis_bin_tau_ratio * tau
        ):
            raise ValueError(
                f"analysis bin length in retained-sample units must be at least "
                f"{minimum_analysis_bin_tau_ratio:g} {name} autocorrelation times"
            )

    observables: dict[str, dict[str, Any]] = {}
    midpoint = len(records) // 2
    for name, values in analysis_bins.items():
        tau = tau_samples(serial_chains[name])
        enforce_tau(tau, name)
        whole = analysis_summary(values)
        first = analysis_summary(values[:midpoint])
        second = analysis_summary(values[midpoint:])
        whole.update(
            {
                "tau_int_samples": tau,
                "effective_sample_count": len(serial_chains[name]) / (2.0 * tau),
                "serial_sample_count": len(serial_chains[name]),
                "serial_measurement_stride_samples": serial_measurement_stride_samples,
                "analysis_bin_length_samples": analysis_bin_length_samples,
                "analysis_bin_tau_ratio": analysis_bin_length_samples / tau,
            }
        )
        whole["half_agreement_z"] = agreement_z_score(
            first["mean"], first["standard_error"], second["mean"], second["standard_error"]
        )
        observables[name] = whole

    m2_serial, m4_serial = serial_chains["m2"], serial_chains["m4"]
    mean_m2, mean_m4 = float(m2_serial.mean()), float(m4_serial.mean())
    influence = (
        2.0 * mean_m2 / mean_m4 * (m2_serial - mean_m2)
        - mean_m2**2 / mean_m4**2 * (m4_serial - mean_m4)
    )
    binder_tau = tau_samples(np.asarray(influence, dtype=np.float64))
    enforce_tau(binder_tau, "Binder")
    binder = jackknife_binder(analysis_bins["m2"], analysis_bins["m4"])
    first_binder = jackknife_binder(
        analysis_bins["m2"][:midpoint], analysis_bins["m4"][:midpoint]
    )
    second_binder = jackknife_binder(
        analysis_bins["m2"][midpoint:], analysis_bins["m4"][midpoint:]
    )
    binder.update(
        {
            "tau_int_samples": binder_tau,
            "effective_sample_count": len(influence) / (2.0 * binder_tau),
            "serial_sample_count": len(influence),
            "serial_measurement_stride_samples": serial_measurement_stride_samples,
            "analysis_bin_length_samples": analysis_bin_length_samples,
            "analysis_bin_tau_ratio": analysis_bin_length_samples / binder_tau,
        }
    )
    binder["half_agreement_z"] = agreement_z_score(
        first_binder["mean"],
        first_binder["standard_error"],
        second_binder["mean"],
        second_binder["standard_error"],
    )
    binder.pop("leave_one_out")
    observables["binder_ratio"] = binder
    return {"bin_count": len(records), "observables": observables}


def summarize_qmc_sse_bins(path: Path, *, bin_length: int = 1) -> dict[str, Any]:
    return summarize_bin_records(
        _load_bin_records(Path(path), _parse_sse_bin),
        analysis_bin_length_samples=bin_length,
        serial_measurement_stride_samples=1,
    )


def summarize_qmc_ltfim_bins(path: Path, *, bin_length: int = 1) -> dict[str, Any]:
    return summarize_bin_records(
        _load_bin_records(Path(path), _parse_ltfim_bin),
        analysis_bin_length_samples=bin_length,
        serial_measurement_stride_samples=1,
    )
