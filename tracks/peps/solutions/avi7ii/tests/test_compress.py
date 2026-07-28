import inspect

import numpy as np
import pytest

from qh147.compress import (
    CompressionObjective,
    ThermodynamicTolerances,
    ThermodynamicWeights,
)
from qh147.contract import BoundaryContractor
from qh147.pepo import FinitePEPO
from qh147.trotter import second_order_gates


def _teacher() -> FinitePEPO:
    pepo = FinitePEPO.identity(1, 1)
    for gate in second_order_gates(
        1,
        1,
        j=1.0,
        h=0.7,
        delta_beta=0.1,
    ):
        pepo.apply_gate(gate, max_bond=4)
    return pepo


def _objective() -> CompressionObjective:
    return CompressionObjective(
        BoundaryContractor(chi=8, cutoff=1e-12),
        j=1.0,
        h=0.7,
        tolerances=ThermodynamicTolerances(
            z=1e-3,
            u=2e-3,
            contraction_noise=1e-8,
        ),
        weights=ThermodynamicWeights(z=2.0, u=3.0, hermiticity=5.0),
    )


@pytest.mark.parametrize("field", ["z", "u"])
def test_thermodynamic_tolerance_must_exceed_contraction_noise(field):
    values = {"z": 1e-6, "u": 1e-6, "contraction_noise": 1e-7}
    values[field] = values["contraction_noise"]
    with pytest.raises(ValueError, match="contraction noise"):
        ThermodynamicTolerances(**values)


def test_ordinary_mode_is_exactly_the_relative_frobenius_loss():
    teacher = _teacher()
    student = FinitePEPO.identity(1, 1)
    objective = _objective()
    target = objective.teacher_point(teacher)

    loss = objective.loss(student, teacher, teacher_point=target, mode="ordinary")

    assert np.allclose(
        loss,
        objective.contractor.relative_frobenius_loss(student, teacher),
    )


def test_thermodynamic_mode_matches_the_approved_composite_loss():
    teacher = _teacher()
    student = FinitePEPO.identity(1, 1)
    objective = _objective()
    target = objective.teacher_point(teacher)
    student_point = objective.contractor.thermodynamic_point(
        student,
        j=objective.j,
        h=objective.h,
        log_scale=0.0,
    )
    frobenius = objective.contractor.relative_frobenius_loss(student, teacher)
    dz = student_point.z - target.z
    du = student_point.u - target.u
    hermiticity = objective.contractor.hermiticity_residual(student)
    expected = (
        frobenius
        + objective.weights.z * (dz / objective.tolerances.z) ** 2
        + objective.weights.u * (du / objective.tolerances.u) ** 2
        + objective.weights.hermiticity * hermiticity**2
    )

    actual = objective.loss(
        student,
        teacher,
        teacher_point=target,
        mode="thermodynamic",
    )

    assert np.allclose(actual, expected)


def test_diagnostics_report_unscaled_differences_and_loss_components():
    teacher = _teacher()
    student = FinitePEPO.identity(1, 1)
    objective = _objective()
    target = objective.teacher_point(teacher)

    diagnostics = objective.diagnostics(
        student,
        teacher,
        teacher_point=target,
        mode="thermodynamic",
    ).as_floats()

    assert np.isclose(
        diagnostics.total,
        diagnostics.frobenius
        + diagnostics.z_penalty
        + diagnostics.u_penalty
        + diagnostics.hermiticity_penalty,
    )
    assert np.isfinite(diagnostics.z_difference)
    assert np.isfinite(diagnostics.u_difference)


def test_objective_api_has_no_specific_heat_or_external_reference_inputs():
    parameters = set(inspect.signature(CompressionObjective).parameters)
    assert parameters == {
        "contractor",
        "j",
        "h",
        "tolerances",
        "weights",
    }
