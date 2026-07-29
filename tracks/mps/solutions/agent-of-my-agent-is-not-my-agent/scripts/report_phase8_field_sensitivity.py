#!/usr/bin/env python3
"""Compare Phase 8 gaps at the self-consistent and published fields."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from lrtfim.phase8_protocol import (
    GAP_DISCARDED_WEIGHT_LIMIT,
    GAP_RELATIVE_VARIANCE_LIMIT,
    GAMMA_ST,
)
from lrtfim.phase8_scaling import (
    direct_gap_power_law,
    gap_scaling_summary,
)


SIGMA = 1.75
SIZES = (16, 32, 64, 96, 128)
SECTORS = ("even", "odd")
ALLOWED_CHI = (128, 256)


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty table {path.name}")
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _state_record(summary: dict, sector: str, chi: int) -> dict:
    settings = summary.get("settings", {})
    state = summary.get("direct", {}).get(sector, {})
    energy = float(state.get("energy", np.nan))
    variance = float(state.get("variance", np.nan))
    discarded = float(state.get("discarded_weight", np.nan))
    sweeps = int(state.get("sweeps", -1))
    max_sweeps = int(settings.get("max_sweeps", -1))
    relative_variance = variance / max(energy * energy, 1.0)
    finite = all(
        np.isfinite(value)
        for value in (energy, variance, discarded, relative_variance)
    )
    accepted = (
        summary.get("status") == "success"
        and finite
        and relative_variance <= GAP_RELATIVE_VARIANCE_LIMIT
        and discarded <= GAP_DISCARDED_WEIGHT_LIMIT
        and 0 <= sweeps < max_sweeps
        and int(state.get("reached_chi", 0)) > 0
    )
    return {
        "chi": chi,
        "energy": energy,
        "variance": variance,
        "relative_variance": relative_variance,
        "discarded_weight": discarded,
        "requested_chi": int(state.get("requested_chi", chi)),
        "reached_chi": int(state.get("reached_chi", 0)),
        "sweeps": sweeps,
        "max_sweeps": max_sweeps,
        "wall_seconds": float(state.get("wall_seconds", np.nan)),
        "accepted": bool(accepted),
        "code_hash": summary.get("code_hash"),
        "fit_hash": summary.get("fit", {}).get("fit_hash"),
        "initialization": summary.get("initialization", {}).get(sector),
    }


def _validate_setup(summary: dict, length: int, sector: str, chi: int) -> None:
    settings = summary.get("settings", {})
    expected = {
        "sigma": SIGMA,
        "length": length,
        "gamma": GAMMA_ST,
        "num_exponentials": 24,
        "alpha": 0.5,
        "r_fit": 2048,
        "chi_schedule": [chi],
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
                f"L={length} {sector} chi={chi} {field} mismatch: "
                f"{actual!r} != {value!r}"
            )
    mpo = summary.get("mpo", {})
    if mpo.get("pruned") is not True:
        raise ValueError("exact-zero MPO pruning must be enabled")
    if mpo.get("approximate_compression") is not False:
        raise ValueError("approximate MPO compression must be disabled")


def _select_states(root: Path) -> tuple[dict, dict, list[dict]]:
    candidates: dict[tuple[int, str], dict[int, dict]] = {}
    for path in sorted(root.rglob("summary.json")):
        summary = _load(path)
        settings = summary.get("settings", {})
        sectors = settings.get("sectors", [])
        chi_schedule = settings.get("chi_schedule", [])
        if len(sectors) != 1 or len(chi_schedule) != 1:
            continue
        length = int(settings.get("length", -1))
        sector = sectors[0]
        chi = int(chi_schedule[0])
        key = (length, sector)
        if key not in {
            (size, parity) for size in SIZES for parity in SECTORS
        }:
            continue
        if chi not in ALLOWED_CHI:
            raise ValueError(f"unexpected chi={chi} for L={length} {sector}")
        _validate_setup(summary, length, sector, chi)
        if chi in candidates.setdefault(key, {}):
            raise ValueError(f"duplicate L={length} {sector} chi={chi}")
        candidates[key][chi] = _state_record(summary, sector, chi)

    selected = {}
    baselines: dict[str, dict] = {}
    refinements = []
    for length in SIZES:
        baselines[str(length)] = {}
        for sector in SECTORS:
            key = (length, sector)
            if key not in candidates or 128 not in candidates[key]:
                raise ValueError(f"missing L={length} {sector} chi=128 baseline")
            baseline = candidates[key][128]
            baselines[str(length)][sector] = baseline
            accepted = [
                record
                for record in candidates[key].values()
                if record["accepted"]
            ]
            if not accepted:
                raise ValueError(f"no accepted L={length} {sector} state")
            final = max(accepted, key=lambda record: record["chi"])
            selected[key] = final
            if final["chi"] == 256:
                refinements.append(
                    {
                        "L": length,
                        "sector": sector,
                        "chi128_energy": baseline["energy"],
                        "chi256_energy": final["energy"],
                        "energy_shift": final["energy"] - baseline["energy"],
                        "chi128_relative_variance": baseline[
                            "relative_variance"
                        ],
                        "chi256_relative_variance": final[
                            "relative_variance"
                        ],
                        "chi128_discarded_weight": baseline[
                            "discarded_weight"
                        ],
                        "chi256_discarded_weight": final[
                            "discarded_weight"
                        ],
                        "chi256_wall_seconds": final["wall_seconds"],
                    }
                )
    return selected, baselines, refinements


def _branch_analysis(gaps: list[float]) -> dict:
    scaling = gap_scaling_summary(SIZES, gaps)
    return {
        "gaps": {
            str(length): gap for length, gap in zip(SIZES, gaps)
        },
        "z_eff": scaling["z_eff"],
        "correction_sensitivity": scaling["regression"],
        "direct_gap_power_law": direct_gap_power_law(SIZES, gaps),
    }


def _rows_and_analysis(selected: dict, baselines: dict, previous: dict):
    st_gaps = []
    selected_chi: dict[str, dict] = {}
    gap_rows = []
    for length in SIZES:
        even = selected[(length, "even")]
        odd = selected[(length, "odd")]
        gap = odd["energy"] - even["energy"]
        if not np.isfinite(gap) or gap <= 0.0:
            raise ValueError(f"L={length} final gap must be positive")
        st_gaps.append(gap)
        selected_chi[str(length)] = {
            "even": even["chi"],
            "odd": odd["chi"],
        }
        gap_rows.append(
            {
                "L": length,
                "Gamma_c_power_gap": previous["gaps"][str(length)],
                "Gamma_c_ST_gap": gap,
                "ST_even_chi": even["chi"],
                "ST_odd_chi": odd["chi"],
            }
        )

    previous_gaps = [float(previous["gaps"][str(size)]) for size in SIZES]
    power_branch = _branch_analysis(previous_gaps)
    st_branch = _branch_analysis(st_gaps)
    power_branch["Gamma"] = float(previous["critical_field"]["gap_field"])
    power_branch["field_role"] = "self_consistent_crossing_field"
    st_branch["Gamma"] = GAMMA_ST
    st_branch["field_role"] = "external_published_benchmark"
    st_branch["selected_chi"] = selected_chi
    st_branch["chi128_baselines"] = baselines

    z_rows = []
    for index, pair in enumerate(st_branch["z_eff"]["pairs"]):
        old = power_branch["z_eff"]["values"][index]
        new = st_branch["z_eff"]["values"][index]
        z_rows.append(
            {
                "size_pair": pair,
                "effective_L": st_branch["z_eff"]["effective_lengths"][index],
                "Gamma_c_power_z_eff": old,
                "Gamma_c_ST_z_eff": new,
                "shift": new - old,
            }
        )

    fit_rows = [
        {
            "analysis": "direct_gap_power_law",
            "Gamma_c_power": power_branch["direct_gap_power_law"]["exponent"],
            "Gamma_c_ST": st_branch["direct_gap_power_law"]["exponent"],
            "published_reference": np.nan,
        },
        {
            "analysis": "z_eff_power_correction",
            "Gamma_c_power": power_branch["correction_sensitivity"]["power"][
                "estimate"
            ],
            "Gamma_c_ST": st_branch["correction_sensitivity"]["power"][
                "estimate"
            ],
            "published_reference": previous["published_comparison"][
                "z_power"
            ],
        },
        {
            "analysis": "z_eff_log_correction",
            "Gamma_c_power": power_branch["correction_sensitivity"]["log"][
                "estimate"
            ],
            "Gamma_c_ST": st_branch["correction_sensitivity"]["log"][
                "estimate"
            ],
            "published_reference": previous["published_comparison"]["z_log"],
        },
    ]
    power_reduced = abs(
        fit_rows[1]["Gamma_c_ST"] - fit_rows[1]["published_reference"]
    ) < abs(
        fit_rows[1]["Gamma_c_power"] - fit_rows[1]["published_reference"]
    )
    log_reduced = abs(
        fit_rows[2]["Gamma_c_ST"] - fit_rows[2]["published_reference"]
    ) < abs(
        fit_rows[2]["Gamma_c_power"] - fit_rows[2]["published_reference"]
    )
    analysis = {
        "sigma": SIGMA,
        "branches": {
            "self_consistent_crossing_field": power_branch,
            "external_published_field": st_branch,
        },
        "z_eff_comparison": z_rows,
        "fit_comparison": fit_rows,
        "published_comparison": previous["published_comparison"],
        "interpretation": {
            "power_correction_discrepancy_reduced": power_reduced,
            "log_correction_discrepancy_reduced": log_reduced,
            "discrepancy_reduced_in_both_declared_coordinates": (
                power_reduced and log_reduced
            ),
            "field_selected_by_outcome": False,
            "external_field_role": "sensitivity_only",
        },
        "constraints": {
            "Gamma_search_performed": False,
            "sigma_extension_performed": False,
            "L_greater_than_128_performed": False,
            "K32_performed": False,
        },
    }
    return gap_rows, z_rows, fit_rows, analysis


def _plot(path: Path, analysis: dict) -> None:
    power = analysis["branches"]["self_consistent_crossing_field"]
    st = analysis["branches"]["external_published_field"]
    blue, orange, green = "#0072B2", "#E69F00", "#009E73"
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.2))

    for branch, color, label in (
        (power, blue, "self-consistent field"),
        (st, orange, "published field"),
    ):
        gaps = [branch["gaps"][str(size)] for size in SIZES]
        axes[0].loglog(SIZES, gaps, "o-", color=color, label=label)
    axes[0].set_xticks([16, 32, 64, 128], ["16", "32", "64", "128"])
    axes[0].tick_params(axis="x", which="minor", labelbottom=False)
    axes[0].set(xlabel="L", ylabel="gap")
    axes[0].legend(frameon=False, fontsize=7)

    effective = st["z_eff"]["effective_lengths"]
    axes[1].plot(
        effective,
        power["z_eff"]["values"],
        "o-",
        color=blue,
        label="self-consistent field",
    )
    axes[1].plot(
        effective,
        st["z_eff"]["values"],
        "s--",
        color=orange,
        label="published field",
    )
    axes[1].axhline(
        analysis["published_comparison"]["z_power"],
        color=green,
        linestyle=":",
        label="published z (power)",
    )
    axes[1].set(xlabel="effective L", ylabel="z_eff")
    axes[1].legend(frameon=False, fontsize=7)

    rows = analysis["fit_comparison"]
    x = np.arange(len(rows))
    axes[2].plot(
        x,
        [row["Gamma_c_power"] for row in rows],
        "o",
        color=blue,
        label="self-consistent field",
    )
    axes[2].plot(
        x,
        [row["Gamma_c_ST"] for row in rows],
        "s",
        color=orange,
        label="published field",
    )
    for index, row in enumerate(rows):
        reference = row["published_reference"]
        if np.isfinite(reference):
            axes[2].plot(index, reference, "*", color=green, markersize=9)
    axes[2].set_xticks(
        x,
        ["direct", "power corr.", "log corr."],
        rotation=20,
        ha="right",
    )
    axes[2].set_ylabel("z estimate")
    axes[2].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(path / "phase8-field-sensitivity.png", dpi=220)
    fig.savefig(path / "phase8-field-sensitivity.pdf")
    plt.close(fig)


def _write_report(path: Path, analysis: dict, refinements: list[dict]) -> None:
    power = analysis["branches"]["self_consistent_crossing_field"]
    st = analysis["branches"]["external_published_field"]
    interpretation = analysis["interpretation"]
    text = f"""# Phase 8 critical-field sensitivity at sigma=1.75

This branch keeps the original DMRG crossing result at
Gamma={power['Gamma']:.16g} and independently evaluates all final energies
at the external Shiratani--Todo benchmark Gamma={st['Gamma']:.7g}. The
external field is a sensitivity coordinate, not a replacement or a
field-selection criterion.

The direct gap regressions give z={power['direct_gap_power_law']['exponent']:.8g}
at the self-consistent field and z={st['direct_gap_power_law']['exponent']:.8g}
at the published field. The effective-exponent power-correction results are
{power['correction_sensitivity']['power']['estimate']:.8g} and
{st['correction_sensitivity']['power']['estimate']:.8g}; the logarithmic
results are {power['correction_sensitivity']['log']['estimate']:.8g} and
{st['correction_sensitivity']['log']['estimate']:.8g}.

Relative to Shiratani--Todo's published power/log values, the discrepancy
is {'reduced' if interpretation['discrepancy_reduced_in_both_declared_coordinates'] else 'not reduced in both coordinates'}
by using the external field. This statement describes sensitivity only;
`field_selected_by_outcome` remains false. No Gamma search, larger size,
sigma extension, or K=32 calculation was performed.

Selective chi=256 refinements: {len(refinements)}. Every chi=128 baseline,
including failed convergence diagnostics, is retained in `analysis.json`;
final gaps use only accepted states.
"""
    path.write_text(text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--st-root", type=Path, required=True)
    parser.add_argument("--power-analysis", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    selected, baselines, refinements = _select_states(args.st_root)
    previous = _load(args.power_analysis)
    if not np.isclose(float(previous.get("sigma", np.nan)), SIGMA):
        raise ValueError("previous analysis must have sigma=1.75")
    gap_rows, z_rows, fit_rows, analysis = _rows_and_analysis(
        selected,
        baselines,
        previous,
    )
    analysis["refinement_diagnostics"] = refinements

    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(args.output_dir / "gaps-comparison.csv", gap_rows)
    _write_csv(args.output_dir / "z-eff-comparison.csv", z_rows)
    _write_csv(args.output_dir / "fit-comparison.csv", fit_rows)
    _write_csv(
        args.output_dir / "refinement-diagnostics.csv",
        refinements
        if refinements
        else [
            {
                "L": "",
                "sector": "none",
                "chi128_energy": "",
                "chi256_energy": "",
                "energy_shift": "",
                "chi128_relative_variance": "",
                "chi256_relative_variance": "",
                "chi128_discarded_weight": "",
                "chi256_discarded_weight": "",
                "chi256_wall_seconds": "",
            }
        ],
    )
    (args.output_dir / "analysis.json").write_text(
        json.dumps(analysis, indent=2) + "\n"
    )
    _plot(args.output_dir, analysis)
    _write_report(args.output_dir / "report.md", analysis, refinements)
    print(
        f"wrote Phase 8 field-sensitivity report to {args.output_dir}",
        flush=True,
    )


if __name__ == "__main__":
    main()
