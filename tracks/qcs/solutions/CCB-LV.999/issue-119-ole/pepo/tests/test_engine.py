from dataclasses import FrozenInstanceError
from pathlib import Path

import numpy as np
import pytest
import quimb.tensor as qtn

from ole_pepo.contraction import normalized_overlap_exact
from ole_pepo.engine import (
    ProductObservablePEPO,
    ProgressRecord,
    build_pepo_circuit,
    reverse_lightcone_indices,
)
from ole_pepo.exact import normalized_ole_dense, seven_site_oracle_protocol
from ole_pepo.qasm import OLEProtocol, QASMGate, parse_qasm


I = np.eye(2, dtype=np.complex128)
X = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.complex128)
Z = np.diag([1.0, -1.0]).astype(np.complex128)
CZ = np.diag([1.0, 1.0, 1.0, -1.0]).astype(np.complex128)
FULL_QASM = (
    Path(__file__).resolve().parents[2]
    / "inputs/49Q_OLE_circuit_L_3_b_0.25_delta0.15.qasm"
)


def _three_site_gates() -> tuple[qtn.Gate, ...]:
    rx = np.cos(0.19) * I - 1j * np.sin(0.19) * X
    return (
        qtn.Gate.from_raw(rx, qubits=(2,)),
        qtn.Gate.from_raw(CZ, qubits=(1, 2)),
        qtn.Gate.from_raw(rx, qubits=(1,)),
        qtn.Gate.from_raw(CZ, qubits=(0, 1)),
        qtn.Gate.from_raw(rx, qubits=(0,)),
    )


def _dense_three_site(operator: qtn.TensorNetworkGenOperator) -> np.ndarray:
    return operator.to_dense(
        tuple(operator.upper_ind(i) for i in (0, 1, 2)),
        tuple(operator.lower_ind(i) for i in (0, 1, 2)),
    )


def test_one_site_product_matches_upstream_pepo_evolution():
    """Breaks if product evolution diverges from pinned upstream for one factor."""
    gates = _three_site_gates()
    options = {"edges": ((0, 1), (1, 2)), "cutoff": 0.0, "gate_opts": {"renorm": False}}
    upstream = qtn.CircuitPEPOSimpleUpdate(**options)
    upstream.apply_gates(gates)
    product = ProductObservablePEPO(**options)
    product.apply_gates(gates)

    product_result = product.evolve_product({0: Z})
    upstream_operator = upstream.get_evolved_operator(Z, 0)

    np.testing.assert_allclose(
        product_result.operator.to_dense(
            tuple(product_result.operator.upper_ind(i) for i in (0, 1, 2)),
            tuple(product_result.operator.lower_ind(i) for i in (0, 1, 2)),
        ),
        upstream_operator.to_dense(
            tuple(upstream_operator.upper_ind(i) for i in (0, 1, 2)),
            tuple(upstream_operator.lower_ind(i) for i in (0, 1, 2)),
        ),
        atol=1e-12,
    )


def test_no_gate_product_observable_keeps_all_physical_labels():
    """Breaks if an additional product factor is omitted or labels are renumbered."""
    circuit = ProductObservablePEPO(edges=((0, 1), (1, 2)))

    result = circuit.evolve_product({0: Z, 2: Z})

    np.testing.assert_allclose(
        _dense_three_site(result.operator),
        np.kron(np.kron(Z, I), Z),
        atol=1e-12,
    )
    assert result.diagnostics.final_support == (0, 2)


def test_reverse_lightcone_excludes_disjoint_gates_and_grows_through_selected_edges():
    """Breaks if a disjoint gate grows support or a connecting gate is skipped."""
    gates = (
        qtn.Gate.from_raw(CZ, qubits=(3, 4)),
        qtn.Gate.from_raw(CZ, qubits=(1, 2)),
        qtn.Gate.from_raw(X, qubits=(4,)),
        qtn.Gate.from_raw(CZ, qubits=(0, 1)),
    )

    assert reverse_lightcone_indices(gates, {0}) == (3, 1)


def test_progress_and_diagnostics_describe_real_causal_evolution():
    """Breaks if progress cadence or causal-gate diagnostics lose real evolution state."""
    circuit = ProductObservablePEPO(
        edges=((0, 1), (1, 2)),
        cutoff=0.0,
        gate_opts={"renorm": False},
    )
    circuit.apply_gates(_three_site_gates())
    records: list[ProgressRecord] = []

    result = circuit.evolve_product(
        {0: X},
        progress_every=2,
        progress_callback=records.append,
    )

    assert [record.processed_causal_gates for record in records] == [1, 2, 4, 5]
    assert all(record.total_causal_gates == 5 for record in records)
    assert all(record.elapsed_seconds >= 0.0 for record in records)
    assert result.diagnostics.total_recorded_gates == 5
    assert result.diagnostics.causal_gates == 5
    assert result.diagnostics.final_support == (0, 1, 2)
    assert result.diagnostics.max_realized_bond >= 1
    assert result.diagnostics.max_retained_tail_ratio is not None


def test_retained_tail_ratio_matches_dense_operator_schmidt_values():
    """Breaks if the diagnostic does not report the retained smallest/largest ratio."""
    seed = np.arange(1, 17).reshape(4, 4) + 1j * np.arange(17, 33).reshape(4, 4) ** 2
    unitary = np.linalg.qr(seed)[0]
    evolved_dense = unitary.conj().T @ np.kron(Z, I) @ unitary
    operator_schmidt = np.linalg.svd(
        evolved_dense.reshape(2, 2, 2, 2)
        .transpose(0, 2, 1, 3)
        .reshape(4, 4),
        compute_uv=False,
    )
    expected_ratio = operator_schmidt[-1] / operator_schmidt[0]
    circuit = ProductObservablePEPO(
        edges=((0, 1),),
        cutoff=0.0,
        gate_opts={"renorm": False},
    )
    circuit.apply_gates((qtn.Gate.from_raw(unitary, qubits=(0, 1)),))

    result = circuit.evolve_product({0: Z})

    assert result.diagnostics.max_retained_tail_ratio == pytest.approx(
        expected_ratio,
        abs=1e-14,
    )


def test_evolve_product_refuses_an_empty_observable():
    """Breaks if an empty product reaches evolution without a clear contract error."""
    circuit = ProductObservablePEPO(edges=((0, 1),))

    with pytest.raises(ValueError, match="at least one"):
        circuit.evolve_product({})


def test_evolve_product_refuses_nonpositive_progress_cadence():
    """Breaks if an invalid callback cadence is accepted or divides by zero later."""
    circuit = ProductObservablePEPO(edges=((0, 1),))

    with pytest.raises(ValueError, match="positive"):
        circuit.evolve_product({0: Z}, progress_every=0)


def test_progress_records_are_immutable():
    """Breaks if a callback consumer can mutate a recorded diagnostic."""
    record = ProgressRecord(1, 2, 1, 1, None, 0.0)

    with pytest.raises(FrozenInstanceError):
        record.support_size = 2


def test_build_pepo_circuit_records_protocol_gates_on_declared_geometry():
    """Breaks if construction drops physical labels, edges, or recorded gate order."""
    protocol = OLEProtocol(
        register_size=8,
        layers=(
            (
                QASMGate("rx", (2,), 0.3, 0, 0),
                QASMGate("cz", (2, 7), None, 0, 1),
            ),
        ),
        active_sites=(2, 7),
        barrier_count=0,
    )

    circuit = build_pepo_circuit(protocol, max_bond=4, cutoff=1e-9)

    assert circuit.edges == ((2, 7),)
    assert circuit.sites == (2, 7)
    assert tuple(gate.qubits for gate in circuit.gates) == ((2,), (2, 7))
    assert circuit.max_bond == 4
    assert circuit.cutoff == 1e-9
    assert circuit.gate_opts["renorm"] is False


def test_build_pepo_circuit_refuses_protocol_without_cz_geometry():
    """Breaks if PEPO construction accepts a protocol with no interaction graph."""
    protocol = OLEProtocol(
        register_size=1,
        layers=((QASMGate("rx", (0,), 0.3, 0, 0),),),
        active_sites=(0,),
        barrier_count=0,
    )

    with pytest.raises(ValueError, match="CZ geometry"):
        build_pepo_circuit(protocol, max_bond=4, cutoff=1e-9)


@pytest.mark.parametrize("delta_zero", [True, False])
def test_seven_site_exact_pepo_matches_dense(delta_zero):
    """Breaks if real PEPO evolution and the independent seven-site oracle diverge."""
    full = parse_qasm(FULL_QASM.read_text(encoding="utf-8"))
    protocol = seven_site_oracle_protocol(full, delta_zero=delta_zero)
    dense = normalized_ole_dense(protocol, (52,))
    circuit = build_pepo_circuit(protocol, max_bond=None, cutoff=0.0)
    evolved = circuit.evolve_product({52: Z}, cutoff=0.0)
    pepo = normalized_overlap_exact(evolved.operator, {52: Z})

    assert pepo == pytest.approx(dense, rel=0.0, abs=1e-10)
    if delta_zero:
        assert dense == pytest.approx(1.0, rel=0.0, abs=1e-10)
        assert pepo == pytest.approx(1.0, rel=0.0, abs=1e-10)
