from pathlib import Path

import pytest

from challenge15.cluster_profile import load_profile


ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "production" / "slurm" / "profiles"


def test_qdeshell_profile_is_exact_and_gpu_only():
    profile = load_profile(PROFILES / "qdeshell.json")
    assert profile.controller == "qdeshell"
    assert profile.scheduler == {
        "partition": "dzagnormal",
        "account": "giggleliu",
        "qos": "user_jiangweiqi",
        "nodes": 1,
        "ntasks": 1,
        "cpus_per_task": 8,
        "mem": "60000M",
        "time": "24:00:00",
        "gres": "gpu:NVIDIAA80080GBPCIeLC:1",
    }
    assert profile.array_concurrency == 5
    assert profile.allowed_roles == ("training", "coordinate")
    with pytest.raises(ValueError, match="CPU-only"):
        profile.require_role("exact")


def test_lasg02_profile_is_exact_and_cpu_only():
    profile = load_profile(PROFILES / "lasg02.json")
    assert profile.scheduler == {
        "partition": "ihicnormal",
        "account": "chenkun2025",
        "qos": "user_student090",
        "nodes": 1,
        "ntasks": 1,
        "cpus_per_task": 24,
        "mem": "80000M",
        "time": "24:00:00",
    }
    assert profile.array_concurrency == 1
    assert profile.allowed_roles == ("oracle", "exact", "reducer")


def test_wuzh_profile_fails_closed_until_discovered():
    assert not (PROFILES / "wuzh02.json").exists()
    with pytest.raises(ValueError, match="inactive"):
        load_profile(PROFILES / "wuzh02.inactive.json")
