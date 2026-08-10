import pytest

from challenge15.spec import SphereSpec


@pytest.mark.parametrize(
    ("particles", "two_q", "orbitals", "dimension"),
    [(6, 15, 16, 8008), (7, 18, 19, 50388), (8, 21, 22, 319770)],
)
def test_laughlin_sphere_spec(particles, two_q, orbitals, dimension):
    spec = SphereSpec(particles)
    assert spec.two_q == two_q
    assert spec.orbital_count == orbitals
    assert spec.full_dimension == dimension
    assert spec.two_m_values[0] == -two_q
    assert spec.two_m_values[-1] == two_q


def test_invalid_particle_number_is_rejected():
    with pytest.raises(ValueError, match="particles must be at least 2"):
        SphereSpec(1)
