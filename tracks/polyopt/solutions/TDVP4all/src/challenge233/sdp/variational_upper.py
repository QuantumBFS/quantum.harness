"""Exact variational upper bounds guided by sparse QuSpin eigenvectors."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import struct
from typing import Iterable


TRIAL_PURPOSE = "finite-N-pxp-variational-upper-bound"
TRUSTED_BASIS_RELATIVE_PATH = "external/1d-basis/pxpbasis.py"
SIGNED_INT64_MIN = -(1 << 63)
SIGNED_INT64_MAX = (1 << 63) - 1


def _validate_size(size: int) -> int:
    if isinstance(size, bool) or not isinstance(size, int):
        raise TypeError("size must be an integer")
    if not 4 <= size <= 20:
        raise ValueError("size must satisfy 4 <= size <= 20")
    return size


def _validate_detuning(detuning: Fraction) -> Fraction:
    if not isinstance(detuning, Fraction):
        raise TypeError("detuning must be an exact Fraction")
    return detuning


def _is_periodic_legal(size: int, state: int) -> bool:
    return all(
        not (
            (state >> site) & 1
            and (state >> ((site + 1) % size)) & 1
        )
        for site in range(size)
    )


def _periodic_blockade_dimension(size: int) -> int:
    previous, current = 2, 1
    for _ in range(size):
        previous, current = current, previous + current
    return previous


def _encode_fraction(value: Fraction) -> str:
    value = Fraction(value)
    return f"{value.numerator}/{value.denominator}"


def _packed_u64(values: Iterable[int]) -> bytes:
    return b"".join(struct.pack("<Q", value) for value in values)


def _packed_i64(values: Iterable[int]) -> bytes:
    return b"".join(struct.pack("<q", value) for value in values)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


@dataclass(frozen=True)
class TrialVector:
    size: int
    detuning: Fraction
    bits: int
    states: tuple[int, ...]
    coefficients: tuple[int, ...]
    basis_dimension: int
    basis_state_order_sha256: str
    guidance_energy: float
    residual_norm: float
    arpack_tolerance: float
    random_seed: int
    quspin_version: str
    numpy_version: str
    scipy_version: str
    trusted_basis_path: str
    trusted_basis_sha256: str

    @property
    def coefficient_norm_squared(self) -> int:
        return sum(
            coefficient * coefficient
            for coefficient in self.coefficients
        )

    @property
    def b_var(self) -> Fraction:
        return exact_rayleigh_quotient(
            self.size,
            self.detuning,
            self.states,
            self.coefficients,
        )

    @property
    def rayleigh_numerator(self) -> Fraction:
        return self.b_var * self.coefficient_norm_squared


def exact_rayleigh_quotient(
    size: int,
    detuning: Fraction,
    states,
    coefficients,
) -> Fraction:
    """Compute ``qᵀHq/qᵀq`` exactly by directed legal PXP flips."""
    size = _validate_size(size)
    detuning = _validate_detuning(detuning)
    states = tuple(states)
    coefficients = tuple(coefficients)
    if len(states) != len(coefficients):
        raise ValueError("states and coefficients must have the same length")
    if not states:
        raise ValueError("trial vector must not be empty")

    coefficient_by_state = {}
    for state, coefficient in zip(states, coefficients):
        if (
            isinstance(state, bool)
            or not isinstance(state, int)
            or not 0 <= state < (1 << size)
        ):
            raise ValueError("trial state must fit the declared size")
        if not _is_periodic_legal(size, state):
            raise ValueError("trial contains an illegal periodic state")
        if state in coefficient_by_state:
            raise ValueError("trial contains a duplicate state")
        if isinstance(coefficient, bool) or not isinstance(coefficient, int):
            raise TypeError("trial coefficients must be integers")
        coefficient_by_state[state] = coefficient

    denominator = sum(
        coefficient * coefficient
        for coefficient in coefficients
    )
    if denominator == 0:
        raise ValueError("trial coefficients define the zero vector")

    rabi_numerator = 0
    occupation_weight = 0
    for state, coefficient in coefficient_by_state.items():
        occupation_weight += (
            bin(state).count("1") * coefficient * coefficient
        )
        for site in range(size):
            target = state ^ (1 << site)
            rabi_numerator += (
                coefficient
                * coefficient_by_state.get(target, 0)
            )

    numerator = (
        Fraction(rabi_numerator)
        - detuning * occupation_weight
    )
    return numerator / denominator


def round_trial_vector(vector, bits: int) -> tuple[int, ...]:
    """Round a real normalized vector to signed integers over ``2**bits``."""
    if isinstance(bits, bool) or not isinstance(bits, int):
        raise TypeError("bits must be an integer")
    if not 0 <= bits <= 62:
        raise ValueError("bits must satisfy 0 <= bits <= 62")
    vector = tuple(vector)
    if not vector:
        raise ValueError("trial vector must not be empty")

    scale = 1 << bits
    rounded = []
    for entry in vector:
        value = complex(entry)
        if not math.isfinite(value.real) or not math.isfinite(value.imag):
            raise ValueError("trial vector contains a non-finite entry")
        if value.imag != 0.0:
            raise ValueError("trial vector must be real")
        coefficient = round(scale * value.real)
        if not SIGNED_INT64_MIN <= coefficient <= SIGNED_INT64_MAX:
            raise OverflowError("rounded coefficient does not fit int64")
        rounded.append(coefficient)
    if not any(rounded):
        raise ValueError("dyadic rounding produced the zero vector")
    return tuple(rounded)


def generate_quspin_trial(
    size: int,
    detuning: Fraction,
    bits: int = 40,
    tolerance: float = 1e-12,
    seed: int = 233,
) -> TrialVector:
    """Generate one sparse-ARPACK ground-state guide and round it dyadically."""
    size = _validate_size(size)
    detuning = _validate_detuning(detuning)
    if (
        isinstance(tolerance, bool)
        or not isinstance(tolerance, (int, float))
        or not math.isfinite(float(tolerance))
        or tolerance <= 0
    ):
        raise ValueError("tolerance must be a positive finite number")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")

    import numpy as np
    import quspin
    import scipy

    from challenge233.basis.pxp import build_constrained_basis
    from challenge233.ed.pxp_gap import build_pxp_hamiltonian

    basis = build_constrained_basis(size)
    expected_dimension = _periodic_blockade_dimension(size)
    if basis.Ns != expected_dimension:
        raise RuntimeError(
            "QuSpin constrained-basis dimension does not match "
            f"the Lucas count: {basis.Ns} != {expected_dimension}"
        )
    operator, energy_shift = build_pxp_hamiltonian(
        size,
        float(detuning),
    )
    if operator.Ns != basis.Ns:
        raise RuntimeError("Hamiltonian and constrained basis dimensions differ")

    initial_vector = np.random.default_rng(seed).standard_normal(basis.Ns)
    eigenvalues, eigenvectors = operator.eigsh(
        k=1,
        which="SA",
        tol=float(tolerance),
        maxiter=max(1000, 50 * basis.Ns),
        v0=initial_vector,
    )
    unshifted_energy = float(eigenvalues[0])
    eigenvector = np.asarray(eigenvectors[:, 0])
    if np.iscomplexobj(eigenvector):
        maximum_imaginary = float(np.max(np.abs(eigenvector.imag)))
        if maximum_imaginary > max(float(tolerance), 1e-14):
            raise RuntimeError("ground-state guide is unexpectedly complex")
        eigenvector = eigenvector.real
    else:
        eigenvector = eigenvector.astype(float, copy=False)
    pivot = int(np.argmax(np.abs(eigenvector)))
    if eigenvector[pivot] < 0:
        eigenvector = -eigenvector

    rounded = round_trial_vector(eigenvector, bits)
    retained = tuple(
        (int(state), int(coefficient))
        for state, coefficient in zip(basis.states, rounded)
        if coefficient
    )
    states = tuple(state for state, _ in retained)
    coefficients = tuple(coefficient for _, coefficient in retained)
    exact_rayleigh_quotient(size, detuning, states, coefficients)

    residual = float(
        np.linalg.norm(
            operator.dot(eigenvector)
            - unshifted_energy * eigenvector
        )
    )
    basis_state_bytes = _packed_u64(
        int(state) for state in basis.states
    )
    project_root = Path(__file__).resolve().parents[3]
    trusted_basis = project_root / TRUSTED_BASIS_RELATIVE_PATH
    return TrialVector(
        size=size,
        detuning=detuning,
        bits=bits,
        states=states,
        coefficients=coefficients,
        basis_dimension=basis.Ns,
        basis_state_order_sha256=_sha256_bytes(basis_state_bytes),
        guidance_energy=unshifted_energy + energy_shift,
        residual_norm=residual,
        arpack_tolerance=float(tolerance),
        random_seed=seed,
        quspin_version=str(quspin.__version__),
        numpy_version=str(np.__version__),
        scipy_version=str(scipy.__version__),
        trusted_basis_path=TRUSTED_BASIS_RELATIVE_PATH,
        trusted_basis_sha256=_sha256_file(trusted_basis),
    )


def write_trial_vector(trial: TrialVector, output_directory) -> dict:
    """Write binary integer data first and the hash-bound JSON metadata last."""
    if not isinstance(trial, TrialVector):
        raise TypeError("trial must be a TrialVector")
    _validate_size(trial.size)
    _validate_detuning(trial.detuning)
    if len(trial.states) != len(trial.coefficients):
        raise ValueError("trial states and coefficients must align")
    for coefficient in trial.coefficients:
        if not SIGNED_INT64_MIN <= coefficient <= SIGNED_INT64_MAX:
            raise OverflowError("trial coefficient does not fit int64")
    recomputed_b_var = exact_rayleigh_quotient(
        trial.size,
        trial.detuning,
        trial.states,
        trial.coefficients,
    )

    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    state_path = output_directory / "trial-states.u64le"
    coefficient_path = (
        output_directory / "trial-coefficients.i64le"
    )
    metadata_path = output_directory / "trial-vector.json"
    for path in (state_path, coefficient_path, metadata_path):
        if path.exists():
            raise FileExistsError(f"refusing to overwrite trial artifact: {path}")

    state_bytes = _packed_u64(trial.states)
    coefficient_bytes = _packed_i64(trial.coefficients)
    _atomic_write_bytes(state_path, state_bytes)
    _atomic_write_bytes(coefficient_path, coefficient_bytes)

    project_root = Path(__file__).resolve().parents[3]
    source_paths = (
        "src/challenge233/basis/pxp.py",
        "src/challenge233/ed/pxp_gap.py",
        "src/challenge233/sdp/variational_upper.py",
    )
    denominator = trial.coefficient_norm_squared
    metadata = {
        "schema_version": 1,
        "purpose": TRIAL_PURPOSE,
        "hamiltonian": (
            "H_N(delta)=sum_i P_{i-1} X_i P_{i+1}"
            "-delta sum_i n_i"
        ),
        "size": trial.size,
        "detuning": _encode_fraction(trial.detuning),
        "boundary": "periodic",
        "local_state_convention": "0=down, 1=up",
        "blockade_constraint": "n_i n_{i+1}=0",
        "rounding_bits": trial.bits,
        "nonzero_count": len(trial.states),
        "basis_state_count": trial.basis_dimension,
        "basis_state_order_sha256": trial.basis_state_order_sha256,
        "trusted_basis_path": trial.trusted_basis_path,
        "trusted_basis_sha256": trial.trusted_basis_sha256,
        "state_file": state_path.name,
        "state_file_bytes": len(state_bytes),
        "state_file_sha256": _sha256_bytes(state_bytes),
        "coefficient_file": coefficient_path.name,
        "coefficient_file_bytes": len(coefficient_bytes),
        "coefficient_file_sha256": _sha256_bytes(
            coefficient_bytes
        ),
        "rayleigh_numerator": _encode_fraction(
            trial.rayleigh_numerator
        ),
        "rayleigh_denominator": str(denominator),
        "b_var": _encode_fraction(recomputed_b_var),
        "guidance_energy": trial.guidance_energy,
        "arpack_tolerance": trial.arpack_tolerance,
        "arpack_residual": trial.residual_norm,
        "random_seed": trial.random_seed,
        "versions": {
            "python": platform.python_version(),
            "quspin": trial.quspin_version,
            "numpy": trial.numpy_version,
            "scipy": trial.scipy_version,
        },
        "thread_environment": {
            variable: os.environ.get(variable)
            for variable in (
                "OMP_NUM_THREADS",
                "MKL_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
            )
        },
        "source_file_sha256": {
            relative: _sha256_file(project_root / relative)
            for relative in source_paths
        },
    }
    metadata_bytes = (
        json.dumps(metadata, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    _atomic_write_bytes(metadata_path, metadata_bytes)
    return {
        "status": "written",
        "trial_vector_sha256": _sha256_bytes(metadata_bytes),
        "nonzero_count": len(trial.states),
        "b_var": metadata["b_var"],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate an exact dyadic PXP variational upper bound"
    )
    parser.add_argument("--size", type=int, required=True)
    parser.add_argument("--detuning", required=True)
    parser.add_argument("--bits", type=int, default=40)
    parser.add_argument("--tolerance", type=float, default=1e-12)
    parser.add_argument("--seed", type=int, default=233)
    parser.add_argument("--output-dir", required=True)
    arguments = parser.parse_args(argv)
    try:
        detuning = Fraction(arguments.detuning)
    except (ValueError, ZeroDivisionError) as error:
        parser.error(f"invalid exact detuning: {error}")

    trial = generate_quspin_trial(
        arguments.size,
        detuning,
        bits=arguments.bits,
        tolerance=arguments.tolerance,
        seed=arguments.seed,
    )
    summary = write_trial_vector(trial, arguments.output_dir)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
