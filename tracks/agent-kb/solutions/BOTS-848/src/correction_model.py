"""Channel-wise static correction for a DFPT perturbation operator."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from numbers import Number, Real

from .channel_decomposition import CHANNELS, decompose_operator


def correct_operator(
    dfpt_operator: Sequence[Sequence[Number]],
    site_blocks: Sequence[Sequence[int]],
    kernels: Mapping[str, Number],
) -> list[list[complex]]:
    """Scale each operator channel and reconstruct the corrected perturbation.

    This minimum model uses one finite real scalar kernel per channel, so a
    Hermitian input remains Hermitian. It does not fit or
    infer those kernels; they must come from a source-traceable comparison or a
    higher-level many-body calculation.
    """

    if set(kernels) != set(CHANNELS):
        raise ValueError(f"kernels must contain exactly {', '.join(CHANNELS)}")
    numeric_kernels = {}
    for name in CHANNELS:
        value = kernels[name]
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError("kernels must be finite real scalars and not booleans")
        numeric_value = float(value)
        if not math.isfinite(numeric_value):
            raise ValueError("kernels must be finite real scalars and not booleans")
        numeric_kernels[name] = numeric_value

    channels = decompose_operator(dfpt_operator, site_blocks)
    size = len(channels["global_charge"])
    corrected = [
        [
            sum(
                numeric_kernels[name] * channels[name][row][column]
                for name in CHANNELS
            )
            for column in range(size)
        ]
        for row in range(size)
    ]
    if any(
        not math.isfinite(value.real) or not math.isfinite(value.imag)
        for row in corrected
        for value in row
    ):
        raise ValueError("corrected operator entries must remain finite")
    return corrected
