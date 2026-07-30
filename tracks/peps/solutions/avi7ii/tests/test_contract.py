import warnings

import numpy as np
import pytest
import quimb.tensor as qtn

import qh147.contract as contract_module
from qh147.contract import BoundaryContractor
from qh147.model import tfim_dense
from qh147.pepo import FinitePEPO
from qh147.trotter import second_order_gates


def _one_trotter_step(lx: int, ly: int) -> FinitePEPO:
    pepo = FinitePEPO.identity(lx, ly)
    for gate in second_order_gates(
        lx,
        ly,
        j=1.0,
        h=3.0,
        delta_beta=0.1,
    ):
        pepo.apply_gate(gate, max_bond=64)
    return pepo


def _uniform_bond_pepo(lx: int, ly: int, bond: int) -> FinitePEPO:
    tensors = []
    for x in range(lx):
        for y in range(ly):
            virtual = []
            if x > 0:
                virtual.append(f"hx{x - 1},{y}")
            if x + 1 < lx:
                virtual.append(f"hx{x},{y}")
            if y > 0:
                virtual.append(f"vy{x},{y - 1}")
            if y + 1 < ly:
                virtual.append(f"vy{x},{y}")
            data = np.zeros((2, 2) + (bond,) * len(virtual))
            tensors.append(
                qtn.Tensor(
                    data,
                    inds=(f"ko{x},{y}", f"ki{x},{y}", *virtual),
                    tags={f"I{x},{y}", "PEPO"},
                )
            )
    return FinitePEPO(lx=lx, ly=ly, tn=qtn.TensorNetwork(tensors))


@pytest.mark.parametrize("shape", [(1, 1), (2, 2)])
@pytest.mark.parametrize("evolved", [False, True])
def test_trace_and_operator_insertion_match_dense(shape, evolved):
    lx, ly = shape
    pepo = _one_trotter_step(lx, ly) if evolved else FinitePEPO.identity(lx, ly)
    dense = pepo.to_dense()
    contractor = BoundaryContractor(chi=64, cutoff=1e-12)

    assert np.allclose(contractor.trace(pepo), np.trace(dense))

    operator = np.array(
        [[1.0 + 2.0j, -3.0j], [0.5 + 1.0j, -2.0 + 0.25j]]
    )
    inserted = contractor.expectation_numerator(pepo, {(0, 0): operator})
    full_operator = np.kron(operator, np.eye(1 << (lx * ly - 1)))
    assert np.allclose(inserted, np.trace(dense @ full_operator))


@pytest.mark.parametrize("shape", [(1, 1), (2, 2)])
def test_overlap_and_relative_frobenius_loss_match_dense(shape):
    lx, ly = shape
    teacher = _one_trotter_step(lx, ly)
    student = FinitePEPO.identity(lx, ly)
    teacher_dense = teacher.to_dense()
    student_dense = student.to_dense()
    contractor = BoundaryContractor(chi=64, cutoff=1e-12)

    expected_overlap = np.trace(student_dense.conj().T @ teacher_dense)
    expected_loss = (
        np.linalg.norm(student_dense - teacher_dense) ** 2
        / np.linalg.norm(teacher_dense) ** 2
    )
    assert np.allclose(contractor.overlap(student, teacher), expected_overlap)
    assert np.allclose(
        contractor.relative_frobenius_loss(student, teacher), expected_loss
    )


def test_double_layer_network_remains_lazy_at_teacher_bond(monkeypatch):
    pepo = _uniform_bond_pepo(3, 3, bond=16)
    contractor = BoundaryContractor(chi=16, cutoff=1e-12)
    autoray_do = contract_module.ar.do

    def reject_local_materialization(function, *args, **kwargs):
        if function == "einsum":
            raise AssertionError("double-layer construction materialized a site")
        return autoray_do(function, *args, **kwargs)

    monkeypatch.setattr(contract_module.ar, "do", reject_local_materialization)

    network = contractor._double_layer_network(
        pepo,
        pepo,
        conjugate_bra=True,
        swap_ket_physical=False,
    )

    assert network.num_tensors == 18
    for x in range(3):
        for y in range(3):
            site_tensors = network.select_tensors(f"I{x},{y}")
            assert len(site_tensors) == 2
            assert {"BRA", "KET"} == {
                next(tag for tag in tensor.tags if tag in {"BRA", "KET"})
                for tensor in site_tensors
            }
            assert all(tensor.ndim <= 6 for tensor in site_tensors)
            assert all(tensor.size < 16**8 for tensor in site_tensors)


def test_operator_insertion_contracts_input_then_output_indices():
    pepo = FinitePEPO.identity(1, 1)
    pepo.tn["I0,0"].modify(
        data=np.array([[1.0 + 0.5j, 2.0j], [3.0 - 1.0j, -4.0]])
    )
    operator = np.array(
        [[2.0 - 1.0j, -3.0j], [0.25 + 2.0j, 1.0 + 0.5j]]
    )
    contractor = BoundaryContractor(chi=4, cutoff=1e-12)

    assert np.allclose(
        contractor.expectation_numerator(pepo, {(0, 0): operator}),
        np.trace(pepo.to_dense() @ operator),
    )


@pytest.mark.parametrize("shape", [(1, 1), (2, 2)])
@pytest.mark.parametrize("evolved", [False, True])
def test_thermodynamic_point_and_hermiticity_match_dense(shape, evolved):
    lx, ly = shape
    pepo = _one_trotter_step(lx, ly) if evolved else FinitePEPO.identity(lx, ly)
    dense = pepo.to_dense()
    hmat = tfim_dense(lx, ly, j=1.0, h=3.0)
    contractor = BoundaryContractor(chi=64, cutoff=1e-12)

    point = contractor.thermodynamic_point(pepo, j=1.0, h=3.0, log_scale=0.0)
    partition_function = np.trace(dense)
    expected_z = np.log(partition_function.real) / (lx * ly)
    expected_u = np.trace(hmat @ dense) / (lx * ly * partition_function)
    expected_hermiticity = (
        np.linalg.norm(dense - dense.conj().T) / np.linalg.norm(dense)
    )

    assert np.allclose(point.z, expected_z)
    assert np.allclose(point.u, expected_u)
    assert np.allclose(
        contractor.hermiticity_residual(pepo),
        expected_hermiticity,
        atol=5e-8,
    )


def test_trace_remains_jax_differentiable():
    jax = pytest.importorskip("jax")
    jnp = pytest.importorskip("jax.numpy")
    pepo = FinitePEPO.identity(1, 1)
    site = pepo.tn["I0,0"]
    contractor = BoundaryContractor(chi=4, cutoff=1e-12)

    def trace_at(scale):
        site.modify(data=scale * jnp.eye(2))
        return contractor.trace(pepo)

    assert np.allclose(jax.grad(trace_at)(jnp.array(1.0)), 2.0)


def test_lazy_frobenius_loss_remains_jax_differentiable():
    jax = pytest.importorskip("jax")
    jnp = pytest.importorskip("jax.numpy")
    student = FinitePEPO.identity(1, 1)
    teacher = FinitePEPO.identity(1, 1)
    site = student.tn["I0,0"]
    contractor = BoundaryContractor(chi=4, cutoff=0.0)

    def loss_at(scale):
        site.modify(data=scale * jnp.eye(2))
        return contractor.relative_frobenius_loss(student, teacher)

    scale = jnp.array(0.5)
    derivative = jax.grad(loss_at)(scale)
    finite_difference = (loss_at(scale + 1e-4) - loss_at(scale - 1e-4)) / (
        2e-4
    )

    assert np.allclose(derivative, -1.0, rtol=1e-6, atol=1e-6)
    assert np.allclose(derivative, finite_difference, rtol=2e-4, atol=1e-6)


def test_hermiticity_residual_matches_a_nonhermitian_dense_operator():
    pepo = FinitePEPO.identity(1, 1)
    pepo.tn["I0,0"].modify(data=np.array([[1.0, 2.0j], [0.0, 1.0]]))
    dense = pepo.to_dense()
    expected = np.linalg.norm(dense - dense.conj().T) / np.linalg.norm(dense)

    contractor = BoundaryContractor(chi=4, cutoff=1e-12)
    assert np.allclose(contractor.hermiticity_residual(pepo), expected)


def test_nonpositive_partition_is_rejected_only_when_reporting_floats():
    pepo = FinitePEPO.identity(1, 1)
    pepo.tn["I0,0"].modify(data=-np.eye(2))
    contractor = BoundaryContractor(chi=4, cutoff=1e-12)

    with np.errstate(invalid="ignore"):
        point = contractor.thermodynamic_point(
            pepo,
            j=1.0,
            h=3.0,
            log_scale=0.0,
        )
    with pytest.raises(FloatingPointError, match="non-positive"):
        point.as_floats()


def test_boundary_contraction_does_not_require_optional_kahypar():
    pepo = FinitePEPO.identity(2, 2)
    contractor = BoundaryContractor(chi=4, cutoff=1e-12)

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "error",
            message="Couldn't import `kahypar`.*",
            category=UserWarning,
        )
        assert np.isclose(contractor.trace(pepo), 16.0)


def test_thermodynamic_point_reuses_plaquette_environments():
    class CountingContractor(BoundaryContractor):
        def __init__(self):
            super().__init__(chi=16, cutoff=1e-12)
            self.full_contractions = 0

        def _contract(self, network):
            self.full_contractions += 1
            return super()._contract(network)

    pepo = _one_trotter_step(2, 2)
    contractor = CountingContractor()

    point = contractor.thermodynamic_point(
        pepo,
        j=1.0,
        h=3.0,
        log_scale=0.0,
    ).as_floats()

    assert np.isfinite(point.u)
    assert contractor.full_contractions == 1


def test_batched_energy_remains_jax_differentiable():
    jax = pytest.importorskip("jax")
    jnp = pytest.importorskip("jax.numpy")
    pepo = FinitePEPO.identity(2, 2)
    site = pepo.tn["I0,0"]
    base = jnp.asarray(site.data)
    perturbation = jnp.zeros_like(base).at[0, 1].set(1.0)
    contractor = BoundaryContractor(chi=8, cutoff=1e-12)

    def energy_at(scale):
        site.modify(data=base + scale * perturbation)
        return contractor.thermodynamic_point(
            pepo,
            j=1.0,
            h=3.0,
            log_scale=0.0,
        ).u

    derivative = jax.grad(energy_at)(jnp.array(0.0))

    assert np.isfinite(float(derivative))
