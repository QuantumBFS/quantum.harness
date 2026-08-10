from __future__ import annotations

from collections import OrderedDict

import jax
import jax.numpy as jnp
import numpy as np
import pytest
from flax import serialization
from flax.core import freeze

from challenge15.named_arrays import (
    canonicalize_named_arrays,
    flax_params_to_named,
    named_to_flax_params,
)


jax.config.update("jax_enable_x64", True)


def test_canonical_named_arrays_are_sorted_little_endian_and_immutable():
    source = np.asarray([[1.5, -2.0]], dtype=">f8")
    values = canonicalize_named_arrays(
        {"z/kernel": source, "a/bias": np.asarray([3.0], dtype=np.float64)}
    )

    assert isinstance(values, OrderedDict)
    assert tuple(values) == ("a/bias", "z/kernel")
    assert all(value.dtype == np.dtype("<f8") for value in values.values())
    assert all(value.flags.c_contiguous for value in values.values())
    assert all(not value.flags.writeable for value in values.values())
    assert values["z/kernel"].tobytes() == np.asarray([[1.5, -2.0]], dtype="<f8").tobytes()


def test_canonical_named_arrays_do_not_alias_mutable_sources():
    source = np.asarray([1.0, 2.0], dtype=np.float64)
    restored = canonicalize_named_arrays({"layer/kernel": source})
    source[:] = 99.0

    np.testing.assert_array_equal(restored["layer/kernel"], [1.0, 2.0])
    with pytest.raises(ValueError, match="read-only"):
        restored["layer/kernel"][0] = 4.0


@pytest.mark.parametrize(
    "path",
    (
        "",
        "/a",
        "a/",
        "a//b",
        ".",
        "..",
        "a/.",
        "a/..",
        "../a",
        "a\\b",
        "a b",
        "café/kernel",
        "cafe\u0301/kernel",
        "a\x00b",
    ),
)
def test_named_arrays_reject_invalid_or_ambiguous_paths(path):
    with pytest.raises(ValueError, match="path"):
        canonicalize_named_arrays({path: np.asarray([1.0], dtype=np.float64)})


@pytest.mark.parametrize(
    "value",
    (
        np.asarray([1], dtype=np.int64),
        np.asarray([True], dtype=np.bool_),
        np.asarray([1.0], dtype=np.float32),
        np.asarray([1.0 + 0.0j], dtype=np.complex128),
        [1.0],
    ),
)
def test_named_arrays_reject_non_float64_ndarrays(value):
    with pytest.raises((TypeError, ValueError), match="float64|ndarray"):
        canonicalize_named_arrays({"a": value})


@pytest.mark.parametrize("value", (np.nan, np.inf, -np.inf))
def test_named_arrays_reject_nonfinite_values(value):
    with pytest.raises(ValueError, match="finite"):
        canonicalize_named_arrays({"a": np.asarray([value], dtype=np.float64)})


def test_named_arrays_require_a_mapping_and_string_keys():
    with pytest.raises(TypeError, match="mapping"):
        canonicalize_named_arrays([("a", np.asarray([1.0], dtype=np.float64))])
    with pytest.raises(TypeError, match="string"):
        canonicalize_named_arrays({1: np.asarray([1.0], dtype=np.float64)})


def test_flax_mapping_round_trip_preserves_paths_values_and_serialized_bytes():
    params = freeze(
        {
            "carrier_tokens": jnp.asarray([[1.0, 2.0]], dtype=jnp.float64),
            "shared_input": {
                "kernel": jnp.asarray([[3.0, 4.0], [5.0, 6.0]], dtype=jnp.float64),
                "bias": jnp.asarray([7.0, 8.0], dtype=jnp.float64),
            },
        }
    )
    before = serialization.to_bytes(params)

    named = flax_params_to_named(params)
    restored = named_to_flax_params(named)

    assert tuple(named) == (
        "carrier_tokens",
        "shared_input/bias",
        "shared_input/kernel",
    )
    np.testing.assert_array_equal(
        restored["shared_input"]["kernel"], params["shared_input"]["kernel"]
    )
    assert serialization.to_bytes(params) == before
    round_tripped = flax_params_to_named(restored)
    assert tuple(round_tripped) == tuple(named)
    assert all(
        round_tripped[path].tobytes() == named[path].tobytes() for path in named
    )


def test_flax_conversion_does_not_alias_numpy_sources_or_transpose_kernels():
    kernel = np.arange(6, dtype=np.float64).reshape(2, 3)
    params = {"dense": {"kernel": kernel}}
    named = flax_params_to_named(params)
    kernel[:] = -1.0

    assert named["dense/kernel"].shape == (2, 3)
    np.testing.assert_array_equal(
        named["dense/kernel"], np.arange(6, dtype=np.float64).reshape(2, 3)
    )
    np.testing.assert_array_equal(
        named_to_flax_params(named)["dense"]["kernel"],
        np.arange(6, dtype=np.float64).reshape(2, 3),
    )


def test_flax_conversion_rejects_invalid_source_segments_and_collisions():
    first = np.asarray([1.0], dtype=np.float64)
    second = np.asarray([2.0], dtype=np.float64)

    with pytest.raises(TypeError, match="mapping"):
        flax_params_to_named(first)
    with pytest.raises(ValueError, match="segment"):
        flax_params_to_named({"a/b": first})
    with pytest.raises(ValueError, match="segment|collision"):
        flax_params_to_named({"a/b": first, "a": {"b": second}})

    class RepeatingItems(dict):
        def items(self):
            return (("a", first), ("a", second))

    with pytest.raises(ValueError, match="collision"):
        flax_params_to_named(RepeatingItems(a=first))

    with pytest.raises(ValueError, match="collision"):
        named_to_flax_params(
            OrderedDict(
                (
                    ("a", first),
                    ("a/b", second),
                )
            )
        )
