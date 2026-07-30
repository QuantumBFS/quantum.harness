import hashlib
import json
import re
from pathlib import Path

import pytest

from scalable_v1.protocol import load_protocol


PROTOCOL_PATH = Path(__file__).parents[1] / "scalable_v1" / "protocol.json"


def test_protocol_freezes_physics_and_budget() -> None:
    p = load_protocol()
    assert p.schema_version == "challenge-15-scalable-v1.0"
    assert p.physics["n_electrons"] == 6
    assert p.physics["two_q"] == 15
    assert p.training["seeds"] == [848, 1848, 2848]
    assert p.training["optimizer_updates"] == 2048
    assert p.training["local_energy_evaluations_per_sector"] == (
        p.training["optimizer_updates"] * p.training["batch_size_per_sector"]
    )
    assert p.sampling["samples_per_chain"] % p.sampling["block_size"] == 0
    assert p.oracle["human_blind"] is False
    assert p.sha256 == load_protocol().sha256


def test_protocol_freezes_route_capacity_and_n8_smoke() -> None:
    p = load_protocol()
    assert p.capacity["max_trainable_parameters"] == 262_144
    assert set(p.capacity["routes"]) == {
        "occupation_autoregressive", "continuous_holomorphic", "cf_operator_nqs"
    }
    assert p.smoke_n8["n_electrons"] == 8
    assert p.smoke_n8["two_q"] == 21
    assert p.smoke_n8["batch_size"] == 256


def test_route_c_uses_strict_lll_operator_capacity() -> None:
    protocol = load_protocol()

    assert protocol.capacity["routes"]["cf_operator_nqs"] == {
        "operator_layers": 1,
        "density_ranks": [2, 3, 4],
        "hidden_width": 64,
    }
    assert "cf_flow_l2" not in protocol.capacity["routes"]


def test_protocol_internal_snapshot_is_deeply_immutable() -> None:
    p = load_protocol()
    mutable = []

    try:
        p._data["physics"] = {}
    except TypeError:
        pass
    else:
        mutable.append("internal mapping")

    try:
        p._data["training"]["seeds"][0] = 0
    except TypeError:
        pass
    else:
        mutable.append("nested sequence")

    assert mutable == []


def test_protocol_sha256_uses_exact_committed_bytes() -> None:
    expected = hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest()
    assert load_protocol().sha256 == expected


def test_nested_public_section_mutation_does_not_change_snapshot() -> None:
    p = load_protocol()
    training = p.training
    capacity = p.capacity

    training["seeds"][0] = 0
    capacity["routes"]["occupation_autoregressive"]["hidden_width"] = 0

    assert p.training["seeds"] == [848, 1848, 2848]
    assert p.capacity["routes"]["occupation_autoregressive"]["hidden_width"] == 128


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("schema", "invalid scalable-v1 protocol"),
        ("missing", "invalid scalable-v1 protocol; missing=physics"),
        ("n6_flux", "two_q must equal 3*(N-1)"),
        ("budget", "inconsistent local-energy budget"),
        ("seeds", "three unique comparison seeds are required"),
        ("blocks", "block_size must divide samples_per_chain"),
        ("human_blind", "human_blind must remain false"),
        ("n8_flux", "invalid N=8 smoke flux"),
        ("route_c_capacity", "invalid Route C capacity"),
    ],
)
def test_protocol_rejects_invalid_contract_values(
    tmp_path: Path, case: str, expected: str
) -> None:
    data = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    if case == "schema":
        data["schema_version"] = "wrong"
    elif case == "missing":
        data.pop("physics")
    elif case == "n6_flux":
        data["physics"]["two_q"] = 14
    elif case == "budget":
        data["training"]["local_energy_evaluations_per_sector"] = 0
    elif case == "seeds":
        data["training"]["seeds"] = [848, 848, 2848]
    elif case == "blocks":
        data["sampling"]["samples_per_chain"] = 8193
    elif case == "human_blind":
        data["oracle"]["human_blind"] = True
    elif case == "n8_flux":
        data["smoke_n8"]["two_q"] = 20
    elif case == "route_c_capacity":
        data["capacity"]["routes"]["cf_operator_nqs"]["operator_layers"] = 3
    else:
        raise AssertionError(f"unknown test case: {case}")

    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match=f"^{re.escape(expected)}$"):
        load_protocol(protocol_path)
