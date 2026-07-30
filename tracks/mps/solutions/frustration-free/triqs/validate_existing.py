"""Freshly resolve and validate an immutable CT-HYB publication."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath

from artifacts import strict_json_load
from publication import validate_published_run


def resolve_current(output_root: Path) -> Path:
    pointer = strict_json_load(output_root / "current.json")
    if not isinstance(pointer, dict) or set(pointer) != {"relative_path", "summary_sha256"}:
        raise ValueError("current pointer is malformed")
    relative = PurePosixPath(pointer["relative_path"])
    if relative.is_absolute() or ".." in relative.parts or relative.parts[:1] != ("runs",):
        raise ValueError("current pointer path is unsafe")
    run = output_root.joinpath(*relative.parts)
    summary = validate_published_run(run)
    if summary["sha256"] != pointer["summary_sha256"]:
        raise ValueError("current pointer digest mismatch")
    return run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    arguments = parser.parse_args()
    print(resolve_current(arguments.output_root))


if __name__ == "__main__":
    main()
