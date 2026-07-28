from .problem import EDGES, VERTICES, independence_number
from .theta_relaxation import solve_theta


def test_graph33_independence_number():
    assert independence_number() == 2


def test_pentagon_level_two_closes():
    pentagon = {(index, (index + 1) % 5) for index in range(5)}
    result = solve_theta(5, pentagon, 2)
    assert abs(result["value"] - 2.0) < 2e-5


def test_graph33_strengthened_levels_are_monotone():
    values = [solve_theta(len(VERTICES), EDGES, order)["value"] for order in (1, 2, 3)]
    assert abs(values[0] - 2.2360679775) < 2e-6
    assert values[0] >= values[1] >= values[2] >= 2.0 - 2e-7
    # These include more state-polynomial identities than the paper's reduced
    # theta_k hierarchy, so levels 2/3 are intentionally stronger.
    assert values[1] < 2.003
    assert values[2] < 2.0001
