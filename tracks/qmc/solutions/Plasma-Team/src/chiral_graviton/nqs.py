"""Symmetry-projected neural quantum states for small sphere systems."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import optimize, sparse

from .angular_momentum import highest_weight_basis, l2_operator
from .basis import FockBasis, SphereSystem
from .ed import interaction_pair_table
from .hamiltonian import build_hamiltonian
from .rotation_equivariance import nqs_multiplet_rotation_error, scalar_invariance_error


@dataclass(frozen=True)
class ProjectedSector:
    """Hamiltonian data for one exact total-L highest-weight sector."""

    total_l: int
    basis: FockBasis
    hamiltonian: sparse.csr_matrix
    projector_basis: np.ndarray
    features: np.ndarray

    @classmethod
    def build(cls, system: SphereSystem, total_l: int, interaction: str) -> ProjectedSector:
        basis = FockBasis(system, two_lz=2 * total_l)
        projector_basis = highest_weight_basis(basis)
        table = interaction_pair_table(system, interaction)
        hamiltonian = build_hamiltonian(basis, table)
        occupancy = basis.occupancy_matrix()
        features = occupancy - system.n_electrons / system.n_orbitals
        return cls(total_l, basis, hamiltonian, projector_basis, features)

    def project(self, raw_vector: np.ndarray) -> np.ndarray:
        return self.projector_basis @ (self.projector_basis.T @ raw_vector)


@dataclass(frozen=True)
class NQSEstimate:
    total_l: int
    energy: float
    variance: float
    l2_expectation: float
    residual_norm: float


@dataclass(frozen=True)
class NQSTrainingResult:
    success: bool
    message: str
    iterations: int
    objective: float
    ground: NQSEstimate
    graviton: NQSEstimate
    gap: float
    parameters: np.ndarray


@dataclass(frozen=True)
class MonteCarloEstimate:
    """Direct |psi|^2 sampling estimate in a finite Fock sector."""

    mean: float
    standard_error: float
    variance: float
    n_samples: int
    seed: int


class SharedProjectedMLP:
    """One-hidden-layer neural quantum state with exact angular-momentum projection.

    Occupation features feed a shared nonlinear trunk. Separate scalar heads
    produce raw amplitudes in the Lz=0 and Lz=2 Fock sectors. Projection onto
    ``ker(L_+)`` makes the final states exact L=0 and L=2 highest weights
    (output-state symmetry, not architectural input equivariance).

    Fermionic antisymmetry is exact because amplitudes multiply ordered Fock
    determinants.  Rotation equivariance of the resulting quantum states is
    verified by finite-rotation tests in ``rotation_equivariance.py`` rather
    than by a symmetry-constrained network architecture.
    """

    labels = (0, 2)

    def __init__(
        self,
        ground: ProjectedSector,
        graviton: ProjectedSector,
        *,
        hidden_width: int = 24,
        seed: int = 1729,
    ):
        if ground.basis.system != graviton.basis.system:
            raise ValueError("NQS sectors must use the same physical system")
        if (ground.total_l, graviton.total_l) != self.labels:
            raise ValueError("NQS requires L=0 and L=2 sectors")
        if hidden_width < 1:
            raise ValueError("hidden_width must be positive")
        self.sectors = {0: ground, 2: graviton}
        self.hidden_width = hidden_width
        self.n_features = ground.basis.system.n_orbitals
        rng = np.random.default_rng(seed)
        self.initial_parameters = rng.normal(scale=0.15, size=self.parameter_count)

    @classmethod
    def build(
        cls,
        system: SphereSystem,
        interaction: str = "coulomb",
        *,
        hidden_width: int = 24,
        seed: int = 1729,
    ) -> SharedProjectedMLP:
        return cls(
            ProjectedSector.build(system, 0, interaction),
            ProjectedSector.build(system, 2, interaction),
            hidden_width=hidden_width,
            seed=seed,
        )

    @property
    def parameter_count(self) -> int:
        trunk = self.hidden_width * self.n_features + self.hidden_width
        heads = len(self.labels) * (self.hidden_width + 1)
        return trunk + heads

    def _unpack(self, parameters: np.ndarray):
        parameters = np.asarray(parameters, dtype=np.float64)
        if parameters.shape != (self.parameter_count,):
            raise ValueError("parameter vector has the wrong shape")
        cursor = 0
        size = self.hidden_width * self.n_features
        weights = parameters[cursor : cursor + size].reshape(
            self.hidden_width, self.n_features
        )
        cursor += size
        bias = parameters[cursor : cursor + self.hidden_width]
        cursor += self.hidden_width
        heads: dict[int, tuple[np.ndarray, float]] = {}
        for label in self.labels:
            head_weights = parameters[cursor : cursor + self.hidden_width]
            cursor += self.hidden_width
            head_bias = float(parameters[cursor])
            cursor += 1
            heads[label] = (head_weights, head_bias)
        return weights, bias, heads

    def _forward(self, parameters: np.ndarray, total_l: int):
        weights, bias, heads = self._unpack(parameters)
        sector = self.sectors[total_l]
        hidden = np.tanh(sector.features @ weights.T + bias)
        head_weights, head_bias = heads[total_l]
        raw = hidden @ head_weights + head_bias
        vector = sector.project(raw)
        norm = float(vector @ vector)
        if norm < 1e-24:
            raise FloatingPointError("CG006: symmetry projection produced a zero state")
        return raw, hidden, vector / np.sqrt(norm)

    def vector(self, parameters: np.ndarray, total_l: int) -> np.ndarray:
        return self._forward(parameters, total_l)[2]

    def estimate(self, parameters: np.ndarray, total_l: int) -> NQSEstimate:
        sector = self.sectors[total_l]
        vector = self.vector(parameters, total_l)
        h_vector = sector.hamiltonian @ vector
        energy = float(vector @ h_vector)
        residual = h_vector - energy * vector
        variance = float(residual @ residual)
        l2 = l2_operator(sector.basis)
        l2_expectation = float(vector @ (l2 @ vector))
        return NQSEstimate(total_l, energy, variance, l2_expectation, np.sqrt(variance))

    def objective_and_gradient(self, parameters: np.ndarray) -> tuple[float, np.ndarray]:
        weights, bias, heads = self._unpack(parameters)
        del weights, bias
        total_objective = 0.0
        gradient_weights = np.zeros((self.hidden_width, self.n_features))
        gradient_bias = np.zeros(self.hidden_width)
        gradient_heads: dict[int, tuple[np.ndarray, float]] = {
            label: (np.zeros(self.hidden_width), 0.0) for label in self.labels
        }

        for total_l in self.labels:
            sector = self.sectors[total_l]
            raw, hidden, vector = self._forward(parameters, total_l)
            del raw
            h_vector = sector.hamiltonian @ vector
            energy = float(vector @ h_vector)
            total_objective += 0.5 * energy

            # For normalized real psi, dE/dpsi = 2(H-E)psi. Backpropagate
            # through the orthogonal symmetry projector and normalization.
            grad_vector = h_vector - energy * vector
            grad_raw = sector.project(grad_vector)
            raw_norm = np.linalg.norm(sector.project(
                hidden @ heads[total_l][0] + heads[total_l][1]
            ))
            grad_raw = grad_raw / raw_norm

            head_weights, _ = heads[total_l]
            grad_head_weights = hidden.T @ grad_raw
            grad_head_bias = float(np.sum(grad_raw))
            grad_hidden_pre = (
                grad_raw[:, None] * head_weights[None, :] * (1.0 - hidden * hidden)
            )
            gradient_weights += grad_hidden_pre.T @ sector.features
            gradient_bias += np.sum(grad_hidden_pre, axis=0)
            gradient_heads[total_l] = (grad_head_weights, grad_head_bias)

        chunks = [gradient_weights.ravel(), gradient_bias]
        for label in self.labels:
            chunks.extend([gradient_heads[label][0], np.array([gradient_heads[label][1]])])
        return total_objective, np.concatenate(chunks)

    def fit(
        self,
        parameters: np.ndarray | None = None,
        *,
        max_iterations: int = 400,
        gradient_tolerance: float = 1e-9,
    ) -> NQSTrainingResult:
        start = self.initial_parameters if parameters is None else np.asarray(parameters)

        result = optimize.minimize(
            fun=lambda p: self.objective_and_gradient(p),
            x0=start,
            method="L-BFGS-B",
            jac=True,
            options={"maxiter": max_iterations, "gtol": gradient_tolerance, "ftol": 1e-13},
        )
        ground = self.estimate(result.x, 0)
        graviton = self.estimate(result.x, 2)
        return NQSTrainingResult(
            success=bool(result.success),
            message=str(result.message),
            iterations=int(result.nit),
            objective=float(result.fun),
            ground=ground,
            graviton=graviton,
            gap=graviton.energy - ground.energy,
            parameters=np.asarray(result.x),
        )

    def irrep_error(self, parameters: np.ndarray) -> float:
        """Return max |<L^2>-L(L+1)| for the projected output states.

        This certifies that the output state vector belongs to the correct
        SO(3) irreducible representation after projection onto ker(L_+).
        It measures a property of the projected state, not of the raw
        neural-network architecture.
        """

        errors = []
        for total_l in self.labels:
            estimate = self.estimate(parameters, total_l)
            errors.append(abs(estimate.l2_expectation - total_l * (total_l + 1)))
        return max(errors)

    def scalar_rotation_error(self, parameters: np.ndarray) -> float:
        """Verify the L=0 ground state is invariant under all rotations.

        Checks that the state is annihilated by L_- (in addition to the
        L_+ annihilation enforced by projection).  Together these prove
        the state is a true SO(3) scalar.

        Returns
        -------
        float
            ``||L_-|psi_0>||``.  Zero for a genuine L=0 state.
        """

        ground_sector = self.sectors[0]
        vector = self.vector(parameters, 0)
        return scalar_invariance_error(ground_sector.basis, vector)

    def multiplet_rotation_error(
        self,
        parameters: np.ndarray,
        *,
        axis: tuple[float, float, float] = (1.0, 2.0, 3.0),
        angle: float = 0.371,
    ) -> float:
        """Build the L=2 multiplet and verify finite-rotation behaviour.

        Constructs all five M components from the NQS highest-weight state
        via exact lowering, then applies a generic-axis rotation to a
        superposition and compares against the expected spin-2 Wigner-D
        transformation.

        This is a genuine input-sensitive rotation test: if the NQS assigned
        wrong relative amplitudes to different basis states, the multiplet
        members would not transform correctly under the many-body rotation
        operator.

        Returns
        -------
        float
            ``||R_actual|psi> - D^{L=2}(R)|psi>||`` for a fixed
            superposition of multiplet components.
        """

        sector = self.sectors[2]
        vector = self.vector(parameters, 2)
        return nqs_multiplet_rotation_error(
            sector.basis, vector, 2, axis=axis, angle=angle
        )

    def sample_energy(
        self,
        parameters: np.ndarray,
        total_l: int,
        *,
        n_samples: int = 50_000,
        seed: int = 1729,
    ) -> MonteCarloEstimate:
        """Estimate energy by independent sampling from the enumerated NQS.

        This is a posterior energy-estimator diagnostic at fixed optimized
        parameters. It draws independent samples from enumerated |psi|^2, so
        no burn-in or autocorrelation correction is needed. It is not a
        scalable VMC training loop and does not include optimizer or ansatz
        uncertainty.
        """

        if n_samples < 2:
            raise ValueError("n_samples must be at least two")
        sector = self.sectors[total_l]
        vector = self.vector(parameters, total_l)
        probabilities = np.abs(vector) ** 2
        probabilities /= probabilities.sum()
        h_vector = sector.hamiltonian @ vector
        support = vector != 0.0
        local_energy = np.zeros_like(vector, dtype=np.float64)
        local_energy[support] = np.real(h_vector[support] / vector[support])
        rng = np.random.default_rng(seed)
        indices = rng.choice(vector.size, size=n_samples, replace=True, p=probabilities)
        samples = local_energy[indices]
        variance = float(np.var(samples, ddof=1))
        return MonteCarloEstimate(
            mean=float(np.mean(samples)),
            standard_error=float(np.sqrt(variance / n_samples)),
            variance=variance,
            n_samples=n_samples,
            seed=seed,
        )
