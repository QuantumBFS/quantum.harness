from pathlib import Path

import pytest

from ole_pepo.circuits import get_circuit_profile, load_circuit_protocol


OLE_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("name", "sha256", "byte_count", "layers", "cz_count"),
    [
        (
            "baseline",
            "1705197e7b1ebb02266600b3ddaba0d2c47a96de84c5895e2bb530728b815455",
            150686,
            73,
            648,
        ),
        (
            "active",
            "d237a273c7cc233e9d64039ad06613af17eb472b19bda12f4ce458b9c4541645",
            297926,
            145,
            1296,
        ),
    ],
)
def test_registered_circuit_loads_only_its_audited_protocol(
    name: str,
    sha256: str,
    byte_count: int,
    layers: int,
    cz_count: int,
):
    """Breaks if a profile accepts the wrong input identity or circuit structure."""
    profile = get_circuit_profile(name)
    protocol = load_circuit_protocol(profile, OLE_ROOT)

    assert profile.qasm_sha256 == sha256
    assert profile.qasm_bytes == byte_count
    assert profile.expected_layers == layers
    assert profile.expected_cz == cz_count
    assert protocol.register_size == 156
    assert len(protocol.active_sites) == 49
    assert len(protocol.layers) == layers
    assert protocol.barrier_count == layers
    assert sum(gate.name == "cz" for gate in protocol.gates) == cz_count
    assert sum(
        gate.name == "rz" and gate.angle == pytest.approx(0.3)
        for gate in protocol.gates
    ) == 24


def test_unknown_circuit_is_rejected_before_input_is_read():
    """Breaks if a typo silently falls back to the baseline circuit."""
    with pytest.raises(ValueError, match="unknown circuit"):
        get_circuit_profile("activ")
