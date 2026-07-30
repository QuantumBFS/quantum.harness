from __future__ import annotations

import argparse
import json
import os
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

from .dmrg_runner import limit_bond_dimensions, load_config, run_dmrg
from .fcidump_audit import audit_fcidump
from .render_convergence import render_run
from .verify_checkpoint import verify_checkpoint


def _memory_to_mb(raw: str) -> int:
    value = raw.strip().upper()
    factors = {"K": 1 / 1024, "M": 1, "G": 1024, "T": 1024 * 1024}
    if value and value[-1] in factors:
        return int(float(value[:-1]) * factors[value[-1]])
    return int(value)


def _allocated_memory_mb(environment: Mapping[str, str], cpus: int) -> int:
    if raw := environment.get("SLURM_MEM_PER_NODE"):
        return _memory_to_mb(raw)
    if raw := environment.get("SLURM_MEM_PER_CPU"):
        return _memory_to_mb(raw) * cpus
    raise ValueError(
        "Slurm memory is unknown: SLURM_MEM_PER_NODE and "
        "SLURM_MEM_PER_CPU are both unset"
    )


def preflight_cluster_run(
    config_path: str | Path,
    run_dir: str | Path,
    *,
    target_m: int,
    environment: Mapping[str, str] | None = None,
) -> dict:
    """Validate the scientific input and the live Slurm allocation."""

    env = os.environ if environment is None else environment
    if not env.get("SLURM_JOB_ID"):
        raise ValueError("SLURM_JOB_ID is unset; refusing to run outside Slurm")

    config = limit_bond_dimensions(load_config(config_path), target_m)
    cpus = int(env.get("SLURM_CPUS_PER_TASK", "0"))
    if cpus < config.dmrg.threads:
        raise ValueError(
            f"SLURM_CPUS_PER_TASK={cpus} is smaller than "
            f"dmrg.threads={config.dmrg.threads}"
        )
    memory_mb = _allocated_memory_mb(env, cpus)
    stack_memory_mb = int(config.dmrg.stack_mem_gb * 1024)
    if memory_mb < stack_memory_mb:
        raise ValueError(
            f"Slurm memory {memory_mb} MB is smaller than block2 "
            f"stack_mem_gb={config.dmrg.stack_mem_gb}"
        )

    run_path = Path(run_dir)
    input_path = run_path / "inputs" / config.instance.filename
    audit = audit_fcidump(
        input_path,
        expected_norb=config.instance.norb,
        expected_nelec=config.instance.nelec,
        expected_ms2=config.instance.ms2,
        expected_sha256=config.instance.sha256,
    )
    return {
        "status": "ready",
        "job_id": env["SLURM_JOB_ID"],
        "instance": config.instance.name,
        "input": {
            "path": str(input_path.resolve()),
            "sha256": audit.sha256,
            "size_bytes": audit.size_bytes,
        },
        "sector": {
            "norb": config.instance.norb,
            "nelec": config.instance.nelec,
            "ms2": config.instance.ms2,
            "spin": config.dmrg.spin,
            "symmetry": config.dmrg.symmetry,
        },
        "ordering": config.ordering.method,
        "observable": "saved finite-M MPS energy expectation",
        "bond_dimensions": list(config.dmrg.bond_dimensions),
        "target_m": target_m,
        "resources": {
            "cpus_per_task": cpus,
            "block2_threads": config.dmrg.threads,
            "memory_mb": memory_mb,
            "block2_stack_mem_gb": config.dmrg.stack_mem_gb,
        },
    }


def _write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def run_cluster_job(
    config_path: str | Path,
    run_dir: str | Path,
    *,
    target_m: int,
) -> dict:
    run_path = Path(run_dir)
    manifest_path = run_path / "cluster-job.json"
    preflight = preflight_cluster_run(
        config_path,
        run_path,
        target_m=target_m,
    )
    document = {
        "schema_version": 1,
        "status": "running",
        "started_at_utc": datetime.now(UTC).isoformat(),
        "preflight": preflight,
    }
    _write_json(manifest_path, document)
    print(json.dumps(preflight, sort_keys=True), flush=True)

    try:
        result = run_dmrg(
            config_path,
            run_path,
            resume=True,
            max_bond_dimension=target_m,
        )
        checkpoint = verify_checkpoint(run_path)
        plot, report = render_run(run_path)
        document.update(
            {
                "status": "completed",
                "completed_at_utc": datetime.now(UTC).isoformat(),
                "headline": result["headline"],
                "checkpoint_verification": checkpoint,
                "artifacts": {
                    "result": str((run_path / "result.json").resolve()),
                    "checkpoint_verification": str(
                        (run_path / "checkpoint-verification.json").resolve()
                    ),
                    "convergence_plot": str(plot.resolve()),
                    "report": str(report.resolve()),
                },
            }
        )
        _write_json(manifest_path, document)
        return document
    except BaseException as exc:
        document.update(
            {
                "status": "failed",
                "failed_at_utc": datetime.now(UTC).isoformat(),
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                },
            }
        )
        _write_json(manifest_path, document)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preflight and run one checkpointed Anderson DMRG stage"
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--target-m", required=True, type=int)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()

    if args.preflight_only:
        report = preflight_cluster_run(
            args.config,
            args.run_dir,
            target_m=args.target_m,
        )
        print(json.dumps(report, indent=2, sort_keys=True), flush=True)
        return
    result = run_cluster_job(
        args.config,
        args.run_dir,
        target_m=args.target_m,
    )
    print(json.dumps(result["headline"], sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
