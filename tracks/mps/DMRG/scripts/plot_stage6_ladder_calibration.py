#!/usr/bin/env python3
"""Render a diagnostic-only Stage 6 ladder acceptance figure."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Sequence

import numpy as np


TRACK_ROOT = Path(__file__).resolve().parents[1]
SRC = TRACK_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vmcrg_ref.artifacts import atomic_write_json, sha256_file, verified_promote_directory


def _calibration_payload(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="ascii"))
    if (
        payload.get("schema_version") != 1
        or payload.get("classification") != "CALIBRATION_COMPLETE"
        or payload.get("scope") != "stage6-ladder-calibration-only"
        or payload.get("tc_evidence") is not False
    ):
        raise ValueError("input must be a calibration-only, non-Tc manifest")
    return payload


def _wilson_interval(accepts: int, attempts: int) -> tuple[float, float]:
    z = 1.959963984540054
    probability = accepts / attempts
    denominator = 1.0 + z * z / attempts
    center = (probability + z * z / (2.0 * attempts)) / denominator
    half_width = z / denominator * math.sqrt(
        probability * (1.0 - probability) / attempts
        + z * z / (4.0 * attempts * attempts)
    )
    return max(0.0, center - half_width), min(1.0, center + half_width)


def _rows(payload: dict[str, object]) -> list[dict[str, object]]:
    spec = payload.get("spec")
    tempering = payload.get("parallel_tempering")
    if not isinstance(spec, dict) or not isinstance(tempering, dict):
        raise ValueError("calibration manifest is missing its spec or PT record")
    temperatures = np.asarray(spec.get("temperatures"), dtype=np.float64)
    attempts = np.asarray(tempering.get("edge_attempts"), dtype=np.int64)
    accepts = np.asarray(tempering.get("edge_accepts"), dtype=np.int64)
    acceptance = np.asarray(tempering.get("edge_acceptance"), dtype=np.float64)
    edge_count = temperatures.size - 1
    if (
        temperatures.ndim != 1
        or temperatures.size < 2
        or not np.all(np.isfinite(temperatures))
        or np.any(temperatures <= 0.0)
        or np.any(np.diff(1.0 / temperatures) <= 0.0)
        or attempts.shape != (edge_count,)
        or accepts.shape != (edge_count,)
        or acceptance.shape != (edge_count,)
        or np.any(attempts <= 0)
        or np.any(accepts < 0)
        or np.any(accepts > attempts)
        or not np.all(np.isfinite(acceptance))
        or not np.allclose(acceptance, accepts / attempts, atol=1e-15, rtol=0.0)
    ):
        raise ValueError("calibration ladder arrays are inconsistent")
    lower_target = float(spec.get("swap_target_minimum"))
    upper_target = float(spec.get("swap_target_maximum"))
    if not 0.0 <= lower_target <= upper_target <= 1.0:
        raise ValueError("calibration target band is invalid")

    rows: list[dict[str, object]] = []
    betas = 1.0 / temperatures
    for index in range(edge_count):
        low, high = _wilson_interval(int(accepts[index]), int(attempts[index]))
        value = float(acceptance[index])
        rows.append(
            {
                "edge": index,
                "temperature_upper": float(temperatures[index]),
                "temperature_lower": float(temperatures[index + 1]),
                "beta_upper": float(betas[index]),
                "beta_lower": float(betas[index + 1]),
                "attempts": int(attempts[index]),
                "accepts": int(accepts[index]),
                "acceptance": value,
                "ci95_low": low,
                "ci95_high": high,
                "inside_target_band": lower_target <= value <= upper_target,
            }
        )
    return rows


def build_ladder_diagnostic(
    manifest: str | Path,
    output: str | Path,
) -> dict[str, object]:
    source = Path(manifest).resolve()
    destination = Path(output)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite ladder diagnostic: {destination}")
    payload = _calibration_payload(source)
    rows = _rows(payload)
    spec = payload["spec"]
    assert isinstance(spec, dict)
    lower_target = float(spec["swap_target_minimum"])
    upper_target = float(spec["swap_target_maximum"])

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
    try:
        csv_path = staging / "ladder_acceptance.csv"
        fieldnames = tuple(rows[0])
        with csv_path.open("w", newline="", encoding="ascii") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        **row,
                        "inside_target_band": str(row["inside_target_band"]).lower(),
                    }
                )

        matplotlib_cache = Path(tempfile.mkdtemp(prefix="hg3d-matplotlib-", dir="/tmp"))
        try:
            os.environ["MPLCONFIGDIR"] = str(matplotlib_cache)
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            edge = np.asarray([row["edge"] for row in rows], dtype=np.int64)
            acceptance = np.asarray(
                [row["acceptance"] for row in rows], dtype=np.float64
            )
            low = np.asarray([row["ci95_low"] for row in rows], dtype=np.float64)
            high = np.asarray([row["ci95_high"] for row in rows], dtype=np.float64)
            fig, ax = plt.subplots(figsize=(6.2, 3.4), constrained_layout=True)
            ax.axhspan(
                lower_target,
                upper_target,
                color="#009E73",
                alpha=0.16,
                label="Required range",
            )
            ax.errorbar(
                edge,
                acceptance,
                yerr=np.vstack((acceptance - low, high - acceptance)),
                color="#0072B2",
                marker="o",
                markersize=3.0,
                linewidth=1.2,
                elinewidth=0.7,
                capsize=1.5,
                label="Measured acceptance (95% Wilson CI)",
            )
            ax.set_xlabel("Adjacent temperature edge")
            ax.set_ylabel("Swap acceptance")
            ax.set_ylim(0.0, 1.0)
            ax.set_xlim(-0.8, len(rows) - 0.2)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.legend(frameon=False, fontsize=8, loc="lower right")
            fig.savefig(staging / "ladder_acceptance.png", dpi=300)
            fig.savefig(staging / "ladder_acceptance.pdf")
            plt.close(fig)
        finally:
            shutil.rmtree(matplotlib_cache)

        artifacts = {
            name: sha256_file(staging / name)
            for name in (
                "ladder_acceptance.csv",
                "ladder_acceptance.pdf",
                "ladder_acceptance.png",
            )
        }
        record = {
            "schema_version": 1,
            "classification": "DIAGNOSTIC_ONLY",
            "tc_evidence": False,
            "cell_id": payload.get("cell_id"),
            "ladder_decision": payload["parallel_tempering"]["ladder_decision"],
            "source_manifest": str(source),
            "source_manifest_sha256": sha256_file(source),
            "target_band": [lower_target, upper_target],
            "edge_count": len(rows),
            "artifacts": artifacts,
        }
        record_path = staging / "diagnostic_manifest.json"
        atomic_write_json(record_path, record)
        verified_promote_directory(
            staging,
            destination,
            {**artifacts, "diagnostic_manifest.json": sha256_file(record_path)},
        )
        return record
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        record = build_ladder_diagnostic(args.manifest, args.output)
    except (FileExistsError, KeyError, TypeError, ValueError) as error:
        print(f"ladder diagnostic failed closed: {error}", flush=True)
        return 2
    print(
        f"classification={record['classification']} output={args.output}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
