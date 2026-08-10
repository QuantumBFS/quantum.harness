from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


SIF_NAME = "uv-0.9.9-python3.12-bookworm-slim.sif"
SIF_SHA256 = "2405a769d520e6d0f680c0f1dff0d9f92083724f1ffd85ea0c26b5e36defa323"
CLUSTER_PROFILE = "lasg02-cpu-v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if re.fullmatch(r"[0-9a-f]{40}", args.revision) is None:
        raise ValueError("revision must be a full Git SHA")
    expected_name = f"challenge-113-{args.revision[:7]}.tar.gz"
    if args.archive.name != expected_name:
        raise ValueError("archive name does not bind the revision")
    payload = {
        "archive_name": args.archive.name,
        "archive_sha256": sha256(args.archive),
        "cluster_profile": CLUSTER_PROFILE,
        "critical_packages": {
            "jax": "0.11.0",
            "jaxlib": "0.11.0",
            "numpy": "2.5.1",
            "scipy": "1.18.0",
        },
        "evidence_index_sha256": sha256(args.root / "evidence/task10a/index.json"),
        "pyproject_sha256": sha256(args.root / "pyproject.toml"),
        "python_version": "3.12.12",
        "report_sha256": sha256(args.root / "REPORT.md"),
        "revision": args.revision,
        "schema_version": 1,
        "sif_name": SIF_NAME,
        "sif_sha256": SIF_SHA256,
        "uv_lock_sha256": sha256(args.root / "uv.lock"),
        "uv_version": "0.9.9",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, allow_nan=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    )


if __name__ == "__main__":
    main()
