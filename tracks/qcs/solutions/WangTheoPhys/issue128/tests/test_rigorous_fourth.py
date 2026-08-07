from fractions import Fraction

import pytest

from trottercert.rigorous_fourth import _rational_pair_bound
from trottercert.intervals import RationalInterval


def test_rational_pair_bound_dominates_euclidean_norm() -> None:
    coefficients = (
        RationalInterval.point(3),
        RationalInterval.point(4),
        RationalInterval(Fraction(19, 10), Fraction(21, 10)),
    )
    bound = _rational_pair_bound(coefficients, ((0, 1),), (2,))
    assert float(bound) >= (3**2 + 4**2) ** 0.5 + 2.1


@pytest.mark.slow
def test_fourth_order_rational_certificate_crosses_target() -> None:
    from trottercert.rigorous_fourth import fourth_order_rational_pair_certificate

    certificate = fourth_order_rational_pair_certificate(center=17)
    assert certificate.site_density_upper < Fraction(9687, 100)


@pytest.mark.slow
def test_published_triangle_certificate_reproduces_baseline() -> None:
    from trottercert.rigorous_fourth import (
        fourth_order_published_triangle_certificate,
    )

    certificate = fourth_order_published_triangle_certificate(decimal_digits=12)
    assert certificate.center == 20
    assert Fraction(164) < certificate.site_density_upper < Fraction(166)
