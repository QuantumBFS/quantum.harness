from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
import importlib.util
import multiprocessing as mp
from pathlib import Path
import sys


def _runner():
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    path = scripts / "run_channel_reflection_validation.py"
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location(
            "run_channel_reflection_validation", path
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(scripts))


def test_reflection_candidate_is_parameter_free_and_default_off() -> None:
    runner = _runner()
    config, replicas, warmup, measurement, measure_every = runner._phase_spec(
        "m3_ed"
    )

    assert "temporal_reflection_updates" not in config.as_dict()
    reflected = replace(config, temporal_reflection_updates=True)
    assert reflected.as_dict()["temporal_reflection_updates"] is True
    assert (replicas, warmup, measurement, measure_every) == (4, 240, 800, 2)
    assert runner._seed("m3_ed", 0) == runner._seed("m3_ed", 0)
    assert runner._seed("m3_ed", 0) != runner._seed("m3_ed", 1)


def test_reflection_worker_runs_under_spawn_with_candidate_identity(
    tmp_path: Path,
) -> None:
    runner = _runner()
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    task = {
        "output_dir": str(tmp_path),
        "experiment_id": runner.EXPERIMENT_ID,
        "phase": "m3_ed",
        "arm": "channel_reflection",
        "replica": 0,
        "seed": 8124,
        "config": {
            "m": 3,
            "beta": 0.2,
            "dt": 0.1,
            "t": 0.2,
            "g_b_over_g_a": 0.5,
            "temporal_reflection_updates": True,
        },
        "warmup_sweeps": 1,
        "measurement_sweeps": 2,
        "measure_every": 1,
        "source_revision": "test",
        "m3_release_digest": None,
    }
    sys.path.insert(0, str(scripts))
    try:
        with ProcessPoolExecutor(
            max_workers=1, mp_context=mp.get_context("spawn")
        ) as executor:
            payload = executor.submit(
                runner.common._run_task, task
            ).result(timeout=30)
    finally:
        sys.path.remove(str(scripts))

    assert payload["experiment_id"] == runner.EXPERIMENT_ID
    assert payload["config"]["temporal_reflection_updates"] is True
    assert payload["temporal_reflection_proposed"] > 0
