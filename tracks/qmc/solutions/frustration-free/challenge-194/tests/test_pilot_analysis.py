from __future__ import annotations

import hashlib
import json
import multiprocessing
import shutil
import weakref
from dataclasses import FrozenInstanceError
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import long_range_percolation.pilot_analysis as analysis
import long_range_percolation.pilot_extension as extension
from long_range_percolation import pilot
from long_range_percolation.pilot import PilotCell
from long_range_percolation.pilot_extension import EXTENSION_ANALYSIS_SCHEMA
from long_range_percolation.trajectory import TrajectoryResult

OBSERVABLE_COLUMNS = {
    "s1_fraction": 4,
    "s2_fraction": 5,
    "q_g": 8,
    "four_sector_crossing": 9,
}


def _canonical_bytes(document: object) -> bytes:
    return (
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _sign(document: dict[str, object]) -> None:
    unsigned = dict(document)
    unsigned.pop("analysis_document_sha256", None)
    document["analysis_document_sha256"] = hashlib.sha256(
        _canonical_bytes(unsigned)
    ).hexdigest()


def _extension_grid(lower: float, upper: float) -> tuple[float, ...]:
    points = [lower, upper]
    for _ in range(4):
        ordered = sorted(points)
        points.extend(left + (right - left) / 2.0 for left, right in pairwise(ordered))
    return tuple(sorted(set(points)))


def _combined_source_documents() -> tuple[
    dict[str, object],
    dict[str, object],
    dict[tuple[str, float, int, float, str], np.ndarray],
]:
    sigmas = (0.8, 0.9, 1.0, 1.1)
    lengths = pilot.PILOT_LENGTHS
    p0_kappas = pilot.PILOT_KAPPAS
    extension_grids = {
        0.9: _extension_grid(p0_kappas[4], p0_kappas[8]),
        1.0: _extension_grid(p0_kappas[5], p0_kappas[10]),
    }
    samples: dict[tuple[str, float, int, float, str], np.ndarray] = {}

    def estimates(
        source: str,
        source_sigmas: tuple[float, ...],
        grids: dict[float, tuple[float, ...]],
        replicas: int,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for sigma_index, sigma in enumerate(source_sigmas):
            for length_index, length in enumerate(lengths):
                requests = [
                    hashlib.sha256(
                        f"{source}|{sigma.hex()}|{length}|{replica}".encode()
                    ).hexdigest()
                    for replica in range(replicas)
                ]
                for kappa_index, kappa in enumerate(grids[sigma]):
                    means: dict[str, float] = {}
                    standard_errors: dict[str, float] = {}
                    for observable_index, name in enumerate(OBSERVABLE_COLUMNS):
                        values = np.asarray(
                            [
                                1000.0 * sigma_index
                                + 100.0 * length_index
                                + 10.0 * kappa_index
                                + observable_index
                                + (50.0 if source == "extension" else 0.0)
                                + replica * (observable_index + 1) / 8.0
                                for replica in range(replicas)
                            ],
                            dtype=np.float64,
                        )
                        samples[(source, sigma, length, kappa, name)] = values
                        means[name] = float(np.mean(values))
                        standard_errors[name] = float(
                            np.std(values, ddof=1) / np.sqrt(replicas)
                        )
                    rows.append(
                        {
                            "sigma_hex": sigma.hex(),
                            "length": length,
                            "kappa_hex": kappa.hex(),
                            "replica_count": replicas,
                            "means": means,
                            "standard_errors": standard_errors,
                            "request_sha256": requests,
                        }
                    )
        return rows

    p0: dict[str, object] = {
        "schema_version": analysis.ANALYSIS_SCHEMA,
        "p0_run_spec_sha256": "1" * 64,
        "p0_progress_sha256": "2" * 64,
        "source_revision": "3" * 40,
        "analysis_plan_sha256": "4" * 64,
        "observable_columns": OBSERVABLE_COLUMNS,
        "estimates": estimates(
            "p0",
            sigmas,
            {sigma: p0_kappas for sigma in sigmas},
            8,
        ),
    }
    extension_analysis: dict[str, object] = {
        "schema_version": EXTENSION_ANALYSIS_SCHEMA,
        "source_extension_protocol_sha256": "5" * 64,
        "extension_run_spec_sha256": "6" * 64,
        "extension_progress_sha256": "7" * 64,
        "source_revision": "8" * 40,
        "analysis_plan_sha256": "9" * 64,
        "observable_columns": OBSERVABLE_COLUMNS,
        "estimates": estimates(
            "extension",
            (0.9, 1.0),
            extension_grids,
            16,
        ),
    }
    _sign(p0)
    _sign(extension_analysis)
    return p0, extension_analysis, samples


def test_combine_p0_evidence_unions_grids_and_pools_whole_replica_moments():
    p0, extension_analysis, samples = _combined_source_documents()

    combined = extension._build_combined_p0_evidence(p0, extension_analysis)

    entries = combined["sigma_entries"]
    assert [entry["sigma_hex"] for entry in entries] == [
        sigma.hex() for sigma in (0.8, 0.9, 1.0, 1.1)
    ]
    assert [len(entry["kappas"]) for entry in entries] == [16, 31, 31, 16]
    assert all(entry["lengths"] == list(pilot.PILOT_LENGTHS) for entry in entries)
    assert [len(entry["estimates"]) for entry in entries] == [48, 93, 93, 48]
    assert combined["estimate_count"] == 282

    p0_rows = p0["estimates"]
    assert entries[0]["estimates"] == p0_rows[:48]
    assert entries[3]["estimates"] == p0_rows[-48:]
    blocked = entries[1]
    shared = set(pilot.PILOT_KAPPAS) & {
        float.fromhex(value) for value in blocked["kappas"]
    }
    assert len(shared) == 16
    extension_grid = {
        float.fromhex(row["kappa_hex"])
        for row in extension_analysis["estimates"]
        if row["sigma_hex"] == (0.9).hex()
    }
    assert len(shared & extension_grid) == 2
    replica_counts = {
        row["replica_count"] for entry in entries for row in entry["estimates"]
    }
    assert replica_counts == {8, 16, 24}

    endpoint = min(shared & extension_grid)
    pooled = next(
        row
        for row in blocked["estimates"]
        if row["length"] == pilot.PILOT_LENGTHS[0]
        and row["kappa_hex"] == endpoint.hex()
    )
    for name in OBSERVABLE_COLUMNS:
        direct = np.concatenate(
            (
                samples[("p0", 0.9, pilot.PILOT_LENGTHS[0], endpoint, name)],
                samples[("extension", 0.9, pilot.PILOT_LENGTHS[0], endpoint, name)],
            )
        )
        assert pooled["means"][name] == pytest.approx(float(np.mean(direct)))
        assert pooled["standard_errors"][name] == pytest.approx(
            float(np.std(direct, ddof=1) / np.sqrt(24))
        )
    assert pooled["request_sha256"] == (
        next(
            row["request_sha256"]
            for row in p0_rows
            if row["sigma_hex"] == (0.9).hex()
            and row["length"] == pilot.PILOT_LENGTHS[0]
        )
        + next(
            row["request_sha256"]
            for row in extension_analysis["estimates"]
            if row["sigma_hex"] == (0.9).hex()
            and row["length"] == pilot.PILOT_LENGTHS[0]
        )
    )
    assert len(set(pooled["request_sha256"])) == 24


def test_combine_p0_evidence_binds_sources_and_hashes_unsigned_document():
    p0, extension_analysis, _ = _combined_source_documents()

    combined = extension._build_combined_p0_evidence(p0, extension_analysis)
    unsigned = dict(combined)
    digest = unsigned.pop("analysis_document_sha256")

    assert combined["schema_version"] == extension.COMBINED_ANALYSIS_SCHEMA
    assert (
        combined["source_p0_analysis_document_sha256"] == p0["analysis_document_sha256"]
    )
    assert (
        combined["source_extension_analysis_document_sha256"]
        == (extension_analysis["analysis_document_sha256"])
    )
    assert combined["p0_run_spec_sha256"] == p0["p0_run_spec_sha256"]
    assert combined["p0_progress_sha256"] == p0["p0_progress_sha256"]
    assert (
        combined["extension_run_spec_sha256"]
        == extension_analysis["extension_run_spec_sha256"]
    )
    assert (
        combined["extension_progress_sha256"]
        == extension_analysis["extension_progress_sha256"]
    )
    assert combined["p0_source_revision"] == p0["source_revision"]
    assert (
        combined["extension_source_revision"] == extension_analysis["source_revision"]
    )
    assert combined["observable_columns"] == OBSERVABLE_COLUMNS
    assert digest == hashlib.sha256(_canonical_bytes(unsigned)).hexdigest()


@pytest.mark.parametrize(
    "operation",
    ("combine", "select", "build-p1"),
)
def test_combined_v2_has_no_self_signed_source_only_path(operation: str):
    p0, extension_analysis, _ = _combined_source_documents()
    combined = extension._build_combined_p0_evidence(p0, extension_analysis)

    with pytest.raises(TypeError):
        if operation == "combine":
            extension.combine_p0_evidence(p0, extension_analysis)
        elif operation == "select":
            analysis.select_p1_brackets(
                combined,
                p0_analysis=p0,
                extension_analysis=extension_analysis,
            )
        else:
            brackets = analysis._select_p1_brackets_from_evidence(
                combined,
                analysis._selector_v2_evidence(combined),
            )
            analysis.build_p1_protocol(
                combined,
                brackets,
                p0_analysis=p0,
                extension_analysis=extension_analysis,
            )


def test_real_authenticated_artifacts_remain_unresolved_and_p1_absent():
    results = Path(__file__).resolve().parents[6] / "results/challenge-194"
    p0 = json.loads((results / "p0_analysis.json").read_bytes())
    extension_analysis = json.loads(
        (results / "p0_extension_v1_analysis.json").read_bytes()
    )
    protocol = json.loads((results / "p0_extension_v1_protocol.json").read_bytes())
    p0_root = (results / "pilot-p0-739880d").resolve()
    extension_run_spec = (results / "pilot-p0-extension-v1/run_spec.json").resolve()

    combined = extension.combine_p0_evidence(
        p0,
        extension_analysis,
        p0_evidence_root=p0_root,
        extension_run_spec=extension_run_spec,
        extension_protocol=protocol,
    )
    assert (
        _canonical_bytes(combined)
        == (results / "p0_combined_analysis_v2.json").read_bytes()
    )
    brackets = analysis.select_p1_brackets(
        combined,
        p0_analysis=p0,
        extension_analysis=extension_analysis,
        p0_evidence_root=p0_root,
        extension_run_spec=extension_run_spec,
        extension_protocol=protocol,
    )
    assert (
        _canonical_bytes(brackets)
        == (results / "p0_combined_brackets_v2.json").read_bytes()
    )
    assert brackets["requires_p0_extension"] is True
    assert not (results / "p1_protocol.json").exists()
    with pytest.raises(RuntimeError, match="P0 extension required"):
        analysis.build_p1_protocol(
            combined,
            brackets,
            p0_analysis=p0,
            extension_analysis=extension_analysis,
            p0_evidence_root=p0_root,
            extension_run_spec=extension_run_spec,
            extension_protocol=protocol,
        )


@pytest.mark.parametrize("operation", ("combine", "select", "build-p1"))
def test_fully_synthetic_resigned_282_row_sources_fail_with_real_trust_inputs(
    operation: str,
):
    results = Path(__file__).resolve().parents[6] / "results/challenge-194"
    p0, extension_analysis, _ = _combined_source_documents()
    combined = extension._build_combined_p0_evidence(p0, extension_analysis)
    protocol = json.loads((results / "p0_extension_v1_protocol.json").read_bytes())
    trusted = {
        "p0_evidence_root": (results / "pilot-p0-739880d").resolve(),
        "extension_run_spec": (
            results / "pilot-p0-extension-v1/run_spec.json"
        ).resolve(),
        "extension_protocol": protocol,
    }

    with pytest.raises(RuntimeError, match="P0 source hashes or revision"):
        if operation == "combine":
            extension.combine_p0_evidence(
                p0,
                extension_analysis,
                **trusted,
            )
        elif operation == "select":
            analysis.select_p1_brackets(
                combined,
                p0_analysis=p0,
                extension_analysis=extension_analysis,
                **trusted,
            )
        else:
            brackets = analysis._select_p1_brackets_from_evidence(
                combined,
                analysis._selector_v2_evidence(combined),
            )
            analysis.build_p1_protocol(
                combined,
                brackets,
                p0_analysis=p0,
                extension_analysis=extension_analysis,
                **trusted,
            )


def test_authenticated_combination_rejects_modified_extension_means():
    results = Path(__file__).resolve().parents[6] / "results/challenge-194"
    p0 = json.loads((results / "p0_analysis.json").read_bytes())
    extension_analysis = json.loads(
        (results / "p0_extension_v1_analysis.json").read_bytes()
    )
    extension_analysis["estimates"][0]["means"]["q_g"] += 0.125
    _sign(extension_analysis)
    protocol = json.loads((results / "p0_extension_v1_protocol.json").read_bytes())

    with pytest.raises(RuntimeError, match="authenticated recomputation"):
        extension.combine_p0_evidence(
            p0,
            extension_analysis,
            p0_evidence_root=(results / "pilot-p0-739880d").resolve(),
            extension_run_spec=(
                results / "pilot-p0-extension-v1/run_spec.json"
            ).resolve(),
            extension_protocol=protocol,
        )


@pytest.mark.parametrize("swap", ("p0-root", "extension-run-spec", "protocol"))
def test_authenticated_combination_rejects_root_and_protocol_swaps(
    tmp_path: Path,
    swap: str,
):
    results = Path(__file__).resolve().parents[6] / "results/challenge-194"
    p0 = json.loads((results / "p0_analysis.json").read_bytes())
    extension_analysis = json.loads(
        (results / "p0_extension_v1_analysis.json").read_bytes()
    )
    protocol = json.loads((results / "p0_extension_v1_protocol.json").read_bytes())
    p0_root = (results / "pilot-p0-739880d").resolve()
    extension_run_spec = (results / "pilot-p0-extension-v1/run_spec.json").resolve()
    if swap == "p0-root":
        replacement = tmp_path / "p0-root"
        replacement.mkdir()
        shutil.copyfile(p0_root / "run_spec.json", replacement / "run_spec.json")
        shutil.copyfile(p0_root / "progress.json", replacement / "progress.json")
        p0_root = replacement.resolve()
    elif swap == "extension-run-spec":
        replacement = tmp_path / "extension-root"
        replacement.mkdir()
        (replacement / "run_spec.json").write_bytes(extension_run_spec.read_bytes())
        (replacement / "progress.json").write_bytes(
            (extension_run_spec.parent / "progress.json").read_bytes()
        )
        extension_run_spec = (replacement / "run_spec.json").resolve()
    else:
        protocol["purpose"] = "forged"
        unsigned = dict(protocol)
        unsigned.pop("protocol_sha256")
        protocol["protocol_sha256"] = hashlib.sha256(
            _canonical_bytes(unsigned)
        ).hexdigest()

    with pytest.raises(RuntimeError):
        extension.combine_p0_evidence(
            p0,
            extension_analysis,
            p0_evidence_root=p0_root,
            extension_run_spec=extension_run_spec,
            extension_protocol=protocol,
        )


@pytest.mark.parametrize(
    ("defect", "match"),
    (
        ("source-hash", "digest"),
        ("wrong-grid", "grid"),
        ("extra-overlap", "grid|overlap"),
        ("duplicate-request", "request"),
        ("missing-length", "cardinality|canonical"),
        ("missing-replica", "replica"),
        ("reordered", "canonical"),
        ("noncanonical-hex", "canonical"),
        ("nonfinite", "finite"),
        ("observable-columns", "observable"),
        ("different-shape", "canonical|cardinality|shape"),
    ),
)
def test_combine_p0_evidence_rejects_adversarial_sources(defect: str, match: str):
    p0, extension_analysis, _ = _combined_source_documents()
    target = extension_analysis
    estimates = target["estimates"]
    assert isinstance(estimates, list)
    if defect == "source-hash":
        target["analysis_document_sha256"] = "0" * 64
    elif defect == "wrong-grid":
        estimates[1]["kappa_hex"] = float.fromhex(estimates[1]["kappa_hex"]).hex()
        estimates[1]["kappa_hex"] = (
            float.fromhex(estimates[1]["kappa_hex"]) + 1e-6
        ).hex()
        _sign(target)
    elif defect == "extra-overlap":
        estimates[1]["kappa_hex"] = pilot.PILOT_KAPPAS[1].hex()
        _sign(target)
    elif defect == "duplicate-request":
        estimates[0]["request_sha256"][1] = estimates[0]["request_sha256"][0]
        _sign(target)
    elif defect == "missing-length":
        del estimates[17:34]
        _sign(target)
    elif defect == "missing-replica":
        estimates[0]["replica_count"] = 15
        estimates[0]["request_sha256"].pop()
        _sign(target)
    elif defect == "reordered":
        estimates[0], estimates[1] = estimates[1], estimates[0]
        _sign(target)
    elif defect == "noncanonical-hex":
        estimates[0]["kappa_hex"] = "0X1.F400000000000P-2"
        _sign(target)
    elif defect == "nonfinite":
        estimates[0]["means"]["q_g"] = float("inf")
    elif defect == "observable-columns":
        target["observable_columns"] = {**OBSERVABLE_COLUMNS, "q_g": 7}
        _sign(target)
    else:
        estimates[-1] = dict(estimates[0])
        _sign(target)

    with pytest.raises(RuntimeError, match=match):
        extension._build_combined_p0_evidence(p0, extension_analysis)


@pytest.mark.parametrize(
    "defect",
    ("source-binding", "reordered-sigma-entries", "rehashed-different-shape"),
)
def test_combined_p0_evidence_validation_rejects_internal_mutation(defect: str):
    p0, extension_analysis, _ = _combined_source_documents()
    combined = extension._build_combined_p0_evidence(p0, extension_analysis)
    if defect == "source-binding":
        combined["source_extension_analysis_document_sha256"] = "0" * 64
    elif defect == "reordered-sigma-entries":
        combined["sigma_entries"][0], combined["sigma_entries"][1] = (
            combined["sigma_entries"][1],
            combined["sigma_entries"][0],
        )
    else:
        combined["sigma_entries"][1]["estimates"].pop()
        assert combined["estimate_count"] == 282
    _sign(combined)

    with pytest.raises(RuntimeError, match="recomputation"):
        extension._validate_combined_p0_evidence(
            p0,
            extension_analysis,
            combined,
        )


@pytest.mark.parametrize("source_name", ("p0", "extension"))
@pytest.mark.parametrize(
    ("field", "malformed"),
    (
        ("length", 1024.0),
        ("length", True),
        ("length", np.int64(1024)),
        ("replica_count", 8.0),
        ("replica_count", True),
        ("replica_count", np.int64(8)),
        ("observable_columns", 4.0),
        ("observable_columns", True),
    ),
)
def test_combine_p0_evidence_requires_builtin_integer_source_fields(
    source_name: str,
    field: str,
    malformed: object,
):
    p0, extension_analysis, _ = _combined_source_documents()
    target = p0 if source_name == "p0" else extension_analysis
    rows = target["estimates"]
    assert isinstance(rows, list)
    if field == "observable_columns":
        target["observable_columns"] = {
            **OBSERVABLE_COLUMNS,
            "s1_fraction": malformed,
        }
    else:
        rows[0][field] = (
            16.0
            if source_name == "extension"
            and field == "replica_count"
            and malformed == 8.0
            else np.int64(16)
            if source_name == "extension"
            and field == "replica_count"
            and isinstance(malformed, np.integer)
            else malformed
        )
    if not isinstance(malformed, np.integer):
        _sign(target)

    with pytest.raises(RuntimeError, match="built-in integer"):
        extension._build_combined_p0_evidence(p0, extension_analysis)


@pytest.mark.parametrize(
    ("field", "malformed"),
    (
        ("estimate_count", 282.0),
        ("estimate_count", True),
        ("estimate_count", np.int64(282)),
        ("length_axis", 1024.0),
        ("length_axis", True),
        ("length_axis", np.int64(1024)),
        ("row_length", 1024.0),
        ("row_length", True),
        ("row_length", np.int64(1024)),
        ("replica_count", 8.0),
        ("replica_count", True),
        ("replica_count", np.int64(8)),
        ("observable_columns", 4.0),
        ("observable_columns", True),
        ("observable_columns", np.int64(4)),
    ),
)
def test_combined_p0_evidence_requires_builtin_integer_output_fields(
    field: str,
    malformed: object,
):
    p0, extension_analysis, _ = _combined_source_documents()
    combined = extension._build_combined_p0_evidence(p0, extension_analysis)
    if field == "estimate_count":
        combined["estimate_count"] = malformed
    elif field == "length_axis":
        combined["sigma_entries"][0]["lengths"][0] = malformed
    elif field == "row_length":
        combined["sigma_entries"][0]["estimates"][0]["length"] = malformed
    elif field == "replica_count":
        combined["sigma_entries"][0]["estimates"][0]["replica_count"] = malformed
    else:
        combined["observable_columns"]["s1_fraction"] = malformed
    if not isinstance(malformed, np.integer):
        _sign(combined)

    with pytest.raises(RuntimeError, match="built-in integer"):
        extension._validate_combined_p0_evidence(
            p0,
            extension_analysis,
            combined,
        )


def _selector_document(
    *,
    sigmas: tuple[float, ...] = (0.8, 1.1),
    lengths: tuple[int, ...] = (8, 16, 32),
    kappas: tuple[float, ...] = (0.0, 1.0, 2.0, 4.0),
    values: dict[
        tuple[float, int, float],
        tuple[float, float],
    ]
    | None = None,
) -> dict[str, object]:
    values = values or {}
    estimates: list[dict[str, object]] = []
    for sigma in sigmas:
        for length in lengths:
            for kappa in kappas:
                q_g, crossing = values.get(
                    (sigma, length, kappa),
                    (float(length) + kappa, 0.1 * kappa),
                )
                estimates.append(
                    {
                        "sigma_hex": sigma.hex(),
                        "length": length,
                        "kappa_hex": kappa.hex(),
                        "replica_count": 8,
                        "means": {
                            "s1_fraction": 0.1,
                            "s2_fraction": 0.05,
                            "q_g": q_g,
                            "four_sector_crossing": crossing,
                        },
                        "standard_errors": {name: 0.01 for name in OBSERVABLE_COLUMNS},
                        "request_sha256": [
                            str(replica) * 64 for replica in range(1, 9)
                        ],
                    }
                )
    document: dict[str, object] = {
        "schema_version": analysis.ANALYSIS_SCHEMA,
        "p0_run_spec_sha256": "a" * 64,
        "p0_progress_sha256": "b" * 64,
        "source_revision": "c" * 40,
        "analysis_plan_sha256": "d" * 64,
        "observable_columns": OBSERVABLE_COLUMNS,
        "estimates": estimates,
    }
    document["analysis_document_sha256"] = hashlib.sha256(
        _canonical_bytes(document)
    ).hexdigest()
    return document


def _set_selector_value(
    values: dict[tuple[float, int, float], tuple[float, float]],
    sigma: float,
    length: int,
    kappas: tuple[float, ...],
    q_g: tuple[float, ...],
    crossing: tuple[float, ...],
) -> None:
    for kappa, q_value, crossing_value in zip(kappas, q_g, crossing, strict=True):
        values[(sigma, length, kappa)] = (q_value, crossing_value)


def _configure_selector_rows(
    rows: list[dict[str, object]],
    sigma: float,
    lengths: tuple[int, ...],
    kappas: tuple[float, ...],
    selected_interval: int,
) -> None:
    for row in rows:
        if row["sigma_hex"] != sigma.hex():
            continue
        length = row["length"]
        kappa_index = kappas.index(float.fromhex(row["kappa_hex"]))
        means = row["means"]
        if sigma <= 1.0:
            means["q_g"] = (
                float(kappa_index <= selected_interval)
                if length == lengths[-2]
                else float(kappa_index > selected_interval)
                if length == lengths[-1]
                else 0.0
            )
            means["four_sector_crossing"] = (
                0.1 if kappa_index <= selected_interval else 0.9
            )
        else:
            means["q_g"] = 0.0
            means["four_sector_crossing"] = (
                0.1 if kappa_index <= selected_interval else 0.9
            )


def _combined_selector_document(
    *,
    unresolved_sigma: float | None = None,
    blocked_interval_offset: int = 0,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    p0, extension_analysis, _ = _combined_source_documents()
    p0_rows = p0["estimates"]
    extension_rows = extension_analysis["estimates"]
    assert isinstance(p0_rows, list)
    assert isinstance(extension_rows, list)
    for sigma, interval in ((0.8, 4), (1.1, 8)):
        _configure_selector_rows(
            p0_rows,
            sigma,
            tuple(pilot.PILOT_LENGTHS),
            tuple(pilot.PILOT_KAPPAS),
            interval,
        )

    for sigma, combined_interval in (
        (0.9, 9 + blocked_interval_offset),
        (1.0, 19 + blocked_interval_offset),
    ):
        if sigma == unresolved_sigma:
            continue
        extension_kappas = tuple(
            float.fromhex(row["kappa_hex"])
            for row in extension_rows
            if row["sigma_hex"] == sigma.hex()
            and row["length"] == pilot.PILOT_LENGTHS[0]
        )
        combined_kappas = tuple(sorted(set(pilot.PILOT_KAPPAS) | set(extension_kappas)))
        threshold = combined_kappas[combined_interval]
        for rows, kappas in (
            (p0_rows, tuple(pilot.PILOT_KAPPAS)),
            (extension_rows, extension_kappas),
        ):
            selected_interval = max(
                index for index, kappa in enumerate(kappas) if kappa <= threshold
            )
            _configure_selector_rows(
                rows,
                sigma,
                tuple(pilot.PILOT_LENGTHS),
                kappas,
                selected_interval,
            )
    _sign(p0)
    _sign(extension_analysis)
    combined = extension._build_combined_p0_evidence(p0, extension_analysis)
    return p0, extension_analysis, combined


def _select_test_combined(
    combined: dict[str, object],
    p0: dict[str, object],
    extension_analysis: dict[str, object],
) -> dict[str, object]:
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            extension,
            "_authenticate_combined_sources",
            lambda supplied_p0, supplied_extension, **_kwargs: (
                supplied_p0,
                supplied_extension,
            ),
        )
        return analysis.select_p1_brackets(
            combined,
            p0_analysis=p0,
            extension_analysis=extension_analysis,
            p0_evidence_root=Path("/test/p0"),
            extension_run_spec=Path("/test/extension/run_spec.json"),
            extension_protocol={},
        )


def _build_test_combined_p1(
    combined: dict[str, object],
    brackets: dict[str, object] | None,
    p0: dict[str, object],
    extension_analysis: dict[str, object],
) -> dict[str, object]:
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            extension,
            "_authenticate_combined_sources",
            lambda supplied_p0, supplied_extension, **_kwargs: (
                supplied_p0,
                supplied_extension,
            ),
        )
        return analysis.build_p1_protocol(
            combined,
            brackets,
            p0_analysis=p0,
            extension_analysis=extension_analysis,
            p0_evidence_root=Path("/test/p0"),
            extension_run_spec=Path("/test/extension/run_spec.json"),
            extension_protocol={},
        )


def _tiny_complete_pilot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    name: str = "pilot",
    value_offset: float = 0.0,
) -> tuple[Path, dict[str, object]]:
    path = pilot._write_test_pilot_run_spec(
        tmp_path / name,
        lengths=(8, 16),
        sigmas=(1.0,),
        replicas=(0, 1),
        kappas=(0.0, 0.25, 0.5),
    )

    def deterministic_trajectory(
        request: object, _kernel: np.ndarray, _alias: object
    ) -> TrajectoryResult:
        rows = np.zeros((3, 10), dtype=np.float64)
        for kappa_index in range(3):
            base = request.length / 8 + 2 * request.replica + kappa_index + value_offset
            rows[kappa_index, 4] = base
            rows[kappa_index, 5] = base + 10
            rows[kappa_index, 8] = base + 20
            rows[kappa_index, 9] = (request.replica + kappa_index) % 2
        return TrajectoryResult(
            request_sha256=pilot.request_digest(request),
            observables=rows,
            terminal_counters=np.zeros((4, 4), dtype=np.uint32),
            draw_counts=np.zeros((4, 3), dtype=np.uint64),
            event_count=0,
            duplicate_count=0,
            hash_diagnostics=np.zeros(5, dtype=np.uint64),
        )

    monkeypatch.setattr(pilot, "run_poisson_numba", deterministic_trajectory)
    spec = pilot._load_pilot_spec(
        path,
        verify_current_environment=False,
        expected_schema=pilot.TEST_RUN_SPEC_SCHEMA,
    )
    for cell_index in range(len(spec["cells"])):
        pilot._run_test_pilot_cell(path, cell_index)
    pilot._merge_test_pilot_progress(path)
    return path, spec


def _tiny_complete_p0_extension(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    name: str = "extension",
    value_offset: float = 0.0,
) -> tuple[Path, dict[str, object], dict[str, object]]:
    sigmas = (0.9, 1.0)
    lengths = (8, 16, 32)
    replicas = (24, 25)
    sigma_kappas = {
        0.9: (0.25, 0.5, 0.75),
        1.0: (1.0, 1.5, 2.0),
    }
    document = pilot._build_test_pilot_run_spec(
        tmp_path / name,
        lengths=lengths,
        sigmas=sigmas,
        replicas=replicas,
        kappas=sigma_kappas[0.9],
    )
    document["schema_version"] = pilot.TEST_EXTENSION_RUN_SPEC_SCHEMA
    assignments: list[dict[str, object]] = []
    cells: list[dict[str, object]] = []
    for raw in document["cells"]:
        cell = dict(raw)
        sigma = float.fromhex(cell["sigma"])
        kappas = sigma_kappas[sigma]
        cell["sigma_grid_id"] = f"pilot-p0-extension-test-v1|sigma-f64={sigma.hex()}"
        cell["kappas"] = [value.hex() for value in kappas]
        provisional = PilotCell.from_document(cell)
        request = provisional.request(
            master_seed=pilot.TEST_EXTENSION_CONTRACT.master_seed,
            phase=pilot.TEST_EXTENSION_CONTRACT.phase,
        )
        cell["request_sha256"] = pilot.request_digest(request)
        cell["rng_material_sha256"] = list(
            pilot._stream_hashes(
                provisional.length,
                provisional.sigma_grid_id,
                provisional.replica,
                master_seed=pilot.TEST_EXTENSION_CONTRACT.master_seed,
                phase=pilot.TEST_EXTENSION_CONTRACT.phase,
            )
        )
        identity = {
            "cell_index": cell["cell_index"],
            "sigma": cell["sigma"],
            "length": cell["length"],
            "replica": cell["replica"],
            "request_sha256": cell["request_sha256"],
        }
        cell_id = (
            f"{cell['cell_index']:03d}-"
            f"{hashlib.sha256(_canonical_bytes(identity)).hexdigest()[:16]}"
        )
        cell_path = f"cells/{cell_id}"
        cell.update(
            {
                "cell_id": cell_id,
                "cell_path": cell_path,
                "run_path": f"{cell_path}/run",
                "manifest_path": f"{cell_path}/manifest.json",
            }
        )
        cells.append(cell)
        assignments.append(
            {
                "cell_index": cell["cell_index"],
                "request_sha256": cell["request_sha256"],
                "streams": cell["rng_material_sha256"],
            }
        )
    document["cells"] = cells
    document["rng_assignment_sha256"] = hashlib.sha256(
        _canonical_bytes({"assignments": assignments})
    ).hexdigest()
    document["run_spec_sha256"] = pilot._document_hash(document, "run_spec_sha256")
    pilot._validate_pilot_spec(
        document,
        contract=pilot.TEST_EXTENSION_CONTRACT,
    )
    path = tmp_path / name / pilot.RUN_SPEC_NAME
    pilot._publish_once(path, document)

    protocol: dict[str, object] = {
        "loop_order": ["sigma", "length", "replica"],
        "lengths": list(lengths),
        "replicas": list(replicas),
        "sigma_entries": [
            {
                "sigma_hex": sigma.hex(),
                "kappas": [value.hex() for value in sigma_kappas[sigma]],
            }
            for sigma in sigmas
        ],
    }
    protocol["protocol_sha256"] = hashlib.sha256(_canonical_bytes(protocol)).hexdigest()

    def deterministic_trajectory(
        request: object, _kernel: np.ndarray, _alias: object
    ) -> TrajectoryResult:
        rows = np.zeros((3, 10), dtype=np.float64)
        for kappa_index in range(3):
            base = (
                request.length / 8
                + 2 * (request.replica - replicas[0])
                + kappa_index
                + 10 * request.sigma
                + value_offset
            )
            rows[kappa_index, 4] = base
            rows[kappa_index, 5] = base + 10
            rows[kappa_index, 8] = base + 20
            rows[kappa_index, 9] = (request.replica + kappa_index) % 2
        return TrajectoryResult(
            request_sha256=pilot.request_digest(request),
            observables=rows,
            terminal_counters=np.zeros((4, 4), dtype=np.uint32),
            draw_counts=np.zeros((4, 3), dtype=np.uint64),
            event_count=0,
            duplicate_count=0,
            hash_diagnostics=np.zeros(5, dtype=np.uint64),
        )

    monkeypatch.setattr(pilot, "run_poisson_numba", deterministic_trajectory)
    for cell_index in range(len(cells)):
        pilot._run_test_registered_pilot_cell(path, cell_index)
    pilot._merge_test_registered_pilot_progress(path)
    return path, document, protocol


def test_aggregate_p0_extension_groups_sigma_grids_with_bounded_retention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path, spec, protocol = _tiny_complete_p0_extension(tmp_path, monkeypatch)
    original_loader = pilot._load_analysis_trajectory
    original_grouper = analysis._group_estimates
    previous_trajectory: weakref.ReferenceType[TrajectoryResult] | None = None
    previous_group: weakref.ReferenceType[np.ndarray] | None = None
    observed_group_shapes: list[tuple[int, ...]] = []

    def tracking_loader(
        trajectory: Path,
        expected: dict[str, str],
        required_digest: str,
    ) -> TrajectoryResult:
        nonlocal previous_trajectory
        if previous_trajectory is not None:
            assert previous_trajectory() is None, (
                "more than one trajectory was retained"
            )
        result = original_loader(trajectory, expected, required_digest)
        previous_trajectory = weakref.ref(result)
        return result

    def tracking_grouper(
        sigma: float,
        length: int,
        kappas: tuple[float, ...],
        values: np.ndarray,
        request_sha256: tuple[str, ...],
    ) -> list[analysis.PilotEstimate]:
        nonlocal previous_group
        if previous_group is not None:
            assert previous_group() is None, "more than one group array was retained"
        observed_group_shapes.append(values.shape)
        previous_group = weakref.ref(values)
        return original_grouper(sigma, length, kappas, values, request_sha256)

    monkeypatch.setattr(pilot, "_load_analysis_trajectory", tracking_loader)
    monkeypatch.setattr(analysis, "_group_estimates", tracking_grouper)
    document = analysis._aggregate_test_p0_extension(path, protocol)

    assert observed_group_shapes == [(2, 3, 4)] * 6
    assert len(document["estimates"]) == 2 * 3 * 3
    assert [
        (
            estimate["sigma_hex"],
            estimate["length"],
            estimate["kappa_hex"],
        )
        for estimate in document["estimates"]
    ] == [
        (entry["sigma_hex"], length, kappa)
        for entry in protocol["sigma_entries"]
        for length in (8, 16, 32)
        for kappa in entry["kappas"]
    ]
    first = document["estimates"][0]
    assert first["request_sha256"] == [
        spec["cells"][0]["request_sha256"],
        spec["cells"][1]["request_sha256"],
    ]
    assert first["means"]["q_g"] == 31.0
    assert first["standard_errors"]["q_g"] == 1.0


def test_aggregate_p0_extension_binds_exact_sources_and_document_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path, spec, protocol = _tiny_complete_p0_extension(tmp_path, monkeypatch)

    document = analysis._aggregate_test_p0_extension(path, protocol)
    unsigned = dict(document)
    digest = unsigned.pop("analysis_document_sha256")

    assert document["schema_version"] == EXTENSION_ANALYSIS_SCHEMA
    assert document["source_extension_protocol_sha256"] == protocol["protocol_sha256"]
    assert (
        document["extension_run_spec_sha256"]
        == hashlib.sha256(path.read_bytes()).hexdigest()
    )
    assert (
        document["extension_progress_sha256"]
        == hashlib.sha256((path.parent / "progress.json").read_bytes()).hexdigest()
    )
    assert document["source_revision"] == spec["orchestration_revision"]
    assert document["analysis_plan_sha256"] == spec["analysis_plan_sha256"]
    assert digest == hashlib.sha256(_canonical_bytes(unsigned)).hexdigest()


@pytest.mark.parametrize(
    "defect",
    ("merged-trajectory-digest", "outer-manifest", "inner-progress"),
)
def test_aggregate_p0_extension_rejects_forged_verified_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    defect: str,
):
    path, spec, protocol = _tiny_complete_p0_extension(tmp_path, monkeypatch)
    root = path.parent
    first = spec["cells"][0]
    if defect == "merged-trajectory-digest":
        target = root / "progress.json"
        document = json.loads(target.read_text(encoding="utf-8"))
        document["cells"][0]["trajectory_sha256"] = "0" * 64
    elif defect == "outer-manifest":
        target = root / first["manifest_path"]
        document = json.loads(target.read_text(encoding="utf-8"))
        document["trajectory_sha256"] = "0" * 64
    else:
        target = root / first["run_path"] / "progress.json"
        document = {"schema_version": "forged-progress"}
    target.write_bytes(_canonical_bytes(document))

    with pytest.raises(RuntimeError, match="stale|corrupt|mismatch|progress"):
        analysis._aggregate_test_p0_extension(path, protocol)


@pytest.mark.parametrize("swap", ("root", "progress"))
def test_aggregate_p0_extension_uses_retained_descriptors_during_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    swap: str,
):
    original, _, protocol = _tiny_complete_p0_extension(
        tmp_path, monkeypatch, name="original", value_offset=0.0
    )
    alternate, _, _ = _tiny_complete_p0_extension(
        tmp_path, monkeypatch, name="alternate", value_offset=1000.0
    )
    baseline = analysis._aggregate_test_p0_extension(original, protocol)
    original_root = original.parent
    alternate_root = alternate.parent
    saved = tmp_path / "saved"
    events: list[str] = []

    def swap_and_restore(stage: str) -> None:
        if stage == "snapshot-verified":
            events.append(stage)
            if swap == "root":
                original_root.rename(saved)
                alternate_root.rename(original_root)
            else:
                progress = original_root / "progress.json"
                progress.rename(saved)
                shutil.copyfile(alternate_root / "progress.json", progress)
        elif stage == "snapshot-closed":
            events.append(stage)
            if swap == "root":
                original_root.rename(alternate_root)
                saved.rename(original_root)
            else:
                progress = original_root / "progress.json"
                progress.unlink()
                saved.rename(progress)

    observed = analysis._aggregate_test_p0_extension(
        original,
        protocol,
        _snapshot_hook=swap_and_restore,
    )

    assert observed == baseline
    assert events == ["snapshot-verified", "snapshot-closed"]


def test_p0_extension_snapshot_is_bounded_named_and_cleaned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path, _, protocol = _tiny_complete_p0_extension(tmp_path, monkeypatch)
    parent = _private_snapshot_parent(tmp_path)
    observed_names: list[str] = []

    def capture(stage: str) -> None:
        if stage == "snapshot-copy-start":
            observed_names.extend(entry.name for entry in parent.iterdir())

    analysis._aggregate_test_p0_extension(
        path,
        protocol,
        snapshot_parent=parent,
        _snapshot_hook=capture,
    )

    assert len(observed_names) == 1
    assert "test-p0-extension-v1" in observed_names[0]
    assert list(parent.iterdir()) == []


def test_p0_extension_snapshot_preflight_fails_before_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path, spec, protocol = _tiny_complete_p0_extension(tmp_path, monkeypatch)
    (path.parent / spec["cells"][0]["cell_path"] / "unknown.bin").write_bytes(b"x")
    copy_calls: list[str] = []

    def forbid_copy(*_args: object, **_kwargs: object) -> None:
        copy_calls.append("called")
        raise AssertionError("payload copy started before bounded preflight")

    monkeypatch.setattr(pilot, "_copy_regular_snapshot_at", forbid_copy)
    with pytest.raises(RuntimeError, match="unknown snapshot layout entry"):
        analysis._aggregate_test_p0_extension(
            path,
            protocol,
            snapshot_parent=_private_snapshot_parent(tmp_path),
        )
    assert copy_calls == []


def test_aggregate_p0_extension_requires_exact_production_cardinality(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    sigmas = (0.9, 1.0)
    lengths = (2**10, 2**14, 2**18)
    replicas = tuple(range(24, 40))
    grids = {
        sigma: tuple(sigma + 0.125 * index for index in range(17)) for sigma in sigmas
    }
    protocol: dict[str, object] = {
        "loop_order": ["sigma", "length", "replica"],
        "lengths": list(lengths),
        "replicas": list(replicas),
        "sigma_entries": [
            {
                "sigma_hex": sigma.hex(),
                "kappas": [value.hex() for value in grids[sigma]],
            }
            for sigma in sigmas
        ],
    }
    protocol["protocol_sha256"] = hashlib.sha256(_canonical_bytes(protocol)).hexdigest()
    cells: list[dict[str, object]] = []
    for sigma in sigmas:
        for length in lengths:
            for replica in replicas:
                index = len(cells)
                cell_path = f"cells/{index:03d}"
                cells.append(
                    {
                        "cell_index": index,
                        "cell_id": f"{index:03d}",
                        "sigma": sigma.hex(),
                        "length": length,
                        "replica": replica,
                        "sigma_grid_id": f"production|{sigma.hex()}",
                        "kappas": [value.hex() for value in grids[sigma]],
                        "kernel_sha256": "1" * 64,
                        "request_sha256": f"{index:064x}",
                        "rng_material_sha256": ["2" * 64] * 4,
                        "cell_path": cell_path,
                        "run_path": f"{cell_path}/run",
                        "manifest_path": f"{cell_path}/manifest.json",
                    }
                )

    class FakeSnapshot:
        run_spec_payload = b"production extension run spec\n"
        progress_payload = b"production extension progress\n"

        def __init__(self) -> None:
            self.spec = {
                "source_extension_protocol_sha256": protocol["protocol_sha256"],
                "orchestration_revision": "3" * 40,
                "analysis_plan_sha256": "4" * 64,
                "cells": cells,
            }

        def load_trajectory(self, cell_index: int) -> TrajectoryResult:
            rows = np.zeros((17, 10), dtype=np.float64)
            rows[:, 4] = cell_index
            rows[:, 5] = cell_index + 1
            rows[:, 8] = cell_index + 2
            rows[:, 9] = cell_index % 2
            return TrajectoryResult(
                request_sha256=cells[cell_index]["request_sha256"],
                observables=rows,
                terminal_counters=np.zeros((4, 4), dtype=np.uint32),
                draw_counts=np.zeros((4, 3), dtype=np.uint64),
                event_count=0,
                duplicate_count=0,
                hash_diagnostics=np.zeros(5, dtype=np.uint64),
            )

    class FakeSnapshotContext:
        def __enter__(self) -> FakeSnapshot:
            return FakeSnapshot()

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(
        pilot,
        "_open_verified_pilot_analysis_snapshot",
        lambda *_args, **_kwargs: FakeSnapshotContext(),
    )

    document = analysis.aggregate_p0_extension(
        (tmp_path / "run_spec.json").resolve(),
        protocol,
    )

    assert len(cells) == 2 * 3 * 16
    assert len(document["estimates"]) == 102
    assert all(estimate["replica_count"] == 16 for estimate in document["estimates"])

    malformed = json.loads(json.dumps(protocol))
    malformed["replicas"].pop()
    unsigned = dict(malformed)
    unsigned.pop("protocol_sha256")
    malformed["protocol_sha256"] = hashlib.sha256(
        _canonical_bytes(unsigned)
    ).hexdigest()
    with pytest.raises(RuntimeError, match="2x3x16x17"):
        analysis.aggregate_p0_extension(
            (tmp_path / "run_spec.json").resolve(),
            malformed,
        )


def test_aggregate_p0_groups_whole_replicas_in_canonical_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path, spec = _tiny_complete_pilot(tmp_path, monkeypatch)
    original_loader = pilot._load_analysis_trajectory
    previous: weakref.ReferenceType[TrajectoryResult] | None = None

    def tracking_loader(
        trajectory: Path,
        expected: dict[str, str],
        required_digest: str,
    ) -> TrajectoryResult:
        nonlocal previous
        if previous is not None:
            assert previous() is None, "more than one trajectory was retained"
        result = original_loader(trajectory, expected, required_digest)
        previous = weakref.ref(result)
        return result

    monkeypatch.setattr(pilot, "_load_analysis_trajectory", tracking_loader)
    document = analysis._aggregate_test_p0(path)

    assert analysis.OBSERVABLE_COLUMNS == OBSERVABLE_COLUMNS
    assert [
        (
            estimate["sigma_hex"],
            estimate["length"],
            estimate["kappa_hex"],
        )
        for estimate in document["estimates"]
    ] == [
        ((1.0).hex(), length, kappa.hex())
        for length in (8, 16)
        for kappa in (0.0, 0.25, 0.5)
    ]
    first = document["estimates"][0]
    assert first == {
        "sigma_hex": (1.0).hex(),
        "length": 8,
        "kappa_hex": (0.0).hex(),
        "replica_count": 2,
        "means": {
            "s1_fraction": 2.0,
            "s2_fraction": 12.0,
            "q_g": 22.0,
            "four_sector_crossing": 0.5,
        },
        "standard_errors": {
            "s1_fraction": 1.0,
            "s2_fraction": 1.0,
            "q_g": 1.0,
            "four_sector_crossing": 0.5,
        },
        "request_sha256": [
            spec["cells"][0]["request_sha256"],
            spec["cells"][1]["request_sha256"],
        ],
    }


def test_aggregate_p0_binds_exact_sources_and_hashes_unsigned_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path, spec = _tiny_complete_pilot(tmp_path, monkeypatch)
    document = analysis._aggregate_test_p0(path)
    unsigned = dict(document)
    digest = unsigned.pop("analysis_document_sha256")

    assert document["schema_version"] == "challenge-194-p0-analysis-v1"
    assert (
        document["p0_run_spec_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    )
    assert (
        document["p0_progress_sha256"]
        == hashlib.sha256((path.parent / "progress.json").read_bytes()).hexdigest()
    )
    assert document["source_revision"] == spec["orchestration_revision"]
    assert document["analysis_plan_sha256"] == spec["analysis_plan_sha256"]
    assert digest == hashlib.sha256(_canonical_bytes(unsigned)).hexdigest()


@pytest.mark.parametrize("defect", ("missing", "duplicate"))
def test_aggregate_p0_rejects_missing_or_duplicate_replicas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str
):
    _path, spec = _tiny_complete_pilot(tmp_path, monkeypatch)
    malformed = dict(spec)
    if defect == "missing":
        malformed["cells"] = list(spec["cells"][:-1])
    else:
        malformed["protocol"] = {
            **spec["protocol"],
            "replicas": [0, 0],
        }
    with pytest.raises(RuntimeError, match=defect):
        axes = analysis._validated_axes(malformed)
        analysis._validate_cells(malformed, *axes)


@pytest.mark.parametrize(
    "defect",
    ("merged-trajectory-digest", "outer-manifest", "inner-progress"),
)
def test_aggregate_p0_rejects_forged_or_stale_verified_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    defect: str,
):
    path, spec = _tiny_complete_pilot(tmp_path, monkeypatch)
    root = path.parent
    first = spec["cells"][0]
    if defect == "merged-trajectory-digest":
        target = root / "progress.json"
        document = json.loads(target.read_text(encoding="utf-8"))
        document["cells"][0]["trajectory_sha256"] = "0" * 64
    elif defect == "outer-manifest":
        target = root / first["manifest_path"]
        document = json.loads(target.read_text(encoding="utf-8"))
        document["trajectory_sha256"] = "0" * 64
    else:
        target = root / first["run_path"] / "progress.json"
        document = {"schema_version": "forged-progress"}
    target.write_bytes(_canonical_bytes(document))

    with pytest.raises(RuntimeError, match="stale|corrupt|mismatch|progress"):
        analysis._aggregate_test_p0(path)


def test_aggregate_p0_uses_retained_root_during_swap_and_restore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    original, _ = _tiny_complete_pilot(
        tmp_path, monkeypatch, name="original", value_offset=0.0
    )
    alternate, _ = _tiny_complete_pilot(
        tmp_path, monkeypatch, name="alternate", value_offset=1000.0
    )
    baseline = analysis._aggregate_test_p0(original)
    original_root = original.parent
    alternate_root = alternate.parent
    detached = tmp_path / "detached-original"
    events: list[str] = []

    def swap_and_restore(stage: str) -> None:
        if stage == "snapshot-verified":
            events.append(stage)
            original_root.rename(detached)
            alternate_root.rename(original_root)
        elif stage == "snapshot-closed":
            events.append(stage)
            original_root.rename(alternate_root)
            detached.rename(original_root)

    observed = analysis._aggregate_test_p0(original, _snapshot_hook=swap_and_restore)

    assert observed == baseline
    assert events == ["snapshot-verified", "snapshot-closed"]
    assert original.is_file()
    assert alternate.is_file()


def test_aggregate_p0_uses_descriptor_progress_during_swap_and_restore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    original, _ = _tiny_complete_pilot(
        tmp_path, monkeypatch, name="original", value_offset=0.0
    )
    alternate, _ = _tiny_complete_pilot(
        tmp_path, monkeypatch, name="alternate", value_offset=1000.0
    )
    baseline = analysis._aggregate_test_p0(original)
    progress = original.parent / "progress.json"
    saved = original.parent / "progress.saved"
    events: list[str] = []

    def swap_and_restore(stage: str) -> None:
        if stage == "snapshot-verified":
            events.append(stage)
            progress.rename(saved)
            shutil.copyfile(alternate.parent / "progress.json", progress)
        elif stage == "snapshot-closed":
            events.append(stage)
            progress.unlink()
            saved.rename(progress)

    observed = analysis._aggregate_test_p0(original, _snapshot_hook=swap_and_restore)

    assert observed == baseline
    assert events == ["snapshot-verified", "snapshot-closed"]


def _private_snapshot_parent(tmp_path: Path) -> Path:
    parent = tmp_path / "snapshots"
    parent.mkdir(mode=0o700)
    return parent


def _snapshot_window_owner(
    parent_value: str,
    window: str,
    ready: object,
    finish: object,
) -> None:
    parent = Path(parent_value)
    process_identity = pilot._snapshot_process_identity()
    token = ("a" if window == "mkdir-before-marker" else "b") * 32
    name = pilot._snapshot_directory_name(process_identity, token)
    candidate = parent / name
    candidate.mkdir(mode=0o700)
    if window == "marker-last-before-rmdir":
        marker = candidate / pilot.PILOT_SNAPSHOT_MARKER
        marker.write_bytes(
            pilot._canonical_bytes(
                pilot._snapshot_marker_document(
                    name,
                    token,
                    process_identity,
                )
            )
        )
        marker.unlink()
    ready.send((name, candidate.stat().st_ino))
    finish.recv()
    candidate.rmdir()
    ready.send("completed")


def _assert_active_snapshot_window_survives(
    parent: Path,
    window: str,
) -> None:
    context = multiprocessing.get_context("fork")
    owner_ready, cleaner_ready = context.Pipe()
    cleaner_finish, owner_finish = context.Pipe()
    owner = context.Process(
        target=_snapshot_window_owner,
        args=(str(parent), window, cleaner_ready, owner_finish),
    )
    owner.start()
    try:
        assert owner_ready.poll(10), "snapshot owner did not reach cleanup window"
        name, inode = owner_ready.recv()
        candidate = parent / name
        parent_fd = pilot._open_validated_snapshot_parent(parent)
        try:
            pilot._cleanup_stale_owned_snapshots(parent_fd)
        finally:
            pilot.os.close(parent_fd)
        assert candidate.stat().st_ino == inode
        cleaner_finish.send("finish")
        assert owner_ready.poll(10), "snapshot owner did not complete"
        assert owner_ready.recv() == "completed"
        owner.join(10)
        assert owner.exitcode == 0
        assert not candidate.exists()
    finally:
        if owner.is_alive():
            cleaner_finish.send("finish")
            owner.join(10)
        if owner.is_alive():
            owner.kill()
            owner.join(10)


def test_snapshot_preflight_rejects_aggregate_over_budget_before_payload_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    path, _ = _tiny_complete_pilot(tmp_path, monkeypatch)
    for trajectory in path.parent.glob("cells/*/run/trajectories/*.h5"):
        with trajectory.open("r+b") as stream:
            stream.truncate(40 * 1024 * 1024)
    copy_calls: list[str] = []

    def forbid_copy(*_args: object, **_kwargs: object) -> None:
        copy_calls.append("called")
        raise AssertionError("payload copy started before aggregate preflight")

    monkeypatch.setattr(pilot, "_copy_regular_snapshot_at", forbid_copy)
    with pytest.raises(RuntimeError, match="aggregate byte budget"):
        analysis._aggregate_test_p0(
            path,
            snapshot_parent=_private_snapshot_parent(tmp_path),
        )
    assert copy_calls == []


def test_snapshot_preflight_rejects_extra_entry_before_payload_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    path, spec = _tiny_complete_pilot(tmp_path, monkeypatch)
    (path.parent / spec["cells"][0]["cell_path"] / "unknown.bin").write_bytes(b"x")
    copy_calls: list[str] = []

    def forbid_copy(*_args: object, **_kwargs: object) -> None:
        copy_calls.append("called")
        raise AssertionError("payload copy started before layout preflight")

    monkeypatch.setattr(pilot, "_copy_regular_snapshot_at", forbid_copy)
    with pytest.raises(RuntimeError, match="unknown snapshot layout entry"):
        analysis._aggregate_test_p0(
            path,
            snapshot_parent=_private_snapshot_parent(tmp_path),
        )
    assert copy_calls == []


def test_snapshot_capacity_failure_occurs_before_payload_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    path, _ = _tiny_complete_pilot(tmp_path, monkeypatch)
    copy_calls: list[str] = []

    def forbid_copy(*_args: object, **_kwargs: object) -> None:
        copy_calls.append("called")
        raise AssertionError("payload copy started before capacity preflight")

    monkeypatch.setattr(pilot, "_copy_regular_snapshot_at", forbid_copy)
    monkeypatch.setattr(
        pilot.os,
        "statvfs",
        lambda _path: SimpleNamespace(f_bavail=0, f_frsize=4096),
    )
    with pytest.raises(RuntimeError, match="snapshot filesystem capacity"):
        analysis._aggregate_test_p0(
            path,
            snapshot_parent=_private_snapshot_parent(tmp_path),
        )
    assert copy_calls == []
    assert pilot.PILOT_SNAPSHOT_SAFETY_RESERVE_BYTES > 0


def test_snapshot_copy_global_counter_rejects_file_growth_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    path, spec = _tiny_complete_pilot(tmp_path, monkeypatch)
    request = path.parent / spec["cells"][0]["run_path"] / "request.json"
    parent = _private_snapshot_parent(tmp_path)
    stages: list[str] = []

    def grow_after_preflight(stage: str) -> None:
        if stage == "snapshot-preflighted":
            stages.append(stage)
            with request.open("ab") as stream:
                stream.write(b" ")

    with pytest.raises(RuntimeError, match="snapshot byte budget changed during copy"):
        analysis._aggregate_test_p0(
            path,
            snapshot_parent=parent,
            _snapshot_hook=grow_after_preflight,
        )
    assert stages == ["snapshot-preflighted"]
    assert list(parent.iterdir()) == []


def test_snapshot_exception_removes_uniquely_owned_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    path, _ = _tiny_complete_pilot(tmp_path, monkeypatch)
    parent = _private_snapshot_parent(tmp_path)

    def fail_during_copy(stage: str) -> None:
        if stage == "snapshot-copy-start":
            raise RuntimeError("injected snapshot failure")

    with pytest.raises(RuntimeError, match="injected snapshot failure"):
        analysis._aggregate_test_p0(
            path,
            snapshot_parent=parent,
            _snapshot_hook=fail_during_copy,
        )
    assert list(parent.iterdir()) == []


def test_snapshot_cleanup_removes_ownership_marker_last(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    path, _ = _tiny_complete_pilot(tmp_path, monkeypatch)
    parent = _private_snapshot_parent(tmp_path)
    original_unlink = pilot.os.unlink
    removed_names: list[str] = []

    def tracking_unlink(
        name: str,
        *,
        dir_fd: int | None = None,
    ) -> None:
        removed_names.append(name)
        original_unlink(name, dir_fd=dir_fd)

    monkeypatch.setattr(pilot.os, "unlink", tracking_unlink)
    analysis._aggregate_test_p0(path, snapshot_parent=parent)

    assert removed_names[-1] == pilot.PILOT_SNAPSHOT_MARKER
    assert list(parent.iterdir()) == []


def test_stale_cleanup_preserves_active_mkdir_before_marker_window(
    tmp_path: Path,
):
    parent = _private_snapshot_parent(tmp_path)
    _assert_active_snapshot_window_survives(parent, "mkdir-before-marker")


def test_stale_cleanup_preserves_active_marker_last_before_rmdir_window(
    tmp_path: Path,
):
    parent = _private_snapshot_parent(tmp_path)
    _assert_active_snapshot_window_survives(
        parent,
        "marker-last-before-rmdir",
    )


def test_stale_cleanup_removes_proven_dead_markerless_snapshot(
    tmp_path: Path,
):
    parent = _private_snapshot_parent(tmp_path)
    name = pilot._snapshot_directory_name(
        (2_147_483_647, f"linux-{'0' * 32}-1"),
        "c" * 32,
    )
    candidate = parent / name
    candidate.mkdir(mode=0o700)

    parent_fd = pilot._open_validated_snapshot_parent(parent)
    try:
        pilot._cleanup_stale_owned_snapshots(parent_fd)
    finally:
        pilot.os.close(parent_fd)

    assert not candidate.exists()


def test_stale_cleanup_leaves_unverifiable_markerless_snapshot(
    tmp_path: Path,
):
    parent = _private_snapshot_parent(tmp_path)
    name = pilot._snapshot_directory_name(
        (pilot.os.getpid(), None),
        "d" * 32,
    )
    candidate = parent / name
    candidate.mkdir(mode=0o700)
    inode = candidate.stat().st_ino

    parent_fd = pilot._open_validated_snapshot_parent(parent)
    try:
        pilot._cleanup_stale_owned_snapshots(parent_fd)
    finally:
        pilot.os.close(parent_fd)

    assert candidate.stat().st_ino == inode
    candidate.rmdir()


def test_pilot_estimate_is_immutable():
    estimate = analysis.PilotEstimate(
        sigma=1.0,
        length=8,
        kappa=0.25,
        replica_count=2,
        means={"q_g": 0.5},
        standard_errors={"q_g": 0.1},
        request_sha256=("1" * 64, "2" * 64),
    )
    with pytest.raises(FrozenInstanceError):
        estimate.length = 16
    with pytest.raises(TypeError):
        estimate.means["q_g"] = 1.0


def test_select_p1_brackets_selects_unique_common_interval():
    values: dict[tuple[float, int, float], tuple[float, float]] = {}
    kappas = (0.0, 1.0, 2.0, 4.0)
    _set_selector_value(
        values, 0.8, 16, kappas, (4.0, 2.0, 1.0, 0.0), (0.0, 0.1, 0.2, 0.9)
    )
    _set_selector_value(
        values, 0.8, 32, kappas, (3.0, 1.0, 2.0, 3.0), (0.0, 0.2, 0.8, 1.0)
    )

    selected = analysis.select_p1_brackets(
        _selector_document(sigmas=(0.8,), values=values)
    )

    assert selected["requires_p0_extension"] is False
    bracket = selected["brackets"][0]
    assert bracket["sigma_hex"] == (0.8).hex()
    assert bracket["lower_kappa_hex"] == (1.0).hex()
    assert bracket["upper_kappa_hex"] == (2.0).hex()
    assert bracket["lengths"] == [16, 32]
    assert bracket["estimator_evidence"]["q_g"]["marked"] is True
    assert bracket["estimator_evidence"]["four_sector_crossing"]["marked"] is True
    assert bracket["tie_break"] == {
        "rule": "narrowest_interval_then_lower_coupling",
        "candidate_count": 1,
        "selected_width_hex": (1.0).hex(),
    }


def test_select_p1_brackets_breaks_common_interval_ties_deterministically():
    values: dict[tuple[float, int, float], tuple[float, float]] = {}
    kappas = (0.0, 1.0, 3.0, 5.0, 8.0)
    for length, q_g in (
        (16, (9.0, 3.0, 1.0, 3.0, 3.0)),
        (32, (8.0, 1.0, 2.0, 1.0, 2.0)),
    ):
        _set_selector_value(
            values,
            0.8,
            length,
            kappas,
            q_g,
            (0.0, 0.2, 0.8, 0.2, 0.8),
        )

    selected = analysis.select_p1_brackets(
        _selector_document(sigmas=(0.8,), kappas=kappas, values=values)
    )

    bracket = selected["brackets"][0]
    assert bracket["lower_kappa_hex"] == (1.0).hex()
    assert bracket["upper_kappa_hex"] == (3.0).hex()
    assert bracket["tie_break"]["candidate_count"] == 2


def test_select_p1_brackets_requests_extension_without_common_interval():
    selected = analysis.select_p1_brackets(_selector_document(sigmas=(0.8,), values={}))

    assert selected["requires_p0_extension"] is True
    assert selected["brackets"] == [
        {
            "sigma_hex": (0.8).hex(),
            "status": "requires_p0_extension",
            "reason": "no_nonzero_interval_marked_by_both_estimators",
            "lengths": [16, 32],
        }
    ]


def test_select_p1_brackets_uses_maximum_control_slope():
    values: dict[tuple[float, int, float], tuple[float, float]] = {}
    kappas = (0.0, 1.0, 3.0, 5.0)
    _set_selector_value(
        values,
        1.1,
        32,
        kappas,
        (1.0, 1.0, 1.0, 1.0),
        (0.0, 0.1, 0.9, 1.0),
    )

    selected = analysis.select_p1_brackets(
        _selector_document(sigmas=(1.1,), kappas=kappas, values=values)
    )

    bracket = selected["brackets"][0]
    assert bracket["purpose"] == "crossover_refinement"
    assert bracket["lower_kappa_hex"] == (1.0).hex()
    assert bracket["upper_kappa_hex"] == (3.0).hex()
    assert bracket["estimator_evidence"]["absolute_slope_hex"] == (0.4).hex()
    assert bracket["tie_break"]["rule"] == "maximum_absolute_slope_then_lower_coupling"


def test_combined_selector_uses_per_sigma_axes_and_preserves_control_windows():
    p0, extension_analysis, combined = _combined_selector_document()

    original = analysis.select_p1_brackets(p0)
    first = _select_test_combined(combined, p0, extension_analysis)
    second = _select_test_combined(combined, p0, extension_analysis)

    assert first["schema_version"] == analysis.COMBINED_BRACKET_SCHEMA
    assert (
        first["source_analysis_document_sha256"] == combined["analysis_document_sha256"]
    )
    assert _canonical_bytes(first) == _canonical_bytes(second)
    assert first["requires_p0_extension"] is False
    assert [entry["status"] for entry in first["brackets"]] == ["selected"] * 4
    for index in (1, 2):
        assert float.fromhex(first["brackets"][index]["lower_kappa_hex"]) > 0.0
    for index in (0, 3):
        assert (
            first["brackets"][index]["lower_kappa_hex"],
            first["brackets"][index]["upper_kappa_hex"],
        ) == (
            original["brackets"][index]["lower_kappa_hex"],
            original["brackets"][index]["upper_kappa_hex"],
        )
    assert [
        (
            first["brackets"][index]["lower_kappa_hex"],
            first["brackets"][index]["upper_kappa_hex"],
        )
        for index in (0, 3)
    ] == [
        ("0x1.f400000000000p-2", "0x1.3880000000000p-1"),
        ("0x1.312d000000000p+0", "0x1.7d78400000000p+0"),
    ]
    assert [len(entry["kappas"]) for entry in combined["sigma_entries"]] == [
        16,
        31,
        31,
        16,
    ]


def test_combined_selector_fails_closed_when_one_sigma_remains_unresolved():
    p0, extension_analysis, combined = _combined_selector_document(unresolved_sigma=1.0)

    brackets = _select_test_combined(combined, p0, extension_analysis)

    assert brackets["schema_version"] == analysis.COMBINED_BRACKET_SCHEMA
    assert brackets["requires_p0_extension"] is True
    assert brackets["brackets"][2]["status"] == "requires_p0_extension"
    with pytest.raises(RuntimeError, match="P0 extension required.*1\\.0"):
        _build_test_combined_p1(combined, brackets, p0, extension_analysis)


def test_p1_accepts_combined_only_with_selected_v2_brackets():
    p0, extension_analysis, combined = _combined_selector_document()
    brackets = _select_test_combined(combined, p0, extension_analysis)

    protocol = _build_test_combined_p1(combined, brackets, p0, extension_analysis)

    assert (
        protocol["source_analysis_document_sha256"]
        == combined["analysis_document_sha256"]
    )
    assert (
        protocol["source_bracket_document_sha256"]
        == brackets["bracket_document_sha256"]
    )
    assert protocol["grid_namespace"] == "pilot-p1-v1"
    assert protocol["master_seed"] == 19_420_261_729
    assert protocol["replicas"] == list(range(8, 24))
    assert len(protocol["cells"]) == 4 * 3 * 16
    assert all(len(entry["kappas"]) == 9 for entry in protocol["sigma_entries"])

    legacy = json.loads(json.dumps(brackets))
    legacy["schema_version"] = analysis.BRACKET_SCHEMA
    unsigned = dict(legacy)
    unsigned.pop("bracket_document_sha256")
    legacy["bracket_document_sha256"] = hashlib.sha256(
        _canonical_bytes(unsigned)
    ).hexdigest()
    with pytest.raises(RuntimeError, match="schema version"):
        _build_test_combined_p1(combined, legacy, p0, extension_analysis)

    forged = json.loads(json.dumps(brackets))
    forged["brackets"][0]["lower_kappa_hex"] = (0.5).hex()
    unsigned = dict(forged)
    unsigned.pop("bracket_document_sha256")
    forged["bracket_document_sha256"] = hashlib.sha256(
        _canonical_bytes(unsigned)
    ).hexdigest()
    with pytest.raises(RuntimeError, match="selector output"):
        _build_test_combined_p1(combined, forged, p0, extension_analysis)


def test_combined_v2_requires_sources_for_selection_and_direct_build():
    _p0, _extension_analysis, combined = _combined_selector_document()

    with pytest.raises(RuntimeError, match="source validation"):
        analysis.select_p1_brackets(combined)
    with pytest.raises(RuntimeError, match="source validation"):
        analysis.build_p1_protocol(combined)


@pytest.mark.parametrize("defect", ("missing-nine-fields", "zeroed-source-hash"))
def test_combined_selector_rejects_resigned_provenance_bypass(defect: str):
    p0, extension_analysis, combined = _combined_selector_document()
    forged = json.loads(json.dumps(combined))
    if defect == "missing-nine-fields":
        for field in (
            "source_p0_analysis_document_sha256",
            "source_extension_analysis_document_sha256",
            "p0_run_spec_sha256",
            "p0_progress_sha256",
            "extension_run_spec_sha256",
            "extension_progress_sha256",
            "p0_source_revision",
            "extension_source_revision",
            "observable_columns",
        ):
            forged.pop(field)
    else:
        forged["source_p0_analysis_document_sha256"] = "0" * 64
    _sign(forged)

    with pytest.raises(RuntimeError, match="fields|recomputation"):
        _select_test_combined(forged, p0, extension_analysis)


@pytest.mark.parametrize("source_defect", ("swapped-types", "cross-generation"))
def test_combined_selector_rejects_wrong_source_documents(source_defect: str):
    p0, extension_analysis, combined = _combined_selector_document()
    alternate_p0, alternate_extension, _alternate = _combined_selector_document(
        blocked_interval_offset=1
    )
    supplied_p0, supplied_extension = (
        (extension_analysis, p0)
        if source_defect == "swapped-types"
        else (alternate_p0, alternate_extension)
    )

    with pytest.raises(RuntimeError):
        _select_test_combined(combined, supplied_p0, supplied_extension)


def test_combined_build_rejects_rebound_cross_generation_brackets():
    p0, extension_analysis, combined = _combined_selector_document()
    alternate_p0, alternate_extension, alternate = _combined_selector_document(
        blocked_interval_offset=1
    )
    alternate_brackets = _select_test_combined(
        alternate, alternate_p0, alternate_extension
    )
    rebound = json.loads(json.dumps(alternate_brackets))
    rebound["source_analysis_document_sha256"] = combined["analysis_document_sha256"]
    unsigned = dict(rebound)
    unsigned.pop("bracket_document_sha256")
    rebound["bracket_document_sha256"] = hashlib.sha256(
        _canonical_bytes(unsigned)
    ).hexdigest()

    with pytest.raises(RuntimeError, match="selector output"):
        _build_test_combined_p1(combined, rebound, p0, extension_analysis)


def test_combined_direct_build_rejects_resigned_forged_brackets():
    p0, extension_analysis, combined = _combined_selector_document()
    brackets = _select_test_combined(combined, p0, extension_analysis)
    forged = json.loads(json.dumps(brackets))
    target = forged["brackets"][1]
    lower = float.fromhex(target["lower_kappa_hex"])
    upper = float.fromhex(target["upper_kappa_hex"])
    target["lower_kappa_hex"] = (lower + (upper - lower) / 4.0).hex()
    unsigned = dict(forged)
    unsigned.pop("bracket_document_sha256")
    forged["bracket_document_sha256"] = hashlib.sha256(
        _canonical_bytes(unsigned)
    ).hexdigest()

    with pytest.raises(RuntimeError, match="selector output"):
        _build_test_combined_p1(combined, forged, p0, extension_analysis)


@pytest.mark.parametrize(
    ("defect", "match"),
    (
        ("zero-only", "zero-coupling"),
        ("reordered", "canonical coupling order"),
        ("nan", "finite"),
        ("missing-largest", "largest-size estimates"),
    ),
)
def test_select_p1_brackets_rejects_malformed_evidence(defect: str, match: str):
    values: dict[tuple[float, int, float], tuple[float, float]] = {}
    kappas = (0.0, 1.0, 2.0, 4.0)
    if defect == "zero-only":
        _set_selector_value(
            values,
            0.8,
            16,
            kappas,
            (2.0, 1.0, 1.0, 1.0),
            (0.2, 0.8, 0.8, 0.8),
        )
        _set_selector_value(
            values,
            0.8,
            32,
            kappas,
            (1.0, 2.0, 2.0, 2.0),
            (0.2, 0.8, 0.8, 0.8),
        )
    document = _selector_document(sigmas=(0.8,), values=values)
    estimates = document["estimates"]
    assert isinstance(estimates, list)
    if defect == "reordered":
        estimates[5], estimates[6] = estimates[6], estimates[5]
    elif defect == "nan":
        estimates[-1]["means"]["q_g"] = float("nan")
    elif defect == "missing-largest":
        estimates.pop()
    if defect not in ("zero-only", "nan"):
        unsigned = dict(document)
        unsigned.pop("analysis_document_sha256")
        document["analysis_document_sha256"] = hashlib.sha256(
            _canonical_bytes(unsigned)
        ).hexdigest()

    with pytest.raises(RuntimeError, match=match):
        analysis.select_p1_brackets(document)


def _selected_bracket_document(
    source: dict[str, object],
    *,
    requires_extension: bool = False,
) -> dict[str, object]:
    brackets: list[dict[str, object]] = []
    for index, sigma in enumerate((0.8, 0.9, 1.0, 1.1)):
        if requires_extension and sigma == 1.0:
            brackets.append(
                {
                    "sigma_hex": sigma.hex(),
                    "status": "requires_p0_extension",
                    "reason": "no_nonzero_interval_marked_by_both_estimators",
                    "lengths": [16, 32],
                }
            )
            continue
        brackets.append(
            {
                "sigma_hex": sigma.hex(),
                "status": "selected",
                "purpose": (
                    "transition_refinement" if sigma <= 1.0 else "crossover_refinement"
                ),
                "lower_kappa_hex": float(index + 1).hex(),
                "upper_kappa_hex": float(index + 2).hex(),
                "lengths": [16, 32],
                "estimator_evidence": {"synthetic": True},
                "tie_break": {"rule": "synthetic"},
            }
        )
    document: dict[str, object] = {
        "schema_version": analysis.BRACKET_SCHEMA,
        "source_analysis_document_sha256": source["analysis_document_sha256"],
        "requires_p0_extension": requires_extension,
        "brackets": brackets,
    }
    document["bracket_document_sha256"] = hashlib.sha256(
        _canonical_bytes(document)
    ).hexdigest()
    return document


def test_build_p1_protocol_freezes_grids_requests_and_rng_assignments():
    source = _selector_document(
        sigmas=(0.8, 0.9, 1.0, 1.1),
        lengths=(8, 16, 32),
    )
    brackets = _selected_bracket_document(source)

    protocol = analysis.build_p1_protocol(source, brackets)

    assert protocol["schema_version"] == analysis.P1_PROTOCOL_SCHEMA
    assert (
        protocol["source_analysis_document_sha256"]
        == source["analysis_document_sha256"]
    )
    assert (
        protocol["source_bracket_document_sha256"]
        == brackets["bracket_document_sha256"]
    )
    assert protocol["phase"] == "pilot"
    assert protocol["lengths"] == [8, 16, 32]
    assert protocol["replicas"] == list(range(8, 24))
    assert len(protocol["sigma_entries"]) == 4
    for entry in protocol["sigma_entries"]:
        grid = [float.fromhex(value) for value in entry["kappas"]]
        assert len(grid) == 9
        assert grid == sorted(grid)
        assert len(set(entry["kappas"])) == 9
        assert entry["kappas"][0] == entry["lower_kappa_hex"]
        assert entry["kappas"][-1] == entry["upper_kappa_hex"]

    cells = protocol["cells"]
    assert len(cells) == 4 * 3 * 16
    assert [cell["cell_index"] for cell in cells] == list(range(len(cells)))
    assert all(cell["replica"] not in range(8) for cell in cells)
    assert len({cell["request_sha256"] for cell in cells}) == len(cells)
    stream_hashes = [
        stream_hash for cell in cells for stream_hash in cell["rng_material_sha256"]
    ]
    assert len(set(stream_hashes)) == len(stream_hashes)
    assert all(
        cell["cell_path"] == f"cells/{cell['cell_id']}"
        and cell["run_path"] == f"{cell['cell_path']}/run"
        and cell["manifest_path"] == f"{cell['cell_path']}/manifest.json"
        for cell in cells
    )
    unsigned = dict(protocol)
    digest = unsigned.pop("protocol_sha256")
    assert digest == hashlib.sha256(_canonical_bytes(unsigned)).hexdigest()
    analysis.validate_p1_protocol(source, protocol)


def test_build_p1_protocol_rejects_required_p0_extension():
    source = _selector_document(
        sigmas=(0.8, 0.9, 1.0, 1.1),
        lengths=(8, 16, 32),
    )
    brackets = _selected_bracket_document(source, requires_extension=True)

    with pytest.raises(RuntimeError, match="P0 extension required.*1\\.0"):
        analysis.build_p1_protocol(source, brackets)


def test_original_real_p0_bracket_bytes_hash_and_refusal_are_unchanged():
    source_path = (
        Path(__file__).resolve().parents[6] / "results/challenge-194/p0_analysis.json"
    )
    source = extension.load_frozen_p0_analysis(source_path)

    first = analysis.select_p1_brackets(source)
    second = analysis.select_p1_brackets(source)

    assert _canonical_bytes(first) == _canonical_bytes(second)
    assert first["bracket_document_sha256"] == (
        "fb3df666044bf9531443fc00c5c2c2d489512b4162864b3a92ffc2e756832403"
    )
    assert first["requires_p0_extension"] is True
    assert [
        float.fromhex(entry["sigma_hex"])
        for entry in first["brackets"]
        if entry["status"] == "requires_p0_extension"
    ] == [0.9, 1.0]
