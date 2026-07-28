"""Independent dense-ED oracle for a finite spinful Anderson bath.

The implementation deliberately targets only small baths.  With ``n_bath``
bath orbitals, the full grand-canonical Hilbert dimension is
``D = 2 ** (2 * (n_bath + 1))``.  Dense storage is O(D**2) and diagonalization
is O(D**3).  Dimension and conservative peak-byte guards are both enforced
before allocation; the latter budgets twelve simultaneous float64
matrix-equivalents plus vector/index storage.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import importlib.util
import json
import math
import numbers
import os
import platform
from pathlib import Path
import stat
import tempfile
from typing import Any, Sequence

import numpy as np


MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = 3
MAX_DENSE_DIMENSION = 4096
MAX_DENSE_BYTES = 512 * 1024 * 1024
DENSE_PEAK_MATRIX_EQUIVALENTS = 12
HYBRIDIZATION_CONVENTION = (
    "Gamma(omega) = pi * sum_k V_k^2 * delta(omega - epsilon_k)"
)
BATH_ORDERING_CONVENTION = "k = 1..n_bath; epsilon in descending order"
COUPLING_GAUGE = "V_k is real and nonnegative: V_k = sqrt(weight_k / pi)"
HAMILTONIAN_CONVENTION = (
    "K = (epsilon_d-mu) sum_sigma n_dsigma "
    "+ U n_dup n_ddown + sum_k,sigma (epsilon_k-mu) n_ksigma "
    "+ sum_k,sigma V_k (d_sigma^dag c_ksigma + h.c.)"
)
FERMION_MAPPING_CONVENTION = (
    "occupation-bit basis with explicit Jordan-Wigner parity "
    "over all lower canonical modes"
)
THERMAL_SPACE_CONVENTION = "full grand-canonical Fock space"
GREEN_FUNCTION_CONVENTION = (
    "G_sigma(tau) = -Tr[exp(-(beta-tau)K) d_sigma "
    "exp(-tau K) d_sigma^dag] / Z"
)
BOLTZMANN_STABILIZATION_CONVENTION = (
    "all Lehmann exponents shifted by the many-body ground energy"
)
PARTITION_OVERFLOW_CONVENTION = (
    "Z is null with Z_status='overflow' when finite logZ exceeds "
    "the largest representable float; otherwise Z_status='finite'"
)
DETERMINISTIC_SERIALIZATION_CONVENTION = (
    "canonical JSON bytes are deterministic for a fixed locked "
    "runtime; runtime versions are recorded in provenance"
)
ORACLE_CONVENTIONS = {
    "hamiltonian": HAMILTONIAN_CONVENTION,
    "hybridization": HYBRIDIZATION_CONVENTION,
    "coupling_gauge": COUPLING_GAUGE,
    "fermion_mapping": FERMION_MAPPING_CONVENTION,
    "thermal_space": THERMAL_SPACE_CONVENTION,
    "green_function": GREEN_FUNCTION_CONVENTION,
    "boltzmann_stabilization": BOLTZMANN_STABILIZATION_CONVENTION,
    "partition_overflow": PARTITION_OVERFLOW_CONVENTION,
    "deterministic_serialization": DETERMINISTIC_SERIALIZATION_CONVENTION,
}
DENSE_PEAK_MEMORY_MODEL = (
    "12 float64 matrix-equivalents plus 16 float64 vectors, "
    "covering Hamiltonian/eigenvectors, eigensolver workspace, "
    "operator transforms, Lehmann exponents, and temporaries"
)
STORAGE_COST = "O(D^2) dense matrices"
DIAGONALIZATION_COST = "O(D^3) dense symmetric eigendecomposition"
BATH_CONVENTIONS = {
    "hybridization": HYBRIDIZATION_CONVENTION,
    "quadrature": "Gauss-Chebyshev quadrature of the second kind",
    "target_continuum": (
        "Gamma_target(omega) = gamma * sqrt(1 - "
        "(omega / bandwidth)^2) for |omega| <= bandwidth; 0 otherwise"
    ),
    "ordering": BATH_ORDERING_CONVENTION,
    "epsilon": "bandwidth * cos(k * pi / (n_bath + 1))",
    "V_squared": (
        "gamma * bandwidth / (n_bath + 1) * "
        "sin(k * pi / (n_bath + 1))^2"
    ),
}


def _load_bath_module():
    path = Path(__file__).with_name("bath.py")
    spec = importlib.util.spec_from_file_location(
        "challenge_81_oracle_bath_validation", path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load bath validation module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_BATH_MODULE = _load_bath_module()
MODEL_DEFINITION = _BATH_MODULE.load_model_definition()
if MODEL_DEFINITION["conventions"]["hamiltonian"] != HAMILTONIAN_CONVENTION:
    raise ValueError("authoritative Hamiltonian convention mismatch")
if MODEL_DEFINITION["conventions"]["green_function"] != GREEN_FUNCTION_CONVENTION:
    raise ValueError("authoritative Green-function convention mismatch")
BATH_CONVENTIONS = {
    name: MODEL_DEFINITION["conventions"][name]
    for name in (
        "hybridization",
        "quadrature",
        "target_continuum",
        "ordering",
        "epsilon",
        "V_squared",
    )
}
SUPPORTED_BATH_SCHEMA_VERSION = _BATH_MODULE.SCHEMA_VERSION


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _validate_real(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be a real number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _validate_integer(value: Any, name: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, numbers.Integral):
        qualifier = "positive " if positive else ""
        raise TypeError(f"{name} must be a {qualifier}integer")
    converted = int(value)
    if positive and converted <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return converted


def _validate_numeric_sequence(
    values: Any, name: str, *, nonnegative: bool = False
) -> list[float]:
    if (
        isinstance(values, (str, bytes))
        or not isinstance(values, Sequence)
        or isinstance(values, (bool, np.bool_))
    ):
        raise TypeError(f"{name} must be a sequence of real numbers")
    converted = [_validate_real(value, f"{name} values") for value in values]
    if nonnegative and any(value < 0.0 for value in converted):
        raise ValueError(f"{name} values must be nonnegative")
    return converted


def estimate_dense_peak_memory_bytes(dimension: int) -> int:
    """Conservative peak for eigensolver workspace and Lehmann temporaries."""

    dimension = _validate_integer(dimension, "dimension", positive=True)
    matrix_bytes = (
        DENSE_PEAK_MATRIX_EQUIVALENTS
        * np.dtype(np.float64).itemsize
        * dimension
        * dimension
    )
    vector_and_index_bytes = 16 * np.dtype(np.float64).itemsize * dimension
    return matrix_bytes + vector_and_index_bytes


def _validate_dimension(
    *,
    n_modes: int,
    max_dimension: Any = MAX_DENSE_DIMENSION,
    max_dense_bytes: Any = MAX_DENSE_BYTES,
) -> tuple[int, int, int]:
    max_dimension = _validate_integer(
        max_dimension, "max_dimension", positive=True
    )
    if max_dimension > MAX_DENSE_DIMENSION:
        raise ValueError(
            f"max_dimension cannot exceed safe limit {MAX_DENSE_DIMENSION}"
        )
    max_dense_bytes = _validate_integer(
        max_dense_bytes, "max_dense_bytes", positive=True
    )
    if max_dense_bytes > MAX_DENSE_BYTES:
        raise ValueError(
            f"max_dense_bytes cannot exceed safe limit {MAX_DENSE_BYTES}"
        )
    dimension = 1 << n_modes
    estimate = estimate_dense_peak_memory_bytes(dimension)
    if dimension > max_dimension:
        raise ValueError(
            f"Hilbert dimension {dimension} exceeds max_dimension "
            f"{max_dimension}; estimated dense peak memory is at least "
            f"{estimate} bytes"
        )
    if estimate > max_dense_bytes:
        raise ValueError(
            f"estimated dense peak memory {estimate} bytes exceeds "
            f"max_dense_bytes {max_dense_bytes}"
        )
    return dimension, max_dimension, max_dense_bytes


def fermion_annihilation(
    *,
    n_modes: int,
    mode: int,
    max_dimension: int = MAX_DENSE_DIMENSION,
    max_dense_bytes: int = MAX_DENSE_BYTES,
) -> np.ndarray:
    """Return a real Jordan-Wigner annihilation matrix in occupation basis.

    Basis states are integers whose bit ``m`` is the occupation of canonical
    fermion mode ``m``.  The matrix element includes the parity of all lower
    canonical modes.
    """

    n_modes = _validate_integer(n_modes, "n_modes", positive=True)
    mode = _validate_integer(mode, "mode")
    if mode < 0 or mode >= n_modes:
        raise ValueError("mode must satisfy 0 <= mode < n_modes")
    dimension, _, _ = _validate_dimension(
        n_modes=n_modes,
        max_dimension=max_dimension,
        max_dense_bytes=max_dense_bytes,
    )
    operator = np.zeros((dimension, dimension), dtype=np.float64)
    lower_mask = (1 << mode) - 1
    mode_mask = 1 << mode
    for source in range(dimension):
        if source & mode_mask:
            target = source ^ mode_mask
            sign = -1.0 if (source & lower_mask).bit_count() & 1 else 1.0
            operator[target, source] = sign
    return operator


def _validated_model_inputs(
    *,
    epsilon: Any,
    V: Any,
    U: Any,
    epsilon_d: Any,
    mu: Any,
    max_dimension: Any,
    max_dense_bytes: Any,
) -> tuple[list[float], list[float], float, float, float, int, int, int]:
    epsilon_values = _validate_numeric_sequence(epsilon, "epsilon")
    coupling_values = _validate_numeric_sequence(V, "V", nonnegative=True)
    if len(epsilon_values) != len(coupling_values):
        raise ValueError("epsilon and V must have the same length")
    if not epsilon_values:
        raise ValueError("epsilon and V must contain at least one bath orbital")
    U_value = _validate_real(U, "U")
    epsilon_d_value = (
        -U_value / 2.0
        if epsilon_d is None
        else _validate_real(epsilon_d, "epsilon_d")
    )
    mu_value = _validate_real(mu, "mu")
    n_modes = 2 * (len(epsilon_values) + 1)
    dimension, max_dimension_value, max_dense_bytes_value = _validate_dimension(
        n_modes=n_modes,
        max_dimension=max_dimension,
        max_dense_bytes=max_dense_bytes,
    )
    return (
        epsilon_values,
        coupling_values,
        U_value,
        epsilon_d_value,
        mu_value,
        dimension,
        max_dimension_value,
        max_dense_bytes_value,
    )


def _hop_sign(source: int, annihilate_mode: int, create_mode: int) -> int:
    after_annihilation = source ^ (1 << annihilate_mode)
    annihilation_parity = (
        source & ((1 << annihilate_mode) - 1)
    ).bit_count()
    creation_parity = (
        after_annihilation & ((1 << create_mode) - 1)
    ).bit_count()
    return -1 if (annihilation_parity + creation_parity) & 1 else 1


def build_hamiltonian(
    *,
    epsilon: Sequence[float],
    V: Sequence[float],
    U: float,
    epsilon_d: float | None = None,
    mu: float = 0.0,
    max_dimension: int = MAX_DENSE_DIMENSION,
    max_dense_bytes: int = MAX_DENSE_BYTES,
) -> np.ndarray:
    """Construct K in the complete grand-canonical occupation basis."""

    (
        epsilon,
        V,
        U,
        epsilon_d,
        mu,
        dimension,
        _,
        _,
    ) = _validated_model_inputs(
        epsilon=epsilon,
        V=V,
        U=U,
        epsilon_d=epsilon_d,
        mu=mu,
        max_dimension=max_dimension,
        max_dense_bytes=max_dense_bytes,
    )
    hamiltonian = np.zeros((dimension, dimension), dtype=np.float64)

    for state in range(dimension):
        n_up = (state >> 0) & 1
        n_down = (state >> 1) & 1
        diagonal = (
            (epsilon_d - mu) * (n_up + n_down) + U * n_up * n_down
        )
        for bath_index, bath_energy in enumerate(epsilon):
            first_mode = 2 + 2 * bath_index
            diagonal += (bath_energy - mu) * (
                ((state >> first_mode) & 1)
                + ((state >> (first_mode + 1)) & 1)
            )
        hamiltonian[state, state] = diagonal

    for bath_index, coupling in enumerate(V):
        if coupling == 0.0:
            continue
        for spin in range(2):
            impurity_mode = spin
            bath_mode = 2 + 2 * bath_index + spin
            impurity_mask = 1 << impurity_mode
            bath_mask = 1 << bath_mode
            for source in range(dimension):
                if source & bath_mask and not source & impurity_mask:
                    target = source ^ bath_mask ^ impurity_mask
                    matrix_element = coupling * _hop_sign(
                        source, bath_mode, impurity_mode
                    )
                    hamiltonian[target, source] += matrix_element
                    hamiltonian[source, target] += matrix_element
    return hamiltonian


def _require_keys(mapping: Any, keys: set[str], name: str) -> None:
    if not isinstance(mapping, dict):
        raise TypeError(f"{name} must be a JSON object")
    missing = keys - mapping.keys()
    if missing:
        raise ValueError(f"{name} missing required keys: {sorted(missing)}")


def _validate_digest(digest: Any, name: str) -> str:
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError(f"{name} must be 64 lowercase hexadecimal digits")
    return digest


def _consume_bath_artifact(
    artifact: Any,
) -> dict[str, Any]:
    try:
        _BATH_MODULE.verify_bath_artifact(artifact)
    except (TypeError, ValueError) as error:
        raise type(error)(f"bath artifact validation failed: {error}") from error
    artifact_copy = copy.deepcopy(artifact)
    _require_keys(artifact_copy, {"payload", "sha256"}, "bath artifact")
    payload = artifact_copy["payload"]
    if not isinstance(payload, dict):
        raise TypeError("bath artifact payload must be a JSON object")
    digest = _validate_digest(
        artifact_copy["sha256"], "bath artifact SHA256"
    )
    expected = hashlib.sha256(_canonical_json(payload)).hexdigest()
    if not hmac.compare_digest(digest, expected):
        raise ValueError("bath artifact SHA256 mismatch")

    _require_keys(
        payload,
        {
            "schema_version",
            "parameters",
            "conventions",
            "provenance",
            "epsilon",
            "V",
        },
        "bath artifact payload",
    )
    if (
        type(payload["schema_version"]) is not int
        or payload["schema_version"] != SUPPORTED_BATH_SCHEMA_VERSION
    ):
        raise ValueError(
            f"unsupported bath schema version: {payload['schema_version']!r}"
        )
    _require_keys(payload["parameters"], {"n_bath"}, "bath parameters")
    n_bath = _validate_integer(
        payload["parameters"]["n_bath"], "bath n_bath", positive=True
    )
    _require_keys(payload["conventions"], set(BATH_CONVENTIONS), "bath conventions")
    for name, expected_value in BATH_CONVENTIONS.items():
        if payload["conventions"][name] != expected_value:
            raise ValueError(f"unsupported bath {name} convention")
    _require_keys(
        payload["provenance"],
        {
            "module",
            "module_version",
            "python_version",
            "numpy_version",
            "schema_version",
        },
        "bath provenance",
    )
    provenance = payload["provenance"]
    if (
        provenance["module"] != "bath"
        or type(provenance["schema_version"]) is not int
        or provenance["schema_version"] != SUPPORTED_BATH_SCHEMA_VERSION
        or any(
            not isinstance(provenance[name], str) or not provenance[name]
            for name in ("module_version", "python_version", "numpy_version")
        )
    ):
        raise ValueError("unsupported or malformed bath provenance")
    epsilon = _validate_numeric_sequence(payload["epsilon"], "bath epsilon")
    coupling = _validate_numeric_sequence(
        payload["V"], "bath V", nonnegative=True
    )
    if len(epsilon) != n_bath or len(coupling) != n_bath:
        raise ValueError("bath epsilon and V lengths must equal n_bath")
    return {
        "epsilon": epsilon,
        "V": coupling,
        "n_bath": n_bath,
        "sha256": digest,
        "parameters": copy.deepcopy(payload["parameters"]),
        "artifact": artifact_copy,
    }


def _validate_tau(tau: Any, beta: float) -> list[float]:
    values = _validate_numeric_sequence(tau, "tau")
    if not values:
        raise ValueError("tau must contain at least one point")
    if any(right < left for left, right in zip(values, values[1:])):
        raise ValueError("tau must be monotonically nondecreasing")
    if values[0] < 0.0 or values[-1] > beta:
        raise ValueError("tau values must lie in [0, beta]")
    return values


def _operator_in_eigenbasis(
    eigenvectors: np.ndarray, *, mode: int
) -> np.ndarray:
    dimension = eigenvectors.shape[0]
    applied = np.zeros_like(eigenvectors)
    lower_mask = (1 << mode) - 1
    mode_mask = 1 << mode
    for source in range(dimension):
        if source & mode_mask:
            target = source ^ mode_mask
            sign = -1.0 if (source & lower_mask).bit_count() & 1 else 1.0
            applied[target, :] = sign * eigenvectors[source, :]
    return eigenvectors.T @ applied


def _diagonal_expectation(
    eigenvectors: np.ndarray,
    scaled_weights: np.ndarray,
    diagonal: np.ndarray,
    scaled_partition: float,
) -> float:
    eigenstate_diagonal = np.sum(eigenvectors**2 * diagonal[:, None], axis=0)
    return float(np.dot(scaled_weights, eigenstate_diagonal) / scaled_partition)


def solve_finite_bath(
    *,
    bath_artifact: dict[str, Any],
    U: float,
    beta: float,
    tau: Sequence[float],
    epsilon_d: float | None = None,
    mu: float = 0.0,
    max_dimension: int = MAX_DENSE_DIMENSION,
    max_dense_bytes: int = MAX_DENSE_BYTES,
) -> dict[str, Any]:
    """Exactly diagonalize a small finite bath and return thermal observables."""

    consumed_bath = _consume_bath_artifact(bath_artifact)
    return _solve_consumed_bath(
        consumed_bath=consumed_bath,
        U=U,
        beta=beta,
        tau=tau,
        epsilon_d=epsilon_d,
        mu=mu,
        max_dimension=max_dimension,
        max_dense_bytes=max_dense_bytes,
    )


def _solve_consumed_bath(
    *,
    consumed_bath: dict[str, Any],
    U: Any,
    beta: Any,
    tau: Any,
    epsilon_d: Any,
    mu: Any,
    max_dimension: Any,
    max_dense_bytes: Any,
) -> dict[str, Any]:
    epsilon = consumed_bath["epsilon"]
    coupling = consumed_bath["V"]
    n_bath = consumed_bath["n_bath"]
    beta = _validate_real(beta, "beta")
    if beta < 0.0:
        raise ValueError("beta must be finite and nonnegative")
    tau_values = _validate_tau(tau, beta)
    (
        epsilon,
        coupling,
        U,
        epsilon_d,
        mu,
        dimension,
        max_dimension,
        max_dense_bytes,
    ) = _validated_model_inputs(
        epsilon=epsilon,
        V=coupling,
        U=U,
        epsilon_d=epsilon_d,
        mu=mu,
        max_dimension=max_dimension,
        max_dense_bytes=max_dense_bytes,
    )
    hamiltonian = build_hamiltonian(
        epsilon=epsilon,
        V=coupling,
        U=U,
        epsilon_d=epsilon_d,
        mu=mu,
        max_dimension=max_dimension,
        max_dense_bytes=max_dense_bytes,
    )
    eigenvalues, eigenvectors = np.linalg.eigh(hamiltonian)
    energy_minimum = float(eigenvalues[0])
    shifted_energies = eigenvalues - energy_minimum
    scaled_weights = np.exp(-beta * shifted_energies)
    scaled_partition = float(np.sum(scaled_weights))
    log_partition = -beta * energy_minimum + math.log(scaled_partition)
    if beta == 0.0:
        partition = float(dimension)
        log_partition = math.log(dimension)
    else:
        partition = (
            math.exp(log_partition)
            if log_partition <= math.log(np.finfo(np.float64).max)
            else None
        )
    partition_status = "finite" if partition is not None else "overflow"

    states = np.arange(dimension, dtype=np.uint64)
    n_up_diagonal = ((states >> np.uint64(0)) & np.uint64(1)).astype(float)
    n_down_diagonal = ((states >> np.uint64(1)) & np.uint64(1)).astype(float)
    n_up = _diagonal_expectation(
        eigenvectors, scaled_weights, n_up_diagonal, scaled_partition
    )
    n_down = _diagonal_expectation(
        eigenvectors, scaled_weights, n_down_diagonal, scaled_partition
    )
    double_occupancy = _diagonal_expectation(
        eigenvectors,
        scaled_weights,
        n_up_diagonal * n_down_diagonal,
        scaled_partition,
    )

    green_by_spin: dict[str, list[float]] = {}
    for spin, mode in (("up", 0), ("down", 1)):
        annihilation = _operator_in_eigenbasis(eigenvectors, mode=mode)
        spectral_weight = annihilation**2
        values: list[float] = []
        for tau_value in tau_values:
            exponent = (
                -(beta - tau_value) * shifted_energies[:, None]
                - tau_value * shifted_energies[None, :]
            )
            numerator = float(np.sum(np.exp(exponent) * spectral_weight))
            values.append(-numerator / scaled_partition)
        green_by_spin[spin] = values
    average_green = [
        0.5 * (up + down)
        for up, down in zip(green_by_spin["up"], green_by_spin["down"])
    ]

    return {
        "Z": partition,
        "Z_status": partition_status,
        "logZ": log_partition,
        "occupancy": {
            "up": n_up,
            "down": n_down,
            "total": n_up + n_down,
        },
        "double_occupancy": double_occupancy,
        "green_function": {
            "up": green_by_spin["up"],
            "down": green_by_spin["down"],
            "average": average_green,
        },
        "tau": tau_values,
        "hilbert_dimension": dimension,
        "n_modes": 2 * (n_bath + 1),
        "max_dimension": max_dimension,
        "max_dense_bytes": max_dense_bytes,
    }


def _mode_order(n_bath: int) -> list[str]:
    order = ["d_up", "d_down"]
    for bath_index in range(1, n_bath + 1):
        order.extend([f"c{bath_index}_up", f"c{bath_index}_down"])
    return order


def make_oracle_artifact(
    *,
    bath_artifact: dict[str, Any],
    U: float,
    beta: float,
    tau: Sequence[float],
    epsilon_d: float | None = None,
    mu: float = 0.0,
    max_dimension: int = MAX_DENSE_DIMENSION,
    max_dense_bytes: int = MAX_DENSE_BYTES,
) -> dict[str, Any]:
    """Build a deterministic, integrity-auditable finite-bath ED artifact."""

    consumed_bath = _consume_bath_artifact(bath_artifact)
    epsilon = consumed_bath["epsilon"]
    coupling = consumed_bath["V"]
    n_bath = consumed_bath["n_bath"]
    bath_digest = consumed_bath["sha256"]
    bath_parameters = consumed_bath["parameters"]
    U_value = _validate_real(U, "U")
    epsilon_d_value = (
        -U_value / 2.0
        if epsilon_d is None
        else _validate_real(epsilon_d, "epsilon_d")
    )
    mu_value = _validate_real(mu, "mu")
    result = _solve_consumed_bath(
        consumed_bath=consumed_bath,
        U=U_value,
        beta=beta,
        tau=tau,
        epsilon_d=epsilon_d_value,
        mu=mu_value,
        max_dimension=max_dimension,
        max_dense_bytes=max_dense_bytes,
    )
    dimension = result["hilbert_dimension"]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "parameters": {
            "U": U_value,
            "epsilon_d": epsilon_d_value,
            "mu": mu_value,
            "beta": _validate_real(beta, "beta"),
            "n_bath": n_bath,
            "grand_canonical": True,
            "max_dimension": result["max_dimension"],
            "max_dense_bytes": result["max_dense_bytes"],
        },
        "bath": {
            "parameters": copy.deepcopy(bath_parameters),
            "epsilon": epsilon.copy(),
            "V": coupling.copy(),
        },
        "bath_input": copy.deepcopy(consumed_bath["artifact"]),
        "bath_input_sha256": bath_digest,
        "conventions": dict(ORACLE_CONVENTIONS),
        "mode_order": _mode_order(n_bath),
        "tau": result["tau"],
        "observables": {
            "Z": result["Z"],
            "Z_status": result["Z_status"],
            "logZ": result["logZ"],
            "occupancy": copy.deepcopy(result["occupancy"]),
            "double_occupancy": result["double_occupancy"],
            "green_function": copy.deepcopy(result["green_function"]),
        },
        "resources": {
            "n_modes": result["n_modes"],
            "hilbert_dimension": dimension,
            "dense_peak_memory_estimate_bytes": (
                estimate_dense_peak_memory_bytes(dimension)
            ),
            "dense_peak_memory_model": DENSE_PEAK_MEMORY_MODEL,
            "storage_cost": STORAGE_COST,
            "diagonalization_cost": DIAGONALIZATION_COST,
            "enforced_max_dimension": result["max_dimension"],
            "enforced_max_dense_bytes": result["max_dense_bytes"],
        },
        "provenance": {
            "module": "finite_bath_ed",
            "module_version": MODULE_VERSION,
            "python_version": platform.python_version(),
            "numpy_version": np.__version__,
            "eigensolver": "numpy.linalg.eigh",
            "schema_version": SCHEMA_VERSION,
        },
    }
    return {
        "payload": payload,
        "sha256": hashlib.sha256(_canonical_json(payload)).hexdigest(),
    }


def _validate_finite_tree(value: Any, name: str) -> None:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, numbers.Real):
        if not math.isfinite(float(value)):
            raise ValueError(f"{name} contains nonfinite numeric values")
        return
    if isinstance(value, list):
        for item in value:
            _validate_finite_tree(item, name)
        return
    if isinstance(value, dict):
        for item in value.values():
            _validate_finite_tree(item, name)
        return
    raise TypeError(f"{name} contains a non-JSON value")


def _verify_oracle_structure_only(artifact: Any) -> dict[str, Any]:
    """Check canonical integrity and structure, but not scientific authenticity."""

    _require_keys(artifact, {"payload", "sha256"}, "oracle artifact")
    payload = artifact["payload"]
    if not isinstance(payload, dict):
        raise TypeError("oracle artifact payload must be a JSON object")
    digest = _validate_digest(artifact["sha256"], "oracle artifact SHA256")
    expected = hashlib.sha256(_canonical_json(payload)).hexdigest()
    if not hmac.compare_digest(digest, expected):
        raise ValueError("oracle artifact payload SHA256 mismatch")
    _require_keys(
        payload,
        {
            "schema_version",
            "parameters",
            "bath",
            "bath_input",
            "bath_input_sha256",
            "conventions",
            "mode_order",
            "tau",
            "observables",
            "resources",
            "provenance",
        },
        "oracle payload",
    )
    if (
        type(payload["schema_version"]) is not int
        or payload["schema_version"] != SCHEMA_VERSION
    ):
        raise ValueError(
            f"unsupported oracle schema version: {payload['schema_version']!r}"
        )
    _require_keys(
        payload["parameters"],
        {
            "U",
            "epsilon_d",
            "mu",
            "beta",
            "n_bath",
            "grand_canonical",
            "max_dimension",
            "max_dense_bytes",
        },
        "oracle parameters",
    )
    parameters = payload["parameters"]
    _validate_real(parameters["U"], "oracle U")
    _validate_real(parameters["epsilon_d"], "oracle epsilon_d")
    _validate_real(parameters["mu"], "oracle mu")
    beta = _validate_real(parameters["beta"], "oracle beta")
    if beta < 0.0:
        raise ValueError("oracle beta must be nonnegative")
    n_bath = _validate_integer(
        parameters["n_bath"], "oracle n_bath", positive=True
    )
    if parameters["grand_canonical"] is not True:
        raise ValueError("oracle must use the full grand-canonical space")
    configured_max_dimension = _validate_integer(
        parameters["max_dimension"],
        "oracle configured max dimension",
        positive=True,
    )
    configured_max_dense_bytes = _validate_integer(
        parameters["max_dense_bytes"],
        "oracle configured max dense bytes",
        positive=True,
    )
    if (
        configured_max_dimension > MAX_DENSE_DIMENSION
        or configured_max_dense_bytes > MAX_DENSE_BYTES
    ):
        raise ValueError("oracle configured resource guards exceed safe limits")

    bath_digest = _validate_digest(
        payload["bath_input_sha256"], "bath input SHA256"
    )
    consumed_bath = _consume_bath_artifact(payload["bath_input"])
    if consumed_bath["sha256"] != bath_digest:
        raise ValueError("embedded bath input SHA256 linkage mismatch")
    _require_keys(payload["bath"], {"parameters", "epsilon", "V"}, "oracle bath")
    if (
        payload["bath"]["parameters"] != consumed_bath["parameters"]
        or payload["bath"]["epsilon"] != consumed_bath["epsilon"]
        or payload["bath"]["V"] != consumed_bath["V"]
        or consumed_bath["n_bath"] != n_bath
    ):
        raise ValueError("embedded bath arrays or parameters do not match input")

    _require_keys(
        payload["conventions"], set(ORACLE_CONVENTIONS), "oracle conventions"
    )
    if payload["conventions"] != ORACLE_CONVENTIONS:
        raise ValueError("oracle convention claims do not match supported values")

    expected_mode_order = _mode_order(n_bath)
    if payload["mode_order"] != expected_mode_order:
        raise ValueError("oracle mode order is not canonical")

    tau = _validate_tau(payload["tau"], beta)
    expected_resource_keys = {
        "n_modes",
        "hilbert_dimension",
        "dense_peak_memory_estimate_bytes",
        "dense_peak_memory_model",
        "storage_cost",
        "diagonalization_cost",
        "enforced_max_dimension",
        "enforced_max_dense_bytes",
    }
    _require_keys(
        payload["resources"], expected_resource_keys, "oracle resources"
    )
    resources = payload["resources"]
    if set(resources) != expected_resource_keys:
        raise ValueError("oracle resources contain unsupported claims")
    expected_n_modes = 2 * (n_bath + 1)
    expected_dimension = 1 << expected_n_modes
    n_modes = _validate_integer(resources["n_modes"], "resource n_modes")
    dimension = _validate_integer(
        resources["hilbert_dimension"], "resource hilbert_dimension", positive=True
    )
    if n_modes != expected_n_modes or dimension != expected_dimension:
        raise ValueError("oracle Hilbert-space resources are inconsistent")
    expected_memory = estimate_dense_peak_memory_bytes(dimension)
    memory = _validate_integer(
        resources["dense_peak_memory_estimate_bytes"],
        "resource dense peak memory",
        positive=True,
    )
    enforced_dimension = _validate_integer(
        resources["enforced_max_dimension"],
        "resource enforced max dimension",
        positive=True,
    )
    enforced_bytes = _validate_integer(
        resources["enforced_max_dense_bytes"],
        "resource enforced max dense bytes",
        positive=True,
    )
    if (
        memory != expected_memory
        or resources["dense_peak_memory_model"] != DENSE_PEAK_MEMORY_MODEL
        or resources["storage_cost"] != STORAGE_COST
        or resources["diagonalization_cost"] != DIAGONALIZATION_COST
        or dimension > enforced_dimension
        or enforced_dimension > MAX_DENSE_DIMENSION
        or memory > enforced_bytes
        or enforced_bytes > MAX_DENSE_BYTES
        or enforced_dimension != configured_max_dimension
        or enforced_bytes != configured_max_dense_bytes
    ):
        raise ValueError("oracle dense resource accounting is inconsistent")

    _require_keys(
        payload["observables"],
        {
            "Z",
            "Z_status",
            "logZ",
            "occupancy",
            "double_occupancy",
            "green_function",
        },
        "oracle observables",
    )
    observables = payload["observables"]
    log_partition = _validate_real(observables["logZ"], "oracle logZ")
    if log_partition < -1e-12:
        raise ValueError("oracle logZ must be nonnegative for a Fock-space trace")
    partition_status = observables["Z_status"]
    if partition_status == "finite":
        partition = _validate_real(observables["Z"], "oracle Z")
        if partition <= 0.0 or not math.isclose(
            math.log(partition), log_partition, rel_tol=0.0, abs_tol=2e-12
        ):
            raise ValueError("oracle finite Z and logZ are inconsistent")
    elif partition_status == "overflow":
        if (
            observables["Z"] is not None
            or log_partition <= math.log(np.finfo(np.float64).max)
        ):
            raise ValueError("oracle overflowed Z status is inconsistent")
    else:
        raise ValueError("oracle Z_status must be 'finite' or 'overflow'")

    _require_keys(
        observables["occupancy"],
        {"up", "down", "total"},
        "oracle occupancy",
    )
    occupancy = observables["occupancy"]
    n_up = _validate_real(occupancy["up"], "oracle up occupancy")
    n_down = _validate_real(occupancy["down"], "oracle down occupancy")
    n_total = _validate_real(occupancy["total"], "oracle total occupancy")
    if (
        not 0.0 <= n_up <= 1.0
        or not 0.0 <= n_down <= 1.0
        or not 0.0 <= n_total <= 2.0
        or not math.isclose(n_total, n_up + n_down, abs_tol=2e-12)
    ):
        raise ValueError("oracle occupancies are out of range or inconsistent")
    double_occupancy = _validate_real(
        observables["double_occupancy"], "oracle double occupancy"
    )
    lower_double_bound = max(0.0, n_up + n_down - 1.0)
    if (
        double_occupancy < lower_double_bound - 2e-12
        or double_occupancy > min(n_up, n_down) + 2e-12
    ):
        raise ValueError("oracle double occupancy is out of range")

    _require_keys(
        observables["green_function"],
        {"up", "down", "average"},
        "oracle Green function",
    )
    green: dict[str, list[float]] = {}
    for spin in ("up", "down", "average"):
        green[spin] = _validate_numeric_sequence(
            observables["green_function"][spin],
            f"oracle Green function {spin}",
        )
        if len(green[spin]) != len(tau):
            raise ValueError("oracle Green function length must match tau")
    if any(
        not math.isclose(
            average, 0.5 * (up + down), rel_tol=0.0, abs_tol=2e-12
        )
        for up, down, average in zip(
            green["up"], green["down"], green["average"]
        )
    ):
        raise ValueError("oracle averaged Green function is inconsistent")
    if tau[0] == 0.0:
        for spin, occupation in (("up", n_up), ("down", n_down)):
            if not math.isclose(
                green[spin][0], -(1.0 - occupation), abs_tol=2e-10
            ):
                raise ValueError("oracle G(0+) endpoint identity failed")
    if tau[-1] == beta:
        for spin, occupation in (("up", n_up), ("down", n_down)):
            if not math.isclose(
                green[spin][-1], -occupation, abs_tol=2e-10
            ):
                raise ValueError("oracle G(beta-) endpoint identity failed")

    _require_keys(
        payload["provenance"],
        {
            "module",
            "module_version",
            "python_version",
            "numpy_version",
            "eigensolver",
            "schema_version",
        },
        "oracle provenance",
    )
    provenance = payload["provenance"]
    if (
        provenance["module"] != "finite_bath_ed"
        or type(provenance["schema_version"]) is not int
        or provenance["schema_version"] != SCHEMA_VERSION
        or any(
            not isinstance(provenance[name], str) or not provenance[name]
            for name in (
                "module_version",
                "python_version",
                "numpy_version",
                "eigensolver",
            )
        )
    ):
        raise ValueError("oracle provenance is malformed or unsupported")
    _validate_finite_tree(payload, "oracle payload")
    return {
        "parameters": parameters,
        "tau": tau,
        "observables": observables,
        "resources": resources,
        "consumed_bath": consumed_bath,
    }


def _require_scientific_close(
    reported: Any, recomputed: Any, name: str
) -> None:
    if not math.isclose(
        float(reported),
        float(recomputed),
        rel_tol=2e-12,
        abs_tol=2e-12,
    ):
        raise ValueError(
            f"oracle scientific verification failed for {name}: "
            f"reported {reported!r}, recomputed {recomputed!r}"
        )


def verify_oracle_artifact(artifact: Any) -> None:
    """Scientifically verify integrity by independently rerunning dense ED."""

    checked = _verify_oracle_structure_only(artifact)
    parameters = checked["parameters"]
    observables = checked["observables"]
    resources = checked["resources"]
    recomputed = _solve_consumed_bath(
        consumed_bath=checked["consumed_bath"],
        U=parameters["U"],
        beta=parameters["beta"],
        tau=checked["tau"],
        epsilon_d=parameters["epsilon_d"],
        mu=parameters["mu"],
        max_dimension=parameters["max_dimension"],
        max_dense_bytes=parameters["max_dense_bytes"],
    )

    _require_scientific_close(
        observables["logZ"], recomputed["logZ"], "logZ"
    )
    if observables["Z_status"] != recomputed["Z_status"]:
        raise ValueError(
            "oracle scientific verification failed for Z_status"
        )
    if recomputed["Z_status"] == "finite":
        _require_scientific_close(observables["Z"], recomputed["Z"], "Z")
    elif observables["Z"] is not None:
        raise ValueError(
            "oracle scientific verification failed for overflowed Z"
        )

    for spin in ("up", "down", "total"):
        _require_scientific_close(
            observables["occupancy"][spin],
            recomputed["occupancy"][spin],
            f"{spin} occupancy",
        )
    _require_scientific_close(
        observables["double_occupancy"],
        recomputed["double_occupancy"],
        "double occupancy",
    )
    for spin in ("up", "down", "average"):
        reported_green = np.asarray(
            observables["green_function"][spin], dtype=np.float64
        )
        recomputed_green = np.asarray(
            recomputed["green_function"][spin], dtype=np.float64
        )
        if not np.allclose(
            reported_green,
            recomputed_green,
            rtol=2e-12,
            atol=2e-12,
        ):
            raise ValueError(
                "oracle scientific verification failed for "
                f"{spin} Green function"
            )

    if (
        checked["tau"] != recomputed["tau"]
        or resources["n_modes"] != recomputed["n_modes"]
        or resources["hilbert_dimension"] != recomputed["hilbert_dimension"]
        or resources["enforced_max_dimension"]
        != recomputed["max_dimension"]
        or resources["enforced_max_dense_bytes"]
        != recomputed["max_dense_bytes"]
        or resources["dense_peak_memory_estimate_bytes"]
        != estimate_dense_peak_memory_bytes(recomputed["hilbert_dimension"])
    ):
        raise ValueError(
            "oracle scientific verification failed for dimensions or resources"
        )


def _fsync_directory(directory: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(directory, flags)
    try:
        os.fsync(descriptor)
    except BaseException:
        try:
            os.close(descriptor)
        except BaseException:
            pass
        raise
    os.close(descriptor)


def _hardlink_backup(destination: Path) -> Path:
    descriptor, name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".backup",
    )
    os.close(descriptor)
    os.unlink(name)
    backup_path = Path(name)
    try:
        os.link(destination, backup_path, follow_symlinks=False)
        with backup_path.open("rb") as backup:
            os.fsync(backup.fileno())
    except BaseException:
        try:
            backup_path.unlink(missing_ok=True)
        except BaseException:
            pass
        raise
    return backup_path


def write_oracle_json(
    path: str | os.PathLike[str],
    *,
    bath_artifact: dict[str, Any],
    U: float,
    beta: float,
    tau: Sequence[float],
    epsilon_d: float | None = None,
    mu: float = 0.0,
    max_dimension: int = MAX_DENSE_DIMENSION,
    max_dense_bytes: int = MAX_DENSE_BYTES,
) -> dict[str, Any]:
    """Atomically publish canonical oracle JSON and return the artifact."""

    destination = Path(path)
    artifact = make_oracle_artifact(
        bath_artifact=bath_artifact,
        U=U,
        beta=beta,
        tau=tau,
        epsilon_d=epsilon_d,
        mu=mu,
        max_dimension=max_dimension,
        max_dense_bytes=max_dense_bytes,
    )
    verify_oracle_artifact(artifact)
    encoded = _canonical_json(artifact) + b"\n"
    temporary_path: Path | None = None
    backup_path: Path | None = None
    published = False
    try:
        try:
            destination_status = destination.lstat()
        except FileNotFoundError:
            destination_status = None
        if destination_status is not None:
            if not stat.S_ISREG(destination_status.st_mode):
                raise ValueError(
                    "existing destination must be a regular file, "
                    "not a directory, symlink, or special file"
                )
            backup_path = _hardlink_backup(destination)
            _fsync_directory(destination.parent)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(encoded)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, destination)
        published = True
        _fsync_directory(destination.parent)
        if backup_path is not None:
            backup_path.unlink()
            backup_path = None
            _fsync_directory(destination.parent)
    except BaseException:
        if published:
            try:
                if backup_path is not None:
                    os.replace(backup_path, destination)
                    backup_path = None
                else:
                    destination.unlink(missing_ok=True)
                try:
                    _fsync_directory(destination.parent)
                except BaseException:
                    pass
            except BaseException:
                pass
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except BaseException:
                pass
        if backup_path is not None:
            try:
                backup_path.unlink(missing_ok=True)
            except BaseException:
                pass
        raise
    return artifact
