#!/usr/bin/env python3
"""Build the small, explicitly diagnostic campaign that can finish by the presentation deadline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = str(Path(__file__).resolve().parent)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from build_campaign import GEOMETRIES, atomic_json, cell


def nested_cells() -> list[dict[str, object]]:
    """Two tightening directions around the existing (L,d)=(1,2) P2 baseline."""
    selected: list[dict[str, object]] = []
    for L, d in ((1, 3), (2, 2)):
        item = cell(
            "deadline-nested",
            "observable",
            "83",
            1,
            L,
            d,
            "matrix",
            "complete",
            "U1_INVARIANT_KMS_STATES",
            "P2",
            0.0,
        )
        item.update(
            diagnostic_only=True,
            precision_profile="deadline-balanced",
            requested_walltime="08:00:00",
        )
        selected.append(item)
    if {(item["L"], item["d"]) for item in selected} != {(1, 3), (2, 2)}:
        raise RuntimeError("deadline nested-level regression")
    return selected


def gap_scan_cells() -> list[dict[str, object]]:
    """Independent fixed-gamma trials; UNKNOWN at one gamma does not stop the scan."""
    selected: list[dict[str, object]] = []
    for geometry in GEOMETRIES:
        base = cell(
            "deadline-gapscan",
            "gap",
            geometry,
            1,
            1,
            2,
            "matrix",
            "complete",
            "U1_INVARIANT_KMS_STATES",
            "P2",
        )
        base.update(
            kind="gap_scan",
            id=f"deadline-gapscan-{geometry}-n1-L1-d2-matrix-complete-U1_INVARIANT_KMS_STATES-P2",
            # gamma=0 is first so it can be imported from the completed
            # observable cell.  Remaining trials prioritize the expected
            # transition region; the scan is nonadaptive, so order changes no
            # mathematical classification and only improves deadline yield.
            gamma_trials=[0.0, 0.30, 0.20, 0.40, 0.10, 0.50, 0.15, 0.60, 0.05],
            feasible_anchor_path=(
                "results/presentation_pilots/presentation-primary-observable-"
                f"{geometry}-n1-L1-d2-matrix-complete-U1_INVARIANT_KMS_STATES-P2-g0.00.json"
            ),
            diagnostic_only=True,
            precision_profile="deadline-balanced",
            requested_walltime="06:00:00",
        )
        selected.append(base)
    p4 = cell(
        "deadline-gapscan",
        "gap",
        "83",
        1,
        1,
        2,
        "matrix",
        "complete",
        "U1_INVARIANT_KMS_STATES",
        "P4",
    )
    p4.update(
        kind="gap_scan",
        id="deadline-gapscan-83-n1-L1-d2-matrix-complete-U1_INVARIANT_KMS_STATES-P4",
        gamma_trials=[0.0, 0.10, 0.075, 0.15, 0.05, 0.20, 0.025, 0.30],
        feasible_anchor_path=(
            "results/presentation_pilots/presentation-primary-observable-"
            "83-n1-L1-d2-matrix-complete-U1_INVARIANT_KMS_STATES-P4-g0.00.json"
        ),
        diagnostic_only=True,
        precision_profile="deadline-balanced",
        requested_walltime="06:00:00",
    )
    selected.append(p4)
    return selected


def gap_refinement_cells() -> list[dict[str, object]]:
    """Five-millitherm refinement grids around the first exact exclusions."""
    selected: list[dict[str, object]] = []
    specifications = (
        ("P2", 0.05, 0.50, [index / 200 for index in range(100, 121)]),
        ("P4", 0.03, 0.15, [index / 200 for index in range(30, 41)]),
    )
    for point, expected_t, expected_mu, trials in specifications:
        item = cell(
            "deadline-gaprefine", "gap", "83", 1, 1, 2, "matrix", "complete",
            "U1_INVARIANT_KMS_STATES", point,
        )
        if (float(item["t"]), float(item["mu"])) != (expected_t, expected_mu):
            raise RuntimeError(f"unexpected {point} parameters in refinement manifest")
        item.update(
            kind="gap_scan",
            id=f"deadline-gaprefine-83-n1-L1-d2-matrix-complete-U1_INVARIANT_KMS_STATES-{point}",
            gamma_trials=trials,
            diagnostic_only=True,
            precision_profile="deadline-balanced",
            requested_walltime="06:00:00",
        )
        selected.append(item)
    return selected


def gap_retry_cells() -> list[dict[str, object]]:
    """Known MKL numerical failures retried with an independent KKT backend."""
    item = cell(
        "deadline-gapretry", "gap", "83", 1, 1, 2, "matrix", "complete",
        "U1_INVARIANT_KMS_STATES", "P2",
    )
    item.update(
        kind="gap_scan",
        id="deadline-gapretry-83-n1-L1-d2-matrix-complete-U1_INVARIANT_KMS_STATES-P2-qdldl",
        gamma_trials=[0.510, 0.515],
        diagnostic_only=True,
        precision_profile="deadline-balanced",
        requested_walltime="06:00:00",
        retry_reason="MKL Pardiso zero-pivot numerical failure",
        requested_direct_solver="qdldl",
    )
    return [item]


def gap_micro_cells() -> list[dict[str, object]]:
    """Probe immediately around the unresolved P2 gamma=0.510 trial.

    The non-lattice samples do not reinterpret the failed 0.510 solve.  They
    can nevertheless strengthen the certified upper statement and show how
    localized the numerical transition is while the independent QDLDL retry
    continues.
    """
    item = cell(
        "deadline-gapmicro", "gap", "83", 1, 1, 2, "matrix", "complete",
        "U1_INVARIANT_KMS_STATES", "P2",
    )
    item.update(
        kind="gap_scan",
        id="deadline-gapmicro-83-n1-L1-d2-matrix-complete-U1_INVARIANT_KMS_STATES-P2",
        gamma_trials=[0.511, 0.509, 0.512, 0.508],
        diagnostic_only=True,
        precision_profile="deadline-balanced",
        requested_walltime="02:00:00",
        retry_reason="localize the transition around unresolved gamma=0.510",
    )
    return [item]


def geometry_refinement_cells() -> list[dict[str, object]]:
    """Resolve geometry-sensitive P2 endpoints inside the coarse 0.5--0.6 span."""
    selected: list[dict[str, object]] = []
    for geometry in ("124", "line83"):
        item = cell(
            "deadline-geomrefine", "gap", geometry, 1, 1, 2, "matrix", "complete",
            "U1_INVARIANT_KMS_STATES", "P2",
        )
        item.update(
            kind="gap_scan",
            id=(
                f"deadline-geomrefine-{geometry}-n1-L1-d2-matrix-complete-"
                "U1_INVARIANT_KMS_STATES-P2"
            ),
            # A likely exclusion is attempted first.  The scan remains valid
            # if any individual point is UNKNOWN because trials are independent.
            gamma_trials=[0.52, 0.51, 0.54, 0.56, 0.58],
            diagnostic_only=True,
            precision_profile="deadline-balanced",
            requested_walltime="04:00:00",
        )
        selected.append(item)
    return selected


def geometry_parallel_recovery_cells() -> list[dict[str, object]]:
    """Unblock the long `{12,4}` exact-PSD fallback with independent probes."""
    item = cell(
        "deadline-geomparallel", "gap", "124", 1, 1, 2, "matrix", "complete",
        "U1_INVARIANT_KMS_STATES", "P2",
    )
    item.update(
        kind="gap_scan",
        id=(
            "deadline-geomparallel-124-n1-L1-d2-matrix-complete-"
            "U1_INVARIANT_KMS_STATES-P2"
        ),
        gamma_trials=[0.51, 0.54],
        diagnostic_only=True,
        precision_profile="deadline-balanced",
        requested_walltime="03:00:00",
        retry_reason=(
            "independent probes while gamma=0.52 remains in the exact-field PSD fallback"
        ),
    )
    return [item]


def geometry_micro_recovery_cells() -> list[dict[str, object]]:
    """Independent midpoint probes that can tighten both geometry statements."""
    selected: list[dict[str, object]] = []
    for geometry,trials in (("124",[0.515]),("line83",[0.53])):
        item = cell(
            "deadline-geommicro", "gap", geometry, 1, 1, 2, "matrix", "complete",
            "U1_INVARIANT_KMS_STATES", "P2",
        )
        item.update(
            kind="gap_scan",
            id=(
                f"deadline-geommicro-{geometry}-n1-L1-d2-matrix-complete-"
                "U1_INVARIANT_KMS_STATES-P2"
            ),
            gamma_trials=trials,
            diagnostic_only=True,
            precision_profile="deadline-balanced",
            requested_walltime="03:00:00",
            retry_reason="transition midpoint using the optimized rigorous PSD checker",
        )
        selected.append(item)
    return selected


def geometry_target_grid_cells() -> list[dict[str, object]]:
    """Cover the eight hard-core Target-2 geometry cells still lacking an upper statement.

    The first trial is the smallest coarse exclusion already supported on
    ``{8,3}`` at the same parameter point.  The second trial, ``gamma=0``, is
    an independent non-exclusion anchor.  Trials remain independent, so a
    numerical failure at either value cannot be stepped over or reclassified.
    """
    candidate_upper = {"P1": 0.60, "P3": 0.60, "P4": 0.30, "P5": 1.00}
    selected: list[dict[str, object]] = []
    for geometry in ("124", "line83"):
        for point, upper in candidate_upper.items():
            item = cell(
                "deadline-geometry-grid", "gap", geometry, 1, 1, 2, "matrix",
                "complete", "U1_INVARIANT_KMS_STATES", point,
            )
            item.update(
                kind="gap_scan",
                id=(
                    f"deadline-geometry-grid-{geometry}-n1-L1-d2-matrix-complete-"
                    f"U1_INVARIANT_KMS_STATES-{point}"
                ),
                gamma_trials=[upper, 0.0],
                diagnostic_only=True,
                precision_profile="deadline-balanced",
                requested_walltime="03:00:00",
                retry_reason=(
                    "extended-deadline coverage of the remaining hard-core Target-2 "
                    "geometry/parameter cells"
                ),
            )
            selected.append(item)
    return selected


def final_geometry_refinement_cells() -> list[dict[str, object]]:
    """Reproduce the final P4/P5 refinement cells included in the report."""
    specifications = (
        ("124", "P4", [0.170, 0.160], "03:00:00", "P4"),
        ("line83", "P4", [0.170, 0.160], "03:00:00", "P4"),
        ("124", "P5", [0.800, 0.750], "03:00:00", "P5"),
        ("line83", "P4", [0.165], "02:00:00", "P4-mid"),
    )
    selected: list[dict[str, object]] = []
    for geometry, point, trials, walltime, suffix in specifications:
        item = cell(
            "deadline-geometry-refine", "gap", geometry, 1, 1, 2, "matrix",
            "complete", "U1_INVARIANT_KMS_STATES", point,
        )
        reason = (
            "resolve the 0.160--0.170 line-graph P4 interval at requested spacing"
            if suffix == "P4-mid"
            else (
                f"refine the exact coarse {point} geometry statement before "
                "the extended deadline"
            )
        )
        item.update(
            kind="gap_scan",
            id=(
                f"deadline-geometry-refine-{geometry}-n1-L1-d2-matrix-complete-"
                f"U1_INVARIANT_KMS_STATES-{suffix}"
            ),
            gamma_trials=trials,
            diagnostic_only=True,
            precision_profile="deadline-balanced",
            requested_walltime=walltime,
            retry_reason=reason,
        )
        selected.append(item)
    return selected


def remaining_target_gap_cells() -> list[dict[str, object]]:
    """Coarse complete-level gap coverage for the three unsampled Target-2 points."""
    selected: list[dict[str, object]] = []
    for point in ("P1", "P3", "P5"):
        item = cell(
            "deadline-target-gapscan", "gap", "83", 1, 1, 2, "matrix", "complete",
            "U1_INVARIANT_KMS_STATES", point,
        )
        item.update(
            kind="gap_scan",
            id=(
                "deadline-target-gapscan-83-n1-L1-d2-matrix-complete-"
                f"U1_INVARIANT_KMS_STATES-{point}"
            ),
            gamma_trials=[0.0, 0.50, 0.25, 0.75, 0.10, 0.20, 0.30, 0.40, 0.60, 1.0],
            diagnostic_only=True,
            precision_profile="deadline-balanced",
            requested_walltime="03:00:00",
        )
        selected.append(item)
    return selected


def target_refinement_cells() -> list[dict[str, object]]:
    """Refine the remaining complete hard-core Target-2 transitions.

    P5 is intentionally a short transition-localization cell first: its
    coarse hierarchy remains feasible at 0.75, so seven independent probes
    are ordered to yield a useful endpoint quickly.  P1 and P3 already have
    checked 0.50/0.60 anchors and receive the full missing 0.005 grid.
    """
    specifications = (
        ("P5", [0.875, 0.810, 0.940, 0.845, 0.905, 0.780, 0.970]),
        ("P1", [index / 200 for index in range(101, 120)]),
        ("P3", [index / 200 for index in range(101, 120)]),
    )
    selected: list[dict[str, object]] = []
    for point, trials in specifications:
        item = cell(
            "deadline-target-refine", "gap", "83", 1, 1, 2, "matrix", "complete",
            "U1_INVARIANT_KMS_STATES", point,
        )
        item.update(
            kind="gap_scan",
            id=(
                "deadline-target-refine-83-n1-L1-d2-matrix-complete-"
                f"U1_INVARIANT_KMS_STATES-{point}"
            ),
            gamma_trials=trials,
            diagnostic_only=True,
            precision_profile="deadline-balanced",
            requested_walltime="05:00:00",
        )
        selected.append(item)
    return selected


def p5_fine_refinement_cells() -> list[dict[str, object]]:
    """Requested-spacing grid inside P5's checked 0.750--0.780 transition."""
    item = cell(
        "deadline-p5-fine", "gap", "83", 1, 1, 2, "matrix", "complete",
        "U1_INVARIANT_KMS_STATES", "P5",
    )
    item.update(
        kind="gap_scan",
        id=(
            "deadline-p5-fine-83-n1-L1-d2-matrix-complete-"
            "U1_INVARIANT_KMS_STATES-P5"
        ),
        gamma_trials=[0.765, 0.755, 0.775, 0.760, 0.770],
        diagnostic_only=True,
        precision_profile="deadline-balanced",
        requested_walltime="02:00:00",
    )
    return [item]


def p3_micro_refinement_cells() -> list[dict[str, object]]:
    """Probe around P3's unresolved 0.515 sample without crossing it."""
    item = cell(
        "deadline-p3-micro", "gap", "83", 1, 1, 2, "matrix", "complete",
        "U1_INVARIANT_KMS_STATES", "P3",
    )
    item.update(
        kind="gap_scan",
        id=(
            "deadline-p3-micro-83-n1-L1-d2-matrix-complete-"
            "U1_INVARIANT_KMS_STATES-P3"
        ),
        gamma_trials=[0.514, 0.516, 0.512, 0.518],
        diagnostic_only=True,
        precision_profile="deadline-balanced",
        requested_walltime="02:00:00",
    )
    return [item]


def remaining_target_observable_cells() -> list[dict[str, object]]:
    """Observable coverage for P1/P3/P5 on the fastest complete baseline graph."""
    selected: list[dict[str, object]] = []
    for point in ("P1", "P3", "P5"):
        for gamma in (0.0, 0.05, 0.10):
            item = cell(
                "deadline-target", "observable", "83", 1, 1, 2, "matrix", "complete",
                "U1_INVARIANT_KMS_STATES", point, gamma,
            )
            item.update(
                diagnostic_only=True,
                precision_profile="presentation-fast",
                requested_walltime="04:00:00",
            )
            selected.append(item)
    return selected


def representative_cutoff2_gap_cells() -> list[dict[str, object]]:
    """One bounded cutoff-dependence probe using the complete baseline hierarchy."""
    item = cell(
        "deadline-cutoff2-gapscan", "gap", "83", 2, 1, 2, "matrix", "complete",
        "U1_INVARIANT_KMS_STATES", "P2",
    )
    item.update(
        kind="gap_scan",
        id=(
            "deadline-cutoff2-gapscan-83-n2-L1-d2-matrix-complete-"
            "U1_INVARIANT_KMS_STATES-P2"
        ),
        # Start away from the expected transition so a long representative
        # run has a good chance to preserve one exact exclusion before moving
        # to feasibility and tighter probes.
        gamma_trials=[0.75, 0.0, 0.60, 0.50],
        diagnostic_only=True,
        precision_profile="deadline-balanced",
        requested_walltime="06:00:00",
    )
    return [item]


def exact_observable_cells() -> list[dict[str, object]]:
    """One representative cell whose accepted endpoints receive exact projection."""
    item = cell(
        "deadline-exact", "observable", "83", 1, 1, 2, "matrix", "complete",
        "U1_INVARIANT_KMS_STATES", "P4", 0.10,
    )
    item.update(
        diagnostic_only=True,
        precision_profile="presentation-fast",
        exact_observable_certificate=True,
        requested_walltime="02:00:00",
    )
    return [item]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--nested-output", type=Path, default=Path("results/deadline_nested_manifest.json")
    )
    parser.add_argument(
        "--gap-output", type=Path, default=Path("results/deadline_gap_scan_manifest.json")
    )
    parser.add_argument(
        "--refine-output", type=Path, default=Path("results/deadline_gap_refinement_manifest.json")
    )
    parser.add_argument(
        "--retry-output", type=Path, default=Path("results/deadline_gap_retry_manifest.json")
    )
    parser.add_argument(
        "--micro-output", type=Path, default=Path("results/deadline_gap_micro_manifest.json")
    )
    parser.add_argument(
        "--geometry-refine-output",
        type=Path,
        default=Path("results/deadline_geometry_refinement_manifest.json"),
    )
    parser.add_argument(
        "--geometry-parallel-output",
        type=Path,
        default=Path("results/deadline_geometry_parallel_manifest.json"),
    )
    parser.add_argument(
        "--geometry-micro-output",
        type=Path,
        default=Path("results/deadline_geometry_micro_manifest.json"),
    )
    parser.add_argument(
        "--geometry-grid-output",
        type=Path,
        default=Path("results/deadline_geometry_grid_manifest.json"),
    )
    parser.add_argument(
        "--remaining-gap-output",
        type=Path,
        default=Path("results/deadline_remaining_target_gap_manifest.json"),
    )
    parser.add_argument(
        "--remaining-observable-output",
        type=Path,
        default=Path("results/deadline_remaining_target_observable_manifest.json"),
    )
    parser.add_argument(
        "--target-refine-output",
        type=Path,
        default=Path("results/deadline_target_refinement_manifest.json"),
    )
    parser.add_argument(
        "--p5-fine-output",
        type=Path,
        default=Path("results/deadline_p5_fine_manifest.json"),
    )
    parser.add_argument(
        "--p3-micro-output",
        type=Path,
        default=Path("results/deadline_p3_micro_manifest.json"),
    )
    parser.add_argument(
        "--cutoff2-gap-output",
        type=Path,
        default=Path("results/deadline_cutoff2_gap_manifest.json"),
    )
    parser.add_argument(
        "--exact-observable-output",
        type=Path,
        default=Path("results/deadline_exact_observable_manifest.json"),
    )
    args = parser.parse_args()
    nested = nested_cells()
    scans = gap_scan_cells()
    refinements = gap_refinement_cells()
    retries = gap_retry_cells()
    micro = gap_micro_cells()
    geometry_refinements = geometry_refinement_cells()
    geometry_parallel = geometry_parallel_recovery_cells()
    geometry_micro = geometry_micro_recovery_cells()
    geometry_grid = [*geometry_target_grid_cells(), *final_geometry_refinement_cells()]
    remaining_gaps = remaining_target_gap_cells()
    target_refinements = target_refinement_cells()
    p5_fine = p5_fine_refinement_cells()
    p3_micro = p3_micro_refinement_cells()
    remaining_observables = remaining_target_observable_cells()
    cutoff2_gaps = representative_cutoff2_gap_cells()
    exact_observables = exact_observable_cells()
    common = {
        "schema_version": 1,
        "generated_by": "scripts/build_deadline_manifest.py",
        "claim_scope": "LOW_PRECISION_CLARABEL_DIAGNOSTIC_ONLY",
        "deadline_hours": 18,
        "solver_profile": "deadline-balanced",
    }
    atomic_json(
        args.nested_output,
        {**common, "campaign_kind": "nested_observables", "cell_count": len(nested), "cells": nested},
    )
    atomic_json(
        args.gap_output,
        {
            **common,
            "campaign_kind": "independent_fixed_gamma_scan",
            "cell_count": len(scans),
            "trial_count": sum(len(item["gamma_trials"]) for item in scans),
            "cells": scans,
        },
    )
    atomic_json(
        args.refine_output,
        {
            **common,
            "campaign_kind": "fixed_grid_exact_exclusion_refinement",
            "claim_scope": "EXACT_PROJECTED_EXCLUSIONS_WITH_CHECKED_FEASIBILITY",
            "cell_count": len(refinements),
            "trial_count": sum(len(item["gamma_trials"]) for item in refinements),
            "grid_spacing": 0.005,
            "cells": refinements,
        },
    )
    atomic_json(
        args.retry_output,
        {
            **common,
            "campaign_kind": "alternate_kkt_retry",
            "claim_scope": "EXACT_PROJECTED_EXCLUSIONS_WITH_CHECKED_FEASIBILITY",
            "cell_count": len(retries),
            "trial_count": sum(len(item["gamma_trials"]) for item in retries),
            "cells": retries,
        },
    )
    atomic_json(
        args.micro_output,
        {
            **common,
            "campaign_kind": "transition_micro_scan",
            "claim_scope": "EXACT_PROJECTED_EXCLUSIONS_WITH_CHECKED_FEASIBILITY",
            "cell_count": len(micro),
            "trial_count": sum(len(item["gamma_trials"]) for item in micro),
            "cells": micro,
        },
    )
    atomic_json(
        args.geometry_refine_output,
        {
            **common,
            "campaign_kind": "geometry_fixed_grid_refinement",
            "claim_scope": "EXACT_PROJECTED_EXCLUSIONS_WITH_CHECKED_FEASIBILITY",
            "cell_count": len(geometry_refinements),
            "trial_count": sum(len(item["gamma_trials"]) for item in geometry_refinements),
            "cells": geometry_refinements,
        },
    )
    atomic_json(
        args.geometry_parallel_output,
        {
            **common,
            "campaign_kind": "geometry_parallel_recovery",
            "claim_scope": "EXACT_PROJECTED_EXCLUSIONS_WITH_CHECKED_FEASIBILITY",
            "cell_count": len(geometry_parallel),
            "trial_count": sum(len(item["gamma_trials"]) for item in geometry_parallel),
            "cells": geometry_parallel,
        },
    )
    atomic_json(
        args.geometry_micro_output,
        {
            **common,
            "campaign_kind": "geometry_transition_midpoints",
            "claim_scope": "EXACT_PROJECTED_EXCLUSIONS_WITH_CHECKED_FEASIBILITY",
            "cell_count": len(geometry_micro),
            "trial_count": sum(len(item["gamma_trials"]) for item in geometry_micro),
            "cells": geometry_micro,
        },
    )
    atomic_json(
        args.geometry_grid_output,
        {
            **common,
            "campaign_kind": "extended_deadline_geometry_target_grid",
            "claim_scope": "EXACT_PROJECTED_EXCLUSIONS_WITH_CHECKED_FEASIBILITY",
            "cell_count": len(geometry_grid),
            "trial_count": sum(len(item["gamma_trials"]) for item in geometry_grid),
            "cells": geometry_grid,
        },
    )
    atomic_json(
        args.remaining_gap_output,
        {
            **common,
            "campaign_kind": "remaining_target2_baseline_gap_scan",
            "claim_scope": "EXACT_PROJECTED_EXCLUSIONS_WITH_CHECKED_FEASIBILITY",
            "cell_count": len(remaining_gaps),
            "trial_count": sum(len(item["gamma_trials"]) for item in remaining_gaps),
            "cells": remaining_gaps,
        },
    )
    atomic_json(
        args.remaining_observable_output,
        {
            **common,
            "campaign_kind": "remaining_target2_baseline_observables",
            "claim_scope": "LOW_PRECISION_CLARABEL_DIAGNOSTIC_ONLY",
            "cell_count": len(remaining_observables),
            "observable_optimum_count": 6 * len(remaining_observables),
            "cells": remaining_observables,
        },
    )
    atomic_json(
        args.target_refine_output,
        {
            **common,
            "campaign_kind": "remaining_target2_transition_refinement",
            "claim_scope": "EXACT_PROJECTED_EXCLUSIONS_WITH_CHECKED_FEASIBILITY",
            "cell_count": len(target_refinements),
            "trial_count": sum(len(item["gamma_trials"]) for item in target_refinements),
            "cells": target_refinements,
        },
    )
    atomic_json(
        args.p5_fine_output,
        {
            **common,
            "campaign_kind": "p5_requested_spacing_refinement",
            "claim_scope": "EXACT_PROJECTED_EXCLUSIONS_WITH_CHECKED_FEASIBILITY",
            "cell_count": len(p5_fine),
            "trial_count": sum(len(item["gamma_trials"]) for item in p5_fine),
            "grid_spacing": 0.005,
            "cells": p5_fine,
        },
    )
    atomic_json(
        args.p3_micro_output,
        {
            **common,
            "campaign_kind": "p3_unresolved_transition_micro_scan",
            "claim_scope": "EXACT_PROJECTED_EXCLUSIONS_WITH_CHECKED_FEASIBILITY",
            "cell_count": len(p3_micro),
            "trial_count": sum(len(item["gamma_trials"]) for item in p3_micro),
            "cells": p3_micro,
        },
    )
    atomic_json(
        args.cutoff2_gap_output,
        {
            **common,
            "campaign_kind": "representative_cutoff2_gap_scan",
            "claim_scope": "EXACT_PROJECTED_EXCLUSIONS_WITH_CHECKED_FEASIBILITY",
            "cell_count": len(cutoff2_gaps),
            "trial_count": sum(len(item["gamma_trials"]) for item in cutoff2_gaps),
            "cells": cutoff2_gaps,
        },
    )
    atomic_json(
        args.exact_observable_output,
        {
            **common,
            "campaign_kind": "representative_exact_observable_projection",
            "claim_scope": "EXACT_PROJECTED_OBSERVABLE_BOUNDS",
            "cell_count": len(exact_observables),
            "observable_optimum_count": 6 * len(exact_observables),
            "cells": exact_observables,
        },
    )
    print(
        f"wrote {len(nested)} nested observable cells and "
        f"{sum(len(item['gamma_trials']) for item in scans)} coarse plus "
        f"{sum(len(item['gamma_trials']) for item in refinements)} refinement plus "
        f"{sum(len(item['gamma_trials']) for item in retries)} alternate-backend retry plus "
        f"{sum(len(item['gamma_trials']) for item in micro)} micro plus "
        f"{sum(len(item['gamma_trials']) for item in geometry_refinements)} geometry-refinement plus "
        f"{sum(len(item['gamma_trials']) for item in geometry_parallel)} geometry-recovery plus "
        f"{sum(len(item['gamma_trials']) for item in geometry_micro)} geometry-midpoint plus "
        f"{sum(len(item['gamma_trials']) for item in geometry_grid)} geometry-grid plus "
        f"{sum(len(item['gamma_trials']) for item in remaining_gaps)} remaining-point gap trials and "
        f"{sum(len(item['gamma_trials']) for item in target_refinements)} target-refinement trials and "
        f"{sum(len(item['gamma_trials']) for item in p5_fine)} P5 fine trials and "
        f"{sum(len(item['gamma_trials']) for item in p3_micro)} P3 micro trials and "
        f"{len(remaining_observables)} remaining-point observable cells plus "
        f"{sum(len(item['gamma_trials']) for item in cutoff2_gaps)} cutoff-2 gap probes and "
        f"{len(exact_observables)} exact-observable cell",
        flush=True,
    )


if __name__ == "__main__":
    main()
