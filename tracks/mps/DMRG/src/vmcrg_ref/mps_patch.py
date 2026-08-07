"""Direct physical-index open MPS for shared 3x3 Ising patches."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from .symmetries import transform_patches


@dataclass
class MPSGradient:
    cores: tuple[np.ndarray, ...]

    def copy(self) -> "MPSGradient":
        return MPSGradient(tuple(core.copy() for core in self.cores))

    def norm(self) -> float:
        return float(np.sqrt(sum(np.sum(core * core) for core in self.cores)))


class PatchMPS:
    """Nine-site open MPS with shared parameters across lattice patches."""

    sites = 9

    def __init__(
        self,
        chi: int,
        cores: Sequence[np.ndarray],
        symmetrize: bool = True,
    ) -> None:
        if chi < 1:
            raise ValueError("chi must be positive")
        if len(cores) != self.sites:
            raise ValueError("exactly nine MPS cores are required")
        self.chi = int(chi)
        self.symmetrize = bool(symmetrize)
        self.cores = tuple(np.asarray(core, dtype=np.float64).copy() for core in cores)
        expected = (
            (1, 2, self.chi),
            *((self.chi, 2, self.chi),) * 7,
            (self.chi, 2, 1),
        )
        for index, (core, shape) in enumerate(zip(self.cores, expected)):
            if core.shape != shape:
                raise ValueError(f"core {index} has shape {core.shape}, expected {shape}")
            if not np.all(np.isfinite(core)):
                raise ValueError("MPS parameters must all be finite")

    @classmethod
    def random(
        cls,
        chi: int,
        seed: int,
        symmetrize: bool = True,
    ) -> "PatchMPS":
        rng = np.random.default_rng(seed)
        shapes = (
            (1, 2, chi),
            *((chi, 2, chi),) * 7,
            (chi, 2, 1),
        )
        cores = []
        for left, physical, right in shapes:
            scale = 0.35 / np.sqrt(max(left, right))
            cores.append(rng.normal(0.0, scale, size=(left, physical, right)))
        model = cls(chi, cores, symmetrize=symmetrize)
        model.left_canonicalize()
        return model

    @property
    def parameter_count(self) -> int:
        return sum(int(core.size) for core in self.cores)

    @property
    def parameter_norm(self) -> float:
        return float(np.sqrt(sum(np.sum(core * core) for core in self.cores)))

    def copy(self) -> "PatchMPS":
        return PatchMPS(self.chi, self.cores, symmetrize=self.symmetrize)

    @staticmethod
    def _validate_patches(patches: np.ndarray) -> np.ndarray:
        values = np.asarray(patches, dtype=np.int8)
        if values.ndim == 1:
            values = values.reshape(1, -1)
        if values.ndim != 2 or values.shape[1] != 9:
            raise ValueError("patches must have shape (samples, 9)")
        if not np.all((values == -1) | (values == 1)):
            raise ValueError("patch spins must be -1 or +1")
        return values

    def raw_values(self, patches: np.ndarray) -> np.ndarray:
        values = self._validate_patches(patches)
        physical = ((values + 1) // 2).astype(np.int8)
        state = np.ones((values.shape[0], 1), dtype=np.float64)
        for site, core in enumerate(self.cores):
            matrices = np.transpose(core[:, physical[:, site], :], (1, 0, 2))
            state = np.einsum("bi,bij->bj", state, matrices, optimize=True)
        result = state[:, 0]
        if not np.all(np.isfinite(result)):
            raise FloatingPointError("MPS contraction produced NaN or Inf")
        return result

    def raw_value(self, patch: np.ndarray) -> float:
        return float(self.raw_values(np.asarray(patch))[0])

    def symmetric_values(
        self,
        patches: np.ndarray,
        symmetrize: bool | None = None,
    ) -> np.ndarray:
        values = self._validate_patches(patches)
        enabled = self.symmetrize if symmetrize is None else bool(symmetrize)
        if not enabled:
            return self.raw_values(values)
        result = np.zeros(values.shape[0], dtype=np.float64)
        for transform_index in range(8):
            transformed = transform_patches(values, transform_index)
            result += self.raw_values(transformed)
            result += self.raw_values(-transformed)
        return result / 16.0

    def symmetric_value(self, patch: np.ndarray) -> float:
        return float(self.symmetric_values(np.asarray(patch))[0])

    def _raw_gradient(self, patches: np.ndarray, weights: np.ndarray) -> MPSGradient:
        values = self._validate_patches(patches)
        supplied_weights = np.asarray(weights, dtype=np.float64)
        if supplied_weights.shape != (values.shape[0],):
            raise ValueError("weights must have one value per patch")
        physical = ((values + 1) // 2).astype(np.int8)
        matrices = [
            np.transpose(core[:, physical[:, site], :], (1, 0, 2))
            for site, core in enumerate(self.cores)
        ]
        forward = [np.ones((values.shape[0], 1), dtype=np.float64)]
        for matrix in matrices:
            forward.append(np.einsum("bi,bij->bj", forward[-1], matrix, optimize=True))
        backward: list[np.ndarray] = [np.empty((0, 0)) for _ in range(self.sites + 1)]
        backward[-1] = np.ones((values.shape[0], 1), dtype=np.float64)
        for site in range(self.sites - 1, -1, -1):
            backward[site] = np.einsum(
                "bij,bj->bi", matrices[site], backward[site + 1], optimize=True
            )
        gradients = []
        for site, core in enumerate(self.cores):
            gradient = np.zeros_like(core)
            for physical_index in (0, 1):
                mask = physical[:, site] == physical_index
                if np.any(mask):
                    gradient[:, physical_index, :] = np.einsum(
                        "bi,bj,b->ij",
                        forward[site][mask],
                        backward[site + 1][mask],
                        supplied_weights[mask],
                        optimize=True,
                    )
            gradients.append(gradient)
        return MPSGradient(tuple(gradients))

    def gradient(
        self,
        patches: np.ndarray,
        weights: np.ndarray | None = None,
        symmetrize: bool | None = None,
    ) -> MPSGradient:
        values = self._validate_patches(patches)
        supplied_weights = (
            np.ones(values.shape[0], dtype=np.float64)
            if weights is None
            else np.asarray(weights, dtype=np.float64)
        )
        enabled = self.symmetrize if symmetrize is None else bool(symmetrize)
        if not enabled:
            return self._raw_gradient(values, supplied_weights)
        total = tuple(np.zeros_like(core) for core in self.cores)
        scaled_weights = supplied_weights / 16.0
        for transform_index in range(8):
            transformed = transform_patches(values, transform_index)
            for signed in (transformed, -transformed):
                contribution = self._raw_gradient(signed, scaled_weights)
                for accumulator, derivative in zip(total, contribution.cores):
                    accumulator += derivative
        return MPSGradient(total)

    def left_canonicalize(self) -> None:
        """Fix a deterministic left gauge while retaining declared chi-shaped cores."""
        for site in range(self.sites - 1):
            core = self.cores[site]
            rows = core.shape[0] * 2
            columns = core.shape[2]
            matrix = core.reshape(rows, columns)
            orthogonal, transfer_reduced = np.linalg.qr(matrix, mode="reduced")
            rank = orthogonal.shape[1]
            diagonal = np.diag(transfer_reduced[:, :rank])
            signs = np.where(diagonal < 0.0, -1.0, 1.0)
            orthogonal *= signs.reshape(1, -1)
            transfer_reduced *= signs.reshape(-1, 1)
            padded = np.zeros_like(matrix)
            padded[:, :rank] = orthogonal
            transfer = np.zeros((columns, columns), dtype=np.float64)
            transfer[:rank, :] = transfer_reduced
            core[:] = padded.reshape(core.shape)
            self.cores[site + 1][:] = np.einsum(
                "ab,bpc->apc", transfer, self.cores[site + 1], optimize=True
            )
        if not all(np.all(np.isfinite(core)) for core in self.cores):
            raise FloatingPointError("MPS canonicalization produced NaN or Inf")

    def diagnostics(self) -> dict[str, float | int]:
        from .patch_table import enumerate_patches

        outputs = self.symmetric_values(enumerate_patches())
        return {
            "chi": self.chi,
            "parameter_count": self.parameter_count,
            "parameter_norm": self.parameter_norm,
            "output_min": float(outputs.min()),
            "output_max": float(outputs.max()),
            "output_mean": float(outputs.mean()),
        }

    def save(self, path: str | Path) -> None:
        payload: dict[str, np.ndarray] = {
            "schema_version": np.asarray(1, dtype=np.int64),
            "chi": np.asarray(self.chi, dtype=np.int64),
            "symmetrize": np.asarray(int(self.symmetrize), dtype=np.int8),
        }
        for index, core in enumerate(self.cores):
            payload[f"core_{index}"] = core
        np.savez_compressed(path, **payload)

    @classmethod
    def load(cls, path: str | Path) -> "PatchMPS":
        with np.load(path, allow_pickle=False) as data:
            if int(data["schema_version"]) != 1:
                raise ValueError("unsupported PatchMPS schema")
            chi = int(data["chi"])
            symmetrize = bool(int(data["symmetrize"]))
            cores = tuple(data[f"core_{index}"].copy() for index in range(9))
        return cls(chi, cores, symmetrize=symmetrize)
