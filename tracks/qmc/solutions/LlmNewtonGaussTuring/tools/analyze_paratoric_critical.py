# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Protocol Revision 7 analysis for ParaToric critical raw series."""

from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

import analyze_stage4 as corrected
import run_paratoric_critical as critical


REGISTERED_L_MIN = {
    "triangular": (8, 12, 16),
    "honeycomb": (10, 12, 16),
}
REGISTERED_OMEGAS = (0.80, 0.83, 0.86)
BASE_OMEGA = 0.83
BOOTSTRAP_FAILURE_MAX = 0.01
CHI2_DOF_MAX = 3.0
CONDITION_MAX = 1.0e12
SAMPLING_Z_MAX = 5.0
ERROR_RATIO_MIN = 0.5
ERROR_RATIO_MAX = 2.0
MIN_BLOCKS = 8
MIN_EFFECTIVE_SAMPLES = 1000.0
PREFIX_FRACTIONS = (0.10, 0.20)
PRECISION_LIMIT = {"triangular": 1.8e-5, "honeycomb": 8.0e-6}
OBSERVABLES = ("U_pi", "U_sit")


def binder_value(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    second = float(np.mean(values**2))
    fourth = float(np.mean(values**4))
    if not math.isfinite(second) or not math.isfinite(fourth) or second <= 1e-30:
        return math.nan
    return fourth / second**2


def _json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _expected_cells(target: str) -> set[tuple[int, float, int]]:
    axes = critical.plan_axes(target, "production")
    return {
        (int(size), float(field), int(chain))
        for size in axes["L"]
        for field in axes["field"]
        for chain in axes["chain"]
    }


def load_production(
    spec_path: Path,
) -> tuple[dict[str, Any], dict[tuple[int, float], dict[int, np.ndarray]], dict]:
    spec_path = spec_path.resolve()
    spec = critical.load_spec(spec_path)
    settings = spec.get("settings", {})
    if settings.get("purpose") != "production":
        raise ValueError("Revision 7 analysis requires a production run spec")
    if int(settings.get("samples_per_chain", 0)) != 30000:
        raise ValueError("production must contain 30,000 stored samples per chain")
    target = spec.get("provenance", {}).get("target_lattice")
    if target not in REGISTERED_L_MIN:
        raise ValueError(f"invalid target lattice {target!r}")
    planned = {
        (int(cell["params"]["L"]), float(cell["params"]["field"]),
         int(cell["params"]["chain"]))
        for cell in spec["cells"]
    }
    if planned != _expected_cells(target):
        raise ValueError("production run spec differs from the frozen Revision 7 grid")

    run_dir = critical.resolve_run_dir(spec, spec_path)
    cells: dict[tuple[int, float], dict[int, np.ndarray]] = defaultdict(dict)
    metadata: dict[tuple[int, float, int], dict[str, Any]] = {}
    seeds: set[int] = set()
    for cell in spec["cells"]:
        manifest, raw_path = critical.validate_manifest(spec, cell, run_dir)
        params = cell["params"]
        size = int(params["L"])
        field = float(params["field"])
        chain = int(params["chain"])
        seed = int(params["seed"])
        if seed in seeds:
            raise ValueError(f"production seed {seed} is reused")
        seeds.add(seed)
        expected_thermal = 500 * size**3
        expected_between = 8 * size**3
        actual = manifest["settings"]
        if (int(actual.get("n_thermal", 0)) != expected_thermal
                or int(actual.get("updates_between", 0)) != expected_between):
            raise ValueError(f"cell {(size, field, chain)} violates production cadence")
        values = np.loadtxt(
            raw_path, delimiter=",", skiprows=1, usecols=(12, 13, 14), ndmin=2
        )
        if values.shape != (30000, 3) or not np.all(np.isfinite(values)):
            raise ValueError(f"cell {(size, field, chain)} has malformed raw values")
        if chain in cells[(size, field)]:
            raise ValueError(f"duplicate chain {chain} at {(size, field)}")
        cells[(size, field)][chain] = values
        metadata[(size, field, chain)] = {
            "seed": seed,
            "raw_path": str(raw_path),
            "raw_sha256": manifest["artifacts"]["raw"]["sha256"],
            "package_tau": manifest["diagnostics"]["package_tau_int"],
            "wall_seconds": manifest["wall_seconds"],
        }
    if any(set(chain_map) != {0, 1, 2, 3} for chain_map in cells.values()):
        raise ValueError("every production point must contain chains 0,1,2,3")
    return spec, dict(cells), metadata


def chain_taus(values: np.ndarray) -> np.ndarray:
    if values.ndim != 2 or values.shape[1] != 3:
        raise ValueError("ParaToric chain data must have three observable columns")
    return np.asarray([corrected.tau_int(values[:, index]) for index in range(3)])


def cell_block(chain_map: dict[int, np.ndarray]) -> tuple[int, dict[int, np.ndarray]]:
    taus = {chain: chain_taus(values) for chain, values in chain_map.items()}
    maximum = max(float(np.max(value)) for value in taus.values())
    return max(1, int(math.ceil(2.0 * maximum))), taus


def resample_cell(
    chain_map: dict[int, np.ndarray], block: int, rng: np.random.Generator
) -> np.ndarray:
    chains = sorted(chain_map)
    selected = rng.integers(0, len(chains), len(chains))
    return np.concatenate([
        corrected.circular_block_resample(chain_map[chains[index]], block, rng)
        for index in selected
    ])


def point_estimate(
    chain_map: dict[int, np.ndarray], n_boot: int, rng: np.random.Generator
) -> tuple[dict[str, Any], dict[int, np.ndarray]]:
    if set(chain_map) != {0, 1, 2, 3}:
        raise ValueError("a ParaToric point must contain four chains")
    block, taus = cell_block(chain_map)
    pooled = np.concatenate([chain_map[chain] for chain in sorted(chain_map)])
    primary = binder_value(pooled[:, 0])
    support = binder_value(pooled[:, 1])
    samples = np.empty((n_boot, 2))
    for index in range(n_boot):
        resampled = resample_cell(chain_map, block, rng)
        samples[index, 0] = binder_value(resampled[:, 0])
        samples[index, 1] = binder_value(resampled[:, 1])
    if not np.all(np.isfinite(samples)):
        raise ValueError("point bootstrap produced a non-finite Binder statistic")
    errors = np.std(samples, axis=0, ddof=1)
    if not np.all(np.isfinite(errors)) or np.any(errors <= 0.0):
        raise ValueError("point bootstrap produced a non-positive uncertainty")
    return {
        "U_pi": primary,
        "U_pi_err": float(errors[0]),
        "U_pi_boot": samples[:, 0],
        "U_sit": support,
        "U_sit_err": float(errors[1]),
        "U_sit_boot": samples[:, 1],
        "percolation_mean": float(np.mean(pooled[:, 0])),
        "sit_mean": float(np.mean(pooled[:, 1])),
        "block": block,
        "chains": len(chain_map),
    }, taus


def _ratio_bounds(base: np.ndarray, doubled: np.ndarray) -> tuple[float, float]:
    ratios = []
    for first, second in zip(base, doubled):
        if not np.isfinite(first) or not np.isfinite(second):
            return 0.0, math.inf
        if first <= 0.0 and second <= 0.0:
            ratios.append(1.0)
        elif first <= 0.0 or second <= 0.0:
            return 0.0, math.inf
        else:
            ratios.append(second / first)
    return float(min(ratios, default=0.0)), float(max(ratios, default=math.inf))


def sampling_diagnostic(
    chain_map: dict[int, np.ndarray], block: int, taus: dict[int, np.ndarray]
) -> dict[str, Any]:
    stationarity = []
    base_blocks = []
    doubled_blocks = []
    per_chain_blocks = []
    minimum_blocks = math.inf
    minimum_primary_ess = math.inf
    minimum_sit_ess = math.inf
    for chain, values in sorted(chain_map.items()):
        base = corrected._blocked_means(values, block)
        doubled = corrected._blocked_means(values, 2 * block)
        minimum_blocks = min(minimum_blocks, len(values) // block)
        minimum_primary_ess = min(
            minimum_primary_ess, len(values) / (2.0 * taus[chain][0])
        )
        minimum_sit_ess = min(
            minimum_sit_ess, len(values) / (2.0 * taus[chain][1])
        )
        midpoint = len(base) // 2
        if midpoint >= 2 and len(base) - midpoint >= 2:
            stationarity.append(
                corrected._difference_z(base[:midpoint], base[midpoint:])
            )
        base_blocks.append(base)
        doubled_blocks.append(doubled)
        per_chain_blocks.append((chain, base))
    combined_base = np.concatenate(base_blocks)
    combined_doubled = np.concatenate(doubled_blocks)
    reblock_z = corrected._difference_z(combined_base, combined_doubled)
    base_error = corrected._standard_error(combined_base)
    doubled_error = corrected._standard_error(combined_doubled)
    ratio_min, ratio_max = _ratio_bounds(base_error, doubled_error)
    chain_spread = max(
        corrected._difference_z(
            values,
            np.concatenate([
                other for other_chain, other in per_chain_blocks
                if other_chain != chain
            ]),
        )
        for chain, values in per_chain_blocks
    )
    stationarity_z = max(stationarity, default=math.inf)
    passed = (
        minimum_blocks >= MIN_BLOCKS
        and minimum_primary_ess >= MIN_EFFECTIVE_SAMPLES
        and minimum_sit_ess >= MIN_EFFECTIVE_SAMPLES
        and stationarity_z <= SAMPLING_Z_MAX
        and reblock_z <= SAMPLING_Z_MAX
        and chain_spread <= SAMPLING_Z_MAX
        and ratio_min >= ERROR_RATIO_MIN
        and ratio_max <= ERROR_RATIO_MAX
    )
    return {
        "block": block,
        "minimum_blocks": int(minimum_blocks),
        "minimum_primary_ess": float(minimum_primary_ess),
        "minimum_sit_ess": float(minimum_sit_ess),
        "stationarity_z_max": float(stationarity_z),
        "reblock_z_max": float(reblock_z),
        "error_ratio_min": ratio_min,
        "error_ratio_max": ratio_max,
        "chain_spread_z_max": float(chain_spread),
        "passed": bool(passed),
    }


def analyze_cells(
    cells: dict[tuple[int, float], dict[int, np.ndarray]],
    n_boot: int,
    seed: int,
    progress_label: str,
) -> tuple[dict[tuple[int, float], dict[str, Any]], list[dict], list[dict]]:
    rng = np.random.default_rng(seed)
    points = {}
    chain_rows = []
    sampling_rows = []
    for index, key in enumerate(sorted(cells), start=1):
        point, taus = point_estimate(cells[key], n_boot, rng)
        points[key] = point
        diagnostic = sampling_diagnostic(cells[key], point["block"], taus)
        sampling_rows.append({"L": key[0], "field": key[1], **diagnostic})
        for chain, values in sorted(cells[key].items()):
            chain_rows.append({
                "L": key[0], "field": key[1], "chain": chain,
                "samples": len(values), "block": point["block"],
                "tau_percolation": float(taus[chain][0]),
                "tau_sit": float(taus[chain][1]),
                "tau_star": float(taus[chain][2]),
                "effective_percolation": len(values) / (2.0 * taus[chain][0]),
                "effective_sit": len(values) / (2.0 * taus[chain][1]),
                "star_defect": float(np.max(np.abs(values[:, 2] - 1.0))),
            })
        print(
            f"{progress_label}: point {index}/{len(cells)} L={key[0]} "
            f"g={key[1]:.3f} block={point['block']}",
            flush=True,
        )
    return points, chain_rows, sampling_rows


def fit_variant(
    points: dict[tuple[int, float], dict[str, Any]],
    observable: str,
    l_min: int,
    omega: float,
    include_mixed: bool,
    n_boot: int,
) -> dict[str, Any]:
    keys = sorted(key for key in points if key[0] >= l_min)
    error_name = f"{observable}_err"
    boot_name = f"{observable}_boot"
    sizes = np.asarray([key[0] for key in keys], dtype=float)
    fields = np.asarray([key[1] for key in keys], dtype=float)
    values = np.asarray([points[key][observable] for key in keys], dtype=float)
    errors = np.asarray([points[key][error_name] for key in keys], dtype=float)
    result = {
        "observable": observable,
        "L_min": l_min,
        "omega": omega,
        "include_mixed": include_mixed,
        "n_points": len(keys),
        "status": "failed",
        "failure": "",
    }
    try:
        hc, chi2, dof, coeff, rank, condition = corrected.fit_hc(
            sizes, fields, values, errors, omega, include_mixed
        )
    except ValueError as error:
        result["failure"] = str(error)
        return result
    samples = []
    failed = 0
    for sample in range(n_boot):
        sampled = np.asarray([points[key][boot_name][sample] for key in keys])
        if not np.all(np.isfinite(sampled)):
            failed += 1
            continue
        try:
            samples.append(corrected.fit_hc(
                sizes, fields, sampled, errors, omega, include_mixed
            )[0])
        except ValueError:
            failed += 1
    if len(samples) < 2:
        result["failure"] = "fewer than two successful bootstrap fits"
        return result
    distribution = np.asarray(samples)
    ci_low, ci_high = np.quantile(distribution, [0.025, 0.975])
    failure_rate = failed / n_boot
    chi2_per_dof = chi2 / dof
    passed = (
        failure_rate <= BOOTSTRAP_FAILURE_MAX
        and rank == len(coeff)
        and condition <= CONDITION_MAX
        and chi2_per_dof <= CHI2_DOF_MAX
    )
    result.update({
        "status": "ok",
        "hc": hc,
        "hc_boot_error": float(np.std(distribution, ddof=1)),
        "hc_ci_low": float(ci_low),
        "hc_ci_high": float(ci_high),
        "chi2": chi2,
        "dof": dof,
        "chi2_per_dof": chi2_per_dof,
        "rank": rank,
        "condition": condition,
        "coefficients": coeff.tolist(),
        "bootstrap_success": len(samples),
        "bootstrap_failed": failed,
        "bootstrap_failure_rate": failure_rate,
        "fit_gate_passed": bool(passed),
    })
    return result


def fit_matrix(points, target: str, n_boot: int) -> list[dict[str, Any]]:
    rows = []
    total = len(OBSERVABLES) * len(REGISTERED_L_MIN[target]) * 2 * len(REGISTERED_OMEGAS)
    index = 0
    for observable in OBSERVABLES:
        for l_min in REGISTERED_L_MIN[target]:
            for include_mixed in (True, False):
                for omega in REGISTERED_OMEGAS:
                    index += 1
                    row = fit_variant(
                        points, observable, l_min, omega, include_mixed, n_boot
                    )
                    rows.append(row)
                    print(
                        f"fit {index}/{total}: {observable} L_min={l_min} "
                        f"omega={omega:.2f} mixed={int(include_mixed)} "
                        f"status={row['status']}",
                        flush=True,
                    )
    return rows


def main_fit(rows: list[dict], target: str, observable: str) -> dict:
    matches = [
        row for row in rows
        if row["observable"] == observable
        and row["L_min"] == REGISTERED_L_MIN[target][0]
        and math.isclose(row["omega"], BASE_OMEGA)
        and row["include_mixed"]
    ]
    if len(matches) != 1:
        raise ValueError(f"missing unique primary variant for {observable}")
    return matches[0]


def total_uncertainty(
    rows: list[dict], target: str, observable: str
) -> tuple[float, float]:
    reference = main_fit(rows, target, observable)
    if reference.get("status") != "ok":
        return math.nan, math.nan
    variants = [row for row in rows if row["observable"] == observable]
    if any(row.get("status") != "ok" for row in variants):
        return math.nan, math.nan
    shift = max(abs(row["hc"] - reference["hc"]) for row in variants)
    total = math.hypot(reference["hc_boot_error"], shift)
    return shift, total


def bracketing_rows(points: dict[tuple[int, float], dict[str, Any]]) -> list[dict]:
    rows = []
    for size in sorted({key[0] for key in points}):
        count = sum(
            0.05 < point["percolation_mean"] < 0.95
            for (candidate, _), point in points.items() if candidate == size
        )
        rows.append({"L": size, "interior_fields": count, "passed": count >= 2})
    return rows


def prefix_diagnostics(
    cells: dict[tuple[int, float], dict[int, np.ndarray]],
    reference_rows: list[dict],
    target: str,
    n_boot: int,
    seed: int,
) -> list[dict]:
    output = []
    for prefix_index, fraction in enumerate(PREFIX_FRACTIONS):
        shortened = {
            key: {
                chain: values[int(math.floor(fraction * len(values))):]
                for chain, values in chain_map.items()
            }
            for key, chain_map in cells.items()
        }
        points, _, _ = analyze_cells(
            shortened, n_boot, seed + 10000 * (prefix_index + 1),
            f"prefix {fraction:.0%}",
        )
        for observable in OBSERVABLES:
            reference = main_fit(reference_rows, target, observable)
            fit = fit_variant(
                points, observable, REGISTERED_L_MIN[target][0], BASE_OMEGA,
                True, n_boot,
            )
            row = {"discard_fraction": fraction, "observable": observable}
            if reference.get("status") != "ok" or fit.get("status") != "ok":
                row.update({
                    "status": "failed",
                    "failure": fit.get("failure", "reference fit failed"),
                    "passed": False,
                })
            else:
                shift = fit["hc"] - reference["hc"]
                combined = math.hypot(
                    reference["hc_boot_error"], fit["hc_boot_error"]
                )
                z_value = abs(shift) / combined if combined > 0.0 else math.inf
                row.update({
                    "status": "ok", "failure": "",
                    "reference_hc": reference["hc"],
                    "reference_error": reference["hc_boot_error"],
                    "discarded_hc": fit["hc"],
                    "discarded_error": fit["hc_boot_error"],
                    "shift": shift, "combined_error": combined,
                    "shift_z": z_value, "passed": z_value <= SAMPLING_Z_MAX,
                })
            output.append(row)
    return output


def crossing_diagnostics(
    points: dict[tuple[int, float], dict[str, Any]], n_boot: int
) -> tuple[list[dict], dict[str, dict[str, Any]]]:
    sizes = sorted({key[0] for key in points})
    rows = []
    drift = {}
    exponent = 1.0 / corrected.NU + BASE_OMEGA
    for observable in OBSERVABLES:
        obs_rows = []
        crossing_boot = []
        for first, second in zip(sizes, sizes[1:]):
            fields = np.asarray(sorted(
                field for size, field in points
                if size == first and (second, field) in points
            ))
            first_values = np.asarray([points[(first, field)][observable] for field in fields])
            second_values = np.asarray([points[(second, field)][observable] for field in fields])
            estimate = corrected.crossing(fields, first_values, second_values)
            samples = np.full(n_boot, np.nan)
            for sample in range(n_boot):
                samples[sample] = corrected.crossing(
                    fields,
                    np.asarray([points[(first, field)][f"{observable}_boot"][sample]
                                for field in fields]),
                    np.asarray([points[(second, field)][f"{observable}_boot"][sample]
                                for field in fields]),
                )
            finite = samples[np.isfinite(samples)]
            error = float(np.std(finite, ddof=1)) if len(finite) >= 2 else math.nan
            ci = np.quantile(finite, [0.025, 0.975]) if len(finite) >= 2 else (math.nan, math.nan)
            row = {
                "observable": observable, "L1": first, "L2": second,
                "h_cross": float(estimate), "h_cross_error": error,
                "h_cross_ci_low": float(ci[0]), "h_cross_ci_high": float(ci[1]),
                "bootstrap_success": len(finite),
                "bootstrap_failed": n_boot - len(finite),
                "drift_x": first ** (-exponent),
            }
            rows.append(row)
            obs_rows.append(row)
            crossing_boot.append(samples)
        valid = [row for row in obs_rows if math.isfinite(row["h_cross"])]
        summary = {"exponent": exponent, "status": "failed"}
        if len(valid) >= 2:
            x = np.asarray([row["drift_x"] for row in valid])
            y = np.asarray([row["h_cross"] for row in valid])
            matrix = np.column_stack([np.ones_like(x), x])
            coeff, *_ = np.linalg.lstsq(matrix, y, rcond=None)
            bootstrap_intercepts = []
            valid_indices = [obs_rows.index(row) for row in valid]
            for sample in range(n_boot):
                sample_y = np.asarray([
                    crossing_boot[index][sample] for index in valid_indices
                ])
                if np.all(np.isfinite(sample_y)):
                    sample_coeff, *_ = np.linalg.lstsq(matrix, sample_y, rcond=None)
                    bootstrap_intercepts.append(float(sample_coeff[0]))
            summary.update({
                "status": "ok", "hc_intercept": float(coeff[0]),
                "slope": float(coeff[1]),
                "hc_boot_error": (
                    float(np.std(bootstrap_intercepts, ddof=1))
                    if len(bootstrap_intercepts) >= 2 else math.nan
                ),
                "bootstrap_success": len(bootstrap_intercepts),
                "bootstrap_failed": n_boot - len(bootstrap_intercepts),
            })
        drift[observable] = summary
    return rows, drift


def load_direct_summary(path: Path | None, target: str) -> dict[str, Any]:
    if path is None:
        return {"provided": False, "accepted": False, "reason": "not provided"}
    path = path.resolve()
    payload = _json(path)
    required = {"protocol_id", "target_lattice", "hc", "total_error", "accepted"}
    missing = required - set(payload)
    if missing:
        raise ValueError(f"direct summary is missing {sorted(missing)}")
    if payload["protocol_id"] != critical.PROTOCOL_ID:
        raise ValueError("direct summary uses the wrong protocol identifier")
    if payload["target_lattice"] != target:
        raise ValueError("direct summary target differs from ParaToric production")
    hc = float(payload["hc"])
    error = float(payload["total_error"])
    if not math.isfinite(hc) or not math.isfinite(error) or error <= 0.0:
        raise ValueError("direct summary contains an invalid field or uncertainty")
    return {
        "provided": True, "accepted": bool(payload["accepted"]),
        "hc": hc, "total_error": error,
        "path": str(path), "sha256": critical.sha256_file(path),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames and key not in {"U_pi_boot", "U_sit_boot"}:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: json.dumps(value, separators=(",", ":"))
                if isinstance(value, (list, dict)) else value
                for key, value in row.items()
            })


def plot_diagnostics(
    prefix: Path,
    points: dict[tuple[int, float], dict[str, Any]],
    fits: list[dict[str, Any]],
    target: str,
) -> tuple[Path, Path]:
    sizes = sorted({key[0] for key in points})
    crossings_path = prefix.with_name(prefix.name + "_crossings.png")
    residuals_path = prefix.with_name(prefix.name + "_residuals.png")
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    for axis, observable, ylabel in zip(
        axes, OBSERVABLES, ("winding Binder U", "SIT Binder U")
    ):
        for size in sizes:
            rows = sorted(
                (field, point) for (candidate, field), point in points.items()
                if candidate == size
            )
            axis.errorbar(
                [row[0] for row in rows],
                [row[1][observable] for row in rows],
                yerr=[row[1][f"{observable}_err"] for row in rows],
                marker="o", markersize=3, label=f"L={size}",
            )
        axis.set(xlabel="target field g", ylabel=ylabel)
        axis.legend(ncol=2, fontsize=8)
    figure.savefig(crossings_path, dpi=180)
    plt.close(figure)

    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    for axis, observable in zip(axes, OBSERVABLES):
        result = main_fit(fits, target, observable)
        if result.get("status") != "ok":
            axis.text(0.5, 0.5, f"{observable} fit failed", ha="center", va="center")
            axis.set_axis_off()
            continue
        coefficients = np.asarray(result["coefficients"])
        for size in sizes:
            rows = sorted(
                (field, point) for (candidate, field), point in points.items()
                if candidate == size
            )
            fields = np.asarray([row[0] for row in rows])
            values = np.asarray([row[1][observable] for row in rows])
            errors = np.asarray([row[1][f"{observable}_err"] for row in rows])
            lengths = np.full_like(fields, float(size))
            model = corrected.design_matrix(
                lengths, fields, result["hc"], BASE_OMEGA, True
            ) @ coefficients
            axis.plot(
                (fields - result["hc"]) * lengths ** (1.0 / corrected.NU),
                (values - model) / errors, "o", markersize=3, label=f"L={size}",
            )
        axis.axhline(0.0, color="black", linewidth=0.8)
        axis.axhline(2.0, color="0.6", linewidth=0.7, linestyle="--")
        axis.axhline(-2.0, color="0.6", linewidth=0.7, linestyle="--")
        axis.set(xlabel="(g-g_c)L^(1/nu)", ylabel="standardized residual",
                 title=observable)
        axis.legend(ncol=2, fontsize=8)
    figure.savefig(residuals_path, dpi=180)
    plt.close(figure)
    return crossings_path, residuals_path


def build_summary(
    spec: dict[str, Any], fits: list[dict], sampling: list[dict],
    bracketing: list[dict], prefixes: list[dict], drift: dict,
    direct: dict, artifacts: dict, n_boot: int, seed: int,
) -> dict[str, Any]:
    target = spec["provenance"]["target_lattice"]
    primary = main_fit(fits, target, "U_pi")
    support = main_fit(fits, target, "U_sit")
    primary_variant, primary_total = total_uncertainty(fits, target, "U_pi")
    support_variant, support_total = total_uncertainty(fits, target, "U_sit")
    fit_gate = all(
        row.get("status") == "ok" and row.get("fit_gate_passed", False)
        for row in fits
    )
    sampling_gate = all(row["passed"] for row in sampling)
    bracketing_gate = all(row["passed"] for row in bracketing)
    prefix_gate = all(row["passed"] for row in prefixes)
    star_gate = all(row.get("star_defect", 0.0) <= 1e-12 for row in artifacts["chains"])
    observable_combined = math.hypot(primary_total, support_total)
    observable_z = (
        abs(primary.get("hc", math.nan) - support.get("hc", math.nan))
        / observable_combined if observable_combined > 0.0 else math.inf
    )
    observable_gate = math.isfinite(observable_z) and observable_z <= 3.0
    precision_gate = (
        math.isfinite(primary_total) and primary_total <= PRECISION_LIMIT[target]
    )
    direct_z = math.inf
    direct_gate = False
    if direct.get("provided") and direct.get("accepted") and math.isfinite(primary_total):
        combined = math.hypot(primary_total, direct["total_error"])
        direct_z = abs(primary["hc"] - direct["hc"]) / combined
        direct_gate = math.isfinite(direct_z) and direct_z <= 3.0
    internal = (
        sampling_gate and bracketing_gate and fit_gate and prefix_gate
        and star_gate and observable_gate and precision_gate
    )
    accepted = internal and direct_gate
    return {
        "schema_version": "challenge148-paratoric-critical-analysis-v1",
        "protocol_id": critical.PROTOCOL_ID,
        "run_id": spec["run_id"],
        "target_lattice": target,
        "analysis_settings": {
            "bootstrap_resamples": n_boot,
            "bootstrap_seed": seed,
            "nu": corrected.NU,
            "base_omega": BASE_OMEGA,
            "registered_omegas": list(REGISTERED_OMEGAS),
            "registered_L_min": list(REGISTERED_L_MIN[target]),
            "python": platform.python_version(),
            "numpy": np.__version__,
        },
        "provenance": {
            "source_commit": spec["provenance"].get("source_commit"),
            "sampler_sha256": spec["settings"].get("sampler_sha256"),
            "paratoric_commit": spec["provenance"].get("paratoric_commit"),
            "paratoric_external_patch_sha256": spec["provenance"].get(
                "paratoric_external_patch_sha256"
            ),
        },
        "primary": {
            "observable": "U_pi", "hc": primary.get("hc"),
            "bootstrap_error": primary.get("hc_boot_error"),
            "variant_shift": primary_variant, "total_error": primary_total,
            "precision_limit": PRECISION_LIMIT[target],
        },
        "supporting": {
            "observable": "U_sit", "hc": support.get("hc"),
            "bootstrap_error": support.get("hc_boot_error"),
            "variant_shift": support_variant, "total_error": support_total,
        },
        "gates": {
            "star_sector": star_gate,
            "sampling": sampling_gate,
            "bracketing": bracketing_gate,
            "registered_fits": fit_gate,
            "prefix_stability": prefix_gate,
            "observable_agreement": observable_gate,
            "observable_agreement_z": observable_z,
            "primary_precision": precision_gate,
            "direct_route_accepted": bool(direct.get("accepted", False)),
            "direct_route_agreement": direct_gate,
            "direct_route_agreement_z": direct_z,
        },
        "internal_gates_passed": internal,
        "independent_route_accepted": accepted,
        "direct_route": direct,
        "crossing_drift": drift,
        "artifacts": {key: value for key, value in artifacts.items() if key != "chains"},
        "ratio_computed": False,
        "command": [sys.executable, *sys.argv],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_spec", type=Path)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260729)
    parser.add_argument("--output-prefix", type=Path)
    parser.add_argument("--direct-summary", type=Path)
    parser.add_argument("--enforce-protocol", action="store_true")
    args = parser.parse_args()
    if args.bootstrap < 2:
        parser.error("--bootstrap must be at least two")

    spec, cells, metadata = load_production(args.run_spec)
    run_dir = critical.resolve_run_dir(spec, args.run_spec.resolve())
    prefix = (
        args.output_prefix.resolve() if args.output_prefix
        else run_dir / f"{spec['run_id']}_analysis"
    )
    points, chains, sampling = analyze_cells(
        cells, args.bootstrap, args.seed, "full"
    )
    for row in chains:
        item = metadata[(int(row["L"]), float(row["field"]), int(row["chain"]))]
        row.update({
            "seed": item["seed"], "raw_path": item["raw_path"],
            "raw_sha256": item["raw_sha256"],
            "package_tau_percolation": item["package_tau"]["percolation"],
            "package_tau_sit": item["package_tau"]["sit"],
            "package_tau_star": item["package_tau"]["star"],
            "wall_seconds": item["wall_seconds"],
        })
    target = spec["provenance"]["target_lattice"]
    brackets = bracketing_rows(points)
    fits = fit_matrix(points, target, args.bootstrap)
    prefixes = prefix_diagnostics(
        cells, fits, target, args.bootstrap, args.seed
    )
    crossing_rows, drift = crossing_diagnostics(points, args.bootstrap)

    point_rows = [
        {
            "L": key[0], "field": key[1],
            "U_pi": point["U_pi"], "U_pi_err": point["U_pi_err"],
            "U_sit": point["U_sit"], "U_sit_err": point["U_sit_err"],
            "percolation_mean": point["percolation_mean"],
            "sit_mean": point["sit_mean"], "block": point["block"],
            "chains": point["chains"],
        }
        for key, point in sorted(points.items())
    ]
    paths = {
        "points": prefix.with_name(prefix.name + "_points.csv"),
        "chains": prefix.with_name(prefix.name + "_chains.csv"),
        "sampling": prefix.with_name(prefix.name + "_sampling_gates.csv"),
        "bracketing": prefix.with_name(prefix.name + "_bracketing.csv"),
        "fits": prefix.with_name(prefix.name + "_fits.csv"),
        "prefix": prefix.with_name(prefix.name + "_prefix_stability.csv"),
        "crossings": prefix.with_name(prefix.name + "_crossings.csv"),
    }
    for name, rows in (
        ("points", point_rows), ("chains", chains), ("sampling", sampling),
        ("bracketing", brackets), ("fits", fits), ("prefix", prefixes),
        ("crossings", crossing_rows),
    ):
        write_csv(paths[name], rows)
    crossing_plot, residual_plot = plot_diagnostics(prefix, points, fits, target)
    direct = load_direct_summary(args.direct_summary, target)
    artifact_records = {
        name: {"path": str(path), "sha256": critical.sha256_file(path)}
        for name, path in {**paths, "crossing_plot": crossing_plot,
                           "residual_plot": residual_plot}.items()
    }
    source_files = {
        "run_spec": args.run_spec.resolve(),
        "analysis_source": Path(__file__).resolve(),
        "corrected_fitter_source": Path(corrected.__file__).resolve(),
        "protocol": Path(__file__).resolve().parents[1] / "PROTOCOL.md",
    }
    artifact_records.update({
        name: {"path": str(path), "sha256": critical.sha256_file(path)}
        for name, path in source_files.items()
    })
    artifact_records["chains"] = chains
    summary = build_summary(
        spec, fits, sampling, brackets, prefixes, drift, direct, artifact_records,
        args.bootstrap, args.seed,
    )
    summary_path = prefix.with_name(prefix.name + "_summary.json")
    critical.atomic_json(summary_path, summary)
    primary_hc = summary["primary"]["hc"]
    primary_error = summary["primary"]["total_error"]
    primary_text = (
        f"{primary_hc:.8f} +/- {primary_error:.8f}"
        if isinstance(primary_hc, (int, float)) and math.isfinite(primary_hc)
        and math.isfinite(primary_error) else "fit-failed"
    )
    print(
        f"primary={primary_text} "
        f"internal_gates={summary['internal_gates_passed']} "
        f"independent_accepted={summary['independent_route_accepted']}",
        flush=True,
    )
    print(f"analysis summary -> {summary_path}", flush=True)
    if args.enforce_protocol and not summary["independent_route_accepted"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
