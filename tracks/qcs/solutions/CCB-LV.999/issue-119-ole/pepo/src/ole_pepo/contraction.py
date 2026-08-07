"""Normalized Hilbert--Schmidt contractions for evolved PEPO observables."""

from __future__ import annotations

from collections.abc import Mapping
import math
from numbers import Integral, Real

import numpy as np
import quimb.tensor as qtn


def product_overlap_network(
    operator: qtn.TensorNetworkGenOperator,
    operators: Mapping[int, np.ndarray],
) -> qtn.TensorNetwork:
    """Close an evolved operator against a product of local observables."""
    sites = tuple(operator.gen_sites_present())
    missing = set(operators).difference(sites)
    if missing:
        raise ValueError(f"operator is missing observable sites: {sorted(missing)}")

    network = operator.copy()
    for site in sorted(operators):
        network.gate_upper_(
            np.asarray(operators[site], dtype=np.complex128),
            site,
            contract=True,
        )

    mapping = {
        network.upper_ind(site): network.lower_ind(site)
        for site in network.gen_sites_present()
    }
    return network.reindex(mapping)


def _normalized_finite(raw: complex, nsites: int) -> complex:
    value = raw * math.ldexp(1.0, -nsites)
    if not (math.isfinite(value.real) and math.isfinite(value.imag)):
        raise ValueError("normalized overlap must have finite real and imaginary parts")
    return value


def _trace_local_physical_pairs(
    closed: qtn.TensorNetwork,
    sites: tuple[int, ...],
) -> qtn.TensorNetwork:
    """Remove exact local traces before quimb's non-hyper contraction."""
    for site in sites:
        physical_ind = closed.lower_ind(site)
        tensors = tuple(
            tensor for tensor in closed if physical_ind in tensor.inds
        )
        if len(tensors) != 1 or tensors[0].inds.count(physical_ind) != 2:
            raise ValueError(
                f"site {site} does not form one local repeated physical pair"
            )
        tensors[0].collapse_repeated_()
        closed.sum_reduce_(physical_ind)
    return closed


def normalized_overlap_exact(
    operator: qtn.TensorNetworkGenOperator,
    operators: Mapping[int, np.ndarray],
    optimize: str = "auto-hq",
) -> complex:
    """Contract the normalized product-observable overlap exactly."""
    sites = tuple(operator.gen_sites_present())
    closed = product_overlap_network(operator, operators)
    raw = complex(closed.contract(all, optimize=optimize))
    return _normalized_finite(raw, len(sites))


def normalized_overlap_compressed(
    operator: qtn.TensorNetworkGenOperator,
    operators: Mapping[int, np.ndarray],
    chi_env: int,
    cutoff: float,
    optimize: str = "auto-hq",
    progress: bool = False,
) -> complex:
    """Contract the normalized overlap with bounded intermediate bonds."""
    if (
        isinstance(chi_env, bool)
        or not isinstance(chi_env, Integral)
        or chi_env <= 0
    ):
        raise ValueError("chi_env must be a positive integer")
    if (
        isinstance(cutoff, bool)
        or not isinstance(cutoff, Real)
        or not math.isfinite(float(cutoff))
        or cutoff < 0
    ):
        raise ValueError("cutoff must be a finite nonnegative real number")

    sites = tuple(operator.gen_sites_present())
    closed = product_overlap_network(operator, operators)
    _trace_local_physical_pairs(closed, sites)
    raw = complex(
        closed.contract_compressed(
            max_bond=chi_env,
            cutoff=cutoff,
            optimize=optimize,
            progbar=progress,
        )
    )
    return _normalized_finite(raw, len(sites))
