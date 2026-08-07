"""Load and validate circuit-derived rotated-code geometry records."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


INSTANCE_SCHEMA = "q66-surface-code-instance-v1"


class GeometryError(ValueError):
    """Raised when an exported geometry record is inconsistent."""


@dataclass(frozen=True)
class Site:
    site_id: int
    stim_qubit: int
    role: str
    coord: tuple[float, ...]


@dataclass(frozen=True)
class Check:
    check_id: int
    ancilla_site_id: int
    pauli: str
    support: tuple[int, ...]


@dataclass(frozen=True)
class DataEdge:
    site_id: int
    endpoints: tuple[int, ...]
    logical: int


@dataclass(frozen=True)
class Geometry:
    instance_id: str
    distance: int
    rounds: int
    basis: str
    sites: tuple[Site, ...]
    checks: tuple[Check, ...]
    logical_support: frozenset[int]
    provenance: dict[str, Any]

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> Geometry:
        if record.get("schema_version") != INSTANCE_SCHEMA:
            raise GeometryError(f"unsupported geometry schema {record.get('schema_version')!r}")
        sites = tuple(
            Site(
                site_id=int(site["site_id"]),
                stim_qubit=int(site["stim_qubit"]),
                role=str(site["role"]),
                coord=tuple(float(value) for value in site["coord"]),
            )
            for site in record["sites"]
        )
        site_ids = tuple(site.site_id for site in sites)
        if site_ids != tuple(range(len(sites))):
            raise GeometryError("site IDs must be contiguous and sorted")
        if any(site.role not in {"data", "ancilla"} for site in sites):
            raise GeometryError("site role must be data or ancilla")
        checks = tuple(
            Check(
                check_id=int(check["check_id"]),
                ancilla_site_id=int(check["ancilla_site_id"]),
                pauli=str(check["pauli"]),
                support=tuple(int(site_id) for site_id in check["support"]),
            )
            for check in record["checks"]
        )
        if tuple(check.check_id for check in checks) != tuple(range(len(checks))):
            raise GeometryError("check IDs must be contiguous and sorted")
        data_ids = {site.site_id for site in sites if site.role == "data"}
        ancilla_ids = {site.site_id for site in sites if site.role == "ancilla"}
        for check in checks:
            if check.pauli not in {"X", "Z"}:
                raise GeometryError(f"invalid check Pauli {check.pauli!r}")
            if check.ancilla_site_id not in ancilla_ids:
                raise GeometryError("check ancilla does not name an ancilla site")
            if len(check.support) not in {2, 4} or not set(check.support) <= data_ids:
                raise GeometryError("check support is not a valid data-site support")
        logical_support = frozenset(int(value) for value in record["logical_support"])
        if not logical_support <= data_ids:
            raise GeometryError("logical support contains a non-data site")
        result = cls(
            instance_id=str(record["instance_id"]),
            distance=int(record["distance"]),
            rounds=int(record["rounds"]),
            basis=str(record["basis"]),
            sites=sites,
            checks=checks,
            logical_support=logical_support,
            provenance=dict(record["provenance"]),
        )
        result.data_edges()
        return result

    @classmethod
    def load(
        cls, path: Path, *, distance: int, rounds: int, basis: str
    ) -> Geometry:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            record = json.loads(line)
            if (
                record.get("distance") == distance
                and record.get("rounds") == rounds
                and record.get("basis") == basis
            ):
                return cls.from_record(record)
        raise GeometryError(f"missing geometry d={distance}, T={rounds}, basis={basis}")

    @property
    def n_sites(self) -> int:
        return len(self.sites)

    @property
    def data_site_ids(self) -> tuple[int, ...]:
        return tuple(site.site_id for site in self.sites if site.role == "data")

    @property
    def relevant_checks(self) -> tuple[Check, ...]:
        return tuple(check for check in self.checks if check.pauli == self.basis)

    @property
    def relevant_ancilla_site_ids(self) -> tuple[int, ...]:
        return tuple(check.ancilla_site_id for check in self.relevant_checks)

    def data_edges(self) -> tuple[DataEdge, ...]:
        relevant = self.relevant_checks
        check_positions = {check.check_id: index for index, check in enumerate(relevant)}
        incident: dict[int, list[int]] = {site_id: [] for site_id in self.data_site_ids}
        for check in relevant:
            for site_id in check.support:
                incident[site_id].append(check_positions[check.check_id])
        edges = []
        for site_id in self.data_site_ids:
            endpoints = tuple(sorted(incident[site_id]))
            if len(endpoints) not in {1, 2}:
                raise GeometryError(
                    f"data site {site_id} has relevant-check degree {len(endpoints)}"
                )
            edges.append(
                DataEdge(
                    site_id=site_id,
                    endpoints=endpoints,
                    logical=int(site_id in self.logical_support),
                )
            )
        return tuple(edges)
