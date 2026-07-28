from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
import importlib
from pathlib import Path
from typing import Any

from scalable_v1.evaluator import evaluate_candidate, write_json_report
from scalable_v1.protocol import ProtocolConfig, load_protocol


CandidateFactory = Callable[[ProtocolConfig, int], tuple[Any, Any]]


def load_factory(specification: str) -> CandidateFactory:
    module_name, separator, factory_name = specification.partition(":")
    if (
        separator != ":"
        or not module_name
        or not factory_name
        or ":" in factory_name
    ):
        raise ValueError("candidate factory must use module:factory")
    try:
        module = importlib.import_module(module_name)
        factory = getattr(module, factory_name)
    except (ImportError, AttributeError) as error:
        raise ValueError("candidate factory must use module:factory") from error
    if not callable(factory):
        raise ValueError("candidate factory must use module:factory")
    return factory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the scalable-v1 evaluator")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--oracle", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--training-seed", required=True, type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    protocol = load_protocol()
    if arguments.training_seed not in protocol.training["seeds"]:
        parser.error("training seed must be one of the frozen protocol seeds")

    factory = load_factory(arguments.candidate)
    candidate, diagnostics = factory(protocol, arguments.training_seed)
    record = evaluate_candidate(
        candidate=candidate,
        diagnostics=diagnostics,
        protocol=protocol,
        manifest_path=arguments.manifest,
        project_root=arguments.project_root,
        oracle_path=arguments.oracle,
        training_seed=arguments.training_seed,
        progress=lambda message: print(message, flush=True),
    )
    write_json_report(record, arguments.output)
    return 0 if record["gates"]["scalable_v1_pass"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
