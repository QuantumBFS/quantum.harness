from __future__ import annotations

from scalable_v1.routes.cf_operator_nqs.microbenchmark import classify_record


def _record(*, batch_size: int = 512, median_l2: float = 0.30) -> dict[str, object]:
    return {
        "n_electrons": 6,
        "two_q": 15,
        "batch_size": batch_size,
        "warmup_repetitions": 2,
        "measured_repetitions": 5,
        "compile_seconds": 10.0,
        "sector_median_seconds": {"l0": 0.20, "l2": median_l2},
        "peak_rss_bytes": 1024,
        "finite": True,
    }


def test_classifier_accepts_frozen_full_shape_inside_limits() -> None:
    result = classify_record(_record())

    assert result["classification"] == "GREEN"
    assert result["projected_action_seconds"] == 10.0 + 2 * 2048 * 0.30


def test_classifier_rejects_reduced_batch() -> None:
    assert classify_record(_record(batch_size=8))["classification"] == "RED"


def test_classifier_rejects_slow_full_shape() -> None:
    assert classify_record(_record(median_l2=0.90))["classification"] == "RED"
