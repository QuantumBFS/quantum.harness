#!/usr/bin/env python3
"""Immutable model, field-order, and replay contracts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path


@dataclass(frozen=True)
class ArchiveContract:
    lx: int
    ly: int
    ltrot: int
    nfield: int
    theta: int
    dt: float
    beta: float
    status: str
    selected_projection_sha256: str
    trial_manifest_sha256: str
    storage_order: str
    up_exponent: str
    down_exponent: str
    strict_ground_state_claim_allowed: bool
    alf_to_cpp: tuple[int, ...]


@dataclass(frozen=True)
class ReplayContract:
    right_projector_slices: int
    measurement_window_slices: int
    left_projector_slices: int
    center_slice: int
    central_estimator: str
    endpoint_estimator: str


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _integer_slices(value: float, label: str) -> int:
    rounded = round(value)
    if abs(value - rounded) >= 1.0e-12:
        raise ValueError(f"{label} is not an integer number of slices")
    return int(rounded)


def _site_permutation(path: Path) -> tuple[int, ...]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        values = tuple(int(value) for value in line.split())
        if len(values) != 4:
            raise ValueError("site map row must have four integers")
        rows.append(values)
    if len(rows) != 16:
        raise ValueError("site map is not a 16-site bijection")
    alf = {row[0] for row in rows}
    cpp = {row[1] for row in rows}
    if alf != set(range(1, 17)) or cpp != set(range(16)):
        raise ValueError("site map is not a bijection")
    for _alf, cpp_site, x, y in rows:
        if not (0 <= x < 4 and 0 <= y < 4) or cpp_site != y * 4 + x:
            raise ValueError("site map violates row-major coordinates")
    return tuple(
        cpp_site for _alf, cpp_site, _x, _y in sorted(rows)
    )


def load_contracts(
    selected_path: Path,
    trial_manifest_path: Path,
    site_map_path: Path,
) -> tuple[ArchiveContract, ReplayContract]:
    selected = json.loads(selected_path.read_text(encoding="utf-8"))
    status = selected.get("status")
    allowed = {
        "target_reached",
        "max_theta_fallback",
        "reference_confirmation_failed",
    }
    if status not in allowed:
        raise ValueError(f"unknown selected projection status: {status}")
    dt = float(selected["dt"])
    beta = float(selected["beta"])
    theta = int(selected["theta_star"])
    expected_ltrot = _integer_slices((2 * theta + beta) / dt, "Ltrot")
    if int(selected["ltrot_star"]) != expected_ltrot:
        raise ValueError("selected Ltrot is inconsistent")
    expected_nfield = 16 * expected_ltrot
    if int(selected["nfield_star"]) != expected_nfield:
        raise ValueError("selected nfield is inconsistent")
    trial_hash = sha256_file(trial_manifest_path)
    if selected.get("trial_manifest_sha256") != trial_hash:
        raise ValueError("trial manifest hash mismatch")
    right = _integer_slices(theta / dt, "right projector")
    window = _integer_slices(beta / dt, "measurement window")
    left = _integer_slices(theta / dt, "left projector")
    if right + window + left != expected_ltrot:
        raise ValueError("projection slice partition is inconsistent")
    archive = ArchiveContract(
        lx=4,
        ly=4,
        ltrot=expected_ltrot,
        nfield=expected_nfield,
        theta=theta,
        dt=dt,
        beta=beta,
        status=status,
        selected_projection_sha256=sha256_file(selected_path),
        trial_manifest_sha256=trial_hash,
        storage_order="time_slice_major_then_alf_site",
        up_exponent="+gamma*x",
        down_exponent="-gamma*x",
        strict_ground_state_claim_allowed=(status == "target_reached"),
        alf_to_cpp=_site_permutation(site_map_path),
    )
    replay = ReplayContract(
        right_projector_slices=right,
        measurement_window_slices=window,
        left_projector_slices=left,
        center_slice=right + window // 2,
        central_estimator="two_sided_checkpoint_at_center_slice",
        endpoint_estimator="two_sided_after_all_ltrot_slices",
    )
    return archive, replay
