#!/usr/bin/env python3
"""Build a fail-closed production-v2 Slurm bundle without submitting jobs."""

from __future__ import annotations

import argparse
import json
import shlex
import stat
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_SOURCE_PREFLIGHT = (
    ROOT
    / "results_research_program"
    / "hpc"
    / "production_v2_validation_20260730.json"
)


@dataclass(frozen=True)
class BundleResult:
    ready_count: int
    reuse_count: int
    blocked_count: int
    script_paths: tuple[Path, ...]
    matrix_path: Path
    submission_performed: bool = False


def _quote(value: str | Path) -> str:
    return shlex.quote(str(value))


def _status(payload: Mapping[str, Any] | str | Path | None) -> str:
    if payload is None:
        return "missing"
    if isinstance(payload, Mapping):
        if "status" in payload:
            return str(payload["status"])
        return "accepted" if payload.get("accepted") is True else "missing"
    path = Path(payload)
    if not path.is_file():
        return "missing"
    try:
        return _status(json.loads(path.read_text()))
    except (OSError, json.JSONDecodeError):
        return "invalid"


def production_resource_spec(job: Mapping[str, Any]) -> dict[str, Any]:
    """Use the accepted SCNet fine-resolution resource-pilot envelope."""

    fcs = "fcs_logZ" in job.get("observables", [])
    return {
        "cpus": 32 if fcs else 16,
        "memory": "120G" if fcs else "60G",
        "walltime": "7-00:00:00",
        "fcs": fcs,
        "resource_pilot_job_id": "23009308",
    }


def job_block_reasons_v2(
    job: Mapping[str, Any],
    *,
    convergence_status: str,
    source_preflight_status: str,
    j2_status: str,
    unblinding_status: str,
    reuse_status: str | None,
) -> list[str]:
    reasons: list[str] = []
    if convergence_status != "accepted":
        reasons.append("convergence_gate_not_accepted")
    if source_preflight_status != "pass":
        reasons.append("production_v2_source_preflight_missing_or_failed")
    if j2_status != "pass":
        reasons.append("J2_backend_validation_missing_or_failed")
    if str(job["stage"]) == "production_b" and unblinding_status != "opened":
        reasons.append("blinded_until_registered_unblinding")
    if (
        str(job.get("execution_mode")) == "reuse"
        and reuse_status != "accepted"
    ):
        reasons.append("reuse_attestation_missing_or_failed")
    return reasons


def _slurm_text(
    job: Mapping[str, Any],
    *,
    cluster_root: Path,
    source_root: Path,
    python: str,
    partition: str | None,
    account: str | None,
) -> str:
    job_id = str(job["job_id"])
    resource = production_resource_spec(job)
    output = (
        cluster_root
        / "data"
        / "research"
        / "raw"
        / str(job["stage"])
        / f"{job_id}.npz"
    )
    lines = [
        "#!/usr/bin/env bash",
        f"#SBATCH --job-name=khv2_{job_id[:72]}",
        f"#SBATCH --cpus-per-task={resource['cpus']}",
        f"#SBATCH --mem={resource['memory']}",
        f"#SBATCH --time={resource['walltime']}",
        f"#SBATCH --output={_quote(cluster_root / 'results_research_program' / 'tenpy_logs_v2' / (job_id + '.%j.out'))}",
        f"#SBATCH --error={_quote(cluster_root / 'results_research_program' / 'tenpy_logs_v2' / (job_id + '.%j.err'))}",
    ]
    if partition:
        lines.append(f"#SBATCH --partition={partition}")
    if account:
        lines.append(f"#SBATCH --account={account}")
    lines.extend(
        [
            "",
            "set -euo pipefail",
            f"cd {_quote(source_root)}",
            f"mkdir -p {_quote(cluster_root / 'results_research_program' / 'tenpy_logs_v2')}",
            "RUN_ARGS=(",
            f"  {_quote(source_root / 'scripts' / 'run_tenpy_production_job.py')}",
            f"  --manifest {_quote(source_root / 'results_research_program' / 'production_manifest_v2.json')}",
            f"  --job-id {_quote(job_id)}",
            f"  --output {_quote(output)}",
            ")",
        ]
    )
    gamma = job.get("fcs_gamma")
    if gamma is not None:
        serialized = ",".join(f"{float(value):g}" for value in gamma)
        lines.append(f"RUN_ARGS+=(--fcs-gamma {_quote(serialized)})")
    checkpoint = Path(str(output) + ".checkpoint.h5")
    lines.extend(
        [
            f"if [[ -f {_quote(checkpoint)} ]]; then",
            "  RUN_ARGS+=(--resume)",
            "fi",
            f"{_quote(python)} \"${{RUN_ARGS[@]}}\"",
            "",
        ]
    )
    return "\n".join(lines)


def build_bundle(
    manifest: Mapping[str, Any],
    *,
    outdir: str | Path,
    cluster_root: str | Path,
    source_root: str | Path | None = None,
    python: str,
    gates: Mapping[str, Any],
    reuse_attestations: Mapping[str, Any] | None = None,
    partition: str | None = None,
    account: str | None = None,
) -> BundleResult:
    """Materialize scripts for ready execute rows and never call Slurm."""

    output = Path(outdir)
    code_root = (
        Path(cluster_root)
        if source_root is None
        else Path(source_root)
    )
    output.mkdir(parents=True, exist_ok=True)
    reuse_attestations = reuse_attestations or {}
    convergence_status = _status(gates.get("convergence"))
    source_status = _status(gates.get("source_preflight"))
    j2_status = _status(gates.get("j2"))
    unblinding_status = _status(gates.get("unblinding"))
    records: list[dict[str, Any]] = []
    scripts: list[Path] = []
    reuse_count = 0
    for job in manifest["jobs"]:
        job_id = str(job["job_id"])
        mode = str(job.get("execution_mode"))
        reuse_status = None
        if mode == "reuse":
            reuse_count += 1
            candidate = reuse_attestations.get(job_id)
            reuse_status = _status(candidate)
        reasons = job_block_reasons_v2(
            job,
            convergence_status=convergence_status,
            source_preflight_status=source_status,
            j2_status=j2_status,
            unblinding_status=unblinding_status,
            reuse_status=reuse_status,
        )
        ready = mode == "execute" and not reasons
        script_path: Path | None = None
        if ready:
            script_path = output / f"{job_id}.sbatch"
            script_path.write_text(
                _slurm_text(
                    job,
                    cluster_root=Path(cluster_root),
                    source_root=code_root,
                    python=python,
                    partition=partition,
                    account=account,
                )
            )
            script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR)
            scripts.append(script_path)
        records.append(
            {
                "job_id": job_id,
                "condition_id": job["condition_id"],
                "stage": job["stage"],
                "execution_mode": mode,
                "resource_request": (
                    production_resource_spec(job)
                    if mode == "execute"
                    else None
                ),
                "status": (
                    "ready"
                    if ready
                    else "reuse_logical"
                    if mode == "reuse" and not reasons
                    else "blocked"
                ),
                "block_reasons": reasons,
                "script": str(script_path) if script_path else None,
            }
        )

    submit_path = output / "submit_ready.sh"
    submit_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        (
            'echo "Direct batch submission is disabled; use the '
            'stage-specific hpc/scnet/submit_production_a.py or '
            'hpc/scnet/submit_production_b.py controller." >&2'
        ),
        "exit 2",
    ]
    submit_path.write_text("\n".join(submit_lines) + "\n")
    submit_path.chmod(submit_path.stat().st_mode | stat.S_IXUSR)

    ready_count = len(scripts)
    blocked_count = sum(record["status"] == "blocked" for record in records)
    matrix = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "manifest_summary": dict(manifest["summary"]),
        "gate_status": {
            "convergence": convergence_status,
            "source_preflight": source_status,
            "j2": j2_status,
            "unblinding": unblinding_status,
        },
        "summary": {
            "logical_rows": len(records),
            "ready_execute_rows": ready_count,
            "reuse_rows": reuse_count,
            "blocked_rows": blocked_count,
            "submission_performed": False,
        },
        "records": records,
    }
    matrix_path = output / "execution_matrix.json"
    matrix_path.write_text(json.dumps(matrix, indent=2) + "\n")
    return BundleResult(
        ready_count=ready_count,
        reuse_count=reuse_count,
        blocked_count=blocked_count,
        script_paths=tuple(scripts),
        matrix_path=matrix_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "results_research_program" / "production_manifest_v2.json",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=ROOT / "results_research_program" / "tenpy_jobs_production_v2",
    )
    parser.add_argument(
        "--cluster-root",
        type=Path,
        default=Path("/work/share/giggleliu/cfys01/kharkov_burgers_20260729"),
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=ROOT,
        help="Directory containing scripts/, src/, and the frozen manifest.",
    )
    parser.add_argument("--python", default="python3")
    parser.add_argument(
        "--convergence-audit",
        type=Path,
        default=ROOT / "results_research_program" / "convergence" / "audit.json",
    )
    parser.add_argument(
        "--source-preflight",
        type=Path,
        default=DEFAULT_SOURCE_PREFLIGHT,
    )
    parser.add_argument(
        "--j2-validation",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "hpc"
        / "j2_validation_20260730.json",
    )
    parser.add_argument("--unblinding-record", type=Path)
    parser.add_argument("--reuse-attestations", type=Path)
    parser.add_argument("--partition")
    parser.add_argument("--account")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    reuse = (
        json.loads(args.reuse_attestations.read_text())
        if args.reuse_attestations and args.reuse_attestations.is_file()
        else {}
    )
    result = build_bundle(
        manifest,
        outdir=args.outdir,
        cluster_root=args.cluster_root,
        source_root=args.source_root,
        python=args.python,
        gates={
            "convergence": args.convergence_audit,
            "source_preflight": args.source_preflight,
            "j2": args.j2_validation,
            "unblinding": args.unblinding_record,
        },
        reuse_attestations=reuse,
        partition=args.partition,
        account=args.account,
    )
    print(
        json.dumps(
            {
                "ready_execute_rows": result.ready_count,
                "reuse_rows": result.reuse_count,
                "blocked_rows": result.blocked_count,
                "submission_performed": result.submission_performed,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
