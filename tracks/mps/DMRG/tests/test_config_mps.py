from __future__ import annotations

import pytest

from vmcrg_ref.config import load_experiment_config


def test_load_experiment_config(tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        """
[model]
length = 45
coupling = 0.436
block_size = 3
rg_levels = 1
operator_count = 13

[mps]
chi = 4
symmetrize = true

[training]
walkers = 4
baseline_steps = 3
residual_steps = 5
sweeps_per_step = 2
alpha_learning_rate = 0.01
core_learning_rate = 0.001
linear_learning_rate = 0.0
gradient_clip = 5.0
cache_check_every = 2

[measurement]
thermalization_sweeps = 3
measurement_sweeps = 10
thinning = 1

[run]
seeds = [11, 12, 13]
output = "results/test"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = load_experiment_config(path)
    assert config.model.length == 45
    assert config.mps.chi == 4
    assert config.run.seeds == (11, 12, 13)
    assert config.coarse_length == 15


def test_invalid_config_rejects_nondivisible_rg(tmp_path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text(
        """
[model]
length = 20
coupling = 0.436
block_size = 3
rg_levels = 2
operator_count = 1
[mps]
chi = 2
[training]
walkers = 2
baseline_steps = 1
residual_steps = 1
sweeps_per_step = 1
alpha_learning_rate = 0.01
core_learning_rate = 0.001
[measurement]
thermalization_sweeps = 1
measurement_sweeps = 2
thinning = 1
[run]
seeds = [1]
output = "results/test"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"block_size\*\*rg_levels"):
        load_experiment_config(path)
