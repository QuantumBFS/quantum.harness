import numpy as np

from scripts.project_running_field_full_matrix_wall import (
    running_field,
    wall_from_scaled_structure,
)


def test_running_field_is_exact_joint_scaling_inverse():
    tau = 0.8
    times = np.asarray([50.0, 100.0, 200.0])
    fields = running_field(tau, times)
    assert np.allclose(times * fields**3, tau)
    assert np.all(np.diff(fields) < 0.0)


def test_direct_scaled_fourier_wall_keeps_absolute_width():
    q = np.linspace(0.0, 10.0, 1001)
    variance_q = 1.7
    structure = np.exp(-0.5 * variance_q * q**2)
    x = np.linspace(-180.0, 180.0, 3601)
    h = 0.2
    wall = wall_from_scaled_structure(q, structure, x, h)
    density = np.gradient(wall, x)
    normalization = np.trapezoid(density, x)
    second = np.trapezoid(density * x**2, x) / normalization
    assert np.isclose(normalization, 1.0, atol=2.0e-3)
    assert np.isclose(second, variance_q / h**4, rtol=3.0e-3)
