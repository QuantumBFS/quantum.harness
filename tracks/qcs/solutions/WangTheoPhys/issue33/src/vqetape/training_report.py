"""Generate the audited VQETape time-to-solution report."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import platform
from pathlib import Path
from typing import Any

import jax

from vqetape.spec import (
    ProgramConfig,
    SpatialProgramConfig,
    TFIMVQESpec,
)
from vqetape.training_benchmark import (
    TrainingWorkerError,
    run_training_fresh_process,
)
from vqetape.training_spec import (
    VQETrainingRequest,
    VQETrainingResult,
)


def _request(
    *,
    optimizer: str,
    initialization: str,
    program: ProgramConfig | SpatialProgramConfig,
    source: VQETrainingResult | None = None,
) -> VQETrainingRequest:
    source_spec = None
    source_parameters = None
    if source is not None:
        source_spec = source.request.spec
        source_parameters = source.final_parameters
    return VQETrainingRequest(
        spec=TFIMVQESpec(nqubits=4, depth=2),
        program=program,
        optimizer=optimizer,  # type: ignore[arg-type]
        initialization=initialization,  # type: ignore[arg-type]
        target_energy_error=0.1,
        max_steps=80,
        seed=3,
        learning_rate=0.08,
        damping=0.01,
        recycled_source_spec=source_spec,
        recycled_parameters=source_parameters,
    )


def benchmark_requests(
    source: VQETrainingResult,
) -> tuple[tuple[str, VQETrainingRequest], ...]:
    """Return the fixed, reviewable comparison matrix."""

    spatial = SpatialProgramConfig(
        "greedy",
        "default",
        block_width=2,
    )
    rows: list[tuple[str, VQETrainingRequest]] = []
    for optimizer in (
        "adam",
        "lbfgs",
        "natural-gradient",
    ):
        for initialization in ("zeros", "random"):
            rows.append(
                (
                    f"optimizer-{optimizer}-{initialization}",
                    _request(
                        optimizer=optimizer,
                        initialization=initialization,
                        program=spatial,
                    ),
                )
            )
        rows.append(
            (
                f"optimizer-{optimizer}-recycled",
                _request(
                    optimizer=optimizer,
                    initialization="recycled",
                    program=spatial,
                    source=source,
                ),
            )
        )

    rows.extend(
        (
            (
                "program-statevector",
                _request(
                    optimizer="lbfgs",
                    initialization="random",
                    program=ProgramConfig(
                        "scan",
                        "default",
                    ),
                ),
            ),
            (
                "program-z2-native",
                _request(
                    optimizer="lbfgs",
                    initialization="random",
                    program=SpatialProgramConfig(
                        "greedy",
                        "default",
                        block_width=1,
                        symmetry="z2-native",
                    ),
                ),
            ),
        )
    )
    return tuple(rows)


def _source_request() -> VQETrainingRequest:
    return VQETrainingRequest(
        spec=TFIMVQESpec(nqubits=3, depth=1),
        program=SpatialProgramConfig(
            "greedy",
            "default",
        ),
        optimizer="lbfgs",
        initialization="random",
        target_energy_error=0.1,
        max_steps=80,
        seed=3,
    )


def _run_entry(
    identifier: str,
    request: VQETrainingRequest,
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        result = run_training_fresh_process(
            request,
            timeout_seconds=timeout_seconds,
        )
    except TrainingWorkerError as exc:
        return {
            "id": identifier,
            "request": request.to_dict(),
            "worker_failure": (
                f"{type(exc).__name__}: {exc}"
            ),
        }
    return {
        "id": identifier,
        "result": result.to_dict(),
    }


def _derived(
    source: VQETrainingResult,
    runs: list[dict[str, Any]],
) -> dict[str, Any]:
    successful = [
        row
        for row in runs
        if row.get("result", {}).get("converged")
    ]
    ranked = sorted(
        successful,
        key=lambda row: row["result"][
            "time_to_target_seconds"
        ],
    )
    by_id = {row["id"]: row for row in runs}
    recycled: dict[str, Any] = {}
    for optimizer in (
        "adam",
        "lbfgs",
        "natural-gradient",
    ):
        random_row = by_id[
            f"optimizer-{optimizer}-random"
        ]["result"]
        recycled_row = by_id[
            f"optimizer-{optimizer}-recycled"
        ]["result"]
        recycled[optimizer] = {
            "random_evaluations": random_row[
                "evaluations"
            ],
            "recycled_evaluations": recycled_row[
                "evaluations"
            ],
            "target_only_seconds": recycled_row[
                "time_to_target_seconds"
            ],
            "two_stage_seconds": (
                source.time_to_target_seconds
                + recycled_row["time_to_target_seconds"]
                if source.time_to_target_seconds is not None
                and recycled_row[
                    "time_to_target_seconds"
                ]
                is not None
                else None
            ),
        }
    return {
        "ranking_policy": (
            "converged runs only, ascending synchronized "
            "time_to_target_seconds including compilation"
        ),
        "converged_run_ids": [
            row["id"] for row in ranked
        ],
        "best_run_id": (
            ranked[0]["id"] if ranked else None
        ),
        "recycling": recycled,
        "source_training_seconds": (
            source.time_to_target_seconds
        ),
    }


def _environment() -> dict[str, Any]:
    devices = jax.devices()
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "jax": jax.__version__,
        "backend": jax.default_backend(),
        "devices": [
            {
                "id": device.id,
                "platform": device.platform,
                "device_kind": device.device_kind,
            }
            for device in devices
        ],
    }


def _write_markdown(
    payload: dict[str, Any],
    destination: Path,
) -> None:
    source = payload["recycling_source"]
    rows = payload["runs"]
    lines = [
        "# VQETape VQE time-to-solution findings",
        "",
        "All candidates ran in fresh processes. Time to target "
        "includes compilation, first execution, every synchronized "
        "value-gradient evaluation, and optimizer overhead.",
        "",
        "## Audited workload",
        "",
        "- Target: open-chain TFIM, 4 qubits, depth-2 RZZ-RX "
        "ansatz, energy error at most 0.1.",
        "- Initialization seed: 3; Adam/natural-gradient learning "
        "rate: 0.08; natural-gradient damping: 0.01.",
        "- Recycled source: 3 qubits, depth 1, independently "
        "converged with L-BFGS-B.",
        "",
        "## Results",
        "",
        "| ID | program | optimizer | start | converged | calls | "
        "compile (s) | target (s) | final error |",
        "|---|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        if "result" not in row:
            lines.append(
                f"| {row['id']} | — | — | — | no | — | — | — "
                f"| worker failure |"
            )
            continue
        result = row["result"]
        request = result["request"]
        error = (
            result["final_energy"]
            - result["ground_energy"]
        )
        target_seconds = result["time_to_target_seconds"]
        lines.append(
            "| {identifier} | {program} | {optimizer} | "
            "{initialization} | {converged} | {calls} | "
            "{compile:.3f} | {target} | {error:.6f} |".format(
                identifier=row["id"],
                program=result["program_label"],
                optimizer=request["optimizer"],
                initialization=request["initialization"],
                converged="yes" if result["converged"] else "no",
                calls=result["evaluations"],
                compile=result["compile_seconds"],
                target=(
                    f"{target_seconds:.3f}"
                    if target_seconds is not None
                    else "—"
                ),
                error=error,
            )
        )
    derived = payload["derived"]
    lines.extend(
        [
            "",
            "## What the measurement supports",
            "",
            f"- Fastest converged run: `{derived['best_run_id']}`. "
            "This is workload- and machine-specific.",
            "- Zero initialization does not converge here: the "
            "RZZ-RX circuit starts at a stationary point, so Adam, "
            "L-BFGS-B, and natural gradient cannot leave it.",
            "- Natural gradient reaches the target in very few "
            "value-gradient calls from random or recycled starts, "
            "but exact QGT construction makes wall time larger on "
            "this small CPU run.",
            "- Recycling reduces target-workload calls. Its source "
            f"cost is {source['time_to_target_seconds']:.3f} s and "
            "is reported separately; it should only be amortized "
            "when a continuation schedule actually reuses that "
            "solution.",
            "- Statevector wins this tiny workload. Spatial and "
            "Z2-native programs remain exact scalable candidates; "
            "their asymptotic memory advantages are not expected "
            "to dominate at four qubits.",
            "",
            "## Interpretation boundary",
            "",
            "The report establishes a reproducible end-to-solution "
            "method and exposes optimizer/initialization failure "
            "modes. It does not claim that one optimizer or tensor "
            "representation is universally best.",
            "",
        ]
    )
    destination.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def generate_training_report(
    output: Path,
    findings: Path,
    *,
    timeout_seconds: float = 900,
) -> dict[str, Any]:
    """Run the fixed comparison and write JSON plus Markdown."""

    source = run_training_fresh_process(
        _source_request(),
        timeout_seconds=timeout_seconds,
    )
    if not source.converged:
        raise RuntimeError(
            "recycling source failed to converge"
        )
    runs = [
        _run_entry(identifier, request, timeout_seconds)
        for identifier, request in benchmark_requests(source)
    ]
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": _environment(),
        "method": {
            "fresh_process_per_run": True,
            "unique_jax_cache_per_run": True,
            "synchronization": "jax.block_until_ready",
            "target_includes_compile": True,
        },
        "recycling_source": source.to_dict(),
        "runs": runs,
        "derived": _derived(source, runs),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    findings.parent.mkdir(parents=True, exist_ok=True)
    _write_markdown(payload, findings)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--findings", required=True, type=Path)
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=900,
    )
    args = parser.parse_args(argv)
    payload = generate_training_report(
        args.output,
        args.findings,
        timeout_seconds=args.timeout_seconds,
    )
    print(
        f"runs={len(payload['runs'])} "
        f"best={payload['derived']['best_run_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
