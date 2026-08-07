#!/usr/bin/env python3
"""Independent matrix validation of ALF archive time/site ordering."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.linalg import expm

from path_archive import ArchiveReader


def read_orbitals(path: Path) -> np.ndarray:
    tokens = path.read_text(encoding="utf-8").split()
    rows, cols = int(tokens[0]), int(tokens[1])
    values = np.asarray([float(value) for value in tokens[2:]])
    if values.size != rows * cols:
        raise ValueError(f"wrong orbital value count in {path}")
    return values.reshape(rows, cols)


def read_alf_to_cpp(path: Path, nsites: int) -> np.ndarray:
    mapping = np.full(nsites, -1, dtype=int)
    for line in path.read_text(encoding="utf-8").splitlines():
        alf_site, cpp_site, x, y = (int(value) for value in line.split())
        if cpp_site != y * int(round(math.sqrt(nsites))) + x:
            raise ValueError("site map row-major coordinate mismatch")
        mapping[alf_site - 1] = cpp_site
    if sorted(mapping.tolist()) != list(range(nsites)):
        raise ValueError("site map is not a bijection")
    return mapping


def kinetic_matrix(lx: int, ly: int, hopping: float) -> np.ndarray:
    sites = lx * ly
    result = np.zeros((sites, sites))
    for y in range(ly):
        for x in range(lx):
            site = y * lx + x
            for nx, ny in (
                ((x + 1) % lx, y),
                ((x - 1) % lx, y),
                (x, (y + 1) % ly),
                (x, (y - 1) % ly),
            ):
                result[site, ny * lx + nx] -= hopping
    return result


def _stabilize(orbitals: np.ndarray) -> tuple[np.ndarray, int, float]:
    q, r = np.linalg.qr(orbitals, mode="reduced")
    sign, logabs = np.linalg.slogdet(r)
    return q, int(sign), float(logabs)


def _apply_slice(
    orbitals: np.ndarray,
    half_k: np.ndarray,
    fields: np.ndarray,
    gamma: float,
    spin_sign: int,
) -> np.ndarray:
    propagated = half_k @ orbitals
    propagated *= np.exp(spin_sign * gamma * fields)[:, None]
    return half_k @ propagated


def _propagate(
    initial: np.ndarray,
    half_k: np.ndarray,
    fields: np.ndarray,
    gamma: float,
    spin_sign: int,
    stabilization_interval: int,
) -> tuple[np.ndarray, int, float]:
    orbitals = initial.copy()
    scale_sign = 1
    scale_logabs = 0.0
    for index, slice_fields in enumerate(fields, start=1):
        orbitals = _apply_slice(
            orbitals, half_k, slice_fields, gamma, spin_sign
        )
        if (
            stabilization_interval > 0
            and index % stabilization_interval == 0
        ):
            orbitals, sign, logabs = _stabilize(orbitals)
            scale_sign *= sign
            scale_logabs += logabs
    return orbitals, scale_sign, scale_logabs


def _overlap(
    left: np.ndarray,
    right: np.ndarray,
    right_sign: int,
    right_logabs: float,
) -> tuple[int, float]:
    sign, logabs = np.linalg.slogdet(left.T @ right)
    return int(sign) * right_sign, float(logabs) + right_logabs


def _density(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    overlap = left.T @ right
    return right @ np.linalg.solve(overlap, left.T)


def _energy(
    kinetic: np.ndarray,
    interaction: float,
    left_up: np.ndarray,
    left_down: np.ndarray,
    right_up: np.ndarray,
    right_down: np.ndarray,
) -> tuple[float, float, float, float]:
    density_up = _density(left_up, right_up)
    density_down = _density(left_down, right_down)
    kinetic_energy = float(np.sum(
        kinetic * (density_up.T + density_down.T)
    ))
    interaction_energy = float(interaction * np.sum(
        np.diag(density_up) * np.diag(density_down)
    ))
    particles = float(np.trace(density_up) + np.trace(density_down))
    return (
        kinetic_energy,
        interaction_energy,
        kinetic_energy + interaction_energy,
        particles,
    )


def _candidate(
    fields: np.ndarray,
    initial_up: np.ndarray,
    initial_down: np.ndarray,
    kinetic: np.ndarray,
    interaction: float,
    dt: float,
    stabilization_interval: int,
) -> dict[str, Any]:
    half_k = expm(-0.5 * dt * kinetic)
    gamma = math.acosh(math.exp(dt * interaction / 2.0))
    ltrot, nsites = fields.shape
    center = ltrot // 2
    right_up, sign_up, scale_up = _propagate(
        initial_up, half_k, fields, gamma, +1,
        stabilization_interval,
    )
    right_down, sign_down, scale_down = _propagate(
        initial_down, half_k, fields, gamma, -1,
        stabilization_interval,
    )
    overlap_up = _overlap(initial_up, right_up, sign_up, scale_up)
    overlap_down = _overlap(
        initial_down, right_down, sign_down, scale_down
    )
    endpoint_sign = overlap_up[0] * overlap_down[0]
    common = (
        -ltrot * nsites * math.log(2.0)
        -0.5 * dt * interaction
        * (initial_up.shape[1] + initial_down.shape[1]) * ltrot
    )
    endpoint_logabs = overlap_up[1] + overlap_down[1] + common
    endpoint_energy = _energy(
        kinetic, interaction, initial_up, initial_down,
        right_up, right_down,
    )

    center_right_up, _, _ = _propagate(
        initial_up, half_k, fields[:center], gamma, +1,
        stabilization_interval,
    )
    center_right_down, _, _ = _propagate(
        initial_down, half_k, fields[:center], gamma, -1,
        stabilization_interval,
    )
    reversed_tail = fields[center:][::-1]
    center_left_up, _, _ = _propagate(
        initial_up, half_k, reversed_tail, gamma, +1,
        stabilization_interval,
    )
    center_left_down, _, _ = _propagate(
        initial_down, half_k, reversed_tail, gamma, -1,
        stabilization_interval,
    )
    central_energy = _energy(
        kinetic, interaction,
        center_left_up, center_left_down,
        center_right_up, center_right_down,
    )
    return {
        "endpoint_sign": endpoint_sign,
        "endpoint_logabs": endpoint_logabs,
        "endpoint_energy": endpoint_energy,
        "central_energy": central_energy,
    }


def validate_record(
    *,
    record: Any,
    up_path: Path,
    down_path: Path,
    site_map_path: Path,
    lx: int,
    ly: int,
    hopping: float,
    interaction: float,
    dt: float,
    stabilization_interval: int,
    tolerance: float,
) -> dict[str, Any]:
    nsites = lx * ly
    alf_to_cpp = read_alf_to_cpp(site_map_path, nsites)
    initial_up_alf = read_orbitals(up_path)
    initial_down_alf = read_orbitals(down_path)
    initial_up = np.empty_like(initial_up_alf)
    initial_down = np.empty_like(initial_down_alf)
    initial_up[alf_to_cpp] = initial_up_alf
    initial_down[alf_to_cpp] = initial_down_alf
    if len(record.fields) % nsites:
        raise ValueError("record field count is not divisible by site count")
    raw_alf = np.asarray(record.fields, dtype=float).reshape(-1, nsites)
    raw = np.empty_like(raw_alf)
    raw[:, alf_to_cpp] = raw_alf
    kinetic = kinetic_matrix(lx, ly, hopping)
    candidates: dict[str, dict[str, Any]] = {}
    for reverse_time in (False, True):
        for reverse_site in (False, True):
            transformed = raw
            if reverse_time:
                transformed = transformed[::-1]
            if reverse_site:
                transformed = transformed[:, ::-1]
            name = (
                f"time_{'reverse' if reverse_time else 'forward'}_"
                f"site_{'reverse' if reverse_site else 'forward'}"
            )
            candidates[name] = _candidate(
                transformed, initial_up, initial_down, kinetic,
                interaction, dt, stabilization_interval,
            )

    def residual(candidate: dict[str, Any]) -> tuple[float, float, float]:
        endpoint_energy = candidate["endpoint_energy"]
        central_energy = candidate["central_energy"]
        return (
            abs(candidate["endpoint_logabs"] -
                record.endpoint_logabs_d),
            max(
                abs(endpoint_energy[0] - record.endpoint_ekin),
                abs(endpoint_energy[1] - record.endpoint_epot),
                abs(endpoint_energy[2] - record.endpoint_etot),
            ),
            max(
                abs(central_energy[0] - record.central_ekin),
                abs(central_energy[1] - record.central_epot),
                abs(central_energy[2] - record.central_etot),
                abs(central_energy[3] - record.central_npart),
            ),
        )

    residuals = {name: residual(value)
                 for name, value in candidates.items()}
    matches = [
        name for name, value in candidates.items()
        if value["endpoint_sign"] == record.endpoint_sign
        and max(residuals[name]) < tolerance
    ]
    best_name = min(residuals, key=lambda name: max(residuals[name]))
    best = residuals[best_name]
    return {
        "matching_candidates": matches,
        "best_candidate": best_name,
        "endpoint_logabs_residual": best[0],
        "endpoint_energy_residual": best[1],
        "central_energy_residual": best[2],
        "candidate_residuals": residuals,
        "candidate_values": candidates,
        "archive_values": {
            "endpoint_sign": record.endpoint_sign,
            "endpoint_logabs": record.endpoint_logabs_d,
            "endpoint_energy": (
                record.endpoint_ekin,
                record.endpoint_epot,
                record.endpoint_etot,
            ),
            "central_energy": (
                record.central_ekin,
                record.central_epot,
                record.central_etot,
                record.central_npart,
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--up", type=Path, required=True)
    parser.add_argument("--down", type=Path, required=True)
    parser.add_argument("--site-map", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lx", type=int, default=4)
    parser.add_argument("--ly", type=int, default=4)
    parser.add_argument("--hopping", type=float, default=1.0)
    parser.add_argument("--interaction", type=float, default=4.0)
    parser.add_argument("--dt", type=float, default=0.05)
    parser.add_argument("--stabilize-every", type=int, default=10)
    parser.add_argument("--tolerance", type=float, default=2.0e-3)
    args = parser.parse_args()
    reader = ArchiveReader(args.archive)
    records = list(reader.records())
    if not records:
        raise ValueError("archive contains no complete records")
    result = validate_record(
        record=records[-1],
        up_path=args.up,
        down_path=args.down,
        site_map_path=args.site_map,
        lx=args.lx,
        ly=args.ly,
        hopping=args.hopping,
        interaction=args.interaction,
        dt=args.dt,
        stabilization_interval=args.stabilize_every,
        tolerance=args.tolerance,
    )
    result.update({
        "archive": str(args.archive),
        "sample_id": records[-1].sample_id,
        "tolerance": args.tolerance,
        "validated": result["matching_candidates"] == [
            "time_forward_site_forward"
        ],
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not result["validated"]:
        raise ValueError("field-order validation did not find one candidate")
    print(json.dumps({
        "validated": True,
        "candidate": result["matching_candidates"][0],
        "max_residual": max(
            result["endpoint_logabs_residual"],
            result["endpoint_energy_residual"],
            result["central_energy_residual"],
        ),
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
