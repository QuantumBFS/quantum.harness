from __future__ import annotations

from src.transport_study import (
    DELTA0_VALUES,
    OFFSET_CENTERS,
    PATH_U_VALUES,
    TransportCase,
    select_refinement_cases,
    static_cases,
    realtime_cases,
)


def test_transport_manifest_is_complete_unique_and_reuses_center_reference():
    static = static_cases()
    realtime = realtime_cases()

    assert DELTA0_VALUES == (0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0)
    assert OFFSET_CENTERS == (1.5, 2.85, 3.6)
    assert len(static) == 9 * 41 + 3 * len(PATH_U_VALUES) == 393
    assert len(realtime) == 3 * len(static) == 1179
    assert len({case.key for case in static}) == len(static)
    assert len({case.key for case in realtime}) == len(realtime)
    assert all(
        not (case.family == "amplitude" and case.Delta0 == 3.0)
        for case in static
    )


def test_transport_case_round_trips_a_strict_json_record():
    case = TransportCase(
        index=17,
        family="offset",
        label="Delta-center-1.5",
        U=6.0,
        t=1.0,
        delta0=0.9,
        Delta0=3.0,
        delta_center=0.0,
        Delta_center=1.5,
    )

    assert TransportCase.from_dict(case.as_dict()) == case
    assert "offset" in case.key
    assert "Dc_p1d500" in case.key


def test_refinement_selection_tracks_transitions_within_each_path_only():
    cases = (
        TransportCase(0, "amplitude", "Delta0=1", 0, 1, 0.9, 1, 0, 0),
        TransportCase(1, "amplitude", "Delta0=1", 1, 1, 0.9, 1, 0, 0),
        TransportCase(2, "amplitude", "Delta0=2", 0, 1, 0.9, 2, 0, 0),
        TransportCase(3, "amplitude", "Delta0=2", 1, 1, 0.9, 2, 0, 0),
    )
    summaries = {
        0: {"C_MB_integer": 2, "Delta_min": 1, "minimum_link_overlap": 1, "maximum_abs_berry_flux": 0.1},
        1: {"C_MB_integer": 0, "Delta_min": 1, "minimum_link_overlap": 1, "maximum_abs_berry_flux": 0.1},
        2: {"C_MB_integer": 2, "Delta_min": 1, "minimum_link_overlap": 1, "maximum_abs_berry_flux": 0.1},
        3: {"C_MB_integer": 2, "Delta_min": 0.2, "minimum_link_overlap": 1, "maximum_abs_berry_flux": 0.1},
    }

    selected = select_refinement_cases(cases, summaries)

    assert [case.index for case in selected] == [0, 1, 3]
