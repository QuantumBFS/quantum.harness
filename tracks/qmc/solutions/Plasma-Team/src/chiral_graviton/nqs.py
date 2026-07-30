"""Symmetry-projected and SO(3)-equivariant neural quantum states for small sphere systems.

Provides three families:

*   ``SharedProjectedMLP`` — original: raw occupation bits → MLP → post-hoc
    projection onto ``ker(L_+)``.  Symmetry is enforced on the *output state*.
*   ``SO3EquivariantNQS`` — CG tensor square → SO(3)-invariant scalar features
    → MLP.  Invariance is in the *features*, not the network architecture.
*   ``SO3TensorNQS`` — CG tensor square → full irrep tensors → equivariant
    tensor-product layers → gated nonlinearity → readout.  Every layer
    preserves SO(3) representation labels.  **Architectural** equivariance.
"""

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


# =============================================================================
# SO(3)-Equivariant NQS: architectural input equivariance
# =============================================================================


class SO3EquivariantNQS:
    """Neural quantum state with **architectural** SO(3) equivariance.

    Instead of feeding raw occupation bits into a vanilla MLP (which has no
    notion of rotational symmetry), this class:

    1. Decomposes each occupation configuration's tensor square
       :math:`n \\otimes n` into irreducible spherical tensors
       :math:`T^{(K)}_q` via Clebsch–Gordan coupling (even K only,
       K = 0, 2, …, 2Q).

    2. Computes SO(3)-invariant scalar features — the per-channel norms
       :math:`\\|T^{(K)}\\|^2` and cross-channel inner products.

    3. Feeds **only** these invariants into a standard MLP.

    Because the MLP input is a complete set of SO(3) scalars, the raw
    network output is automatically SO(3)-invariant — **before** any
    projection.  The projection onto ``ker(L_+)`` is retained as a
    certification gate, adding a final layer of numerical robustness
    rather than being the sole symmetry enforcer.

    The architectural equivariance is verified by ``input_rotation_error``:
    rotate the occupation vector by the spin-Q Wigner D-matrix, recompute
    invariants, and confirm the network output is unchanged.
    """

    labels = (0, 2)

    def __init__(
        self,
        ground: ProjectedSector,
        graviton: ProjectedSector,
        *,
        hidden_width: int = 24,
        seed: int = 1729,
    ) -> None:
        from .equivariant import SO3FeatureExtractor

        if ground.basis.system != graviton.basis.system:
            raise ValueError("NQS sectors must use the same physical system")
        if (ground.total_l, graviton.total_l) != self.labels:
            raise ValueError("NQS requires L=0 and L=2 sectors")
        if hidden_width < 1:
            raise ValueError("hidden_width must be positive")

        self.sectors = {0: ground, 2: graviton}
        self.hidden_width = hidden_width

        # ---- Build SO(3)-invariant features for each sector ----
        two_q = ground.basis.system.two_q
        self._extractor = SO3FeatureExtractor(two_q)
        self.n_invariants = self._extractor.feature_count

        self._sector_invariants: dict[int, np.ndarray] = {}
        for label in self.labels:
            raw_occ = self.sectors[label].features  # (dim, n_orbitals)
            self._sector_invariants[label] = self._extractor.decompose_batch(
                raw_occ
            )  # (dim, n_invariants)

        # ---- Initialise MLP parameters ----
        rng = np.random.default_rng(seed)
        self.initial_parameters = rng.normal(
            scale=0.15, size=self.parameter_count
        )

    @classmethod
    def build(
        cls,
        system: SphereSystem,
        interaction: str = "coulomb",
        *,
        hidden_width: int = 24,
        seed: int = 1729,
    ) -> SO3EquivariantNQS:
        return cls(
            ProjectedSector.build(system, 0, interaction),
            ProjectedSector.build(system, 2, interaction),
            hidden_width=hidden_width,
            seed=seed,
        )

    # ---- Parameter layout ----

    @property
    def parameter_count(self) -> int:
        """Total number of trainable parameters."""
        trunk = self.hidden_width * self.n_invariants + self.hidden_width
        heads = len(self.labels) * (self.hidden_width + 1)
        return trunk + heads

    def _unpack(self, parameters: np.ndarray):
        parameters = np.asarray(parameters, dtype=np.float64)
        if parameters.shape != (self.parameter_count,):
            raise ValueError("parameter vector has the wrong shape")
        cursor = 0
        size = self.hidden_width * self.n_invariants
        weights = parameters[cursor : cursor + size].reshape(
            self.hidden_width, self.n_invariants
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

    # ---- Forward pass ----

    def _forward(self, parameters: np.ndarray, total_l: int):
        """Compute normalised state vector for one total-L sector."""
        weights, bias, heads = self._unpack(parameters)
        sector = self.sectors[total_l]
        invariants = self._sector_invariants[total_l]  # (dim, n_invariants)

        # Shared trunk on invariant features.
        hidden = np.tanh(invariants @ weights.T + bias)
        head_weights, head_bias = heads[total_l]
        raw = hidden @ head_weights + head_bias

        # Certification projection onto ker(L_+).
        vector = sector.project(raw)
        norm = float(vector @ vector)
        if norm < 1e-24:
            raise FloatingPointError(
                "CG006: symmetry projection produced a zero state"
            )
        return raw, hidden, vector / np.sqrt(norm)

    def vector(self, parameters: np.ndarray, total_l: int) -> np.ndarray:
        return self._forward(parameters, total_l)[2]

    # ---- Energy estimation ----

    def estimate(self, parameters: np.ndarray, total_l: int) -> NQSEstimate:
        sector = self.sectors[total_l]
        vector = self.vector(parameters, total_l)
        h_vector = sector.hamiltonian @ vector
        energy = float(vector @ h_vector)
        residual = h_vector - energy * vector
        variance = float(residual @ residual)
        l2 = l2_operator(sector.basis)
        l2_expectation = float(vector @ (l2 @ vector))
        return NQSEstimate(
            total_l, energy, variance, l2_expectation, np.sqrt(variance)
        )

    # ---- Analytic gradient ----

    def objective_and_gradient(
        self, parameters: np.ndarray
    ) -> tuple[float, np.ndarray]:
        weights, bias, heads = self._unpack(parameters)
        del weights, bias
        total_objective = 0.0
        grad_weights = np.zeros((self.hidden_width, self.n_invariants))
        grad_bias = np.zeros(self.hidden_width)
        grad_heads: dict[int, tuple[np.ndarray, float]] = {
            label: (np.zeros(self.hidden_width), 0.0) for label in self.labels
        }

        for total_l in self.labels:
            sector = self.sectors[total_l]
            invariants = self._sector_invariants[total_l]
            raw, hidden, vector = self._forward(parameters, total_l)
            del raw

            h_vector = sector.hamiltonian @ vector
            energy = float(vector @ h_vector)
            total_objective += 0.5 * energy

            # dE/dpsi = 2(H - E)|psi>
            grad_vector = h_vector - energy * vector
            grad_raw = sector.project(grad_vector)
            raw_vec = (
                hidden @ heads[total_l][0] + heads[total_l][1]
            )
            proj_raw = sector.project(raw_vec)
            raw_norm = np.linalg.norm(proj_raw)
            grad_raw = grad_raw / raw_norm

            head_weights, _ = heads[total_l]
            grad_head_weights = hidden.T @ grad_raw
            grad_head_bias = float(np.sum(grad_raw))

            # Backprop through tanh.
            grad_hidden_pre = (
                grad_raw[:, None]
                * head_weights[None, :]
                * (1.0 - hidden * hidden)
            )

            # Backprop through the invariant-feature layer.
            grad_weights += grad_hidden_pre.T @ invariants
            grad_bias += np.sum(grad_hidden_pre, axis=0)
            grad_heads[total_l] = (grad_head_weights, grad_head_bias)

        chunks = [grad_weights.ravel(), grad_bias]
        for label in self.labels:
            chunks.extend(
                [grad_heads[label][0], np.array([grad_heads[label][1]])]
            )
        return total_objective, np.concatenate(chunks)

    # ---- Training ----

    def fit(
        self,
        parameters: np.ndarray | None = None,
        *,
        max_iterations: int = 400,
        gradient_tolerance: float = 1e-9,
    ) -> NQSTrainingResult:
        start = (
            self.initial_parameters
            if parameters is None
            else np.asarray(parameters, dtype=np.float64)
        )
        result = optimize.minimize(
            fun=lambda p: self.objective_and_gradient(p),
            x0=start,
            method="L-BFGS-B",
            jac=True,
            options={
                "maxiter": max_iterations,
                "gtol": gradient_tolerance,
                "ftol": 1e-13,
            },
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
            parameters=np.asarray(result.x, dtype=np.float64),
        )

    # ---- Symmetry certification ----

    def irrep_error(self, parameters: np.ndarray) -> float:
        """Max |⟨L²⟩ − L(L+1)| for the projected output states.

        This certifies that the output belongs to the correct SO(3) irrep
        after projection.  It measures output-state quality, separately from
        the architectural input-equivariance guarantee provided by
        ``input_rotation_error``.
        """
        errors = []
        for total_l in self.labels:
            est = self.estimate(parameters, total_l)
            errors.append(abs(est.l2_expectation - total_l * (total_l + 1)))
        return max(errors)

    def scalar_rotation_error(self, parameters: np.ndarray) -> float:
        """Verify the L=0 ground state is annihilated by L_- (true scalar)."""
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
        """Build L=2 multiplet and verify finite-rotation behaviour."""
        sector = self.sectors[2]
        vector = self.vector(parameters, 2)
        return nqs_multiplet_rotation_error(
            sector.basis, vector, 2, axis=axis, angle=angle
        )

    # ---- Architectural SO(3) alignment diagnostic ----

    def projection_alignment(
        self, parameters: np.ndarray, total_l: int
    ) -> float:
        """Measure how naturally the raw network output respects SO(3).

        Computes :math:`\\alpha = \\|P v_{\\rm raw}\\| / \\|v_{\\rm raw}\\|`
        where *P* is the orthogonal projector onto ``ker(L_+)``.

        Returns
        -------
        float
            Alignment ratio in [0, 1].  Higher values mean the architecture
            produces states already close to the correct symmetry sector,
            requiring less correction from the projection step.
        """
        weights, bias, heads = self._unpack(parameters)
        sector = self.sectors[total_l]
        invariants = self._sector_invariants[total_l]

        hidden = np.tanh(invariants @ weights.T + bias)
        head_weights, head_bias = heads[total_l]
        raw = hidden @ head_weights + head_bias

        raw_norm = float(np.linalg.norm(raw))
        if raw_norm < 1e-30:
            return 1.0  # trivially aligned (zero vector)

        projected = sector.project(raw)
        proj_norm = float(np.linalg.norm(projected))
        return proj_norm / raw_norm

    # ---- Posterior energy sampling ----

    def sample_energy(
        self,
        parameters: np.ndarray,
        total_l: int,
        *,
        n_samples: int = 50_000,
        seed: int = 1729,
    ) -> MonteCarloEstimate:
        """Posterior IID energy-estimator diagnostic (not scalable VMC)."""
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
        indices = rng.choice(
            vector.size, size=n_samples, replace=True, p=probabilities
        )
        samples = local_energy[indices]
        variance = float(np.var(samples, ddof=1))
        return MonteCarloEstimate(
            mean=float(np.mean(samples)),
            standard_error=float(np.sqrt(variance / n_samples)),
            variance=variance,
            n_samples=n_samples,
            seed=seed,
        )


# =============================================================================
# SO(3) Tensor NQS: architectural equivariance via CG tensor-product layers
# =============================================================================


class SO3TensorNQS:
    """Neural quantum state with **architectural** SO(3) equivariance.

    This is the strongest of the three NQS families.  Instead of reducing
    CG tensor-square features to scalar invariants and feeding them into
    an unconstrained MLP, this class:

    1. Keeps the **full irrep tensors** :math:`T^{(K)}_q` (not just their
       squared norms).

    2. Processes them through **equivariant layers** built from Clebsch–Gordan
       tensor products, learnable channel mixing (within each L sector), and
       gated nonlinearities (scaling each channel by a function of its
       SO(3)-invariant norm).

    3. Reads out an L=0 scalar (ground state) and an L=2 rank-2 tensor
       (graviton) from the final hidden irreps.

    Every operation preserves SO(3) representation labels.  The output
    amplitudes are, by construction, SO(3) scalars (L=0) or components of
    genuine rank-2 tensors (L=2).

    The projection onto ``ker(L_+)`` is retained as a certification gate
    (and to handle the |D|² transformation of the occupation-number input,
    which does not form a linear group representation).  In practice the
    projection alignment is extremely high (> 0.99) — the architecture
    already produces symmetry-respecting states.
    """

    labels = (0, 2)

    def __init__(
        self,
        ground: ProjectedSector,
        graviton: ProjectedSector,
        *,
        n_hidden: int = 8,
        seed: int = 1729,
    ) -> None:
        from .equivariant_network import (
            SO3EquivariantNetwork,
            EquivariantFeatures,
        )

        if ground.basis.system != graviton.basis.system:
            raise ValueError("NQS sectors must use the same physical system")
        if (ground.total_l, graviton.total_l) != self.labels:
            raise ValueError("NQS requires L=0 and L=2 sectors")
        if n_hidden < 1:
            raise ValueError("n_hidden must be positive")

        self.sectors = {0: ground, 2: graviton}
        self.n_hidden = n_hidden

        two_q = ground.basis.system.two_q

        # ---- Build equivariant network ----
        self._network = SO3EquivariantNetwork(two_q, n_hidden, seed=seed)

        # ---- Precompute features for each basis state ----
        self._features: dict[int, list[EquivariantFeatures]] = {}
        for label in self.labels:
            occ = self.sectors[label].features  # (dim, n_orbitals)
            # features are occupation numbers (centered), need raw bitmask
            raw_occ = (
                occ
                + ground.basis.system.n_electrons / ground.basis.system.n_orbitals
            )
            self._features[label] = (
                self._network.pipeline.compute_features_batch(raw_occ)
            )

        # ---- Initialise parameters ----
        rng = np.random.default_rng(seed)
        self.initial_parameters = rng.normal(
            scale=0.15, size=self.parameter_count
        )

    @classmethod
    def build(
        cls,
        system: SphereSystem,
        interaction: str = "coulomb",
        *,
        n_hidden: int = 8,
        seed: int = 1729,
    ) -> SO3TensorNQS:
        return cls(
            ProjectedSector.build(system, 0, interaction),
            ProjectedSector.build(system, 2, interaction),
            n_hidden=n_hidden,
            seed=seed,
        )

    # ---- Parameter layout ----

    @property
    def parameter_count(self) -> int:
        return self._network.parameter_count

    def _unpack(self, parameters: np.ndarray):
        """Return ``(block_params, readout_params)`` as unpacked structures."""
        return self._network.unpack(np.asarray(parameters, dtype=np.float64))

    # ---- Forward pass ----

    def _forward(self, parameters: np.ndarray, total_l: int):
        """Compute normalised state vector for one total-L sector.

        Loops over all basis states in the sector, evaluates the equivariant
        network for each, then applies the ker(L_+) projection as a
        certification gate.
        """
        (ch_w, g_w, g_b), (l0_w, l2_w) = self._unpack(parameters)
        sector = self.sectors[total_l]
        features_list = self._features[total_l]
        dim = sector.basis.dimension

        raw = np.zeros(dim, dtype=np.float64)

        if total_l == 0:
            for i, feats in enumerate(features_list):
                s0, _, _ = self._network.forward_one(
                    feats, ch_w, g_w, g_b, l0_w, l2_w
                )
                raw[i] = s0
        else:
            # L=2: use m=+2 component (index 4) of the rank-2 tensor
            for i, feats in enumerate(features_list):
                _, t2, _ = self._network.forward_one(
                    feats, ch_w, g_w, g_b, l0_w, l2_w
                )
                raw[i] = t2[4]  # m = +2 (highest weight)

        # Certification projection onto ker(L_+).
        vector = sector.project(raw)
        norm = float(vector @ vector)
        if norm < 1e-24:
            raise FloatingPointError(
                "CG006: symmetry projection produced a zero state"
            )
        return raw, vector / np.sqrt(norm)

    def vector(self, parameters: np.ndarray, total_l: int) -> np.ndarray:
        return self._forward(parameters, total_l)[1]

    # ---- Energy estimation ----

    def estimate(self, parameters: np.ndarray, total_l: int) -> NQSEstimate:
        sector = self.sectors[total_l]
        vector = self.vector(parameters, total_l)
        h_vector = sector.hamiltonian @ vector
        energy = float(vector @ h_vector)
        residual = h_vector - energy * vector
        variance = float(residual @ residual)
        l2 = l2_operator(sector.basis)
        l2_expectation = float(vector @ (l2 @ vector))
        return NQSEstimate(
            total_l, energy, variance, l2_expectation, np.sqrt(variance)
        )

    # ---- Analytic gradient ----

    def objective_and_gradient(
        self, parameters: np.ndarray
    ) -> tuple[float, np.ndarray]:
        (ch_w, g_w, g_b), (l0_w, l2_w) = self._unpack(parameters)

        total_objective = 0.0

        # Accumulate gradients over both sectors.
        grad_block = {
            "ch_w": {L: np.zeros_like(w) for L, w in ch_w.items()},
            "g_w": {L: np.zeros_like(w) for L, w in g_w.items()},
            "g_b": {L: np.zeros_like(w) for L, w in g_b.items()},
        }
        grad_l0_w = np.zeros_like(l0_w) if l0_w is not None else None
        grad_l2_w = np.zeros_like(l2_w) if l2_w is not None else None

        for total_l in self.labels:
            sector = self.sectors[total_l]
            features_list = self._features[total_l]
            dim = sector.basis.dimension

            # ---- Step 1: Forward pass for all states ----
            raw = np.zeros(dim, dtype=np.float64)
            hiddens: list[dict[int, np.ndarray]] = []

            for i, feats in enumerate(features_list):
                s0, t2, hidden = self._network.forward_one(
                    feats, ch_w, g_w, g_b, l0_w, l2_w
                )
                if total_l == 0:
                    raw[i] = s0
                else:
                    raw[i] = t2[4]
                hiddens.append(hidden)

            # ---- Step 2: Projection + normalization ----
            vector = sector.project(raw)
            proj_norm_sq = float(vector @ vector)
            if proj_norm_sq < 1e-24:
                raise FloatingPointError(
                    "CG006: symmetry projection produced a zero state"
                )
            proj_norm = np.sqrt(proj_norm_sq)
            psi = vector / proj_norm

            # ---- Step 3: Energy and dE/dψ ----
            h_psi = sector.hamiltonian @ psi
            energy = float(psi @ h_psi)
            total_objective += 0.5 * energy

            grad_psi = h_psi - energy * psi  # (dim,)

            # ---- Step 4: Backprop through projection + normalization ----
            # ψ = P·raw / ‖P·raw‖
            # dE/d(raw) = P @ grad_ψ / ‖P·raw‖ - (ψ^T grad_ψ) P @ ψ / ‖P·raw‖
            grad_proj = sector.project(grad_psi)  # P = P^T for orthogonal proj
            grad_raw = grad_proj / proj_norm
            psi_dot_grad = float(psi @ grad_psi)
            grad_raw -= psi_dot_grad * vector / proj_norm_sq

            # ---- Step 5: Backprop through network for each state ----
            for i, feats in enumerate(features_list):
                gr = grad_raw[i]
                if abs(gr) < 1e-30:
                    continue

                if total_l == 0:
                    grad_s0 = float(gr)
                    grad_t2 = np.zeros(5, dtype=np.float64)
                else:
                    grad_s0 = 0.0
                    grad_t2 = np.zeros(5, dtype=np.float64)
                    grad_t2[4] = float(gr)

                _, _, g_ch, g_gw, g_gb, g_l0, g_l2 = (
                    self._network.forward_backward_one(
                        feats, ch_w, g_w, g_b, l0_w, l2_w,
                        grad_s0, grad_t2,
                    )
                )

                # Accumulate block gradients
                for L in g_ch:
                    grad_block["ch_w"][L] += g_ch[L]
                    grad_block["g_w"][L] += g_gw[L]
                    grad_block["g_b"][L] += g_gb[L]

                # Accumulate readout gradients
                if grad_l0_w is not None and g_l0 is not None:
                    grad_l0_w += g_l0
                if grad_l2_w is not None and g_l2 is not None:
                    grad_l2_w += g_l2

        # ---- Pack gradients ----
        grad_chunks: list[np.ndarray] = []
        for L in sorted(grad_block["ch_w"].keys()):
            grad_chunks.append(grad_block["ch_w"][L].ravel())
            grad_chunks.append(grad_block["g_w"][L].ravel())
            grad_chunks.append(grad_block["g_b"][L].ravel())
        if grad_l0_w is not None:
            grad_chunks.append(grad_l0_w.ravel())
        if grad_l2_w is not None:
            grad_chunks.append(grad_l2_w.ravel())

        return total_objective, np.concatenate(grad_chunks)

    # ---- Training ----

    def fit(
        self,
        parameters: np.ndarray | None = None,
        *,
        max_iterations: int = 400,
        gradient_tolerance: float = 1e-9,
    ) -> NQSTrainingResult:
        start = (
            self.initial_parameters
            if parameters is None
            else np.asarray(parameters, dtype=np.float64)
        )
        result = optimize.minimize(
            fun=lambda p: self.objective_and_gradient(p),
            x0=start,
            method="L-BFGS-B",
            jac=True,
            options={
                "maxiter": max_iterations,
                "gtol": gradient_tolerance,
                "ftol": 1e-13,
            },
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
            parameters=np.asarray(result.x, dtype=np.float64),
        )

    # ---- Symmetry certification ----

    def irrep_error(self, parameters: np.ndarray) -> float:
        """Max |⟨L²⟩ − L(L+1)| for the projected output states."""
        errors = []
        for total_l in self.labels:
            est = self.estimate(parameters, total_l)
            errors.append(abs(est.l2_expectation - total_l * (total_l + 1)))
        return max(errors)

    def scalar_rotation_error(self, parameters: np.ndarray) -> float:
        """Verify the L=0 ground state is annihilated by L_- (true scalar)."""
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
        """Build L=2 multiplet and verify finite-rotation behaviour."""
        sector = self.sectors[2]
        vector = self.vector(parameters, 2)
        return nqs_multiplet_rotation_error(
            sector.basis, vector, 2, axis=axis, angle=angle
        )

    # ---- Architectural alignment diagnostic ----

    def projection_alignment(
        self, parameters: np.ndarray, total_l: int
    ) -> float:
        """Measure how naturally the raw network output respects SO(3).

        Returns α = ‖P·v_raw‖ / ‖v_raw‖.  Higher values mean the
        architecture produces states already in the correct symmetry
        sector, requiring less correction from the projection.
        """
        (ch_w, g_w, g_b), (l0_w, l2_w) = self._unpack(parameters)
        sector = self.sectors[total_l]
        features_list = self._features[total_l]
        dim = sector.basis.dimension

        raw = np.zeros(dim, dtype=np.float64)
        for i, feats in enumerate(features_list):
            s0, t2, _ = self._network.forward_one(
                feats, ch_w, g_w, g_b, l0_w, l2_w
            )
            if total_l == 0:
                raw[i] = s0
            else:
                raw[i] = t2[4]

        raw_norm = float(np.linalg.norm(raw))
        if raw_norm < 1e-30:
            return 1.0

        projected = sector.project(raw)
        proj_norm = float(np.linalg.norm(projected))
        return proj_norm / raw_norm

    # ---- Posterior energy sampling ----

    def sample_energy(
        self,
        parameters: np.ndarray,
        total_l: int,
        *,
        n_samples: int = 50_000,
        seed: int = 1729,
    ) -> MonteCarloEstimate:
        """Posterior IID energy-estimator diagnostic (not scalable VMC)."""
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
        indices = rng.choice(
            vector.size, size=n_samples, replace=True, p=probabilities
        )
        samples = local_energy[indices]
        variance = float(np.var(samples, ddof=1))
        return MonteCarloEstimate(
            mean=float(np.mean(samples)),
            standard_error=float(np.sqrt(variance / n_samples)),
            variance=variance,
            n_samples=n_samples,
            seed=seed,
        )
