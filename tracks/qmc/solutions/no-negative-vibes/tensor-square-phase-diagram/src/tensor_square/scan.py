"""Grid, sharding, reproducibility, and early classification for Stage 3."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import hmac
import json
import math
from pathlib import Path
from typing import Iterable

from .dqmc import DQMCConfig


EXPERIMENT_ID = "stage3-coarse-20260729"
DENSITY_AUDIT_TOL = 1.0e-7


@dataclass(frozen=True)
class ScanCell:
    index: int
    cell_id: str
    config: DQMCConfig
    worker_id: int = -1


def _scaled_label(value: float) -> str:
    return f"{int(round(100.0 * value)):03d}"


def _mu_label(value: float) -> str:
    if value < 0.0:
        return f"n{int(round(10.0 * abs(value))):02d}"
    if value > 0.0:
        return f"p{int(round(10.0 * value)):02d}"
    return "000"


def coarse_grid() -> list[ScanCell]:
    cells: list[ScanCell] = []
    for m in (4, 6, 8):
        for beta in (2.0, 4.0, 8.0):
            for g_ratio in (0.0, 0.25, 0.5, 1.0, 2.0):
                for t in (0.0, 0.25, 0.5, 1.0, 2.0):
                    for mu in (-1.5, 0.0, 1.5):
                        proposal_scale = (
                            0.75
                            if beta == 2.0
                            else (0.50 if beta == 4.0 else 0.25)
                        )
                        config = DQMCConfig(
                            m=m,
                            beta=beta,
                            dt=0.2,
                            t=t,
                            g_b_over_g_a=g_ratio,
                            mu=mu,
                            proposal_scale=proposal_scale,
                            stabilize=beta >= 4.0,
                        )
                        cell_id = (
                            f"m{m:02d}_b{int(beta):02d}"
                            f"_g{_scaled_label(g_ratio)}"
                            f"_t{_scaled_label(t)}"
                            f"_mu{_mu_label(mu)}"
                        )
                        cells.append(
                            ScanCell(
                                index=len(cells),
                                cell_id=cell_id,
                                config=config,
                            )
                        )
    return cells


def select_shard(cells: Iterable[ScanCell], machine: str) -> list[ScanCell]:
    if machine not in {"wsl", "cpu"}:
        raise ValueError("machine must be 'wsl' or 'cpu'")
    selected = [
        cell
        for cell in cells
        if (cell.index % 5 == 0) == (machine == "wsl")
    ]
    first_worker = 0 if machine == "wsl" else 14
    worker_count = 14 if machine == "wsl" else 62
    return [
        replace(
            cell,
            worker_id=first_worker + ordinal % worker_count,
        )
        for ordinal, cell in enumerate(selected)
    ]


def deterministic_seed(
    experiment_id: str, cell_id: str, worker_id: int
) -> int:
    material = f"{experiment_id}|{cell_id}|{worker_id}".encode("utf-8")
    digest = hashlib.sha256(material).digest()
    return int.from_bytes(digest[:4], byteorder="big", signed=False)


def portable_command(
    argv: Iterable[str], project_root: str | Path
) -> list[str]:
    portable_root = str(project_root).replace("\\", "/").rstrip("/")
    root = Path(project_root).resolve()
    command = ["python"]
    for argument in argv:
        portable_argument = str(argument).replace("\\", "/")
        if portable_argument.startswith(f"{portable_root}/"):
            command.append(portable_argument[len(portable_root) + 1 :])
            continue
        path = Path(argument)
        if path.is_absolute():
            try:
                argument = path.resolve().relative_to(root).as_posix()
            except ValueError:
                argument = path.name
        command.append(argument)
    return command


def run_fingerprint(run_spec: dict[str, object]) -> str:
    encoded = json.dumps(
        run_spec,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_run_fingerprint(stored: str, expected: str) -> None:
    if not hmac.compare_digest(stored, expected):
        raise ValueError("run fingerprint mismatch; refusing stale result")


def validate_source_revision(commit: str, *, dirty: bool) -> None:
    if not commit or commit == "unknown" or dirty:
        raise ValueError(
            "source revision must be known and clean for production scan"
        )


def needs_stable_retry(summary: dict[str, object]) -> bool:
    sign = float(
        summary.get(
            "direct_sign_min",
            summary.get("direct_sign_mean", float("nan")),
        )
    )
    log_error = float(
        summary.get(
            "weight_log_error_max",
            summary.get("weight_log_error_mean", float("nan")),
        )
    )
    density_min = float(
        summary.get(
            "density_min",
            summary.get("density_mean", float("nan")),
        )
    )
    density_max = float(
        summary.get(
            "density_max",
            summary.get("density_mean", float("nan")),
        )
    )
    values = (sign, log_error, density_min, density_max)
    if not all(math.isfinite(value) for value in values):
        return True
    return (
        sign < 1.0 - 1.0e-8
        or log_error > 1.0e-6
        or density_min < -DENSITY_AUDIT_TOL
        or density_max > 1.0 + DENSITY_AUDIT_TOL
    )


def _uncertainty(row: dict[str, object], name: str) -> float:
    value = float(row.get(f"{name}_stderr", float("nan")))
    return value if math.isfinite(value) and value >= 0.0 else float("inf")


def _row_is_broken(row: dict[str, object]) -> bool:
    required = (
        "q_combined_mean",
        "q_a_sq_mean",
        "q_b_sq_mean",
        "density_mean",
        "direct_sign_mean",
        "weight_log_error_mean",
    )
    if any(not math.isfinite(float(row.get(key, float("nan")))) for key in required):
        return True
    return needs_stable_retry(row)


def _z_score(delta: float, *errors: float) -> float:
    sigma = math.sqrt(sum(error * error for error in errors))
    if not math.isfinite(sigma):
        return 0.0
    return delta / max(1.0e-12, sigma)


def classify_regions(
    rows: Iterable[dict[str, object]],
) -> list[dict[str, object]]:
    row_list = list(rows)
    grouped: dict[tuple[float, float, float], list[dict[str, object]]] = {}
    for row in row_list:
        key = (
            float(row["g_b_over_g_a"]),
            float(row["t"]),
            float(row["mu"]),
        )
        grouped.setdefault(key, []).append(row)

    competition_keys: set[tuple[float, float, float]] = set()
    for t in sorted({key[1] for key in grouped}):
        for mu in sorted({key[2] for key in grouped}):
            candidates: list[tuple[float, dict[str, object]]] = []
            for key, group in grouped.items():
                if key[1:] != (t, mu):
                    continue
                complete = [
                    row
                    for row in group
                    if float(row["beta"]) == 8.0 and int(row["m"]) == 8
                ]
                if complete and not _row_is_broken(complete[0]):
                    candidates.append((key[0], complete[0]))
            candidates.sort(key=lambda item: item[0])
            for (g_left, left), (g_right, right) in zip(
                candidates, candidates[1:]
            ):
                balance_left = float(left["channel_balance_mean"])
                balance_right = float(right["channel_balance_mean"])
                difference_z = _z_score(
                    abs(balance_right - balance_left),
                    _uncertainty(left, "channel_balance"),
                    _uncertainty(right, "channel_balance"),
                )
                if balance_left * balance_right < 0.0 and difference_z >= 2.0:
                    competition_keys.add((g_left, t, mu))
                    competition_keys.add((g_right, t, mu))

    regions: list[dict[str, object]] = []
    for key, group in sorted(grouped.items()):
        g_ratio, t, mu = key
        reasons: list[str] = []
        if any(_row_is_broken(row) for row in group):
            regions.append(
                {
                    "g_b_over_g_a": g_ratio,
                    "t": t,
                    "mu": mu,
                    "classification": "BROKEN",
                    "reasons": ["determinant/stability audit failed"],
                    "cells": len(group),
                }
            )
            continue
        lookup = {
            (float(row["beta"]), int(row["m"])): row for row in group
        }
        required = {
            (beta, m)
            for beta in (2.0, 4.0, 8.0)
            for m in (4, 6, 8)
        }
        if not required <= lookup.keys():
            regions.append(
                {
                    "g_b_over_g_a": g_ratio,
                    "t": t,
                    "mu": mu,
                    "classification": "EXTEND",
                    "reasons": ["incomplete size/temperature grid"],
                    "cells": len(group),
                }
            )
            continue
        if g_ratio == 0.0 or t == 0.0:
            regions.append(
                {
                    "g_b_over_g_a": g_ratio,
                    "t": t,
                    "mu": mu,
                    "classification": "STOP",
                    "reasons": [
                        (
                            "single-channel control line"
                            if g_ratio == 0.0
                            else "zero-kinetic control stopped after ED"
                        )
                    ],
                    "cells": len(group),
                }
            )
            continue

        low_small = lookup[(8.0, 4)]
        low_large = lookup[(8.0, 8)]
        high_large = lookup[(2.0, 8)]
        q_low_small = float(low_small["q_combined_mean"])
        q_low_large = float(low_large["q_combined_mean"])
        q_high_large = float(high_large["q_combined_mean"])
        size_delta = q_low_large - q_low_small
        thermal_delta = q_low_large - q_high_large
        size_z = _z_score(
            size_delta,
            _uncertainty(low_small, "q_combined"),
            _uncertainty(low_large, "q_combined"),
        )
        thermal_z = _z_score(
            thermal_delta,
            _uncertainty(high_large, "q_combined"),
            _uncertainty(low_large, "q_combined"),
        )
        size_fraction = size_delta / max(1.0e-12, abs(q_low_small))
        thermal_fraction = thermal_delta / max(1.0e-12, abs(q_high_large))
        structure_signal = (
            size_z >= 2.0
            and thermal_z >= 2.0
            and size_fraction >= 0.05
            and thermal_fraction >= 0.05
        )
        if structure_signal:
            reasons.append("size-and-temperature enhancement")
        if key in competition_keys:
            reasons.append("competing-channel reordering")

        measurements = int(low_large.get("measurements", 0))
        tau = max(
            0.5,
            float(low_large.get("q_a_sq_tau_int", float("inf"))),
        )
        effective_samples = measurements / (2.0 * tau)
        acceptance = float(low_large.get("acceptance", float("nan")))
        quality_ok = (
            math.isfinite(acceptance)
            and 0.05 <= acceptance <= 0.995
            and effective_samples >= 4.0
        )
        if reasons and quality_ok:
            classification = "SURVIVE"
        elif reasons:
            classification = "EXTEND"
            reasons.append("signal present but short-chain quality is marginal")
        elif (
            size_z >= 1.2
            and thermal_z >= 1.2
            and size_delta > 0.0
            and thermal_delta > 0.0
        ):
            classification = "EXTEND"
            reasons.append("sub-threshold positive size/temperature trend")
        elif not quality_ok:
            classification = "EXTEND"
            reasons.append("effective sample or acceptance threshold not met")
        else:
            classification = "STOP"
            reasons.append("flat within 2σ with no size-consistent trend")

        regions.append(
            {
                "g_b_over_g_a": g_ratio,
                "t": t,
                "mu": mu,
                "classification": classification,
                "reasons": reasons,
                "cells": len(group),
                "q_combined_beta8_m4": q_low_small,
                "q_combined_beta8_m8": q_low_large,
                "q_combined_beta2_m8": q_high_large,
                "size_delta": size_delta,
                "size_z": size_z,
                "thermal_delta": thermal_delta,
                "thermal_z": thermal_z,
                "effective_samples_beta8_m8": effective_samples,
                "acceptance_beta8_m8": acceptance,
                "channel_balance_beta8_m8": float(
                    low_large["channel_balance_mean"]
                ),
            }
        )
    return regions
