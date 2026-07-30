from xxzcert.lti_reflection import reflection_bases, solve_reflection_lti
from xxzcert.lti_u1 import sector_basis, solve_u1_lti


def test_reflection_bases_span_each_sector():
    for ones in range(7):
        plus, minus = reflection_bases(6, ones)
        assert plus.shape[0] == len(sector_basis(6, ones))
        assert plus.shape[1] + minus.shape[1] == plus.shape[0]
        assert (plus.T @ minus == 0).all()


def test_reflection_reduction_matches_u1_lti():
    ordinary = solve_u1_lti(1.0, 5)
    reflected = solve_reflection_lti(
        1.0,
        5,
        solver_options={"eps": 1e-7, "max_iters": 20_000},
    )
    assert abs(ordinary.raw_lower - reflected.raw_lower) < 2e-6
    assert reflected.max_equality_residual < 1e-6
