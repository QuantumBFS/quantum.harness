from __future__ import annotations

import copy
import tomllib
from pathlib import Path

import numpy as np
import pytest

from spinglass3d.backend import BackendCase, NumpyReferenceBackend, SamplerBackend
from spinglass3d.model import EABonds, delta_energy, energy


def test_reference_backend_proposal_deltas_match_scalar_oracle() -> None:
    case = BackendCase.random(length=3, temperatures=4, samples=2, walkers=1, seed=90)
    backend = NumpyReferenceBackend(case)
    deltas = backend.all_proposal_deltas()
    for sample, temperature, walker, site in (
        (0, 0, 0, (0, 0, 0)),
        (0, 3, 0, (2, 1, 0)),
        (1, 2, 0, (1, 2, 2)),
    ):
        bonds = EABonds(case.bonds[sample])
        expected = delta_energy(
            case.spins[sample, temperature, walker],
            bonds,
            site,
        )
        assert deltas[(sample, temperature, walker) + site] == expected


def test_backend_protocol_checkpoint_measure_and_resources() -> None:
    case = BackendCase.random(length=3, temperatures=3, samples=1, walkers=2, seed=91)
    backend: SamplerBackend = NumpyReferenceBackend(case)
    before = backend.measure()
    backend.sweeps(2)
    after = backend.measure()
    assert before["energy"].shape == after["energy"].shape == (1, 3, 2)
    checkpoint = backend.checkpoint_state()
    assert checkpoint["spins"].shape == case.spins.shape
    resources = backend.resource_snapshot()
    assert resources["host_rss_bytes"] > 0
    assert resources["backend"] == "numpy-reference"


def test_jax_backend_proposal_deltas_and_decisions_match_reference() -> None:
    pytest.importorskip("jax")
    from spinglass3d.jax_backend import JaxBatchedBackend

    case = BackendCase.random(length=3, temperatures=4, samples=3, walkers=1, seed=92)
    reference = NumpyReferenceBackend(case)
    candidate = JaxBatchedBackend(case)
    np.testing.assert_allclose(
        candidate.all_proposal_deltas(),
        reference.all_proposal_deltas(),
        atol=1e-10,
        rtol=1e-12,
    )
    uniforms = np.random.default_rng(93).random(case.spins.shape)
    np.testing.assert_array_equal(
        candidate.accept_decisions(uniforms),
        reference.accept_decisions(uniforms),
    )
    assert candidate.resource_snapshot()["float64_enabled"] is True


def test_jax_random_sequential_sweep_keeps_binary_state() -> None:
    pytest.importorskip("jax")
    from spinglass3d.jax_backend import JaxBatchedBackend

    case = BackendCase.random(length=3, temperatures=3, samples=2, walkers=1, seed=94)
    backend = JaxBatchedBackend(case)
    backend.sweeps(2)
    state = backend.checkpoint_state()["spins"]
    assert set(np.unique(state)) == {-1, 1}
    assert backend.accepted_changes >= 0


def test_tensor_train_cores_are_a_float64_jax_pytree() -> None:
    jax = pytest.importorskip("jax")
    from spinglass3d.jax_backend import JaxTensorTrain
    from spinglass3d.tensor_train import LocalTensorTrain

    model = LocalTensorTrain.random(13, 4, seed=95)
    candidate = JaxTensorTrain.from_local(model)
    leaves = jax.tree_util.tree_leaves(candidate)
    assert len(leaves) == 13
    assert all(leaf.dtype.name == "float64" for leaf in leaves)
    tokens = np.random.default_rng(96).choice(
        np.array([-1, 1], dtype=np.int8),
        size=13,
    )
    assert float(candidate.value(tokens)) == pytest.approx(
        model.value(tokens),
        abs=1e-12,
        rel=0.0,
    )


def test_accelerator_dependency_is_optional() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    optional = data["project"]["optional-dependencies"]
    assert optional["accelerator"] == ["jax>=0.4"]
    assert "jax>=0.4" not in data["project"]["dependencies"]


def _deterministic_pt_case() -> BackendCase:
    bonds = np.ones((1, 2, 2, 2, 3), dtype=np.int8)
    ferro = np.ones((2, 2, 2), dtype=np.int8)
    checkerboard = np.fromfunction(
        lambda x, y, z: 1 - 2 * ((x + y + z) % 2),
        (2, 2, 2),
        dtype=int,
    ).astype(np.int8)
    stripe = np.fromfunction(
        lambda x, y, z: 1 - 2 * (x % 2),
        (2, 2, 2),
        dtype=int,
    ).astype(np.int8)
    spins = np.empty((1, 3, 2, 2, 2, 2), dtype=np.int8)
    spins[:, 0, :, ...] = ferro
    spins[:, 1, :, ...] = checkerboard
    spins[:, 2, :, ...] = stripe
    return BackendCase(
        spins=spins,
        bonds=bonds,
        betas=np.array([0.4, 0.8, 1.2]),
        seed=2026073190,
    )


def test_jax_pt_swaps_complete_replicas_with_scalar_action() -> None:
    pytest.importorskip("jax")
    from spinglass3d.jax_backend import JaxParallelTemperingBackend

    case = _deterministic_pt_case()
    backend = JaxParallelTemperingBackend(case)
    before = backend.spins.copy()
    accepted = backend.attempt_swaps(
        parity=0,
        uniforms=np.full((1, 2, 2), 0.5, dtype=np.float64),
    )
    assert accepted.shape == (1, 2, 2)
    assert np.all(accepted[:, 0, :])
    assert not np.any(accepted[:, 1, :])
    np.testing.assert_array_equal(backend.spins[:, 0], before[:, 1])
    np.testing.assert_array_equal(backend.spins[:, 1], before[:, 0])
    np.testing.assert_array_equal(backend.spins[:, 2], before[:, 2])
    np.testing.assert_array_equal(
        backend.replica_ids,
        np.array([[[1, 1], [0, 0], [2, 2]]]),
    )
    assert tuple(backend.swap_attempts) == (2, 0)
    assert tuple(backend.swap_accepts) == (2, 0)
    measured = backend.measure()["energy"]
    bonds = EABonds(case.bonds[0])
    for temperature in range(3):
        for walker in range(2):
            assert measured[0, temperature, walker] == energy(
                backend.spins[0, temperature, walker],
                bonds,
            )


def test_jax_pt_overlap_pairs_are_explicit_and_independent() -> None:
    pytest.importorskip("jax")
    from spinglass3d.jax_backend import JaxParallelTemperingBackend

    backend = JaxParallelTemperingBackend(_deterministic_pt_case())
    fields = backend.overlap_fields()
    assert fields.shape == (1, 3, 1, 2, 2, 2)
    np.testing.assert_array_equal(fields, 1)
    with pytest.raises(ValueError, match="even"):
        case = BackendCase.random(
            length=3,
            temperatures=3,
            samples=1,
            walkers=1,
            seed=2026073191,
        )
        JaxParallelTemperingBackend(case)


def test_jax_pt_checkpoint_resume_is_trajectory_identical() -> None:
    pytest.importorskip("jax")
    from spinglass3d.jax_backend import JaxParallelTemperingBackend

    case = BackendCase.random(
        length=3,
        temperatures=4,
        samples=1,
        walkers=4,
        seed=2026073192,
    )
    uninterrupted = JaxParallelTemperingBackend(case)
    uninterrupted.run_sweeps(2)
    checkpoint = uninterrupted.checkpoint_state()
    resumed = JaxParallelTemperingBackend(case)
    resumed.restore_checkpoint_state(checkpoint)
    uninterrupted.run_sweeps(2)
    resumed.run_sweeps(2)
    np.testing.assert_array_equal(resumed.spins, uninterrupted.spins)
    np.testing.assert_array_equal(resumed.replica_ids, uninterrupted.replica_ids)
    np.testing.assert_array_equal(resumed.swap_attempts, uninterrupted.swap_attempts)
    np.testing.assert_array_equal(resumed.swap_accepts, uninterrupted.swap_accepts)
    np.testing.assert_array_equal(resumed.round_trips, uninterrupted.round_trips)
    assert resumed.sweep_count == uninterrupted.sweep_count == 4


def _assert_pt_checkpoint_equal(
    observed: dict[str, object],
    expected: dict[str, object],
) -> None:
    assert set(observed) == set(expected)
    for name in observed:
        if name == "sampler":
            assert isinstance(observed[name], dict)
            assert isinstance(expected[name], dict)
            _assert_pt_checkpoint_equal(observed[name], expected[name])
        elif isinstance(observed[name], np.ndarray):
            np.testing.assert_array_equal(observed[name], expected[name])
        else:
            assert observed[name] == expected[name]


def test_jax_pt_checkpoint_validation_is_nonmutating() -> None:
    pytest.importorskip("jax")
    from spinglass3d.jax_backend import JaxParallelTemperingBackend

    case = BackendCase.random(
        length=3,
        temperatures=4,
        samples=1,
        walkers=4,
        seed=2026073196,
    )
    source = JaxParallelTemperingBackend(case)
    source.run_sweeps(3)
    state = source.checkpoint_state()
    state_before = copy.deepcopy(state)
    candidate = JaxParallelTemperingBackend(case)
    candidate_before = candidate.checkpoint_state()

    candidate.validate_checkpoint_state(state)

    _assert_pt_checkpoint_equal(state, state_before)
    _assert_pt_checkpoint_equal(candidate.checkpoint_state(), candidate_before)


def test_jax_pt_checkpoint_rejects_nonpermutation_replica_ids_before_mutation() -> None:
    pytest.importorskip("jax")
    from spinglass3d.jax_backend import JaxParallelTemperingBackend

    case = BackendCase.random(length=3, temperatures=4, samples=1, walkers=4, seed=2026073197)
    source = JaxParallelTemperingBackend(case)
    source.run_sweeps(2)
    state = source.checkpoint_state()
    state["replica_ids"][:, 0, :] = state["replica_ids"][:, 1, :]
    candidate = JaxParallelTemperingBackend(case)
    before = candidate.checkpoint_state()

    with pytest.raises(ValueError, match="replica IDs"):
        candidate.restore_checkpoint_state(state)

    _assert_pt_checkpoint_equal(candidate.checkpoint_state(), before)


def test_jax_pt_checkpoint_rejects_invalid_round_trip_phase_before_mutation() -> None:
    pytest.importorskip("jax")
    from spinglass3d.jax_backend import JaxParallelTemperingBackend

    case = BackendCase.random(length=3, temperatures=4, samples=1, walkers=4, seed=2026073198)
    source = JaxParallelTemperingBackend(case)
    source.run_sweeps(2)
    state = source.checkpoint_state()
    state["round_trip_phase"][0, 0, 0] = 3
    candidate = JaxParallelTemperingBackend(case)
    before = candidate.checkpoint_state()

    with pytest.raises(ValueError, match="round-trip phase"):
        candidate.restore_checkpoint_state(state)

    _assert_pt_checkpoint_equal(candidate.checkpoint_state(), before)


@pytest.mark.parametrize("counter_case", ["local", "swap", "scalar_type"])
def test_jax_pt_checkpoint_rejects_inconsistent_counters_before_mutation(
    counter_case: str,
) -> None:
    pytest.importorskip("jax")
    from spinglass3d.jax_backend import JaxParallelTemperingBackend

    case = BackendCase.random(length=3, temperatures=4, samples=1, walkers=4, seed=2026073199)
    source = JaxParallelTemperingBackend(case)
    source.run_sweeps(2)
    state = source.checkpoint_state()
    if counter_case == "local":
        state["sampler"]["accepted_changes"] = state["sampler"]["proposed_changes"] + 1
    elif counter_case == "swap":
        state["swap_accepts"][0] = state["swap_attempts"][0] + 1
    else:
        state["sweep_count"] = True
    candidate = JaxParallelTemperingBackend(case)
    before = candidate.checkpoint_state()

    with pytest.raises((TypeError, ValueError), match="counter"):
        candidate.restore_checkpoint_state(state)

    _assert_pt_checkpoint_equal(candidate.checkpoint_state(), before)


@pytest.mark.parametrize("counter_case", ["local_proposals", "swap_attempts"])
def test_jax_pt_checkpoint_rejects_impossible_sweep_derived_counters_before_mutation(
    counter_case: str,
) -> None:
    pytest.importorskip("jax")
    from spinglass3d.jax_backend import JaxParallelTemperingBackend

    case = BackendCase.random(length=3, temperatures=4, samples=1, walkers=4, seed=2026073200)
    source = JaxParallelTemperingBackend(case)
    source.run_sweeps(2)
    state = source.checkpoint_state()
    if counter_case == "local_proposals":
        state["sampler"]["accepted_changes"] = 0
        state["sampler"]["proposed_changes"] = 0
    else:
        state["swap_attempts"] = state["swap_attempts"] + case.spins.shape[2]
    candidate = JaxParallelTemperingBackend(case)
    before = candidate.checkpoint_state()

    with pytest.raises(ValueError, match="counter"):
        candidate.restore_checkpoint_state(state)

    _assert_pt_checkpoint_equal(candidate.checkpoint_state(), before)


@pytest.mark.parametrize("state_case", ["round_trips", "endpoint_timer"])
def test_jax_pt_checkpoint_rejects_impossible_travel_state_before_mutation(
    state_case: str,
) -> None:
    pytest.importorskip("jax")
    from spinglass3d.jax_backend import JaxParallelTemperingBackend

    case = BackendCase.random(length=3, temperatures=4, samples=1, walkers=4, seed=2026073201)
    source = JaxParallelTemperingBackend(case)
    source.run_sweeps(2)
    state = source.checkpoint_state()
    if state_case == "round_trips":
        state["round_trips"].flat[0] = 1
    else:
        state["time_since_endpoint"].flat[0] = 4
    candidate = JaxParallelTemperingBackend(case)
    before = candidate.checkpoint_state()

    with pytest.raises(ValueError, match="counter|round.trip|timer|travel"):
        candidate.restore_checkpoint_state(state)

    _assert_pt_checkpoint_equal(candidate.checkpoint_state(), before)
