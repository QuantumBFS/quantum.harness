import numpy as np

from oracle.oddcycle_local_hs_scan import (
    forbidden_label_indices,
    locality_specs,
    scan_positive_matrix_kernel,
)
from oracle.oddcycle_word_operator import NormalOrderedLabel, normal_ordered_labels


def test_ring_edge_locality_does_not_accept_a_three_site_support():
    spec = locality_specs()["ring-edge"]
    labels = normal_ordered_labels(5)
    three_site = NormalOrderedLabel(create=(0, 2), annihilate=(0, 1))
    assert three_site.support == frozenset({0, 1, 2})
    forbidden = {labels[index] for index in forbidden_label_indices(labels, spec)}
    assert three_site in forbidden


def test_ring_arc3_accepts_only_one_contiguous_three_site_arc():
    spec = locality_specs()["ring-arc3"]
    assert spec.allows_support(frozenset({4, 0, 1}))
    assert not spec.allows_support(frozenset({0, 2, 4}))


def test_positive_kernel_scan_distinguishes_feasible_and_infeasible():
    feasible = scan_positive_matrix_kernel(
        np.array([[1.0, -1.0], [0.0, 0.0]])
    )
    assert feasible.status == "numerical-survivor"
    assert np.all(feasible.weights > 0)
    assert np.max(np.abs(np.array([[1.0, -1.0]]) @ feasible.weights)) < 1e-9

    impossible = scan_positive_matrix_kernel(np.array([[1.0, 2.0]]))
    assert impossible.status == "numerically-infeasible"
