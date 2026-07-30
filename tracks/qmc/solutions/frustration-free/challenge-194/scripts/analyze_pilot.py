#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path

from long_range_percolation.artifacts import (
    _publish_json_once,
    _read_canonical_json,
    _verify_installed_bytes,
)
from long_range_percolation.pilot_analysis import (
    ANALYSIS_SCHEMA,
    P1_PROTOCOL_SCHEMA,
    aggregate_p0,
    build_p1_protocol,
    select_p1_brackets,
    validate_p1_protocol,
)
from long_range_percolation.pilot_analysis import (
    _canonical_bytes as _analysis_canonical_bytes,
)
from long_range_percolation.pilot_extension import (
    EXTENSION_PROTOCOL_SCHEMA,
    build_p0_extension_protocol,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish and verify Challenge 194 Pilot analysis artifacts."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    analyze = commands.add_parser("analyze")
    analyze.add_argument("--run-spec", type=Path, required=True)
    analyze.add_argument("--output", type=Path, required=True)

    build = commands.add_parser("build-p1")
    build.add_argument("--analysis", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)

    extension = commands.add_parser("build-p0-extension")
    extension.add_argument("--analysis", type=Path, required=True)
    extension.add_argument("--output", type=Path, required=True)

    verify = commands.add_parser("verify")
    verify.add_argument("--analysis", type=Path, required=True)
    verify.add_argument("--p1-protocol", type=Path, required=True)
    return parser


def _mapping_document(path: Path, description: str) -> Mapping[str, object]:
    document = _read_canonical_json(path, description)
    if not isinstance(document, Mapping):
        raise TypeError(f"{description} is not a JSON object")
    return document


def _publish_or_verify(
    path: Path,
    document: Mapping[str, object],
    schema: str,
) -> str:
    try:
        _publish_json_once(path, dict(document), schema)
    except FileExistsError:
        _verify_installed_bytes(
            path,
            _analysis_canonical_bytes(document),
            "published JSON artifact",
        )
        return "verified-existing"
    return "published"


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "analyze":
            document = aggregate_p0(arguments.run_spec.resolve())
            publication = _publish_or_verify(
                arguments.output.resolve(),
                document,
                ANALYSIS_SCHEMA,
            )
            result = {
                "status": "analyzed",
                "publication": publication,
                "output": str(arguments.output.resolve()),
                "analysis_document_sha256": document["analysis_document_sha256"],
            }
        elif arguments.command == "build-p0-extension":
            source = _mapping_document(
                arguments.analysis.resolve(), "P0 analysis document"
            )
            document = build_p0_extension_protocol(source)
            publication = _publish_or_verify(
                arguments.output.resolve(),
                document,
                EXTENSION_PROTOCOL_SCHEMA,
            )
            result = {
                "status": "ready",
                "publication": publication,
                "output": str(arguments.output.resolve()),
                "protocol_sha256": document["protocol_sha256"],
            }
        elif arguments.command == "build-p1":
            source = _mapping_document(
                arguments.analysis.resolve(), "P0 analysis document"
            )
            brackets = select_p1_brackets(source)
            document = build_p1_protocol(source, brackets)
            publication = _publish_or_verify(
                arguments.output.resolve(),
                document,
                P1_PROTOCOL_SCHEMA,
            )
            result = {
                "status": "ready",
                "publication": publication,
                "output": str(arguments.output.resolve()),
                "protocol_sha256": document["protocol_sha256"],
            }
        else:
            source = _mapping_document(
                arguments.analysis.resolve(), "P0 analysis document"
            )
            protocol = _mapping_document(
                arguments.p1_protocol.resolve(), "P1 protocol document"
            )
            validate_p1_protocol(source, protocol)
            result = {
                "status": "verified",
                "protocol_sha256": protocol["protocol_sha256"],
            }
    except Exception as error:  # noqa: BLE001 - CLI converts failures to status 1
        print(
            f"pilot analysis failure: {type(error).__name__}: {error}",
            file=sys.stderr,
            flush=True,
        )
        return 1
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
