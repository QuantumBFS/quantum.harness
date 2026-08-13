import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pytest

import oracle.oddcycle_local_hs_runner as runner
from oracle.oddcycle_local_hs_runner import (
    BatchCell,
    expand_settings,
    promote_from_payloads,
    run_batch,
    run_cell,
)
from oracle.oddcycle_local_hs_scan import NumericalConeResult


def test_batch_resume_does_not_repeat_completed_cells(tmp_path):
    settings = {
        "schema": "oddcycle-local-hs-settings-v1",
        "seed": 20260730,
        "cells": [
            {
                "id": "free-l2-path-edge",
                "mode": "free",
                "max_word_length": 2,
                "locality": "path-edge",
            },
            {
                "id": "portfolio-l1",
                "mode": "portfolio",
                "max_word_length": 1,
                "sample_count": 2,
            },
        ],
    }

    first = run_batch(settings, tmp_path, workers=1, resume=True)
    second = run_batch(settings, tmp_path, workers=1, resume=True)

    assert first.completed == 2
    assert second.completed == 0
    assert second.skipped == 2
    records = [
        json.loads(line)
        for line in (tmp_path / "manifest.jsonl").read_text().splitlines()
    ]
    assert len(records) == 2
    assert {record["cell_id"] for record in records} == {
        "free-l2-path-edge",
        "portfolio-l1",
    }


def test_frozen_settings_expand_to_40_stable_cells():
    settings = json.loads(
        Path("protocols/oddcycle-local-hs-v1/settings.json").read_text()
    )

    cells = expand_settings(settings)

    assert len(cells) == 40
    assert len({cell.id for cell in cells}) == 40
    assert cells == tuple(sorted(cells, key=lambda cell: cell.id))


def _payload_hash(payload):
    unhashed = dict(payload)
    unhashed.pop("payload_sha256", None)
    encoded = json.dumps(
        unhashed,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_cell_payload(path, cell, scans):
    payload = {
        "schema": "oddcycle-local-hs-cell-v1",
        "cell_id": cell.id,
        "cell": asdict(cell),
        "status": "survivor",
        "dictionary": {
            "max_word_length": cell.max_word_length,
            "column_count": 1,
        },
        "result": {
            "locality": cell.locality,
            "numerical_survivor_count": len(scans),
            "scans": scans,
        },
    }
    payload["payload_sha256"] = _payload_hash(payload)
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n"
    )
    return payload


def test_cpu_screening_does_not_run_exact_promotion(monkeypatch, tmp_path):
    cell = BatchCell(
        id="free-l1-path-edge",
        mode="free",
        max_word_length=1,
        locality="path-edge",
    )
    numerical = NumericalConeResult(
        status="numerical-survivor",
        weights=np.array([1.0]),
        residual=0.0,
        minimum_retained_weight=1.0,
        active_indices=(0,),
        objective=0.0,
        solver_message="synthetic",
        iteration_count=0,
    )
    monkeypatch.setattr(runner, "build_word_dictionary", lambda _length: (object(),))
    monkeypatch.setattr(
        runner,
        "scan_positive_local_kernel",
        lambda _columns, _spec: (numerical,),
    )
    monkeypatch.setattr(
        runner,
        "exact_local_hs_certificate",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("CPU screening must not promote")
        ),
    )

    payload = run_cell(cell, tmp_path)

    assert payload["status"] == "survivor"
    assert payload["result"]["numerical_survivor_count"] == 1
    assert "exact_promotion" not in payload["result"]["scans"][0]


def test_promotion_errors_are_per_survivor_and_resume_is_append_only(
    monkeypatch,
    tmp_path,
):
    cell = BatchCell(
        id="free-l1-path-edge",
        mode="free",
        max_word_length=1,
        locality="path-edge",
    )
    scans = [
        {
            "scan_index": index,
            "status": "numerical-survivor",
            "residual": 0.0,
            "active_indices": [0],
            "active_weights": [1.0],
        }
        for index in range(2)
    ]
    source = tmp_path / "incoming" / f"{cell.id}.json"
    _write_cell_payload(source, cell, scans)
    source_bytes = source.read_bytes()
    monkeypatch.setattr(runner, "build_word_dictionary", lambda _length: (object(),))
    monkeypatch.setattr(
        runner,
        "exact_local_hs_certificate",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ArithmeticError("synthetic exact replay failure")
        ),
    )
    output = tmp_path / "promoted"

    first = promote_from_payloads([source], output, workers=1, resume=True)
    second = promote_from_payloads([source], output, workers=1, resume=True)

    assert first.completed == 2
    assert second.completed == 0
    assert second.skipped == 2
    assert source.read_bytes() == source_bytes
    records = [
        json.loads(line)
        for line in (output / "promotion-manifest.jsonl").read_text().splitlines()
    ]
    assert len(records) == 2
    for record in records:
        payload = json.loads((output / record["path"]).read_text())
        assert payload["certificate"]["status"] == (
            "exact-promotion-inconclusive"
        )
        assert payload["certificate"]["error_type"] == "ArithmeticError"


def _explicit_portfolio_settings():
    return {
        "schema": "oddcycle-local-hs-settings-v1",
        "seed": 20260730,
        "cells": [
            {
                "id": "portfolio-l1",
                "mode": "portfolio",
                "max_word_length": 1,
                "sample_count": 0,
            }
        ],
    }


def test_manifest_only_completion_is_rejected(tmp_path):
    settings = _explicit_portfolio_settings()
    cell = expand_settings(settings)[0]
    record = runner._manifest_record_for_cell(
        cell,
        payload_sha256="0" * 64,
        status="inconclusive",
    )
    (tmp_path / "manifest.jsonl").write_text(
        json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n"
    )

    with pytest.raises(ValueError, match="orphan manifest"):
        run_batch(settings, tmp_path, workers=1, resume=True)


def test_manifest_full_cell_digest_rejects_changed_settings(tmp_path):
    settings = _explicit_portfolio_settings()
    cell = expand_settings(settings)[0]
    record = runner._manifest_record_for_cell(
        cell,
        payload_sha256="0" * 64,
        status="inconclusive",
    )
    record["cell_settings_sha256"] = "f" * 64
    (tmp_path / "manifest.jsonl").write_text(
        json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n"
    )

    with pytest.raises(ValueError, match="different settings"):
        run_batch(settings, tmp_path, workers=1, resume=True)


def test_torn_final_manifest_line_is_repaired_from_verified_cell(tmp_path):
    settings = _explicit_portfolio_settings()
    cell = expand_settings(settings)[0]
    cells_dir = tmp_path / "cells"
    cells_dir.mkdir(parents=True)
    payload = {
        "schema": "oddcycle-local-hs-cell-v1",
        "cell_id": cell.id,
        "cell": asdict(cell),
        "status": "inconclusive",
        "dictionary": {
            "max_word_length": cell.max_word_length,
            "column_count": 0,
        },
        "result": {"sample_count": 0, "records": []},
    }
    runner._atomic_write_payload(
        payload,
        cells_dir / f"{cell.id}.json",
    )
    (tmp_path / "manifest.jsonl").write_text('{"schema":')

    summary = run_batch(settings, tmp_path, workers=1, resume=True)

    assert summary.completed == 0
    assert summary.skipped == 1
    records = [
        json.loads(line)
        for line in (tmp_path / "manifest.jsonl").read_text().splitlines()
    ]
    assert len(records) == 1
    assert records[0]["cell_id"] == cell.id


def test_malformed_interior_manifest_line_is_rejected(tmp_path):
    settings = _explicit_portfolio_settings()
    cell = expand_settings(settings)[0]
    record = runner._manifest_record_for_cell(
        cell,
        payload_sha256="0" * 64,
        status="inconclusive",
    )
    canonical = json.dumps(record, separators=(",", ":"), sort_keys=True)
    (tmp_path / "manifest.jsonl").write_text(
        f"{canonical}\n"
        '{"schema":\n'
        f"{canonical}\n"
    )

    with pytest.raises(ValueError, match="invalid manifest JSON"):
        run_batch(settings, tmp_path, workers=1, resume=True)


def _write_completed_cell(output_dir, cell):
    payload = {
        "schema": "oddcycle-local-hs-cell-v1",
        "cell_id": cell.id,
        "cell": asdict(cell),
        "status": "inconclusive",
        "dictionary": {
            "max_word_length": cell.max_word_length,
            "column_count": 0,
        },
        "result": {"sample_count": 0, "records": []},
    }
    return runner._atomic_write_payload(
        payload,
        output_dir / "cells" / f"{cell.id}.json",
    )


def test_valid_unterminated_manifest_is_normalized_before_backfill(tmp_path):
    settings = {
        "schema": "oddcycle-local-hs-settings-v1",
        "seed": 20260730,
        "cells": [
            {
                "id": f"portfolio-l{length}",
                "mode": "portfolio",
                "max_word_length": length,
                "sample_count": 0,
            }
            for length in (1, 2)
        ],
    }
    cells = expand_settings(settings)
    payloads = [
        _write_completed_cell(tmp_path, cell)
        for cell in cells
    ]
    first_record = runner._manifest_record(payloads[0])
    (tmp_path / "manifest.jsonl").write_text(
        json.dumps(first_record, separators=(",", ":"), sort_keys=True)
    )

    summary = run_batch(settings, tmp_path, workers=1, resume=True)

    assert summary.completed == 0
    assert summary.skipped == 2
    text = (tmp_path / "manifest.jsonl").read_text()
    assert text.endswith("\n")
    records = [json.loads(line) for line in text.splitlines()]
    assert len(records) == 2
    assert {record["cell_id"] for record in records} == {
        "portfolio-l1",
        "portfolio-l2",
    }


def _single_promotion_candidate(tmp_path):
    cell = BatchCell(
        id="free-l1-path-edge",
        mode="free",
        max_word_length=1,
        locality="path-edge",
    )
    source = tmp_path / "incoming" / f"{cell.id}.json"
    source_payload = _write_cell_payload(
        source,
        cell,
        [
            {
                "scan_index": 0,
                "status": "numerical-survivor",
                "residual": 0.0,
                "active_indices": [0],
                "active_weights": [1.0],
            }
        ],
    )
    candidate = runner._promotion_candidates([source])[0]
    return cell, source, source_payload, candidate


def _write_mismatched_promotion(output_dir, cell, source_payload, **changes):
    promotion_id = f"{cell.id}--scan-0000"
    payload = {
        "schema": "oddcycle-local-hs-promotion-v1",
        "promotion_id": promotion_id,
        "cell_id": cell.id,
        "cell_settings_sha256": runner._cell_settings_sha256(cell),
        "source_cell_payload_sha256": source_payload["payload_sha256"],
        "scan_index": 0,
        "status": "inconclusive",
        "certificate": {
            "schema": "oddcycle-local-hs-exact-v1",
            "status": "exact-promotion-inconclusive",
            "reason": "synthetic",
        },
        **changes,
    }
    return runner._atomic_write_payload(
        payload,
        output_dir / "promotions" / f"{promotion_id}.json",
    )


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("cell_id", "free-l9-path-edge"),
        ("scan_index", 9),
    ],
)
def test_promotion_final_only_backfill_rejects_wrong_candidate_identity(
    tmp_path,
    field,
    wrong_value,
):
    cell, source, source_payload, _candidate = _single_promotion_candidate(
        tmp_path
    )
    output = tmp_path / "promoted"
    _write_mismatched_promotion(
        output,
        cell,
        source_payload,
        **{field: wrong_value},
    )

    with pytest.raises(ValueError, match="candidate identity"):
        promote_from_payloads([source], output, workers=1, resume=True)


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("cell_id", "free-l9-path-edge"),
        ("scan_index", 9),
    ],
)
def test_promotion_existing_file_race_rejects_wrong_candidate_identity(
    monkeypatch,
    tmp_path,
    field,
    wrong_value,
):
    cell, _source, source_payload, candidate = _single_promotion_candidate(
        tmp_path
    )
    output = tmp_path / "promoted"
    _write_mismatched_promotion(
        output,
        cell,
        source_payload,
        **{field: wrong_value},
    )
    monkeypatch.setattr(
        runner,
        "build_word_dictionary",
        lambda _length: (object(),),
    )
    monkeypatch.setattr(
        runner,
        "exact_local_hs_certificate",
        lambda *_args, **_kwargs: {
            "schema": "oddcycle-local-hs-exact-v1",
            "status": "exact-promotion-inconclusive",
            "reason": "synthetic",
        },
    )

    with pytest.raises(ValueError, match="candidate identity"):
        runner._promote_source_candidates([candidate], output)


def test_promotion_summary_distinguishes_exact_rejection(
    monkeypatch,
    tmp_path,
):
    cell = BatchCell(
        id="free-l1-path-edge",
        mode="free",
        max_word_length=1,
        locality="path-edge",
    )
    source = tmp_path / "incoming" / f"{cell.id}.json"
    _write_cell_payload(
        source,
        cell,
        [
            {
                "scan_index": index,
                "status": "numerical-survivor",
                "residual": 0.0,
                "active_indices": [0],
                "active_weights": [1.0],
            }
            for index in range(4)
        ],
    )
    certificates = iter(
        [
            {
                "schema": "oddcycle-local-hs-exact-v1",
                "status": "exact-local-interacting-hs-survivor",
            },
            {
                "schema": "oddcycle-local-hs-exact-v1",
                "status": "no-positive-exact-kernel",
            },
            {
                "schema": "oddcycle-local-hs-exact-v1",
                "status": "exact-local-hs-gate-failed",
            },
            {
                "schema": "oddcycle-local-hs-exact-v1",
                "status": "exact-promotion-inconclusive",
                "reason": "synthetic",
            },
        ]
    )
    monkeypatch.setattr(
        runner,
        "build_word_dictionary",
        lambda _length: (object(),),
    )
    monkeypatch.setattr(
        runner,
        "exact_local_hs_certificate",
        lambda *_args, **_kwargs: next(certificates),
    )
    output = tmp_path / "promoted"

    summary = promote_from_payloads(
        [source],
        output,
        workers=1,
        resume=True,
    )

    assert summary.exact_survivors == 1
    assert summary.exact_rejected == 2
    assert summary.inconclusive == 1
    statuses = {
        json.loads(path.read_text())["scan_index"]:
        json.loads(path.read_text())["status"]
        for path in (output / "promotions").glob("*.json")
    }
    assert statuses == {
        0: "exact-survivor",
        1: "exact-rejected",
        2: "exact-rejected",
        3: "inconclusive",
    }


def test_run_cell_propagates_unexpected_compute_error_without_final_payload(
    monkeypatch,
    tmp_path,
):
    cell = BatchCell(
        id="portfolio-l1",
        mode="portfolio",
        max_word_length=1,
        sample_count=0,
    )
    monkeypatch.setattr(
        runner,
        "build_word_dictionary",
        lambda _length: (_ for _ in ()).throw(
            RuntimeError("synthetic unexpected failure")
        ),
    )

    with pytest.raises(RuntimeError, match="synthetic unexpected failure"):
        run_cell(cell, tmp_path)

    assert not (tmp_path / "cells" / f"{cell.id}.json").exists()
    assert not (tmp_path / "cells" / f"{cell.id}.json.tmp").exists()
    assert not (tmp_path / "manifest.jsonl").exists()
