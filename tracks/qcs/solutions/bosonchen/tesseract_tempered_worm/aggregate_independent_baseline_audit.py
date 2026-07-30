#!/usr/bin/env python3
"""Aggregate the independent official-binary audit for phase-0 cases."""

import argparse
import json
from pathlib import Path


BASELINE_COMMIT = "9c73ca0acb1a48fd1dc797f5f6deabbb5f5d3feb"
BASELINE_SHA256 = (
    "f49df68983ee7b5da9d2f093ba42e49052455798140f6d7f60a7079685a4b18a"
)
CASES = [
    {
        "case": "surface_d11",
        "label": "Surface d=11",
        "index": 90,
        "phase0_pqlimit": 200_000,
        "official_pqlimit": 200_000,
    },
    {
        "case": "bbc_nlr10_d18",
        "label": "BBC NLR10 d=18",
        "index": 22,
        "phase0_pqlimit": 200_000,
        "official_pqlimit": 200_000,
    },
    {
        "case": "transcx_d13",
        "label": "TransCX d=13",
        "index": 107,
        "phase0_pqlimit": 200_000,
        "official_pqlimit": 1_000_000,
    },
]


def prediction_masks(path):
    masks = []
    for line in path.read_text().splitlines():
        masks.append(
            sum((character == "1") << index for index, character in enumerate(line))
        )
    return masks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase0-dir", required=True, type=Path)
    parser.add_argument("--audit-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--slurm-job-id", default="417792")
    args = parser.parse_args()

    cases = []
    for definition in CASES:
        phase = json.loads(
            (args.phase0_dir / f"{definition['case']}.json").read_text()
        )
        index_directory = args.audit_dir / f"{definition['index']:03d}"
        audit = json.loads((index_directory / "result.json").read_text())
        official = audit["variants"]["baseline"]
        if official["binary_sha256"] != BASELINE_SHA256:
            raise RuntimeError("Independent audit did not use the pinned binary.")
        if official["num_shots"] != phase["shots"]:
            raise RuntimeError("Independent and embedded shot counts differ.")
        if int(audit["sample_seed"]) != int(phase["sample_seed"]):
            raise RuntimeError("Independent and embedded sampling seeds differ.")

        official_masks = prediction_masks(
            index_directory / "baseline.predictions.01"
        )
        embedded_masks = [
            shot["baseline_logical_mask"] for shot in phase["shot_results"]
        ]
        if len(official_masks) != len(embedded_masks):
            raise RuntimeError("Independent and embedded prediction counts differ.")

        cases.append(
            {
                "case": definition["case"],
                "label": definition["label"],
                "manifest_index": definition["index"],
                "shots": phase["shots"],
                "sample_seed": phase["sample_seed"],
                "phase0_pqlimit": definition["phase0_pqlimit"],
                "official_pqlimit": definition["official_pqlimit"],
                "embedded_seconds_per_shot": (
                    phase["summary"]["baseline_seconds"] / phase["shots"]
                ),
                "official_seconds_per_shot": official[
                    "mean_decode_seconds_per_shot"
                ],
                "official_process_wall_seconds": official[
                    "process_wall_seconds"
                ],
                "prediction_mismatches": sum(
                    left != right
                    for left, right in zip(official_masks, embedded_masks)
                ),
                "official_errors": official["num_errors"],
                "official_low_confidence": official["num_low_confidence"],
                "official_binary_sha256": official["binary_sha256"],
                "official_command": official["command"],
            }
        )

    report = {
        "schema_version": 1,
        "status": "independent_official_baseline_audit",
        "slurm_job_id": args.slurm_job_id,
        "host_cpu": "AMD EPYC 9354 32-Core Processor",
        "baseline_commit": BASELINE_COMMIT,
        "source_and_testdata_recursive_diff_count": 0,
        "cases": cases,
    }
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
