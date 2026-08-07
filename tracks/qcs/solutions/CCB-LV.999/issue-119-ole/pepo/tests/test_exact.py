from pathlib import Path

import numpy as np
import pytest

from ole_pepo.exact import (
    dense_unitary,
    normalized_ole_dense,
    seven_site_oracle_protocol,
)
from ole_pepo.qasm import parse_qasm


IDENTITY_ECHO_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
rx(pi/2) q[0];
rx(-pi/2) q[0];
"""


@pytest.fixture
def full_protocol():
    root = Path(__file__).resolve().parents[2]
    return parse_qasm(
        (root / "inputs/49Q_OLE_circuit_L_3_b_0.25_delta0.15.qasm").read_text(
            encoding="utf-8"
        )
    )


def test_dense_single_qubit_rotation():
    """Breaks if dense evolution uses a nonstandard Rx sign or angle convention."""
    protocol = parse_qasm(
        """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
rx(pi/2) q[0];
"""
    )
    expected = (
        np.cos(np.pi / 4) * np.eye(2)
        - 1j * np.sin(np.pi / 4) * np.array([[0, 1], [1, 0]])
    )

    np.testing.assert_allclose(dense_unitary(protocol), expected, atol=1e-14)


def test_dense_non_nearest_labels_preserve_qasm_qubit_order():
    """Breaks if physical labels 7 and 52 are renumbered or their CZ order changes."""
    protocol = parse_qasm(
        """OPENQASM 2.0;
include "qelib1.inc";
qreg q[80];
rx(pi/2) q[7];
cz q[7],q[52];
"""
    )
    rx = np.array(
        [[np.cos(np.pi / 4), -1j * np.sin(np.pi / 4)],
         [-1j * np.sin(np.pi / 4), np.cos(np.pi / 4)]],
        dtype=np.complex128,
    )
    expected = np.diag([1, 1, 1, -1]) @ np.kron(rx, np.eye(2))

    np.testing.assert_allclose(dense_unitary(protocol), expected, atol=1e-14)


def test_dense_ole_identity_is_one():
    """Breaks if the normalized OLE trace is not normalized by the Hilbert dimension."""
    protocol = parse_qasm(IDENTITY_ECHO_QASM)

    value = normalized_ole_dense(protocol, (0,))

    assert value == pytest.approx(1.0, abs=1e-14)


def test_dense_ole_rx_pi_flips_the_z_echo():
    """Breaks if the Pauli observable or U†OU ordering is reversed."""
    protocol = parse_qasm(
        """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
rx(pi) q[0];
"""
    )

    assert normalized_ole_dense(protocol, (0,)) == pytest.approx(-1.0, abs=1e-14)


def test_dense_unitary_refuses_a_protocol_larger_than_the_oracle_limit():
    """Breaks if dense allocation proceeds after the explicit size guard."""
    protocol = parse_qasm(
        """OPENQASM 2.0;
include "qelib1.inc";
qreg q[13];
rx(0) q[0];
rx(0) q[1];
rx(0) q[2];
rx(0) q[3];
rx(0) q[4];
rx(0) q[5];
rx(0) q[6];
rx(0) q[7];
rx(0) q[8];
rx(0) q[9];
rx(0) q[10];
rx(0) q[11];
rx(0) q[12];
"""
    )

    with pytest.raises(ValueError, match="max_sites"):
        dense_unitary(protocol)


def test_seven_site_oracle_crop_has_the_audited_edges_and_perturbations(full_protocol):
    """Breaks if the oracle crop leaks gates or loses either endpoint perturbation."""
    cropped = seven_site_oracle_protocol(full_protocol)

    assert cropped.active_sites == (33, 39, 49, 50, 51, 52, 53)
    assert {
        tuple(sorted(gate.qubits))
        for gate in cropped.gates
        if gate.name == "cz"
    } == {
        (33, 39),
        (39, 53),
        (52, 53),
        (51, 52),
        (50, 51),
        (49, 50),
    }
    perturbations = [
        gate for gate in cropped.gates if gate.name == "rz" and gate.angle == pytest.approx(0.3)
    ]
    assert [gate.qubits for gate in perturbations] == [(33,), (49,)]


def test_seven_site_oracle_delta_zero_replaces_only_the_two_perturbations(full_protocol):
    """Breaks if delta-zero changes any gate other than the audited endpoint Rz terms."""
    original = seven_site_oracle_protocol(full_protocol)
    zeroed = seven_site_oracle_protocol(full_protocol, delta_zero=True)

    changed = [
        (before, after)
        for before, after in zip(original.gates, zeroed.gates, strict=True)
        if before != after
    ]
    assert [(before.qubits, before.angle, after.angle) for before, after in changed] == [
        ((33,), pytest.approx(0.3), 0.0),
        ((49,), pytest.approx(0.3), 0.0),
    ]
