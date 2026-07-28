import numpy as np
import pytest
import quimb.tensor as qtn

from ole_pepo.gates import (
    gate_matrix,
    interaction_edges,
    quimb_gates,
    to_quimb_gate,
)
from ole_pepo.qasm import OLEProtocol, QASMGate


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("s", np.diag([1.0, 1.0j])),
        ("sdg", np.diag([1.0, -1.0j])),
        (
            "sx",
            0.5 * np.array([[1 + 1j, 1 - 1j], [1 - 1j, 1 + 1j]]),
        ),
        (
            "sxdg",
            0.5 * np.array([[1 - 1j, 1 + 1j], [1 + 1j, 1 - 1j]]),
        ),
    ],
)
def test_fixed_gate_matrices(name: str, expected: np.ndarray):
    """Breaks if a fixed QASM gate uses a different phase convention."""
    gate = QASMGate(name, (7,), None, 0, 0)

    np.testing.assert_allclose(gate_matrix(gate), expected, atol=1e-15)


@pytest.mark.parametrize(
    ("gate", "expected"),
    [
        (
            QASMGate("rx", (4,), np.pi / 3, 0, 0),
            np.array(
                [
                    [np.cos(np.pi / 6), -1j * np.sin(np.pi / 6)],
                    [-1j * np.sin(np.pi / 6), np.cos(np.pi / 6)],
                ]
            ),
        ),
        (
            QASMGate("rz", (4,), np.pi / 3, 0, 0),
            np.diag([np.exp(-1j * np.pi / 6), np.exp(1j * np.pi / 6)]),
        ),
        (QASMGate("cz", (4, 12), None, 0, 0), np.diag([1, 1, 1, -1])),
    ],
)
def test_parameterized_and_two_qubit_gate_matrices(gate: QASMGate, expected: np.ndarray):
    """Breaks if Rx, Rz, or CZ no longer match their analytic operators."""
    np.testing.assert_allclose(gate_matrix(gate), expected, atol=1e-15)


@pytest.mark.parametrize(
    "gate",
    [
        QASMGate("rx", (1,), 0.417, 0, 0),
        QASMGate("rz", (1,), -0.917, 0, 0),
        QASMGate("s", (1,), None, 0, 0),
        QASMGate("sdg", (1,), None, 0, 0),
        QASMGate("sx", (1,), None, 0, 0),
        QASMGate("sxdg", (1,), None, 0, 0),
        QASMGate("cz", (1, 9), None, 0, 0),
    ],
)
def test_every_supported_gate_is_unitary(gate: QASMGate):
    """Breaks if a matrix ceases to represent a unitary evolution."""
    matrix = gate_matrix(gate)

    np.testing.assert_allclose(matrix.conj().T @ matrix, np.eye(matrix.shape[0]), atol=1e-15)


@pytest.mark.parametrize(
    "gate",
    [
        QASMGate("rx", (1,), None, 0, 0),
        QASMGate("rz", (1,), None, 0, 0),
        QASMGate("s", (1,), 0.1, 0, 0),
        QASMGate("cz", (1, 2), 0.1, 0, 0),
    ],
)
def test_gate_matrix_rejects_incompatible_angle_metadata(gate: QASMGate):
    """Breaks if malformed parser metadata silently changes gate meaning."""
    with pytest.raises(ValueError):
        gate_matrix(gate)


def test_gate_matrix_returns_an_independent_array():
    """Breaks if one caller can mutate a later caller's fixed gate matrix."""
    gate = QASMGate("s", (7,), None, 0, 0)
    first = gate_matrix(gate)
    first[0, 0] = 99.0

    np.testing.assert_allclose(gate_matrix(gate), np.diag([1.0, 1.0j]), atol=1e-15)


def _basis_state(bits: str) -> qtn.MatrixProductState:
    return qtn.MPS_computational_state(bits, dtype="complex128")


def _dense_column(state: qtn.MatrixProductState) -> np.ndarray:
    return np.asarray(state.to_dense()).reshape(-1)


def test_converted_cz_changes_only_the_11_computational_basis_column():
    """Breaks if conversion changes the CZ operator applied by quimb."""
    gate = to_quimb_gate(QASMGate("cz", (0, 1), None, 0, 0))

    actual_columns = np.column_stack(
        [_dense_column(_basis_state(bits).gate(gate.array, where=gate.qubits, contract=True)) for bits in ("00", "01", "10", "11")]
    )

    np.testing.assert_allclose(actual_columns, np.diag([1, 1, 1, -1]), atol=1e-15)


def test_quimb_first_qasm_label_is_the_first_matrix_index():
    """Characterizes the label-order convention used by the conversion boundary."""
    nonsymmetric = np.diag([1, 2, 3, 4]).astype(np.complex128)
    gate = qtn.Gate.from_raw(nonsymmetric, qubits=(1, 0))
    output = _dense_column(_basis_state("10").gate(gate.array, where=gate.qubits, contract=True))

    np.testing.assert_allclose(output, np.array([0, 0, 2, 0]), atol=1e-15)


def test_conversion_preserves_qasm_order_and_protocol_order():
    """Breaks if physical labels or temporal gate order changes at conversion."""
    first = QASMGate("cz", (12, 4), None, 0, 0)
    second = QASMGate("rx", (4,), 0.2, 1, 1)
    protocol = OLEProtocol(20, ((first,), (second,)), (4, 12), 1)

    assert to_quimb_gate(first).qubits == (12, 4)
    assert tuple(gate.qubits for gate in quimb_gates(protocol)) == ((12, 4), (4,))


def test_interaction_edges_are_unique_and_canonically_sorted():
    """Breaks if duplicate or reversed CZ records change the interaction graph."""
    protocol = OLEProtocol(
        20,
        ((QASMGate("cz", (9, 2), None, 0, 0), QASMGate("s", (2,), None, 0, 1)),
         (QASMGate("cz", (2, 9), None, 1, 2), QASMGate("cz", (7, 3), None, 1, 3))),
        (2, 3, 7, 9),
        1,
    )

    assert interaction_edges(protocol) == ((2, 9), (3, 7))
