"""Parent-channel chirality evaluated from trained projected NQS states."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .basis import SphereSystem
from .chirality import ChiralGravitonResponse, chiral_graviton_response
from .nqs import NQSTrainingResult, SharedProjectedMLP
from .scalable_nqs import SparseProjectedMLP


ProjectionKind = Literal["dense", "sparse"]


@dataclass(frozen=True)
class NQSChiralityResult:
    """A trained NQS pair together with its parent-channel response."""

    training: NQSTrainingResult
    response: ChiralGravitonResponse
    projection: ProjectionKind
    irrep_error: float


def train_nqs_chirality(
    system: SphereSystem,
    interaction: str = "coulomb",
    *,
    projection: ProjectionKind = "dense",
    hidden_width: int = 24,
    seed: int = 1729,
    max_iterations: int = 400,
    maximum_variance: float = 1e-8,
) -> NQSChiralityResult:
    """Train shared ``L=0/2`` heads and evaluate their chiral response.

    Unlike the ED ``chirality`` command, both the ground state and the lowest
    spin-two pole supplied to the metric probe come directly from the trained
    neural variational family. The operator remains the documented
    ``m_rel=1<->3`` Laughlin parent-channel probe.
    """

    if maximum_variance <= 0.0:
        raise ValueError("maximum_variance must be positive")
    if projection == "dense":
        model_class = SharedProjectedMLP
        build_options: dict[str, object] = {}
    elif projection == "sparse":
        model_class = SparseProjectedMLP
        build_options = {
            "solver_tolerance": 2e-14,
            "certificate_tolerance": 1e-12,
        }
    else:
        raise ValueError(f"unknown projection: {projection}")

    model = model_class.build(
        system,
        interaction,
        hidden_width=hidden_width,
        seed=seed,
        **build_options,
    )
    training = model.fit(max_iterations=max_iterations)
    if not training.success:
        raise RuntimeError(f"CG005: NQS optimizer failed: {training.message}")
    largest_variance = max(training.ground.variance, training.graviton.variance)
    if largest_variance > maximum_variance:
        raise RuntimeError(
            "CG008: NQS variance exceeds acceptance threshold: "
            f"{largest_variance:.3e} > {maximum_variance:.3e}"
        )
    irrep_error = model.irrep_error(training.parameters)
    if irrep_error > 1e-7:
        raise RuntimeError(f"CG006: projected-state irrep error {irrep_error:.3e}")

    ground_sector = model.sectors[0]
    graviton_sector = model.sectors[2]
    response = chiral_graviton_response(
        ground_sector.basis,
        model.vector(training.parameters, 0),
        graviton_sector.basis,
        model.vector(training.parameters, 2),
    )
    return NQSChiralityResult(training, response, projection, irrep_error)
