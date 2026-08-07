"""Stabilized transfer-matrix products with Householder QR."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

NumericArray = NDArray[np.float64] | NDArray[np.complex128]


class LyapunovQR:
    """Accumulate finite-product Lyapunov exponents with a fixed QR interval."""

    def __init__(
        self,
        dimension: int,
        qr_interval: int,
        *,
        complex_valued: bool = False,
        initial_basis: NumericArray | None = None,
    ) -> None:
        if dimension < 1:
            raise ValueError("dimension must be positive")
        if qr_interval < 1:
            raise ValueError("qr_interval must be positive")
        self.dimension = int(dimension)
        self.qr_interval = int(qr_interval)
        self.complex_valued = bool(complex_valued)
        dtype = np.complex128 if self.complex_valued else np.float64
        basis = (
            np.eye(self.dimension, dtype=dtype)
            if initial_basis is None
            else np.asarray(initial_basis, dtype=dtype)
        )
        if basis.shape != (self.dimension, self.dimension):
            raise ValueError("initial_basis shape mismatch")
        if not np.all(np.isfinite(basis)):
            raise ValueError("initial_basis must be finite")
        self._basis = basis.copy()
        self._log_diagonal = np.zeros(self.dimension, dtype=np.float64)
        self._layer_count = 0
        self._layers_since_qr = 0
        self._qr_count = 0
        self._last_orthogonality_error = 0.0
        self._max_orthogonality_error = 0.0

    @property
    def layer_count(self) -> int:
        return self._layer_count

    @property
    def layers_since_qr(self) -> int:
        return self._layers_since_qr

    @property
    def qr_count(self) -> int:
        return self._qr_count

    @property
    def basis(self) -> NumericArray:
        return self._basis.copy()

    @property
    def log_diagonal(self) -> NDArray[np.float64]:
        return self._log_diagonal.copy()

    @property
    def last_orthogonality_error(self) -> float:
        return self._last_orthogonality_error

    @property
    def max_orthogonality_error(self) -> float:
        return self._max_orthogonality_error

    def push(self, transfer: NumericArray) -> bool:
        dtype = np.complex128 if self.complex_valued else np.float64
        matrix = np.asarray(transfer, dtype=dtype)
        if matrix.shape != (self.dimension, self.dimension):
            raise ValueError(
                f"transfer must have shape {(self.dimension, self.dimension)}"
            )
        if not np.all(np.isfinite(matrix)):
            raise ValueError("transfer matrix must be finite")
        self._basis = matrix @ self._basis
        if not np.all(np.isfinite(self._basis)):
            raise FloatingPointError("transfer product became non-finite before QR")
        self._layer_count += 1
        self._layers_since_qr += 1
        if self._layers_since_qr == self.qr_interval:
            self.reorthogonalize()
            return True
        return False

    def reorthogonalize(self) -> None:
        if self._layers_since_qr == 0:
            return
        q_matrix, r_matrix = np.linalg.qr(self._basis, mode="reduced")
        diagonal = np.diag(r_matrix)
        magnitudes = np.abs(diagonal)
        if np.any(magnitudes == 0.0) or not np.all(np.isfinite(magnitudes)):
            raise np.linalg.LinAlgError("rank-deficient or non-finite QR diagonal")

        phases = diagonal / magnitudes
        q_matrix = q_matrix * phases[None, :]
        r_matrix = np.conjugate(phases)[:, None] * r_matrix
        normalized_diagonal = np.real_if_close(np.diag(r_matrix))
        if not np.all(np.real(normalized_diagonal) > 0.0):
            raise RuntimeError("failed to enforce positive QR diagonal")

        self._log_diagonal += np.log(magnitudes)
        self._basis = q_matrix
        identity = np.eye(self.dimension, dtype=q_matrix.dtype)
        error = float(
            np.linalg.norm(
                np.conjugate(q_matrix.T) @ q_matrix - identity,
                ord=np.inf,
            )
        )
        self._last_orthogonality_error = error
        self._max_orthogonality_error = max(
            self._max_orthogonality_error, error
        )
        self._layers_since_qr = 0
        self._qr_count += 1

    def finalize(self) -> NDArray[np.float64]:
        if self._layer_count == 0:
            raise RuntimeError("cannot finalize an empty transfer product")
        self.reorthogonalize()
        exponents = self._log_diagonal / self._layer_count
        if not np.all(np.isfinite(exponents)):
            raise FloatingPointError("Lyapunov exponents are non-finite")
        return exponents.copy()

    def export_state(self) -> tuple[dict[str, Any], dict[str, NumericArray]]:
        metadata = {
            "dimension": self.dimension,
            "qr_interval": self.qr_interval,
            "complex_valued": self.complex_valued,
            "layer_count": self.layer_count,
            "layers_since_qr": self.layers_since_qr,
            "qr_count": self.qr_count,
            "last_orthogonality_error": self.last_orthogonality_error,
            "max_orthogonality_error": self.max_orthogonality_error,
        }
        arrays = {
            "basis": self.basis,
            "log_diagonal": self.log_diagonal,
        }
        return metadata, arrays

    @classmethod
    def from_state(
        cls,
        metadata: dict[str, Any],
        basis: NumericArray,
        log_diagonal: NDArray[np.floating],
    ) -> "LyapunovQR":
        accumulator = cls(
            dimension=int(metadata["dimension"]),
            qr_interval=int(metadata["qr_interval"]),
            complex_valued=bool(metadata["complex_valued"]),
            initial_basis=basis,
        )
        logs = np.asarray(log_diagonal, dtype=np.float64)
        if logs.shape != (accumulator.dimension,):
            raise ValueError("checkpoint log_diagonal shape mismatch")
        if not np.all(np.isfinite(logs)):
            raise ValueError("checkpoint log_diagonal must be finite")
        layer_count = int(metadata["layer_count"])
        pending = int(metadata["layers_since_qr"])
        qr_count = int(metadata["qr_count"])
        if layer_count < 0 or not 0 <= pending < accumulator.qr_interval:
            raise ValueError("checkpoint Lyapunov counters are invalid")
        if qr_count < 0:
            raise ValueError("checkpoint qr_count is invalid")
        accumulator._log_diagonal = logs.copy()
        accumulator._layer_count = layer_count
        accumulator._layers_since_qr = pending
        accumulator._qr_count = qr_count
        accumulator._last_orthogonality_error = float(
            metadata["last_orthogonality_error"]
        )
        accumulator._max_orthogonality_error = float(
            metadata["max_orthogonality_error"]
        )
        return accumulator
