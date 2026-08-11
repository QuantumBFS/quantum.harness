#!/usr/bin/env python3
"""Download and verify the public Zenodo input for Issue #158."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import tempfile
from urllib.request import urlopen


URL = (
    "https://zenodo.org/api/records/17206870/files/data.dat/content"
)
EXPECTED_SIZE = 17_083_117
EXPECTED_SHA256 = (
    "b63ab4f8a73ed0ab7eb3711788f3e50b9f054706f29b5e65792a78cff4fbd901"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(path: Path) -> None:
    size = path.stat().st_size
    digest = sha256(path)
    if size != EXPECTED_SIZE:
        raise RuntimeError(
            f"size mismatch for {path}: {size} != {EXPECTED_SIZE}"
        )
    if digest != EXPECTED_SHA256:
        raise RuntimeError(
            f"SHA-256 mismatch for {path}: {digest} != {EXPECTED_SHA256}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/data.dat"),
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    if args.output.exists():
        validate(args.output)
        print(f"verified existing {args.output}", flush=True)
        return

    with tempfile.NamedTemporaryFile(
        prefix="issue158-data-",
        delete=False,
        dir=args.output.parent,
    ) as temporary:
        temporary_path = Path(temporary.name)
        with urlopen(URL, timeout=120) as response:
            while chunk := response.read(1024 * 1024):
                temporary.write(chunk)
                print(
                    f"downloaded {temporary.tell()} / {EXPECTED_SIZE} bytes",
                    flush=True,
                )

    try:
        validate(temporary_path)
        temporary_path.replace(args.output)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    print(f"verified {args.output}", flush=True)


if __name__ == "__main__":
    main()
