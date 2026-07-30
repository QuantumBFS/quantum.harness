from __future__ import annotations

import numpy as np
from numpy.testing import assert_allclose

from floquet_if_manybody.config import BathConfig
from floquet_if_manybody.model_comparison import (
    diagnostic_heat_rescaling,
    model_variants,
    variant_operators,
)


def test_variants_have_expected_coupling_norms() -> None:
    variants = model_variants(n=3, j=0.5, bath=BathConfig(alpha=0.1, cutoff=2.5))
    bounded = next(item for item in variants if item.name == "bounded_no_ct")
    kac = next(item for item in variants if item.name == "kac_no_ct")
    _, bounded_s = variant_operators(bounded)
    _, kac_s = variant_operators(kac)
    assert_allclose(np.linalg.norm(bounded_s, 2), 1.0)
    assert_allclose(np.linalg.norm(kac_s, 2), np.sqrt(3))


def test_counterterm_difference_is_explicit_s_squared() -> None:
    bath = BathConfig(alpha=0.1, cutoff=2.5)
    variants = model_variants(n=3, j=0.5, bath=bath)
    no_ct = next(item for item in variants if item.name == "bounded_no_ct")
    with_ct = next(item for item in variants if item.name == "bounded_ct")
    h0, coupling = variant_operators(no_ct)
    hct, _ = variant_operators(with_ct)
    assert_allclose(hct - h0, bath.alpha * bath.cutoff * coupling @ coupling)
    assert with_ct.metadata["counterterm_strength"] == 0.25
    assert with_ct.metadata["normalization"] == "bounded"


def test_diagnostic_rescaling_never_overwrites_raw_heat() -> None:
    values = np.array([1.0, 2.0])
    raw, diagnostic = diagnostic_heat_rescaling(values, eta=1 / 3)
    assert_allclose(raw, values)
    assert_allclose(diagnostic, 9 * values)
    assert not np.shares_memory(raw, values)
