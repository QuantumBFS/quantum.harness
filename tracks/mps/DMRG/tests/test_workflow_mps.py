from __future__ import annotations

import json

from vmcrg_ref.config import load_experiment_config
from vmcrg_ref.workflow import run_full_experiment


def test_smoke_workflow_writes_reproducible_artifacts(tmp_path) -> None:
    config_path = tmp_path / "smoke.toml"
    config_path.write_text(
        f"""
[model]
length = 9
coupling = 0.3
block_size = 3
rg_levels = 1
operator_count = 1
[mps]
chi = 2
symmetrize = true
[training]
walkers = 2
baseline_steps = 2
residual_steps = 2
sweeps_per_step = 1
alpha_learning_rate = 0.01
core_learning_rate = 0.001
gradient_clip = 5.0
cache_check_every = 1
canonicalize_every = 0
compiled = true
parallel_walkers = false
[measurement]
thermalization_sweeps = 2
measurement_sweeps = 8
thinning = 1
[run]
seeds = [123]
output = "{(tmp_path / 'unused').as_posix()}"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = load_experiment_config(config_path)
    output = tmp_path / "run"
    summary = run_full_experiment(config, seed=123, output=output)
    assert summary["status"] == "SMOKE_COMPLETE"
    assert (output / "baseline.json").is_file()
    assert (output / "training.json").is_file()
    assert (output / "evaluation.json").is_file()
    assert (output / "checkpoint" / "model.npz").is_file()
    saved = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert saved["seed"] == 123
    assert set(saved["evaluation"]) == {"unbiased", "traditional", "traditional_mps"}
