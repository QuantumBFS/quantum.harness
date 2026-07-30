"""Canonical, backend-independent real parameter arrays."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
import re
from typing import Any, TypeAlias

import numpy as np


NamedArrayTree: TypeAlias = OrderedDict[str, np.ndarray]

_SEGMENT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\Z", re.ASCII)


def validate_array_path(path: Any) -> str:
    """Return a strict canonical ASCII slash path or raise."""

    if not isinstance(path, str):
        raise TypeError("array path keys must be strings")
    if not path or not path.isascii() or "\\" in path or "\x00" in path:
        raise ValueError("array path must be nonempty canonical ASCII")
    segments = path.split("/")
    if any(
        not segment
        or segment in {".", ".."}
        or _SEGMENT.fullmatch(segment) is None
        for segment in segments
    ):
        raise ValueError("array path contains an invalid segment")
    return path


def _validate_flax_segment(key: Any) -> str:
    if not isinstance(key, str):
        raise TypeError("Flax parameter mapping keys must be strings")
    if (
        not key
        or not key.isascii()
        or key in {".", ".."}
        or _SEGMENT.fullmatch(key) is None
    ):
        raise ValueError("Flax parameter mapping key is not a canonical path segment")
    return key


def immutable_float64_array(value: Any, *, path: str) -> np.ndarray:
    """Copy an exact float64 array into immutable canonical bytes."""

    if not isinstance(value, np.ndarray) and not (
        hasattr(value, "dtype")
        and hasattr(value, "shape")
        and hasattr(value, "__array__")
    ):
        raise TypeError(f"named array {path!r} must be an ndarray")
    array = np.asarray(value)
    if array.dtype.kind != "f" or array.dtype.itemsize != 8:
        raise ValueError(f"named array {path!r} must have exact real float64 dtype")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"named array {path!r} must contain only finite values")
    contiguous = np.array(array, dtype="<f8", order="C", copy=True)
    owned_bytes = contiguous.tobytes(order="C")
    canonical = np.frombuffer(owned_bytes, dtype="<f8").reshape(contiguous.shape)
    canonical.flags.writeable = False
    return canonical


def canonicalize_named_arrays(values: Mapping[str, Any]) -> NamedArrayTree:
    """Validate, sort, detach, and freeze a named array mapping."""

    if not isinstance(values, Mapping):
        raise TypeError("named arrays must be supplied as a mapping")
    checked: list[tuple[str, np.ndarray]] = []
    for path, value in values.items():
        checked_path = validate_array_path(path)
        checked.append(
            (checked_path, immutable_float64_array(value, path=checked_path))
        )
    checked.sort(key=lambda item: item[0])
    return OrderedDict(checked)


def flax_params_to_named(params: Mapping[str, Any]) -> NamedArrayTree:
    """Flatten a Flax parameter mapping without changing tensor axes."""

    if not isinstance(params, Mapping):
        raise TypeError("Flax parameters must be a mapping")
    leaves: dict[str, Any] = {}

    def visit(node: Any, prefix: str) -> None:
        if isinstance(node, Mapping):
            if prefix and not node:
                raise ValueError("Flax parameter mappings cannot contain empty nodes")
            for key, child in node.items():
                segment = _validate_flax_segment(key)
                path = f"{prefix}/{segment}" if prefix else segment
                visit(child, path)
            return
        if not prefix:
            raise ValueError("Flax parameter leaf has no path")
        if prefix in leaves:
            raise ValueError(f"Flax parameter canonical path collision at {prefix!r}")
        leaves[prefix] = node

    visit(params, "")
    return canonicalize_named_arrays(leaves)


def named_to_flax_params(values: NamedArrayTree):
    """Rebuild a frozen nested Flax mapping from canonical slash paths."""

    canonical = canonicalize_named_arrays(values)
    root: dict[str, Any] = {}
    for path, value in canonical.items():
        segments = path.split("/")
        node = root
        for segment in segments[:-1]:
            existing = node.get(segment)
            if existing is None:
                child: dict[str, Any] = {}
                node[segment] = child
                node = child
            elif isinstance(existing, dict):
                node = existing
            else:
                raise ValueError("named array path prefix collision")
        leaf = segments[-1]
        if leaf in node:
            raise ValueError("named array path collision")
        node[leaf] = value

    # Keep JAX/Flax optional for Torch-only processes that only use canonical arrays.
    import jax.numpy as jnp
    from flax.core import freeze

    return freeze(
        _map_leaves(root, lambda value: jnp.asarray(value, dtype=jnp.float64))
    )


def _map_leaves(node: Any, function):
    if isinstance(node, dict):
        return {key: _map_leaves(value, function) for key, value in node.items()}
    return function(node)
