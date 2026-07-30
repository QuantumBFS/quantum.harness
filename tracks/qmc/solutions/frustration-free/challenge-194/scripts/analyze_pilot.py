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
    COMBINED_ANALYSIS_SCHEMA,
    EXTENSION_ANALYSIS_SCHEMA,
    P1_PROTOCOL_SCHEMA,
    aggregate_p0,
    aggregate_p0_extension,
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
    combine_p0_evidence,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish and verify Challenge 194 Pilot analysis artifacts."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    analyze = commands.add_parser("analyze")
    analyze.add_argument("--run-spec", type=Path, required=True)
    analyze.add_argument("--output", type=Path, required=True)

    analyze_extension = commands.add_parser("analyze-extension")
    analyze_extension.add_argument("--run-spec", type=Path, required=True)
    analyze_extension.add_argument("--protocol", type=Path, required=True)
    analyze_extension.add_argument("--output", type=Path, required=True)

    combine = commands.add_parser("combine")
    combine.add_argument("--p0-analysis", type=Path, required=True)
    combine.add_argument("--extension-analysis", type=Path, required=True)
    combine.add_argument("--p0-evidence-root", type=Path, required=True)
    combine.add_argument("--extension-run-spec", type=Path, required=True)
    combine.add_argument("--extension-protocol", type=Path, required=True)
    combine.add_argument("--output", type=Path, required=True)

    select = commands.add_parser("select")
    select.add_argument("--analysis", type=Path, required=True)
    select.add_argument("--p0-analysis", type=Path)
    select.add_argument("--extension-analysis", type=Path)
    select.add_argument("--p0-evidence-root", type=Path)
    select.add_argument("--extension-run-spec", type=Path)
    select.add_argument("--extension-protocol", type=Path)
    select.add_argument("--output", type=Path, required=True)

    build = commands.add_parser("build-p1")
    build.add_argument("--analysis", type=Path, required=True)
    build.add_argument("--p0-analysis", type=Path)
    build.add_argument("--extension-analysis", type=Path)
    build.add_argument("--p0-evidence-root", type=Path)
    build.add_argument("--extension-run-spec", type=Path)
    build.add_argument("--extension-protocol", type=Path)
    build.add_argument("--output", type=Path, required=True)

    extension = commands.add_parser("build-p0-extension")
    extension.add_argument("--analysis", type=Path, required=True)
    extension.add_argument("--p0-evidence-root", type=Path, required=True)
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


def _combined_command_sources(
    arguments: argparse.Namespace,
    source: Mapping[str, object],
) -> tuple[
    Mapping[str, object] | None,
    Mapping[str, object] | None,
    Path | None,
    Path | None,
    Mapping[str, object] | None,
]:
    p0_path = arguments.p0_analysis
    extension_path = arguments.extension_analysis
    p0_evidence_root = arguments.p0_evidence_root
    extension_run_spec = arguments.extension_run_spec
    extension_protocol_path = arguments.extension_protocol
    if source.get("schema_version") == COMBINED_ANALYSIS_SCHEMA:
        if (
            p0_path is None
            or extension_path is None
            or p0_evidence_root is None
            or extension_run_spec is None
            or extension_protocol_path is None
        ):
            raise RuntimeError(
                "combined-v2 command requires explicit --p0-analysis, "
                "--extension-analysis, --p0-evidence-root, "
                "--extension-run-spec, and --extension-protocol"
            )
        return (
            _mapping_document(p0_path.resolve(), "P0 analysis document"),
            _mapping_document(
                extension_path.resolve(), "P0 extension analysis document"
            ),
            p0_evidence_root.resolve(),
            extension_run_spec.resolve(),
            _mapping_document(
                extension_protocol_path.resolve(),
                "immutable P0 extension protocol document",
            ),
        )
    if source.get("schema_version") == ANALYSIS_SCHEMA:
        if any(
            value is not None
            for value in (
                p0_path,
                extension_path,
                p0_evidence_root,
                extension_run_spec,
                extension_protocol_path,
            )
        ):
            raise RuntimeError(
                f"v1 {arguments.command} does not accept combined trusted inputs"
            )
        return None, None, None, None, None
    if any(
        value is not None
        for value in (
            p0_path,
            extension_path,
            p0_evidence_root,
            extension_run_spec,
            extension_protocol_path,
        )
    ):
        raise RuntimeError("analysis schema and source arguments are incompatible")
    return None, None, None, None, None


def _publication_schema(document: Mapping[str, object]) -> str:
    schema = document.get("schema_version")
    if not isinstance(schema, str):
        raise RuntimeError("published document schema is malformed")
    return schema


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
        elif arguments.command == "analyze-extension":
            protocol = _mapping_document(
                arguments.protocol.resolve(), "P0 extension protocol document"
            )
            document = aggregate_p0_extension(
                arguments.run_spec.resolve(),
                protocol,
            )
            publication = _publish_or_verify(
                arguments.output.resolve(),
                document,
                EXTENSION_ANALYSIS_SCHEMA,
            )
            result = {
                "status": "analyzed",
                "publication": publication,
                "output": str(arguments.output.resolve()),
                "analysis_document_sha256": document["analysis_document_sha256"],
            }
        elif arguments.command == "combine":
            p0_source = _mapping_document(
                arguments.p0_analysis.resolve(), "P0 analysis document"
            )
            extension_source = _mapping_document(
                arguments.extension_analysis.resolve(),
                "P0 extension analysis document",
            )
            extension_protocol = _mapping_document(
                arguments.extension_protocol.resolve(),
                "immutable P0 extension protocol document",
            )
            document = combine_p0_evidence(
                p0_source,
                extension_source,
                p0_evidence_root=arguments.p0_evidence_root.resolve(),
                extension_run_spec=arguments.extension_run_spec.resolve(),
                extension_protocol=extension_protocol,
            )
            publication = _publish_or_verify(
                arguments.output.resolve(),
                document,
                COMBINED_ANALYSIS_SCHEMA,
            )
            result = {
                "status": "combined",
                "publication": publication,
                "output": str(arguments.output.resolve()),
                "analysis_document_sha256": document["analysis_document_sha256"],
            }
        elif arguments.command == "select":
            source = _mapping_document(
                arguments.analysis.resolve(), "P0 analysis document"
            )
            (
                p0_source,
                extension_source,
                p0_evidence_root,
                extension_run_spec,
                extension_protocol,
            ) = _combined_command_sources(
                arguments,
                source,
            )
            if p0_source is None:
                document = select_p1_brackets(source)
            else:
                document = select_p1_brackets(
                    source,
                    p0_analysis=p0_source,
                    extension_analysis=extension_source,
                    p0_evidence_root=p0_evidence_root,
                    extension_run_spec=extension_run_spec,
                    extension_protocol=extension_protocol,
                )
            publication = _publish_or_verify(
                arguments.output.resolve(),
                document,
                _publication_schema(document),
            )
            result = {
                "status": "selected",
                "publication": publication,
                "output": str(arguments.output.resolve()),
                "bracket_document_sha256": document["bracket_document_sha256"],
            }
        elif arguments.command == "build-p0-extension":
            source = _mapping_document(
                arguments.analysis.resolve(), "P0 analysis document"
            )
            document = build_p0_extension_protocol(
                source,
                arguments.p0_evidence_root,
            )
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
            (
                p0_source,
                extension_source,
                p0_evidence_root,
                extension_run_spec,
                extension_protocol,
            ) = _combined_command_sources(
                arguments,
                source,
            )
            if p0_source is None:
                brackets = select_p1_brackets(source)
                document = build_p1_protocol(source, brackets)
            else:
                brackets = select_p1_brackets(
                    source,
                    p0_analysis=p0_source,
                    extension_analysis=extension_source,
                    p0_evidence_root=p0_evidence_root,
                    extension_run_spec=extension_run_spec,
                    extension_protocol=extension_protocol,
                )
                document = build_p1_protocol(
                    source,
                    brackets,
                    p0_analysis=p0_source,
                    extension_analysis=extension_source,
                    p0_evidence_root=p0_evidence_root,
                    extension_run_spec=extension_run_spec,
                    extension_protocol=extension_protocol,
                )
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
