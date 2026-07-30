from __future__ import annotations

from pathlib import Path
import sys

import pytest

TRIQS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRIQS_DIR))

from artifacts import canonical_json, sha256_bytes
from publication import publish_run, validate_published_run
from reduce import effective_samples, independent_chain_statistics
from validate_existing import resolve_current


def test_independent_chain_statistics_preserve_means_and_student_interval():
    result = independent_chain_statistics([1.0, 2.0, 3.0, 4.0])
    assert result["chain_values"] == [1.0, 2.0, 3.0, 4.0]
    assert result["mean"] == 2.5
    assert result["standard_error"] == pytest.approx(0.6454972243679028)
    assert result["degrees_of_freedom"] == 3
    assert result["student_quantile_95"] == 3.182446305284263
    half = 3.182446305284263 * result["standard_error"]
    assert result["interval_95"] == pytest.approx([2.5 - half, 2.5 + half])
    for count in (3, 5):
        with pytest.raises(ValueError):
            independent_chain_statistics([1.0] * count)


def test_effective_samples_uses_tau_floor_and_rejects_bad_values():
    assert effective_samples(1_000_000, 0.5) == 500_000
    assert effective_samples(1_000_000, 1.0) == 500_000
    assert effective_samples(1_000_000, 5.0) == 100_000
    assert effective_samples(1_000_000, 5.1) == 98_039
    with pytest.raises(ValueError):
        effective_samples(0, 1.0)


def test_publication_is_immutable_hash_complete_and_revalidated(tmp_path):
    summary_payload = {
        "artifact_type": "cthyb_summary",
        "schema_version": 2,
        "status": "accepted",
    }
    summary = {
        "payload": summary_payload,
        "sha256": sha256_bytes(canonical_json(summary_payload)),
    }
    chains = []
    for index in range(4):
        chain = tmp_path / f"source-{index}"
        chain.mkdir()
        (chain / "raw.h5").write_bytes(f"raw-{index}".encode())
        (chain / "chain-summary.json").write_text("{}\n")
        (chain / "completion.json").write_text("{}\n")
        (chain / "stdout.log").write_text("")
        (chain / "stderr.log").write_text("")
        chains.append(chain)
    root = tmp_path / "published"
    run = publish_run(root, summary, chains)
    validated = validate_published_run(run)
    assert validated["sha256"] == summary["sha256"]
    assert resolve_current(root) == run
    assert publish_run(root, summary, chains) == run
    (run / "chains" / "chain-000" / "raw.h5").write_bytes(b"changed")
    with pytest.raises(ValueError):
        validate_published_run(run)
