#!/usr/bin/env python3
"""Generate and commitment-check issue #71 mystery predictions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from circuit import Circuit, prediction_bytes


EXPECTED_SHA256 = {
    "A": "51e3f026def41778ecd0d7dcaee9f970b9937488e6716891932b73824c16d4c7",
    "B": "e2c9d0e23ee36bfc0f12d7f39fdfe2ca5a8abe8eb194fec56500733694b75c28",
    "C": "c7b37413844bf0b10ebad0010046469f500354a22cc2ba95cbe42709f8e8337d",
    "D": "b445a717483303fa3c5d8a1f7abe81888b267b7c472121c9c464fa9766808580",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--datasets", type=Path, required=True)
    parser.add_argument("--netlists", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    records: dict[str, dict[str, object]] = {}
    for instance, expected in EXPECTED_SHA256.items():
        name = f"mystery-{instance}"
        netlist = args.netlists / f"{name}.txt"
        test_inputs = args.datasets / name / "test_inputs.csv"
        destination = args.output / name / "test_outputs.csv"
        temporary = destination.with_suffix(".csv.tmp")

        circuit = Circuit.parse(netlist)
        payload = prediction_bytes(circuit, test_inputs)
        actual = hashlib.sha256(payload).hexdigest()
        if actual != expected:
            raise RuntimeError(
                f"{name}: prediction commitment mismatch: {actual} != {expected}"
            )

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_bytes(payload)
        temporary.replace(destination)
        records[instance] = {
            "gates": len(circuit.gates),
            "netlist": str(netlist),
            "netlist_sha256": sha256_file(netlist),
            "prediction": str(destination),
            "prediction_sha256": actual,
            "official_commitment_sha256": expected,
            "commitment_matches": True,
        }

    manifest = {
        "challenge": "QuantumBFS/quantum.harness issue 71",
        "all_official_commitments_match": True,
        "instances": records,
    }
    manifest_path = args.output / "prediction_manifest.json"
    temporary_manifest = manifest_path.with_suffix(".json.tmp")
    temporary_manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary_manifest.replace(manifest_path)
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
