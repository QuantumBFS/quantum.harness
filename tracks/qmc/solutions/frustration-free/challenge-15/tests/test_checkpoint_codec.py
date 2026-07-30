from __future__ import annotations

import ast
from collections import OrderedDict
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from challenge15.checkpoint_codec import (
    CODEC,
    MAGIC,
    CodecLimits,
    NamedAdam,
    decode_adam,
    decode_parameters,
    encode_adam,
    encode_parameters,
)
from challenge15.named_arrays import canonicalize_named_arrays


def _parameter_bytes():
    return encode_parameters(
        {
            "z/kernel": np.asarray([[1.5]], dtype=">f8"),
            "a/bias": np.asarray([2.5, -3.0], dtype=np.float64),
        },
        backend_source="torch",
        model_config={"depth": 0, "enabled": True, "rank": 1},
    )


def _split(encoded: bytes):
    assert encoded.startswith(MAGIC)
    start = len(MAGIC)
    header_length = int.from_bytes(encoded[start : start + 8], "little")
    header_start = start + 8
    header_end = header_start + header_length
    return json.loads(encoded[header_start:header_end]), encoded[header_end:]


def _join(header, payload: bytes, *, canonical: bool = True) -> bytes:
    if canonical:
        header_bytes = json.dumps(
            header, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    else:
        header_bytes = json.dumps(header).encode("utf-8")
    return MAGIC + len(header_bytes).to_bytes(8, "little") + header_bytes + payload


def test_parameter_codec_is_deterministic_sorted_little_endian_and_exact():
    first = _parameter_bytes()
    second = encode_parameters(
        OrderedDict(
            (
                ("a/bias", np.asarray([2.5, -3.0], dtype="<f8")),
                ("z/kernel", np.asarray([[1.5]], dtype=np.float64)),
            )
        ),
        backend_source="torch",
        model_config={"rank": 1, "enabled": True, "depth": 0},
    )

    assert MAGIC == b"C15NQS1"
    assert first == second
    header, restored = decode_parameters(first)
    assert header.codec == CODEC == "challenge15-named-arrays-v1"
    assert header.kind == "parameters"
    assert header.step is None
    assert tuple(restored) == ("a/bias", "z/kernel")
    assert all(value.dtype == np.dtype("<f8") for value in restored.values())
    assert all(not value.flags.writeable for value in restored.values())
    np.testing.assert_array_equal(restored["z/kernel"], [[1.5]])

    raw_header, payload = _split(first)
    assert raw_header == {
        "arrays": [
            {
                "dtype": "<f8",
                "nbytes": 16,
                "offset": 0,
                "path": "a/bias",
                "sha256": hashlib.sha256(
                    np.asarray([2.5, -3.0], dtype="<f8").tobytes()
                ).hexdigest(),
                "shape": [2],
            },
            {
                "dtype": "<f8",
                "nbytes": 8,
                "offset": 16,
                "path": "z/kernel",
                "sha256": hashlib.sha256(
                    np.asarray([[1.5]], dtype="<f8").tobytes()
                ).hexdigest(),
                "shape": [1, 1],
            },
        ],
        "backend_source": "torch",
        "codec": CODEC,
        "kind": "parameters",
        "model_config": {"depth": 0, "enabled": True, "rank": 1},
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "step": None,
    }


def test_codec_copies_source_arrays_before_encoding_and_decoding():
    source = np.asarray([1.0, 2.0], dtype=np.float64)
    encoded = encode_parameters(
        {"layer/kernel": source}, backend_source="jax", model_config={}
    )
    source[:] = 99.0
    _, restored = decode_parameters(encoded)
    np.testing.assert_array_equal(restored["layer/kernel"], [1.0, 2.0])


def test_named_adam_round_trip_is_exact_and_uses_reserved_namespaces():
    first = canonicalize_named_arrays(
        {
            "dense/kernel": np.asarray([[0.25, -0.5]], dtype=np.float64),
            "dense/bias": np.asarray([0.125, 0.75], dtype=np.float64),
        }
    )
    second = canonicalize_named_arrays(
        {
            "dense/kernel": np.asarray([[1.25, 2.5]], dtype=np.float64),
            "dense/bias": np.asarray([3.0, 4.0], dtype=np.float64),
        }
    )
    state = NamedAdam(step=7, first_moment=first, second_moment=second)

    encoded = encode_adam(
        state, backend_source="torch", model_config={"rank": 1}
    )
    header, restored = decode_adam(encoded)

    assert header.kind == "adam"
    assert header.step == 7
    assert [item.path for item in header.arrays] == [
        "first_moment/dense/bias",
        "first_moment/dense/kernel",
        "second_moment/dense/bias",
        "second_moment/dense/kernel",
    ]
    assert restored.step == 7
    for path in first:
        assert restored.first_moment[path].tobytes() == first[path].tobytes()
        assert restored.second_moment[path].tobytes() == second[path].tobytes()


@pytest.mark.parametrize("step", (-1, True, 1.0, "1"))
def test_named_adam_rejects_invalid_step_types(step):
    values = canonicalize_named_arrays(
        {"a": np.asarray([1.0], dtype=np.float64)}
    )
    with pytest.raises((TypeError, ValueError), match="step"):
        NamedAdam(step=step, first_moment=values, second_moment=values)


def test_named_adam_rejects_mismatched_paths_or_shapes():
    first = canonicalize_named_arrays(
        {"a": np.asarray([1.0], dtype=np.float64)}
    )
    other_path = canonicalize_named_arrays(
        {"b": np.asarray([1.0], dtype=np.float64)}
    )
    other_shape = canonicalize_named_arrays(
        {"a": np.asarray([[1.0]], dtype=np.float64)}
    )
    with pytest.raises(ValueError, match="paths"):
        NamedAdam(0, first, other_path)
    with pytest.raises(ValueError, match="shapes"):
        NamedAdam(0, first, other_shape)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("codec", 1),
        ("backend_source", True),
        ("model_config", []),
        ("kind", 1),
        ("step", False),
        ("arrays", {}),
        ("payload_sha256", 1),
    ),
)
def test_decoder_rejects_wrong_exact_header_field_types(field, value):
    header, payload = _split(_parameter_bytes())
    header[field] = value
    with pytest.raises(ValueError, match=field):
        decode_parameters(_join(header, payload))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("path", 1),
        ("shape", {}),
        ("dtype", True),
        ("offset", False),
        ("nbytes", 8.0),
        ("sha256", 1),
    ),
)
def test_decoder_rejects_wrong_exact_array_header_types(field, value):
    header, payload = _split(_parameter_bytes())
    header["arrays"][0][field] = value
    with pytest.raises(ValueError, match=field):
        decode_parameters(_join(header, payload))


def test_decoder_rejects_unknown_missing_duplicate_and_noncanonical_json_fields():
    header, payload = _split(_parameter_bytes())

    unknown = dict(header, surprise=None)
    with pytest.raises(ValueError, match="fields"):
        decode_parameters(_join(unknown, payload))

    missing = dict(header)
    del missing["kind"]
    with pytest.raises(ValueError, match="fields"):
        decode_parameters(_join(missing, payload))

    canonical = json.dumps(
        header, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
    duplicate = canonical[:-1] + ',"kind":"parameters"}'
    encoded = (
        MAGIC
        + len(duplicate.encode()).to_bytes(8, "little")
        + duplicate.encode()
        + payload
    )
    with pytest.raises(ValueError, match="duplicate"):
        decode_parameters(encoded)

    with pytest.raises(ValueError, match="canonical"):
        decode_parameters(_join(header, payload, canonical=False))


@pytest.mark.parametrize("path", ("../a", "a/../b", "a//b", "café/kernel"))
def test_decoder_rejects_traversal_empty_or_unicode_paths(path):
    header, payload = _split(_parameter_bytes())
    header["arrays"][0]["path"] = path
    with pytest.raises(ValueError, match="path"):
        decode_parameters(_join(header, payload))


def test_decoder_rejects_duplicate_paths_even_with_distinct_offsets():
    header, payload = _split(_parameter_bytes())
    header["arrays"][1]["path"] = header["arrays"][0]["path"]
    with pytest.raises(ValueError, match="duplicate|sorted"):
        decode_parameters(_join(header, payload))


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("truncate_prefix", "truncated"),
        ("truncate_header", "truncated"),
        ("truncate_payload", "length|truncated"),
        ("extra", "extra|length"),
        ("payload_digest", "payload SHA256"),
        ("array_digest", "array SHA256"),
        ("payload_corruption", "SHA256"),
    ),
)
def test_codec_rejects_truncation_extra_bytes_and_digest_corruption(
    mutation, message
):
    encoded = _parameter_bytes()
    header, payload = _split(encoded)
    if mutation == "truncate_prefix":
        damaged = encoded[:5]
    elif mutation == "truncate_header":
        damaged = encoded[: len(MAGIC) + 9]
    elif mutation == "truncate_payload":
        damaged = encoded[:-1]
    elif mutation == "extra":
        damaged = encoded + b"x"
    elif mutation == "payload_digest":
        header["payload_sha256"] = "0" * 64
        damaged = _join(header, payload)
    elif mutation == "array_digest":
        header["arrays"][0]["sha256"] = "0" * 64
        damaged = _join(header, payload)
    else:
        corrupted = bytearray(payload)
        corrupted[0] ^= 1
        damaged = _join(header, bytes(corrupted))
    with pytest.raises(ValueError, match=message):
        decode_parameters(damaged)


@pytest.mark.parametrize(
    ("change", "message"),
    (
        ({"offset": 1}, "gap|offset"),
        ({"nbytes": 8}, "nbytes|shape"),
        ({"dtype": ">f8"}, "dtype"),
        ({"shape": [2, True]}, "shape"),
        ({"shape": [-1]}, "dimension|shape"),
    ),
)
def test_decoder_rejects_invalid_layout_and_shape_fields(change, message):
    header, payload = _split(_parameter_bytes())
    header["arrays"][0].update(change)
    with pytest.raises(ValueError, match=message):
        decode_parameters(_join(header, payload))


def test_decoder_rejects_overlap_and_offset_arithmetic_overflow():
    header, payload = _split(_parameter_bytes())
    header["arrays"][1]["offset"] = 8
    with pytest.raises(ValueError, match="overlap|offset"):
        decode_parameters(_join(header, payload))

    header, payload = _split(_parameter_bytes())
    header["arrays"][0]["offset"] = (1 << 64) - 4
    with pytest.raises(ValueError, match="offset|overflow"):
        decode_parameters(_join(header, payload))


def test_decoder_rejects_huge_claimed_shapes_before_allocation():
    header, payload = _split(_parameter_bytes())
    header["arrays"][0]["shape"] = [1 << 62, 1 << 62]
    header["arrays"][0]["nbytes"] = 0
    with pytest.raises(ValueError, match="dimension|payload|overflow"):
        decode_parameters(_join(header, payload))


def test_decoder_enforces_each_explicit_resource_limit():
    encoded = _parameter_bytes()
    default = CodecLimits()
    cases = (
        (CodecLimits(max_header_bytes=1), "header"),
        (CodecLimits(max_arrays=1), "array"),
        (CodecLimits(max_rank=1), "rank"),
        (CodecLimits(max_dimension=1), "dimension"),
        (CodecLimits(max_payload_bytes=1), "payload"),
    )
    for limits, message in cases:
        with pytest.raises(ValueError, match=message):
            decode_parameters(encoded, limits=limits)
    decode_parameters(encoded, limits=default)


@pytest.mark.parametrize("limits", (None, {}, True))
def test_decoder_requires_codec_limits_object(limits):
    with pytest.raises(TypeError, match="CodecLimits"):
        decode_parameters(_parameter_bytes(), limits=limits)


def test_encoder_rejects_non_json_or_ambiguous_model_configuration():
    for config in (
        {"rank": np.int64(1)},
        {"value": np.nan},
        {1: "bad key"},
        {"café": 1},
        {"nested": {"cafe\u0301": 1}},
    ):
        with pytest.raises((TypeError, ValueError), match="model_config|JSON|Unicode"):
            encode_parameters(
                {"a": np.asarray([1.0], dtype=np.float64)},
                backend_source="torch",
                model_config=config,
            )


def test_encoder_rejects_ambiguous_backend_source_and_nonfinite_arrays():
    with pytest.raises(ValueError, match="backend_source"):
        encode_parameters(
            {"a": np.asarray([1.0], dtype=np.float64)},
            backend_source="café",
            model_config={},
        )
    with pytest.raises(ValueError, match="finite"):
        encode_parameters(
            {"a": np.asarray([np.inf], dtype=np.float64)},
            backend_source="torch",
            model_config={},
        )


def test_decoder_rejects_nonfinite_payload_even_with_matching_digests():
    header, payload = _split(_parameter_bytes())
    damaged = np.asarray([np.nan, -3.0], dtype="<f8").tobytes() + payload[16:]
    header["arrays"][0]["sha256"] = hashlib.sha256(damaged[:16]).hexdigest()
    header["payload_sha256"] = hashlib.sha256(damaged).hexdigest()
    with pytest.raises(ValueError, match="finite"):
        decode_parameters(_join(header, damaged))


def test_decoder_rejects_wrong_kind_and_direct_flax_or_pickle_bytes():
    encoded = _parameter_bytes()
    with pytest.raises(ValueError, match="kind"):
        decode_adam(encoded)
    for hostile in (b"\x80\x04pickle", b"\xde\x00\x01flax"):
        with pytest.raises(ValueError, match="magic|truncated"):
            decode_parameters(hostile)


def test_codec_module_has_no_executable_deserialization_or_framework_imports():
    spec = importlib.util.find_spec("challenge15.checkpoint_codec")
    assert spec is not None and spec.origin is not None
    tree = ast.parse(Path(spec.origin).read_text(encoding="utf-8"))
    forbidden = {"pickle", "torch", "jax", "flax", "optax"}
    imported = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert imported.isdisjoint(forbidden)
    assert "eval" not in {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
