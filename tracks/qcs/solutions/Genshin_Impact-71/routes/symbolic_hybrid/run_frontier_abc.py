#!/usr/bin/env python3
"""Audit native ABC transformations of the exact C154 and D109 frontiers."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Sequence

import routes
from run_experiments import convert_and_audit


INSTANCES = {
    "C": {
        "expected_sha256": (
            "f9396ee77462152c03fe061a4676944dc04e83787ef2a3915263bd2be8010bd9"
        ),
        "expected_gates": 154,
        "discovery_dir": "mystery-C",
    },
    "D": {
        "expected_sha256": (
            "cd3f317f4a0b88818e54869e40b4550fd67549f8eb4a5eb02c74db4ec6864dbd"
        ),
        "expected_gates": 109,
        "discovery_dir": "mystery-D",
    },
}

FLOWS = {
    "roundtrip": "",
    "strash_if": "strash; if -K 2;",
    "dc2_if": "strash; dc2; if -K 2;",
    "resyn2_explicit_if": (
        "strash; balance; rewrite; refactor; balance; rewrite; "
        "rewrite -z; balance; refactor -z; rewrite -z; balance; if -K 2;"
    ),
    "xag_put_if": "&get; &xag; &put; if -K 2;",
    "xag_put_strash_if": "&get; &xag; &put; strash; if -K 2;",
    "gia_dc2_put_if": "&get; &dc2; &put; if -K 2;",
}


def run(
    argv: Sequence[str],
    log: Path,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(argv),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(completed.stdout, encoding="utf-8", newline="\n")
    return completed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", required=True)
    parser.add_argument("--abc", required=True)
    parser.add_argument("--bridge", required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--circuit-c", required=True)
    parser.add_argument("--circuit-d", required=True)
    args = parser.parse_args()

    work = Path(args.work).resolve()
    abc = Path(args.abc).resolve()
    bridge = Path(args.bridge).resolve()
    circuits = {"C": Path(args.circuit_c), "D": Path(args.circuit_d)}
    if not os.access(abc, os.X_OK):
        raise ValueError(f"ABC executable missing: {abc}")

    report: dict[str, object] = {
        "schema": "occam71-frontier-native-abc-v1",
        "root_seed": routes.ROOT_SEED,
        "abc": str(abc),
        "abc_sha256": routes.sha256_file(abc),
        "flows": FLOWS,
        "instances": {},
    }
    for instance, config in INSTANCES.items():
        source = circuits[instance].resolve()
        actual_sha = routes.sha256_file(source)
        if actual_sha != config["expected_sha256"]:
            raise ValueError(f"{instance} source SHA mismatch: {actual_sha}")

        directory = work / instance
        directory.mkdir(parents=True, exist_ok=True)
        source_blif = directory / "source.blif"
        bridge_run = run(
            (
                args.python,
                "-u",
                str(bridge),
                "to-blif",
                str(source),
                str(source_blif),
                "--model",
                f"frontier_{instance}",
            ),
            directory / "bridge.log",
        )
        if bridge_run.returncode or not source_blif.is_file():
            raise RuntimeError(f"bridge failed for {instance}")

        discovery = (
            work.parent
            / "symbolic-hybrid-seed42"
            / str(config["discovery_dir"])
            / "discovery.json"
        )
        instance_report: dict[str, object] = {
            "source": str(source),
            "source_sha256": actual_sha,
            "source_gates": config["expected_gates"],
            "source_blif": str(source_blif),
            "routes": {},
        }
        for flow_name, flow in FLOWS.items():
            mapped = directory / f"{flow_name}.blif"
            command = (
                f"read_blif {source_blif}; {flow} "
                f"print_stats; write_blif {mapped}"
            )
            completed = run(
                (str(abc), "-c", command),
                directory / f"{flow_name}.abc.log",
            )
            route_report: dict[str, object] = {
                "command": command,
                "abc_returncode": completed.returncode,
                "abc_log": str(directory / f"{flow_name}.abc.log"),
            }
            if completed.returncode or not mapped.is_file():
                route_report["status"] = "ABC_FAILED_NOT_COMPARABLE"
            else:
                try:
                    audit_path = directory / f"{flow_name}.audit.json"
                    audit = convert_and_audit(
                        discovery,
                        mapped,
                        directory / f"{flow_name}.txt",
                        audit_path,
                        require_exact=True,
                    )
                except Exception as exc:  # preserve an honest incomparable result
                    route_report["status"] = "CONVERSION_OR_AUDIT_FAILED"
                    route_report["error"] = f"{type(exc).__name__}: {exc}"
                else:
                    route_report.update(
                        {
                            "status": "EXACT_COMPARABLE",
                            "mapped_blif": str(mapped),
                            "challenge": str(directory / f"{flow_name}.txt"),
                            "audit": str(audit_path),
                            "gates": audit["gates"],
                            "full_mismatches": audit[
                                "full_domain_vector_mismatches"
                            ],
                        }
                    )
            instance_report["routes"][flow_name] = route_report
            routes.atomic_json(directory / "summary.partial.json", instance_report)
        report["instances"][instance] = instance_report

    routes.atomic_json(work / "frontier-abc-summary.json", report)
    (work / "FRONTIER_ABC_COMPLETE").write_text(
        "success\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
