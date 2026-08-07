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


def test_attempt_004_systems_have_required_dimensions():
    config = load_module("config")
    systems = load_module("systems")

    one = systems.build_system(config.ONE_QUBIT_X)
    two = systems.build_system(config.TWO_QUBIT_CZ)

    assert one.target.shape == (2, 2)
    assert len(one.control_hamiltonians) == 2
    assert one.config.raw_dim == 16
    assert two.target.shape == (4, 4)
    assert len(two.control_hamiltonians) == 6
    assert two.config.raw_dim == 48


def test_attempt_004_dynamics_are_unitary_and_phase_invariant():
    config = load_module("config")
    systems = load_module("systems")
    pulses = load_module("pulses")
    dynamics = load_module("dynamics")

    system = systems.build_system(config.ONE_QUBIT_X)
    theta = pulses.initial_pulse(config.ONE_QUBIT_X, seed=2)
    unitary = dynamics.propagator(theta, system)
    identity = unitary.conj().T @ unitary

    assert float(abs(identity[0, 0] - 1.0)) < 1e-9
    assert float(abs(identity[1, 1] - 1.0)) < 1e-9
    assert float(dynamics.unitary_infidelity(system.target, system.target)) < 1e-12
    assert float(dynamics.unitary_infidelity(1j * system.target, system.target)) < 1e-12


def test_attempt_004_two_qubit_open_loop_reaches_cz_with_48_parameters():
    config = load_module("config")
    systems = load_module("systems")
    pulses = load_module("pulses")
    open_loop = load_module("open_loop")

    system = systems.build_system(config.TWO_QUBIT_CZ)
    start = pulses.initial_pulse(config.TWO_QUBIT_CZ, seed=0)
    cfg = config.OpenLoopConfig(
        steps=90,
        learning_rate=0.035,
        target_infidelity=2e-3,
        seed_scale=0.0,
    )

    result = open_loop.optimize_model_pulse(system, start, cfg)

    assert system.config.raw_dim == 48
    assert result.final_infidelity <= 2e-3
