import importlib.util
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004"


def load_module(name):
    for module_name in [
        "config",
        "systems",
        "pulses",
        "dynamics",
        "open_loop",
        "hessian",
        "device",
        "optimizers",
        "baselines",
        "experiments",
        "analysis",
        "plotting",
    ]:
        sys.modules.pop(module_name, None)
    sys.path.insert(0, str(ATTEMPT))
    spec = importlib.util.spec_from_file_location(name, ATTEMPT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_attempt_004_default_sweeps_have_required_axes():
    config = load_module("config")
    smoke = config.default_smoke_sweep()
    full = config.default_full_sweep()

    assert {system.name for system in smoke.systems} == {"one_qubit_x", "two_qubit_cz"}
    assert {system.name for system in full.systems} == {"one_qubit_x", "two_qubit_cz"}
    assert full.gaps == ("small", "medium", "large")
    assert full.shots_per_query == (128, 512, 2048)
    assert full.seeds == tuple(range(8))
    assert max(full.cpu_array_cores_per_task * full.cpu_array_max_concurrent_tasks, 1) <= 200
    assert full.gpu_array_max_concurrent_tasks == 1
