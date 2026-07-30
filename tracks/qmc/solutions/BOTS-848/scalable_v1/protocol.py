from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


DEFAULT_PROTOCOL_PATH = Path(__file__).with_name("protocol.json")
SECTIONS = (
    "physics",
    "training",
    "sampling",
    "symmetry",
    "oracle",
    "capacity",
    "resources",
    "smoke_n8",
)


@dataclass(frozen=True)
class ProtocolConfig:
    schema_version: str
    sha256: str
    _data: Mapping[str, Any]

    def section(self, name: str) -> Mapping[str, Any]:
        return MappingProxyType(_thaw(self._data[name]))

    @property
    def physics(self) -> Mapping[str, Any]:
        return self.section("physics")

    @property
    def training(self) -> Mapping[str, Any]:
        return self.section("training")

    @property
    def sampling(self) -> Mapping[str, Any]:
        return self.section("sampling")

    @property
    def symmetry(self) -> Mapping[str, Any]:
        return self.section("symmetry")

    @property
    def oracle(self) -> Mapping[str, Any]:
        return self.section("oracle")

    @property
    def capacity(self) -> Mapping[str, Any]:
        return self.section("capacity")

    @property
    def resources(self) -> Mapping[str, Any]:
        return self.section("resources")

    @property
    def smoke_n8(self) -> Mapping[str, Any]:
        return self.section("smoke_n8")


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return copy.deepcopy(value)


def _validate(data: Mapping[str, Any]) -> None:
    missing = [name for name in SECTIONS if name not in data]
    if data.get("schema_version") != "challenge-15-scalable-v1.0" or missing:
        message = "invalid scalable-v1 protocol"
        if missing:
            message += f"; missing={','.join(missing)}"
        raise ValueError(message)

    physics = data["physics"]
    if physics["two_q"] != 3 * (physics["n_electrons"] - 1):
        raise ValueError("two_q must equal 3*(N-1)")

    training = data["training"]
    if training["local_energy_evaluations_per_sector"] != (
        training["optimizer_updates"] * training["batch_size_per_sector"]
    ):
        raise ValueError("inconsistent local-energy budget")
    seeds = training["seeds"]
    if len(seeds) != 3 or len(set(seeds)) != 3:
        raise ValueError("three unique comparison seeds are required")

    sampling = data["sampling"]
    if sampling["samples_per_chain"] % sampling["block_size"] != 0:
        raise ValueError("block_size must divide samples_per_chain")

    if data["oracle"]["human_blind"] is not False:
        raise ValueError("human_blind must remain false")

    route_c = data["capacity"]["routes"].get("cf_operator_nqs")
    expected_route_c = {
        "operator_layers": 1,
        "density_ranks": [2, 3, 4],
        "hidden_width": 64,
    }
    if route_c != expected_route_c:
        raise ValueError("invalid Route C capacity")

    smoke_n8 = data["smoke_n8"]
    if smoke_n8["n_electrons"] != 8 or smoke_n8["two_q"] != 3 * (
        smoke_n8["n_electrons"] - 1
    ):
        raise ValueError("invalid N=8 smoke flux")


def load_protocol(path: Path = DEFAULT_PROTOCOL_PATH) -> ProtocolConfig:
    raw = Path(path).read_bytes()
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("invalid scalable-v1 protocol")
    _validate(data)
    return ProtocolConfig(
        schema_version=data["schema_version"],
        sha256=hashlib.sha256(raw).hexdigest(),
        _data=_freeze(data),
    )
