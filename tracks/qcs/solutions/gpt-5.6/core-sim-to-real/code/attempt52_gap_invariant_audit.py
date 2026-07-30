#!/usr/bin/env python3
"""Attempt 52: verify the sealed failure-boundary and size-invariant appendix.

This is a simulator-free derivation from Attempts 25, 28, 34, and 45.  It
does not create new performance evidence or open confirmation truths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CORE = HERE.parent
RESULTS = CORE / "results_summary"
OUTPUT = RESULTS / "QL1F-attempt52-gap-invariant-audit.json"
REPORT = CORE / "docs" / "ATTEMPT52_DELIVERABLE_REPORT.md"
PROTOCOL = CORE / "docs" / "ATTEMPT52_PROTOCOL.md"
PLOT = CORE / "plots" / "attempt45-gap-size-evidence-development.png"

INPUTS = {
    "attempt25": RESULTS / "QL1F-attempt25-mismatch-boundary.json",
    "attempt26": RESULTS / "QL1F-attempt26-dimension-benchmark.json",
    "attempt27": RESULTS / "QL1F-attempt27-exact-dimension-scaling.json",
    "attempt28": RESULTS / "QL1F-attempt28-joint-dimension-scaling.json",
    "attempt34_v1": (
        RESULTS / "QL1F-attempt34-endpoint-rank-audit.v1-default-ode.json"
    ),
    "attempt34": RESULTS / "QL1F-attempt34-endpoint-rank-audit.json",
    "attempt45": RESULTS / "QL1F-attempt45-existing-gap-size-evidence.json",
}


def canonical_bytes(path: Path) -> bytes:
    text = path.read_text(encoding="utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def binary_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def joint_rows(attempt45: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        (
            row
            for row in attempt45["gap_evidence"][
                "success_curve_truth_bootstrap"
            ]
            if row["method"] == "joint-15-v1"
        ),
        key=lambda row: (row["family"], float(row["epsilon"])),
    )


def build_payload() -> dict[str, Any]:
    for path in (*INPUTS.values(), PROTOCOL, PLOT):
        if not path.is_file():
            raise FileNotFoundError(path)

    attempt26 = load(INPUTS["attempt26"])
    attempt27 = load(INPUTS["attempt27"])
    attempt28 = load(INPUTS["attempt28"])
    attempt34_v1 = load(INPUTS["attempt34_v1"])
    attempt34 = load(INPUTS["attempt34"])
    attempt45 = load(INPUTS["attempt45"])
    rows = joint_rows(attempt45)
    size_rows = attempt45["size_evidence"]["rows"]

    upstream_hashes_close = all(
        attempt45["source_hashes"][name]["canonical_sha256"]
        == canonical_sha256(INPUTS[name])
        for name in ("attempt25", "attempt28", "attempt34")
    )
    families = sorted({row["family"] for row in rows})
    epsilons = sorted({float(row["epsilon"]) for row in rows})
    by_key = {
        (row["family"], float(row["epsilon"])): row for row in rows
    }
    observed_ranks = [
        [int(row["endpoint_rank"]), int(row["hessian_rank"])]
        for row in size_rows
    ]
    zero_cost_raw = attempt45["negative_resource_scaling_result"][
        "zero_cost_raw_by_dimension"
    ]
    selected_points = {
        "general-d2": "exact-construction",
        "general-d3": "exact-construction",
        "general-d4": "exact-construction",
        "original-d4-cnot": "refined-optimized",
    }
    audited_points = []
    for system in attempt34["systems"]:
        point = next(
            row
            for row in system["points"]
            if row["label"] == selected_points[system["label"]]
        )
        audited_points.append((system, point))
    old_gap_ranks = [
        int(row["inferred_rank"]) for row in attempt27["models"]
    ]

    checks = {
        "attempt45_complete": attempt45["status"] == "complete",
        "attempt45_upstream_hashes_close": upstream_hashes_close,
        "attempt45_plot_hash_closes": (
            attempt45["artifacts"]["plot_png"]["sha256"]
            == binary_sha256(PLOT)
        ),
        "three_failure_families_retained": families
        == ["combined", "control-map", "drift"],
        "three_gap_levels_retained": epsilons == [0.02, 0.05, 0.10],
        "combined_failure_boundary_visible": (
            float(by_key[("combined", 0.05)]["success"]) >= 0.75
            and float(by_key[("combined", 0.10)]["success"]) < 0.75
        ),
        "three_hilbert_dimensions_retained": (
            sorted({int(row["dimension"]) for row in size_rows}) == [2, 3, 4]
        ),
        "selected_points_are_converged_controls": all(
            point["label"] in {"exact-construction", "refined-optimized"}
            for _, point in audited_points
        ),
        "all_selected_systems_full_su_controllable": all(
            system["lie_algebra"]["full_su_controllable"]
            for system, _ in audited_points
        ),
        "endpoint_hessian_rank_equality_holds": all(
            endpoint == hessian for endpoint, hessian in observed_ranks
        ),
        "endpoint_ranks_are_physical": all(
            int(point["endpoint_rank"]["rank"])
            <= int(system["dimension"]) ** 2 - 1
            for system, point in audited_points
        ),
        "finite_difference_errors_below_5e_3": all(
            float(point["finite_difference_max_relative_error"]) < 5e-3
            for _, point in audited_points
        ),
        "unitarity_residuals_below_1e_6": all(
            float(point["unitarity_residual_frobenius"]) < 1e-6
            for _, point in audited_points
        ),
        "weighted_gram_errors_below_0_05": all(
            float(point["weighted_endpoint_hessian_relative_error"]) < 0.05
            for _, point in audited_points
        ),
        "old_attempt27_gap_ranks_are_3_8_8": old_gap_ranks == [3, 8, 8],
        "d4_old_rank_discrepancy_marked_numerical_artifact": (
            attempt34["checks"][
                "dimension_general_d4_discrepancy_is_numerical_artifact"
            ]
            and "artifact"
            in attempt34["decision"][
                "attempt27_d4_rank_discrepancy_classification"
            ]
        ),
        "unconditional_rank_law_rejected": (
            attempt34["decision"]["rejected_claim"]
            == "Unconditional rank(H)=d^2-1."
        ),
        "resource_scaling_nonidentifiability_preserved": (
            all(bool(value) for value in zero_cost_raw.values())
            and not attempt45["claim_boundary"][
                "cross_dimension_resource_advantage"
            ]
            and attempt28["checks"]["resource_scaling_testable"] is False
        ),
        "no_new_simulator_queries": (
            attempt45["checks"]["new_simulator_queries"] == 0
        ),
        "no_confirmation_truths_opened": (
            attempt45["checks"]["confirmation_truths_opened"] == 0
        ),
        "attempt26_reachability_construction_retained": (
            attempt26["status"] == "complete"
            and sorted(int(key) for key in attempt26["reachability"]) == [2, 3, 4]
        ),
        "attempt34_v1_failure_retained": (
            attempt34_v1["status"] == "diagnostic-failed"
            and not attempt34_v1["checks"][
                "converged_hessian_endpoint_ranks_match"
            ]
        ),
    }
    status = "pass" if all(checks.values()) else "fail"
    return {
        "schema": "QL1F-attempt52-derived-invariant-audit-v2",
        "attempt": 52,
        "status": status,
        "scope": (
            "simulator-free verification of development failure-mode and "
            "cross-size mechanism evidence"
        ),
        "source_hashes": {
            name: {
                "path": path.relative_to(CORE).as_posix(),
                "canonical_sha256": canonical_sha256(path),
            }
            for name, path in INPUTS.items()
        },
        "protocol": {
            "path": PROTOCOL.relative_to(CORE).as_posix(),
            "canonical_sha256": canonical_sha256(PROTOCOL),
        },
        "runner": {
            "path": Path(__file__).resolve().relative_to(CORE).as_posix(),
            "canonical_sha256": canonical_sha256(Path(__file__).resolve()),
        },
        "no_new_compute": {
            "simulator_queries": 0,
            "fidelity_calls": 0,
            "gradient_calls": 0,
            "hessian_calls": 0,
            "optimization_calls": 0,
            "confirmation_truths_opened": 0,
        },
        "construction_context": {
            "source_attempt": 26,
            "reachability": attempt26["reachability"],
            "representative_selection_warning": (
                "Attempt-26/27 spectral-gap ranks are historical diagnostics, "
                "not physical-rank evidence."
            ),
        },
        "failure_mode_evidence": {
            "source_attempt": 45,
            "method": "historical joint-15-v1 coordinate-scan package",
            "families": families,
            "gap_levels": epsilons,
            "rows": rows,
            "interpretation": (
                "Development success degrades as the model-truth gap grows; "
                "the combined family falls from 0.875 at epsilon=0.05 to "
                "0.15625 at epsilon=0.10."
            ),
            "claim_boundary": (
                "This is historical development evidence, not a fresh "
                "principal-global confirmation sweep."
            ),
        },
        "cross_size_invariant": {
            "source_attempts": [34, 45],
            "rows": size_rows,
            "distinct_hilbert_dimensions": [2, 3, 4],
            "observed_rank_pairs": observed_ranks,
            "supported_claim": attempt34["decision"]["supported_claim"],
            "rejected_claim": attempt34["decision"]["rejected_claim"],
            "numerical_artifact_correction": attempt34["decision"][
                "attempt27_d4_rank_discrepancy_classification"
            ],
            "old_attempt27_gap_ranks": old_gap_ranks,
            "spectral_gap_is_rank_definition": False,
            "interpretation": attempt45["size_evidence"][
                "rank_interpretation"
            ],
        },
        "honest_negative_result": {
            "source_attempt": 28,
            "zero_cost_raw_by_dimension": zero_cost_raw,
            "claim": attempt45["negative_resource_scaling_result"]["claim"],
            "reason": attempt45["negative_resource_scaling_result"][
                "falsification_reason"
            ],
            "status": "unidentifiable-zero-cost-raw-baseline",
            "cross_dimension_resource_advantage_established": False,
        },
        "checks": checks,
        "artifacts": {
            "figure": {
                "path": PLOT.relative_to(CORE).as_posix(),
                "sha256": binary_sha256(PLOT),
            }
        },
        "claim_boundary": {
            "new_simulator_queries": 0,
            "confirmation_truths_opened": 0,
            "fresh_confirmation": False,
            "cross_dimension_resource_advantage": False,
            "universal_rank_theorem": False,
            "qubit_count_scaling": False,
            "hardware_or_cesium_evidence": False,
        },
    }


def build_report(payload: dict[str, Any]) -> str:
    checks_passed = sum(payload["checks"].values())
    checks_total = len(payload["checks"])
    rows = payload["cross_size_invariant"]["rows"]
    rank_table = "\n".join(
        "| {system} | {dimension} | {endpoint_rank} | {hessian_rank} |".format(
            **row
        )
        for row in rows
    )
    return f"""# Attempt 52 — failure boundary and cross-size invariant

Status: **{payload["status"].upper()}** ({checks_passed}/{checks_total} checks).

This appendix turns sealed development/mechanism evidence into a directly
auditable Challenge-113 deliverable. It performs no simulator query and opens
no confirmation truth.

## Failure-mode evidence

For the historical Joint-15 v1 coordinate-scan package, the combined-mismatch
success rate falls from **0.875** at epsilon=0.05 to **0.15625** at
epsilon=0.10. Control-map and drift families also degrade at the largest gap.
These are development curves, not a fresh principal-global confirmation sweep.

## Cross-size mechanism invariant

| System | Hilbert dimension | Endpoint rank | Hessian rank |
|---|---:|---:|---:|
{rank_table}

The supported local statement is:
**{payload["cross_size_invariant"]["supported_claim"]}**

The unconditional statement
**{payload["cross_size_invariant"]["rejected_claim"]}** is rejected. The old
d=4 discrepancy was classified as
**{payload["cross_size_invariant"]["numerical_artifact_correction"]}**.

## Honest negative result

No cross-dimension resource advantage is claimed. Attempt 28 left the raw
warm-start baseline at zero restricted cost in d=2,3,4, so the proposed
resource-scaling comparison was not identifiable under that frozen epsilon.

## Reproduce

```bash
python core-sim-to-real/code/attempt52_gap_invariant_audit.py --verify-only
```

The displayed figure is
`../plots/attempt45-gap-size-evidence-development.png`.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="compare sealed output with a fresh simulator-free derivation",
    )
    args = parser.parse_args()
    payload = build_payload()
    if payload["status"] != "pass":
        raise RuntimeError(payload["checks"])

    if args.verify_only:
        stored = load(OUTPUT)
        if stored != payload:
            raise RuntimeError("stored Attempt-52 result does not match")
    else:
        write_json(OUTPUT, payload)
        REPORT.write_text(
            build_report(payload),
            encoding="utf-8",
            newline="\n",
        )

    passed = sum(payload["checks"].values())
    print(
        f"attempt52 {payload['status']}; checks={passed}/{len(payload['checks'])}"
    )


if __name__ == "__main__":
    main()
