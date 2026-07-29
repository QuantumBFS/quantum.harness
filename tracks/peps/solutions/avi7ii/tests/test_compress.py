import inspect

import numpy as np
import pytest

from qh147.compress import (
    CompressionObjective,
    ThermodynamicTolerances,
    ThermodynamicWeights,
    VariationalCompressor,
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


def test_optimization_contractor_uses_fixed_rank_cutoff():
    objective = _objective()

    assert objective.contractor.cutoff == 1e-12
    assert objective.optimization_contractor.chi == objective.contractor.chi
    assert objective.optimization_contractor.cutoff == 0.0


def _two_site_objective() -> tuple[FinitePEPO, CompressionObjective]:
    teacher = FinitePEPO.identity(2, 1)
    for gate in second_order_gates(
        2,
        1,
        j=1.0,
        h=0.7,
        delta_beta=0.1,
    ):
        teacher.apply_gate(gate, max_bond=8)
    objective = CompressionObjective(
        BoundaryContractor(chi=8, cutoff=1e-10),
        j=1.0,
        h=0.7,
        tolerances=ThermodynamicTolerances(
            z=5e-2,
            u=5e-2,
            contraction_noise=1e-7,
        ),
        weights=ThermodynamicWeights(z=1.0, u=1.0, hermiticity=1.0),
    )
    return teacher, objective


@pytest.mark.parametrize("mode", ["ordinary", "thermodynamic"])
def test_variational_compression_reduces_its_loss_and_keeps_fixed_bond(mode):
    teacher, objective = _two_site_objective()
    result = VariationalCompressor(
        objective,
        max_iterations=3,
        optimizer="L-BFGS-B",
    ).compress(teacher, max_bond=1, mode=mode)

    assert result.max_bond <= 1
    assert result.final.total <= result.initial.total + 1e-10
    assert result.loss_history[-1] <= result.loss_history[0] + 1e-10
    assert np.isfinite(result.final.as_floats().total)
    assert result.mode == mode


def test_compression_modes_record_the_same_compute_budget():
    teacher, objective = _two_site_objective()
    compressor = VariationalCompressor(
        objective,
        max_iterations=1,
        optimizer="L-BFGS-B",
    )

    ordinary = compressor.compress(teacher, max_bond=1, mode="ordinary")
    thermodynamic = compressor.compress(
        teacher,
        max_bond=1,
        mode="thermodynamic",
    )

    assert ordinary.budget == thermodynamic.budget
    assert ordinary.budget.chi == objective.contractor.chi
    assert ordinary.budget.cutoff == objective.contractor.cutoff
    assert ordinary.budget.max_iterations == 1
    assert ordinary.budget.optimizer == "L-BFGS-B"


def test_optimizer_is_skipped_when_seed_already_meets_tolerance():
    teacher = FinitePEPO.identity(1, 1)
    objective = _objective()
    result = VariationalCompressor(
        objective,
        max_iterations=3,
        skip_optimization_tolerance=1e-10,
    ).compress(teacher, max_bond=1, mode="thermodynamic")

    assert result.iterations == 0
    assert result.loss_history == (result.initial.as_floats().total,)
    assert result.final == result.initial


def test_result_history_excludes_nonfinite_line_search_trials():
    teacher = FinitePEPO.identity(2, 2)
    for gate in second_order_gates(
        2,
        2,
        j=1.0,
        h=3.0,
        delta_beta=0.025,
    ):
        teacher.apply_gate(gate, max_bond=8)
    objective = CompressionObjective(
        BoundaryContractor(chi=16, cutoff=1e-10),
        j=1.0,
        h=3.0,
        tolerances=ThermodynamicTolerances(
            z=5e-2,
            u=5e-2,
            contraction_noise=1e-7,
        ),
        weights=ThermodynamicWeights(z=1.0, u=1.0, hermiticity=1.0),
    )

    result = VariationalCompressor(
        objective,
        max_iterations=3,
    ).compress(teacher, max_bond=1, mode="thermodynamic")

    assert result.iterations <= result.budget.max_iterations
    assert all(np.isfinite(value) for value in result.loss_history)
    assert np.isclose(result.loss_history[-1], result.final.as_floats().total)
