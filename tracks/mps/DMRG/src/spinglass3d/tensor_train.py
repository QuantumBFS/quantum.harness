"""Trainable variable-length local Matrix-Product-State/Tensor-Train model."""

from __future__ import annotations

from dataclasses import dataclass
import math
from collections.abc import Mapping, Sequence

import numpy as np

from .templates import TemplateEncoder


@dataclass(frozen=True)
class TTGradient:
    cores: tuple[np.ndarray, ...]

    def __post_init__(self) -> None:
        if not self.cores:
            raise ValueError("gradient must contain at least one core")
        owned: list[np.ndarray] = []
        for core in self.cores:
            array = np.asarray(core, dtype=np.float64)
            if array.ndim != 3 or not np.all(np.isfinite(array)):
                raise ValueError("gradient cores must be finite rank-three arrays")
            copy = array.copy()
            copy.setflags(write=False)
            owned.append(copy)
        object.__setattr__(self, "cores", tuple(owned))

    def norm(self) -> float:
        squared = sum(
            float(np.vdot(core, core).real) for core in self.cores
        )
        return math.sqrt(squared)

    def scale(self, factor: float) -> "TTGradient":
        value = float(factor)
        if not math.isfinite(value):
            raise ValueError("gradient scale must be finite")
        return TTGradient(tuple(value * core for core in self.cores))

    def add(self, other: "TTGradient") -> "TTGradient":
        if not isinstance(other, TTGradient) or len(other.cores) != len(self.cores):
            raise ValueError("gradient structures must match")
        if any(left.shape != right.shape for left, right in zip(self.cores, other.cores, strict=True)):
            raise ValueError("gradient core shapes must match")
        return TTGradient(
            tuple(left + right for left, right in zip(self.cores, other.cores, strict=True))
        )


class LocalTensorTrain:
    """Open-boundary binary Tensor Train used as one shared local density."""

    def __init__(self, cores: Sequence[np.ndarray]) -> None:
        arrays = [np.asarray(core, dtype=np.float64).copy() for core in cores]
        if len(arrays) < 2:
            raise ValueError("Tensor Train needs at least two token cores")
        for index, core in enumerate(arrays):
            if core.ndim != 3 or core.shape[1] != 2:
                raise ValueError("each TT core must have shape (left,2,right)")
            if not np.all(np.isfinite(core)):
                raise ValueError("TT cores must be finite")
            if index and arrays[index - 1].shape[2] != core.shape[0]:
                raise ValueError("neighboring TT bond dimensions must match")
        if arrays[0].shape[0] != 1 or arrays[-1].shape[2] != 1:
            raise ValueError("TT boundary bond dimensions must equal one")
        self.cores = arrays

    @classmethod
    def random(cls, token_count: int, chi: int, seed: int) -> "LocalTensorTrain":
        if isinstance(token_count, bool) or not isinstance(token_count, (int, np.integer)) or int(token_count) < 2:
            raise ValueError("token_count must be an integer at least two")
        if isinstance(chi, bool) or not isinstance(chi, (int, np.integer)) or int(chi) < 1:
            raise ValueError("chi must be a positive integer")
        token_count, chi = int(token_count), int(chi)
        rng = np.random.default_rng(seed)
        scale = 1.0 / math.sqrt(max(1, chi))
        shapes = [(1, 2, chi)]
        shapes.extend((chi, 2, chi) for _ in range(token_count - 2))
        shapes.append((chi, 2, 1))
        return cls([rng.normal(scale=scale, size=shape) for shape in shapes])

    @property
    def token_count(self) -> int:
        return len(self.cores)

    @property
    def chi(self) -> int:
        return max(max(core.shape[0], core.shape[2]) for core in self.cores)

    @property
    def parameter_count(self) -> int:
        return sum(int(core.size) for core in self.cores)

    @property
    def parameter_norm(self) -> float:
        return math.sqrt(
            sum(float(np.vdot(core, core).real) for core in self.cores)
        )

    def _validated_tokens(self, tokens: np.ndarray) -> np.ndarray:
        values = np.asarray(tokens)
        if values.shape != (self.token_count,):
            raise ValueError(f"token sequence must have shape ({self.token_count},)")
        if not np.all((values == -1) | (values == 1)):
            raise ValueError("tokens must contain only -1 and +1")
        return values.astype(np.int8, copy=False)

    def value(self, tokens: np.ndarray) -> float:
        values = self._validated_tokens(tokens)
        state = np.ones(1, dtype=np.float64)
        for core, token in zip(self.cores, values, strict=True):
            state = state @ core[:, 0 if token == -1 else 1, :]
        result = float(state[0])
        if not math.isfinite(result):
            raise FloatingPointError("TT contraction is not finite")
        return result

    def values(self, tokens: np.ndarray) -> np.ndarray:
        batch = np.asarray(tokens)
        if batch.ndim == 1:
            return np.asarray([self.value(batch)], dtype=np.float64)
        if batch.ndim != 2 or batch.shape[1] != self.token_count:
            raise ValueError("token batch has the wrong shape")
        return np.asarray([self.value(row) for row in batch], dtype=np.float64)

    def gradient(self, tokens: np.ndarray, weights: np.ndarray) -> TTGradient:
        batch = np.asarray(tokens)
        if batch.ndim == 1:
            batch = batch[None, :]
        if batch.ndim != 2 or batch.shape[1] != self.token_count:
            raise ValueError("token batch has the wrong shape")
        coefficients = np.asarray(weights, dtype=np.float64)
        if coefficients.shape != (batch.shape[0],) or not np.all(np.isfinite(coefficients)):
            raise ValueError("weights must be one finite value per token row")
        result = [np.zeros_like(core) for core in self.cores]
        for row, weight in zip(batch, coefficients, strict=True):
            values = self._validated_tokens(row)
            left: list[np.ndarray] = [np.ones(1, dtype=np.float64)]
            for core, token in zip(self.cores, values, strict=True):
                left.append(left[-1] @ core[:, 0 if token == -1 else 1, :])
            right: list[np.ndarray] = [np.empty(0)] * (self.token_count + 1)
            right[-1] = np.ones(1, dtype=np.float64)
            for index in range(self.token_count - 1, -1, -1):
                physical = 0 if values[index] == -1 else 1
                right[index] = self.cores[index][:, physical, :] @ right[index + 1]
            for index, token in enumerate(values):
                physical = 0 if token == -1 else 1
                result[index][:, physical, :] += weight * np.outer(
                    left[index], right[index + 1]
                )
        if not all(np.all(np.isfinite(core)) for core in result):
            raise FloatingPointError("TT gradient is not finite")
        return TTGradient(tuple(result))

    def left_canonicalize(self) -> "LocalTensorTrain":
        cores = [core.copy() for core in self.cores]
        for index in range(len(cores) - 1):
            left, physical, right = cores[index].shape
            matrix = cores[index].reshape(left * physical, right)
            q_factor, r_factor = np.linalg.qr(matrix, mode="reduced")
            rank = q_factor.shape[1]
            diagonal = np.diag(r_factor[:, :rank])
            signs = np.where(diagonal < 0.0, -1.0, 1.0)
            q_factor = q_factor * signs[None, :]
            r_factor = signs[:, None] * r_factor
            padded_q = np.zeros_like(matrix)
            padded_q[:, :rank] = q_factor
            padded_r = np.zeros((right, right), dtype=np.float64)
            padded_r[:rank, :] = r_factor
            cores[index] = padded_q.reshape(left, physical, right)
            cores[index + 1] = np.tensordot(
                padded_r,
                cores[index + 1],
                axes=(1, 0),
            )
        return LocalTensorTrain(cores)

    def copy(self) -> "LocalTensorTrain":
        return LocalTensorTrain(self.cores)

    def save_arrays(self) -> tuple[np.ndarray, ...]:
        return tuple(core.copy() for core in self.cores)

    @classmethod
    def from_arrays(
        cls,
        arrays: Sequence[np.ndarray] | Mapping[str, np.ndarray],
    ) -> "LocalTensorTrain":
        if isinstance(arrays, Mapping):
            ordered = [arrays[key] for key in sorted(arrays)]
        else:
            ordered = list(arrays)
        return cls(ordered)


class SymmetricLocalTT:
    """Exact O_h x Z2 group average of one local Tensor Train."""

    def __init__(
        self,
        model: LocalTensorTrain,
        encoder: TemplateEncoder,
        mode: str = "group_average",
    ) -> None:
        if not isinstance(model, LocalTensorTrain) or not isinstance(encoder, TemplateEncoder):
            raise TypeError("model and encoder have incompatible types")
        if model.token_count != encoder.token_count:
            raise ValueError("model token count must match encoder")
        if mode != "group_average":
            raise ValueError("only exact group_average mode is implemented")
        self.model = model
        self.encoder = encoder
        self.mode = mode

    def value(self, tokens: np.ndarray) -> float:
        total = 0.0
        for transformed in self.encoder.symmetry_images(tokens):
            total += self.model.value(transformed)
            total += self.model.value(self.encoder.flip_q_tokens(transformed))
        result = total / (2.0 * self.encoder.cubic_group_size)
        if not math.isfinite(result):
            raise FloatingPointError("symmetric TT value is not finite")
        return result

    def values(self, tokens: np.ndarray) -> np.ndarray:
        batch = np.asarray(tokens)
        if batch.ndim == 1:
            return np.asarray([self.value(batch)], dtype=np.float64)
        return np.asarray([self.value(row) for row in batch], dtype=np.float64)

    def _uniform_q_value(self, tokens: np.ndarray) -> float:
        q_positions = set(self.encoder.q_token_indices)
        state = np.ones(1, dtype=np.float64)
        for position, core in enumerate(self.model.cores):
            if position in q_positions:
                matrix = 0.5 * (core[:, 0, :] + core[:, 1, :])
            else:
                token = int(tokens[position])
                matrix = core[:, 0 if token == -1 else 1, :]
            state = state @ matrix
        return float(state[0])

    def uniform_target_mean(self, tokens: np.ndarray) -> float:
        images = self.encoder.symmetry_images(tokens)
        result = float(
            np.mean([self._uniform_q_value(image) for image in images], dtype=np.float64)
        )
        if not math.isfinite(result):
            raise FloatingPointError("uniform target mean is not finite")
        return result

    def centered_value(self, tokens: np.ndarray) -> float:
        return self.value(tokens) - self.uniform_target_mean(tokens)

    def gradient(self, tokens: np.ndarray, weights: np.ndarray) -> TTGradient:
        batch = np.asarray(tokens)
        if batch.ndim == 1:
            batch = batch[None, :]
        coefficients = np.asarray(weights, dtype=np.float64)
        if coefficients.shape != (batch.shape[0],):
            raise ValueError("weights must match the symmetric token batch")
        expanded: list[np.ndarray] = []
        expanded_weights: list[float] = []
        divisor = 2.0 * self.encoder.cubic_group_size
        for row, weight in zip(batch, coefficients, strict=True):
            for image in self.encoder.symmetry_images(row):
                expanded.append(image)
                expanded.append(self.encoder.flip_q_tokens(image))
                expanded_weights.extend((weight / divisor, weight / divisor))
        return self.model.gradient(
            np.asarray(expanded, dtype=np.int8),
            np.asarray(expanded_weights, dtype=np.float64),
        )
