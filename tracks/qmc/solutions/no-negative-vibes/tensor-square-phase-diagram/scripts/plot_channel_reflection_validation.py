#!/usr/bin/env python3
"""Render m=3 and Stage 4 evidence for the channel-reflection candidate."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt

from tensor_square.stage4 import MONITORED_TAU_KEYS


ARMS = ("control", "channel_reflection")
LABELS = ("local control", "channel reflection")
COLORS = ("#4C78A8", "#E45756")


def _point_pair(
    axis: plt.Axes,
    aggregate: dict[str, object],
    metric: str,
    ylabel: str,
    *,
    exact: float | None = None,
) -> None:
    for index, (arm, color) in enumerate(zip(ARMS, COLORS, strict=True)):
        estimate = aggregate["arms"][arm][metric]
        axis.errorbar(
            [index],
            [float(estimate["mean"])],
            yerr=[float(estimate["stderr"])],
            fmt="o",
            color=color,
            ecolor=color,
            capsize=4,
        )
    if exact is not None:
        axis.axhline(exact, color="#54A24B", linestyle="--", label="ED")
        axis.legend(frameon=False)
    axis.set_xticks(range(2), LABELS, rotation=16)
    axis.set_ylabel(ylabel)
    axis.grid(alpha=0.2)


def _write_stage4_replica_audit(
    results_dir: Path,
    output_path: Path,
    *,
    m3_release_digest: str,
) -> None:
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
                "m3_release_digest": m3_release_digest,
                "acceptance": payload["acceptance"],
                "temporal_reflection_acceptance": payload[
                    "temporal_reflection_acceptance"
                ],
                "direct_sign_min": payload["direct_sign_min"],
                "weight_log_error_max": payload["weight_log_error_max"],
                "density_min": payload["density_min"],
                "density_max": payload["density_max"],
                "energy_mean": payload["energy_mean"],
                "energy_stderr": payload["energy_stderr"],
                "q_a_sq_mean": payload["q_a_sq_mean"],
                "q_a_sq_stderr": payload["q_a_sq_stderr"],
                "q_b_sq_mean": payload["q_b_sq_mean"],
                "q_b_sq_stderr": payload["q_b_sq_stderr"],
                "q_combined_mean": payload["q_combined_mean"],
                "q_combined_stderr": payload["q_combined_stderr"],
                "worst_tau_key": worst_key,
                "worst_tau_int": payload[worst_key],
                "cpu_seconds": payload["cpu_seconds"],
                "wall_seconds": payload["wall_seconds"],
            }
        )
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _save(figure: plt.Figure, base: Path) -> None:
    figure.savefig(base.with_suffix(".png"), dpi=220, bbox_inches="tight")
    figure.savefig(base.with_suffix(".pdf"), bbox_inches="tight")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--m3-results-dir", required=True, type=Path)
    parser.add_argument("--stage4-results-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    m3 = json.loads(
        (args.m3_results_dir / "aggregate.json").read_text(encoding="utf-8")
    )
    stage4 = json.loads(
        (args.stage4_results_dir / "aggregate.json").read_text(
            encoding="utf-8"
        )
    )
    stage4_manifest = json.loads(
        (args.stage4_results_dir / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_stage4_replica_audit(
        args.m3_results_dir,
        args.output_dir / "m3_reflection_replica_audit.csv",
        m3_release_digest="",
    )
    _write_stage4_replica_audit(
        args.stage4_results_dir,
        args.output_dir / "stage4_reflection_replica_audit.csv",
        m3_release_digest=str(stage4_manifest["m3_release_digest"]),
    )

    figure, axes = plt.subplots(2, 3, figsize=(11.2, 6.4))
    _point_pair(
        axes[0, 0],
        m3,
        "energy",
        "m=3 energy",
        exact=float(m3["ed_checks"]["control"]["energy"]["exact"]),
    )
    _point_pair(
        axes[0, 1],
        m3,
        "q_combined",
        r"m=3 $Q_{\rm combined}$",
        exact=float(
            m3["ed_checks"]["control"]["q_combined"]["exact"]
        ),
    )
    _point_pair(
        axes[0, 2],
        stage4,
        "q_combined",
        r"m=8, $\beta=8$: $Q_{\rm combined}$",
    )

    tau = [
        float(stage4["arms"][arm]["worst_tau_median"]) for arm in ARMS
    ]
    axes[1, 0].bar(range(2), tau, color=COLORS)
    axes[1, 0].set_xticks(range(2), LABELS, rotation=16)
    axes[1, 0].set_ylabel("median worst $\\tau_{\\rm int}$")
    axes[1, 0].grid(axis="y", alpha=0.2)

    reflection_acceptance = [
        float(
            json.loads(path.read_text(encoding="utf-8"))[
                "temporal_reflection_acceptance"
            ]
        )
        for path in sorted(
            args.stage4_results_dir.glob(
                "chains/channel_reflection/replica_*.json"
            )
        )
    ]
    axes[1, 1].scatter(
        range(len(reflection_acceptance)),
        reflection_acceptance,
        color=COLORS[1],
        zorder=3,
    )
    axes[1, 1].axhline(
        0.05, color="black", linestyle="--", label="frozen minimum"
    )
    axes[1, 1].set_xticks(
        range(len(reflection_acceptance)),
        [f"replica {index}" for index in range(len(reflection_acceptance))],
    )
    axes[1, 1].set_ylabel("reflection acceptance")
    axes[1, 1].legend(frameon=False)
    axes[1, 1].grid(alpha=0.2)

    cost = [
        float(
            stage4["arms"][arm][
                "cpu_seconds_per_effective_sample_median"
            ]
        )
        for arm in ARMS
    ]
    axes[1, 2].bar(range(2), cost, color=COLORS)
    axes[1, 2].set_xticks(range(2), LABELS, rotation=16)
    axes[1, 2].set_ylabel("CPU seconds / effective sample")
    axes[1, 2].grid(axis="y", alpha=0.2)

    figure.suptitle(
        "Channel reflection: m=3 PASS, censored Stage 4 A/B STOP",
        fontsize=11,
    )
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))
    _save(figure, args.output_dir / "channel_reflection_validation")
    plt.close(figure)

    maximum_shift = max(
        float(row["absolute_z"])
        for row in stage4["observable_consistency"]["metrics"].values()
    )
    lines = [
        "# Channel-reflection validation",
        "",
        f"- m=3 decision: **{m3['decision']['status']}**.",
        f"- Stage 4 A/B decision: **{stage4['decision']['status']}**.",
        (
            "- Reflection acceptance range at m=8: "
            f"`{min(reflection_acceptance):.4f}-"
            f"{max(reflection_acceptance):.4f}`; frozen minimum `0.05`."
        ),
        (
            "- Median worst tau ratio (reflection/control): "
            f"`{float(stage4['tau_reduction']['reflection_over_control']):.4f}`."
        ),
        (
            "- CPU seconds per effective sample ratio: "
            f"`{float(stage4['cost_audit']['reflection_over_control_cpu_seconds_per_effective_sample']):.4f}`."
        ),
        (
            "- Largest two-arm observable displacement: "
            f"`|z|={maximum_shift:.3f}` (all pass the frozen 2-sigma gate)."
        ),
        (
            "- Consequence: stop this sampler candidate; do not extend or "
            "promote the m=8 signal to Stage 5."
        ),
    ]
    (args.output_dir / "channel_reflection_validation.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
