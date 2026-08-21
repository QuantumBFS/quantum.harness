#!/usr/bin/env python3
"""Build the accepted direct-SSE summary consumed by the ParaToric adapter."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any


PROTOCOL_ID = "c148-prereg-v1+rev1+rev2+rev3+rev4+rev5+rev6+rev7"
SCHEMA_VERSION = "challenge148-direct-summary-v1"
PRECISION_LIMIT = {"triangular": 1.8e-5, "honeycomb": 8.0e-6}
OBSERVABLES = ("Q", "xi")
FIT_CHI2_MAX = 3.0
FIT_CONDITION_MAX = 1.0e12
BOOTSTRAP_FAILURE_MAX = 0.01


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"missing or empty artifact: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"artifact has no rows: {path}")
    return rows


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"missing or empty artifact: {path}")
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"artifact is not a JSON object: {path}")
    return payload


def parse_bool(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value in {"0", "1"}:
        return value == "1"
    raise ValueError(f"{field} must be a JSON boolean or CSV 0/1")


def finite_float(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} is not numeric") from error
    if not math.isfinite(result):
        raise ValueError(f"{field} is not finite")
    return result


def fit_passes(row: dict[str, Any]) -> bool:
    return (
        finite_float(row["chi2_per_dof"], "chi2_per_dof") <= FIT_CHI2_MAX
        and finite_float(row["condition"], "condition") <= FIT_CONDITION_MAX
        and finite_float(row["bootstrap_failure_rate"], "bootstrap_failure_rate")
        <= BOOTSTRAP_FAILURE_MAX
    )


def one_per_observable(rows: list[dict[str, str]], label: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        observable = row.get("observable")
        if observable not in OBSERVABLES or observable in result:
            raise ValueError(f"{label} must contain exactly one row for each observable")
        result[observable] = row
    if set(result) != set(OBSERVABLES):
        raise ValueError(f"{label} omitted an observable")
    return result


def validate_bins(path: Path, target: str) -> None:
    rows = read_csv(path)
    required = {"raw_schema", "lattice", "sign_avg", "L", "h", "seed", "bin"}
    if required - set(rows[0]):
        raise ValueError(f"raw bins omit required columns: {sorted(required - set(rows[0]))}")
    identities = {(row["raw_schema"], row["lattice"]) for row in rows}
    if identities != {("challenge148-raw-v1", target)}:
        raise ValueError("raw bins do not contain exactly the requested target lattice")
    if any(finite_float(row["sign_avg"], "sign_avg") != 1.0 for row in rows):
        raise ValueError("raw bins violate the exact positive-sign gate")


def build_summary(
    *, run_id: str, target: str, bins: Path, fits_path: Path,
    sampling_path: Path, prefix_path: Path, robustness_path: Path,
    ctau_gate_path: Path, ctau_fits_path: Path,
) -> dict[str, Any]:
    if target not in PRECISION_LIMIT:
        raise ValueError(f"unsupported target lattice {target!r}")
    paths = {
        "bins": bins, "fits": fits_path, "sampling_gates": sampling_path,
        "prefix_stability": prefix_path, "robustness": robustness_path,
        "finite_temperature_gate": ctau_gate_path,
        "finite_temperature_fits": ctau_fits_path,
    }
    validate_bins(bins, target)
    fits = one_per_observable(read_csv(fits_path), "primary fit artifact")
    sampling = read_csv(sampling_path)
    prefixes = read_csv(prefix_path)
    robustness_rows = read_csv(robustness_path)
    ctau_gate = read_json(ctau_gate_path)
    ctau_fits = one_per_observable(
        read_csv(ctau_fits_path), "finite-temperature fit artifact"
    )

    if ctau_gate.get("schema_version") != "challenge148-ctau-gate-v2":
        raise ValueError("finite-temperature gate uses an unsupported schema")
    if ctau_gate.get("lattice") != target:
        raise ValueError("finite-temperature gate target differs from direct summary")

    primary = fits["Q"]
    supporting = fits["xi"]
    primary_hc = finite_float(primary["hc"], "primary hc")
    supporting_hc = finite_float(supporting["hc"], "supporting hc")
    bootstrap = {
        observable: finite_float(fits[observable]["hc_boot_err"], "bootstrap error")
        for observable in OBSERVABLES
    }
    if any(error <= 0.0 for error in bootstrap.values()):
        raise ValueError("bootstrap errors must be positive")

    robustness_gate = all(
        row.get("status") == "ok" and fit_passes(row)
        for row in robustness_rows
    )
    variant_shift = {
        observable: max(
            abs(finite_float(row["hc"], "robustness hc") - finite_float(fits[observable]["hc"], "hc"))
            for row in robustness_rows
            if row.get("observable") == observable and row.get("status") == "ok"
        )
        for observable in OBSERVABLES
    }
    finite_beta = {
        observable: finite_float(ctau_fits[observable]["shift_upper_95"], "shift_upper_95")
        for observable in OBSERVABLES
    }
    total = {
        observable: bootstrap[observable] + variant_shift[observable] + finite_beta[observable]
        for observable in OBSERVABLES
    }

    gates = {
        "sampling": all(parse_bool(row["passed"], "sampling passed") for row in sampling),
        "prefix_stability": all(
            row.get("status") == "ok" and parse_bool(row["passed"], "prefix passed")
            for row in prefixes
        ),
        "primary_and_supporting_fits": all(fit_passes(row) for row in fits.values()),
        "registered_robustness": robustness_gate,
        "finite_temperature": parse_bool(ctau_gate.get("passed"), "c_tau passed"),
    }
    combined = math.hypot(total["Q"], total["xi"])
    observable_z = abs(primary_hc - supporting_hc) / combined if combined > 0.0 else math.inf
    gates["observable_agreement"] = math.isfinite(observable_z) and observable_z <= 1.0
    gates["primary_precision"] = total["Q"] <= PRECISION_LIMIT[target]
    accepted = all(gates.values())

    artifacts = {
        name: {"path": str(path.resolve()), "sha256": sha256_file(path.resolve())}
        for name, path in paths.items()
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "protocol_id": PROTOCOL_ID,
        "run_id": run_id,
        "target_lattice": target,
        "hc": primary_hc,
        "total_error": total["Q"],
        "accepted": accepted,
        "primary": {
            "observable": "Q", "hc": primary_hc,
            "bootstrap_error": bootstrap["Q"],
            "variant_envelope": variant_shift["Q"],
            "finite_temperature_upper_95": finite_beta["Q"],
            "total_error": total["Q"],
        },
        "supporting": {
            "observable": "xi", "hc": supporting_hc,
            "bootstrap_error": bootstrap["xi"],
            "variant_envelope": variant_shift["xi"],
            "finite_temperature_upper_95": finite_beta["xi"],
            "total_error": total["xi"],
        },
        "uncertainty_combination": "linear conservative sum",
        "gates": {**gates, "observable_agreement_z": observable_z},
        "artifacts": artifacts,
        "ratio_computed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--target-lattice", required=True, choices=tuple(PRECISION_LIMIT))
    parser.add_argument("--bins", type=Path, required=True)
    parser.add_argument("--fits", type=Path, required=True)
    parser.add_argument("--sampling-gates", type=Path, required=True)
    parser.add_argument("--prefix-stability", type=Path, required=True)
    parser.add_argument("--robustness", type=Path, required=True)
    parser.add_argument("--ctau-gate", type=Path, required=True)
    parser.add_argument("--ctau-fits", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()
    summary = build_summary(
        run_id=args.run_id, target=args.target_lattice, bins=args.bins,
        fits_path=args.fits, sampling_path=args.sampling_gates,
        prefix_path=args.prefix_stability, robustness_path=args.robustness,
        ctau_gate_path=args.ctau_gate, ctau_fits_path=args.ctau_fits,
    )
    atomic_json(args.output, summary)
    print(
        f"target={args.target_lattice} hc={summary['hc']:.8f} "
        f"total_error={summary['total_error']:.8g} accepted={summary['accepted']}",
        flush=True,
    )
    print(f"direct summary -> {args.output}", flush=True)
    if args.enforce and not summary["accepted"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
