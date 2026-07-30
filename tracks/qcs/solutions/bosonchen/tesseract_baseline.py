#!/usr/bin/env python3
"""Run a small, deterministic baseline using the official Tesseract decoder."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time


PINNED_COMMIT = "9c73ca0acb1a48fd1dc797f5f6deabbb5f5d3feb"
SOURCE_URL = "https://github.com/quantumlib/tesseract-decoder.git"
BAZEL_VERSION = "8.2.1"
BAZEL_DARWIN_ARM64_URL = (
    "https://github.com/bazelbuild/bazel/releases/download/8.2.1/"
    "bazel-8.2.1-darwin-arm64"
)
BAZEL_DARWIN_ARM64_SHA256 = (
    "22ff65b05869f6160e5157b1b425a14a62085d71d8baef571f462b8fe5a703a3"
)
SAMPLE_SEED = 752024
DET_ORDER_SEED = 2384753

CASES = [
    {
        "name": "surface_d5",
        "family": "surface",
        "circuit": (
            "testdata/surfacecodes/"
            "r=5,d=5,p=0.001,noise=si1000,c=surface_code_X,q=49,gates=cz.stim"
        ),
    },
    {
        "name": "color_d5",
        "family": "superdense color",
        "circuit": (
            "testdata/colorcodes/"
            "r=5,d=5,p=0.001,noise=si1000,c=superdense_color_code_X,q=37,gates=cz.stim"
        ),
    },
    {
        "name": "bbc_d6",
        "family": "bivariate bicycle",
        "circuit": (
            "testdata/bivariatebicyclecodes/"
            "r=6,d=6,p=0.001,noise=si1000,c=bivariate_bicycle_X,"
            "nkd=[[72,12,6]],q=144,iscolored=True,A_poly=x^3+y+y^2,"
            "B_poly=y^3+x+x^2.stim"
        ),
    },
    {
        "name": "transcx_d5",
        "family": "transversal-CX",
        "circuit": (
            "testdata/surface_code_trans_cx_circuits/"
            "r=5,d=5,p=0.001,noise=si1000,c=surface_code_trans_cx_X,"
            "q=98,gates=cz.stim"
        ),
    },
]

PRESETS = {
    "short": {
        "beam": 15,
        "pqlimit": 200_000,
        "num_det_orders": 16,
    },
    "long": {
        "beam": 20,
        "pqlimit": 1_000_000,
        "num_det_orders": 21,
    },
}

FIELDNAMES = [
    "case",
    "family",
    "preset",
    "circuit",
    "shots",
    "num_errors",
    "num_low_confidence",
    "decode_seconds",
    "milliseconds_per_shot",
    "process_wall_seconds",
    "sample_seed",
    "det_order_seed",
    "beam",
    "pqlimit",
    "num_det_orders",
    "source_commit",
]


def run_checked(command: list[str], cwd: Path, *, quiet: bool = False) -> subprocess.CompletedProcess:
    kwargs: dict[str, object] = {
        "cwd": cwd,
        "text": True,
        "check": True,
    }
    if quiet:
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL
    return subprocess.run(command, **kwargs)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_source(source: Path) -> None:
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        print(f"Cloning official Tesseract source into {source}...", flush=True)
        run_checked(["git", "clone", SOURCE_URL, str(source)], source.parent)
        run_checked(["git", "checkout", PINNED_COMMIT], source)
    verify_source(source)


def ensure_bazel(bazel: Path) -> None:
    if not bazel.exists():
        if platform.system() != "Darwin" or platform.machine() != "arm64":
            raise RuntimeError(
                f"Bazel {BAZEL_VERSION} is missing at {bazel}. "
                "Automatic download is currently pinned for Darwin arm64 only; "
                "provide a Bazel 8.2.1 executable with --bazel."
            )
        bazel.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading pinned Bazel {BAZEL_VERSION}...", flush=True)
        run_checked(
            ["curl", "-L", BAZEL_DARWIN_ARM64_URL, "-o", str(bazel)],
            bazel.parent,
        )
        bazel.chmod(0o755)
    if not bazel.is_file() or not os.access(bazel, os.X_OK):
        raise RuntimeError(f"Executable Bazel {BAZEL_VERSION} not found: {bazel}")
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        actual_hash = sha256(bazel)
        if actual_hash != BAZEL_DARWIN_ARM64_SHA256:
            raise RuntimeError(
                f"Unexpected Bazel SHA-256 at {bazel}: {actual_hash}; "
                f"expected {BAZEL_DARWIN_ARM64_SHA256}"
            )


def verify_source(source: Path) -> None:
    if not (source / ".git").is_dir():
        raise RuntimeError(f"Official source checkout not found: {source}")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=source, text=True
    ).strip()
    if head != PINNED_COMMIT:
        raise RuntimeError(f"Expected Tesseract {PINNED_COMMIT}, found {head}")
    for case in CASES:
        circuit = source / case["circuit"]
        if not circuit.is_file():
            raise RuntimeError(f"Missing official circuit: {circuit}")


def build(source: Path, bazel: Path) -> None:
    print("Building official Tesseract binary with one Bazel job...", flush=True)
    run_checked(
        [
            str(bazel),
            "--output_user_root=/tmp/tesseract-bazel-root",
            "build",
            "--jobs=1",
            "-c",
            "opt",
            "//src:tesseract",
        ],
        source,
    )


def decoder_command(
    binary: Path,
    circuit: Path,
    preset: dict[str, int],
    shots: int,
    stats_path: Path,
) -> list[str]:
    return [
        str(binary),
        "--circuit",
        str(circuit),
        "--sample-num-shots",
        str(shots),
        "--sample-seed",
        str(SAMPLE_SEED),
        "--threads",
        "1",
        "--beam",
        str(preset["beam"]),
        "--beam-climbing",
        "--no-revisit-dets",
        "--pqlimit",
        str(preset["pqlimit"]),
        "--num-det-orders",
        str(preset["num_det_orders"]),
        "--det-order-index",
        "--det-order-seed",
        str(DET_ORDER_SEED),
        "--stats-out",
        str(stats_path),
    ]


def write_outputs(rows: list[dict[str, object]], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "baseline_summary.json"
    csv_path = output / "baseline_summary.csv"
    payload = {
        "protocol": {
            "source_commit": PINNED_COMMIT,
            "sample_seed": SAMPLE_SEED,
            "det_order_seed": DET_ORDER_SEED,
            "threads": 1,
            "host": {
                "platform": platform.platform(),
                "machine": platform.machine(),
                "python": platform.python_version(),
            },
        },
        "results": rows,
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def svg_bar_chart(
    rows: list[dict[str, object]],
    output_path: Path,
    *,
    value_key: str,
    title: str,
    y_label: str,
) -> None:
    width = 1120
    height = 620
    left = 100
    right = 30
    top = 70
    bottom = 150
    plot_w = width - left - right
    plot_h = height - top - bottom
    values = [float(row[value_key]) for row in rows]
    max_value = max(values, default=1.0)
    if max_value <= 0:
        max_value = 1.0
    bar_slot = plot_w / max(len(rows), 1)
    bar_w = bar_slot * 0.68
    colors = {"short": "#3b82f6", "long": "#f97316"}

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{width / 2}" y="35" text-anchor="middle" '
        'font-family="sans-serif" font-size="24" font-weight="600">'
        f"{title}</text>",
    ]
    for tick in range(6):
        value = max_value * tick / 5
        y = top + plot_h - plot_h * tick / 5
        lines.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}" '
            'stroke="#e5e7eb" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{left - 12}" y="{y + 5:.2f}" text-anchor="end" '
            f'font-family="monospace" font-size="13">{value:.3g}</text>'
        )
    lines.append(
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" '
        'stroke="#111827" stroke-width="2"/>'
    )
    lines.append(
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" '
        f'y2="{top + plot_h}" stroke="#111827" stroke-width="2"/>'
    )
    for index, row in enumerate(rows):
        value = float(row[value_key])
        h = plot_h * value / max_value
        x = left + index * bar_slot + (bar_slot - bar_w) / 2
        y = top + plot_h - h
        color = colors[str(row["preset"])]
        label = f'{row["case"]}\\n{row["preset"]}'
        lines.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{h:.2f}" '
            f'fill="{color}" rx="3"/>'
        )
        lines.append(
            f'<text x="{x + bar_w / 2:.2f}" y="{max(y - 8, 55):.2f}" '
            f'text-anchor="middle" font-family="monospace" font-size="12">{value:.4g}</text>'
        )
        parts = label.split("\\n")
        for line_index, part in enumerate(parts):
            lines.append(
                f'<text x="{x + bar_w / 2:.2f}" '
                f'y="{top + plot_h + 25 + line_index * 18:.2f}" text-anchor="middle" '
                f'font-family="sans-serif" font-size="12">{part}</text>'
            )
    lines.append(
        f'<text x="25" y="{top + plot_h / 2}" text-anchor="middle" '
        f'transform="rotate(-90 25 {top + plot_h / 2})" '
        f'font-family="sans-serif" font-size="15">{y_label}</text>'
    )
    lines.append(
        f'<rect x="{width - 215}" y="48" width="14" height="14" fill="{colors["short"]}"/>'
    )
    lines.append(
        f'<text x="{width - 195}" y="60" font-family="sans-serif" font-size="13">short beam</text>'
    )
    lines.append(
        f'<rect x="{width - 110}" y="48" width="14" height="14" fill="{colors["long"]}"/>'
    )
    lines.append(
        f'<text x="{width - 90}" y="60" font-family="sans-serif" font-size="13">long beam</text>'
    )
    lines.append("</svg>")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    default_root = Path(__file__).resolve().parents[4]
    parser.add_argument(
        "--source",
        type=Path,
        default=default_root / ".external" / "tesseract-decoder",
    )
    parser.add_argument(
        "--bazel",
        type=Path,
        default=default_root / ".external" / "bin" / "bazel",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            default_root
            / "tracks"
            / "qcs"
            / "results"
            / "20260727-232344-tesseract-baseline"
        ),
    )
    parser.add_argument("--shots", type=int, default=1000)
    parser.add_argument("--warmup-shots", type=int, default=10)
    parser.add_argument("--skip-build", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.source.resolve()
    bazel = args.bazel.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    ensure_source(source)
    ensure_bazel(bazel)
    if not args.skip_build:
        build(source, bazel)
    binary = source / "bazel-bin" / "src" / "tesseract"
    if not binary.is_file():
        raise RuntimeError(f"Tesseract binary was not built: {binary}")

    rows: list[dict[str, object]] = []
    total_points = len(CASES) * len(PRESETS)
    point = 0
    for case in CASES:
        for preset_name, preset in PRESETS.items():
            point += 1
            circuit = source / case["circuit"]
            stem = f'{case["name"]}_{preset_name}'
            warmup_path = output / f"{stem}_warmup.json"
            result_path = output / f"{stem}.json"
            print(
                f"[{point}/{total_points}] {case['family']} / {preset_name}: "
                f"warm-up {args.warmup_shots} shots",
                flush=True,
            )
            warmup_command = decoder_command(
                binary, circuit, preset, args.warmup_shots, warmup_path
            )
            run_checked(warmup_command, source, quiet=True)
            print(
                f"[{point}/{total_points}] {case['family']} / {preset_name}: "
                f"measure {args.shots} shots",
                flush=True,
            )
            command = decoder_command(binary, circuit, preset, args.shots, result_path)
            start = time.perf_counter()
            run_checked(command, source, quiet=True)
            process_wall = time.perf_counter() - start
            stats = json.loads(result_path.read_text(encoding="utf-8"))
            decoded_shots = int(stats["num_shots"])
            decode_seconds = float(stats["total_time_seconds"])
            row: dict[str, object] = {
                "case": case["name"],
                "family": case["family"],
                "preset": preset_name,
                "circuit": case["circuit"],
                "shots": decoded_shots,
                "num_errors": int(stats["num_errors"]),
                "num_low_confidence": int(stats["num_low_confidence"]),
                "decode_seconds": decode_seconds,
                "milliseconds_per_shot": 1000 * decode_seconds / decoded_shots,
                "process_wall_seconds": process_wall,
                "sample_seed": SAMPLE_SEED,
                "det_order_seed": DET_ORDER_SEED,
                "beam": preset["beam"],
                "pqlimit": preset["pqlimit"],
                "num_det_orders": preset["num_det_orders"],
                "source_commit": PINNED_COMMIT,
            }
            rows.append(row)
            write_outputs(rows, output)
            print(
                f"    {row['milliseconds_per_shot']:.6g} ms/shot, "
                f"errors={row['num_errors']}, "
                f"low-confidence={row['num_low_confidence']}",
                flush=True,
            )

    svg_bar_chart(
        rows,
        output / "runtime.svg",
        value_key="milliseconds_per_shot",
        title="Official Tesseract baseline runtime",
        y_label="decoder time (ms / shot)",
    )
    svg_bar_chart(
        rows,
        output / "logical_errors.svg",
        value_key="num_errors",
        title=f"Official Tesseract outcomes ({args.shots} fixed-seed shots)",
        y_label="logical error count",
    )
    print(f"Baseline complete: {output}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
