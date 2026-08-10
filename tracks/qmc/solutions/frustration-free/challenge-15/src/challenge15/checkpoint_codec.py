"""Strict non-executable codec for canonical parameters and Adam moments."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Literal, TypeAlias

import numpy as np

from challenge15.named_arrays import (
    NamedArrayTree,
    canonicalize_named_arrays,
    validate_array_path,
)


MAGIC = b"C15NQS1"
CODEC = "challenge15-named-arrays-v1"
_U64_MAX = (1 << 64) - 1
_SHA256 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_BACKEND_SOURCE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\Z", re.ASCII)
_HEADER_FIELDS = {
    "codec",
    "backend_source",
    "model_config",
    "kind",
    "step",
    "arrays",
    "payload_sha256",
}
_ARRAY_FIELDS = {"path", "shape", "dtype", "offset", "nbytes", "sha256"}

JSONValue: TypeAlias = (
    None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
)


@dataclass(frozen=True, slots=True)
class CodecLimits:
    max_header_bytes: int = 1 << 20
    max_arrays: int = 4096
    max_rank: int = 16
    max_dimension: int = 10_000_000
    max_payload_bytes: int = 1 << 30

    def __post_init__(self) -> None:
        for name in (
            "max_header_bytes",
            "max_arrays",
            "max_rank",
            "max_dimension",
            "max_payload_bytes",
        ):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive Python integer")


DEFAULT_LIMITS = CodecLimits()


@dataclass(frozen=True, slots=True)
class ArrayHeader:
    path: str
    shape: tuple[int, ...]
    dtype: Literal["<f8"]
    offset: int
    nbytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class CodecHeader:
    codec: str
    backend_source: str
    model_config: Mapping[str, JSONValue]
    kind: Literal["parameters", "adam"]
    step: int | None
    arrays: tuple[ArrayHeader, ...]
    payload_sha256: str


@dataclass(frozen=True, slots=True)
class NamedAdam:
    step: int
    first_moment: NamedArrayTree
    second_moment: NamedArrayTree

    def __post_init__(self) -> None:
        if type(self.step) is not int or self.step < 0:
            raise ValueError("Adam step must be a nonnegative Python integer")
        first = canonicalize_named_arrays(self.first_moment)
        second = canonicalize_named_arrays(self.second_moment)
        if tuple(first) != tuple(second):
            raise ValueError("Adam moment paths must match exactly")
        if any(first[path].shape != second[path].shape for path in first):
            raise ValueError("Adam moment shapes must match exactly")
        object.__setattr__(self, "first_moment", first)
        object.__setattr__(self, "second_moment", second)


def encode_parameters(
    values: Mapping[str, Any],
    *,
    backend_source: str,
    model_config: Mapping[str, JSONValue],
) -> bytes:
    """Encode canonical parameters without executable serialization."""

    return _encode(
        canonicalize_named_arrays(values),
        backend_source=backend_source,
        model_config=model_config,
        kind="parameters",
        step=None,
    )


def decode_parameters(
    encoded: bytes, *, limits: CodecLimits = DEFAULT_LIMITS
) -> tuple[CodecHeader, NamedArrayTree]:
    """Decode parameters after complete bounded structural validation."""

    header, arrays = _decode(encoded, limits=limits, expected_kind="parameters")
    return header, arrays


def encode_adam(
    state: NamedAdam,
    *,
    backend_source: str,
    model_config: Mapping[str, JSONValue],
) -> bytes:
    """Encode named Adam moments in two explicit path namespaces."""

    if not isinstance(state, NamedAdam):
        raise TypeError("state must be a NamedAdam")
    namespaced = {
        **{
            f"first_moment/{path}": value
            for path, value in state.first_moment.items()
        },
        **{
            f"second_moment/{path}": value
            for path, value in state.second_moment.items()
        },
    }
    return _encode(
        canonicalize_named_arrays(namespaced),
        backend_source=backend_source,
        model_config=model_config,
        kind="adam",
        step=state.step,
    )


def decode_adam(
    encoded: bytes, *, limits: CodecLimits = DEFAULT_LIMITS
) -> tuple[CodecHeader, NamedAdam]:
    """Decode and separate strictly namespaced Adam moments."""

    header, arrays = _decode(encoded, limits=limits, expected_kind="adam")
    first: dict[str, np.ndarray] = {}
    second: dict[str, np.ndarray] = {}
    for path, value in arrays.items():
        if path.startswith("first_moment/"):
            target = first
            inner = path.removeprefix("first_moment/")
        elif path.startswith("second_moment/"):
            target = second
            inner = path.removeprefix("second_moment/")
        else:
            raise ValueError("Adam array path must use a moment namespace")
        validate_array_path(inner)
        target[inner] = value
    if header.step is None:
        raise ValueError("Adam header step is missing")
    return header, NamedAdam(header.step, OrderedDict(first), OrderedDict(second))


def _encode(
    values: NamedArrayTree,
    *,
    backend_source: str,
    model_config: Mapping[str, JSONValue],
    kind: Literal["parameters", "adam"],
    step: int | None,
) -> bytes:
    checked_backend = _validate_backend_source(backend_source)
    checked_config = _validate_model_config(model_config)
    payload_parts: list[bytes] = []
    arrays: list[dict[str, JSONValue]] = []
    offset = 0
    for path, value in values.items():
        raw = value.tobytes(order="C")
        payload_parts.append(raw)
        arrays.append(
            {
                "path": path,
                "shape": list(value.shape),
                "dtype": "<f8",
                "offset": offset,
                "nbytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        offset += len(raw)
    payload = b"".join(payload_parts)
    raw_header: dict[str, JSONValue] = {
        "codec": CODEC,
        "backend_source": checked_backend,
        "model_config": checked_config,
        "kind": kind,
        "step": step,
        "arrays": arrays,
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
    }
    header_bytes = _canonical_json_bytes(raw_header)
    if len(header_bytes) > DEFAULT_LIMITS.max_header_bytes:
        raise ValueError("encoded header exceeds the header resource limit")
    if len(values) > DEFAULT_LIMITS.max_arrays:
        raise ValueError("encoded array count exceeds the array resource limit")
    if len(payload) > DEFAULT_LIMITS.max_payload_bytes:
        raise ValueError("encoded payload exceeds the payload resource limit")
    for value in values.values():
        if value.ndim > DEFAULT_LIMITS.max_rank:
            raise ValueError("encoded array rank exceeds the rank resource limit")
        if any(size > DEFAULT_LIMITS.max_dimension for size in value.shape):
            raise ValueError("encoded array dimension exceeds the dimension resource limit")
    return (
        MAGIC
        + len(header_bytes).to_bytes(8, byteorder="little", signed=False)
        + header_bytes
        + payload
    )


def _decode(
    encoded: bytes,
    *,
    limits: CodecLimits,
    expected_kind: Literal["parameters", "adam"],
) -> tuple[CodecHeader, NamedArrayTree]:
    if not isinstance(limits, CodecLimits):
        raise TypeError("limits must be a CodecLimits")
    if not isinstance(encoded, bytes):
        raise TypeError("encoded checkpoint must be bytes")
    prefix_length = len(MAGIC) + 8
    if len(encoded) < prefix_length:
        raise ValueError("checkpoint is truncated before its header")
    if encoded[: len(MAGIC)] != MAGIC:
        raise ValueError("checkpoint magic is not C15NQS1")
    header_length = int.from_bytes(
        encoded[len(MAGIC) : prefix_length], byteorder="little", signed=False
    )
    if header_length > limits.max_header_bytes:
        raise ValueError("checkpoint header exceeds the header resource limit")
    header_end = prefix_length + header_length
    if header_end > len(encoded):
        raise ValueError("checkpoint is truncated inside its header")
    header_bytes = encoded[prefix_length:header_end]
    raw_header = _load_canonical_json(header_bytes)
    header = _validate_header(
        raw_header,
        limits=limits,
        expected_kind=expected_kind,
    )

    payload_length = len(encoded) - header_end
    if payload_length > limits.max_payload_bytes:
        raise ValueError("checkpoint payload exceeds the payload resource limit")
    expected_payload_length = 0
    previous_path: str | None = None
    for array in header.arrays:
        if previous_path is not None and array.path <= previous_path:
            if array.path == previous_path:
                raise ValueError("checkpoint contains a duplicate array path")
            raise ValueError("checkpoint array paths are not sorted")
        previous_path = array.path
        if array.offset > _U64_MAX - array.nbytes:
            raise ValueError("checkpoint array offset arithmetic overflow")
        if array.offset != expected_payload_length:
            relation = "overlap" if array.offset < expected_payload_length else "gap"
            raise ValueError(f"checkpoint array offsets contain a {relation}")
        expected_payload_length = array.offset + array.nbytes
        if expected_payload_length > limits.max_payload_bytes:
            raise ValueError("checkpoint payload exceeds the payload resource limit")
    if payload_length != expected_payload_length:
        raise ValueError("checkpoint payload length has truncation or extra bytes")

    payload = encoded[header_end:]
    if hashlib.sha256(payload).hexdigest() != header.payload_sha256:
        raise ValueError("checkpoint payload SHA256 mismatch")
    restored: NamedArrayTree = OrderedDict()
    for array in header.arrays:
        raw = payload[array.offset : array.offset + array.nbytes]
        if hashlib.sha256(raw).hexdigest() != array.sha256:
            raise ValueError(f"checkpoint array SHA256 mismatch for {array.path!r}")
        value = np.frombuffer(raw, dtype="<f8").reshape(array.shape)
        if not np.all(np.isfinite(value)):
            raise ValueError(f"checkpoint array {array.path!r} is not finite")
        value.flags.writeable = False
        restored[array.path] = value
    return header, restored


def _validate_header(
    value: JSONValue,
    *,
    limits: CodecLimits,
    expected_kind: Literal["parameters", "adam"],
) -> CodecHeader:
    if type(value) is not dict:
        raise ValueError("checkpoint header must be a JSON object")
    if set(value) != _HEADER_FIELDS:
        raise ValueError("checkpoint header fields are not exact")
    if type(value["codec"]) is not str or value["codec"] != CODEC:
        raise ValueError("checkpoint codec field is invalid")
    backend_source = _validate_backend_source(value["backend_source"])
    model_config = _validate_model_config(value["model_config"])
    if type(value["kind"]) is not str or value["kind"] != expected_kind:
        raise ValueError("checkpoint kind field is invalid")
    step = value["step"]
    if expected_kind == "parameters":
        if step is not None:
            raise ValueError("parameters step field must be null")
    elif type(step) is not int or step < 0:
        raise ValueError("Adam step field must be a nonnegative integer")
    if type(value["arrays"]) is not list:
        raise ValueError("checkpoint arrays field must be a JSON array")
    if len(value["arrays"]) > limits.max_arrays:
        raise ValueError("checkpoint array count exceeds the array resource limit")
    arrays = tuple(
        _validate_array_header(item, limits=limits) for item in value["arrays"]
    )
    payload_sha256 = _validate_digest(
        value["payload_sha256"], field="payload_sha256"
    )
    return CodecHeader(
        codec=CODEC,
        backend_source=backend_source,
        model_config=model_config,
        kind=expected_kind,
        step=step,
        arrays=arrays,
        payload_sha256=payload_sha256,
    )


def _validate_array_header(value: JSONValue, *, limits: CodecLimits) -> ArrayHeader:
    if type(value) is not dict:
        raise ValueError("each arrays entry must be a JSON object")
    if set(value) != _ARRAY_FIELDS:
        raise ValueError("array header fields are not exact")
    try:
        path = validate_array_path(value["path"])
    except (TypeError, ValueError) as error:
        raise ValueError(f"array path is invalid: {error}") from error
    if type(value["shape"]) is not list:
        raise ValueError("array shape field must be a JSON array")
    if len(value["shape"]) > limits.max_rank:
        raise ValueError("array rank exceeds the rank resource limit")
    shape: list[int] = []
    max_elements = limits.max_payload_bytes // 8
    elements = 1
    for dimension in value["shape"]:
        if type(dimension) is not int or dimension < 0:
            raise ValueError("array shape dimensions must be nonnegative integers")
        if dimension > limits.max_dimension:
            raise ValueError("array dimension exceeds the dimension resource limit")
        if dimension and elements > max_elements // dimension:
            raise ValueError("array shape product exceeds payload limits or overflows")
        elements *= dimension
        shape.append(dimension)
    if type(value["dtype"]) is not str or value["dtype"] != "<f8":
        raise ValueError("array dtype field must be exactly '<f8'")
    offset = _validate_u64(value["offset"], field="offset")
    nbytes = _validate_u64(value["nbytes"], field="nbytes")
    expected_nbytes = elements * 8
    if nbytes != expected_nbytes:
        raise ValueError("array nbytes does not match its shape and dtype")
    sha256 = _validate_digest(value["sha256"], field="sha256")
    return ArrayHeader(path, tuple(shape), "<f8", offset, nbytes, sha256)


def _validate_u64(value: JSONValue, *, field: str) -> int:
    if type(value) is not int or value < 0 or value > _U64_MAX:
        raise ValueError(f"array {field} must be an unsigned 64-bit integer")
    return value


def _validate_digest(value: JSONValue, *, field: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{field} must be a lowercase SHA256 hex string")
    return value


def _validate_backend_source(value: Any) -> str:
    if type(value) is not str or _BACKEND_SOURCE.fullmatch(value) is None:
        raise ValueError("backend_source must be nonempty canonical ASCII")
    return value


def _validate_model_config(value: Any) -> dict[str, JSONValue]:
    if type(value) is not dict and not isinstance(value, Mapping):
        raise ValueError("model_config must be a JSON object")
    checked = _validate_json_value(dict(value), path="model_config")
    if type(checked) is not dict:
        raise AssertionError("validated model_config is not an object")
    return checked


def _validate_json_value(value: Any, *, path: str) -> JSONValue:
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        return value
    if type(value) is float:
        if not np.isfinite(value):
            raise ValueError(f"{path} contains a nonfinite JSON number")
        return value
    if type(value) is str:
        if not value.isascii():
            raise ValueError(f"{path} contains Unicode ambiguity")
        return value
    if type(value) is list:
        return [
            _validate_json_value(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if type(value) is dict:
        checked: dict[str, JSONValue] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError(f"{path} JSON object keys must be strings")
            if not key.isascii():
                raise ValueError(f"{path} contains Unicode ambiguity")
            checked[key] = _validate_json_value(item, path=f"{path}.{key}")
        return checked
    raise TypeError(f"{path} contains a value outside the exact JSON domain")


def _canonical_json_bytes(value: JSONValue) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _load_canonical_json(encoded: bytes) -> JSONValue:
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError(f"nonfinite JSON constant {value!r}")

    try:
        text = encoded.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=object_pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("checkpoint header is not valid UTF-8 JSON") from error
    checked = _validate_json_value(value, path="header")
    if _canonical_json_bytes(checked) != encoded:
        raise ValueError("checkpoint header JSON is not canonical")
    return checked
