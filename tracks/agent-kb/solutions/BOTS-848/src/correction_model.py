"""Channel-wise static correction for a DFPT perturbation operator."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from numbers import Number

from .channel_decomposition import CHANNELS, decompose_operator


def correct_operator(
    dfpt_operator: Sequence[Sequence[Number]],
    site_blocks: Sequence[Sequence[int]],
    kernels: Mapping[str, Number],
) -> list[list[complex]]:
    """Scale each operator channel and reconstruct the corrected perturbation.

    This minimum model uses one scalar kernel per channel. It does not fit or
    infer those kernels; they must come from a source-traceable comparison or a
    higher-level many-body calculation.
    """

    if set(kernels) != set(CHANNELS):
        raise ValueError(f"kernels must contain exactly {', '.join(CHANNELS)}")
    try:
        numeric_kernels = {name: complex(kernels[name]) for name in CHANNELS}
    except (TypeError, ValueError) as exc:
        raise ValueError("kernels must be numeric") from exc

    channels = decompose_operator(dfpt_operator, site_blocks)
    size = len(channels["charge"])
    return [
        [
            sum(
                numeric_kernels[name] * channels[name][row][column]
                for name in CHANNELS
            )
            for column in range(size)
        ]
        for row in range(size)
    ]
