from fractions import Fraction

from trottercert.crosscheck import small_exact_crosscheck


def test_small_exact_evolution_is_below_certificate() -> None:
    result = small_exact_crosscheck(2, Fraction(1, 1000))
    assert result["bound_dominates_empirical_error"]
    assert result["bound_meets_tolerance"]
