import numpy as np
import pytest

from ole_pepo.contraction import (
    normalized_overlap_compressed,
    normalized_overlap_exact,
    product_overlap_network,
)
from ole_pepo.engine import build_pepo_circuit
from ole_pepo.exact import normalized_ole_dense
from ole_pepo.qasm import OLEProtocol, QASMGate


Z = np.diag([1.0, -1.0]).astype(np.complex128)


@pytest.fixture
def three_site_protocol() -> OLEProtocol:
    return OLEProtocol(
        register_size=3,
        layers=(
            (
                QASMGate("rx", (0,), 0.37, 0, 0),
                QASMGate("rx", (1,), -0.29, 0, 1),
                QASMGate("rx", (2,), 0.41, 0, 2),
            ),
            (
                QASMGate("cz", (0, 1), None, 1, 3),
                QASMGate("cz", (1, 2), None, 1, 4),
            ),
            (
                QASMGate("rx", (1,), 0.23, 2, 5),
                QASMGate("rz", (2,), -0.17, 2, 6),
            ),
        ),
        active_sites=(0, 1, 2),
        barrier_count=2,
    )


def _evolved_operator(protocol: OLEProtocol, operators: dict[int, np.ndarray]):
    circuit = build_pepo_circuit(protocol, max_bond=None, cutoff=0.0)
    return circuit.evolve_product(operators, cutoff=0.0).operator


def test_exact_and_compressed_overlap_match_independent_dense_oracle(
    three_site_protocol,
):
    """Breaks if closure, normalization, or compressed contraction changes the OLE."""
    dense_value = normalized_ole_dense(three_site_protocol, (1,))
    operator = _evolved_operator(three_site_protocol, {1: Z})
    exact = normalized_overlap_exact(operator, {1: Z})
    compressed = normalized_overlap_compressed(
        operator,
        {1: Z},
        chi_env=64,
        cutoff=0.0,
    )

    assert exact == pytest.approx(
        dense_value,
        abs=1e-11,
    )
    assert compressed == pytest.approx(exact, abs=1e-10)
    assert compressed == pytest.approx(dense_value, abs=1e-10)


def test_product_observable_overlap_matches_independent_dense_oracle(
    three_site_protocol,
):
    """Breaks if either factor of a disconnected product observable is omitted."""
    dense_value = normalized_ole_dense(three_site_protocol, (0, 2))
    operator = _evolved_operator(three_site_protocol, {0: Z, 2: Z})

    assert normalized_overlap_exact(operator, {0: Z, 2: Z}) == pytest.approx(
        dense_value,
        abs=1e-11,
    )


def test_identity_evolution_has_unit_normalized_product_overlap():
    """Breaks if the raw Hilbert--Schmidt trace is not divided by 2**N."""
    protocol = OLEProtocol(
        register_size=3,
        layers=(
            (
                QASMGate("cz", (0, 1), None, 0, 0),
                QASMGate("cz", (1, 2), None, 0, 1),
            ),
        ),
        active_sites=(0, 1, 2),
        barrier_count=0,
    )
    operator = _evolved_operator(protocol, {0: Z, 2: Z})

    assert normalized_overlap_exact(operator, {0: Z, 2: Z}) == pytest.approx(
        1.0,
        abs=1e-12,
    )


def test_product_overlap_network_refuses_an_absent_observable_site(
    three_site_protocol,
):
    """Breaks if an unknown label silently creates a malformed closed network."""
    operator = _evolved_operator(three_site_protocol, {1: Z})

    with pytest.raises(ValueError, match="observable sites"):
        product_overlap_network(operator, {7: Z})


@pytest.mark.parametrize("chi_env", [0, -1, 1.5, True])
def test_compressed_overlap_requires_a_positive_integer_environment_bond(
    three_site_protocol,
    chi_env,
):
    """Breaks if an invalid compression bond dimension reaches quimb."""
    operator = _evolved_operator(three_site_protocol, {1: Z})

    with pytest.raises(ValueError, match="chi_env"):
        normalized_overlap_compressed(
            operator,
            {1: Z},
            chi_env=chi_env,
            cutoff=0.0,
        )


def test_compressed_overlap_refuses_a_negative_cutoff(three_site_protocol):
    """Breaks if a negative truncation threshold reaches quimb."""
    operator = _evolved_operator(three_site_protocol, {1: Z})

    with pytest.raises(ValueError, match="cutoff"):
        normalized_overlap_compressed(
            operator,
            {1: Z},
            chi_env=4,
            cutoff=-1e-12,
        )


@pytest.mark.parametrize(
    "contract",
    [
        pytest.param(
            lambda operator: normalized_overlap_exact(operator, {1: Z}),
            id="exact",
        ),
        pytest.param(
            lambda operator: normalized_overlap_compressed(
                operator,
                {1: Z},
                chi_env=4,
                cutoff=0.0,
            ),
            id="compressed",
        ),
    ],
)
def test_overlap_refuses_a_nonfinite_contracted_scalar(
    three_site_protocol,
    contract,
):
    """Breaks if NaN or infinity can escape into an OLE result."""
    operator = _evolved_operator(three_site_protocol, {1: Z}).copy()
    tensor = operator.tensors[0]
    data = tensor.data.copy()
    data.flat[0] = np.nan
    tensor.modify(data=data)

    with pytest.raises(ValueError, match="finite"):
        contract(operator)
