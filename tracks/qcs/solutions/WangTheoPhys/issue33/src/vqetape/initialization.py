"""Deterministic parameter initialization and VQE recycling."""

from __future__ import annotations

from typing import Any

import numpy as np

from vqetape.spec import TFIMVQESpec
from vqetape.training_spec import VQETrainingRequest


def _real_dtype(spec: TFIMVQESpec):
    return (
        np.float32
        if spec.dtype == "complex64"
        else np.float64
    )


def _force_padding_zero(parameters: np.ndarray) -> np.ndarray:
    result = np.array(parameters, copy=True)
    result[:, 0, -1] = 0
    return result


def recycle_parameters(
    source_parameters: np.ndarray,
    source_spec: TFIMVQESpec,
    target_spec: TFIMVQESpec,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Map converged local patterns to a new chain/depth."""

    source = np.asarray(
        source_parameters,
        dtype=_real_dtype(target_spec),
    )
    if tuple(source.shape) != source_spec.parameter_shape:
        raise ValueError(
            "source parameter shape does not match source spec"
        )
    if not np.all(np.isfinite(source)):
        raise ValueError("source parameters must be finite")

    target = np.zeros(
        target_spec.parameter_shape,
        dtype=_real_dtype(target_spec),
    )
    for target_layer in range(target_spec.depth):
        source_layer = min(
            target_layer,
            source_spec.depth - 1,
        )
        source_rzz = source[
            source_layer,
            0,
            : source_spec.nqubits - 1,
        ]
        source_rx = source[source_layer, 1, :]
        rzz_mean = float(np.mean(source_rzz))
        rx_mean = float(np.mean(source_rx))

        for site in range(target_spec.nqubits - 1):
            target[target_layer, 0, site] = (
                source_rzz[site]
                if site < source_rzz.size
                else rzz_mean
            )
        for site in range(target_spec.nqubits):
            target[target_layer, 1, site] = (
                source_rx[site]
                if site < source_rx.size
                else rx_mean
            )
    target = _force_padding_zero(target)
    provenance = {
        "policy": "translation-mean-recycle",
        "source_spec": source_spec.to_dict(),
        "target_spec": target_spec.to_dict(),
        "source_shape": list(source_spec.parameter_shape),
        "target_shape": list(target_spec.parameter_shape),
        "new_site_fill": "source-layer-active-mean",
        "new_layer_fill": "last-source-layer",
        "padding_forced_zero": True,
    }
    return target, provenance


def initialize_parameters(
    request: VQETrainingRequest,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Construct the exact serialized initialization for a run."""

    dtype = _real_dtype(request.spec)
    if request.initialization == "zeros":
        parameters = np.zeros(
            request.spec.parameter_shape,
            dtype=dtype,
        )
        return parameters, {
            "policy": "zeros",
            "seed": None,
            "padding_forced_zero": True,
        }
    if request.initialization == "random":
        rng = np.random.default_rng(request.seed)
        parameters = rng.normal(
            loc=0.0,
            scale=0.1,
            size=request.spec.parameter_shape,
        ).astype(dtype)
        parameters = _force_padding_zero(parameters)
        return parameters, {
            "policy": "normal",
            "mean": 0.0,
            "scale": 0.1,
            "seed": request.seed,
            "padding_forced_zero": True,
        }

    assert request.recycled_source_spec is not None
    assert request.recycled_parameters is not None
    parameters, provenance = recycle_parameters(
        np.asarray(
            request.recycled_parameters,
            dtype=dtype,
        ),
        request.recycled_source_spec,
        request.spec,
    )
    return parameters, provenance
