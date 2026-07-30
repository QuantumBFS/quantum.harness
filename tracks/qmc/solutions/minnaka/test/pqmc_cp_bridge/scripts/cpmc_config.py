#!/usr/bin/env python3
"""Frozen parameter contract for mixed-boundary CPMC-Lab runs."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path


@dataclass(frozen=True)
class CpmcContract:
    lx: int
    ly: int
    n_up: int
    n_down: int
    dt: float
    ltrot: int
    nfield: int
    stabilize_every: int
    energy_every: int
    primary_pc_every: int
    strict_ground_state_claim_allowed: bool
    input_sha256: dict[str, str]
    site_permutation: tuple[int, ...]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _locate(root: Path, direct: str, conventional: str) -> Path:
    candidate = root / direct
    return candidate if candidate.is_file() else root / conventional


def _site_permutation(path: Path) -> tuple[int, ...]:
    rows = [
        tuple(int(value) for value in line.split())
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    if len(rows) != 16 or any(len(row) != 4 for row in rows):
        raise ValueError("CPMC site map is not a 16-site permutation")
    if {row[0] for row in rows} != set(range(1, 17)) \
            or {row[1] for row in rows} != set(range(16)):
        raise ValueError("CPMC site map is not a permutation")
    for _alf, cpp, x, y in rows:
        if cpp != y * 4 + x or not (0 <= x < 4 and 0 <= y < 4):
            raise ValueError("CPMC site permutation is not row-major")
    return tuple(row[1] for row in sorted(rows))


def load_cpmc_contract(root: Path) -> CpmcContract:
    paths = {
        "selected_projection": _locate(
            root, "selected_projection.json",
            "results/selected_projection.json",
        ),
        "trial_manifest": _locate(
            root, "trial_manifest.json",
            "assets/trials/trial_manifest.json",
        ),
        "field_order": _locate(
            root, "field_order.json", "contracts/field_order.json"
        ),
        "strata_contract": _locate(
            root, "strata_contract.json", "results/strata_contract.json"
        ),
        "site_map": _locate(
            root, "site_map.dat", "assets/trials/site_map.dat"
        ),
    }
    if not all(path.is_file() for path in paths.values()):
        missing = [name for name, path in paths.items() if not path.is_file()]
        raise ValueError(f"missing CPMC contract inputs: {missing}")
    selected = json.loads(
        paths["selected_projection"].read_text(encoding="utf-8")
    )
    dt = float(selected["dt"])
    ltrot = int(selected["ltrot_star"])
    nfield = int(selected["nfield_star"])
    theta = int(selected["theta_star"])
    beta = float(selected.get("beta", 1.0))
    expected_ltrot = round((2 * theta + beta) / dt)
    if ltrot != expected_ltrot or nfield != 16 * ltrot:
        raise ValueError("CPMC Ltrot/nfield disagrees with selected projection")
    hashes = {name: _sha(path) for name, path in paths.items()}
    required_hashes = {
        "trial_manifest_sha256": "trial_manifest",
        "field_order_sha256": "field_order",
        "strata_contract_sha256": "strata_contract",
    }
    for selected_key, input_name in required_hashes.items():
        if selected_key in selected \
                and selected[selected_key] != hashes[input_name]:
            raise ValueError(f"{input_name} hash mismatch")
    if selected.get("trial_manifest_sha256") != hashes["trial_manifest"]:
        raise ValueError("trial manifest hash mismatch")
    status = selected.get("status")
    if status not in {
        "target_reached",
        "max_theta_fallback",
        "reference_confirmation_failed",
    }:
        raise ValueError("unknown selected projection status")
    return CpmcContract(
        lx=4,
        ly=4,
        n_up=8,
        n_down=8,
        dt=dt,
        ltrot=ltrot,
        nfield=nfield,
        stabilize_every=5,
        energy_every=5,
        primary_pc_every=5,
        strict_ground_state_claim_allowed=(status == "target_reached"),
        input_sha256=hashes,
        site_permutation=_site_permutation(paths["site_map"]),
    )


def production_parameters(
    contract: CpmcContract, nwalkers: int
) -> dict[str, int]:
    if nwalkers <= 0:
        raise ValueError("walker count must be positive")
    block_steps = 20
    equilibrium_blocks = math.ceil(contract.ltrot / block_steps)
    return {
        "mode": "production",
        "Nw": nwalkers,
        "N_blksteps": block_steps,
        "N_eqblk": equilibrium_blocks,
        "N_blk": 50,
        "stabilize_every": contract.stabilize_every,
        "energy_every": contract.energy_every,
        "pc_every": contract.primary_pc_every,
    }


def fixed_horizon_parameters(
    contract: CpmcContract,
    nwalkers: int,
    pc_every: int,
    seed: int,
) -> dict[str, int]:
    if nwalkers <= 0 or pc_every <= 0 or seed <= 0:
        raise ValueError("fixed-horizon walkers, PC interval, and seed are positive")
    return {
        "mode": "fixed_horizon",
        "Nw": nwalkers,
        "steps": contract.ltrot,
        "pc_every": pc_every,
        "stabilize_every": contract.stabilize_every,
        "energy_every": contract.energy_every,
        "seed": seed,
    }
