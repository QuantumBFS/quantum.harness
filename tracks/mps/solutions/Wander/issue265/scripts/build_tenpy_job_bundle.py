#!/usr/bin/env python3
"""Materialize reproducible Slurm launch files for registered TeNPy jobs.

This command never submits jobs. It records unvalidated Hamiltonian backends
and blinded stages explicitly so a generated bundle cannot silently broaden
the confirmed scope.
"""

from __future__ import annotations

import argparse
import json
import shlex
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_J2_VALIDATION = (
    ROOT / "results_research_program" / "hpc" / "j2_validation_20260730.json"
)


RESOURCE_LEVELS = {
    "coarse": {
        "non_fcs": {"cpus": 4, "memory": "12G"},
        "fcs": {"cpus": 8, "memory": "24G"},
        "walltime": "7-00:00:00",
    },
    "medium": {
        "non_fcs": {"cpus": 8, "memory": "30G"},
        "fcs": {"cpus": 16, "memory": "60G"},
        "walltime": "7-00:00:00",
    },
    "fine": {
        "non_fcs": {"cpus": 16, "memory": "60G"},
        "fcs": {"cpus": 32, "memory": "120G"},
        "walltime": "7-00:00:00",
    },
    "selected_after_convergence": {
        "non_fcs": {"cpus": 16, "memory": "60G"},
        "fcs": {"cpus": 32, "memory": "120G"},
        "walltime": "7-00:00:00",
    },
}


def _shell(value: str | Path) -> str:
    return shlex.quote(str(value))


def _resource_spec(job: dict[str, Any]) -> dict[str, Any]:
    level = str(job["resolution_level"])
    fcs = "fcs_logZ" in job.get("observables", [])
    registered = RESOURCE_LEVELS[level]
    base = {
        **dict(registered["fcs" if fcs else "non_fcs"]),
        "walltime": registered["walltime"],
    }
    base.update(
        {
            "fcs_counting_branches": 3 if fcs else 0,
            "resource_pilot_job_id": "23009308",
            "warning": (
                "FCS evolves three positive counting branches concurrently "
                "with the physical branch; measure peak memory in a reduced "
                "pilot before production."
                if fcs
                else None
            ),
        }
    )
    return base


def _j2_validation_passed(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return payload.get("status") == "pass"


def job_block_reasons(
    job: dict[str, Any],
    *,
    j2_validation: Path = DEFAULT_J2_VALIDATION,
) -> list[str]:
    """Return all independent reasons a registered job is not launchable."""

    reasons: list[str] = []
    if str(job["stage"]) == "production_b":
        reasons.append("blinded_until_registered_unblinding")
    condition = dict(job["condition"])
    if (
        abs(float(condition.get("j2", 0.0))) > 1e-15
        and not _j2_validation_passed(j2_validation)
    ):
        reasons.append("J2_backend_validation_missing_or_failed")
    return reasons


def _slurm_text(
    job: dict[str, Any],
    *,
    manifest: Path,
    python: str,
    cluster_root: Path,
    partition: str | None,
    account: str | None,
    resource: dict[str, Any],
) -> str:
    output_path = (
        cluster_root
        / "data"
        / "research"
        / "raw"
        / str(job["stage"])
        / (str(job["job_id"]) + ".npz")
    )
    directives = [
        "#!/usr/bin/env bash",
        f"#SBATCH --job-name=kh_{job['job_id'][:80]}",
        f"#SBATCH --cpus-per-task={resource['cpus']}",
        f"#SBATCH --mem={resource['memory']}",
        f"#SBATCH --time={resource['walltime']}",
        f"#SBATCH --output={_shell(cluster_root / 'results_research_program' / 'tenpy_logs' / (job['job_id'] + '.%j.out'))}",
        f"#SBATCH --error={_shell(cluster_root / 'results_research_program' / 'tenpy_logs' / (job['job_id'] + '.%j.err'))}",
    ]
    if partition:
        directives.append(f"#SBATCH --partition={partition}")
    if account:
        directives.append(f"#SBATCH --account={account}")
    directives.extend(
        [
            "",
            "set -euo pipefail",
            f"cd {_shell(cluster_root)}",
            f"mkdir -p {_shell(cluster_root / 'results_research_program' / 'tenpy_logs')}",
            f"OUTPUT_PATH={_shell(output_path)}",
            "RUN_ARGS=(",
            "  scripts/run_tenpy_research_job.py",
            f"  --manifest {_shell(cluster_root / 'results_research_program' / 'manifest.json')}",
            f"  --job-id {_shell(job['job_id'])}",
            '  --output "$OUTPUT_PATH"',
            ")",
            'if [[ -f "${OUTPUT_PATH}.checkpoint.h5" ]]; then',
            "  RUN_ARGS+=(--resume)",
            "fi",
            f"{_shell(python)} \"${{RUN_ARGS[@]}}\"",
            "",
        ]
    )
    return "\n".join(directives)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "results_research_program" / "manifest.json",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=ROOT / "results_research_program" / "tenpy_jobs",
    )
    parser.add_argument(
        "--stages",
        default="convergence",
        help="Comma-separated manifest stages; defaults to convergence only.",
    )
    parser.add_argument(
        "--python",
        default="python3",
        help="Python executable available on compute nodes.",
    )
    parser.add_argument(
        "--cluster-root",
        type=Path,
        default=ROOT,
        help="Absolute project root as mounted on compute nodes.",
    )
    parser.add_argument("--partition")
    parser.add_argument("--account")
    parser.add_argument(
        "--j2-validation",
        type=Path,
        default=DEFAULT_J2_VALIDATION,
        help=(
            "Validation evidence whose status must be pass before a J2 job "
            "is marked ready."
        ),
    )
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    selected_stages = {
        value.strip() for value in args.stages.split(",") if value.strip()
    }
    known_stages = {"convergence", "production_a", "production_b"}
    if not selected_stages or not selected_stages <= known_stages:
        raise SystemExit(
            "stages must be drawn from convergence,production_a,production_b"
        )

    args.outdir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    ready_scripts: list[Path] = []
    for job in manifest["jobs"]:
        if str(job["stage"]) not in selected_stages:
            continue
        reasons = job_block_reasons(
            job,
            j2_validation=args.j2_validation,
        )
        resource = _resource_spec(job)
        record: dict[str, Any] = {
            "job_id": job["job_id"],
            "stage": job["stage"],
            "condition_id": job["condition_id"],
            "resolution_level": job["resolution_level"],
            "observables": job.get("observables", []),
            "output_path": job["output_path"],
            "resource_request": resource,
            "status": "blocked" if reasons else "ready",
            "block_reasons": reasons,
        }
        if not reasons:
            script_path = args.outdir / f"{job['job_id']}.sbatch"
            script_path.write_text(
                _slurm_text(
                    job,
                    manifest=args.manifest,
                    python=args.python,
                    cluster_root=args.cluster_root,
                    partition=args.partition,
                    account=args.account,
                    resource=resource,
                )
            )
            script_path.chmod(
                script_path.stat().st_mode
                | stat.S_IXUSR
                | stat.S_IXGRP
            )
            record["script"] = str(script_path.resolve())
            ready_scripts.append(script_path)
        records.append(record)

    submit_path = args.outdir / "submit_ready.sh"
    submit_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# This file is generated but never executed by the builder.",
        *[f"sbatch {_shell(path.resolve())}" for path in ready_scripts],
        "",
    ]
    submit_path.write_text("\n".join(submit_lines))
    submit_path.chmod(
        submit_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP
    )
    summary = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(args.manifest.resolve()),
        "cluster_root": str(args.cluster_root),
        "j2_validation": str(args.j2_validation.resolve()),
        "j2_validation_passed": _j2_validation_passed(
            args.j2_validation
        ),
        "selected_stages": sorted(selected_stages),
        "ready_count": sum(record["status"] == "ready" for record in records),
        "blocked_count": sum(
            record["status"] == "blocked" for record in records
        ),
        "submission_performed": False,
        "records": records,
    }
    (args.outdir / "execution_matrix.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    )
    report = [
        "# TeNPy execution bundle",
        "",
        f"- selected stages: `{', '.join(sorted(selected_stages))}`",
        f"- compute-node project root: `{args.cluster_root}`",
        f"- ready jobs: `{summary['ready_count']}`",
        f"- blocked jobs: `{summary['blocked_count']}`",
        "- submitted: `false`",
        "",
        (
            "The resource requests are conservative starting points, not "
            "measured guarantees. Run one reduced wall-time/memory pilot "
            "before submitting the full ladder. FCS jobs carry multiple "
            "counting-field MPS branches and are called out in "
            "`execution_matrix.json`."
        ),
        "",
        (
            "The manifest is used locally to build this bundle. Each launch "
            "file overrides the dataset path with the compute-node project "
            "root, so the developer-machine absolute paths embedded in the "
            "manifest are not reused on the cluster."
        ),
        "",
        (
            "After configuring the cluster partition/account and validating "
            "one pilot, submit explicitly with:"
        ),
        "",
        "```bash",
        str(submit_path.resolve()),
        "```",
        "",
        "The builder does not execute that file.",
        "",
    ]
    (args.outdir / "README.md").write_text("\n".join(report))
    print(
        json.dumps(
            {
                "outdir": str(args.outdir.resolve()),
                "ready_count": summary["ready_count"],
                "blocked_count": summary["blocked_count"],
                "submission_performed": False,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
