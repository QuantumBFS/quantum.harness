"""Construction of aligned profile/current/response/FCS analysis panels."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np

from .research_dataset import ResearchDataset

Array = np.ndarray
PULSE_POS = "response_local_pulse_pos"
PULSE_NEG = "response_local_pulse_neg"
EQUILIBRIUM = "equilibrium_m0"


@dataclass(frozen=True)
class JointObservablePanel:
    t: Array
    x: Array
    profile: dict[str, Array]
    current: dict[str, Array]
    response_cmm: dict[str, Array]
    response_cjm: dict[str, Array]
    response_even: dict[str, Array]
    fcs_gamma: dict[str, Array]
    fcs_logz: dict[str, Array]
    masks: dict[str, Array]
    diagnostics: dict[str, float]
    metadata: dict[str, dict[str, object]] = field(default_factory=dict)
    simulation_x: Array | None = None
    profile_mask: Array | None = None
    current_masks: dict[str, Array] = field(default_factory=dict)
    physical_initial: dict[str, Array] = field(default_factory=dict)
    czz: dict[str, Array] = field(default_factory=dict)


def subset_joint_observable_panel(
    panel: JointObservablePanel,
    condition_ids: set[str],
) -> JointObservablePanel:
    """Return a condition subset while preserving registered response blocks."""

    selected = set(map(str, condition_ids))
    unknown = selected - set(panel.profile)
    if unknown:
        raise ValueError(
            "unknown panel conditions: " + ", ".join(sorted(unknown))
        )
    retain_response = {PULSE_POS, PULSE_NEG} <= selected
    return JointObservablePanel(
        t=np.asarray(panel.t).copy(),
        x=np.asarray(panel.x).copy(),
        profile={
            key: value for key, value in panel.profile.items() if key in selected
        },
        current={
            key: value for key, value in panel.current.items() if key in selected
        },
        response_cmm=(
            dict(panel.response_cmm) if retain_response else {}
        ),
        response_cjm=(
            dict(panel.response_cjm) if retain_response else {}
        ),
        response_even=(
            dict(panel.response_even) if retain_response else {}
        ),
        fcs_gamma={
            key: value
            for key, value in panel.fcs_gamma.items()
            if key in selected
        },
        fcs_logz={
            key: value
            for key, value in panel.fcs_logz.items()
            if key in selected
        },
        masks={key: np.asarray(value).copy() for key, value in panel.masks.items()},
        diagnostics=dict(panel.diagnostics),
        metadata={
            key: value for key, value in panel.metadata.items() if key in selected
        },
        simulation_x=(
            None
            if panel.simulation_x is None
            else np.asarray(panel.simulation_x).copy()
        ),
        profile_mask=(
            None
            if panel.profile_mask is None
            else np.asarray(panel.profile_mask).copy()
        ),
        current_masks={
            key: value
            for key, value in panel.current_masks.items()
            if key in selected
        },
        physical_initial={
            key: value
            for key, value in panel.physical_initial.items()
            if key in selected
        },
        czz={
            key: value for key, value in panel.czz.items() if key in selected
        },
    )


def _physical_signature(dataset: ResearchDataset) -> tuple[object, ...]:
    metadata = dataset.metadata
    return tuple(
        metadata.get(key)
        for key in (
            "delta",
            "J",
            "J2",
            "temperature",
            "L",
            "boundary_condition",
        )
    )


def _indices(source: Array, target: Array) -> Array:
    positions = np.searchsorted(source, target)
    if np.any(positions >= source.size) or not np.array_equal(
        source[positions], target
    ):
        raise ValueError("time grids do not share an exact recorded intersection")
    return positions


def build_joint_observable_panel(
    datasets: Mapping[str, ResearchDataset],
    *,
    pulse_amplitude: float,
    spatial_window: tuple[float, float],
) -> JointObservablePanel:
    """Align registered datasets and form centered finite-amplitude response."""

    if pulse_amplitude <= 0:
        raise ValueError("pulse_amplitude must be positive")
    required = {PULSE_POS, PULSE_NEG, EQUILIBRIUM}
    missing = required - set(datasets)
    if missing:
        raise ValueError("missing required response datasets: " + ", ".join(sorted(missing)))
    ordered = {str(key): value for key, value in sorted(datasets.items())}
    first = next(iter(ordered.values()))
    signature = _physical_signature(first)
    for condition_id, dataset in ordered.items():
        if _physical_signature(dataset) != signature:
            raise ValueError(f"Hamiltonian/numerical signature mismatch for {condition_id}")
        if not np.array_equal(dataset.x, first.x):
            raise ValueError(f"spatial grid mismatch for {condition_id}")

    start, stop = map(float, spatial_window)
    if not start < stop:
        raise ValueError("spatial_window must be increasing")
    spatial_mask = (first.x >= start) & (first.x <= stop)
    if np.count_nonzero(spatial_mask) < 3:
        raise ValueError("spatial_window retains fewer than three sites")

    common_t = np.asarray(first.t)
    for dataset in ordered.values():
        common_t = np.intersect1d(common_t, np.asarray(dataset.t), assume_unique=True)
    if common_t.size < 2:
        raise ValueError("datasets have fewer than two common recorded times")

    profile: dict[str, Array] = {}
    current: dict[str, Array] = {}
    czz: dict[str, Array] = {}
    fcs_gamma: dict[str, Array] = {}
    fcs_logz: dict[str, Array] = {}
    aligned_m: dict[str, Array] = {}
    physical_initial: dict[str, Array] = {}
    current_masks: dict[str, Array] = {}
    for condition_id, dataset in ordered.items():
        time_index = _indices(np.asarray(dataset.t), common_t)
        profile[condition_id] = np.asarray(dataset.u)[time_index][:, spatial_mask]
        physical_m = dataset.m if dataset.m is not None else dataset.u
        physical_values = np.asarray(physical_m)[time_index]
        aligned_m[condition_id] = physical_values[:, spatial_mask]
        physical_initial[condition_id] = physical_values[0].copy()
        if dataset.current is not None:
            current_values = np.asarray(dataset.current)[time_index]
            if current_values.shape[1] == dataset.x.size:
                current_mask = spatial_mask
            elif current_values.shape[1] == dataset.x.size - 1:
                bond_centers = 0.5 * (dataset.x[:-1] + dataset.x[1:])
                current_mask = (bond_centers >= start) & (bond_centers <= stop)
            else:
                raise ValueError(f"invalid current grid for {condition_id}")
            current[condition_id] = current_values[:, current_mask]
            current_masks[condition_id] = np.asarray(current_mask, dtype=bool)
        if dataset.czz is not None:
            czz[condition_id] = np.asarray(dataset.czz)[time_index][
                :, spatial_mask
            ]
        if dataset.fcs_gamma is not None and dataset.fcs_logZ is not None:
            fcs_gamma[condition_id] = np.asarray(dataset.fcs_gamma, dtype=float)
            fcs_logz[condition_id] = np.asarray(dataset.fcs_logZ)[time_index]

    pos = ordered[PULSE_POS]
    neg = ordered[PULSE_NEG]
    if (
        not np.isclose(float(pos.metadata.get("mu")), pulse_amplitude)
        or not np.isclose(float(neg.metadata.get("mu")), pulse_amplitude)
        or int(pos.metadata.get("orientation", 0)) != 1
        or int(neg.metadata.get("orientation", 0)) != -1
        or not np.isclose(float(pos.metadata.get("width")), float(neg.metadata.get("width")))
    ):
        raise ValueError("pulse pair amplitude, orientation, or width mismatch")
    cmm = (aligned_m[PULSE_POS] - aligned_m[PULSE_NEG]) / (
        2.0 * pulse_amplitude
    )
    equilibrium_m = aligned_m[EQUILIBRIUM]
    even_m = (
        0.5 * (aligned_m[PULSE_POS] + aligned_m[PULSE_NEG])
        - equilibrium_m
    )
    if PULSE_POS not in current or PULSE_NEG not in current:
        raise ValueError("pulse pair is missing local spin current")
    if current[PULSE_POS].shape != current[PULSE_NEG].shape:
        raise ValueError("pulse current grids do not match")
    cjm = (current[PULSE_POS] - current[PULSE_NEG]) / (
        2.0 * pulse_amplitude
    )
    equilibrium_current = current.get(EQUILIBRIUM)
    even_current = 0.5 * (current[PULSE_POS] + current[PULSE_NEG])
    if equilibrium_current is not None:
        if equilibrium_current.shape != even_current.shape:
            raise ValueError("equilibrium and pulse current grids do not match")
        even_current = even_current - equilibrium_current

    masks = {
        "train": (common_t >= 50.0) & (common_t <= 150.0),
        "validation": (common_t > 150.0) & (common_t <= 200.0),
        "blind": (common_t > 200.0) & (common_t <= 400.0),
    }
    return JointObservablePanel(
        t=common_t,
        x=np.asarray(first.x)[spatial_mask],
        profile=profile,
        current=current,
        response_cmm={"pulse_pair": cmm},
        response_cjm={"pulse_pair": cjm},
        response_even={
            "magnetization": even_m,
            "current": even_current,
        },
        fcs_gamma=fcs_gamma,
        fcs_logz=fcs_logz,
        masks=masks,
        diagnostics={
            "pulse_spin_flip_magnetization_max_abs": float(
                np.max(np.abs(aligned_m[PULSE_POS] + aligned_m[PULSE_NEG]))
            ),
            "pulse_even_magnetization_max_abs": float(np.max(np.abs(even_m))),
            "pulse_even_current_max_abs": float(np.max(np.abs(even_current))),
        },
        metadata={
            condition_id: dict(dataset.metadata)
            for condition_id, dataset in ordered.items()
        },
        simulation_x=np.asarray(first.x).copy(),
        profile_mask=np.asarray(spatial_mask, dtype=bool),
        current_masks=current_masks,
        physical_initial=physical_initial,
        czz=czz,
    )
