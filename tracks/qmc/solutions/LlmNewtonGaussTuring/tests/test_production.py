#!/usr/bin/env python3
"""End-to-end checks for the resumable Challenge 148 cell contract."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import tempfile
from argparse import Namespace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("run_stage4", ROOT / "tools" / "run_stage4.py")
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RUNNER)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sampler", type=Path, required=True)
    args = parser.parse_args()
    sampler = args.sampler.resolve()
    require(RUNNER.build_info(sampler)["build_type"] == "Release", "sampler is not Release")

    source = RUNNER.source_provenance()
    with tempfile.TemporaryDirectory() as directory:
        run_dir = Path(directory) / "c148-contract-test"
        params = [
            {"L": 4, "h": 3.04, "initial_state": start, "replica": 0, "lattice": "square"}
            for start in ("hot", "cold")
        ]
        for item in params:
            item["seed"] = RUNNER.stable_seed("c148-contract-test", item)
        settings = {
            "J": 1.0,
            "c_tau": 1.0,
            "n_thermal": 20,
            "n_bins": 4,
            "sweeps_per_bin": 2,
            "sampler": str(sampler),
            "raw_schema": RUNNER.RAW_SCHEMA,
            "update_algorithm": "sandvik-tfim-cluster-v1",
            "primary_estimator": "Q=<mbar^2>^2/<mbar^4>",
            "secondary_estimator": "xi/L from equal-time S(0)/S(q_min)",
            "required_initial_states": ["hot", "cold"],
            "allow_dirty_source": True,
        }
        spec = {
            "run_id": "c148-contract-test",
            "run_dir": str(run_dir),
            "settings": settings,
            "provenance": {
                **source,
                "protocol_id": RUNNER.PROTOCOL_ID,
                "challenge_issue": "https://github.com/QuantumBFS/quantum.harness/issues/148",
                "lattice": "square",
            },
            "cells": [
                {"cell_id": f"cell-{index:04d}", "params": item}
                for index, item in enumerate(params, start=1)
            ],
        }
        run_dir.mkdir(parents=True)
        spec_path = run_dir / "run_spec.json"
        RUNNER.atomic_json(spec_path, spec)

        RUNNER.cmd_run_local(
            Namespace(
                run_spec=spec_path, workers=2, retry_failed=False, collect=True
            )
        )

        # The seeded sampler is part of the resumable-cell contract.  Run a
        # small cell twice and compare the complete raw files, not only a
        # derived observable, so estimator optimizations cannot alter the
        # trajectory or metadata silently.
        deterministic_a = run_dir / "deterministic-a.csv"
        deterministic_b = run_dir / "deterministic-b.csv"
        deterministic_command = [
            str(sampler), "square", "4", "3.04", "1", "148148", "hot",
            "20", "4", "2",
        ]
        subprocess.run(
            [*deterministic_command, str(deterministic_a)],
            cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        subprocess.run(
            [*deterministic_command, str(deterministic_b)],
            cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        require(
            deterministic_a.read_bytes() == deterministic_b.read_bytes(),
            "seeded sampler output is not deterministic",
        )

        RUNNER.cmd_run_cell(
            Namespace(run_spec=spec_path, cell="cell-0001", retry_failed=False)
        )

        merged = run_dir / "c148-contract-test_bins.csv"
        require(merged.is_file(), "collector did not create merged raw bins")
        require(len(merged.read_text(encoding="utf-8").splitlines()) == 9, "merged row count is wrong")
        first_manifest = json.loads(
            (run_dir / "cells" / "cell-0001" / "manifest.json").read_text(encoding="utf-8")
        )
        require(first_manifest["status"] == "success", "cell manifest is not successful")
        require(first_manifest["diagnostics"]["sign_avg"] == 1.0, "sign gate failed")
        require(first_manifest["physics"]["c_tau"] == 1.0, "aspect-ratio metadata missing")

        raw = run_dir / "cells" / "cell-0001" / "bins.csv"
        raw.write_text(raw.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
        try:
            RUNNER.validate_manifest(spec, spec["cells"][0], run_dir)
        except ValueError:
            pass
        else:
            raise AssertionError("tampered raw artifact was accepted")

    print("All Challenge 148 production-contract tests passed.")


if __name__ == "__main__":
    main()
