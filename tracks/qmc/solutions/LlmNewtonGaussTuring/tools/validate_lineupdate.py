#!/usr/bin/env python3
"""Validate C++ and Julia line updates against finite-temperature ED."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import shutil
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path


OBSERVABLES = ("energy_per_site", "mx", "mz2")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_qmc_line(line: str) -> dict[str, dict[str, float]]:
    values = [float(value) for value in line.strip().split(",")]
    if len(values) != 10:
        raise RuntimeError(f"expected ten QMC columns, got: {line!r}")
    return {
        "energy_per_site": {"mean": values[0], "standard_error": values[1]},
        "mx": {"mean": values[2], "standard_error": values[3]},
        "mz2": {"mean": values[4], "standard_error": values[5]},
        "mz4": {"mean": values[6], "standard_error": values[7]},
        "binder": {"mean": values[8], "standard_error": values[9]},
    }


def run_qmc(command: list[str]) -> dict[str, object]:
    completed = subprocess.run(command, check=True, text=True, capture_output=True)
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"QMC command returned no stdout: {command}")
    return {
        "command": command,
        "observables": parse_qmc_line(lines[-1]),
        "stderr": completed.stderr.strip(),
    }


def combine_chains(chains: list[dict[str, object]], exact: dict[str, float]) -> dict[str, object]:
    combined: dict[str, object] = {}
    count = len(chains)
    for observable in OBSERVABLES:
        means = [float(chain["observables"][observable]["mean"]) for chain in chains]
        errors = [
            float(chain["observables"][observable]["standard_error"])
            for chain in chains
        ]
        mean = statistics.mean(means)
        propagated_error = math.sqrt(sum(error * error for error in errors)) / count
        chain_spread_error = statistics.stdev(means) / math.sqrt(count)
        conservative_error = max(propagated_error, chain_spread_error)
        difference = mean - exact[observable]
        z_score = abs(difference) / conservative_error if conservative_error > 0.0 else math.inf
        combined[observable] = {
            "mean": mean,
            "standard_error": conservative_error,
            "within_chain_propagated_error": propagated_error,
            "between_chain_standard_error": chain_spread_error,
            "exact": exact[observable],
            "difference": difference,
            "absolute_z_score": z_score,
            "pass_5sigma": z_score <= 5.0,
        }
    return combined


def main() -> int:
    project = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, default=project / "build" / "tfim_lineupdate")
    parser.add_argument("--julia", default=shutil.which("julia") or "julia")
    parser.add_argument("--thermalization", type=int, default=5000)
    parser.add_argument("--measurements", type=int, default=30000)
    parser.add_argument("--seeds", default="12345,23456,34567")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    seeds = [int(seed) for seed in args.seeds.split(",")]
    if len(seeds) < 2:
        parser.error("at least two independent seeds are required")

    executable = args.executable.resolve()
    qmc_source = (project / "src" / "TIM_lattice_QMC.jl").resolve()
    ed_source = (project / "src" / "TIM_lattice_ED.jl").resolve()
    fixed = ["honeycomb", "2", "2", "-1.0", "2.1325", "0.0", "4.0"]

    ed_command = [args.julia, "--startup-file=no", str(ed_source), *fixed, "4.0", "1.0"]
    ed_completed = subprocess.run(ed_command, check=True, text=True, capture_output=True)
    ed_values = [float(value) for value in ed_completed.stdout.strip().splitlines()[-1].split(",")]
    if len(ed_values) != 5:
        raise RuntimeError(f"expected five ED columns, got: {ed_completed.stdout!r}")
    exact = {"energy_per_site": ed_values[1], "mx": ed_values[2], "mz2": ed_values[4]}

    cpp_chains = []
    julia_chains = []
    for seed in seeds:
        run_args = [str(args.thermalization), str(args.measurements), str(seed), "0.0", "50"]
        cpp_chains.append(run_qmc([str(executable), *fixed, *run_args]))
        julia_chains.append(
            run_qmc(
                [
                    args.julia,
                    "--startup-file=no",
                    str(qmc_source),
                    *fixed,
                    str(args.thermalization),
                    str(args.measurements),
                    str(seed),
                ]
            )
        )

    cpp_combined = combine_chains(cpp_chains, exact)
    julia_combined = combine_chains(julia_chains, exact)
    success = all(
        bool(summary[observable]["pass_5sigma"])
        for summary in (cpp_combined, julia_combined)
        for observable in OBSERVABLES
    )
    result = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "success": success,
        "criterion": "combined independent-chain mean agrees with ED within 5 conservative standard errors",
        "settings": {
            "lattice": "honeycomb",
            "Lx": 2,
            "Ly": 2,
            "sites": 8,
            "interaction_J": -1.0,
            "transverse_field_Gamma": 2.1325,
            "longitudinal_field_B": 0.0,
            "beta": 4.0,
            "thermalization_sweeps": args.thermalization,
            "measurement_sweeps": args.measurements,
            "bins": 50,
            "seeds": seeds,
        },
        "exact_diagonalization": {"command": ed_command, "observables": exact},
        "cpp": {"combined": cpp_combined, "chains": cpp_chains},
        "julia": {"combined": julia_combined, "chains": julia_chains},
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "julia": subprocess.run(
                [args.julia, "--version"], check=True, text=True, capture_output=True
            ).stdout.strip(),
        },
        "provenance": {
            "executable_sha256": sha256(executable),
            "cpp_source_sha256": sha256(project / "cpp" / "src" / "tfim_sse.cpp"),
            "julia_qmc_sha256": sha256(qmc_source),
            "julia_ed_sha256": sha256(ed_source),
            "validator_sha256": sha256(Path(__file__).resolve()),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": success, "cpp": cpp_combined, "julia": julia_combined}, indent=2))
    print(args.output)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
