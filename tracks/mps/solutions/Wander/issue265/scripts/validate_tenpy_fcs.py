#!/usr/bin/env python3
"""Validate the two-measurement charge-transfer FCS on paired smoke data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research_dataset import ResearchDataset, load_research_dataset


def _mean_transfer_from_logz(dataset: ResearchDataset) -> np.ndarray:
    gamma = np.asarray(dataset.fcs_gamma, dtype=float)
    logz = np.asarray(dataset.fcs_logZ)
    positive = gamma[gamma > 1e-13]
    if positive.size == 0:
        raise ValueError("FCS grid needs a positive counting field")
    step = float(np.min(positive))
    positive_index = int(np.argmin(np.abs(gamma - step)))
    negative_index = int(np.argmin(np.abs(gamma + step)))
    return np.imag(
        logz[:, positive_index] - logz[:, negative_index]
    ) / (2.0 * step)


def _direct_charge_transfer(dataset: ResearchDataset) -> np.ndarray:
    if dataset.m is None:
        raise ValueError("Physical magnetization is required")
    first_right = dataset.x.size // 2
    charge = np.sum(dataset.m[:, first_right:], axis=1)
    return charge - charge[0]


def _integrated_current(dataset: ResearchDataset) -> np.ndarray:
    if dataset.current is None:
        raise ValueError("Local spin current is required")
    central_bond = dataset.x.size // 2 - 1
    current = dataset.current[:, central_bond]
    result = np.zeros_like(current)
    result[1:] = np.cumsum(
        0.5 * (current[1:] + current[:-1]) * np.diff(dataset.t)
    )
    return result


def validate_fcs_pair(up_path: Path, down_path: Path) -> dict[str, object]:
    up = load_research_dataset(up_path)
    down = load_research_dataset(down_path)
    if up.fcs_gamma is None or up.fcs_logZ is None:
        raise ValueError("Up dataset has no FCS")
    if down.fcs_gamma is None or down.fcs_logZ is None:
        raise ValueError("Down dataset has no FCS")
    np.testing.assert_allclose(up.x, down.x)
    np.testing.assert_allclose(up.t, down.t)
    np.testing.assert_allclose(up.fcs_gamma, down.fcs_gamma)
    gamma = np.asarray(up.fcs_gamma, dtype=float)
    reverse = np.arange(gamma.size - 1, -1, -1)
    zero = int(np.argmin(np.abs(gamma)))

    hermiticity_up = float(
        np.max(np.abs(up.fcs_logZ - np.conj(up.fcs_logZ[:, reverse])))
    )
    hermiticity_down = float(
        np.max(np.abs(down.fcs_logZ - np.conj(down.fcs_logZ[:, reverse])))
    )
    spin_flip = float(
        np.max(np.abs(down.fcs_logZ - up.fcs_logZ[:, reverse]))
    )
    zero_field = float(
        max(
            np.max(np.abs(up.fcs_logZ[:, zero])),
            np.max(np.abs(down.fcs_logZ[:, zero])),
        )
    )
    initial_logz = float(
        max(
            np.max(np.abs(up.fcs_logZ[0])),
            np.max(np.abs(down.fcs_logZ[0])),
        )
    )

    mean_up = _mean_transfer_from_logz(up)
    mean_down = _mean_transfer_from_logz(down)
    charge_up = _direct_charge_transfer(up)
    charge_down = _direct_charge_transfer(down)
    current_up = _integrated_current(up)
    current_down = _integrated_current(down)
    scale = max(
        float(np.max(np.abs(charge_up))),
        float(np.max(np.abs(charge_down))),
        1e-14,
    )
    fcs_charge_relative = float(
        max(
            np.max(np.abs(mean_up - charge_up)),
            np.max(np.abs(mean_down - charge_down)),
        )
        / scale
    )
    current_charge_relative = float(
        max(
            np.max(np.abs(current_up - charge_up)),
            np.max(np.abs(current_down - charge_down)),
        )
        / scale
    )
    thresholds = {
        "algebraic_absolute": 1e-10,
        "fcs_mean_relative": 0.02,
        "current_integral_relative": 0.002,
    }
    checks = {
        "characteristic_function_hermiticity": (
            max(hermiticity_up, hermiticity_down)
            < thresholds["algebraic_absolute"]
        ),
        "spin_flip_counting_field_reversal": (
            spin_flip < thresholds["algebraic_absolute"]
        ),
        "zero_counting_field_normalization": (
            zero_field < thresholds["algebraic_absolute"]
        ),
        "initial_transfer_is_zero": (
            initial_logz < thresholds["algebraic_absolute"]
        ),
        "fcs_first_cumulant_matches_charge_transfer": (
            fcs_charge_relative < thresholds["fcs_mean_relative"]
        ),
        "integrated_current_matches_charge_transfer": (
            current_charge_relative
            < thresholds["current_integral_relative"]
        ),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "inputs": {"up": str(up_path.resolve()), "down": str(down_path.resolve())},
        "definition": (
            "Z(gamma,t)=Tr[rho0 U^dagger exp(i gamma Q_R) "
            "U exp(-i gamma Q_R)]"
        ),
        "thresholds": thresholds,
        "checks": checks,
        "metrics": {
            "hermiticity_up_max_abs": hermiticity_up,
            "hermiticity_down_max_abs": hermiticity_down,
            "spin_flip_max_abs": spin_flip,
            "zero_gamma_max_abs": zero_field,
            "initial_logZ_max_abs": initial_logz,
            "fcs_mean_vs_charge_relative": fcs_charge_relative,
            "integrated_current_vs_charge_relative": current_charge_relative,
            "endpoint": {
                "fcs_mean_up": float(mean_up[-1]),
                "charge_transfer_up": float(charge_up[-1]),
                "integrated_current_up": float(current_up[-1]),
                "fcs_mean_down": float(mean_down[-1]),
                "charge_transfer_down": float(charge_down[-1]),
                "integrated_current_down": float(current_down[-1]),
            },
        },
    }


def _report(summary: dict[str, object]) -> str:
    checks = summary["checks"]
    metrics = summary["metrics"]
    endpoint = metrics["endpoint"]
    lines = [
        "# TeNPy transfer-FCS validation",
        "",
        f"**Status:** `{summary['status']}`",
        "",
        "This is an implementation-level small-chain test. The generating "
        "function uses a genuine two-measurement counting-field branch, not "
        "an equal-time fluctuation proxy.",
        "",
        f"\\[{summary['definition']}\\]",
        "",
        "| Check | Result |",
        "|---|---:|",
        *[
            f"| {name} | {'pass' if passed else 'fail'} |"
            for name, passed in checks.items()
        ],
        "",
        "## Metrics",
        "",
        f"- Hermiticity defect (up/down): "
        f"`{metrics['hermiticity_up_max_abs']:.6e}` / "
        f"`{metrics['hermiticity_down_max_abs']:.6e}`",
        f"- spin-flip/counting-field reversal defect: "
        f"`{metrics['spin_flip_max_abs']:.6e}`",
        f"- FCS first-cumulant versus direct charge relative error: "
        f"`{metrics['fcs_mean_vs_charge_relative']:.6e}`",
        f"- integrated-current versus direct charge relative error: "
        f"`{metrics['integrated_current_vs_charge_relative']:.6e}`",
        "",
        "At the last saved time for the up wall:",
        "",
        f"- FCS mean transfer: `{endpoint['fcs_mean_up']:.9e}`",
        f"- direct right-half charge change: "
        f"`{endpoint['charge_transfer_up']:.9e}`",
        f"- trapezoidal integrated central current: "
        f"`{endpoint['integrated_current_up']:.9e}`",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    smoke_root = ROOT / "results_research_program" / "tenpy_smoke"
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--up",
        type=Path,
        default=smoke_root / "fcs_up_smoke.npz",
    )
    parser.add_argument(
        "--down",
        type=Path,
        default=smoke_root / "fcs_down_smoke.npz",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=smoke_root / "fcs_validation",
    )
    args = parser.parse_args()
    summary = validate_fcs_pair(args.up, args.down)
    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    )
    (args.outdir / "REPORT.md").write_text(_report(summary))
    print(json.dumps(summary, ensure_ascii=False))
    if summary["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
