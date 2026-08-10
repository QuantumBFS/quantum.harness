"""Angular-momentum-resolved exact-diagonalization oracle."""

from __future__ import annotations

from collections.abc import Mapping
import base64
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import subprocess
from typing import Any

import numpy as np
from scipy import sparse as scipy_sparse
from scipy.linalg import expm
from scipy.sparse.linalg import eigsh
from scipy.special import eval_legendre

from challenge15.angular import (
    _canonical_thin_subspace_basis,
    _fixed_sector_l2_sparse,
    _sparse_target_l2_basis,
    SPARSE_GRAM_TOLERANCE,
    SPARSE_L2_RESIDUAL_TOLERANCE,
    SPARSE_LADDER_TOLERANCE,
    angular_operators,
    target_irrep_isometry_sparse,
    verify_ladder_multiplet,
)
from challenge15.coulomb import (
    many_body_coulomb,
    orbital_coulomb_tensor,
    pair_pseudopotentials,
    pseudopotential_coulomb_tensor,
)
from challenge15.fermions import (
    DeterminantBasis,
    iter_ordered_determinant_blocks,
)
from challenge15.spec import SphereSpec


_QUADRATURE_ROTATION_CACHE: dict[
    tuple[int, int, int, int], tuple[np.ndarray, ...]
] = {}
_QUADRATURE_CACHE_HITS = 0
_QUADRATURE_CACHE_MISSES = 0


def clear_quadrature_cache() -> None:
    global _QUADRATURE_CACHE_HITS, _QUADRATURE_CACHE_MISSES
    _QUADRATURE_ROTATION_CACHE.clear()
    _QUADRATURE_CACHE_HITS = 0
    _QUADRATURE_CACHE_MISSES = 0


def quadrature_cache_info() -> dict[str, int]:
    return {
        "hits": _QUADRATURE_CACHE_HITS,
        "misses": _QUADRATURE_CACHE_MISSES,
        "entries": len(_QUADRATURE_ROTATION_CACHE),
    }


def _cached_beta_rotations(
    spec: SphereSpec,
    n_beta: int,
    start: int = 0,
    stop: int | None = None,
) -> tuple[np.ndarray, ...]:
    global _QUADRATURE_CACHE_HITS, _QUADRATURE_CACHE_MISSES
    final = n_beta if stop is None else stop
    if not 0 <= start < final <= n_beta:
        raise ValueError("cached beta rotation range is invalid")
    key = (spec.two_q, int(n_beta), int(start), int(final))
    cached = _QUADRATURE_ROTATION_CACHE.get(key)
    if cached is not None:
        _QUADRATURE_CACHE_HITS += 1
        return cached
    beta_nodes, _ = np.polynomial.legendre.leggauss(n_beta)
    jy = _single_particle_jy(spec)
    rotations = tuple(
        _sealed_array(expm(-1j * float(np.arccos(node)) * jy))
        for node in beta_nodes[start:final]
    )
    if len(_QUADRATURE_ROTATION_CACHE) >= 16:
        _QUADRATURE_ROTATION_CACHE.pop(next(iter(_QUADRATURE_ROTATION_CACHE)))
    _QUADRATURE_ROTATION_CACHE[key] = rotations
    _QUADRATURE_CACHE_MISSES += 1
    return rotations


@dataclass(frozen=True, slots=True)
class _PaddedQuadratureBlock:
    indices: np.ndarray
    nodes: np.ndarray
    weights: np.ndarray
    rotations: np.ndarray
    valid: np.ndarray

    def __post_init__(self) -> None:
        width = self.valid.size
        if (
            self.indices.shape != (width,)
            or self.nodes.shape != (width,)
            or self.weights.shape != (width,)
            or self.rotations.ndim != 3
            or self.rotations.shape[0] != width
            or self.rotations.shape[1] != self.rotations.shape[2]
            or self.valid.dtype != np.bool_
        ):
            raise ValueError("quadrature block arrays must have one fixed width")
        for name in ("indices", "nodes", "weights", "rotations", "valid"):
            object.__setattr__(
                self, name, _sealed_array(np.asarray(getattr(self, name)))
            )


def _iter_padded_quadrature_blocks(
    spec: SphereSpec, n_beta: int, block_size: int
):
    """Yield fixed-width beta quadrature blocks with explicit validity masks."""

    if not isinstance(spec, SphereSpec):
        raise TypeError("spec must be a SphereSpec")
    _validate_positive_block(n_beta, "n_beta")
    _validate_positive_block(block_size, "block_size")
    beta_nodes, beta_weights = np.polynomial.legendre.leggauss(n_beta)
    for start in range(0, n_beta, block_size):
        stop = min(start + block_size, n_beta)
        count = stop - start
        indices = np.full(block_size, -1, dtype=np.int64)
        nodes = np.zeros(block_size, dtype=np.float64)
        weights = np.zeros(block_size, dtype=np.float64)
        rotations = np.broadcast_to(
            np.eye(spec.orbital_count, dtype=np.complex128),
            (block_size, spec.orbital_count, spec.orbital_count),
        ).copy()
        valid = np.zeros(block_size, dtype=np.bool_)
        indices[:count] = np.arange(start, stop, dtype=np.int64)
        nodes[:count] = beta_nodes[start:stop]
        weights[:count] = beta_weights[start:stop]
        rotations[:count] = np.asarray(
            _cached_beta_rotations(spec, n_beta, start, stop),
            dtype=np.complex128,
        )
        valid[:count] = True
        yield _PaddedQuadratureBlock(
            indices=indices,
            nodes=nodes,
            weights=weights,
            rotations=rotations,
            valid=valid,
        )


@dataclass(frozen=True, slots=True)
class SectorResult:
    angular_momentum: int
    multiplicity: int
    energy: float
    spectrum: tuple[float, ...]
    residual: float
    mean_l2: float
    l2_variance: float
    l2_target_deviation_squared: float


@dataclass(frozen=True, slots=True)
class SparseSymmetryDiagnostic:
    angular_momentum: int
    multiplicity: int
    gram_defect: float
    l2_target_residual: float
    ladder_intertwining_residual: float
    row_pivots: tuple[int, ...]
    workspace_elements_upper_bound: int
    dense_projector_allocated: bool


@dataclass(frozen=True, slots=True)
class LowEnergyState:
    energy: float
    angular_momentum: int
    eigenpair_residual: float
    l2_residual: float
    l2_variance: float
    state: np.ndarray

    def __post_init__(self) -> None:
        vector = np.asarray(self.state, dtype=np.complex128)
        if vector.ndim != 1:
            raise ValueError("low-energy state vector must be one-dimensional")
        object.__setattr__(self, "state", _sealed_array(vector))


@dataclass(frozen=True, slots=True)
class DenseOracleDiagnostics:
    hamiltonian_hermiticity_defect: float
    l2_hermiticity_defect: float
    sector_multiplicity_sum: int
    m_zero_dimension: int


@dataclass(frozen=True, slots=True)
class _GroundDiagnostics:
    energy: float
    residual: float
    mean_l2: float
    l2_variance: float
    l2_target_deviation_squared: float
    state: np.ndarray


@dataclass(frozen=True, slots=True)
class ExactSectorEigensystem:
    """Stored ED data consumed by acceptance without another eigensolve."""

    angular_momentum: int
    isometry: np.ndarray
    hamiltonian: np.ndarray
    l2_operator: np.ndarray
    eigenvalues: np.ndarray
    eigenvectors: np.ndarray

    def __post_init__(self) -> None:
        arrays = {
            "isometry": np.asarray(self.isometry, dtype=np.complex128),
            "hamiltonian": np.asarray(self.hamiltonian, dtype=np.complex128),
            "l2_operator": np.asarray(self.l2_operator, dtype=np.complex128),
            "eigenvalues": np.asarray(self.eigenvalues, dtype=np.float64),
            "eigenvectors": np.asarray(self.eigenvectors, dtype=np.complex128),
        }
        if arrays["isometry"].ndim != 2:
            raise ValueError("sector isometry must be two-dimensional")
        multiplicity = arrays["isometry"].shape[1]
        if arrays["hamiltonian"].shape != (multiplicity, multiplicity):
            raise ValueError("sector Hamiltonian shape must match its isometry")
        if arrays["l2_operator"].shape != (multiplicity, multiplicity):
            raise ValueError("sector L2 operator shape must match its isometry")
        if arrays["eigenvalues"].shape != (multiplicity,):
            raise ValueError("sector eigenvalue shape must match its isometry")
        if arrays["eigenvectors"].shape != (multiplicity, multiplicity):
            raise ValueError("sector eigenvector shape must match its isometry")
        for name, array in arrays.items():
            object.__setattr__(self, name, _sealed_array(array))


@dataclass(frozen=True, slots=True)
class OracleResult:
    solver_mode: str
    spec: SphereSpec
    sectors: tuple[SectorResult, ...]
    energy_l0: float
    energy_l2: float
    gap: float
    residual_l0: float
    residual_l2: float
    mean_l2_l0: float
    mean_l2_l2: float
    l2_variance_l0: float
    l2_variance_l2: float
    l2_target_deviation_squared_l0: float
    l2_target_deviation_squared_l2: float
    absolute_excitation_energy: float | None
    absolute_excitation_gap: float | None
    absolute_excitation_l: int | None
    m_zero_dimension: int
    pair_channels: tuple[tuple[int, float], ...]
    array_hash_items: tuple[tuple[str, str], ...]
    source_hash_items: tuple[tuple[str, str], ...]
    package_version_items: tuple[tuple[str, str], ...]
    git_revision: str
    exact_sectors: tuple[ExactSectorEigensystem, ...]
    sparse_symmetry_diagnostics: tuple[SparseSymmetryDiagnostic, ...]
    low_energy_states: tuple[LowEnergyState, ...]
    dense_diagnostics: DenseOracleDiagnostics | None
    m_zero_hamiltonian: Any
    m_zero_l2: Any

    def exact_sector(self, target_l: int) -> ExactSectorEigensystem:
        """Return the stored eigensystem for one angular-momentum sector."""

        for sector in self.exact_sectors:
            if sector.angular_momentum == target_l:
                return sector
        raise ValueError(f"oracle does not contain an L={target_l} sector")

    def to_payload(self) -> dict[str, Any]:
        background = -(self.spec.particles**2) / (
            2.0 * self.spec.radius_in_magnetic_lengths
        )
        return {
            "schema": "challenge15.oracle-result.v1",
            "solver_mode": self.solver_mode,
            "physical_conventions": {
                "particles": self.spec.particles,
                "filling": "1/3",
                "laughlin_shift": 3,
                "two_q": self.spec.two_q,
                "one_particle_l": self.spec.q,
                "orbital_two_m_order": list(self.spec.two_m_values),
                "determinant_order": "ascending integer bit patterns; creation operators ascending in m",
                "monopole_chart": "north, holomorphic spinor polynomial",
                "distance": "physical chord r_ij=2*sqrt(Q)*l_B*sin(gamma_ij/2)",
                "energy_unit": "e^2/(4*pi*epsilon_0*epsilon*l_B)",
                "two_body_tensor": "(V_abcd-V_abdc)/2, antisymmetrized in bra and ket",
                "hamiltonian": "(1/2)*sum_abcd A_abcd cdag_a cdag_b c_d c_c",
                "background": "uniform neutralizing shell, -N^2/(2*sqrt(Q))",
            },
            "dimensions": {
                "full": self.spec.full_dimension,
                "m_zero": self.m_zero_dimension,
                "sector_multiplicities": {
                    str(sector.angular_momentum): sector.multiplicity
                    for sector in self.sectors
                },
            },
            "energies": {
                "electron_electron": {
                    "l0": self.energy_l0,
                    "l2": self.energy_l2,
                    "delta_l2": self.gap,
                    "absolute_excitation": self.absolute_excitation_energy,
                    "absolute_gap": self.absolute_excitation_gap,
                    "absolute_excitation_l": self.absolute_excitation_l,
                },
                "background_constant": background,
                "background_corrected": {
                    "l0": self.energy_l0 + background,
                    "l2": self.energy_l2 + background,
                },
            },
            "diagnostics": {
                "residual_l0": self.residual_l0,
                "residual_l2": self.residual_l2,
                "mean_l2_l0": self.mean_l2_l0,
                "mean_l2_l2": self.mean_l2_l2,
                "l2_variance_l0": self.l2_variance_l0,
                "l2_variance_l2": self.l2_variance_l2,
                "l2_target_deviation_squared_l0": self.l2_target_deviation_squared_l0,
                "l2_target_deviation_squared_l2": self.l2_target_deviation_squared_l2,
            },
            "sparse_symmetry_diagnostics": [
                {
                    "angular_momentum": item.angular_momentum,
                    "multiplicity": item.multiplicity,
                    "gram_defect": item.gram_defect,
                    "l2_target_residual": item.l2_target_residual,
                    "ladder_intertwining_residual": (
                        item.ladder_intertwining_residual
                    ),
                    "generator_ladder_intertwining_residual": (
                        item.ladder_intertwining_residual
                    ),
                    "row_pivots": list(item.row_pivots),
                    "workspace_elements_upper_bound": (
                        item.workspace_elements_upper_bound
                    ),
                    "dense_projector_allocated": item.dense_projector_allocated,
                    "thresholds": {
                        "gram_defect": SPARSE_GRAM_TOLERANCE,
                        "l2_target_residual": SPARSE_L2_RESIDUAL_TOLERANCE,
                        "ladder_intertwining_residual": SPARSE_LADDER_TOLERANCE,
                        "generator_ladder_intertwining_residual": (
                            SPARSE_LADDER_TOLERANCE
                        ),
                    },
                }
                for item in self.sparse_symmetry_diagnostics
            ],
            "low_energy_scan": [
                {
                    "energy": item.energy,
                    "angular_momentum": item.angular_momentum,
                    "eigenpair_residual": item.eigenpair_residual,
                    "l2_residual": item.l2_residual,
                    "l2_variance": item.l2_variance,
                }
                for item in self.low_energy_states
            ],
            "dense_diagnostics": (
                None
                if self.dense_diagnostics is None
                else {
                    "hamiltonian_hermiticity_defect": (
                        self.dense_diagnostics.hamiltonian_hermiticity_defect
                    ),
                    "l2_hermiticity_defect": (
                        self.dense_diagnostics.l2_hermiticity_defect
                    ),
                    "sector_multiplicity_sum": (
                        self.dense_diagnostics.sector_multiplicity_sum
                    ),
                    "m_zero_dimension": self.dense_diagnostics.m_zero_dimension,
                }
            ),
            "sectors": [
                {
                    "angular_momentum": sector.angular_momentum,
                    "multiplicity": sector.multiplicity,
                    "energy": sector.energy,
                    "spectrum": list(sector.spectrum),
                    "residual": sector.residual,
                    "mean_l2": sector.mean_l2,
                    "l2_variance": sector.l2_variance,
                    "l2_target_deviation_squared": sector.l2_target_deviation_squared,
                }
                for sector in self.sectors
            ],
            "pair_pseudopotentials": {
                str(channel): value for channel, value in self.pair_channels
            },
            "package_versions": dict(self.package_version_items),
            "git_revision": self.git_revision,
            "source_hashes": dict(self.source_hash_items),
            "array_hashes": dict(self.array_hash_items),
        }


@dataclass(frozen=True, slots=True)
class VerifiedOracle:
    """Schema-verified production identity paired with decoded immutable arrays."""

    path: Path
    payload_sha256: str
    payload: Mapping[str, Any]
    result: OracleResult

    def __post_init__(self) -> None:
        from challenge15.production_schema import payload_sha256

        if not isinstance(self.result, OracleResult):
            raise TypeError("verified oracle result must be an OracleResult")
        if payload_sha256(self.payload) != self.payload_sha256:
            raise ValueError("verified oracle payload SHA256 mismatch")
        particles = self.payload.get("particles")
        if particles is not None and particles != self.result.spec.particles:
            raise ValueError("verified oracle particle identity mismatch")
        object.__setattr__(self, "path", Path(self.path))


def oracle_cache_payload(result: OracleResult) -> dict[str, Any]:
    """Serialize immutable target-sector data without executable pickle content."""

    def encode(array: np.ndarray) -> dict[str, Any]:
        value = np.ascontiguousarray(array)
        raw = value.tobytes()
        return {
            "dtype": value.dtype.str,
            "shape": list(value.shape),
            "data_base64": base64.b64encode(raw).decode("ascii"),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "array_sha256": _array_sha256(value),
        }

    encoded_sectors = []
    declared_hashes: dict[str, str] = {}
    for sector in result.exact_sectors:
        encoded = {"angular_momentum": sector.angular_momentum}
        for field in (
            "isometry",
            "hamiltonian",
            "l2_operator",
            "eigenvalues",
            "eigenvectors",
        ):
            encoded[field] = encode(getattr(sector, field))
            declared_hashes[
                f"sector.{sector.angular_momentum}.{field}"
            ] = encoded[field]["array_sha256"]
        encoded_sectors.append(encoded)
    encoded_operators = {}
    for name, matrix in (
        ("hamiltonian", result.m_zero_hamiltonian),
        ("l2", result.m_zero_l2),
    ):
        csr = scipy_sparse.csr_matrix(matrix)
        encoded_operators[name] = {
            "shape": list(csr.shape),
            "data": encode(csr.data),
            "indices": encode(csr.indices),
            "indptr": encode(csr.indptr),
        }
        for field in ("data", "indices", "indptr"):
            declared_hashes[f"{name}.{field}"] = encoded_operators[name][
                field
            ]["array_sha256"]
    encoded_low_energy = []
    for index, state in enumerate(result.low_energy_states):
        encoded = encode(state.state)
        encoded_low_energy.append(encoded)
        declared_hashes[f"low_energy.{index}.state"] = encoded["array_sha256"]
    summary = json.loads(json.dumps(result.to_payload(), allow_nan=False))
    summary["array_hashes"] = declared_hashes
    return {
        "schema": "challenge15.oracle-cache.v2",
        "solver_mode": result.solver_mode,
        "summary": summary,
        "exact_sectors": encoded_sectors,
        "operators": encoded_operators,
        "low_energy_vectors": encoded_low_energy,
    }


def oracle_from_cache_payload(payload: Mapping[str, Any]) -> OracleResult:
    """Validate and restore an oracle cache produced by :func:`oracle_cache_payload`."""

    required_keys = {
        "schema",
        "solver_mode",
        "summary",
        "exact_sectors",
        "operators",
        "low_energy_vectors",
    }
    if set(payload) != required_keys:
        raise ValueError("oracle cache schema has missing or unexpected fields")
    if payload.get("schema") != "challenge15.oracle-cache.v2":
        raise ValueError("oracle cache schema is invalid")
    solver_mode = payload.get("solver_mode")
    if solver_mode not in {"dense-small-n", "sparse-production"}:
        raise ValueError("oracle cache solver mode is invalid")
    if not isinstance(payload.get("summary"), Mapping):
        raise ValueError("oracle cache summary is required")
    if payload["summary"].get("solver_mode") != solver_mode:
        raise ValueError("oracle cache solver mode is inconsistent")
    if not isinstance(payload.get("exact_sectors"), list):
        raise ValueError("oracle cache exact sectors are required")
    if not isinstance(payload.get("operators"), Mapping):
        raise ValueError("oracle cache operators are required")
    if set(payload["operators"]) != {"hamiltonian", "l2"}:
        raise ValueError("oracle cache required operators are missing")
    if not isinstance(payload.get("low_energy_vectors"), list):
        raise ValueError("oracle cache low-energy vectors are required")

    decoded_hashes: dict[str, str] = {}

    def decode(
        encoded: Mapping[str, Any], *, declared_name: str
    ) -> np.ndarray:
        raw = base64.b64decode(encoded["data_base64"], validate=True)
        if hashlib.sha256(raw).hexdigest() != encoded.get("sha256"):
            raise ValueError("oracle cache array SHA256 mismatch")
        dtype = np.dtype(encoded["dtype"])
        shape = tuple(int(value) for value in encoded["shape"])
        expected_size = int(np.prod(shape, dtype=np.int64)) * dtype.itemsize
        if len(raw) != expected_size:
            raise ValueError("oracle cache array size is invalid")
        array = np.frombuffer(raw, dtype=dtype).reshape(shape).copy()
        digest = _array_sha256(array)
        if digest != encoded.get("array_sha256"):
            raise ValueError("oracle cache declared array hash mismatch")
        decoded_hashes[declared_name] = digest
        return array

    summary = payload["summary"]
    particles = int(summary["physical_conventions"]["particles"])
    sectors = tuple(
        SectorResult(
            angular_momentum=int(item["angular_momentum"]),
            multiplicity=int(item["multiplicity"]),
            energy=float(item["energy"]),
            spectrum=tuple(float(value) for value in item["spectrum"]),
            residual=float(item["residual"]),
            mean_l2=float(item["mean_l2"]),
            l2_variance=float(item["l2_variance"]),
            l2_target_deviation_squared=float(
                item["l2_target_deviation_squared"]
            ),
        )
        for item in summary["sectors"]
    )
    exact_items = []
    for item in payload["exact_sectors"]:
        target_l = int(item["angular_momentum"])
        decoded = {
            field: decode(
                item[field], declared_name=f"sector.{target_l}.{field}"
            )
            for field in (
                "isometry",
                "hamiltonian",
                "l2_operator",
                "eigenvalues",
                "eigenvectors",
            )
        }
        exact_items.append(
            ExactSectorEigensystem(
                angular_momentum=target_l,
                **decoded,
            )
        )
    exact = tuple(exact_items)
    operators = {}
    for name in ("hamiltonian", "l2"):
        encoded = payload["operators"][name]
        if set(encoded) != {"shape", "data", "indices", "indptr"}:
            raise ValueError("oracle cache operator schema is invalid")
        shape = tuple(int(value) for value in encoded["shape"])
        if len(shape) != 2 or shape[0] != shape[1]:
            raise ValueError("oracle cache operator shape is invalid")
        data = decode(
            encoded["data"], declared_name=f"{name}.data"
        )
        indices = decode(
            encoded["indices"], declared_name=f"{name}.indices"
        )
        indptr = decode(
            encoded["indptr"], declared_name=f"{name}.indptr"
        )
        operators[name] = scipy_sparse.csr_matrix(
            (data, indices, indptr), shape=shape
        )
    low_vectors = tuple(
        decode(encoded, declared_name=f"low_energy.{index}.state")
        for index, encoded in enumerate(payload["low_energy_vectors"])
    )
    if summary.get("array_hashes") != decoded_hashes:
        raise ValueError("oracle cache declared array hashes are inconsistent")
    energies = summary["energies"]["electron_electron"]
    diagnostics = summary["diagnostics"]
    sparse_values = summary.get("sparse_symmetry_diagnostics")
    low_values = summary.get("low_energy_scan")
    dense_value = summary.get("dense_diagnostics")
    if solver_mode == "sparse-production":
        if not isinstance(sparse_values, list) or not sparse_values:
            raise ValueError("sparse symmetry diagnostics are required")
        if not isinstance(low_values, list) or not low_values:
            raise ValueError("sparse low-energy scan is required")
        if len(low_values) != len(low_vectors):
            raise ValueError("sparse low-energy vectors are required")
        if dense_value is not None:
            raise ValueError("sparse cache must not contain dense diagnostics")
    else:
        if sparse_values != [] or low_values != [] or low_vectors:
            raise ValueError("dense cache contains sparse-only diagnostics")
        if not isinstance(dense_value, Mapping):
            raise ValueError("dense diagnostics are required")
    sparse_diagnostics = tuple(
        SparseSymmetryDiagnostic(
            angular_momentum=int(item["angular_momentum"]),
            multiplicity=int(item["multiplicity"]),
            gram_defect=float(item["gram_defect"]),
            l2_target_residual=float(item["l2_target_residual"]),
            ladder_intertwining_residual=float(
                item["ladder_intertwining_residual"]
            ),
            row_pivots=tuple(int(value) for value in item["row_pivots"]),
            workspace_elements_upper_bound=int(
                item["workspace_elements_upper_bound"]
            ),
            dense_projector_allocated=bool(item["dense_projector_allocated"]),
        )
        for item in sparse_values
    )
    low_energy_states = tuple(
        LowEnergyState(
            energy=float(item["energy"]),
            angular_momentum=int(item["angular_momentum"]),
            eigenpair_residual=float(item["eigenpair_residual"]),
            l2_residual=float(item["l2_residual"]),
            l2_variance=float(item["l2_variance"]),
            state=state,
        )
        for item, state in zip(low_values, low_vectors, strict=True)
    )
    dense_diagnostics = (
        None
        if dense_value is None
        else DenseOracleDiagnostics(
            hamiltonian_hermiticity_defect=float(
                dense_value["hamiltonian_hermiticity_defect"]
            ),
            l2_hermiticity_defect=float(
                dense_value["l2_hermiticity_defect"]
            ),
            sector_multiplicity_sum=int(
                dense_value["sector_multiplicity_sum"]
            ),
            m_zero_dimension=int(dense_value["m_zero_dimension"]),
        )
    )
    result = OracleResult(
        solver_mode=solver_mode,
        spec=SphereSpec(particles),
        sectors=sectors,
        energy_l0=float(energies["l0"]),
        energy_l2=float(energies["l2"]),
        gap=float(energies["delta_l2"]),
        residual_l0=float(diagnostics["residual_l0"]),
        residual_l2=float(diagnostics["residual_l2"]),
        mean_l2_l0=float(diagnostics["mean_l2_l0"]),
        mean_l2_l2=float(diagnostics["mean_l2_l2"]),
        l2_variance_l0=float(diagnostics["l2_variance_l0"]),
        l2_variance_l2=float(diagnostics["l2_variance_l2"]),
        l2_target_deviation_squared_l0=float(
            diagnostics["l2_target_deviation_squared_l0"]
        ),
        l2_target_deviation_squared_l2=float(
            diagnostics["l2_target_deviation_squared_l2"]
        ),
        absolute_excitation_energy=(
            None
            if energies["absolute_excitation"] is None
            else float(energies["absolute_excitation"])
        ),
        absolute_excitation_gap=(
            None if energies["absolute_gap"] is None else float(energies["absolute_gap"])
        ),
        absolute_excitation_l=(
            None
            if energies["absolute_excitation_l"] is None
            else int(energies["absolute_excitation_l"])
        ),
        m_zero_dimension=int(summary["dimensions"]["m_zero"]),
        pair_channels=tuple(
            (int(channel), float(value))
            for channel, value in summary["pair_pseudopotentials"].items()
        ),
        array_hash_items=tuple(sorted(decoded_hashes.items())),
        source_hash_items=tuple(sorted(summary["source_hashes"].items())),
        package_version_items=tuple(sorted(summary["package_versions"].items())),
        git_revision=str(summary["git_revision"]),
        exact_sectors=exact,
        sparse_symmetry_diagnostics=sparse_diagnostics,
        low_energy_states=low_energy_states,
        dense_diagnostics=dense_diagnostics,
        m_zero_hamiltonian=operators["hamiltonian"],
        m_zero_l2=operators["l2"],
    )
    _validate_restored_oracle(result, summary)
    return result


def _validate_restored_oracle(
    result: OracleResult, summary: Mapping[str, Any]
) -> None:
    energy_tolerance = 1e-12
    basis = DeterminantBasis.with_two_m(result.spec, 0)
    if (
        result.m_zero_hamiltonian.shape != (basis.dimension, basis.dimension)
        or result.m_zero_l2.shape != (basis.dimension, basis.dimension)
        or result.m_zero_dimension != basis.dimension
    ):
        raise ValueError("oracle cache M=0 operator dimensions are invalid")
    by_l = {sector.angular_momentum: sector for sector in result.exact_sectors}
    if set(by_l) != {0, 2}:
        raise ValueError("oracle cache exact target sectors are incomplete")
    sector_results = {sector.angular_momentum: sector for sector in result.sectors}
    for target_l, sector in by_l.items():
        next_dimension = (
            DeterminantBasis.with_two_m(result.spec, 2 * (target_l + 1)).dimension
            if target_l < result.spec.l_max
            else 0
        )
        expected_multiplicity = (
            DeterminantBasis.with_two_m(result.spec, 2 * target_l).dimension
            - next_dimension
        )
        if (
            sector.isometry.shape[1] != expected_multiplicity
            or target_l not in sector_results
            or sector_results[target_l].multiplicity != expected_multiplicity
        ):
            raise ValueError("oracle cache sector multiplicity is invalid")
        projected_hamiltonian = (
            sector.isometry.conj().T
            @ result.m_zero_hamiltonian
            @ sector.isometry
        )
        projected_l2 = (
            sector.isometry.conj().T @ result.m_zero_l2 @ sector.isometry
        )
        if not np.allclose(
            projected_hamiltonian,
            sector.hamiltonian,
            rtol=1e-10,
            atol=1e-12,
        ) or not np.allclose(
            projected_l2,
            sector.l2_operator,
            rtol=1e-10,
            atol=1e-12,
        ):
            raise ValueError(
                "oracle cache target operators do not match full operators"
            )
        gram_defect = float(
            np.linalg.norm(
                sector.isometry.conj().T @ sector.isometry
                - np.eye(sector.isometry.shape[1]),
                ord=2,
            )
        )
        l2_residual = float(
            np.linalg.norm(
                sector.l2_operator
                - target_l * (target_l + 1) * np.eye(sector.isometry.shape[1])
            )
            / max(np.linalg.norm(sector.l2_operator), 1.0)
        )
        eigen_residual = float(
            np.linalg.norm(
                sector.hamiltonian @ sector.eigenvectors
                - sector.eigenvectors * sector.eigenvalues
            )
            / max(np.linalg.norm(sector.eigenvectors), 1.0)
        )
        if gram_defect > SPARSE_GRAM_TOLERANCE:
            raise ValueError("restored oracle Gram diagnostic exceeds threshold")
        if l2_residual > SPARSE_L2_RESIDUAL_TOLERANCE:
            raise ValueError("restored oracle L2 diagnostic exceeds threshold")
        if eigen_residual > 1e-10:
            raise ValueError("restored oracle eigensystem residual exceeds threshold")
        declared_result = sector_results[target_l]
        ground = _ground_diagnostics(
            result.m_zero_hamiltonian,
            result.m_zero_l2,
            sector.isometry,
            sector.eigenvalues,
            sector.eigenvectors,
            target_l,
        )
        actual_sector = (
            tuple(float(value) for value in sector.eigenvalues),
            ground.energy,
            ground.residual,
            ground.mean_l2,
            ground.l2_variance,
            ground.l2_target_deviation_squared,
        )
        stored_sector = (
            declared_result.spectrum,
            declared_result.energy,
            declared_result.residual,
            declared_result.mean_l2,
            declared_result.l2_variance,
            declared_result.l2_target_deviation_squared,
        )
        if not all(
            np.allclose(actual, stored, rtol=1e-8, atol=1e-13)
            for actual, stored in zip(actual_sector, stored_sector, strict=True)
        ):
            raise ValueError("oracle cache target-sector diagnostics are inconsistent")

    recomputed_l0 = float(by_l[0].eigenvalues[0])
    recomputed_l2 = float(by_l[2].eigenvalues[0])
    recomputed_gap = recomputed_l2 - recomputed_l0
    if (
        abs(result.energy_l0 - recomputed_l0) > energy_tolerance
        or abs(result.energy_l2 - recomputed_l2) > energy_tolerance
        or abs(result.gap - recomputed_gap) > energy_tolerance
    ):
        raise ValueError("oracle cache target energy or gap aggregate is invalid")

    if result.solver_mode == "sparse-production":
        full_l2 = _fixed_sector_l2_sparse(basis)
        declared_by_l = {
            item.angular_momentum: item
            for item in result.sparse_symmetry_diagnostics
        }
        if set(declared_by_l) != set(by_l):
            raise ValueError("oracle cache symmetry diagnostics have wrong sectors")
        for target_l, declared in declared_by_l.items():
            isometry = by_l[target_l].isometry
            expected_multiplicity = (
                DeterminantBasis.with_two_m(result.spec, 2 * target_l).dimension
                - DeterminantBasis.with_two_m(
                    result.spec, 2 * (target_l + 1)
                ).dimension
            )
            if declared.multiplicity != expected_multiplicity:
                raise ValueError(
                    "oracle cache sparse diagnostic multiplicity is invalid"
                )
            canonical, canonical_report = _canonical_thin_subspace_basis(isometry)
            if not np.allclose(canonical, isometry, rtol=1e-10, atol=1e-12):
                raise ValueError("oracle cache isometry is not canonically gauged")
            recomputed_pivots = tuple(
                int(value) for value in canonical_report["row_pivots"]
            )
            if declared.row_pivots != recomputed_pivots:
                raise ValueError("oracle cache canonical row pivots are invalid")
            if (
                declared.workspace_elements_upper_bound
                != canonical_report["workspace_elements_upper_bound"]
            ):
                raise ValueError("oracle cache thin workspace bound is invalid")
            if (
                declared.dense_projector_allocated
                is not canonical_report["dense_projector_allocated"]
            ):
                raise ValueError("oracle cache thin allocation metadata is invalid")
            recomputed_gram = float(
                np.linalg.norm(
                    isometry.conj().T @ isometry
                    - np.eye(isometry.shape[1]),
                    ord=2,
                )
            )
            recomputed_l2 = float(
                np.linalg.norm(
                    full_l2 @ isometry
                    - target_l * (target_l + 1) * isometry
                )
                / max(np.linalg.norm(isometry), 1.0)
            )
            ladder_report = verify_ladder_multiplet(
                basis, target_l, isometry
            )
            recomputed_ladder = max(
                float(ladder_report["max_ladder_error"]),
                float(ladder_report["max_norm_error"]),
                float(ladder_report["max_orthogonality_error"]),
            )
            actual = (
                recomputed_gram,
                recomputed_l2,
                recomputed_ladder,
            )
            stored = (
                declared.gram_defect,
                declared.l2_target_residual,
                declared.ladder_intertwining_residual,
            )
            if not np.allclose(actual, stored, rtol=1e-8, atol=1e-15):
                raise ValueError(
                    "oracle cache symmetry diagnostics do not match decoded arrays"
                )
            if (
                recomputed_gram > SPARSE_GRAM_TOLERANCE
                or recomputed_l2 > SPARSE_L2_RESIDUAL_TOLERANCE
                or recomputed_ladder > SPARSE_LADDER_TOLERANCE
            ):
                raise ValueError("oracle cache symmetry diagnostics fail thresholds")
            if declared.dense_projector_allocated:
                raise ValueError("oracle cache declares a dense projector allocation")

    if result.solver_mode == "sparse-production":
        states = result.low_energy_states
        if len(states) < 2 or states[0].angular_momentum != 0:
            raise ValueError("oracle cache low-energy scan is incomplete")
        validated_scan: list[tuple[float, int, int]] = []
        for item in states:
            vector = item.state
            norm = float(np.linalg.norm(vector))
            if abs(norm - 1.0) > 1e-10:
                raise ValueError("oracle cache low-energy vector is not normalized")
            h_vector = np.asarray(result.m_zero_hamiltonian @ vector)
            recomputed_energy = float(np.vdot(vector, h_vector).real)
            energy_residual = float(
                np.linalg.norm(h_vector - recomputed_energy * vector)
                / max(abs(recomputed_energy), 1.0)
            )
            l2_vector = np.asarray(result.m_zero_l2 @ vector)
            mean_l2 = float(np.vdot(vector, l2_vector).real)
            classified_l = int(round((-1.0 + np.sqrt(1.0 + 4.0 * mean_l2)) / 2.0))
            target = float(classified_l * (classified_l + 1))
            l2_residual = float(np.linalg.norm(l2_vector - target * vector))
            centered_l2 = l2_vector - mean_l2 * vector
            l2_variance = float(np.vdot(centered_l2, centered_l2).real)
            if (
                classified_l < 0
                or abs(mean_l2 - target) > 1e-10
                or classified_l != item.angular_momentum
            ):
                raise ValueError(
                    "oracle cache low-energy integer-L classification is invalid"
                )
            actual = (
                recomputed_energy,
                energy_residual,
                l2_residual,
                l2_variance,
            )
            stored = (
                item.energy,
                item.eigenpair_residual,
                item.l2_residual,
                item.l2_variance,
            )
            if not np.allclose(actual, stored, rtol=1e-7, atol=1e-13):
                raise ValueError(
                    "oracle cache low-energy diagnostics do not match vectors"
                )
            if (
                energy_residual > 1e-10
                or l2_residual > 1e-11
                or l2_variance > 1e-20
            ):
                raise ValueError(
                    "oracle cache low-energy diagnostics fail thresholds"
                )
            validated_scan.append(
                (recomputed_energy, classified_l, len(validated_scan))
            )
        if validated_scan != sorted(validated_scan):
            raise ValueError("oracle cache low-energy scan order is invalid")
        if (
            abs(validated_scan[0][0] - recomputed_l0) > energy_tolerance
            or validated_scan[0][1] != 0
        ):
            raise ValueError("oracle cache low-energy ground energy is invalid")
        absolute_energy, absolute_l, _ = min(validated_scan[1:])
        absolute_gap = absolute_energy - validated_scan[0][0]
        if (
            result.absolute_excitation_energy is None
            or result.absolute_excitation_gap is None
            or abs(result.absolute_excitation_energy - absolute_energy)
            > energy_tolerance
            or result.absolute_excitation_l != absolute_l
            or abs(result.absolute_excitation_gap - absolute_gap)
            > energy_tolerance
        ):
            raise ValueError(
                "oracle cache absolute-excitation energy, L, or gap is invalid"
            )
    else:
        dense = result.dense_diagnostics
        if dense is None:
            raise ValueError("oracle cache dense diagnostics are required")
        h_dense = result.m_zero_hamiltonian.toarray()
        l2_dense = result.m_zero_l2.toarray()
        h_hermiticity = float(
            np.linalg.norm(h_dense - h_dense.conj().T)
            / max(np.linalg.norm(h_dense), 1.0)
        )
        l2_hermiticity = float(
            np.linalg.norm(l2_dense - l2_dense.conj().T)
            / max(np.linalg.norm(l2_dense), 1.0)
        )
        expected_multiplicities: dict[int, int] = {}
        for target_l in range(result.spec.l_max + 1):
            current_dimension = DeterminantBasis.with_two_m(
                result.spec, 2 * target_l
            ).dimension
            next_dimension = (
                DeterminantBasis.with_two_m(
                    result.spec, 2 * (target_l + 1)
                ).dimension
                if target_l < result.spec.l_max
                else 0
            )
            multiplicity = current_dimension - next_dimension
            if multiplicity > 0:
                expected_multiplicities[target_l] = multiplicity
        declared_ls = [sector.angular_momentum for sector in result.sectors]
        if (
            len(declared_ls) != len(set(declared_ls))
            or set(declared_ls) != set(expected_multiplicities)
        ):
            raise ValueError(
                "oracle cache dense sector decomposition is not complete"
            )
        dimensions = summary.get("dimensions")
        declared_metadata = (
            dimensions.get("sector_multiplicities")
            if isinstance(dimensions, Mapping)
            else None
        )
        expected_metadata = {
            str(target_l): multiplicity
            for target_l, multiplicity in expected_multiplicities.items()
        }
        if declared_metadata != expected_metadata:
            raise ValueError(
                "oracle cache dense sector multiplicity metadata is invalid"
            )
        l2_values, l2_vectors = np.linalg.eigh(l2_dense)
        validated_dimension_sum = 0
        excitation_candidates: list[tuple[float, int, int]] = []
        for target_l in sorted(expected_multiplicities):
            declared = sector_results[target_l]
            target = target_l * (target_l + 1)
            mask = np.abs(l2_values - target) <= 1e-8
            expected_multiplicity = int(np.count_nonzero(mask))
            if (
                expected_multiplicity != expected_multiplicities[target_l]
                or declared.multiplicity != expected_multiplicity
            ):
                raise ValueError("oracle cache dense sector multiplicity is invalid")
            validated_dimension_sum += declared.multiplicity
            isometry = l2_vectors[:, mask]
            projected = isometry.conj().T @ h_dense @ isometry
            spectrum, eigenvectors = np.linalg.eigh(projected)
            if not np.allclose(spectrum, declared.spectrum, rtol=1e-9, atol=1e-11):
                raise ValueError("oracle cache dense sector spectrum is invalid")
            dense_ground = _ground_diagnostics(
                h_dense,
                l2_dense,
                isometry,
                spectrum,
                eigenvectors,
                target_l,
            )
            if not np.allclose(
                (
                    dense_ground.energy,
                    dense_ground.residual,
                    dense_ground.mean_l2,
                    dense_ground.l2_variance,
                    dense_ground.l2_target_deviation_squared,
                ),
                (
                    declared.energy,
                    declared.residual,
                    declared.mean_l2,
                    declared.l2_variance,
                    declared.l2_target_deviation_squared,
                ),
                rtol=1e-8,
                atol=1e-13,
            ):
                raise ValueError("oracle cache dense sector diagnostics are invalid")
            excitation_candidates.extend(
                (float(energy), target_l, index)
                for index, energy in enumerate(spectrum)
            )
        if (
            validated_dimension_sum != basis.dimension
            or dense.sector_multiplicity_sum != validated_dimension_sum
            or dense.m_zero_dimension != basis.dimension
            or not np.allclose(
                (
                    h_hermiticity,
                    l2_hermiticity,
                ),
                (
                    dense.hamiltonian_hermiticity_defect,
                    dense.l2_hermiticity_defect,
                ),
                rtol=1e-8,
                atol=1e-15,
            )
        ):
            raise ValueError("oracle cache dense diagnostics are inconsistent")
        absolute_energy, absolute_l, _ = min(
            candidate
            for candidate in excitation_candidates
            if not (candidate[1] == 0 and candidate[2] == 0)
        )
        absolute_gap = absolute_energy - recomputed_l0
        if (
            result.absolute_excitation_energy is None
            or result.absolute_excitation_gap is None
            or abs(result.absolute_excitation_energy - absolute_energy)
            > energy_tolerance
            or result.absolute_excitation_l != absolute_l
            or abs(result.absolute_excitation_gap - absolute_gap)
            > energy_tolerance
        ):
            raise ValueError(
                "oracle cache absolute-excitation energy, L, or gap is invalid"
            )
        if h_hermiticity > 1e-12 or l2_hermiticity > 1e-12:
            raise ValueError("oracle cache dense diagnostics fail thresholds")

    if result.to_payload() != summary:
        raise ValueError("oracle cache summary does not match decoded arrays")


@dataclass(frozen=True, slots=True)
class ExactNQSMetrics:
    """Independent coefficient-space acceptance diagnostics for L=0 and L=2."""

    norm_l0: float
    norm_l2: float
    energy_l0: float
    energy_l2: float
    h_variance_l0: float
    h_variance_l2: float
    overlap_l0: float
    overlap_l2: float
    l2_residual_l0: float
    l2_residual_l2: float
    l2_variance_l0: float
    l2_variance_l2: float
    carrier_gram_singular_values_l0: np.ndarray
    carrier_gram_singular_values_l2: np.ndarray
    carrier_gram_relative_singular_values_l0: np.ndarray
    carrier_gram_relative_singular_values_l2: np.ndarray
    projected_span_rank_l0: int
    projected_span_rank_l2: int
    projected_span_dimension_l0: int
    projected_span_dimension_l2: int
    projected_span_complete_l0: bool
    projected_span_complete_l2: bool
    quadrature_coefficient_relative_change_l0: float
    quadrature_coefficient_relative_change_l2: float
    quadrature_energy_relative_change_l0: float
    quadrature_energy_relative_change_l2: float
    quadrature_orders_l0: tuple[tuple[int, int], tuple[int, int]]
    quadrature_orders_l2: tuple[tuple[int, int], tuple[int, int]]
    bare_potential_sampling_variance: None
    _normalized_sector_coefficients_l0: np.ndarray
    _normalized_sector_coefficients_l2: np.ndarray

    def __post_init__(self) -> None:
        for name in (
            "carrier_gram_singular_values_l0",
            "carrier_gram_singular_values_l2",
            "carrier_gram_relative_singular_values_l0",
            "carrier_gram_relative_singular_values_l2",
            "_normalized_sector_coefficients_l0",
            "_normalized_sector_coefficients_l2",
        ):
            object.__setattr__(
                self, name, _sealed_array(np.asarray(getattr(self, name)))
            )

    def normalized_sector_coefficients(self, target_l: int) -> np.ndarray:
        """Return normalized coefficients in the oracle's immutable T_L basis."""

        if target_l == 0:
            return self._normalized_sector_coefficients_l0
        if target_l == 2:
            return self._normalized_sector_coefficients_l2
        raise ValueError("target_l must be 0 or 2")

    def projected_carrier_relative_singular_values(
        self, target_l: int
    ) -> np.ndarray:
        if target_l == 0:
            return self.carrier_gram_relative_singular_values_l0
        if target_l == 2:
            return self.carrier_gram_relative_singular_values_l2
        raise ValueError("target_l must be 0 or 2")

    def projected_span_rank(self, target_l: int) -> int:
        if target_l == 0:
            return self.projected_span_rank_l0
        if target_l == 2:
            return self.projected_span_rank_l2
        raise ValueError("target_l must be 0 or 2")

    def projected_span_complete(self, target_l: int) -> bool:
        if target_l == 0:
            return self.projected_span_complete_l0
        if target_l == 2:
            return self.projected_span_complete_l2
        raise ValueError("target_l must be 0 or 2")


@dataclass(frozen=True, slots=True)
class _SectorAcceptance:
    norm: float
    energy: float
    h_variance: float
    overlap: float
    l2_residual: float
    l2_variance: float
    gram_singular_values: np.ndarray
    gram_relative_singular_values: np.ndarray
    span_rank: int
    span_dimension: int
    span_complete: bool
    normalized_coefficients: np.ndarray
    quadrature_orders: tuple[tuple[int, int], tuple[int, int]]
    quadrature_coefficient_relative_change: float
    quadrature_energy_relative_change: float


def evaluate_exact_nqs(
    spec: SphereSpec,
    model_parameters,
    oracle: OracleResult,
    *,
    block_size: int = 256,
    determinant_block: int | None = None,
    carrier_block: int | None = None,
    quadrature_block: int | None = None,
) -> ExactNQSMetrics:
    """Bridge shared model parameters to exact normalized ED diagnostics.

    Carrier coefficients are generated analytically in bounded determinant
    blocks.  Projection uses only the stored immutable target isometries, and
    all Hamiltonian comparisons use the eigensystems already held by ``oracle``.
    """

    if not isinstance(spec, SphereSpec):
        raise TypeError("spec must be a SphereSpec")
    if spec.particles > 8:
        raise ValueError("exact NQS acceptance is limited to N <= 8")
    if not isinstance(oracle, OracleResult) or oracle.spec != spec:
        raise ValueError("oracle must be an OracleResult for the supplied spec")
    _validate_positive_block(block_size, "block_size")
    determinant_width = block_size if determinant_block is None else determinant_block
    _validate_positive_block(determinant_width, "determinant_block")

    quadrature_width = (
        2 * spec.l_max + 1 if quadrature_block is None else quadrature_block
    )
    _validate_positive_block(quadrature_width, "quadrature_block")
    accepted = {
        target_l: _evaluate_sector_acceptance(
            spec,
            model_parameters,
            oracle,
            target_l,
            determinant_block=determinant_width,
            carrier_block=carrier_block,
            quadrature_block=quadrature_width,
        )
        for target_l in (0, 2)
    }
    l0 = accepted[0]
    l2 = accepted[2]
    return ExactNQSMetrics(
        norm_l0=l0.norm,
        norm_l2=l2.norm,
        energy_l0=l0.energy,
        energy_l2=l2.energy,
        h_variance_l0=l0.h_variance,
        h_variance_l2=l2.h_variance,
        overlap_l0=l0.overlap,
        overlap_l2=l2.overlap,
        l2_residual_l0=l0.l2_residual,
        l2_residual_l2=l2.l2_residual,
        l2_variance_l0=l0.l2_variance,
        l2_variance_l2=l2.l2_variance,
        carrier_gram_singular_values_l0=l0.gram_singular_values,
        carrier_gram_singular_values_l2=l2.gram_singular_values,
        carrier_gram_relative_singular_values_l0=l0.gram_relative_singular_values,
        carrier_gram_relative_singular_values_l2=l2.gram_relative_singular_values,
        projected_span_rank_l0=l0.span_rank,
        projected_span_rank_l2=l2.span_rank,
        projected_span_dimension_l0=l0.span_dimension,
        projected_span_dimension_l2=l2.span_dimension,
        projected_span_complete_l0=l0.span_complete,
        projected_span_complete_l2=l2.span_complete,
        quadrature_coefficient_relative_change_l0=(
            l0.quadrature_coefficient_relative_change
        ),
        quadrature_coefficient_relative_change_l2=(
            l2.quadrature_coefficient_relative_change
        ),
        quadrature_energy_relative_change_l0=l0.quadrature_energy_relative_change,
        quadrature_energy_relative_change_l2=l2.quadrature_energy_relative_change,
        quadrature_orders_l0=l0.quadrature_orders,
        quadrature_orders_l2=l2.quadrature_orders,
        bare_potential_sampling_variance=None,
        _normalized_sector_coefficients_l0=l0.normalized_coefficients,
        _normalized_sector_coefficients_l2=l2.normalized_coefficients,
    )


def _model_reduced_carriers(
    spec: SphereSpec, model_parameters
) -> tuple[np.ndarray, dict[int, tuple[np.ndarray, np.ndarray]]]:
    if not isinstance(model_parameters, Mapping):
        raise ValueError("model_parameters must be a params mapping or variables mapping")
    params = (
        model_parameters["params"]
        if "params" in model_parameters
        else model_parameters
    )
    try:
        tokens = np.asarray(params["carrier_tokens"], dtype=np.float64)
        gate_components = np.asarray(params["carrier_gates"], dtype=np.float64)
        input_layer = params["shared_input"]
        output_layer = params["shared_reduced_output"]
    except (KeyError, TypeError) as exc:
        raise ValueError("model_parameters do not contain shared carrier parameters") from exc
    if tokens.ndim != 2 or gate_components.shape != (tokens.shape[0], 2):
        raise ValueError("model carrier token and gate shapes are inconsistent")
    gates = _complex_components(gate_components)
    input_kernel = np.asarray(input_layer["kernel"], dtype=np.float64)
    input_bias = np.asarray(input_layer["bias"], dtype=np.float64)
    output_kernel = np.asarray(output_layer["kernel"], dtype=np.float64)
    output_bias = np.asarray(output_layer["bias"], dtype=np.float64)
    fixed_width = input_kernel.shape[0] - tokens.shape[1]
    if fixed_width < 5 or (fixed_width - 3) % 2:
        raise ValueError("shared input width does not encode a valid Fourier order")
    fourier_order = (fixed_width - 3) // 2
    residual_names = sorted(
        (
            name
            for name in params
            if isinstance(name, str) and name.startswith("shared_residual_")
        ),
        key=lambda name: int(name.rsplit("_", 1)[1]),
    )
    residual_scale = 1.0 / np.sqrt(max(len(residual_names), 1))

    positive_two_m = tuple(two_m for two_m in spec.two_m_values if two_m > 0)
    reduced_coordinates = np.asarray((*positive_two_m, 0), dtype=np.float64) / float(
        spec.two_q
    )
    reduced: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for target_l in (0, 2):
        features = _fixed_model_features(
            reduced_coordinates, target_l, fourier_order
        )
        fixed_bank = np.broadcast_to(
            features[None, :, :],
            (tokens.shape[0], features.shape[0], features.shape[1]),
        )
        token_bank = np.broadcast_to(
            tokens[:, None, :],
            (tokens.shape[0], features.shape[0], tokens.shape[1]),
        )
        inputs = np.concatenate((fixed_bank, token_bank), axis=-1)
        hidden = np.tanh(inputs @ input_kernel + input_bias)
        for name in residual_names:
            layer = params[name]
            kernel = np.asarray(layer["kernel"], dtype=np.float64)
            bias = np.asarray(layer["bias"], dtype=np.float64)
            hidden = hidden + residual_scale * np.tanh(hidden @ kernel + bias)
        outputs = _complex_components(hidden @ output_kernel + output_bias)
        reduced[target_l] = (outputs[:, :-1], outputs[:, -1])

    arrays = (gates, *(array for pair in reduced.values() for array in pair))
    if not all(np.all(np.isfinite(array)) for array in arrays):
        raise ValueError("model parameters produce nonfinite carrier values")
    return gates, reduced


def _fixed_model_features(
    coordinates: np.ndarray, target_l: int, fourier_order: int
) -> np.ndarray:
    frequencies = np.arange(1, fourier_order + 1, dtype=np.float64)
    angles = 2.0 * np.pi * coordinates[:, None] * frequencies[None, :]
    sector = np.asarray(
        [float(target_l == 0), float(target_l == 2)], dtype=np.float64
    )
    return np.concatenate(
        (
            coordinates[:, None],
            np.sin(angles),
            np.cos(angles),
            np.broadcast_to(sector, (coordinates.shape[0], 2)),
        ),
        axis=-1,
    )


def _complex_components(components: np.ndarray) -> np.ndarray:
    array = np.asarray(components, dtype=np.float64)
    if array.shape[-1] != 2:
        raise ValueError("complex components must have a final axis of length two")
    return array[..., 0] + 1j * array[..., 1]


def _validate_positive_block(value: int, name: str) -> None:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value <= 0
    ):
        raise ValueError(f"{name} must be a positive Python integer")


@lru_cache(maxsize=64)
def _occupied_orbitals(
    states: tuple[int, ...], orbital_count: int, particles: int
) -> tuple[tuple[int, ...], ...]:
    occupied_by_state = tuple(
        tuple(
            orbital
            for orbital in range(orbital_count)
            if state & (1 << orbital)
        )
        for state in states
    )
    if any(len(occupied) != particles for occupied in occupied_by_state):
        raise ValueError("each state must occupy spec.particles orbitals")
    return occupied_by_state


def _numpy_pfaffian(matrix: np.ndarray) -> complex:
    size = matrix.shape[0]
    if size == 0:
        return 1.0 + 0.0j
    return sum(
        (-1.0 if column % 2 == 0 else 1.0)
        * matrix[0, column]
        * _numpy_pfaffian(
            np.delete(np.delete(matrix, (0, column), axis=0), (0, column), axis=1)
        )
        for column in range(1, size)
    )


def _numpy_orbital_data(
    spec: SphereSpec,
    pair_weights: np.ndarray,
    border_weights: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    weights = np.asarray(pair_weights, dtype=np.complex128)
    borders = np.asarray(border_weights, dtype=np.complex128)
    positive = tuple(
        index for index, two_m in enumerate(spec.two_m_values) if two_m > 0
    )
    negative = tuple(
        spec.two_m_values.index(-spec.two_m_values[index]) for index in positive
    )
    if weights.ndim != 2 or weights.shape[1] != len(positive):
        raise ValueError("pair weights do not match the positive-m channels")
    if borders.shape != (weights.shape[0],):
        raise ValueError("border weights do not match the carrier count")
    matrices = np.zeros(
        (weights.shape[0], spec.orbital_count, spec.orbital_count),
        dtype=np.complex128,
    )
    matrices[:, positive, negative] = weights
    matrices[:, negative, positive] = -weights
    border_vectors = np.zeros(
        (weights.shape[0], spec.orbital_count), dtype=np.complex128
    )
    if spec.particles % 2:
        border_vectors[:, spec.two_m_values.index(0)] = borders
    return matrices, border_vectors


def _numpy_pfaffian_coefficients(
    spec: SphereSpec,
    pair_matrices: np.ndarray,
    border_vectors: np.ndarray,
    states: tuple[int, ...],
) -> np.ndarray:
    occupied_by_state = _occupied_orbitals(
        states, spec.orbital_count, spec.particles
    )
    coefficients = np.empty(
        (pair_matrices.shape[0], len(states)), dtype=np.complex128
    )
    for carrier_index, (matrix, border) in enumerate(
        zip(pair_matrices, border_vectors, strict=True)
    ):
        for state_index, occupied in enumerate(occupied_by_state):
            restricted = matrix[np.ix_(occupied, occupied)]
            if spec.particles % 2:
                augmented = np.zeros(
                    (spec.particles + 1, spec.particles + 1),
                    dtype=np.complex128,
                )
                augmented[:-1, :-1] = restricted
                augmented[:-1, -1] = border[np.asarray(occupied)]
                augmented[-1, :-1] = -augmented[:-1, -1]
                restricted = augmented
            coefficients[carrier_index, state_index] = _numpy_pfaffian(
                restricted
            )
    return coefficients


def nqs_sector_coefficients(
    spec: SphereSpec,
    model_parameters: Mapping[str, Any],
    oracle: OracleResult,
    *,
    target_l: int,
    determinant_block: int = 256,
    carrier_block: int | None = None,
    _details: dict[str, Any] | None = None,
) -> np.ndarray:
    """Return normalized NQS coefficients in the oracle's target-sector basis."""

    if not isinstance(spec, SphereSpec):
        raise TypeError("spec must be a SphereSpec")
    if spec.particles > 8:
        raise ValueError("exact NQS acceptance is limited to N <= 8")
    if not isinstance(oracle, OracleResult) or oracle.spec != spec:
        raise ValueError("oracle must be an OracleResult for the supplied spec")
    if (
        not isinstance(target_l, int)
        or isinstance(target_l, bool)
        or target_l not in (0, 2)
    ):
        raise ValueError("target_l must be 0 or 2")
    _validate_positive_block(determinant_block, "determinant_block")

    gates, reduced = _model_reduced_carriers(spec, model_parameters)
    pair_weights, border_weights = reduced[target_l]
    carrier_width = len(gates) if carrier_block is None else carrier_block
    _validate_positive_block(carrier_width, "carrier_block")
    basis = DeterminantBasis.with_two_m(spec, 0)
    sector = oracle.exact_sector(target_l)
    multiplicity = sector.isometry.shape[1]
    rank = pair_weights.shape[0]
    projected_carriers = np.zeros((multiplicity, rank), dtype=np.complex128)
    for carrier_start in range(0, rank, carrier_width):
        carrier_stop = min(carrier_start + carrier_width, rank)
        carrier_count = carrier_stop - carrier_start
        padded_pairs = np.zeros(
            (carrier_width, pair_weights.shape[1]), dtype=np.complex128
        )
        padded_borders = np.zeros(carrier_width, dtype=np.complex128)
        padded_pairs[:carrier_count] = pair_weights[carrier_start:carrier_stop]
        padded_borders[:carrier_count] = border_weights[
            carrier_start:carrier_stop
        ]
        pair_matrices, border_vectors = _numpy_orbital_data(
            spec, padded_pairs, padded_borders
        )
        for determinant in iter_ordered_determinant_blocks(
            basis, determinant_block
        ):
            valid_states = tuple(
                int(value) for value in determinant.states[determinant.valid]
            )
            coefficients = np.zeros(
                (carrier_width, determinant_block), dtype=np.complex128
            )
            coefficients[:, : len(valid_states)] = _numpy_pfaffian_coefficients(
                spec, pair_matrices, border_vectors, valid_states
            )
            rows = determinant.indices[determinant.valid]
            projected_carriers[:, carrier_start:carrier_stop] += (
                sector.isometry[rows].conj().T
                @ coefficients[:carrier_count, determinant.valid].T
            )

    coefficients = projected_carriers @ gates
    norm = float(np.linalg.norm(coefficients))
    if not np.isfinite(norm) or norm == 0.0:
        raise ValueError(f"projected L={target_l} model coefficients have zero norm")
    normalized = np.asarray(coefficients / norm, dtype=np.complex128)
    if _details is not None:
        _details.update(
            {
                "gates": gates,
                "pair_weights": pair_weights,
                "border_weights": border_weights,
                "projected_carriers": projected_carriers,
                "norm": norm,
                "carrier_block": carrier_width,
            }
        )
    return normalized


def _evaluate_sector_acceptance(
    spec: SphereSpec,
    model_parameters: Mapping[str, Any],
    oracle: OracleResult,
    target_l: int,
    *,
    determinant_block: int,
    carrier_block: int | None,
    quadrature_block: int,
) -> _SectorAcceptance:
    sector = oracle.exact_sector(target_l)
    multiplicity = sector.isometry.shape[1]
    details: dict[str, Any] = {}
    normalized = nqs_sector_coefficients(
        spec,
        model_parameters,
        oracle,
        target_l=target_l,
        determinant_block=determinant_block,
        carrier_block=carrier_block,
        _details=details,
    )
    gates = details["gates"]
    pair_weights = details["pair_weights"]
    border_weights = details["border_weights"]
    projected_carriers = details["projected_carriers"]
    norm = details["norm"]
    carrier_width = details["carrier_block"]
    h_image = sector.hamiltonian @ normalized
    energy = float(np.vdot(normalized, h_image).real)
    h_residual = h_image - energy * normalized
    h_variance = max(0.0, float(np.vdot(h_residual, h_residual).real))
    overlap = float(abs(np.vdot(sector.eigenvectors[:, 0], normalized)) ** 2)
    overlap = min(1.0, max(0.0, overlap))

    l2_image = sector.l2_operator @ normalized
    target_l2 = float(target_l * (target_l + 1))
    l2_residual = float(np.linalg.norm(l2_image - target_l2 * normalized))
    mean_l2 = float(np.vdot(normalized, l2_image).real)
    centered_l2 = l2_image - mean_l2 * normalized
    l2_variance = max(0.0, float(np.vdot(centered_l2, centered_l2).real))

    carrier_gram = projected_carriers.conj().T @ projected_carriers
    gram_singular_values = np.linalg.svd(carrier_gram, compute_uv=False)
    if gram_singular_values.size and gram_singular_values[0] > 0:
        relative = gram_singular_values / gram_singular_values[0]
    else:
        relative = np.zeros_like(gram_singular_values)
    span_rank = int(np.count_nonzero(relative > 1e-10))
    minimal_orders = (
        2 * spec.l_max + 1,
        (spec.l_max + target_l + 2) // 2,
    )
    quadrature_orders = (
        minimal_orders,
        (2 * minimal_orders[0], 2 * minimal_orders[1]),
    )
    quadrature_coefficients = tuple(
        _quadrature_projected_coefficients(
            spec,
            pair_weights,
            border_weights,
            gates,
            target_l,
            n_alpha=n_alpha,
            n_beta=n_beta,
            determinant_block=determinant_block,
            carrier_block=carrier_width,
            quadrature_block=quadrature_block,
        )
        for n_alpha, n_beta in quadrature_orders
    )
    minimal_coefficients, doubled_coefficients = quadrature_coefficients
    phase_overlap = np.vdot(minimal_coefficients, doubled_coefficients)
    if phase_overlap != 0:
        doubled_coefficients = doubled_coefficients * np.exp(
            -1j * np.angle(phase_overlap)
        )
    quadrature_coefficient_change = float(
        np.linalg.norm(doubled_coefficients - minimal_coefficients)
    )
    minimal_energy = _sector_energy_from_m0(sector, minimal_coefficients)
    doubled_energy = _sector_energy_from_m0(sector, doubled_coefficients)
    quadrature_energy_change = abs(doubled_energy - minimal_energy) / max(
        abs(minimal_energy), 1.0
    )
    return _SectorAcceptance(
        norm=norm,
        energy=energy,
        h_variance=h_variance,
        overlap=overlap,
        l2_residual=l2_residual,
        l2_variance=l2_variance,
        gram_singular_values=gram_singular_values,
        gram_relative_singular_values=relative,
        span_rank=span_rank,
        span_dimension=multiplicity,
        span_complete=span_rank == multiplicity,
        normalized_coefficients=normalized,
        quadrature_orders=quadrature_orders,
        quadrature_coefficient_relative_change=quadrature_coefficient_change,
        quadrature_energy_relative_change=quadrature_energy_change,
    )


def _quadrature_projected_coefficients(
    spec: SphereSpec,
    pair_weights: np.ndarray,
    border_weights: np.ndarray,
    gates: np.ndarray,
    target_l: int,
    *,
    n_alpha: int,
    n_beta: int,
    block_size: int | None = None,
    determinant_block: int | None = None,
    carrier_block: int | None = None,
    quadrature_block: int | None = None,
) -> np.ndarray:
    """Project orbital Pfaffian data with explicit finite-grid rotations."""

    basis = DeterminantBasis.with_two_m(spec, 0)
    determinant_width = (
        256
        if determinant_block is None and block_size is None
        else block_size
        if determinant_block is None
        else determinant_block
    )
    assert determinant_width is not None
    carrier_width = len(gates) if carrier_block is None else carrier_block
    quadrature_width = n_beta if quadrature_block is None else quadrature_block
    _validate_positive_block(determinant_width, "determinant_block")
    _validate_positive_block(carrier_width, "carrier_block")
    _validate_positive_block(quadrature_width, "quadrature_block")
    alpha_nodes = np.arange(n_alpha, dtype=np.float64) * (2.0 * np.pi / n_alpha)
    alpha_weights = np.full(n_alpha, 2.0 * np.pi / n_alpha)
    alpha_factor = np.dot(alpha_weights, np.exp(0j * alpha_nodes)) / (2.0 * np.pi)
    coefficients = np.zeros(basis.dimension, dtype=np.complex128)

    rank = len(gates)
    for quadrature in _iter_padded_quadrature_blocks(
        spec, n_beta, quadrature_width
    ):
        for local_index in range(quadrature_width):
            if not quadrature.valid[local_index]:
                continue
            rotation = quadrature.rotations[local_index]
            beta_node = quadrature.nodes[local_index]
            beta_weight = quadrature.weights[local_index]
            kernel = (
                alpha_factor
                * (2 * target_l + 1)
                / 2.0
                * beta_weight
                * eval_legendre(target_l, beta_node)
            )
            for carrier_start in range(0, rank, carrier_width):
                carrier_stop = min(carrier_start + carrier_width, rank)
                carrier_count = carrier_stop - carrier_start
                padded_pairs = np.zeros(
                    (carrier_width, pair_weights.shape[1]),
                    dtype=np.complex128,
                )
                padded_borders = np.zeros(carrier_width, dtype=np.complex128)
                padded_gates = np.zeros(carrier_width, dtype=np.complex128)
                padded_pairs[:carrier_count] = pair_weights[
                    carrier_start:carrier_stop
                ]
                padded_borders[:carrier_count] = border_weights[
                    carrier_start:carrier_stop
                ]
                padded_gates[:carrier_count] = gates[
                    carrier_start:carrier_stop
                ]
                pair_matrices, border_vectors = _numpy_orbital_data(
                    spec, padded_pairs, padded_borders
                )
                rotated_pairs = (
                    rotation[None, :, :]
                    @ pair_matrices
                    @ rotation.T[None, :, :]
                )
                rotated_borders = border_vectors @ rotation.T
                for determinant in iter_ordered_determinant_blocks(
                    basis, determinant_width
                ):
                    valid_states = tuple(
                        int(value)
                        for value in determinant.states[determinant.valid]
                    )
                    block_values = np.zeros(
                        (carrier_width, determinant_width),
                        dtype=np.complex128,
                    )
                    block_values[:, determinant.valid] = (
                        _numpy_pfaffian_coefficients(
                            spec,
                            rotated_pairs,
                            rotated_borders,
                            valid_states,
                        )
                    )
                    coefficients[determinant.indices[determinant.valid]] += (
                        kernel
                        * np.sum(
                            padded_gates[:, None]
                            * block_values[:, determinant.valid],
                            axis=0,
                        )
                    )
    norm = np.linalg.norm(coefficients)
    if not np.isfinite(norm) or norm == 0:
        raise ValueError("quadrature-projected coefficients have zero norm")
    return coefficients / norm


def _orbital_border_vector(spec: SphereSpec, border_weight: complex) -> np.ndarray:
    vector = np.zeros(spec.orbital_count, dtype=np.complex128)
    if spec.particles % 2:
        vector[spec.two_m_values.index(0)] = border_weight
    return vector


def _single_particle_jy(spec: SphereSpec) -> np.ndarray:
    raising = np.zeros(
        (spec.orbital_count, spec.orbital_count), dtype=np.complex128
    )
    for column, two_m in enumerate(spec.two_m_values[:-1]):
        m = two_m / 2.0
        raising[column + 1, column] = np.sqrt(
            spec.q * (spec.q + 1.0) - m * (m + 1.0)
        )
    return (raising - raising.conj().T) / (2j)


def _sector_energy_from_m0(
    sector: ExactSectorEigensystem, coefficients: np.ndarray
) -> float:
    sector_coefficients = sector.isometry.conj().T @ coefficients
    norm = np.linalg.norm(sector_coefficients)
    if not np.isfinite(norm) or norm == 0:
        raise ValueError("quadrature projection has no target-sector component")
    normalized = sector_coefficients / norm
    return float(np.vdot(normalized, sector.hamiltonian @ normalized).real)


def solve_target_sectors(spec: SphereSpec) -> OracleResult:
    """Solve each accessible ``M=0`` angular-momentum sector exactly once."""

    if not isinstance(spec, SphereSpec):
        raise TypeError("spec must be a SphereSpec")
    basis = DeterminantBasis.with_two_m(spec, 0)
    direct_tensor = orbital_coulomb_tensor(spec)
    pair_values = pair_pseudopotentials(spec)
    pair_tensor = pseudopotential_coulomb_tensor(spec, pair_values)
    if not np.allclose(direct_tensor, pair_tensor, rtol=0.0, atol=1e-11):
        raise RuntimeError("independent finite-sphere Coulomb builders disagree")

    hamiltonian_sparse = many_body_coulomb(basis, direct_tensor)
    hamiltonian = np.asarray(hamiltonian_sparse.toarray(), dtype=np.complex128)
    hamiltonian = 0.5 * (hamiltonian + hamiltonian.conj().T)
    l2 = np.asarray(angular_operators(basis, return_l2_only=True), dtype=np.complex128)
    hamiltonian_csr = scipy_sparse.csr_matrix(hamiltonian)
    l2_csr = scipy_sparse.csr_matrix(l2)
    l2_eigenvalues, l2_eigenvectors = np.linalg.eigh(l2)

    array_hashes = {
        "coulomb.direct": _array_sha256(direct_tensor),
        "coulomb.pseudopotential": _array_sha256(pair_tensor),
        "hamiltonian.data": _array_sha256(hamiltonian_csr.data),
        "hamiltonian.indices": _array_sha256(hamiltonian_csr.indices),
        "hamiltonian.indptr": _array_sha256(hamiltonian_csr.indptr),
        "hamiltonian.dense": _array_sha256(hamiltonian),
        "l2": _array_sha256(l2),
        "l2.data": _array_sha256(l2_csr.data),
        "l2.indices": _array_sha256(l2_csr.indices),
        "l2.indptr": _array_sha256(l2_csr.indptr),
        "l2.eigenvalues": _array_sha256(l2_eigenvalues),
        "l2.eigenvectors": _array_sha256(l2_eigenvectors),
    }
    sectors: list[SectorResult] = []
    exact_sectors: list[ExactSectorEigensystem] = []
    excitation_candidates: list[tuple[float, int, int]] = []

    for target_l in range(spec.l_max + 1):
        target_value = target_l * (target_l + 1)
        mask = np.abs(l2_eigenvalues - target_value) <= 1e-10
        multiplicity = int(np.count_nonzero(mask))
        if multiplicity == 0:
            continue
        eigenspace = l2_eigenvectors[:, mask]
        isometry = _canonical_thin_subspace_basis(eigenspace)[0]
        projected = isometry.conj().T @ hamiltonian @ isometry
        projected = 0.5 * (projected + projected.conj().T)
        eigenvalues, eigenvectors = np.linalg.eigh(projected)
        diagnostics = _ground_diagnostics(
            hamiltonian,
            l2,
            isometry,
            eigenvalues,
            eigenvectors,
            target_l,
        )
        sectors.append(
            SectorResult(
                angular_momentum=target_l,
                multiplicity=multiplicity,
                energy=diagnostics.energy,
                spectrum=tuple(float(value) for value in eigenvalues),
                residual=diagnostics.residual,
                mean_l2=diagnostics.mean_l2,
                l2_variance=diagnostics.l2_variance,
                l2_target_deviation_squared=diagnostics.l2_target_deviation_squared,
            )
        )
        if target_l in (0, 2):
            projected_l2 = isometry.conj().T @ l2 @ isometry
            array_hashes[f"sector.{target_l}.l2_operator"] = _array_sha256(
                projected_l2
            )
            exact_sectors.append(
                ExactSectorEigensystem(
                    angular_momentum=target_l,
                    isometry=isometry,
                    hamiltonian=projected,
                    l2_operator=projected_l2,
                    eigenvalues=eigenvalues,
                    eigenvectors=eigenvectors,
                )
            )
        prefix = f"sector.{target_l}"
        array_hashes[f"{prefix}.isometry"] = _array_sha256(isometry)
        array_hashes[f"{prefix}.hamiltonian"] = _array_sha256(projected)
        array_hashes[f"{prefix}.eigenvalues"] = _array_sha256(eigenvalues)
        array_hashes[f"{prefix}.eigenvectors"] = _array_sha256(eigenvectors)
        array_hashes[f"{prefix}.ground_state_m0"] = _array_sha256(diagnostics.state)
        excitation_candidates.extend(
            (float(value), target_l, index) for index, value in enumerate(eigenvalues)
        )

    by_l = {sector.angular_momentum: sector for sector in sectors}
    if 0 not in by_l or 2 not in by_l:
        raise RuntimeError("required L=0 and L=2 sectors are not accessible")
    l0 = by_l[0]
    l2_sector = by_l[2]
    candidates_without_ground = [
        candidate
        for candidate in excitation_candidates
        if not (candidate[1] == 0 and candidate[2] == 0)
    ]
    absolute_energy, absolute_l, _ = min(candidates_without_ground)
    gap = l2_sector.energy - l0.energy

    return OracleResult(
        solver_mode="dense-small-n",
        spec=spec,
        sectors=tuple(sectors),
        energy_l0=l0.energy,
        energy_l2=l2_sector.energy,
        gap=gap,
        residual_l0=l0.residual,
        residual_l2=l2_sector.residual,
        mean_l2_l0=l0.mean_l2,
        mean_l2_l2=l2_sector.mean_l2,
        l2_variance_l0=l0.l2_variance,
        l2_variance_l2=l2_sector.l2_variance,
        l2_target_deviation_squared_l0=l0.l2_target_deviation_squared,
        l2_target_deviation_squared_l2=l2_sector.l2_target_deviation_squared,
        absolute_excitation_energy=absolute_energy,
        absolute_excitation_gap=absolute_energy - l0.energy,
        absolute_excitation_l=absolute_l,
        m_zero_dimension=basis.dimension,
        pair_channels=tuple(sorted(pair_values.items())),
        array_hash_items=tuple(sorted(array_hashes.items())),
        source_hash_items=tuple(sorted(_source_hashes().items())),
        package_version_items=tuple(sorted(_package_versions().items())),
        git_revision=_git_revision(),
        exact_sectors=tuple(exact_sectors),
        sparse_symmetry_diagnostics=(),
        low_energy_states=(),
        dense_diagnostics=DenseOracleDiagnostics(
            hamiltonian_hermiticity_defect=float(
                np.linalg.norm(hamiltonian - hamiltonian.conj().T)
                / max(np.linalg.norm(hamiltonian), 1.0)
            ),
            l2_hermiticity_defect=float(
                np.linalg.norm(l2 - l2.conj().T)
                / max(np.linalg.norm(l2), 1.0)
            ),
            sector_multiplicity_sum=sum(
                sector.multiplicity for sector in sectors
            ),
            m_zero_dimension=basis.dimension,
        ),
        m_zero_hamiltonian=hamiltonian_csr,
        m_zero_l2=l2_csr,
    )


def solve_required_target_sectors_sparse(spec: SphereSpec) -> OracleResult:
    """Solve only L=0 and L=2 without dense full-L2 diagonalization."""

    if not isinstance(spec, SphereSpec):
        raise TypeError("spec must be a SphereSpec")
    basis = DeterminantBasis.with_two_m(spec, 0)
    direct_tensor = orbital_coulomb_tensor(spec)
    pair_values = pair_pseudopotentials(spec)
    pair_tensor = pseudopotential_coulomb_tensor(spec, pair_values)
    if not np.allclose(direct_tensor, pair_tensor, rtol=0.0, atol=1e-11):
        raise RuntimeError("independent finite-sphere Coulomb builders disagree")
    hamiltonian = many_body_coulomb(basis, direct_tensor).tocsr()
    l2 = _fixed_sector_l2_sparse(basis)
    sectors: list[SectorResult] = []
    exact_sectors: list[ExactSectorEigensystem] = []
    hashes = {
        "coulomb.direct": _array_sha256(direct_tensor),
        "coulomb.pseudopotential": _array_sha256(pair_tensor),
        "hamiltonian.data": _array_sha256(hamiltonian.data),
        "hamiltonian.indices": _array_sha256(hamiltonian.indices),
        "hamiltonian.indptr": _array_sha256(hamiltonian.indptr),
        "l2.data": _array_sha256(l2.data),
        "l2.indices": _array_sha256(l2.indices),
        "l2.indptr": _array_sha256(l2.indptr),
    }
    diagnostics_by_l: dict[int, _GroundDiagnostics] = {}
    sparse_diagnostics: list[SparseSymmetryDiagnostic] = []
    for target_l in (0, 2):
        isometry, symmetry = target_irrep_isometry_sparse(
            basis, target_l, return_diagnostics=True
        )
        sparse_diagnostics.append(
            SparseSymmetryDiagnostic(
                angular_momentum=target_l,
                multiplicity=int(symmetry["multiplicity"]),
                gram_defect=float(symmetry["gram_defect"]),
                l2_target_residual=float(symmetry["l2_target_residual"]),
                ladder_intertwining_residual=float(
                    symmetry["ladder_intertwining_residual"]
                ),
                row_pivots=tuple(int(value) for value in symmetry["row_pivots"]),
                workspace_elements_upper_bound=int(
                    symmetry["workspace_elements_upper_bound"]
                ),
                dense_projector_allocated=bool(
                    symmetry["dense_projector_allocated"]
                ),
            )
        )
        projected = np.asarray(
            isometry.conj().T @ (hamiltonian @ isometry),
            dtype=np.complex128,
        )
        projected = 0.5 * (projected + projected.conj().T)
        eigenvalues, eigenvectors = np.linalg.eigh(projected)
        diagnostics = _ground_diagnostics(
            hamiltonian,
            l2,
            isometry,
            eigenvalues,
            eigenvectors,
            target_l,
        )
        projected_l2 = np.asarray(
            isometry.conj().T @ (l2 @ isometry), dtype=np.complex128
        )
        exact = ExactSectorEigensystem(
            angular_momentum=target_l,
            isometry=isometry,
            hamiltonian=projected,
            l2_operator=projected_l2,
            eigenvalues=eigenvalues,
            eigenvectors=eigenvectors,
        )
        exact_sectors.append(exact)
        diagnostics_by_l[target_l] = diagnostics
        sectors.append(
            SectorResult(
                angular_momentum=target_l,
                multiplicity=isometry.shape[1],
                energy=diagnostics.energy,
                spectrum=tuple(float(value) for value in eigenvalues),
                residual=diagnostics.residual,
                mean_l2=diagnostics.mean_l2,
                l2_variance=diagnostics.l2_variance,
                l2_target_deviation_squared=(
                    diagnostics.l2_target_deviation_squared
                ),
            )
        )
        prefix = f"sector.{target_l}"
        hashes[f"{prefix}.isometry"] = _array_sha256(isometry)
        hashes[f"{prefix}.hamiltonian"] = _array_sha256(projected)
        hashes[f"{prefix}.l2_operator"] = _array_sha256(projected_l2)
        hashes[f"{prefix}.eigenvalues"] = _array_sha256(eigenvalues)
        hashes[f"{prefix}.eigenvectors"] = _array_sha256(eigenvectors)
        hashes[f"{prefix}.ground_state_m0"] = _array_sha256(diagnostics.state)
    l0 = diagnostics_by_l[0]
    l2_result = diagnostics_by_l[2]
    low_energy_states = _sparse_low_energy_scan(
        basis,
        hamiltonian,
        l2,
        isometry_cache={
            sector.angular_momentum: sector.isometry
            for sector in exact_sectors
        },
    )
    absolute = low_energy_states[1]
    if (
        abs(low_energy_states[0].energy - l0.energy) > 1e-10
        or low_energy_states[0].angular_momentum != 0
    ):
        raise RuntimeError("sparse low-energy scan ground state is inconsistent")
    for index, state in enumerate(low_energy_states):
        hashes[f"low_energy.{index}.state"] = _array_sha256(state.state)
    return OracleResult(
        solver_mode="sparse-production",
        spec=spec,
        sectors=tuple(sectors),
        energy_l0=l0.energy,
        energy_l2=l2_result.energy,
        gap=l2_result.energy - l0.energy,
        residual_l0=l0.residual,
        residual_l2=l2_result.residual,
        mean_l2_l0=l0.mean_l2,
        mean_l2_l2=l2_result.mean_l2,
        l2_variance_l0=l0.l2_variance,
        l2_variance_l2=l2_result.l2_variance,
        l2_target_deviation_squared_l0=l0.l2_target_deviation_squared,
        l2_target_deviation_squared_l2=l2_result.l2_target_deviation_squared,
        absolute_excitation_energy=absolute.energy,
        absolute_excitation_gap=absolute.energy - low_energy_states[0].energy,
        absolute_excitation_l=absolute.angular_momentum,
        m_zero_dimension=basis.dimension,
        pair_channels=tuple(sorted(pair_values.items())),
        array_hash_items=tuple(sorted(hashes.items())),
        source_hash_items=tuple(sorted(_source_hashes().items())),
        package_version_items=tuple(sorted(_package_versions().items())),
        git_revision=_git_revision(),
        exact_sectors=tuple(exact_sectors),
        sparse_symmetry_diagnostics=tuple(sparse_diagnostics),
        low_energy_states=low_energy_states,
        dense_diagnostics=None,
        m_zero_hamiltonian=hamiltonian,
        m_zero_l2=l2,
    )


def _sparse_low_energy_scan(
    basis: DeterminantBasis,
    hamiltonian,
    l2,
    *,
    initial_eigenpairs: int = 8,
    isometry_cache: dict[int, np.ndarray] | None = None,
) -> tuple[LowEnergyState, ...]:
    """Adaptively classify a complete low-energy window by angular momentum."""

    dimension = int(hamiltonian.shape[0])
    if dimension < 3:
        raise RuntimeError("sparse low-energy scan requires dimension at least three")
    requested = min(initial_eigenpairs, dimension - 1)
    while True:
        energies, vectors = eigsh(
            hamiltonian,
            k=requested,
            which="SA",
            tol=1e-13,
            maxiter=max(2000, 30 * dimension),
        )
        order = np.argsort(energies)
        energies = np.asarray(energies[order], dtype=np.float64)
        vectors = np.asarray(vectors[:, order], dtype=np.complex128)
        boundary = float(energies[-1])
        complete_count = int(np.count_nonzero(energies < boundary - 1e-9))
        if complete_count >= 4:
            selected_count = 4
            while (
                selected_count < complete_count
                and abs(
                    float(
                        energies[selected_count] - energies[selected_count - 1]
                    )
                )
                <= 1e-9
            ):
                selected_count += 1
            return _classify_low_energy_window(
                basis,
                hamiltonian,
                l2,
                energies[:selected_count],
                vectors[:, :selected_count],
                isometry_cache={} if isometry_cache is None else isometry_cache,
            )
        if requested == dimension - 1:
            return _classify_low_energy_window(
                basis,
                hamiltonian,
                l2,
                energies,
                vectors,
                isometry_cache={} if isometry_cache is None else isometry_cache,
            )
        requested = min(dimension - 1, 2 * requested)


def _classify_low_energy_window(
    basis: DeterminantBasis,
    hamiltonian,
    l2,
    energies: np.ndarray,
    vectors: np.ndarray,
    *,
    isometry_cache: dict[int, np.ndarray],
) -> tuple[LowEnergyState, ...]:
    classified: list[LowEnergyState] = []
    start = 0
    while start < len(energies):
        stop = start + 1
        while (
            stop < len(energies)
            and abs(float(energies[stop] - energies[start])) <= 1e-9
        ):
            stop += 1
        subspace = vectors[:, start:stop]
        projected_l2 = np.asarray(
            subspace.conj().T @ (l2 @ subspace), dtype=np.complex128
        )
        projected_l2 = 0.5 * (projected_l2 + projected_l2.conj().T)
        _, rotation = np.linalg.eigh(projected_l2)
        resolved = subspace @ rotation
        for column in range(resolved.shape[1]):
            state = resolved[:, column]
            state /= np.linalg.norm(state)
            l2_state = l2 @ state
            mean_l2 = float(np.vdot(state, l2_state).real)
            angular_momentum = int(round(0.5 * (np.sqrt(1.0 + 4.0 * mean_l2) - 1.0)))
            if angular_momentum not in isometry_cache:
                isometry_cache[angular_momentum] = _sparse_target_l2_basis(
                    basis, angular_momentum
                )[0]
            target_isometry = isometry_cache[angular_momentum]
            state = target_isometry @ (target_isometry.conj().T @ state)
            projected_norm = np.linalg.norm(state)
            if projected_norm <= 1e-12:
                raise RuntimeError(
                    "low-energy angular-momentum projection lost the state"
                )
            state /= projected_norm
            h_state = hamiltonian @ state
            energy = float(np.vdot(state, h_state).real)
            eigenpair_residual = float(
                np.linalg.norm(h_state - energy * state)
                / max(abs(energy), 1.0)
            )
            l2_state = l2 @ state
            mean_l2 = float(np.vdot(state, l2_state).real)
            target_l2 = float(angular_momentum * (angular_momentum + 1))
            l2_residual = float(
                np.linalg.norm(l2_state - target_l2 * state)
                / max(np.linalg.norm(state), 1.0)
            )
            centered = l2_state - mean_l2 * state
            l2_variance = float(np.vdot(centered, centered).real)
            if eigenpair_residual > 1e-10:
                raise RuntimeError("low-energy eigenpair residual exceeds 1e-10")
            if (
                abs(mean_l2 - target_l2) > 1e-11
                or l2_residual > 1e-11
                or l2_variance > 1e-20
            ):
                raise RuntimeError("low-energy angular-momentum classification is ambiguous")
            classified.append(
                LowEnergyState(
                    energy=energy,
                    angular_momentum=angular_momentum,
                    eigenpair_residual=eigenpair_residual,
                    l2_residual=l2_residual,
                    l2_variance=l2_variance,
                    state=state,
                )
            )
        start = stop
    classified.sort(key=lambda item: (item.energy, item.angular_momentum))
    if len(classified) < 2:
        raise RuntimeError("low-energy scan did not resolve an excitation")
    return tuple(classified)


def _ground_diagnostics(
    hamiltonian: np.ndarray,
    l2: np.ndarray,
    isometry: np.ndarray,
    eigenvalues: np.ndarray,
    eigenvectors: np.ndarray,
    target_l: int,
) -> _GroundDiagnostics:
    """Compute diagnostics from the supplied eigensystem without re-solving."""

    energy = float(eigenvalues[0])
    state = np.asarray(isometry @ eigenvectors[:, 0], dtype=np.complex128)
    state /= np.linalg.norm(state)
    residual = float(np.linalg.norm(hamiltonian @ state - energy * state))
    l2_state = l2 @ state
    mean_l2 = float(np.vdot(state, l2_state).real)
    centered_l2_error = l2_state - mean_l2 * state
    variance = float(np.vdot(centered_l2_error, centered_l2_error).real)
    expected_l2 = float(target_l * (target_l + 1))
    target_l2_error = l2_state - expected_l2 * state
    target_deviation_squared = float(np.vdot(target_l2_error, target_l2_error).real)
    return _GroundDiagnostics(
        energy=energy,
        residual=residual,
        mean_l2=mean_l2,
        l2_variance=variance,
        l2_target_deviation_squared=target_deviation_squared,
        state=state,
    )


def _array_sha256(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(np.asarray(array))
    descriptor = json.dumps(
        {"dtype": contiguous.dtype.str, "shape": contiguous.shape},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    digest = hashlib.sha256()
    digest.update(descriptor)
    digest.update(b"\0")
    digest.update(contiguous.tobytes(order="C"))
    return digest.hexdigest()


def _sealed_array(array: np.ndarray) -> np.ndarray:
    contiguous = np.ascontiguousarray(np.asarray(array))
    return np.frombuffer(contiguous.tobytes(), dtype=contiguous.dtype).reshape(
        contiguous.shape
    )


def _source_hashes() -> dict[str, str]:
    root = Path(__file__).resolve().parents[2]
    hashes: dict[str, str] = {}
    for path in sorted((root / "src" / "challenge15").glob("*.py")):
        relative = path.relative_to(root).as_posix()
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _package_versions() -> dict[str, str]:
    versions = {"python": platform.python_version()}
    for distribution in ("numpy", "scipy", "sympy"):
        versions[distribution] = metadata.version(distribution)
    return versions


def _git_revision() -> str:
    root = Path(__file__).resolve().parents[2]
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("could not determine Git revision") from exc
    revision = completed.stdout.strip()
    if len(revision) != 40 or any(character not in "0123456789abcdef" for character in revision):
        raise RuntimeError("Git revision is not a full lowercase commit hash")
    return revision
