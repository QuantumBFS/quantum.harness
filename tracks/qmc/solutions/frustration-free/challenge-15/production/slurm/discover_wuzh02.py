"""Render WUZH02 only from complete, explicitly labelled discovery facts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from challenge15.production_schema import canonical_json, envelope_for

REQUIRED = (
    "CONTROLLER",
    "PARTITION",
    "ACCOUNT",
    "QOS",
    "CPUS_PER_TASK",
    "MEMORY_MIB",
    "WALL_TIME",
    "PROJECT_ROOT",
    "RESULTS_ROOT",
    "PYTHON_VERSION",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--facts", required=True)
    parser.add_argument("--required-cores", required=True, type=int)
    parser.add_argument("--required-memory-mib", required=True, type=int)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    text = Path(args.facts).read_text(encoding="utf-8")
    facts = {
        key: match.group(1).strip()
        for key in REQUIRED
        if (match := re.search(rf"(?m)^{key}=(.+)$", text))
    }
    missing = sorted(set(REQUIRED) - set(facts))
    if missing:
        parser.error(
            "WUZH02 remains inactive; discovery facts are incomplete: "
            + ", ".join(missing)
        )
    if facts["CONTROLLER"] != "wuzh02":
        parser.error("facts are not for WUZH02")
    cores = int(facts["CPUS_PER_TASK"])
    memory = int(facts["MEMORY_MIB"])
    if cores < args.required_cores or memory < args.required_memory_mib:
        parser.error("WUZH02 audited capacity is insufficient")
    if not facts["PYTHON_VERSION"].startswith("Python 3.12"):
        parser.error("WUZH02 CPython 3.12 is unavailable")
    payload = {
        "controller": "wuzh02",
        "partition": facts["PARTITION"],
        "account": facts["ACCOUNT"],
        "qos": facts["QOS"],
        "nodes": 1,
        "ntasks": 1,
        "cpus_per_task": cores,
        "memory": f"{memory}M",
        "wall_time": facts["WALL_TIME"],
        "array_concurrency": 1,
        "approved_project_root": facts["PROJECT_ROOT"],
        "approved_results_root": facts["RESULTS_ROOT"],
        "scheduler_facts": {
            "facts_sha256": __import__("hashlib").sha256(text.encode()).hexdigest()
        },
    }
    destination = Path(args.output)
    with destination.open("xb") as stream:
        stream.write(
            canonical_json(envelope_for("challenge15.cluster-profile.v1", payload))
            + b"\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
