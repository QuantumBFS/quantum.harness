"""Gauge-invariant finite-feature comparator for overlap-field VMCRG."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

import numpy as np

from .model import EABonds
from .templates import TemplateEncoder, TemplateKind


@dataclass(frozen=True)
class LinearFeature:
    name: str
    q_parity: int
    gauge_invariant: bool


class LinearFeatureBasis:
    def __init__(
        self,
        features: Sequence[LinearFeature],
        *,
        is_primary_comparator: bool,
    ) -> None:
        self.features = tuple(features)
        self.is_primary_comparator = bool(is_primary_comparator)

    @classmethod
    def cube_v1(cls) -> "LinearFeatureBasis":
        names_and_parity = (
            ("q_pair_nn", 2),
            ("q_pair_face", 2),
            ("q_plaquette", 4),
            ("flux_q_pair_nn", 2),
            ("flux_q_plaquette", 4),
        )
        return cls(
            [LinearFeature(name, parity, True) for name, parity in names_and_parity],
            is_primary_comparator=True,
        )

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(feature.name for feature in self.features)

    def q_only_ablation(self) -> "LinearFeatureBasis":
        return LinearFeatureBasis(
            self.features[:3],
            is_primary_comparator=False,
        )

    @staticmethod
    def _raw_cube_features(
        q_values: np.ndarray,
        disorder: np.ndarray,
    ) -> np.ndarray:
        nearest = np.asarray(
            [q_values[0] * q_values[index] for index in (1, 3, 7)],
            dtype=np.float64,
        )
        faces = np.asarray(
            [q_values[0] * q_values[index] for index in (2, 4, 6)],
            dtype=np.float64,
        )
        plaquettes = np.asarray(
            [
                q_values[0] * q_values[1] * q_values[2] * q_values[3],
                q_values[0] * q_values[1] * q_values[6] * q_values[7],
                q_values[0] * q_values[3] * q_values[4] * q_values[7],
            ],
            dtype=np.float64,
        )
        result = [
            float(np.mean(nearest)),
            float(np.mean(faces)),
            float(np.mean(plaquettes)),
        ]
        if disorder.size:
            result.extend(
                (
                    float(np.mean(nearest * disorder[:3])),
                    float(np.mean(plaquettes * disorder[2:5])),
                )
            )
        return np.asarray(result, dtype=np.float64)

    def local_features(
        self,
        tokens: np.ndarray,
        encoder: TemplateEncoder,
    ) -> np.ndarray:
        if encoder.kind is not TemplateKind.CUBE:
            raise ValueError("cube_v1 features require the cube template")
        if len(self.features) == 5 and not encoder.conditioned:
            raise ValueError("primary comparator requires conditioned tokens")
        images = encoder.symmetry_images(tokens)
        raw = []
        for image in images:
            q_values, disorder = encoder._unpack(image)
            raw.append(self._raw_cube_features(q_values, disorder))
        averaged = np.mean(np.asarray(raw), axis=0, dtype=np.float64)
        return averaged[: len(self.features)]

    def values(
        self,
        q: np.ndarray,
        bonds: EABonds,
        encoder: TemplateEncoder,
    ) -> np.ndarray:
        field = np.asarray(q)
        total = np.zeros(len(self.features), dtype=np.float64)
        for center in np.ndindex(field.shape):
            total += self.local_features(encoder.encode(field, bonds, center), encoder)
        return total

    def delta(
        self,
        q: np.ndarray,
        bonds: EABonds,
        encoder: TemplateEncoder,
        site: tuple[int, int, int],
    ) -> np.ndarray:
        field = np.asarray(q, dtype=np.int8)
        before = self.values(field, bonds, encoder)
        changed = field.copy()
        changed[site] *= -1
        return self.values(changed, bonds, encoder) - before
