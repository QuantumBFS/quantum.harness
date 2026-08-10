"""Hierarchical stream/block bootstrap for the candidate transition."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .anisotropy import calibrate_alpha, fit_spatial_dimension
from .casimir import fit_casimir
from .data_io import LoadedRun, LoadedStream
from .phase import TransitionBracket


@dataclass(frozen=True)
class CandidateDistribution:
    threshold_phi_pi: np.ndarray
    casimir_amplitude: np.ndarray
    alpha: np.ndarray
    central_charge: np.ndarray


@dataclass(frozen=True)
class BootstrapSummary:
    estimate: float | None
    interval: tuple[float, float] | None
    valid_replicates: int
    failure_fraction: float
    unavailable: bool


def summarize_bootstrap(samples: np.ndarray, requested: int) -> BootstrapSummary:
    values = np.asarray(samples, dtype=float)
    if values.ndim != 1 or requested <= 0 or len(values) != requested:
        raise ValueError("bootstrap summary requires one value per requested replicate")
    valid = values[np.isfinite(values)]
    failures = requested - len(valid)
    failure_fraction = failures / requested
    unavailable = failure_fraction > 0.05 or len(valid) == 0
    if unavailable:
        return BootstrapSummary(None, None, len(valid), failure_fraction, True)
    return BootstrapSummary(
        estimate=float(np.mean(valid)),
        interval=(
            float(np.quantile(valid, 0.025)),
            float(np.quantile(valid, 0.975)),
        ),
        valid_replicates=len(valid),
        failure_fraction=failure_fraction,
        unavailable=False,
    )


def hierarchical_bootstrap_means(
    groups: dict[int, tuple[np.ndarray, ...]], samples: int, seed: int
) -> np.ndarray:
    if samples <= 0 or not groups:
        raise ValueError("bootstrap requires positive samples and non-empty groups")
    ordered = sorted(groups)
    if any(not streams for streams in groups.values()):
        raise ValueError("every bootstrap group requires at least one stream")
    rng = np.random.default_rng(seed)
    result = np.empty((samples, len(ordered)))
    maximum_streams = max(len(groups[key]) for key in ordered)
    for replicate in range(samples):
        shared_uniform = rng.random(maximum_streams)
        for column, key in enumerate(ordered):
            streams = groups[key]
            selected_streams = (shared_uniform[: len(streams)] * len(streams)).astype(int)
            stream_means = []
            for selected in selected_streams:
                blocks = np.asarray(streams[selected], dtype=float)
                if blocks.ndim != 1 or len(blocks) == 0 or not np.all(np.isfinite(blocks)):
                    raise ValueError("bootstrap streams require finite complete blocks")
                indices = rng.integers(0, len(blocks), len(blocks))
                stream_means.append(float(blocks[indices].mean()))
            result[replicate, column] = np.mean(stream_means)
    return result


def bootstrap_candidate(
    loaded: LoadedRun,
    bracket: TransitionBracket,
    samples: int,
    seed: int,
) -> CandidateDistribution:
    midpoint = 0.5 * (bracket.lower_phi_pi + bracket.upper_phi_pi)
    candidate_streams = [
        stream
        for key, stream in loaded.streams.items()
        if "diii" in key[0] and math.isclose(key[2], midpoint, abs_tol=1e-12)
    ]
    if not candidate_streams:
        available = sorted(
            {
                key[2]
                for key in loaded.streams
                if "diii" in key[0]
                and bracket.lower_phi_pi <= key[2] <= bracket.upper_phi_pi
            }
        )
        if not available:
            raise ValueError("no DIII streams lie inside the candidate bracket")
        chosen = min(available, key=lambda value: abs(value - midpoint))
        candidate_streams = [
            stream
            for key, stream in loaded.streams.items()
            if "diii" in key[0] and key[2] == chosen
        ]
    by_width: dict[int, list[LoadedStream]] = {}
    for stream in candidate_streams:
        by_width.setdefault(stream.width, []).append(stream)
    widths = np.array(sorted(by_width), dtype=float)
    if len(widths) < 5:
        raise ValueError("candidate bootstrap requires at least five widths")

    rng = np.random.default_rng(seed)
    amplitudes = np.full(samples, np.nan)
    alphas = np.full(samples, np.nan)
    for replicate in range(samples):
        gamma = []
        correlations: dict[int, list[np.ndarray]] = {}
        lyapunov: dict[int, list[np.ndarray]] = {}
        for width in widths.astype(int):
            streams = by_width[width]
            selected = rng.integers(0, len(streams), len(streams))
            selected_blocks = []
            for stream_index in selected:
                stream = streams[stream_index]
                block_indices = rng.integers(0, len(stream.blocks), len(stream.blocks))
                selected_blocks.extend(stream.blocks[index] for index in block_indices)
            gamma.append(np.mean([block.gamma for block in selected_blocks]))
            correlations[width] = [
                np.array(
                    [
                        (point.distance, point.connected_parity)
                        for point in block.spatial_correlations
                    ]
                )
                for block in selected_blocks
            ]
            lyapunov[width] = [
                np.asarray(block.lyapunov) for block in selected_blocks
            ]
        try:
            casimir = fit_casimir(
                widths,
                np.asarray(gamma),
                np.eye(len(widths)) * 1e-8,
                float(widths.min()),
                "l3",
            )
            spatial = fit_spatial_dimension(
                correlations, tuple(widths.astype(int)), (1 / 8, 3 / 8)
            )
            alpha = calibrate_alpha(spatial, lyapunov, (None, None))
        except (ValueError, np.linalg.LinAlgError):
            continue
        amplitudes[replicate] = casimir.casimir_amplitude
        alphas[replicate] = alpha.alpha
    central = amplitudes / alphas
    threshold = np.full(samples, midpoint)
    return CandidateDistribution(
        threshold_phi_pi=_readonly(threshold),
        casimir_amplitude=_readonly(amplitudes),
        alpha=_readonly(alphas),
        central_charge=_readonly(central),
    )


def _readonly(values: np.ndarray) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    result.setflags(write=False)
    return result
