import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from scalable_v1.contracts import ConstructionCertificate, ResourceMetrics, SampleBatch
from scalable_v1.resources import RuntimeMeter, peak_rss_bytes


def _resource_metrics(
    *,
    wall_seconds: float = 2.0,
    effective_sample_size: float = 50.0,
    n8_to_n6_time_ratio: float = 1.5,
    n8_to_n6_memory_ratio: float = 1.2,
) -> ResourceMetrics:
    return ResourceMetrics(
        placement="local", wall_seconds=wall_seconds, peak_rss_bytes=1024,
        peak_vram_bytes=None, checkpoint_bytes=512,
        estimator_evaluations=100, effective_sample_size=effective_sample_size,
        n8_smoke_complete=True, n8_to_n6_time_ratio=n8_to_n6_time_ratio,
        n8_to_n6_memory_ratio=n8_to_n6_memory_ratio, device_fingerprint="cpu:test",
    )


def test_sample_batch_rejects_wrong_count() -> None:
    with pytest.raises(ValueError, match="n_samples"):
        SampleBatch(np.zeros((3, 4)), n_samples=4, burn_in_steps=1024, seed=848)


def test_resource_record_computes_ess_rate() -> None:
    certificate = ConstructionCertificate(
        strict_lll=True,
        antisymmetric=True,
        scalable=True,
        trainable_parameters=100,
        statement="fixed LLL configuration space; no full-basis allocation",
    )
    metrics = ResourceMetrics(
        placement="local", wall_seconds=2.0, peak_rss_bytes=1024,
        peak_vram_bytes=None, checkpoint_bytes=512,
        estimator_evaluations=100, effective_sample_size=50.0,
        n8_smoke_complete=True, n8_to_n6_time_ratio=1.5,
        n8_to_n6_memory_ratio=1.2, device_fingerprint="cpu:test",
    )
    assert certificate.strict_lll
    assert metrics.ess_per_second == 25.0


def test_resource_metrics_rejects_nan_wall_seconds() -> None:
    with pytest.raises(ValueError, match="wall_seconds"):
        _resource_metrics(wall_seconds=float("nan"))


def test_resource_metrics_rejects_negative_effective_sample_size() -> None:
    with pytest.raises(ValueError, match="effective_sample_size"):
        _resource_metrics(effective_sample_size=-1.0)


@pytest.mark.parametrize(
    ("time_ratio", "memory_ratio"),
    [(float("nan"), 1.2), (1.5, float("nan"))],
)
def test_resource_metrics_rejects_nan_completed_smoke_ratio(
    time_ratio: float,
    memory_ratio: float,
) -> None:
    with pytest.raises(ValueError, match="ratios"):
        _resource_metrics(
            n8_to_n6_time_ratio=time_ratio,
            n8_to_n6_memory_ratio=memory_ratio,
        )


def test_runtime_meter_reports_positive_process_usage() -> None:
    with RuntimeMeter() as meter:
        payload = np.ones(1024, dtype=float)
        assert payload.sum() == 1024.0
    assert meter.wall_seconds > 0.0
    assert meter.peak_rss_bytes > 0


@pytest.mark.skipif(os.name != "nt", reason="Windows ctypes concurrency regression")
def test_peak_rss_bytes_is_thread_safe_on_windows() -> None:
    call_count = 2000
    with ThreadPoolExecutor(max_workers=32) as executor:
        futures = [executor.submit(peak_rss_bytes) for _ in range(call_count)]
    measurements = []
    failures = []
    for future in futures:
        try:
            measurements.append(future.result())
        except Exception as exc:
            failures.append(exc)
    assert not failures, f"{len(failures)} of {call_count} calls failed: {failures[:3]!r}"
    assert len(measurements) == call_count
    assert all(measurement > 0 for measurement in measurements)
