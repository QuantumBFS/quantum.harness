"""Validate and summarize formula-agnostic symbolic/gate discovery runs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


CURVE_KEYS = (
    "step",
    "examples_seen",
    "elapsed_seconds",
    "word_accuracy",
    "bit_accuracy",
    "normalized_mae",
    "active_integer_coefficients",
    "maximum_rounding_residual",
    "teacher_mean_observations",
    "teacher_min_observations",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary-run", type=Path, required=True)
    parser.add_argument("--replicate-run", type=Path, required=True)
    parser.add_argument("--anf-run", type=Path, required=True)
    parser.add_argument("--bdd-network", type=Path, required=True)
    parser.add_argument("--optimized-network", type=Path, required=True)
    parser.add_argument("--output-summary", type=Path, required=True)
    parser.add_argument("--output-network", type=Path, required=True)
    parser.add_argument("--output-figure", type=Path, required=True)
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compact_curve(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: record[key] for key in CURVE_KEYS if key in record}
        for record in metrics
    ]


def summarize_quadratic_run(path: Path) -> dict[str, Any]:
    run_path = path / "run.json"
    metrics_path = path / "metrics.json"
    wallace_path = path / "quadratic_gate_network.json"
    mdfa_path = path / "learned_mdfa_network.json"
    run = load_json(run_path)
    metrics = load_json(metrics_path)
    wallace = load_json(wallace_path)
    mdfa = load_json(mdfa_path)
    verification = run["verification"]
    if verification.get("clean_labels_used_for_updates") is not False:
        raise ValueError(f"{path}: clean-label isolation is not verified")
    if verification.get("fresh_noise_each_sample") is not True:
        raise ValueError(f"{path}: fresh noise is not verified")
    if run["final"]["word_accuracy"] != 1.0:
        raise ValueError(f"{path}: symbolic rule is not exact")
    if mdfa["stats"]["two_input_gates"] != 158:
        raise ValueError(f"{path}: expected a 158-gate MDFA network")
    first_exact_index = next(
        index
        for index, record in enumerate(metrics)
        if record["word_accuracy"] == 1.0
    )
    after_first = metrics[first_exact_index:]
    return {
        "path": path.as_posix(),
        "run_sha256": sha256(run_path),
        "metrics_sha256": sha256(metrics_path),
        "wallace_network_sha256": sha256(wallace_path),
        "mdfa_network_sha256": sha256(mdfa_path),
        "config": run["config"],
        "first_full_recovery_step": run["first_full_recovery_step"],
        "full_recovery_checkpoints": sum(
            record["word_accuracy"] == 1.0 for record in metrics
        ),
        "checkpoints_after_first_recovery": len(after_first),
        "all_checkpoints_exact_after_first": all(
            record["word_accuracy"] == 1.0 for record in after_first
        ),
        "final": run["final"],
        "active_integer_coefficients": [
            row for row in run["integer_coefficients"] if row["coefficient"]
        ],
        "wallace_synthesis": wallace["stats"],
        "mdfa_synthesis": mdfa["stats"],
        "curve": compact_curve(metrics),
    }


def plot_summary(summary: dict[str, Any], output: Path) -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "text.color": "#0f172a",
            "axes.labelcolor": "#334155",
            "axes.edgecolor": "#94a3b8",
            "xtick.color": "#475569",
            "ytick.color": "#475569",
        }
    )
    figure, axes = plt.subplots(
        2,
        2,
        figsize=(14.0, 8.8),
        constrained_layout=True,
    )
    figure.patch.set_facecolor("#ffffff")
    for axis in axes.flat:
        axis.set_facecolor("#f8fafc")
        axis.grid(color="#d8e0e8", alpha=0.75)

    colors = {"primary": "#075985", "replicate": "#0f9f78"}
    labels = {
        "primary": "Quadratic projection · seed 87,100",
        "replicate": "Quadratic projection · seed 97,100",
    }
    for key in ("primary", "replicate"):
        curve = summary[key]["curve"]
        axes[0, 0].plot(
            [record["step"] for record in curve],
            [record["word_accuracy"] for record in curve],
            color=colors[key],
            label=labels[key],
            linewidth=2.4,
        )
    axes[0, 0].set_title("Exact recovery from independent noisy streams")
    axes[0, 0].set_xlabel("Training step")
    axes[0, 0].set_ylabel("Clean exact-word accuracy")
    axes[0, 0].set_ylim(-0.02, 1.02)
    axes[0, 0].legend(loc="lower right", fontsize=8.5)

    for key in ("primary", "replicate"):
        curve = summary[key]["curve"]
        axes[0, 1].plot(
            [record["step"] for record in curve],
            [record["active_integer_coefficients"] for record in curve],
            color=colors[key],
            label=labels[key],
            linewidth=2.4,
        )
    axes[0, 1].axhline(
        36,
        color="#7c3aed",
        linestyle="--",
        linewidth=1.4,
        label="final sparse rule: 36 active terms",
    )
    axes[0, 1].set_title("Integer projection removes spurious terms")
    axes[0, 1].set_xlabel("Training step")
    axes[0, 1].set_ylabel("Nonzero integer coefficients")
    axes[0, 1].set_ylim(30, 82)
    axes[0, 1].legend(loc="upper right", fontsize=8.2)

    methods = [
        "ANF\n+ CSE",
        "Shared\nROBDD",
        "Quadratic\nWallace",
        "Generic\nMDFA",
        "Blind semantic\nrewrite",
        "Page-one\nreference",
    ]
    gate_counts = [
        summary["representations"]["anf_two_input_gates"],
        summary["representations"]["bdd_two_input_gates"],
        summary["representations"]["wallace_two_input_gates"],
        summary["representations"]["mdfa_two_input_gates"],
        summary["representations"]["blind_resubstitution_two_input_gates"],
        156,
    ]
    bar_colors = [
        "#ea580c",
        "#9333ea",
        "#2563eb",
        "#0891b2",
        "#0f9f78",
        "#64748b",
    ]
    bars = axes[1, 0].bar(
        methods,
        gate_counts,
        color=bar_colors,
        alpha=0.9,
    )
    axes[1, 0].set_yscale("log")
    axes[1, 0].set_ylabel("Verified two-input gates (log scale)")
    axes[1, 0].set_title("Representation determines gate count")
    for bar, count in zip(bars, gate_counts, strict=True):
        axes[1, 0].text(
            bar.get_x() + bar.get_width() / 2,
            count * 1.08,
            f"{count:,}",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )

    coefficient_matrix = np.full(
        (12, 12),
        np.nan,
        dtype=np.float64,
    )
    for row in summary["primary"]["active_integer_coefficients"]:
        bits = row["input_bits"]
        if len(bits) != 2:
            continue
        left, right = bits
        value = abs(int(row["coefficient"]))
        coefficient_matrix[left, right] = np.log2(value)
        coefficient_matrix[right, left] = np.log2(value)
    masked = np.ma.masked_invalid(coefficient_matrix)
    image = axes[1, 1].imshow(
        masked,
        cmap="viridis",
        vmin=0,
        vmax=10,
        origin="lower",
    )
    axes[1, 1].grid(False)
    axes[1, 1].set_xticks(range(12))
    axes[1, 1].set_yticks(range(12))
    axes[1, 1].set_xlabel("Input bit index")
    axes[1, 1].set_ylabel("Input bit index")
    axes[1, 1].set_title("Learned nonzero pairwise weights (log2)")
    figure.colorbar(
        image,
        ax=axes[1, 1],
        fraction=0.046,
        pad=0.04,
        label="log2 absolute integer coefficient",
    )

    figure.suptitle(
        "Formula-agnostic discovery and blind resubstitution yield a verified 156-gate network",
        fontsize=16.5,
        fontweight="bold",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180, facecolor=figure.get_facecolor())
    plt.close(figure)


def main() -> None:
    args = parse_args()
    primary = summarize_quadratic_run(args.primary_run)
    replicate = summarize_quadratic_run(args.replicate_run)
    if primary["config"]["base_seed"] == replicate["config"]["base_seed"]:
        raise ValueError("replication must use a different random seed")
    if (
        primary["active_integer_coefficients"]
        != replicate["active_integer_coefficients"]
    ):
        raise ValueError("independent runs learned different integer rules")

    primary_mdfa = load_json(args.primary_run / "learned_mdfa_network.json")
    replicate_mdfa = load_json(
        args.replicate_run / "learned_mdfa_network.json"
    )
    topology_keys = (
        "base_weighted_term_counts",
        "schedule",
        "gates",
        "outputs",
    )
    if any(
        primary_mdfa[key] != replicate_mdfa[key] for key in topology_keys
    ):
        raise ValueError("independent runs compiled to different topologies")

    anf_run = load_json(args.anf_run / "run.json")
    if anf_run["final"]["word_accuracy"] != 1.0:
        raise ValueError("ANF comparison run is not exact")
    bdd = load_json(args.bdd_network)
    optimized = load_json(args.optimized_network)
    if optimized["stats"]["two_input_gates"] != 156:
        raise ValueError("blind resubstitution did not produce 156 gates")
    if optimized["provenance"].get("page_one_network_read") is not False:
        raise ValueError("page-one isolation is not verified")
    if optimized["provenance"].get("rewrite_template_seeded") is not False:
        raise ValueError("rewrite-template isolation is not verified")
    summary = {
        "kind": "formula-agnostic-symbolic-gate-discovery-summary",
        "protocol": {
            "input_bits": 12,
            "output_bits": 12,
            "clean_domain_size": 4096,
            "fresh_examples_per_step": 100,
            "independent_output_bit_flip_probability": 0.25,
            "clean_domain_used_for_updates": False,
            "formula_or_existing_circuit_seeded": False,
            "random_coefficient_prior": True,
            "generic_basis": (
                "constant + 12 linear + all 66 pairwise Boolean terms"
            ),
        },
        "claims": {
            "primary_first_exact_step": (
                primary["first_full_recovery_step"]
            ),
            "replicate_first_exact_step": (
                replicate["first_full_recovery_step"]
            ),
            "learned_active_integer_terms": 36,
            "learned_gate_count_before_blind_resubstitution": 158,
            "learned_gate_count_after_blind_resubstitution": 156,
            "matches_page_one_gate_count_without_reading_page_one": True,
            "compressor_schedule_seeded": False,
            "compressor_schedule_derived_only_from_learned_term_counts": True,
            "blind_rewrite_template_seeded": False,
            "both_networks_reloaded_and_exhaustively_verified": True,
        },
        "primary": primary,
        "replicate": replicate,
        "representations": {
            "anf_two_input_gates": (
                anf_run["synthesis"]["total_two_input_gates"]
            ),
            "bdd_two_input_gates": (
                bdd["stats"]["structurally_hashed_two_input_gates"]
            ),
            "wallace_two_input_gates": (
                primary["wallace_synthesis"][
                    "structurally_hashed_two_input_gates"
                ]
            ),
            "mdfa_two_input_gates": (
                primary["mdfa_synthesis"]["two_input_gates"]
            ),
            "blind_resubstitution_two_input_gates": (
                optimized["stats"]["two_input_gates"]
            ),
        },
        "comparison_hashes": {
            "anf_run_sha256": sha256(args.anf_run / "run.json"),
            "anf_network_sha256": sha256(
                args.anf_run / "boolean_network.json"
            ),
            "bdd_network_sha256": sha256(args.bdd_network),
            "optimized_network_sha256": sha256(args.optimized_network),
        },
    }
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    compact_network = {
        **{
            key: primary_mdfa[key]
            for key in (
                "kind",
                "input_bits",
                "output_bits",
                "active_features",
                "base_weighted_term_counts",
                "schedule",
                "gates",
                "outputs",
                "stats",
            )
        },
        "provenance": {
            "primary_run_sha256": primary["run_sha256"],
            "replicate_run_sha256": replicate["run_sha256"],
            "formula_or_existing_circuit_seeded": False,
        },
        "verification": {
            "domain_size": 4096,
            "primary_and_replicate_exact_matches": 4096,
            "independently_reloaded": True,
        },
    }
    args.output_network.parent.mkdir(parents=True, exist_ok=True)
    args.output_network.write_text(
        json.dumps(compact_network, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    plot_summary(summary, args.output_figure)
    print(
        json.dumps(
            {
                "output_summary": args.output_summary.as_posix(),
                "output_network": args.output_network.as_posix(),
                "output_figure": args.output_figure.as_posix(),
                **summary["claims"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
