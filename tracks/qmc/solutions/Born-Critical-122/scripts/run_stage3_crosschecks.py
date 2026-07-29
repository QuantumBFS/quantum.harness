#!/usr/bin/env python3
"""Run the independent Stage-3 RBIM sensitivity and distribution checks."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time
from typing import Any

import numpy as np

from borncritical.casimir_fit import fit_casimir
from borncritical.rbim import fermionic_log_partition


def atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def uint64_seed(base: int, size: int, replica: int) -> int:
    payload = f"{base}|pc-sensitivity|{size}|{replica}".encode()
    return int.from_bytes(
        hashlib.blake2b(payload, digest_size=8, person=b"borncrit-xcheck").digest(),
        "big",
    )


def parse_output(text: str) -> dict[str, float]:
    result: dict[str, float] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = float(value)
    return result


def run_stream(payload: dict[str, Any]) -> dict[str, Any]:
    output = Path(payload["work"]) / payload["name"]
    command = [
        payload["binary"],
        str(payload["size"]),
        str(payload["seed"]),
        f"{payload['p']:.17g}",
        f"{payload['coupling']:.17g}",
        str(payload["qr_interval"]),
        str(payload["burn_in"]),
        str(payload["measurement"]),
        str(payload["block_size"]),
        "1",
        str(output),
    ]
    started = time.perf_counter()
    process = subprocess.run(command, check=True, capture_output=True, text=True)
    elapsed = time.perf_counter() - started
    blocks = np.fromfile(output, dtype=np.float64)
    output.unlink()
    expected = payload["measurement"] // payload["block_size"]
    if blocks.size != expected or not np.all(np.isfinite(blocks)):
        raise RuntimeError(f"{payload['name']}: invalid C++ block output")
    return {
        **payload,
        "mean": float(np.mean(blocks)),
        "block_standard_error": float(
            np.std(blocks, ddof=1) / math.sqrt(blocks.size)
        ),
        "elapsed": elapsed,
        "reported": parse_output(process.stdout),
    }


def write_bonds(
    path: Path,
    vertical: np.ndarray,
    horizontal: np.ndarray,
    coupling: float,
) -> None:
    lines = [
        f"{vertical.shape[0]} {vertical.shape[1]} {coupling:.17g} 1",
        *(" ".join(str(int(value)) for value in row) for row in vertical),
        *(" ".join(str(int(value)) for value in row) for row in horizontal),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def fit_charge(
    sizes: np.ndarray,
    values: np.ndarray,
    errors: np.ndarray | None,
    *,
    model: str,
) -> dict[str, Any]:
    fit = fit_casimir(
        sizes,
        values,
        errors=errors,
        model=model,
        quantity="phi",
    )
    return {
        "central_charge": fit.central_charge,
        "central_charge_analytic_error": fit.central_charge_error,
        "coefficients": fit.coefficients.tolist(),
        "chi_squared": fit.chi_squared,
        "degrees_of_freedom": fit.degrees_of_freedom,
        "reduced_chi_squared": fit.reduced_chi_squared,
        "design_condition_number": fit.design_condition_number,
        "residuals": fit.residuals.tolist(),
    }


def pc_sensitivity(
    config: dict[str, Any],
    *,
    binary: Path,
    work: Path,
    workers: int,
) -> dict[str, Any]:
    section = config["pc_sensitivity"]
    pc = float(config["pc"])
    delta = float(config["pc_half_width"])
    payloads: list[dict[str, Any]] = []
    for label, p in (("minus", pc - delta), ("plus", pc + delta)):
        coupling = 0.5 * math.log((1.0 - p) / p)
        for size in section["sizes"]:
            for replica in range(int(section["replicas"])):
                payloads.append(
                    {
                        "name": f"pc-{label}-L{size}-r{replica}.bin",
                        "label": label,
                        "binary": str(binary),
                        "work": str(work),
                        "size": int(size),
                        "replica": replica,
                        "seed": uint64_seed(
                            int(config["base_seed"]), int(size), replica
                        ),
                        "p": p,
                        "coupling": coupling,
                        "qr_interval": int(config["qr_interval"]),
                        "burn_in": (
                            int(section["burn_in_rows_per_size"]) * int(size)
                        ),
                        "measurement": int(section["measurement_rows"]),
                        "block_size": int(config["output_block_size"]),
                    }
                )
    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_stream, payload) for payload in payloads]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(
                f"[crosscheck] pc-{result['label']} L={result['size']} "
                f"r={result['replica']} phi={result['mean']:.12g}",
                flush=True,
            )

    sizes = np.array(section["sizes"], dtype=float)
    labels: dict[str, dict[int, np.ndarray]] = {"minus": {}, "plus": {}}
    for label in labels:
        for size in sizes.astype(int):
            rows = sorted(
                (
                    row
                    for row in results
                    if row["label"] == label and row["size"] == size
                ),
                key=lambda row: row["replica"],
            )
            labels[label][size] = np.array([row["mean"] for row in rows])
    values: dict[str, np.ndarray] = {}
    errors: dict[str, np.ndarray] = {}
    fits: dict[str, dict[str, Any]] = {}
    for label in labels:
        values[label] = np.array(
            [np.mean(labels[label][size]) for size in sizes.astype(int)]
        )
        errors[label] = np.array(
            [
                np.std(labels[label][size], ddof=1)
                / math.sqrt(labels[label][size].size)
                for size in sizes.astype(int)
            ]
        )
        fits[label] = fit_charge(
            sizes,
            values[label],
            errors[label],
            model=section["fit_model"],
        )

    bootstrap_count = int(section["bootstrap_samples"])
    rng = np.random.default_rng(int(config["base_seed"]) + 1)
    paired_differences = np.empty(bootstrap_count)
    for sample in range(bootstrap_count):
        sample_values: dict[str, list[float]] = {"minus": [], "plus": []}
        for size in sizes.astype(int):
            count = labels["minus"][size].size
            indices = rng.integers(0, count, size=count)
            for label in sample_values:
                sample_values[label].append(
                    float(np.mean(labels[label][size][indices]))
                )
        sample_fits = {
            label: fit_casimir(
                sizes,
                np.asarray(sample_values[label]),
                errors=errors[label],
                model=section["fit_model"],
                quantity="phi",
            )
            for label in sample_values
        }
        paired_differences[sample] = 0.5 * (
            sample_fits["plus"].central_charge
            - sample_fits["minus"].central_charge
        )
    half_span = 0.5 * (
        fits["plus"]["central_charge"] - fits["minus"]["central_charge"]
    )
    return {
        "sizes": sizes.astype(int).tolist(),
        "replicas": int(section["replicas"]),
        "measurement_rows_per_replica": int(section["measurement_rows"]),
        "p_minus": pc - delta,
        "p_plus": pc + delta,
        "fit_minus": fits["minus"],
        "fit_plus": fits["plus"],
        "central_charge_signed_half_span": half_span,
        "central_charge_absolute_half_span": abs(half_span),
        "paired_bootstrap_half_span_median": float(
            np.median(paired_differences)
        ),
        "paired_bootstrap_half_span_95_interval": np.quantile(
            paired_differences, [0.025, 0.975]
        ).tolist(),
        "maximum_orthogonality_error": max(
            row["reported"]["maximum_orthogonality_error"] for row in results
        ),
        "median_rows_per_second": float(
            np.median([row["reported"]["rows_per_second"] for row in results])
        ),
    }


def clean_limit(
    config: dict[str, Any],
    *,
    binary: Path,
    work: Path,
    workers: int,
) -> dict[str, Any]:
    section = config["clean_limit"]
    payloads = [
        {
            "name": f"clean-L{size}.bin",
            "binary": str(binary),
            "work": str(work),
            "size": int(size),
            "seed": uint64_seed(int(config["base_seed"]) + 2, int(size), 0),
            "p": 0.0,
            "coupling": float(section["coupling"]),
            "qr_interval": int(config["qr_interval"]),
            "burn_in": int(section["burn_in_rows_per_size"]) * int(size),
            "measurement": int(section["measurement_rows"]),
            "block_size": int(config["output_block_size"]),
        }
        for size in section["sizes"]
    ]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(run_stream, payloads))
    results.sort(key=lambda row: row["size"])
    sizes = np.array([row["size"] for row in results], dtype=float)
    values = np.array([row["mean"] for row in results])
    selected = sizes >= int(section["fit_lmin"])
    fit = fit_charge(
        sizes[selected],
        values[selected],
        None,
        model=section["fit_model"],
    )
    error = abs(fit["central_charge"] - float(section["central_charge_target"]))
    return {
        "sizes": sizes.astype(int).tolist(),
        "phi": values.tolist(),
        "fit_model": section["fit_model"],
        "fit_lmin": int(section["fit_lmin"]),
        "fit": fit,
        "central_charge_absolute_error": error,
        "absolute_tolerance": float(section["absolute_tolerance"]),
        "passes": error <= float(section["absolute_tolerance"]),
        "maximum_orthogonality_error": max(
            row["reported"]["maximum_orthogonality_error"] for row in results
        ),
    }


def upstream_distribution(
    config: dict[str, Any],
    *,
    driver: Path,
    work: Path,
) -> dict[str, Any]:
    section = config["upstream_distribution"]
    p = float(config["pc"])
    coupling = 0.5 * math.log((1.0 - p) / p)
    rng = np.random.default_rng(int(section["seed"]))
    internal_values: list[float] = []
    upstream_values: list[float] = []
    for sample in range(int(section["samples"])):
        vertical = np.where(
            rng.random((int(section["length"]), int(section["size"]))) < p,
            -1,
            1,
        ).astype(np.int8)
        horizontal = np.where(
            rng.random((int(section["length"]) - 1, int(section["size"]))) < p,
            -1,
            1,
        ).astype(np.int8)
        internal, _ = fermionic_log_partition(
            vertical, horizontal, coupling, parity=1, qr_interval=1
        )
        bond_path = work / f"distribution-{sample:04d}.txt"
        write_bonds(bond_path, vertical, horizontal, coupling)
        process = subprocess.run(
            [str(driver), str(bond_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        bond_path.unlink()
        internal_values.append(internal)
        upstream_values.append(float(process.stdout.strip().splitlines()[-1]))
    internal_array = np.asarray(internal_values)
    upstream_array = np.asarray(upstream_values)
    differences = internal_array - upstream_array
    np.savez(
        work / "upstream-distribution.npz",
        internal=internal_array,
        upstream=upstream_array,
    )
    return {
        "samples": int(section["samples"]),
        "length": int(section["length"]),
        "size": int(section["size"]),
        "maximum_paired_absolute_logZ_difference": float(
            np.max(np.abs(differences))
        ),
        "mean_paired_logZ_difference": float(np.mean(differences)),
        "internal_mean": float(np.mean(internal_array)),
        "upstream_mean": float(np.mean(upstream_array)),
        "internal_standard_deviation": float(np.std(internal_array, ddof=1)),
        "upstream_standard_deviation": float(np.std(upstream_array, ddof=1)),
        "maximum_sorted_quantile_absolute_difference": float(
            np.max(np.abs(np.sort(internal_array) - np.sort(upstream_array)))
        ),
        "passes": bool(np.max(np.abs(differences)) < 2.0e-10),
    }


def parity_defect(config: dict[str, Any]) -> dict[str, Any]:
    section = config["parity_defect"]
    p = float(config["pc"])
    coupling = 0.5 * math.log((1.0 - p) / p)
    rng = np.random.default_rng(int(section["seed"]))
    rows: list[dict[str, Any]] = []
    all_finite = True
    for size in section["sizes"]:
        length = int(section["aspect_ratio"]) * int(size)
        differences: list[float] = []
        for _ in range(int(section["samples_per_size"])):
            vertical = np.where(
                rng.random((length, int(size))) < p, -1, 1
            ).astype(np.int8)
            horizontal = np.where(
                rng.random((length - 1, int(size))) < p, -1, 1
            ).astype(np.int8)
            periodic, _ = fermionic_log_partition(
                vertical, horizontal, coupling, parity=1, qr_interval=1
            )
            antiperiodic, _ = fermionic_log_partition(
                vertical, horizontal, coupling, parity=-1, qr_interval=1
            )
            differences.append(periodic - antiperiodic)
        values = np.asarray(differences)
        all_finite = all_finite and bool(np.all(np.isfinite(values)))
        rows.append(
            {
                "L": int(size),
                "length": length,
                "samples": int(values.size),
                "mean_logZ_periodic_minus_antiperiodic": float(np.mean(values)),
                "standard_error": float(
                    np.std(values, ddof=1) / math.sqrt(values.size)
                ),
                "median": float(np.median(values)),
                "fraction_positive": float(np.mean(values > 0.0)),
            }
        )
    return {
        "rows": rows,
        "all_finite": all_finite,
        "all_sizes_sampled": len(rows) == len(section["sizes"]),
        "passes": all_finite and len(rows) == len(section["sizes"]),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--upstream-driver", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    work = args.work.resolve()
    output = args.output.resolve()
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).isoformat()
    pc_result = pc_sensitivity(
        config,
        binary=args.binary.resolve(),
        work=work,
        workers=args.workers,
    )
    clean_result = clean_limit(
        config,
        binary=args.binary.resolve(),
        work=work,
        workers=args.workers,
    )
    distribution_result = upstream_distribution(
        config,
        driver=args.upstream_driver.resolve(),
        work=work,
    )
    parity_result = parity_defect(config)
    metrics = {
        "schema_version": 1,
        "pc_sensitivity": pc_result,
        "clean_limit": clean_result,
        "upstream_distribution": distribution_result,
        "parity_defect": parity_result,
        "gates": {
            "clean_limit": clean_result["passes"],
            "upstream_complete_distribution": distribution_result["passes"],
            "parity_defect_finite": parity_result["passes"],
            "pc_sensitivity_finite": math.isfinite(
                pc_result["central_charge_absolute_half_span"]
            ),
        },
    }
    metrics["all_intrinsic_gates_passed"] = all(metrics["gates"].values())
    atomic_json(output / "metrics.json", metrics)
    atomic_json(
        output / "manifest.json",
        {
            "schema_version": 1,
            "stage": "stage3-rbim-crosschecks",
            "status": (
                "success" if metrics["all_intrinsic_gates_passed"] else "failed"
            ),
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
            "config": config,
            "artifacts": {
                "metrics": "metrics.json",
                "upstream_distribution": "upstream-distribution.npz",
            },
        },
    )
    (work / "upstream-distribution.npz").replace(
        output / "upstream-distribution.npz"
    )
    print(json.dumps(metrics, indent=2, sort_keys=True), flush=True)
    return 0 if metrics["all_intrinsic_gates_passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
