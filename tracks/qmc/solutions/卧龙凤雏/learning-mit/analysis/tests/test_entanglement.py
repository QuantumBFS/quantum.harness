import numpy as np

from analysis.entanglement import fit_entropy_arc


def arc_points(kind: str) -> np.ndarray:
    length = 64.0
    interval = np.arange(1.0, 32.0)
    radius = length / np.pi * np.sin(np.pi * interval / length)
    log_radius = np.log(radius)
    if kind == "constant":
        entropy = np.full_like(interval, 0.8)
    elif kind == "log":
        entropy = 0.4 + 0.23 * log_radius
    elif kind == "log_log2":
        entropy = 0.4 + 0.12 * log_radius + 0.19 * log_radius**2
    else:
        raise AssertionError(kind)
    entropy += 1e-4 * np.sin(interval)
    sigma = np.full_like(interval, 1e-3)
    return np.column_stack([interval, np.full_like(interval, length), entropy, sigma])


def test_aicc_selects_area_log_and_squared_log_fixtures():
    models = ("constant", "log", "log2", "log_log2", "page_log_log2")
    assert fit_entropy_arc(arc_points("constant"), models).best_model == "constant"
    assert fit_entropy_arc(arc_points("log"), models).best_model == "log"
    assert fit_entropy_arc(arc_points("log_log2"), models).best_model == "log_log2"
