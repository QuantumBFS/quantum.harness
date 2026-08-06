"""Deterministic manifests for the L=8 transport-visualization study."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .batch import PERIODS, U_VALUES


DELTA0_VALUES = (0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0)
OFFSET_CENTERS = (1.5, 2.85, 3.6)
PATH_U_VALUES = (-8.0, 0.0, 6.0, 7.0, 7.25, 7.5, 8.0, 16.0)


def _token(value: float) -> str:
    return (
        f"{float(value):+.3f}"
        .replace("+", "p")
        .replace("-", "neg")
        .replace(".", "d")
    )


@dataclass(frozen=True)
class TransportCase:
    index: int
    family: str
    label: str
    U: float
    t: float
    delta0: float
    Delta0: float
    delta_center: float
    Delta_center: float

    @property
    def key(self) -> str:
        return (
            f"{self.index:04d}_{self.family}_U_{_token(self.U)}_"
            f"D0_{_token(self.Delta0)}_dc_{_token(self.delta_center)}_"
            f"Dc_{_token(self.Delta_center)}"
        )

    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, record: dict) -> "TransportCase":
        if set(record) != set(cls.__dataclass_fields__):
            raise ValueError("transport case record has unexpected fields")
        return cls(**record)


@dataclass(frozen=True)
class TransportRealtimeCase:
    index: int
    static_case: TransportCase
    period: float

    @property
    def key(self) -> str:
        return f"{self.static_case.key}_T_{_token(self.period)}"

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "static_case": self.static_case.as_dict(),
            "period": self.period,
        }

    @classmethod
    def from_dict(cls, record: dict) -> "TransportRealtimeCase":
        if set(record) != {"index", "static_case", "period"}:
            raise ValueError("real-time transport record has unexpected fields")
        return cls(
            index=int(record["index"]),
            static_case=TransportCase.from_dict(record["static_case"]),
            period=float(record["period"]),
        )


def static_cases() -> tuple[TransportCase, ...]:
    records: list[dict] = []
    for Delta0 in DELTA0_VALUES:
        if Delta0 == 3.0:
            continue
        for U in U_VALUES:
            records.append(
                dict(
                    family="amplitude",
                    label=f"Delta0={Delta0:g}",
                    U=U,
                    t=1.0,
                    delta0=0.9,
                    Delta0=Delta0,
                    delta_center=0.0,
                    Delta_center=0.0,
                )
            )
    for center in OFFSET_CENTERS:
        for U in PATH_U_VALUES:
            records.append(
                dict(
                    family="offset",
                    label=f"Delta-center={center:g}",
                    U=U,
                    t=1.0,
                    delta0=0.9,
                    Delta0=3.0,
                    delta_center=0.0,
                    Delta_center=center,
                )
            )
    return tuple(
        TransportCase(index=index, **record)
        for index, record in enumerate(records)
    )


def realtime_cases() -> tuple[TransportRealtimeCase, ...]:
    return tuple(
        TransportRealtimeCase(index=index, static_case=case, period=period)
        for index, (case, period) in enumerate(
            (case, period) for case in static_cases() for period in PERIODS
        )
    )


def select_refinement_cases(
    cases: tuple[TransportCase, ...],
    summaries: dict[int, dict],
    *,
    gap_threshold: float = 0.35,
    overlap_threshold: float = 0.35,
    flux_threshold: float = 0.75,
) -> tuple[TransportCase, ...]:
    """Select hard points and both sides of Chern jumps within each path."""
    selected = {
        case.index
        for case in cases
        if float(summaries[case.index]["Delta_min"]) < gap_threshold
        or float(summaries[case.index]["minimum_link_overlap"]) < overlap_threshold
        or float(summaries[case.index]["maximum_abs_berry_flux"]) > flux_threshold
    }
    groups: dict[tuple, list[TransportCase]] = {}
    for case in cases:
        path = (
            case.family,
            case.delta0,
            case.Delta0,
            case.delta_center,
            case.Delta_center,
        )
        groups.setdefault(path, []).append(case)
    for group in groups.values():
        ordered = sorted(group, key=lambda case: case.U)
        for first, second in zip(ordered, ordered[1:]):
            if int(summaries[first.index]["C_MB_integer"]) != int(
                summaries[second.index]["C_MB_integer"]
            ):
                selected.update((first.index, second.index))
    return tuple(case for case in cases if case.index in selected)
