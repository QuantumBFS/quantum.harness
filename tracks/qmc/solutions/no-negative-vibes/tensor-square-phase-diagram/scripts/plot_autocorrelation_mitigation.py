#!/usr/bin/env python3
"""Render the pre-registered autocorrelation-mitigation gate evidence."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt

from tensor_square.stage4 import MONITORED_TAU_KEYS


def _write_replica_audit(results_dir: Path, output_path: Path) -> None:
    rows = []
    for path in sorted(results_dir.glob("chains/*/replica_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        worst_key = max(
            MONITORED_TAU_KEYS, key=lambda key: float(payload[key])
        )
        rows.append(
            {
                "arm": payload["arm"],
                "replica": payload["replica"],
                "seed": payload["seed"],
                "source_revision": payload["source_revision"],
                "run_fingerprint": payload["run_fingerprint"],
                "acceptance": payload["acceptance"],
                "temporal_block_acceptance": payload[
                    "temporal_block_acceptance"
                ],
                "direct_sign_min": payload["direct_sign_min"],
                "weight_log_error_max": payload["weight_log_error_max"],
                "density_min": payload["density_min"],
                "density_max": payload["density_max"],
                "energy_mean": payload["energy_mean"],
                "energy_stderr": payload["energy_stderr"],
                "q_combined_mean": payload["q_combined_mean"],
                "q_combined_stderr": payload["q_combined_stderr"],
                "worst_tau_key": worst_key,
                "worst_tau_int": payload[worst_key],
                "cpu_seconds": payload["cpu_seconds"],
                "wall_seconds": payload["wall_seconds"],
            }
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _save(fig: plt.Figure, base: Path) -> None:
    fig.savefig(base.with_suffix(".png"), dpi=220, bbox_inches="tight")
    fig.savefig(base.with_suffix(".pdf"), bbox_inches="tight")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    aggregate = json.loads(
        (args.results_dir / "aggregate.json").read_text(encoding="utf-8")
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_replica_audit(
        args.results_dir, args.output_dir / "m3_replica_audit.csv"
    )

    arms = ("control", "temporal_block")
    labels = ("local control", "temporal block")
    colors = ("#4C78A8", "#F58518")
    figure, axes = plt.subplots(1, 3, figsize=(11.0, 3.4))
    for axis, metric, label in (
        (axes[0], "energy", "Energy"),
        (axes[1], "q_combined", r"$Q_{\rm combined}$"),
    ):
        means = [
            float(aggregate["arms"][arm][metric]["mean"]) for arm in arms
        ]
        errors = [
            float(aggregate["arms"][arm][metric]["stderr"]) for arm in arms
        ]
        for index, (mean, error, color) in enumerate(
            zip(means, errors, colors, strict=True)
        ):
            axis.errorbar(
                [index],
                [mean],
                yerr=[error],
                fmt="o",
                color=color,
                ecolor=color,
                capsize=4,
                markersize=5,
            )
        exact = float(
            aggregate["ed_checks"]["control"][metric]["exact"]
        )
        axis.axhline(exact, color="#54A24B", linestyle="--", label="ED")
        axis.set_xticks(range(2), labels, rotation=18)
        axis.set_ylabel(label)
        axis.grid(alpha=0.2)
    axes[0].legend(frameon=False)

    tau = [
        float(aggregate["arms"][arm]["worst_tau_median"]) for arm in arms
    ]
    axes[2].bar(range(2), tau, color=colors, alpha=0.85)
    axes[2].set_xticks(range(2), labels, rotation=18)
    axes[2].set_ylabel("median worst $\\tau_{\\mathrm{int}}$")
    axes[2].grid(axis="y", alpha=0.2)
    decision = aggregate["decision"]
    figure.suptitle(
        f"m=3 sampler gate: {decision['status']} — {decision['reason']}",
        fontsize=10,
    )
    _save(figure, args.output_dir / "m3_sampler_gate")
    plt.close(figure)

    block_energy = aggregate["ed_checks"]["temporal_block"]["energy"]
    control_tau = float(aggregate["arms"]["control"]["worst_tau_median"])
    block_tau = float(
        aggregate["arms"]["temporal_block"]["worst_tau_median"]
    )
    lines = [
        "# m=3 temporal-block sampler gate",
        "",
        f"- Decision: **{decision['status']}**.",
        f"- Reason: {decision['reason']}.",
        (
            "- Temporal-block energy vs ED: "
            f"`|z|={float(block_energy['absolute_z']):.3f}` "
            "(frozen limit `3.0`)."
        ),
        (
            "- Median worst autocorrelation: "
            f"control `{control_tau:.3f}`, block `{block_tau:.3f}` "
            f"({100.0 * (1.0 - block_tau / control_tau):.1f}% reduction)."
        ),
        (
            "- Numerical audits: control "
            f"`{aggregate['numerical_audit']['control']}`, block "
            f"`{aggregate['numerical_audit']['temporal_block']}`."
        ),
        (
            "- Consequence: the mandatory m=3 gate blocks the Stage 4 "
            "m=8 A/B run. No scale, seed, or budget was changed."
        ),
    ]
    (args.output_dir / "m3_sampler_gate.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
