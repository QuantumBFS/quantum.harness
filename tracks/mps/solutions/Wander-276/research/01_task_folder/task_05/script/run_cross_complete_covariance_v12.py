#!/usr/bin/env python3
"""Complete three-pairing covariance cumulants for opened v12 panel ensembles."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import norm

from lgeth.complete_covariance_oracle import leave_diagonal_augmented_wick
from lgeth.cumulant_inference import (
    aggregate_cumulant,
    directional_pseudovalues,
)
from lgeth.full_wick_ustat import (
    ResponseFactors,
    self_tensor,
    symmetrized_pairings,
)
from lgeth.lattice_susy_parent import (
    lattice_susy_response,
    normalized_cycle_couplings,
    solve_cycle_union_frame,
)
from run_lattice_susy_geometric_eth_v10 import REGISTERED_SEED as LATTICE_SEED
from run_lattice_susy_geometric_eth_v10 import tangent_panel
from run_moore_read_geometric_eth_v9 import REGISTERED_SEED as MOORE_SEED
from run_moore_read_geometric_eth_v9 import case_for_particle_number


VERSION = "v12"
SCRIPT_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = SCRIPT_ROOT / "output"
REALIZATION_COUNT = 24
LABEL_COUNT = 2
FAMILY_ALPHA = 0.05


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fixed_invariant_direction(labels: int = LABEL_COUNT) -> np.ndarray:
    """Return the frozen sum of the two proper-complex Kronecker pairings."""

    count = int(labels)
    if count < 2:
        raise ValueError("complete-covariance direction requires two labels")
    identity = np.eye(count, dtype=complex)
    direction = np.einsum("ab,cd->abcd", identity, identity) + np.einsum(
        "ad,cb->abcd", identity, identity
    )
    return np.asarray(direction / np.linalg.norm(direction), dtype=complex)


def complete_covariance_summary(
    samples: tuple[ResponseFactors, ...],
    *,
    block_size: int,
    oracle: bool = False,
) -> dict[str, Any]:
    """Compute the complete U-statistic and frozen directional jackknife."""

    records = tuple(samples)
    if len(records) < 4:
        raise ValueError("complete covariance requires at least four panels")
    if any(record.label_count != LABEL_COUNT for record in records):
        raise ValueError("complete covariance requires the fixed two-label view")
    self_tensors = np.asarray([self_tensor(record) for record in records])
    pair_sums = {
        (first, second): symmetrized_pairings(
            records[first],
            records[second],
            block_size=int(block_size),
        )
        for first in range(len(records))
        for second in range(first + 1, len(records))
    }
    estimate = aggregate_cumulant(self_tensors, pair_sums)
    direction = fixed_invariant_direction(LABEL_COUNT)
    directional = directional_pseudovalues(self_tensors, pair_sums, direction)
    scale = max(float(np.linalg.norm(estimate.wick_total)), np.finfo(float).tiny)
    normalized_norm = float(np.linalg.norm(estimate.cumulant) / scale)
    normalized_estimate = float(directional.estimate / scale)
    normalized_error = float(directional.standard_error / scale)
    z_score = normalized_estimate / normalized_error
    p_value = float(norm.sf(z_score))
    critical = float(norm.ppf(1.0 - FAMILY_ALPHA))
    interval_low = normalized_estimate - critical * normalized_error
    oracle_error: float | None = None
    if oracle:
        oracle_wick = leave_diagonal_augmented_wick(records)
        oracle_error = float(
            np.linalg.norm(oracle_wick - estimate.wick_pairings)
            / max(float(np.linalg.norm(estimate.wick_pairings)), np.finfo(float).tiny)
        )
    checks = {
        "complete_unordered_pair_grid": bool(
            estimate.unordered_pair_count
            == len(records) * (len(records) - 1) // 2
        ),
        "three_wick_pairings": bool(estimate.wick_pairings.shape[0] == 3),
        "finite_complete_cumulant": bool(
            np.all(np.isfinite(estimate.cumulant.real))
            and np.all(np.isfinite(estimate.cumulant.imag))
        ),
        "nonzero_wick_normalizer": bool(scale > np.finfo(float).tiny),
        "nonzero_jackknife_variance": bool(normalized_error > 0.0),
        "oracle_agreement": bool(
            oracle_error is None or oracle_error < 2e-10
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(f"complete covariance audit failed: {checks}")
    return {
        "realization_count": len(records),
        "unordered_pair_count": estimate.unordered_pair_count,
        "pairing_count": 3,
        "label_count": LABEL_COUNT,
        "ambient_dimension": records[0].ambient_dimension,
        "fiber_rank": records[0].target_rank,
        "normalized_cumulant_norm": normalized_norm,
        "directional_estimate": normalized_estimate,
        "standard_error": normalized_error,
        "z_score": z_score,
        "one_sided_p_value": p_value,
        "one_sided_interval_low": interval_low,
        "positive_directional_gate": bool(
            p_value < FAMILY_ALPHA and interval_low > 0.0
        ),
        "oracle_relative_error": oracle_error,
        "checks": checks,
    }


def lattice_susy_panel_ensemble(
    cycles: int,
    *,
    count: int = REALIZATION_COUNT,
) -> tuple[ResponseFactors, ...]:
    """Build fixed-coupling, exchangeable local tangent panels."""

    number = int(count)
    component_count = int(cycles)
    couplings = normalized_cycle_couplings(
        component_count,
        int(LATTICE_SEED) + component_count,
    )
    frame = solve_cycle_union_frame(component_count, couplings)
    samples: list[ResponseFactors] = []
    for panel in range(number):
        tangents = tangent_panel(
            component_count,
            couplings,
            "local",
            seed=int(LATTICE_SEED) + 1_000 * component_count + panel,
        )
        response = lattice_susy_response(frame, couplings, tangents)
        if not all(response.checks.values()):
            raise RuntimeError("lattice-SUSY response failed before covariance")
        samples.append(
            ResponseFactors(
                frame=frame.projector_frame,
                channels=np.asarray(response.total[:LABEL_COUNT], dtype=complex),
            )
        )
    return tuple(samples)


def moore_read_panel_ensemble(
    particles: int,
    root: Path = OUTPUT_ROOT,
) -> tuple[ResponseFactors, ...]:
    """Load a complete 24-panel Moore--Read thin-factor ensemble."""

    case = case_for_particle_number(int(particles))
    kernel = (
        Path(root)
        / "moore_read_v9"
        / "kernels"
        / f"N{case.N}_flux{case.n_flux}_v9.npz"
    )
    with np.load(kernel, allow_pickle=False) as arrays:
        frame = np.asarray(arrays["frame"], dtype=complex)
    samples: list[ResponseFactors] = []
    for panel in range(REALIZATION_COUNT):
        path = (
            Path(root)
            / "moore_read_v9"
            / "panels"
            / f"N{case.N}_flux{case.n_flux}_panel{panel:02d}_v9.npz"
        )
        if not path.is_file():
            raise FileNotFoundError(f"missing registered Moore--Read panel: {path}")
        with np.load(path, allow_pickle=False) as arrays:
            channels = np.asarray(arrays["response_channels"], dtype=complex)
        samples.append(
            ResponseFactors(frame=frame, channels=channels[:LABEL_COUNT])
        )
    return tuple(samples)


def run(root: Path = OUTPUT_ROOT) -> dict[str, Any]:
    """Run accepted local complete-covariance cases."""

    started = time.perf_counter()
    cases: dict[str, dict[str, Any]] = {}
    for cycles in (1, 2, 3):
        samples = lattice_susy_panel_ensemble(cycles)
        cases[f"lattice_susy_m{cycles}"] = complete_covariance_summary(
            samples,
            block_size=max(2, samples[0].target_rank),
            oracle=cycles == 1,
        )
    for particles in (4, 6):
        moore_samples = moore_read_panel_ensemble(particles, root)
        cases[f"moore_read_N{particles}"] = complete_covariance_summary(
            moore_samples,
            block_size=64,
            oracle=False,
        )
    result = {
        "version": VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "protocol": {
            "realization_unit": "fixed-base local tangent panel",
            "realization_count": REALIZATION_COUNT,
            "label_count": LABEL_COUNT,
            "direction": "fixed_two_Kronecker_invariants",
            "null_parameters_refit": False,
            "wick_pairings": 3,
            "family_alpha": FAMILY_ALPHA,
            "claim_boundary": (
                "Inference is conditional on panel exchangeability and does not "
                "replace an independent disorder or Hamiltonian ensemble."
            ),
        },
        "cases": cases,
        "all_checks_pass": all(
            all(case["checks"].values()) for case in cases.values()
        ),
        "runtime_seconds": time.perf_counter() - started,
    }
    path = Path(root) / f"cross_complete_covariance_{VERSION}.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    result["sha256"] = _sha256(path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=OUTPUT_ROOT)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
