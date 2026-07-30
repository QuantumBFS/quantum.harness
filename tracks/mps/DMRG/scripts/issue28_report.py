#!/usr/bin/env python3
"""Build the fail-closed Issue #28 N5 paired analysis and report."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


TRACK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TRACK_ROOT.parents[2]
SRC = TRACK_ROOT / "src"
if str(TRACK_ROOT) not in sys.path:
    sys.path.insert(0, str(TRACK_ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

REPORT_RENDERER = REPO_ROOT / "skills" / "report" / "render_report.py"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="ascii"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid N5 input: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"N5 input must be a JSON object: {path}")
    return value


def _positive_vector(value: object, label: str) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 1 or array.size < 2:
        raise ValueError(f"{label} must contain at least two independent chains")
    if not np.all(np.isfinite(array)) or np.any(array <= 0.0):
        raise ValueError(f"{label} must contain finite positive values")
    return array


def _atomic_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[dict[str, Any]]) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            encoding="ascii",
            newline="",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _ratio_bootstrap(
    neural: np.ndarray,
    comparison: np.ndarray,
    *,
    replicates: int,
    seed: int,
    confidence: float,
) -> dict[str, Any]:
    from vmcrg_ref.objective import hierarchical_paired_bootstrap

    record = hierarchical_paired_bootstrap(
        np.log(neural),
        np.log(comparison),
        replicates=replicates,
        seed=seed,
        confidence=confidence,
    )
    return {
        **record,
        "estimate_ratio": float(math.exp(record["paired_estimate"])),
        "ci95_low_ratio": float(math.exp(record["ci95_low"])),
        "ci95_high_ratio": float(math.exp(record["ci95_high"])),
        "scale": "log_ratio",
    }


def _plot_seed_ratios(
    rows: Sequence[dict[str, Any]],
    output: Path,
) -> tuple[Path, Path]:
    labels = [str(row["bundle_id"]) for row in rows]
    x = np.arange(len(labels), dtype=np.float64)
    tau_unbiased = np.asarray(
        [float(row["tau_neural_over_unbiased"]) for row in rows]
    )
    tau_linear = np.asarray(
        [float(row["tau_neural_over_linear"]) for row in rows]
    )
    ess_unbiased = np.asarray(
        [float(row["ess_neural_over_unbiased"]) for row in rows]
    )
    ess_linear = np.asarray(
        [float(row["ess_neural_over_linear"]) for row in rows]
    )
    colors = {"unbiased": "#0072B2", "linear": "#D55E00"}
    figure, axes = plt.subplots(1, 2, figsize=(8.0, 3.2), constrained_layout=True)
    axes[0].plot(
        x,
        tau_unbiased,
        "o-",
        color=colors["unbiased"],
        label="neural / unbiased",
    )
    axes[0].plot(
        x,
        tau_linear,
        "s--",
        color=colors["linear"],
        label="neural / linear",
    )
    axes[0].axhline(1.0, color="#333333", linewidth=0.8)
    axes[0].axhline(1.10, color=colors["linear"], linewidth=0.8, linestyle=":")
    axes[0].set_ylabel("Integrated autocorrelation ratio")
    axes[0].set_title("Lower is better")
    axes[1].plot(
        x,
        ess_unbiased,
        "o-",
        color=colors["unbiased"],
        label="neural / unbiased",
    )
    axes[1].plot(
        x,
        ess_linear,
        "s--",
        color=colors["linear"],
        label="neural / linear",
    )
    axes[1].axhline(1.0, color="#333333", linewidth=0.8)
    axes[1].axhline(0.90, color=colors["linear"], linewidth=0.8, linestyle=":")
    axes[1].set_ylabel("ESS per second ratio")
    axes[1].set_title("Higher is better")
    for axis in axes:
        axis.set_xticks(x, labels, rotation=25, ha="right")
        axis.set_xlabel("Formal seed bundle")
        axis.spines[["top", "right"]].set_visible(False)
        axis.legend(frameon=False, fontsize=8)
    png = output / "paired_seed_ratios.png"
    pdf = output / "paired_seed_ratios.pdf"
    figure.savefig(png, dpi=300)
    figure.savefig(pdf)
    plt.close(figure)
    return png, pdf


def _plot_arm_means(
    chain_rows: Sequence[dict[str, Any]],
    output: Path,
) -> tuple[Path, Path]:
    arms = ("neural", "linear", "unbiased")
    tau = [
        np.mean([float(row["tau_int"]) for row in chain_rows if row["arm"] == arm])
        for arm in arms
    ]
    ess = [
        np.mean(
            [float(row["ess_per_second"]) for row in chain_rows if row["arm"] == arm]
        )
        for arm in arms
    ]
    colors = ["#009E73", "#D55E00", "#0072B2"]
    figure, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), constrained_layout=True)
    axes[0].bar(arms, tau, color=colors)
    axes[0].set_ylabel("Mean integrated autocorrelation")
    axes[0].set_title("Autocorrelation")
    axes[1].bar(arms, ess, color=colors)
    axes[1].set_ylabel("Mean ESS per second")
    axes[1].set_title("Sampling efficiency")
    for axis in axes:
        axis.spines[["top", "right"]].set_visible(False)
    png = output / "three_arm_means.png"
    pdf = output / "three_arm_means.pdf"
    figure.savefig(png, dpi=300)
    figure.savefig(pdf)
    plt.close(figure)
    return png, pdf


def build_issue28_report(
    root: str | Path,
    protocol: Any,
    *,
    output: str | Path | None = None,
    bootstrap_replicates: int = 20_000,
) -> dict[str, Any]:
    """Validate five N4 bundles and publish the N5 paired report."""
    from vmcrg_ref.artifacts import atomic_write_json, sha256_file
    from vmcrg_ref.formal import classify_formal_root
    from vmcrg_ref.issue28_workflow import create_stage_manifest

    formal_root = Path(root).resolve()
    destination = (
        Path(output).resolve() if output is not None else formal_root.parent / "N5"
    )
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise FileExistsError(f"refusing to overwrite N5 report: {destination}")
    if bootstrap_replicates < 1000:
        raise ValueError("N5 bootstrap requires at least 1000 replicates")
    destination.mkdir(parents=True, exist_ok=True)
    formal = classify_formal_root(formal_root, protocol)
    expected_ids = [bundle.bundle_id for bundle in protocol.formal_bundles]
    if formal["missing_bundles"] or formal["extra_bundles"]:
        raise ValueError("N5 requires exactly the five preregistered formal bundles")

    seed_rows: list[dict[str, Any]] = []
    chain_rows: list[dict[str, Any]] = []
    objective_identifiable = True
    tau_neural: list[np.ndarray] = []
    tau_linear: list[np.ndarray] = []
    tau_unbiased: list[np.ndarray] = []
    ess_neural: list[np.ndarray] = []
    ess_linear: list[np.ndarray] = []
    ess_unbiased: list[np.ndarray] = []
    predecessor_hashes: list[str] = []
    for bundle_id in expected_ids:
        bundle = formal_root / bundle_id
        result = _read_json(bundle / "bundle_result.json")
        autocorrelation = _read_json(
            bundle / "autocorrelation" / "autocorrelation.json"
        )
        predecessor_hashes.append(sha256_file(bundle / "manifest.json"))
        values: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for arm in ("neural", "linear", "unbiased"):
            arm_value = autocorrelation.get(arm)
            if not isinstance(arm_value, dict):
                raise ValueError(f"N5 autocorrelation arm is missing: {bundle_id}/{arm}")
            values[arm] = (
                _positive_vector(
                    arm_value.get("tau_int_by_chain"),
                    f"{bundle_id}/{arm}/tau",
                ),
                _positive_vector(
                    arm_value.get("ess_per_second_by_chain"),
                    f"{bundle_id}/{arm}/ess_per_second",
                ),
            )
        shapes = {array.shape for pair in values.values() for array in pair}
        if len(shapes) != 1:
            raise ValueError(f"N5 paired chain budgets differ for {bundle_id}")
        tn, en = values["neural"]
        tl, el = values["linear"]
        tu, eu = values["unbiased"]
        tau_neural.append(tn)
        tau_linear.append(tl)
        tau_unbiased.append(tu)
        ess_neural.append(en)
        ess_linear.append(el)
        ess_unbiased.append(eu)
        objective_classification = str(result.get("objective_classification", ""))
        objective_identifiable = objective_identifiable and (
            objective_classification == "IDENTIFIABLE"
        )
        seed_rows.append(
            {
                "bundle_id": bundle_id,
                "classification": str(result["classification"]),
                "objective_classification": objective_classification,
                "objective_delta_per_site": result.get("objective_delta_per_site", ""),
                "tau_neural_over_unbiased": float(tn.mean() / tu.mean()),
                "tau_neural_over_linear": float(tn.mean() / tl.mean()),
                "ess_neural_over_unbiased": float(en.mean() / eu.mean()),
                "ess_neural_over_linear": float(en.mean() / el.mean()),
            }
        )
        for chain in range(tn.size):
            for arm, tau_values, ess_values in (
                ("neural", tn, en),
                ("linear", tl, el),
                ("unbiased", tu, eu),
            ):
                chain_rows.append(
                    {
                        "bundle_id": bundle_id,
                        "chain": chain,
                        "arm": arm,
                        "tau_int": float(tau_values[chain]),
                        "ess_per_second": float(ess_values[chain]),
                    }
                )

    tau_n = np.stack(tau_neural)
    tau_l = np.stack(tau_linear)
    tau_u = np.stack(tau_unbiased)
    ess_n = np.stack(ess_neural)
    ess_l = np.stack(ess_linear)
    ess_u = np.stack(ess_unbiased)
    confidence = float(protocol.gates["confidence_level"])
    seed = int(protocol.formal_bundles[0].streams["bootstrap"].entropy)
    statistics = {
        "tau_neural_over_unbiased": _ratio_bootstrap(
            tau_n,
            tau_u,
            replicates=bootstrap_replicates,
            seed=seed,
            confidence=confidence,
        ),
        "tau_neural_over_linear": _ratio_bootstrap(
            tau_n,
            tau_l,
            replicates=bootstrap_replicates,
            seed=seed + 1,
            confidence=confidence,
        ),
        "ess_neural_over_unbiased": _ratio_bootstrap(
            ess_n,
            ess_u,
            replicates=bootstrap_replicates,
            seed=seed + 2,
            confidence=confidence,
        ),
        "ess_neural_over_linear": _ratio_bootstrap(
            ess_n,
            ess_l,
            replicates=bootstrap_replicates,
            seed=seed + 3,
            confidence=confidence,
        ),
    }
    tau_upper = float(protocol.gates["tau_linear_noninferiority_upper"])
    ess_lower = float(protocol.gates["ess_per_second_linear_noninferiority_lower"])
    aggregate_gates = {
        "objective_identifiable": objective_identifiable,
        "tau_improves_over_unbiased": statistics["tau_neural_over_unbiased"][
            "ci95_high_ratio"
        ]
        < 1.0,
        "tau_linear_noninferiority": statistics["tau_neural_over_linear"][
            "ci95_high_ratio"
        ]
        <= tau_upper,
        "ess_improves_over_unbiased": statistics["ess_neural_over_unbiased"][
            "ci95_low_ratio"
        ]
        > 1.0,
        "ess_linear_noninferiority": statistics["ess_neural_over_linear"][
            "ci95_low_ratio"
        ]
        >= ess_lower,
    }
    directional_counts = {
        "tau_improves_over_unbiased": sum(
            float(row["tau_neural_over_unbiased"]) < 1.0 for row in seed_rows
        ),
        "tau_linear_noninferiority": sum(
            float(row["tau_neural_over_linear"]) <= tau_upper for row in seed_rows
        ),
        "ess_improves_over_unbiased": sum(
            float(row["ess_neural_over_unbiased"]) > 1.0 for row in seed_rows
        ),
        "ess_linear_noninferiority": sum(
            float(row["ess_neural_over_linear"]) >= ess_lower for row in seed_rows
        ),
    }
    direction_gate = all(
        count >= int(protocol.gates["minimum_directional_seed_count"])
        for count in directional_counts.values()
    )
    if formal["classification"] in ("CORRECTNESS_FAILURE", "PROTOCOL_FAILURE"):
        classification = formal["classification"]
    elif (
        formal["classification"] == "EASY_GOAL_SUCCESS"
        and all(aggregate_gates.values())
        and direction_gate
    ):
        classification = "EASY_GOAL_SUCCESS"
    else:
        classification = "SCIENTIFIC_NEGATIVE"

    seed_csv = destination / "paired_seed_metrics.csv"
    chain_csv = destination / "autocorrelation_chains.csv"
    _atomic_csv(seed_csv, tuple(seed_rows[0]), seed_rows)
    _atomic_csv(chain_csv, tuple(chain_rows[0]), chain_rows)
    ratios_png, ratios_pdf = _plot_seed_ratios(seed_rows, destination)
    arms_png, arms_pdf = _plot_arm_means(chain_rows, destination)
    figures = [
        {
            "name": "paired_seed_ratios",
            "source_csv": str(seed_csv),
            "png": str(ratios_png),
            "pdf": str(ratios_pdf),
        },
        {
            "name": "three_arm_means",
            "source_csv": str(chain_csv),
            "png": str(arms_png),
            "pdf": str(arms_pdf),
        },
    ]
    verdict_style = "good" if classification == "EASY_GOAL_SUCCESS" else "warn"
    document: dict[str, Any] = {
        "schema_version": 1,
        "stage": "N5",
        "title": "Issue #28 Pure-Neural VMCRG Easy Goal",
        "eyebrow": "Five seeds, five neural-to-neural RG rounds",
        "lede": (
            "Periodic 45 x 45 Ising model at K=0.436 with 3 x 3 majority "
            "blocking; MPS results are excluded from all success gates."
        ),
        "classification": classification,
        "formal_seed_count": 5,
        "formal_rounds": int(protocol.formal_rounds),
        "formal_classification": formal["classification"],
        "statistics": statistics,
        "aggregate_gates": aggregate_gates,
        "directional_seed_counts": directional_counts,
        "minimum_directional_seed_count": int(
            protocol.gates["minimum_directional_seed_count"]
        ),
        "postformal_seed_extension_allowed": False,
        "failed_seed_replacement_allowed": False,
        "valid_negative_outcome": (
            "direction_correct_but_confidence_interval_misses_frozen_gate"
        ),
        "bundles": seed_rows,
        "figures": figures,
        "sections": [
            {
                "title": "Final classification",
                "blocks": [
                    {
                        "kind": "verdict",
                        "status": verdict_style,
                        "label": classification,
                        "why": (
                            "All frozen gates and paired confidence intervals passed."
                            if classification == "EASY_GOAL_SUCCESS"
                            else "At least one frozen correctness, protocol, or scientific gate did not pass."
                        ),
                    },
                    {
                        "kind": "kv",
                        "pairs": {
                            "Lattice": "45 x 45 periodic Ising",
                            "Coupling": "K = 0.436",
                            "Blocking": "3 x 3 majority",
                            "Formal evidence": "5 seed bundles x 5 dependent rounds",
                            "Bootstrap": "seed bundle, then independent chain",
                        },
                    },
                ],
            },
            {
                "title": "Paired sampling endpoints",
                "blocks": [
                    {
                        "kind": "figures",
                        "items": [
                            {
                                "src": ratios_png.name,
                                "caption": (
                                    "Paired seed-level neural-to-unbiased and neural-to-linear ratios. "
                                    "Dotted lines show the frozen non-inferiority bounds."
                                ),
                            },
                            {
                                "src": arms_png.name,
                                "caption": (
                                    "Three-arm chain means for autocorrelation and effective samples per second. "
                                    "All values come from independent formal chain streams."
                                ),
                            },
                        ],
                    },
                    {
                        "kind": "table",
                        "columns": [
                            "Seed",
                            "Classification",
                            "tau neural/linear",
                            "ESS/s neural/linear",
                        ],
                        "rows": [
                            [
                                row["bundle_id"],
                                row["classification"],
                                f"{float(row['tau_neural_over_linear']):.4f}",
                                f"{float(row['ess_neural_over_linear']):.4f}",
                            ]
                            for row in seed_rows
                        ],
                    },
                ],
            },
            {
                "title": "Provenance and scope",
                "blocks": [
                    {
                        "kind": "list",
                        "items": [
                            "The 13-operator branch is required to remain exactly zero in every neural round.",
                            "No failed formal seed is replaced and no post-formal seed is added.",
                            "MPS code and results remain an optional appendix and do not enter Issue #28 gates.",
                            "Every plotted figure has an exact CSV source table in this directory.",
                        ],
                    }
                ],
            },
        ],
    }
    atomic_write_json(destination / "report.json", document)
    subprocess.run(
        [sys.executable, str(REPORT_RENDERER), str(destination)],
        check=True,
        cwd=REPO_ROOT,
    )
    outputs = tuple(
        path.relative_to(destination).as_posix()
        for path in sorted(destination.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    )
    manifest = create_stage_manifest(
        stage="N5",
        protocol=protocol,
        classification=classification,
        reason=(
            "FIVE_SEED_PAIRED_GATES_PASS"
            if classification == "EASY_GOAL_SUCCESS"
            else "N5_TERMINAL_CLASSIFICATION"
        ),
        output_root=destination,
        outputs=outputs,
        correctness_gates={
            "five_formal_bundles": "PASS",
            "paired_chain_budgets": "PASS",
            "figure_source_tables": "PASS",
        },
        scientific_gates={
            **{
                key: "PASS" if value else "FAIL"
                for key, value in aggregate_gates.items()
            },
            "minimum_directional_seed_count": "PASS" if direction_gate else "FAIL",
        },
        resources={
            "backend": "local_analysis",
            "bootstrap_replicates": int(bootstrap_replicates),
            "formal_seed_count": 5,
        },
        predecessor_manifest_sha256=predecessor_hashes,
        round_index=protocol.formal_rounds,
    )
    manifest["scope"] = "N5_FINAL_REPORT"
    atomic_write_json(destination / "manifest.json", manifest)
    return document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the Issue #28 N5 report")
    parser.add_argument("--root", type=Path, required=True, help="N4 cells directory")
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("config/issue28_formal_v1.json"),
        help="Frozen Issue #28 formal protocol",
    )
    parser.add_argument("--output", type=Path, required=True, help="New N5 output directory")
    parser.add_argument("--bootstrap-replicates", type=int, default=20_000)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    from vmcrg_ref.issue28_protocol import load_issue28_protocol

    args = build_parser().parse_args(argv)
    report = build_issue28_report(
        args.root,
        load_issue28_protocol(args.protocol),
        output=args.output,
        bootstrap_replicates=args.bootstrap_replicates,
    )
    print(
        f"N5 report complete: {report['classification']} -> {args.output / 'report.html'}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
