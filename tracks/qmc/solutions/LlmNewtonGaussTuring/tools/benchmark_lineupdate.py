#!/usr/bin/env python3
"""Benchmark the C++ and warmed Julia merge-unmerge line updates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import re
import shutil
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ELAPSED_PATTERN = re.compile(r"elapsed_seconds=([0-9.eE+-]+)")


def parse_sizes(value: str) -> list[int]:
    sizes = [int(item) for item in value.split(",") if item]
    if not sizes or any(size <= 0 for size in sizes):
        raise argparse.ArgumentTypeError("sizes must be a comma-separated list of positive integers")
    return sizes


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command_version(command: list[str]) -> str:
    completed = subprocess.run(command, check=True, text=True, capture_output=True)
    return (completed.stdout or completed.stderr).splitlines()[0]


def cpu_model() -> str:
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    return platform.processor() or "unknown"


def run_cpp(executable: Path, args: argparse.Namespace, size: int, seed: int) -> float:
    beta = args.beta_factor * size
    command = [
        str(executable),
        args.lattice,
        str(size),
        str(size),
        str(args.interaction),
        str(args.gamma),
        str(args.longitudinal_field),
        str(beta),
        str(args.thermalization),
        str(args.measurements),
        str(seed),
        str(args.anneal_start),
        str(args.bins),
    ]
    completed = subprocess.run(command, check=True, text=True, capture_output=True)
    match = ELAPSED_PATTERN.search(completed.stderr)
    if match is None:
        raise RuntimeError(f"C++ timing line missing from stderr: {completed.stderr}")
    return float(match.group(1))


def run_julia(
    julia: str,
    source: Path,
    args: argparse.Namespace,
    size: int,
    seeds: list[int],
) -> list[float]:
    beta = args.beta_factor * size
    source_literal = json.dumps(str(source))
    lattice_literal = json.dumps(args.lattice)
    seed_literal = ",".join(str(seed) for seed in seeds)
    code = f"""
include({source_literal})
run({lattice_literal}, 2, 2, {args.interaction}, {args.gamma},
    {args.longitudinal_field}, 4.0, 20, 20, {seeds[0]}; nbin=2,
    G0={args.anneal_start})
GC.gc()
times = Float64[]
for seed in [{seed_literal}]
    GC.gc()
    push!(times, @elapsed run({lattice_literal}, {size}, {size},
        {args.interaction}, {args.gamma}, {args.longitudinal_field}, {beta},
        {args.thermalization}, {args.measurements}, seed;
        nbin={args.bins}, G0={args.anneal_start}))
end
println(join(times, ","))
"""
    completed = subprocess.run(
        [julia, "--startup-file=no", "--history-file=no", "-e", code],
        check=True,
        text=True,
        capture_output=True,
    )
    output_lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not output_lines:
        raise RuntimeError("Julia benchmark returned no timing data")
    times = [float(value) for value in output_lines[-1].split(",")]
    if len(times) != len(seeds):
        raise RuntimeError(f"expected {len(seeds)} Julia timings, got {times}")
    return times


def parse_args() -> argparse.Namespace:
    project = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lattice", choices=("triangular", "honeycomb", "square"), default="triangular")
    parser.add_argument("--sizes", type=parse_sizes, default=parse_sizes("4,8,12"))
    parser.add_argument("--interaction", type=float, default=-1.0)
    parser.add_argument("--gamma", type=float, default=4.768)
    parser.add_argument("--longitudinal-field", type=float, default=0.0)
    parser.add_argument("--beta-factor", type=float, default=2.0)
    parser.add_argument("--thermalization", type=int, default=1000)
    parser.add_argument("--measurements", type=int, default=3000)
    parser.add_argument("--bins", type=int, default=50)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=41000)
    parser.add_argument("--anneal-start", type=float, default=0.0)
    parser.add_argument("--executable", type=Path, default=project / "build" / "tfim_lineupdate")
    parser.add_argument("--julia", default=shutil.which("julia") or "julia")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--run-spec",
        type=Path,
        help="optional parameter-scan run_spec.json; writes one manifest per L cell",
    )
    args = parser.parse_args()
    if args.repeats < 1 or args.thermalization < 0 or args.measurements < 2:
        parser.error("repeats must be positive; measurements must be >=2")
    if args.bins < 2 or args.bins > args.measurements:
        parser.error("bins must be in [2, measurements]")
    if args.beta_factor <= 0.0 or args.gamma <= 0.0:
        parser.error("beta-factor and gamma must be positive")
    return args


def main() -> int:
    args = parse_args()
    project = Path(__file__).resolve().parents[1]
    executable = args.executable.resolve()
    julia_source = (project / "src" / "TIM_lattice_QMC.jl").resolve()
    if not executable.is_file():
        raise SystemExit(f"missing executable: {executable}; build the Release target first")
    if not julia_source.is_file():
        raise SystemExit(f"missing Julia reference: {julia_source}")

    rows: list[dict[str, object]] = []
    total_sweeps = args.thermalization + args.measurements
    for size in args.sizes:
        seeds = [args.seed + 1000 * size + repeat for repeat in range(args.repeats)]
        julia_times = run_julia(args.julia, julia_source, args, size, seeds)
        cpp_times = [run_cpp(executable, args, size, seed) for seed in seeds]
        sites = 2 * size * size if args.lattice == "honeycomb" else size * size
        for repeat, (seed, cpp_seconds, julia_seconds) in enumerate(
            zip(seeds, cpp_times, julia_times), start=1
        ):
            rows.append(
                {
                    "lattice": args.lattice,
                    "L": size,
                    "sites": sites,
                    "beta": args.beta_factor * size,
                    "thermalization_sweeps": args.thermalization,
                    "measurement_sweeps": args.measurements,
                    "repeat": repeat,
                    "seed": seed,
                    "cpp_seconds": cpp_seconds,
                    "julia_seconds": julia_seconds,
                    "speedup": julia_seconds / cpp_seconds,
                    "cpp_sweeps_per_second": total_sweeps / cpp_seconds,
                    "julia_sweeps_per_second": total_sweeps / julia_seconds,
                }
            )
        print(
            f"{args.lattice} L={size}: "
            f"C++ {statistics.median(cpp_times):.6g}s, "
            f"Julia {statistics.median(julia_times):.6g}s, "
            f"speedup {statistics.median(julia_times) / statistics.median(cpp_times):.3f}x"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    run_spec = None
    if args.run_spec is not None:
        run_spec = json.loads(args.run_spec.read_text(encoding="utf-8"))
        planned_sizes = [int(cell["params"]["L"]) for cell in run_spec["cells"]]
        if planned_sizes != args.sizes:
            raise RuntimeError(
                f"run-spec L axis {planned_sizes} does not match --sizes {args.sizes}"
            )
        run_dir = Path(run_spec["run_dir"])
        if not run_dir.is_absolute():
            run_dir = (Path.cwd() / run_dir).resolve()
        for cell in run_spec["cells"]:
            size = int(cell["params"]["L"])
            cell_rows = [row for row in rows if int(row["L"]) == size]
            cpp_seconds = statistics.median(float(row["cpp_seconds"]) for row in cell_rows)
            julia_seconds = statistics.median(float(row["julia_seconds"]) for row in cell_rows)
            manifest = {
                "success": True,
                "params": cell["params"],
                "settings": {**run_spec.get("settings", {}), **cell.get("settings", {})},
                "provenance": run_spec.get("provenance", {}),
                "protocol": "warmed-julia-constructor-through-measurement-v1",
                "observables": {
                    "cpp_seconds": cpp_seconds,
                    "julia_seconds": julia_seconds,
                    "speedup": julia_seconds / cpp_seconds,
                    "cpp_sweeps_per_second": total_sweeps / cpp_seconds,
                    "julia_sweeps_per_second": total_sweeps / julia_seconds,
                },
                "repeats": cell_rows,
            }
            cell_dir = run_dir / "cells" / cell["cell_id"]
            cell_dir.mkdir(parents=True, exist_ok=True)
            (cell_dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )

    source_paths = [
        project / "CMakeLists.txt",
        *sorted((project / "cpp").rglob("*.cpp")),
        *sorted((project / "cpp").rglob("*.hpp")),
        julia_source,
        Path(__file__).resolve(),
    ]
    reference_repo = project.parent / "sse_new"
    reference_commit = "unavailable"
    if reference_repo.is_dir():
        completed = subprocess.run(
            ["git", "-C", str(reference_repo), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
        )
        if completed.returncode == 0:
            reference_commit = completed.stdout.strip()
    manifest = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "command": [sys.executable, *sys.argv],
        "timing_scope": "constructor plus thermalization and measurement; Julia JIT warm-up excluded",
        "settings": {
            "lattice": args.lattice,
            "sizes": args.sizes,
            "interaction": args.interaction,
            "gamma": args.gamma,
            "longitudinal_field": args.longitudinal_field,
            "beta_factor": args.beta_factor,
            "thermalization_sweeps": args.thermalization,
            "measurement_sweeps": args.measurements,
            "bins": args.bins,
            "repeats": args.repeats,
            "base_seed": args.seed,
            "anneal_start": args.anneal_start,
        },
        "environment": {
            "platform": platform.platform(),
            "cpu": cpu_model(),
            "python": platform.python_version(),
            "julia": command_version([args.julia, "--version"]),
            "compiler": command_version(["c++", "--version"]),
        },
        "provenance": {
            "sse_new_reference_commit": reference_commit,
            "files": {str(path.relative_to(project)): sha256(path) for path in source_paths},
            "executable_sha256": sha256(executable),
        },
        "rows": rows,
    }
    if run_spec is not None:
        manifest["parameter_scan"] = {
            "run_id": run_spec["run_id"],
            "run_spec_sha256": sha256(args.run_spec),
        }
    manifest_path = args.output.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    print(f"wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
