#!/usr/bin/env python3
"""Assemble the Phase 8 sigma=1.75 finite-size report."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from lrtfim.phase8_scaling import gap_scaling_summary


SIGMA = 1.75
SIZES = (16, 32, 64, 96, 128)
SECTORS = ("even", "odd")
K = 24
CHI = 128
PUBLISHED = {
    "authors": "Sora Shiratani and Synge Todo",
    "arxiv": "2305.14121v4",
    "url": "https://arxiv.org/abs/2305.14121",
    "table": 2,
    "sigma": 1.75,
    "Gamma_c": 1.5609,
    "Gamma_c_uncertainty": 0.0003,
    "z_power": 0.91,
    "z_power_uncertainty": 0.02,
    "z_log": 0.98,
    "z_log_uncertainty": 0.03,
    "L_max": 362,
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty table {path.name}")
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _load_states(root: Path, gamma: float) -> dict[tuple[int, str], dict]:
    states = {}
    for path in sorted(root.rglob("summary.json")):
        summary = _load(path)
        settings = summary.get("settings", {})
        sectors = settings.get("sectors", [])
        if len(sectors) != 1:
            continue
        key = (int(settings.get("length", -1)), sectors[0])
        if key not in {(length, sector) for length in SIZES for sector in SECTORS}:
            continue
        if key in states:
            raise ValueError(f"duplicate state summary for L={key[0]} {key[1]}")
        _validate_state(summary, length=key[0], sector=key[1], gamma=gamma)
        states[key] = summary
    expected = {(length, sector) for length in SIZES for sector in SECTORS}
    missing = sorted(expected - set(states))
    if missing:
        raise ValueError(f"missing common-field summaries: {missing}")
    return states


def _validate_state(
    summary: dict,
    *,
    length: int,
    sector: str,
    gamma: float,
) -> None:
    if summary.get("status") != "success":
        raise ValueError(f"L={length} {sector} summary is not successful")
    settings = summary.get("settings", {})
    expected = {
        "sigma": SIGMA,
        "length": length,
        "gamma": gamma,
        "num_exponentials": K,
        "alpha": 0.5,
        "r_fit": 2048,
        "chi_schedule": [CHI],
        "sectors": [sector],
        "direct_only": True,
    }
    for field, value in expected.items():
        actual = settings.get(field)
        if isinstance(value, float):
            matches = actual is not None and np.isclose(float(actual), value)
        else:
            matches = actual == value
        if not matches:
            raise ValueError(
                f"L={length} {sector} {field} mismatch: "
                f"{actual!r} != {value!r}"
            )
    mpo = summary.get("mpo", {})
    if mpo.get("pruned") is not True:
        raise ValueError("exact-zero MPO pruning must be enabled")
    if mpo.get("approximate_compression") is not False:
        raise ValueError("approximate MPO compression must be disabled")

    state = summary.get("direct", {}).get(sector, {})
    energy = float(state.get("energy", np.nan))
    variance = float(state.get("variance", np.nan))
    discarded = float(state.get("discarded_weight", np.nan))
    sweeps = int(state.get("sweeps", -1))
    max_sweeps = int(settings.get("max_sweeps", -1))
    relative_variance = variance / max(energy * energy, 1.0)
    if not np.isfinite(relative_variance) or relative_variance > 1.0e-10:
        raise ValueError(f"L={length} {sector} relative variance failed")
    if not np.isfinite(discarded) or discarded > 1.0e-8:
        raise ValueError(f"L={length} {sector} discarded weight failed")
    if sweeps < 0 or max_sweeps <= 0 or sweeps >= max_sweeps:
        raise ValueError(f"L={length} {sector} sweep gate failed")


def _max_absolute(comparisons: list[dict], *path: str) -> float:
    values = []
    for comparison in comparisons:
        node = comparison
        for key in path:
            node = node[key]
        values.append(abs(float(node)))
    return max(values) if values else float("nan")


def _uncertainty_summary(phase6: dict, finite_spread: float) -> dict:
    mpo = phase6.get("mpo", {}).get("comparisons", [])
    mps = phase6.get("mps", {}).get("comparisons", [])
    return {
        "MPO": {
            "source": "Phase 6 K=24 to K=32 comparison",
            "max_abs_gap_shift": _max_absolute(mpo, "gap", "absolute"),
            "max_abs_R_xi_shift": _max_absolute(mpo, "r_xi", "absolute"),
        },
        "MPS": {
            "source": "Phase 6 chi=128 to chi=256 comparison",
            "max_abs_gap_shift": _max_absolute(mps, "gap", "absolute"),
            "max_abs_R_xi_shift": _max_absolute(mps, "r_xi", "absolute"),
        },
        "finite_size": {
            "source": "Phase 8 five-size correction-coordinate sensitivity",
            "z_power_log_spread": float(finite_spread),
        },
        "critical_field_propagation": {
            "status": "not_fully_propagated",
            "reason": "only two finite-size crossings are available",
        },
    }


def _rows_and_analysis(decision: dict, states: dict, phase6: dict) -> tuple:
    gamma = float(decision["common_field"]["gap_field"])
    crossings = [
        {
            "size_pair": "32_64",
            "Gamma_x": decision["Gamma_x_32_64"],
            "resolution": decision.get("crossing_resolution", np.nan),
        },
        {
            "size_pair": "64_128",
            "Gamma_x": decision["Gamma_x_64_128"],
            "resolution": decision["crossing_resolution"],
        },
    ]
    critical_rows = [
        {
            "coordinate": form,
            "Gamma_c_sensitivity": decision["common_field"][form]["estimate"],
            "residual_degrees_of_freedom": 0,
            "known_correction_exponent_assumed": False,
        }
        for form in ("power", "log")
    ]

    diagnostic_rows = []
    equal_time_rows = []
    gaps = []
    for length in SIZES:
        even = states[(length, "even")]
        odd = states[(length, "odd")]
        even_state = even["direct"]["even"]
        odd_state = odd["direct"]["odd"]
        gap = float(odd_state["energy"]) - float(even_state["energy"])
        if not np.isfinite(gap) or gap <= 0.0:
            raise ValueError(f"L={length} gap must be positive")
        gaps.append(gap)
        for sector, state in (("even", even_state), ("odd", odd_state)):
            diagnostic_rows.append(
                {
                    "L": length,
                    "sector": sector,
                    "Gamma": gamma,
                    "energy": state["energy"],
                    "variance": state["variance"],
                    "relative_variance": state["variance"]
                    / max(state["energy"] ** 2, 1.0),
                    "discarded_weight": state["discarded_weight"],
                    "requested_chi": state["requested_chi"],
                    "reached_chi": state["reached_chi"],
                    "sweeps": state["sweeps"],
                    "wall_seconds": state["wall_seconds"],
                    "gap": gap,
                }
            )
        raw = even["raw_observables"]
        equal_time_rows.append(
            {
                "L": length,
                "S_eq_zero": raw["s_zero"],
                "S_k_min": raw["s_k_min"],
                "xi": raw["xi"],
                "R_xi": raw["r_xi"],
                "role": "auxiliary_diagnostic",
            }
        )

    z = gap_scaling_summary(SIZES, gaps)
    z_rows = [
        {
            "quantity": f"z_eff_{pair}",
            "value": value,
            "role": "adjacent_size_diagnostic",
        }
        for pair, value in zip(z["z_eff"]["pairs"], z["z_eff"]["values"])
    ]
    for form in ("power", "log"):
        z_rows.append(
            {
                "quantity": f"z_{form}",
                "value": z["regression"][form]["estimate"],
                "role": "five_size_sensitivity_regression",
            }
        )
        z_rows.append(
            {
                "quantity": f"z_{form}_leave_L16_out",
                "value": z["regression"]["leave_L16_out"][form]["estimate"],
                "role": "leave_smallest_size_sensitivity",
            }
        )
    uncertainty = _uncertainty_summary(
        phase6,
        z["regression"]["spread"],
    )
    analysis = {
        "sigma": SIGMA,
        "critical_field": decision["common_field"],
        "crossings": crossings,
        "gaps": dict(zip((str(length) for length in SIZES), gaps)),
        "z": z,
        "published_comparison": PUBLISHED,
        "susceptibility_gamma_over_nu": "not_measured",
        "equal_time_structure_factor": {
            "role": "auxiliary_diagnostic",
            "susceptibility_exponent_claimed": False,
            "rows": equal_time_rows,
        },
        "uncertainty": uncertainty,
        "limitations": [
            "maximum size is L=128",
            "published QMC comparison reaches L=362",
            "critical-field power/log sensitivity is not fully propagated into gaps",
            "susceptibility gamma/nu is outside the DMRG scope",
        ],
    }
    return (
        crossings,
        critical_rows,
        diagnostic_rows,
        z_rows,
        equal_time_rows,
        uncertainty,
        analysis,
    )


def _plot(output: Path, analysis: dict) -> None:
    crossings = analysis["crossings"]
    z = analysis["z"]
    gaps = np.array([analysis["gaps"][str(length)] for length in SIZES])
    blue, orange, green = "#0072B2", "#E69F00", "#009E73"
    fig, axes = plt.subplots(1, 3, figsize=(8.4, 2.7))

    coordinate = np.array([1.0 / 32.0, 1.0 / 64.0])
    values = np.array([row["Gamma_x"] for row in crossings])
    axes[0].plot(coordinate, values, "o", color=blue)
    axes[0].plot(
        [0.0, *coordinate[::-1]],
        [
            analysis["critical_field"]["power"]["estimate"],
            *values[::-1],
        ],
        "-",
        color=blue,
    )
    axes[0].set(xlabel="1/L sensitivity coordinate", ylabel="Gamma crossing")

    effective_lengths = np.asarray(z["z_eff"]["effective_lengths"])
    z_eff = np.asarray(z["z_eff"]["values"])
    axes[1].plot(effective_lengths, z_eff, "o", color=orange, label="z_eff")
    dense_lengths = np.linspace(effective_lengths[0], 140.0, 200)
    power = z["regression"]["power"]
    axes[1].plot(
        dense_lengths,
        power["estimate"] + power["coefficient"] / dense_lengths,
        "--",
        color=blue,
        label="power regression",
    )
    log = z["regression"]["log"]
    axes[1].plot(
        dense_lengths,
        log["estimate"] + log["coefficient"] / np.log(dense_lengths),
        ":",
        color=green,
        label="log regression",
    )
    axes[1].set_xlim(0.0, 140.0)
    axes[1].set(xlabel="effective L", ylabel="z")
    axes[1].legend(frameon=False, fontsize=7)

    axes[2].loglog(SIZES, gaps, "o-", color=green)
    axes[2].set(xlabel="L", ylabel="gap")
    fig.tight_layout()
    fig.savefig(output / "phase8-sigma175.png", dpi=220)
    fig.savefig(output / "phase8-sigma175.pdf")
    plt.close(fig)


def _write_report(path: Path, analysis: dict) -> None:
    z = analysis["z"]
    published = analysis["published_comparison"]
    diagnostics = ", ".join(
        f"z_eff({pair.replace('_', ',')})={value:.8g}"
        for pair, value in zip(z["z_eff"]["pairs"], z["z_eff"]["values"])
    )
    text = f"""# Phase 8 sigma=1.75 finite-size scaling

The adjacent-size diagnostics are {diagnostics}. The five-size power and
logarithmic sensitivity regressions give
z={z['regression']['power']['estimate']:.8g} and
z={z['regression']['log']['estimate']:.8g}. These deterministic regressions
have two residual degrees of freedom. Adjacent z_eff values share gap
estimates, so their residuals are correlated and are not treated as
independent statistical samples. The 1/L_eff and 1/log(L_eff) coordinates
do not assume a known leading correction exponent.

Leaving L=16 out gives z={z['regression']['leave_L16_out']['power']['estimate']:.8g}
and z={z['regression']['leave_L16_out']['log']['estimate']:.8g} for the
power and logarithmic coordinates, respectively.

Shiratani--Todo report z={published['z_power']}({int(100*published['z_power_uncertainty']):d})
for the power correction and z={published['z_log']}({int(100*published['z_log_uncertainty']):d})
for the logarithmic correction at sigma=7/4
([arXiv:{published['arxiv']}]({published['url']}), Table {published['table']}).
Their calculation reaches L={published['L_max']}; the present L<=128
comparison is therefore qualitative and is not a precision reproduction.

The power/log critical-field sensitivity is reported separately and is not
fully propagated into gap uncertainty because only two crossings are
available. The zero-frequency susceptibility gamma/nu is not measured.
Equal-time C_eq(r) and S_eq(0) are auxiliary diagnostics only.
"""
    path.write_text(text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--gap-root", type=Path, required=True)
    parser.add_argument("--phase6-uncertainty", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    decision = _load(args.decision)
    if decision.get("status") != "resolved":
        raise ValueError("report requires a resolved crossing decision")
    if not np.isclose(float(decision.get("sigma", np.nan)), SIGMA):
        raise ValueError("report requires sigma=1.75")
    gamma = float(decision.get("common_field", {}).get("gap_field", np.nan))
    if not np.isfinite(gamma):
        raise ValueError("decision is missing a finite common gap field")

    states = _load_states(args.gap_root, gamma)
    phase6 = _load(args.phase6_uncertainty)
    (
        crossings,
        critical_rows,
        diagnostic_rows,
        z_rows,
        equal_time_rows,
        uncertainty,
        analysis,
    ) = _rows_and_analysis(decision, states, phase6)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(args.output_dir / "crossings.csv", crossings)
    _write_csv(
        args.output_dir / "critical-field-sensitivity.csv",
        critical_rows,
    )
    _write_csv(args.output_dir / "gap-diagnostics.csv", diagnostic_rows)
    _write_csv(args.output_dir / "z-sensitivity.csv", z_rows)
    _write_csv(
        args.output_dir / "equal-time-diagnostics.csv",
        equal_time_rows,
    )
    _write_csv(
        args.output_dir / "uncertainty-budget.csv",
        [
            {
                "source": key,
                "details": json.dumps(value, sort_keys=True),
            }
            for key, value in uncertainty.items()
        ],
    )
    (args.output_dir / "analysis.json").write_text(
        json.dumps(analysis, indent=2) + "\n"
    )
    _plot(args.output_dir, analysis)
    _write_report(args.output_dir / "report.md", analysis)
    print(f"wrote Phase 8 report to {args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
