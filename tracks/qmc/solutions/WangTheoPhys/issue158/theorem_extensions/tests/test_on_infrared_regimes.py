import json
import math
import os
from pathlib import Path
import subprocess
import sys

from scripts.on_infrared_regimes import infrared_integral, proxy_kernel


def _run(output: Path) -> dict:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = "."
    subprocess.run(
        [
            sys.executable,
            "scripts/on_infrared_regimes.py",
            "--output",
            str(output),
        ],
        check=True,
        env=environment,
    )
    return json.loads(output.read_text())


def test_proxy_kernels_have_the_registered_forms():
    k = 1e-4
    assert math.isclose(proxy_kernel(k, 1.75), k**1.75)
    assert math.isclose(
        proxy_kernel(k, 2.0),
        k**2 * math.log(math.e / k),
    )
    assert math.isclose(proxy_kernel(k, 2.25), k**2)


def test_infrared_regime_growth():
    small = 2**12
    large = 2**20
    finite_limit = 1.0 / (2.0 * math.pi * 0.25)
    assert infrared_integral(large, 1.75) < finite_limit
    assert (
        finite_limit - infrared_integral(large, 1.75)
        < finite_limit - infrared_integral(small, 1.75)
    )
    marginal_ratio = infrared_integral(large, 2.0) / math.log(
        math.log(math.e * large / (2.0 * math.pi))
    )
    short_range_ratio = infrared_integral(large, 2.25) / math.log(
        large / (2.0 * math.pi)
    )
    expected = 1.0 / (2.0 * math.pi)
    assert math.isclose(marginal_ratio, expected, rel_tol=2e-15)
    assert math.isclose(short_range_ratio, expected, rel_tol=2e-15)
    assert infrared_integral(large, 2.0) > infrared_integral(small, 2.0)
    assert infrared_integral(large, 2.25) > infrared_integral(small, 2.25)


def test_infrared_artifact_is_complete_and_reproducible(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    payload = _run(first)
    _run(second)
    assert first.read_bytes() == second.read_bytes()
    assert payload["schema"] == "issue158.on_infrared_regimes.v1"
    assert set(payload["regimes"]) == {"1.75", "2.00", "2.25"}
    assert payload["regimes"]["1.75"]["infrared_behavior"] == "finite"
    assert payload["regimes"]["2.00"]["infrared_behavior"] == "log log L"
    assert payload["regimes"]["2.25"]["infrared_behavior"] == "log L"
    assert "not Monte Carlo data" in payload["interpretation"]
