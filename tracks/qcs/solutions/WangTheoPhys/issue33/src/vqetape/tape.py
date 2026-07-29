"""Reverse-mode residual inspection for VQE programs."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from math import prod
from typing import Any, Callable

import numpy as np
import jax
import jax.numpy as jnp
from jax._src.ad_checkpoint import saved_residuals
from jax.ad_checkpoint import checkpoint_name


_NAMED_PATTERN = re.compile(r"^named '([^']+)'")
_JITTED_PATTERN = re.compile(r"^output of jitted function '([^']+)'")
_OUTPUT_PATTERN = re.compile(r"^output of ([^ ]+)")


def name_residual(value: jax.Array, name: str) -> jax.Array:
    """Attach a checkpoint-policy name, splitting complex values safely."""

    if jnp.issubdtype(value.dtype, jnp.complexfloating):
        real = checkpoint_name(jnp.real(value), f"{name}:real")
        imag = checkpoint_name(jnp.imag(value), f"{name}:imag")
        return jax.lax.complex(real, imag)
    return checkpoint_name(value, name)


@dataclass(frozen=True)
class ResidualRecord:
    """One value retained by JAX's reverse-mode transformation."""

    shape: tuple[int, ...]
    dtype: str
    bytes: int
    source: str
    category: str
    name: str | None
    recomputable: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResidualProfile:
    """Structured summary of the residuals saved for one differentiated call."""

    records: tuple[ResidualRecord, ...]

    @property
    def total_bytes(self) -> int:
        return sum(record.bytes for record in self.records)

    @property
    def recomputable_bytes(self) -> int:
        return sum(
            record.bytes for record in self.records if record.recomputable
        )

    def bytes_by_category(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for record in self.records:
            totals[record.category] = (
                totals.get(record.category, 0) + record.bytes
            )
        return dict(
            sorted(totals.items(), key=lambda item: (-item[1], item[0]))
        )

    def bytes_by_name(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for record in self.records:
            if record.name is None:
                continue
            totals[record.name] = totals.get(record.name, 0) + record.bytes
        return dict(
            sorted(totals.items(), key=lambda item: (-item[1], item[0]))
        )

    def to_dict(self, *, include_records: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "residual_count": len(self.records),
            "total_bytes": self.total_bytes,
            "recomputable_bytes": self.recomputable_bytes,
            "bytes_by_category": self.bytes_by_category(),
            "bytes_by_name": self.bytes_by_name(),
        }
        if include_records:
            payload["records"] = [
                record.to_dict() for record in self.records
            ]
        return payload


def _classify_source(source: str) -> tuple[str, str | None, bool]:
    named = _NAMED_PATTERN.match(source)
    if named is not None:
        return "named", named.group(1), True
    jitted = _JITTED_PATTERN.match(source)
    if jitted is not None:
        return f"jitted:{jitted.group(1)}", None, True
    output = _OUTPUT_PATTERN.match(source)
    if output is not None:
        primitive = output.group(1)
        return f"primitive:{primitive}", None, True
    if source.startswith("from the argument"):
        return "argument", None, False
    if source == "from a constant":
        return "constant", None, False
    if source == "from a literal":
        return "literal", None, False
    return "other", None, False


def profile_saved_residuals(
    function: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> ResidualProfile:
    """Trace a function's VJP and return byte-accounted saved residuals.

    JAX currently exposes a public printer but not a structured residual API.
    VQETape therefore consumes the corresponding internal structured helper in
    one compatibility boundary, isolated in this module.
    """

    records: list[ResidualRecord] = []
    for abstract_value, source in saved_residuals(function, *args, **kwargs):
        shape = tuple(int(extent) for extent in abstract_value.shape)
        byte_count = prod(shape) * np.dtype(abstract_value.dtype).itemsize
        category, name, recomputable = _classify_source(source)
        records.append(
            ResidualRecord(
                shape=shape,
                dtype=str(np.dtype(abstract_value.dtype)),
                bytes=int(byte_count),
                source=source,
                category=category,
                name=name,
                recomputable=recomputable,
            )
        )
    return ResidualProfile(tuple(records))
