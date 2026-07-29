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
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--expected-archive-sha256", required=True)
    parser.add_argument("--expected-evidence-revision", required=True)
    args = parser.parse_args()
    validate_deployment(
        args.root,
        archive_path=args.archive,
        expected_revision=args.expected_revision,
        expected_archive_sha256=args.expected_archive_sha256,
        expected_evidence_revision=args.expected_evidence_revision,
    )
    print('{"deployment_valid":true}', flush=True)


if __name__ == "__main__":
    main()
