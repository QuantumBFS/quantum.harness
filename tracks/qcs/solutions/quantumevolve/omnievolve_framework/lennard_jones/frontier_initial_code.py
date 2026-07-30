"""#117 large-N frontier seed: audit and improve the monoatomic LJ924 record.

Why N=924:
* the official 562–1000 table is primarily a single 2004 lattice-seeded survey;
* E(924) has the largest positive local interpolation residual in N=310–1000
  after correcting the documented N=447 transcription typo;
* it is therefore an honest audit target, not a claim that the record is wrong.

The seed performs a strict re-minimization of the published configuration.  OmniEvolve
may replace the neighborhood proposals, optimizer, structural representation, and
schedule, but it must retain the output contract and the exact all-pairs LJ potential.
The output contract has two channels: ``best_*`` is the verifier-valid submission,
while ``proposal_*`` must expose the best genuinely searched non-incumbent structure.
Never hide a failed search by returning only the incumbent.

Promising mutations:
* remove weakly-bound surface atoms from LJ925 and relax back to N=924;
* add atoms at bridge/hollow/top sites of LJ923;
* relocate weakly-bound atoms within LJ924;
* introduce icosahedral/decahedral/fcc competing seeds instead of assuming one motif;
* use growth/crossover moves followed by a strict full-potential FIRE polish.
"""

from __future__ import annotations

import hashlib
import json
import os
import time

import lj_ref
import numpy as np
from scipy.optimize import minimize

N = 924
TIME_BUDGET_SEC = float(os.environ.get("LJ_FRONTIER_TIME_BUDGET_SEC", "150"))
INCUMBENT_FILE = os.environ.get("LJ924_INCUMBENT_FILE", "924.TXT")
OUTPUT_FILE = "candidate_result.json"
IMPROVEMENT_TOL = 1e-8
MAX_ATOM_FORCE_TOL = 1e-8
_START = time.perf_counter()


def _time_left() -> float:
    return TIME_BUDGET_SEC - (time.perf_counter() - _START)


class Counter:
    def __init__(self) -> None:
        self.energy = 0
        self.force = 0

    @property
    def total(self) -> int:
        return self.energy + self.force


def lbfgs_polish(
    coords: np.ndarray,
    counter: Counter,
    maxiter: int = 300,
) -> np.ndarray:
    """Fast approach to the local basin; FIRE below supplies the strict force gate."""

    def objective(flat: np.ndarray) -> float:
        counter.energy += 1
        return lj_ref.lj_energy_fast(flat.reshape(-1, 3))

    def gradient(flat: np.ndarray) -> np.ndarray:
        counter.force += 1
        return -lj_ref.lj_forces(flat.reshape(-1, 3)).ravel()

    result = minimize(
        objective,
        coords.ravel(),
        jac=gradient,
        method="L-BFGS-B",
        options={
            "maxiter": maxiter,
            "ftol": 1e-15,
            "gtol": 1e-11,
            "maxls": 40,
            "maxcor": 20,
        },
    )
    polished = result.x.reshape(-1, 3)
    polished -= polished.mean(axis=0)
    return polished


def fire_polish(
    coords: np.ndarray,
    counter: Counter,
    max_steps: int = 6000,
    force_tol: float = 1e-9,
) -> np.ndarray:
    """Force-based polish that is not stopped by tiny float64 energy changes."""

    coords = coords.copy()
    coords -= coords.mean(axis=0)
    velocity = np.zeros_like(coords)
    dt, dt_max, alpha = 0.01, 0.05, 0.1
    positive_steps = 0
    for step in range(max_steps):
        counter.force += 1
        forces = lj_ref.lj_forces(coords)
        max_atom_force = float(np.max(np.linalg.norm(forces, axis=1)))
        if max_atom_force < force_tol or _time_left() < 3.0:
            break
        velocity += dt * forces
        power = float(np.sum(velocity * forces))
        if power > 0.0:
            positive_steps += 1
            v_norm = float(np.linalg.norm(velocity))
            f_norm = float(np.linalg.norm(forces))
            if v_norm > 0.0 and f_norm > 0.0:
                velocity = (1.0 - alpha) * velocity + alpha * (v_norm / f_norm) * forces
            if positive_steps > 5:
                dt = min(dt * 1.1, dt_max)
                alpha *= 0.99
        else:
            positive_steps = 0
            velocity.fill(0.0)
            dt *= 0.5
            alpha = 0.1
        coords += dt * velocity
        coords -= coords.mean(axis=0)
        if step % 250 == 0:
            print(
                f"FIRE step={step} max_force={max_atom_force:.3e} "
                f"time_left={_time_left():.1f}s",
                flush=True,
            )
    return coords


def _pair_contributions(coords: np.ndarray) -> np.ndarray:
    """Per-atom sum of LJ pair terms; the least-bound atom has the largest value."""
    diff = coords[:, None, :] - coords[None, :, :]
    r2 = np.einsum("ijk,ijk->ij", diff, diff)
    np.fill_diagonal(r2, np.inf)
    inv6 = r2 ** -3
    return np.sum(4.0 * (inv6 * inv6 - inv6), axis=1)


def _insertion_energy(coords: np.ndarray, point: np.ndarray) -> float:
    r2 = np.sum((coords - point) ** 2, axis=1)
    if float(np.min(r2)) < 0.72:
        return float("inf")
    inv6 = r2 ** -3
    return float(np.sum(4.0 * (inv6 * inv6 - inv6)))


def _surface_site_proposals(coords: np.ndarray) -> list[np.ndarray]:
    """Generate top/bridge proposals around the outer shell."""
    centered = coords - coords.mean(axis=0)
    radii = np.linalg.norm(centered, axis=1)
    surface = np.argsort(radii)[-48:]
    proposals: list[np.ndarray] = []
    for idx in surface:
        direction = centered[idx] / radii[idx]
        proposals.append(centered[idx] + 1.05 * direction)
    for pos, i in enumerate(surface):
        for j in surface[pos + 1 :]:
            delta = centered[i] - centered[j]
            distance = float(np.linalg.norm(delta))
            if 0.95 <= distance <= 1.35:
                midpoint = 0.5 * (centered[i] + centered[j])
                norm = float(np.linalg.norm(midpoint))
                if norm > 0.0:
                    height = np.sqrt(max(0.05, 1.05**2 - (0.5 * distance) ** 2))
                    proposals.append(midpoint + height * midpoint / norm)
    return proposals


def _growth_seeds(coords923: np.ndarray, count: int) -> list[tuple[str, np.ndarray]]:
    """Add one atom at several low-energy, geometrically distinct surface sites."""
    centered = coords923 - coords923.mean(axis=0)
    proposals = _surface_site_proposals(centered)
    ranked = sorted(proposals, key=lambda point: _insertion_energy(centered, point))
    selected: list[np.ndarray] = []
    for point in ranked:
        if all(float(np.linalg.norm(point - other)) > 0.35 for other in selected):
            selected.append(point)
        if len(selected) >= count:
            break
    seeds: list[tuple[str, np.ndarray]] = []
    for rank, point in enumerate(selected, start=1):
        grown = np.vstack([centered, point])
        grown -= grown.mean(axis=0)
        seeds.append((f"923-growth-{rank}", grown))
    return seeds


def _relocation_seeds(
    coords924: np.ndarray,
    count: int,
    rng: np.random.Generator,
) -> list[tuple[str, np.ndarray]]:
    """Move weakly-bound atoms to candidate-specific alternative surface sites."""
    centered = coords924 - coords924.mean(axis=0)
    weak = np.argsort(_pair_contributions(centered))[::-1][:24]
    seeds: list[tuple[str, np.ndarray]] = []
    for rank in range(1, count + 1):
        remove = int(rng.choice(weak))
        reduced = np.delete(centered, remove, axis=0)
        old_position = centered[remove]
        ranked = sorted(
            _surface_site_proposals(reduced),
            key=lambda point: _insertion_energy(reduced, point),
        )
        alternatives = [
            point
            for point in ranked
            if float(np.linalg.norm(point - old_position)) > 0.6
        ][:48]
        if not alternatives:
            continue
        site_index = int(rng.integers(0, min(24, len(alternatives))))
        relocated = np.vstack([reduced, alternatives[site_index]])
        relocated -= relocated.mean(axis=0)
        seeds.append(
            (
                f"924-relocate-{rank}-atom-{remove}-site-{site_index}",
                relocated,
            )
        )
    return seeds


def _shrink_seeds(coords925: np.ndarray, count: int) -> list[tuple[str, np.ndarray]]:
    """Remove several weakly bound atoms from the independently optimized LJ925."""
    contributions = _pair_contributions(coords925)
    removals = np.argsort(contributions)[::-1][:count]
    seeds: list[tuple[str, np.ndarray]] = []
    for rank, remove in enumerate(removals, start=1):
        shrunk = np.delete(coords925, int(remove), axis=0)
        shrunk -= shrunk.mean(axis=0)
        seeds.append((f"925-shrink-{rank}-atom-{int(remove)}", shrunk))
    return seeds


def run() -> dict:
    incumbent_raw = np.loadtxt(INCUMBENT_FILE, dtype=float)
    if incumbent_raw.shape != (N, 3):
        raise ValueError(f"expected {(N, 3)}, got {incumbent_raw.shape}")
    counter = Counter()
    # The published text coordinates are rounded and do not themselves satisfy
    # the strict force gate.  Reconstruct a high-precision incumbent every run
    # so a failed structural move always falls back to a verifier-valid result.
    incumbent = lbfgs_polish(incumbent_raw, counter)
    incumbent = fire_polish(incumbent, counter)
    incumbent_energy = float(lj_ref.lj_energy_fast(incumbent))
    counter.energy += 1
    incumbent_forces = lj_ref.lj_forces(incumbent)
    counter.force += 1
    incumbent_max_force = float(
        np.max(np.linalg.norm(incumbent_forces, axis=1))
    )
    if incumbent_max_force >= MAX_ATOM_FORCE_TOL:
        raise RuntimeError(
            "strict incumbent reconstruction failed: "
            f"max_atom_force={incumbent_max_force:.3e}"
        )
    print(
        f"strict incumbent: E={incumbent_energy:.12f} "
        f"max_force={incumbent_max_force:.3e}",
        flush=True,
    )

    # Compare several issue-motivated, independently sourced morphology moves.
    # Each seed gets a bounded local relaxation before the best basin receives
    # the strict force polish.
    incumbent_dir = os.path.dirname(INCUMBENT_FILE) or "."
    seed_count = max(2, int(os.environ.get("LJ_FRONTIER_SEED_COUNT", "6")))
    run_key = os.environ.get("LJ_FRONTIER_RUN_KEY", "baseline")
    run_seed = int.from_bytes(
        hashlib.sha256(run_key.encode("utf-8")).digest()[:8],
        "big",
    )
    rng = np.random.default_rng(run_seed)
    relocation_count = max(1, seed_count - 2)
    growth_count = 1
    shrink_count = 1
    relocation_seeds = _relocation_seeds(incumbent, relocation_count, rng)
    seeds = _growth_seeds(
        np.loadtxt(os.path.join(incumbent_dir, "923.TXT"), dtype=float),
        growth_count,
    )
    seeds.extend(
        _shrink_seeds(
            np.loadtxt(os.path.join(incumbent_dir, "925.TXT"), dtype=float),
            shrink_count,
        )
    )
    seeds.extend(relocation_seeds)
    rough = [
        (float(lj_ref.lj_energy_fast(seed)), name, seed) for name, seed in seeds
    ]
    counter.energy += len(rough)
    print(
        "structural seeds: "
        + ", ".join(f"{name}={energy:.9f}" for energy, name, _ in rough),
        flush=True,
    )

    refined: list[tuple[float, str, np.ndarray]] = []
    relocation_rough = sorted(
        (item for item in rough if item[1].startswith("924-relocate-")),
        key=lambda item: item[0],
    )
    other_rough = sorted(
        (item for item in rough if not item[1].startswith("924-relocate-")),
        key=lambda item: item[0],
    )
    # Always test two candidate-specific reconstructions before returning to
    # deterministic growth/shrink seeds, preventing strategy collapse.
    screening_order = relocation_rough[:2] + sorted(
        relocation_rough[2:] + other_rough,
        key=lambda item: item[0],
    )
    attempted_modes: list[str] = []
    for rough_energy, mode, seed in screening_order:
        if _time_left() < 25.0:
            print(f"seed screening stopped with {_time_left():.1f}s left", flush=True)
            break
        attempted_modes.append(mode)
        coords = lbfgs_polish(seed, counter, maxiter=80)
        energy = float(lj_ref.lj_energy_fast(coords))
        counter.energy += 1
        refined.append((energy, mode, coords))
        print(
            f"screened {mode}: rough={rough_energy:.9f} relaxed={energy:.12f} "
            f"time_left={_time_left():.1f}s",
            flush=True,
        )

    candidate_energy, mode, coords = min(
        refined or rough,
        key=lambda item: item[0],
    )
    proposal_coords = coords.copy()
    proposal_energy = candidate_energy
    if candidate_energy < incumbent_energy - IMPROVEMENT_TOL and _time_left() >= 3.0:
        coords = fire_polish(coords, counter)
        strict_energy = float(lj_ref.lj_energy_fast(coords))
        counter.energy += 1
        counter.force += 1
        strict_forces = lj_ref.lj_forces(coords)
        strict_max_force = float(np.max(np.linalg.norm(strict_forces, axis=1)))
        # Even when the strict submission gate rejects this structure, expose it
        # to the independent verifier as the search proposal for the next
        # generation's dense learning signal.
        proposal_coords = coords.copy()
        proposal_energy = strict_energy
        if (
            strict_energy < incumbent_energy - IMPROVEMENT_TOL
            and strict_max_force < MAX_ATOM_FORCE_TOL
        ):
            energy = strict_energy
            search_mode = f"independent-{mode}-verified-improvement"
            unbiased = True
        else:
            coords = incumbent.copy()
            energy = incumbent_energy
            search_mode = (
                f"independent-{mode}-strict-rejected-incumbent-retained"
            )
            unbiased = False
    else:
        coords = incumbent.copy()
        energy = incumbent_energy
        search_mode = f"independent-{mode}-tested-incumbent-retained"
        unbiased = False
    return {
        "N": N,
        "best_energy": energy,
        "best_coords_flat": coords.ravel().tolist(),
        "proposal_energy": proposal_energy,
        "proposal_coords_flat": proposal_coords.ravel().tolist(),
        "proposal_search_mode": mode,
        "submission_fallback": not unbiased,
        "n_force_evals": counter.total,
        "search_mode": search_mode,
        "attempted_modes": attempted_modes,
        "unbiased": unbiased,
    }


if __name__ == "__main__":
    result = run()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as handle:
        json.dump(result, handle)
    print(
        f"LJ{N} frontier seed: E={result['best_energy']:.12f} "
        f"evals={result['n_force_evals']} mode={result['search_mode']}",
        flush=True,
    )
