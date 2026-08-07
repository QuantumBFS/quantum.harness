"""Strict import of measured or published calibration data."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import numpy as np

from .observation import FluorescenceMixtureCalibration
from .stochastic import OneSidedCrossSpectralDensity


@dataclass(frozen=True)
class DataProvenance:
    """Human- and machine-auditable origin of an imported dataset."""

    source_id: str
    source_url: str
    source_version: str
    data_kind: str
    raw_data_available: bool
    content_sha256: str

    def __post_init__(self) -> None:
        if (
            not self.source_id
            or not self.source_url
            or not self.source_version
            or not self.data_kind
            or len(self.content_sha256) != 64
        ):
            raise ValueError("data provenance is incomplete")


@dataclass(frozen=True)
class MeasuredTable:
    """Numeric measured table with explicit per-column units."""

    columns: Mapping[str, tuple[float, ...]]
    units: Mapping[str, str]
    provenance: DataProvenance

    def __post_init__(self) -> None:
        columns = {key: tuple(values) for key, values in self.columns.items()}
        if (
            not columns
            or len({len(values) for values in columns.values()}) != 1
            or any(not values for values in columns.values())
            or any(
                not np.all(np.isfinite(values)) for values in columns.values()
            )
            or set(columns) != set(self.units)
            or any(not unit for unit in self.units.values())
        ):
            raise ValueError("measured table columns/units are invalid")
        object.__setattr__(self, "columns", MappingProxyType(columns))
        object.__setattr__(
            self, "units", MappingProxyType(dict(self.units))
        )

    @property
    def row_count(self) -> int:
        return len(next(iter(self.columns.values())))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_hash(path: Path, expected_sha256: str | None) -> str:
    observed = _sha256(path)
    if expected_sha256 is not None and observed.lower() != expected_sha256.lower():
        raise ValueError(
            f"SHA-256 mismatch for {path.name}: "
            f"expected {expected_sha256}, observed {observed}"
        )
    return observed


def load_published_fluorescence_calibration(
    path: str | Path, *, expected_sha256: str | None = None
) -> tuple[FluorescenceMixtureCalibration, DataProvenance, Mapping[str, float]]:
    """Load a published fit summary, explicitly not an unpublished raw dataset."""

    source = Path(path)
    content_hash = _verify_hash(source, expected_sha256)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema") != "cs_tweezer_sim.fluorescence_fit.v1":
        raise ValueError("unsupported fluorescence calibration schema")
    provenance_raw = payload.get("provenance", {})
    fit = payload.get("fit", {})
    reported = payload.get("reported", {})
    required_fit = {
        "dark_fraction",
        "dark_location_photoelectrons",
        "dark_scale_photoelectrons",
        "dark_shape_k",
        "bright_location_photoelectrons",
        "bright_scale_photoelectrons",
        "bright_shape_a",
        "threshold_photoelectrons",
    }
    if set(fit) != required_fit:
        raise ValueError("fluorescence fit fields do not match schema")
    provenance = DataProvenance(
        source_id=str(provenance_raw["source_id"]),
        source_url=str(provenance_raw["source_url"]),
        source_version=str(provenance_raw["source_version"]),
        data_kind=str(provenance_raw["data_kind"]),
        raw_data_available=bool(provenance_raw["raw_data_available"]),
        content_sha256=content_hash,
    )
    calibration = FluorescenceMixtureCalibration(
        **{key: float(value) for key, value in fit.items()},
        bright_readout_loss_probability=float(
            reported["bright_readout_loss_probability"]
        ),
        dark_readout_loss_probability=float(
            reported["dark_readout_loss_probability"]
        ),
        source_id=provenance.source_id,
        source_url=provenance.source_url,
        source_version=provenance.source_version,
    )
    return (
        calibration,
        provenance,
        MappingProxyType(
            {key: float(value) for key, value in reported.items()}
        ),
    )


def load_measured_table_csv(
    csv_path: str | Path, metadata_path: str | Path
) -> MeasuredTable:
    """Load a numeric CSV against a strict JSON units/provenance sidecar."""

    data_path = Path(csv_path)
    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    if metadata.get("schema") != "cs_tweezer_sim.measured_table.v1":
        raise ValueError("unsupported measured-table schema")
    observed_hash = _verify_hash(data_path, str(metadata["sha256"]))
    with data_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        rows = tuple(reader)
    units = metadata.get("units", {})
    if not fieldnames or set(fieldnames) != set(units):
        raise ValueError("CSV columns and metadata units do not match")
    columns = {}
    for field in fieldnames:
        try:
            columns[field] = tuple(float(row[field]) for row in rows)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"column {field} is not strictly numeric") from exc
    source = metadata.get("provenance", {})
    provenance = DataProvenance(
        source_id=str(source["source_id"]),
        source_url=str(source["source_url"]),
        source_version=str(source["source_version"]),
        data_kind=str(source["data_kind"]),
        raw_data_available=bool(source["raw_data_available"]),
        content_sha256=observed_hash,
    )
    return MeasuredTable(columns, units, provenance)


def load_one_sided_csd_csv(
    csv_path: str | Path, metadata_path: str | Path
) -> OneSidedCrossSpectralDensity:
    """Build the S4-B CSD contract from a strict measured-table CSV.

    Complex matrix columns use ``S_<row>_<column>_real`` and
    ``S_<row>_<column>_imag``. Channel names therefore may not contain
    underscores in this versioned schema.
    """

    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    channels = tuple(str(value) for value in metadata.get("channels", ()))
    if not channels or any("_" in channel for channel in channels):
        raise ValueError("CSD metadata requires underscore-free channels")
    table = load_measured_table_csv(csv_path, metadata_path)
    if table.units.get("frequency_hz") != "Hz":
        raise ValueError("frequency_hz must use Hz")
    matrices = []
    for row_index in range(table.row_count):
        matrix = []
        for first in channels:
            entries = []
            for second in channels:
                real_key = f"S_{first}_{second}_real"
                imag_key = f"S_{first}_{second}_imag"
                if (
                    table.units.get(real_key) != "Hz^2/Hz"
                    or table.units.get(imag_key) != "Hz^2/Hz"
                ):
                    raise ValueError("CSD columns must use Hz^2/Hz")
                entries.append(
                    complex(
                        table.columns[real_key][row_index],
                        table.columns[imag_key][row_index],
                    )
                )
            matrix.append(tuple(entries))
        matrices.append(tuple(matrix))
    return OneSidedCrossSpectralDensity(
        channels,
        table.columns["frequency_hz"],
        tuple(matrices),
    )
