"""Independent verifier for the #117 LJ924 frontier track."""

from __future__ import annotations

import hashlib
import json
import os

import lj_ref
import numpy as np

N = 924
RESULT_FILE = "candidate_result.json"
VERIFY_FILE = "verify_result.json"
E_TABLE = -6558.225148
E_STRICT_BASELINE = -6558.225147857512
E_923 = -6552.722599848312
E_925 = -6565.533987552818


def _coords_hash(coords: np.ndarray) -> str:
    """Permutation-invariant hash for detecting repeated search behavior."""
    centered = coords - coords.mean(axis=0)
    rounded = np.round(centered, decimals=8)
    order = np.lexsort((rounded[:, 2], rounded[:, 1], rounded[:, 0]))
    return hashlib.sha256(rounded[order].tobytes()).hexdigest()[:16]


def verify() -> dict:
    if not os.path.exists(RESULT_FILE):
        return {"valid": False, "error": "missing candidate_result.json"}
    try:
        with open(RESULT_FILE, encoding="utf-8") as handle:
            payload = json.load(handle)
        coords = np.asarray(payload["best_coords_flat"], dtype=float).reshape(N, 3)
        claimed = float(payload["best_energy"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return {"valid": False, "error": f"bad result: {exc}"}

    energy = float(lj_ref.lj_energy_fast(coords))
    forces = lj_ref.lj_forces(coords)
    force_norm = float(np.linalg.norm(forces))
    max_atom_force = float(np.max(np.linalg.norm(forces, axis=1)))
    finite = bool(np.all(np.isfinite(coords)) and np.isfinite(energy))
    d = coords[:, None, :] - coords[None, :, :]
    r2 = np.sum(d * d, axis=-1)
    np.fill_diagonal(r2, np.inf)
    min_distance = float(np.sqrt(np.min(r2)))
    claim_consistent = abs(claimed - energy) < 1e-7

    # Kiessling average-pair-energy necessary condition: v(N-1) <= v(N) <= v(N+1).
    def avg_pair(e: float, n: int) -> float:
        return 2.0 * e / (n * (n - 1))

    v_prev = avg_pair(E_923, 923)
    v_here = avg_pair(energy, N)
    v_next = avg_pair(E_925, 925)
    monotonic_ok = v_prev <= v_here <= v_next
    valid = (
        finite
        and min_distance > 0.7
        and claim_consistent
        and max_atom_force < 1e-8
        and monotonic_ok
    )

    proposal_valid = False
    proposal_error = ""
    proposal_energy = 0.0
    proposal_force_norm = 0.0
    proposal_max_atom_force = 0.0
    proposal_min_distance = 0.0
    proposal_claim_consistent = False
    proposal_coords_hash = ""
    try:
        proposal = np.asarray(payload["proposal_coords_flat"], dtype=float).reshape(N, 3)
        proposal_claimed = float(payload["proposal_energy"])
        proposal_energy = float(lj_ref.lj_energy_fast(proposal))
        proposal_forces = lj_ref.lj_forces(proposal)
        proposal_force_norm = float(np.linalg.norm(proposal_forces))
        proposal_max_atom_force = float(
            np.max(np.linalg.norm(proposal_forces, axis=1))
        )
        proposal_d = proposal[:, None, :] - proposal[None, :, :]
        proposal_r2 = np.sum(proposal_d * proposal_d, axis=-1)
        np.fill_diagonal(proposal_r2, np.inf)
        proposal_min_distance = float(np.sqrt(np.min(proposal_r2)))
        proposal_claim_consistent = abs(proposal_claimed - proposal_energy) < 1e-7
        proposal_valid = bool(
            np.all(np.isfinite(proposal))
            and np.isfinite(proposal_energy)
            and proposal_min_distance > 0.7
            and proposal_claim_consistent
            and proposal_energy < 0.0
        )
        proposal_coords_hash = _coords_hash(proposal)
    except (KeyError, TypeError, ValueError) as exc:
        proposal_error = f"bad/missing exploration proposal: {exc}"

    submission_coords_hash = _coords_hash(coords)
    return {
        "valid": valid,
        "error": "" if valid else "strict geometry/energy/force gate failed",
        "N": N,
        "energy_recomputed": energy,
        "claimed_energy": claimed,
        "delta_vs_table": E_TABLE - energy,
        "delta_vs_strict_baseline": E_STRICT_BASELINE - energy,
        "force_norm": force_norm,
        "max_atom_force": max_atom_force,
        "min_distance": min_distance,
        "claim_consistent": claim_consistent,
        "monotonicity_ok": monotonic_ok,
        "n_force_evals": int(payload.get("n_force_evals", 0)),
        "search_mode": str(payload.get("search_mode", "unknown")),
        "submission_fallback": bool(payload.get("submission_fallback", False)),
        "submission_coords_hash": submission_coords_hash,
        "strict_improvement": energy < E_STRICT_BASELINE - 1e-8,
        "attempted_modes": [
            str(mode) for mode in payload.get("attempted_modes", [])
        ],
        "unbiased": bool(payload.get("unbiased", False)),
        "proposal_valid": proposal_valid,
        "proposal_error": proposal_error,
        "proposal_energy_recomputed": proposal_energy,
        "proposal_delta_vs_strict_baseline": E_STRICT_BASELINE - proposal_energy,
        "proposal_force_norm": proposal_force_norm,
        "proposal_max_atom_force": proposal_max_atom_force,
        "proposal_min_distance": proposal_min_distance,
        "proposal_claim_consistent": proposal_claim_consistent,
        "proposal_coords_hash": proposal_coords_hash,
        "proposal_differs_from_submission": (
            bool(proposal_coords_hash)
            and proposal_coords_hash != submission_coords_hash
        ),
        "proposal_search_mode": str(payload.get("proposal_search_mode", "unknown")),
    }


if __name__ == "__main__":
    result = verify()
    with open(VERIFY_FILE, "w", encoding="utf-8") as handle:
        json.dump(result, handle)
    print(json.dumps(result), flush=True)
