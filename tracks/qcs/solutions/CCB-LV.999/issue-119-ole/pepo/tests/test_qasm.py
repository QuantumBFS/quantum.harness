import hashlib
from pathlib import Path

import numpy as np
import pytest

from ole_pepo.qasm import (
    crop_protocol,
    parse_qasm,
    read_validated_qasm,
    replace_perturbations,
)


TINY_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[80];
rx(pi/2) q[52];
sx q[53];
cz q[52],q[53];
barrier q[52],q[53];
rz(0.3) q[33];
sdg q[52];
"""


@pytest.fixture
def ole_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_parse_qasm_preserves_layers_labels_and_angles():
    """Breaks if parsing loses the barrier-delimited gate sequence."""
    protocol = parse_qasm(TINY_QASM)

    assert protocol.register_size == 80
    assert protocol.barrier_count == 1
    assert protocol.active_sites == (33, 52, 53)
    assert [gate.name for gate in protocol.gates] == [
        "rx",
        "sx",
        "cz",
        "rz",
        "sdg",
    ]
    assert protocol.layers[0][0].angle == pytest.approx(np.pi / 2)
    assert protocol.layers[1][0].angle == pytest.approx(0.3)
    assert [(gate.layer_index, gate.gate_index) for gate in protocol.gates] == [
        (0, 0),
        (0, 1),
        (0, 2),
        (1, 3),
        (1, 4),
    ]


def test_parser_rejects_unknown_gate():
    """Breaks if an unsupported OpenQASM operation is silently accepted."""
    with pytest.raises(ValueError, match="unsupported OpenQASM"):
        parse_qasm(TINY_QASM.replace("sx q[53];", "h q[53];"))


def test_parser_supports_a_single_qubit_barrier():
    """Breaks if valid one-qubit layer boundaries cannot be parsed."""
    protocol = parse_qasm(TINY_QASM.replace("barrier q[52],q[53];", "barrier q[52];"))

    assert len(protocol.layers) == 2
    assert protocol.barrier_count == 1


@pytest.mark.parametrize(
    "changed",
    [
        pytest.param("rx(pi/2) q[80];", id="outside-register"),
        pytest.param("cz q[52],q[52];", id="repeated-cz-endpoint"),
        pytest.param("rx(sin(pi/2)) q[52];", id="nested-angle"),
        pytest.param("barrier q[80];", id="barrier-outside-register"),
    ],
)
def test_parser_rejects_outside_strict_subset(changed: str):
    """Breaks if malformed supported-gate syntax is accepted."""
    if changed.startswith("rx(sin"):
        text = TINY_QASM.replace("rx(pi/2) q[52];", changed)
    elif changed.startswith("rx(pi/2) q[80]"):
        text = TINY_QASM.replace("rx(pi/2) q[52];", changed)
    elif changed.startswith("cz"):
        text = TINY_QASM.replace("cz q[52],q[53];", changed)
    else:
        text = TINY_QASM.replace("barrier q[52],q[53];", changed)

    with pytest.raises(ValueError, match="unsupported OpenQASM"):
        parse_qasm(text)


def test_read_validated_qasm_rejects_changed_digest_and_length(tmp_path: Path):
    """Breaks if input identity validation no longer guards parser input."""
    qasm_path = tmp_path / "tiny.qasm"
    qasm_path.write_text(TINY_QASM, encoding="utf-8")
    digest = hashlib.sha256(TINY_QASM.encode("utf-8")).hexdigest()

    with pytest.raises(ValueError, match="SHA256"):
        read_validated_qasm(qasm_path, expected_sha256="0" * 64, expected_bytes=len(TINY_QASM))
    with pytest.raises(ValueError, match="byte length"):
        read_validated_qasm(qasm_path, expected_sha256=digest, expected_bytes=len(TINY_QASM) + 1)


def test_replace_perturbations_replaces_only_expected_rz_gates():
    """Breaks if perturbation replacement alters gate metadata or other gates."""
    source = parse_qasm(TINY_QASM)

    replaced = replace_perturbations(source, source_angle=0.3, expected_count=1)

    assert replaced is not source
    assert replaced.gates[:3] == source.gates[:3]
    assert replaced.gates[3].name == "rz"
    assert replaced.gates[3].angle == 0.0
    assert replaced.gates[3].qubits == source.gates[3].qubits
    assert replaced.gates[3].layer_index == source.gates[3].layer_index
    assert replaced.gates[3].gate_index == source.gates[3].gate_index
    assert source.gates[3].angle == pytest.approx(0.3)


def test_replace_perturbations_requires_exact_match_count():
    """Breaks if a missing perturbation can produce an unvalidated protocol."""
    with pytest.raises(ValueError, match="expected 2"):
        replace_perturbations(parse_qasm(TINY_QASM), source_angle=0.3, expected_count=2)


def test_crop_protocol_keeps_only_requested_gate_support_and_source_labels():
    """Breaks if cropping retains partial gates or renumbers source records."""
    source = parse_qasm(TINY_QASM)

    cropped = crop_protocol(source, sites=(7, 53))

    assert [gate.name for gate in cropped.gates] == ["sx"]
    assert cropped.active_sites == (53,)
    assert cropped.barrier_count == source.barrier_count
    assert [(gate.layer_index, gate.gate_index) for gate in cropped.gates] == [
        (0, 1),
    ]


def test_full_qasm_matches_audited_counts(ole_root: Path):
    protocol = read_validated_qasm(
        ole_root / "inputs/49Q_OLE_circuit_L_3_b_0.25_delta0.15.qasm",
        expected_sha256=(
            "1705197e7b1ebb02266600b3ddaba0d2c47a96de84c5895e2bb530728b815455"
        ),
        expected_bytes=150686,
    )
    assert len(protocol.active_sites) == 49
    assert len(protocol.layers) == 73
    assert protocol.barrier_count == 73
    assert sum(gate.name == "cz" for gate in protocol.gates) == 648
    assert sum(
        gate.name == "rz"
        and gate.angle is not None
        and np.isclose(gate.angle, 0.3, atol=8 * np.finfo(float).eps, rtol=0)
        for gate in protocol.gates
    ) == 24
    assert len(protocol.gates) == 4756
