#!/usr/bin/env python3
"""Validate RBIM pilot cells and freeze production settings from diagnostics."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

NISHIMORI_C_ANCHOR = 0.464


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def pooled_adjacent_correlation(blocks: list[np.ndarray]) -> float:
    left: list[np.ndarray] = []
    right: list[np.ndarray] = []
    for values in blocks:
        centered = values - np.mean(values)
        left.append(centered[:-1])
        right.append(centered[1:])
    x = np.concatenate(left)
    y = np.concatenate(right)
    correlation = float(np.corrcoef(x, y)[0, 1])
    return correlation if math.isfinite(correlation) else 0.0


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_svg(path: Path, rows: list[dict[str, Any]]) -> None:
    width, height = 920, 430
    left, top, plot_width, plot_height = 85, 55, 760, 290
    sizes = np.array([row["L"] for row in rows], dtype=float)
    speeds = np.array([row["median_rows_per_second"] for row in rows], dtype=float)
    errors = np.array([row["ensemble_standard_error"] for row in rows], dtype=float)
    targets = np.array([row["target_standard_error"] for row in rows], dtype=float)

    def x(value: float) -> float:
        return left + (value - sizes.min()) / (sizes.max() - sizes.min()) * plot_width

    log_min = float(np.log10(min(targets.min(), errors.min()) * 0.7))
    log_max = float(np.log10(max(errors.max(), targets.max()) * 1.4))

    def y(value: float) -> float:
        return top + (log_max - math.log10(value)) / (log_max - log_min) * plot_height

    elements = [
        f'<rect width="{width}" height="{height}" fill="white"/>',
        (
            f'<text x="{width / 2}" y="28" text-anchor="middle" '
            'font-family="sans-serif" font-size="20">RBIM pilot precision and target</text>'
        ),
        f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#111827"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#111827"/>',
    ]
    for values, color, label in (
        (errors, "#dc2626", "pilot SE"),
        (targets, "#2563eb", "production target"),
    ):
        points = " ".join(
            f"{x(size):.2f},{y(value):.2f}"
            for size, value in zip(sizes, values)
        )
        elements.append(
            f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>'
        )
        for size, value in zip(sizes, values):
            elements.append(
                f'<circle cx="{x(size):.2f}" cy="{y(value):.2f}" r="4" fill="{color}"/>'
            )
        elements.append(
            f'<text x="{left + 20}" y="{top + 22 + (0 if label == "pilot SE" else 20)}" '
            f'font-family="sans-serif" font-size="14" fill="{color}">{label}</text>'
        )
    for size in sizes:
        elements.append(
            f'<text x="{x(size):.2f}" y="{top + plot_height + 25}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="13">{int(size)}</text>'
        )
    elements.extend(
        [
            f'<text x="{left + plot_width / 2}" y="400" text-anchor="middle" font-family="sans-serif" font-size="15">circumference L</text>',
            f'<text x="22" y="{top + plot_height / 2}" transform="rotate(-90 22 {top + plot_height / 2})" text-anchor="middle" font-family="sans-serif" font-size="15">standard error of phi_L (log scale)</text>',
            f'<text x="{left + plot_width - 5}" y="{top + 20}" text-anchor="end" font-family="monospace" font-size="12">speed range {speeds.min():.0f}-{speeds.max():.0f} rows/s</text>',
        ]
    )
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
        + "\n".join(elements)
        + "\n</svg>\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run = args.run.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    spec = json.loads((run / "run_spec.json").read_text(encoding="utf-8"))

    by_size: dict[int, list[tuple[dict[str, Any], np.ndarray]]] = {}
    failures: list[str] = []
    settings_payloads: set[str] = set()
    provenance_payloads: set[str] = set()
    for cell in spec["cells"]:
        cell_id = cell["cell_id"]
        cell_dir = run / "cells" / cell_id
        manifest_path = cell_dir / "manifest.json"
        if not manifest_path.is_file():
            failures.append(f"{cell_id}: missing manifest")
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") != "success":
            failures.append(f"{cell_id}: status={manifest.get('status')}")
            continue
        settings_payloads.add(json.dumps(manifest["settings"], sort_keys=True))
        provenance_payloads.add(json.dumps(manifest["provenance"], sort_keys=True))
        block_path = cell_dir / manifest["artifacts"]["block_phi"]
        if sha256(block_path) != manifest["artifacts"]["block_phi_sha256"]:
            failures.append(f"{cell_id}: block checksum mismatch")
            continue
        blocks = np.load(block_path, allow_pickle=False)
        if blocks.ndim != 1 or not np.all(np.isfinite(blocks)):
            failures.append(f"{cell_id}: invalid block array")
            continue
        size = int(manifest["params"]["size"])
        by_size.setdefault(size, []).append((manifest, blocks))
    if failures:
        atomic_json(output / "failures.json", failures)
        raise RuntimeError(f"pilot has {len(failures)} invalid cells")
    if len(settings_payloads) != 1 or len(provenance_payloads) != 1:
        raise RuntimeError("pilot settings or provenance lack consensus")

    summary_rows: list[dict[str, Any]] = []
    frozen_sizes: dict[str, Any] = {}
    maximum_qr_difference = 0.0
    maximum_orthogonality = 0.0
    for size in sorted(by_size):
        entries = by_size[size]
        block_arrays = [blocks for _, blocks in entries]
        all_blocks = np.concatenate(block_arrays)
        mean = float(np.mean(all_blocks))
        standard_error = float(
            np.std(all_blocks, ddof=1) / math.sqrt(all_blocks.size)
        )
        correlation = pooled_adjacent_correlation(block_arrays)
        manifests = [manifest for manifest, _ in entries]
        block_size = int(manifests[0]["result"]["block_size"])
        recommended_block = block_size * 2 if abs(correlation) > 0.1 else block_size
        signal = math.pi * NISHIMORI_C_ANCHOR / (6.0 * size**2)
        target = min(2.0e-6, 0.05 * abs(signal))
        current_rows = int(manifests[0]["result"]["measurement_rows"])
        current_replicas = len(entries)
        production_replicas = 32
        required_rows = current_rows * (standard_error / target) ** 2
        required_rows *= current_replicas / production_replicas
        minimum_rows = 200 * recommended_block / production_replicas
        required_rows = max(required_rows, minimum_rows)
        required_rows = int(
            math.ceil(required_rows / recommended_block) * recommended_block
        )
        median_speed = float(
            np.median([m["result"]["rows_per_second"] for m in manifests])
        )
        qr_difference = max(
            float(m["result"]["qr_interval_mean_phi_absolute_difference"])
            for m in manifests
        )
        orthogonality = max(
            float(m["result"]["maximum_orthogonality_error"])
            for m in manifests
        )
        maximum_qr_difference = max(maximum_qr_difference, qr_difference)
        maximum_orthogonality = max(maximum_orthogonality, orthogonality)
        summary_rows.append(
            {
                "L": size,
                "replicas": current_replicas,
                "blocks": int(all_blocks.size),
                "block_size": block_size,
                "pooled_adjacent_block_correlation": correlation,
                "mean_phi": mean,
                "ensemble_standard_error": standard_error,
                "target_standard_error": target,
                "median_rows_per_second": median_speed,
                "maximum_qr_mean_difference": qr_difference,
                "maximum_orthogonality_error": orthogonality,
                "recommended_production_block_size": recommended_block,
                "estimated_rows_per_production_replica": required_rows,
                "estimated_seconds_per_production_replica": (
                    required_rows / median_speed
                ),
            }
        )
        frozen_sizes[str(size)] = {
            "block_size": recommended_block,
            "estimated_measurement_rows_per_replica": required_rows,
            "pilot_standard_error": standard_error,
            "target_standard_error": target,
            "median_rows_per_second": median_speed,
        }

    minimum_pilot_se = min(row["ensemble_standard_error"] for row in summary_rows)
    selected_qr_interval = 5 if maximum_qr_difference <= 0.1 * minimum_pilot_se else 1
    frozen = {
        "schema_version": 1,
        "source_run": spec["run_id"],
        "selection_rules": {
            "block_doubling_threshold_absolute_correlation": 0.1,
            "qr_difference_fraction_of_minimum_pilot_se": 0.1,
            "minimum_effective_blocks_per_size": 200,
            "target_se": "min(2e-6, 0.05*abs(pi*0.464/(6*L^2)))",
        },
        "production": {
            "p": spec["settings"]["p"],
            "base_seed": 202607270301,
            "qr_interval": selected_qr_interval,
            "burn_in_rows_per_size": 20,
            "replicas": 32,
            "sizes": [6, 8, 10, 12, 14, 16, 20, 24, 30, 32],
            "pilot_size_estimates": frozen_sizes,
        },
    }
    metrics = {
        "all_cells_success": True,
        "cells": len(spec["cells"]),
        "settings_consensus": len(settings_payloads) == 1,
        "provenance_consensus": len(provenance_payloads) == 1,
        "maximum_qr_interval_mean_difference": maximum_qr_difference,
        "selected_qr_interval": selected_qr_interval,
        "maximum_orthogonality_error": maximum_orthogonality,
        "minimum_blocks_per_size": min(row["blocks"] for row in summary_rows),
        "sizes_requiring_block_doubling": [
            row["L"]
            for row in summary_rows
            if row["recommended_production_block_size"] > row["block_size"]
        ],
    }
    write_csv(output / "pilot-summary.csv", summary_rows)
    atomic_json(output / "frozen-production.json", frozen)
    atomic_json(output / "metrics.json", metrics)
    write_svg(output / "pilot-precision.svg", summary_rows)
    print(json.dumps(metrics, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
