#!/usr/bin/env python3
"""Atomically attest the two registered production-v2 reuse rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.production_reuse_gate import ALLOWED_REUSE, validate_reuse


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def _payload_and_hash(
    source: Mapping[str, Any] | str | Path,
) -> tuple[dict[str, Any], str]:
    if isinstance(source, Mapping):
        payload = dict(source)
        return payload, _canonical_sha256(payload)
    path = Path(source)
    payload = dict(json.loads(path.read_text()))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return payload, digest


def materialize_reuse_attestations(
    *,
    v2_manifest: Mapping[str, Any] | str | Path,
    base_manifest: Mapping[str, Any] | str | Path,
    data_root: str | Path,
    dataset_validation: Mapping[str, Any] | str | Path,
    convergence_audit: Mapping[str, Any] | str | Path,
) -> dict[str, Any]:
    """Validate both registered fine datasets without copying either one."""

    v2, v2_hash = _payload_and_hash(v2_manifest)
    base, base_hash = _payload_and_hash(base_manifest)
    validation, validation_hash = _payload_and_hash(dataset_validation)
    audit, audit_hash = _payload_and_hash(convergence_audit)
    targets = {
        str(job.get("job_id")): dict(job)
        for job in v2.get("jobs", [])
        if str(job.get("execution_mode")) == "reuse"
    }
    if set(targets) != set(ALLOWED_REUSE):
        raise ValueError(
            "production-v2 manifest must contain exactly the two registered "
            "reuse rows"
        )

    root = Path(data_root)
    accepted: dict[str, Any] = {}
    for target_id in sorted(ALLOWED_REUSE):
        target = targets[target_id]
        source_id = ALLOWED_REUSE[target_id]
        if str(target.get("reuse_from_job_id")) != source_id:
            raise ValueError(f"reuse source mismatch for {target_id}")
        dataset = root / f"{source_id}.npz"
        run_summary = dataset.with_suffix(".run.json")
        if not run_summary.is_file():
            raise FileNotFoundError(
                f"reuse run summary is missing: {run_summary}"
            )
        summary = dict(json.loads(run_summary.read_text()))
        attestation = validate_reuse(
            target,
            base_manifest=base,
            dataset_path=dataset,
            run_summary=summary,
            dataset_validation=validation,
            convergence_audit=audit,
        )
        accepted[target_id] = attestation.to_dict()

    return {
        "_provenance": {
            "schema_version": 1,
            "v2_manifest_sha256": v2_hash,
            "base_manifest_sha256": base_hash,
            "dataset_validation_sha256": validation_hash,
            "convergence_audit_sha256": audit_hash,
            "data_root": str(root.resolve()),
            "accepted_reuse_count": len(accepted),
        },
        **accepted,
    }


def write_reuse_attestations(
    *,
    output: str | Path,
    **kwargs: Any,
) -> dict[str, Any]:
    """Write only after all reuse rows pass."""

    payload = materialize_reuse_attestations(**kwargs)
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    )
    os.replace(temporary, destination)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--v2-manifest",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "production_manifest_v2.json",
    )
    parser.add_argument(
        "--base-manifest",
        type=Path,
        default=ROOT / "results_research_program" / "manifest.json",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=ROOT / "data" / "research" / "raw" / "convergence",
    )
    parser.add_argument(
        "--dataset-validation",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "dataset_validation.json",
    )
    parser.add_argument(
        "--convergence-audit",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "convergence"
        / "summary.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "production_v2_reuse_attestations.json",
    )
    args = parser.parse_args()
    payload = write_reuse_attestations(
        output=args.output,
        v2_manifest=args.v2_manifest,
        base_manifest=args.base_manifest,
        data_root=args.data_root,
        dataset_validation=args.dataset_validation,
        convergence_audit=args.convergence_audit,
    )
    print(
        json.dumps(
            {
                "status": "accepted",
                "reuse_count": payload["_provenance"][
                    "accepted_reuse_count"
                ],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
