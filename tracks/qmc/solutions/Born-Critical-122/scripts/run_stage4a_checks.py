#!/usr/bin/env python3
"""Run Stage-4A exact/Gaussian checks on a compute node."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import socket
from statistics import NormalDist
import subprocess
import sys


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def source_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in {".py", ".json", ".toml", ".yml"}:
            continue
        relative = path.relative_to(root).as_posix().encode()
        digest.update(relative)
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(root / "src")
    command = [
        sys.executable,
        "-u",
        "-m",
        "unittest",
        "discover",
        "-s",
        str(root / "tests"),
        "-v",
    ]
    with (output / "unittest.log").open("w") as log:
        process = subprocess.Popen(
            command,
            cwd=root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            log.write(line)
        return_code = process.wait()

    metrics: dict[str, object] = {}
    if return_code == 0:
        sys.path.insert(0, str(root / "src"))
        from borncritical.born_circuit_oracle import enumerate_circuit_distribution
        from borncritical.gaussian_born import GaussianBornCircuit
        import numpy as np

        for size, layers in ((2, 2), (4, 1)):
            outcomes = enumerate_circuit_distribution(
                size, layers, vacuum_only=True, max_variables=8
            )
            total_variation = 0.5 * math.fsum(
                abs(item.probability - item.gaussian_probability)
                for item in outcomes
            )
            prefix = f"L{size}_T{layers}"
            metrics[f"{prefix}_outcomes"] = len(outcomes)
            metrics[f"{prefix}_normalization_error"] = abs(
                math.fsum(item.probability for item in outcomes) - 1.0
            )
            metrics[f"{prefix}_dense_gaussian_total_variation"] = total_variation
            metrics[f"{prefix}_forbidden_wilson_records"] = sum(
                sum(item.bits[:size]) % 2 for item in outcomes
            )

        # Precomputed 95% simultaneous multinomial intervals for an actual
        # sequential Gaussian sampler (conditioned on the vacuum Wilson loop).
        unconditional = enumerate_circuit_distribution(
            2, 2, vacuum_only=False, max_variables=8
        )
        vacuum_mass = math.fsum(
            item.probability
            for item in unconditional
            if sum(item.bits[:2]) % 2 == 0
        )
        outcomes = enumerate_circuit_distribution(
            2, 2, vacuum_only=True, max_variables=8
        )
        exact = {item.bits: item.probability for item in outcomes}
        sample_count = 20_000
        counts = {bits: 0 for bits in exact}
        maximum_chain_error = 0.0
        forbidden = 0
        rng = np.random.default_rng(4226072801)
        accepted = 0
        while accepted < sample_count:
            circuit = GaussianBornCircuit(size=2)
            bits_list: list[int] = []
            for _ in range(2):
                layer = circuit.sample_layer(rng)
                bits_list.extend(int(value == -1) for value in layer.s)
                bits_list.extend(int(value == -1) for value in layer.t)
            bits = tuple(bits_list)
            if sum(bits[:2]) % 2:
                continue
            if bits not in counts:
                forbidden += 1
                continue
            conditional_log_probability = (
                circuit.total_log_probability - math.log(vacuum_mass)
            )
            maximum_chain_error = max(
                maximum_chain_error,
                abs(conditional_log_probability - math.log(exact[bits])),
            )
            counts[bits] += 1
            accepted += 1

        # Bonferroni-normal simultaneous intervals are conservative here; the
        # +1 continuity allowance covers the very smallest categories.
        z_score = NormalDist().inv_cdf(
            1.0 - 0.05 / (2.0 * len(outcomes))
        )
        interval_violations = 0
        maximum_standardized_residual = 0.0
        for bits, probability in exact.items():
            expected = sample_count * probability
            sigma = math.sqrt(sample_count * probability * (1.0 - probability))
            residual = abs(counts[bits] - expected)
            maximum_standardized_residual = max(
                maximum_standardized_residual,
                0.0 if sigma == 0.0 else residual / sigma,
            )
            if residual > z_score * sigma + 1.0:
                interval_violations += 1
        metrics.update(
            {
                "mc_sample_count": sample_count,
                "mc_simultaneous_interval_z": z_score,
                "mc_interval_violations": interval_violations,
                "mc_maximum_standardized_residual": maximum_standardized_residual,
                "mc_forbidden_wilson_records": forbidden,
                "mc_chain_log_probability_max_abs_error": maximum_chain_error,
            }
        )
        atomic_json(output / "metrics.json", metrics)

    manifest = {
        "schema_version": 1,
        "stage": "stage4a",
        "status": "success" if return_code == 0 else "failed",
        "return_code": return_code,
        "started_at": started,
        "finished_at": utc_now(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": sys.version,
        "source_sha256": source_digest(root),
        "slurm": {
            "job_id": os.environ.get("SLURM_JOB_ID"),
            "cpus_per_task": os.environ.get("SLURM_CPUS_PER_TASK"),
            "job_nodelist": os.environ.get("SLURM_JOB_NODELIST"),
        },
        "artifacts": ["unittest.log", "metrics.json"] if metrics else ["unittest.log"],
    }
    atomic_json(output / "manifest.json", manifest)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
