from __future__ import annotations

import argparse
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qcontrol.evidence import validate_deployment


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--deployment-metadata", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--expected-archive-sha256", required=True)
    parser.add_argument("--expected-evidence-revision", required=True)
    parser.add_argument("--expected-sif-sha256", required=True)
    parser.add_argument("--expected-deployment-metadata-sha256", required=True)
    parser.add_argument("--expected-pyproject-sha256", required=True)
    parser.add_argument("--expected-uv-lock-sha256", required=True)
    parser.add_argument("--expected-cluster-profile", required=True)
    args = parser.parse_args()
    validate_deployment(
        args.root,
        archive_path=args.archive,
        deployment_metadata_path=args.deployment_metadata,
        expected_revision=args.expected_revision,
        expected_archive_sha256=args.expected_archive_sha256,
        expected_evidence_revision=args.expected_evidence_revision,
        expected_sif_sha256=args.expected_sif_sha256,
        expected_deployment_metadata_sha256=(
            args.expected_deployment_metadata_sha256
        ),
        expected_pyproject_sha256=args.expected_pyproject_sha256,
        expected_uv_lock_sha256=args.expected_uv_lock_sha256,
        expected_cluster_profile=args.expected_cluster_profile,
    )
    print('{"deployment_valid":true}', flush=True)


if __name__ == "__main__":
    main()
