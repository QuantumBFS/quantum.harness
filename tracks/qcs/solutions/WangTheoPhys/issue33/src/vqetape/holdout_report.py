"""Generate fresh-process longitudinal-Ising holdout evidence."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

from vqetape.holdout import LongitudinalIsingSpec
from vqetape.subprocess_env import worker_environment


def run_holdout_fresh_process(
    spec: LongitudinalIsingSpec,
    *,
    target_energy_error: float = 0.01,
    max_steps: int = 100,
    seed: int = 7,
    timeout_seconds: float = 180,
) -> dict[str, Any]:
    """Run the holdout without sharing JAX state."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    with tempfile.TemporaryDirectory(
        prefix="vqetape-holdout-"
    ) as directory:
        root = Path(directory)
        request_path = root / "request.json"
        output_path = root / "result.json"
        request_path.write_text(
            json.dumps(
                {
                    "spec": spec.to_dict(),
                    "target_energy_error": (
                        target_energy_error
                    ),
                    "max_steps": max_steps,
                    "seed": seed,
                },
                indent=2,
                allow_nan=False,
            ),
            encoding="utf-8",
        )
        environment = worker_environment()
        environment["JAX_ENABLE_X64"] = "1"
        environment["JAX_COMPILATION_CACHE_DIR"] = str(
            root / "jax-cache"
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "vqetape.holdout_worker",
                "--request",
                str(request_path),
                "--output",
                str(output_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=environment,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "holdout worker failed: "
                f"{completed.stderr.strip()}"
            )
        payload = json.loads(
            output_path.read_text(encoding="utf-8")
        )
        worker_pid = payload.pop("worker_pid")
        parent_pid = payload.pop("parent_pid")
        if worker_pid == os.getpid() or parent_pid != os.getpid():
            raise RuntimeError(
                "holdout worker isolation check failed"
            )
        return payload


def _write_findings(
    payload: dict[str, Any],
    destination: Path,
) -> None:
    result = payload["result"]
    z2 = result["z2_spatial_compression"]
    lines = [
        "# VQETape symmetry-breaking holdout findings",
        "",
        "## Workload",
        "",
        "The holdout is the open longitudinal-field Ising chain",
        "",
        "\\[",
        "H=-J\\sum_i Z_iZ_{i+1}-g\\sum_iX_i-h\\sum_iZ_i,",
        "\\]",
        "",
        "with a depth-two RZZ–RY–RX ansatz. Its ground energy "
        "comes from independent dense diagonalization, not the "
        "TFIM free-fermion oracle.",
        "",
        "## Result",
        "",
        f"- Converged: `{result['converged']}`.",
        f"- Calls: `{result['evaluations']}`.",
        f"- Compile: `{result['compile_seconds']:.3f}` s.",
        "- Time to target (including compile): "
        f"`{result['time_to_target_seconds']:.3f}` s.",
        f"- Final energy error: `{result['final_energy_error']:.6g}`.",
        "- Global-X commutator Frobenius norm: "
        f"`{z2['commutator_norm']:.6g}`.",
        "",
        "## Symmetry decision",
        "",
        "Z2-native TFIM compression is explicitly inapplicable:",
        "",
    ]
    lines.extend(
        f"- {reason}" for reason in z2["reasons"]
    )
    lines.extend(
        [
            "",
            "This holdout exercises a different conserved-charge "
            "regime and a symmetry-breaking ansatz family. It is "
            "a small exact generality check, not a claim of "
            "large-system longitudinal-Ising tensor performance.",
            "",
        ]
    )
    destination.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def generate_holdout_report(
    output: Path,
    findings: Path,
) -> dict[str, Any]:
    """Run and serialize the audited holdout."""

    result = run_holdout_fresh_process(
        LongitudinalIsingSpec(
            nqubits=4,
            depth=2,
            longitudinal_field=0.35,
            dtype="complex128",
        )
    )
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "method": {
            "fresh_process": True,
            "unique_jax_cache": True,
            "x64_enabled": True,
            "ground_oracle": "dense-eigvalsh",
            "synchronization": "jax.block_until_ready",
        },
        "result": result,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    findings.parent.mkdir(parents=True, exist_ok=True)
    _write_findings(payload, findings)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--findings", required=True, type=Path)
    args = parser.parse_args(argv)
    payload = generate_holdout_report(
        args.output,
        args.findings,
    )
    print(
        "converged="
        f"{payload['result']['converged']} "
        "error="
        f"{payload['result']['final_energy_error']:.6g}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
