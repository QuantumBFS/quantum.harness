import numpy as np

from vqetape.initialization import (
    initialize_parameters,
    recycle_parameters,
)
from vqetape.spec import ProgramConfig, TFIMVQESpec
from vqetape.training_spec import VQETrainingRequest


def _request(spec, initialization, **kwargs):
    return VQETrainingRequest(
        spec=spec,
        program=ProgramConfig("scan", "default"),
        optimizer="adam",
        initialization=initialization,
        target_energy_error=0.1,
        max_steps=10,
        **kwargs,
    )


def test_zero_and_random_initializations_are_deterministic():
    spec = TFIMVQESpec(nqubits=5, depth=2)
    zeros, zero_provenance = initialize_parameters(
        _request(spec, "zeros")
    )
    first, first_provenance = initialize_parameters(
        _request(spec, "random", seed=7)
    )
    second, _ = initialize_parameters(
        _request(spec, "random", seed=7)
    )
    different, _ = initialize_parameters(
        _request(spec, "random", seed=8)
    )

    np.testing.assert_array_equal(zeros, 0)
    np.testing.assert_array_equal(first, second)
    assert not np.array_equal(first, different)
    np.testing.assert_array_equal(first[:, 0, -1], 0)
    assert zero_provenance["policy"] == "zeros"
    assert first_provenance["seed"] == 7


def test_recycling_grows_chain_with_layer_means():
    source = TFIMVQESpec(nqubits=3, depth=1)
    target = TFIMVQESpec(nqubits=5, depth=1)
    parameters = np.asarray(
        [[[0.1, 0.3, 0.0], [1.0, 2.0, 3.0]]],
        dtype=np.float32,
    )

    recycled, provenance = recycle_parameters(
        parameters,
        source,
        target,
    )

    np.testing.assert_allclose(
        recycled[0, 0],
        [0.1, 0.3, 0.2, 0.2, 0.0],
    )
    np.testing.assert_allclose(
        recycled[0, 1],
        [1.0, 2.0, 3.0, 2.0, 2.0],
    )
    assert provenance["source_shape"] == [1, 2, 3]
    assert provenance["target_shape"] == [1, 2, 5]


def test_recycling_grows_depth_from_last_source_layer():
    source = TFIMVQESpec(nqubits=4, depth=2)
    target = TFIMVQESpec(nqubits=4, depth=4)
    parameters = np.arange(
        np.prod(source.parameter_shape),
        dtype=np.float32,
    ).reshape(source.parameter_shape)
    parameters[:, 0, -1] = 0

    recycled, _ = recycle_parameters(
        parameters,
        source,
        target,
    )

    np.testing.assert_allclose(recycled[:2], parameters)
    np.testing.assert_allclose(recycled[2], parameters[-1])
    np.testing.assert_allclose(recycled[3], parameters[-1])
    np.testing.assert_array_equal(recycled[:, 0, -1], 0)


def test_recycling_can_shrink_chain_and_depth():
    source = TFIMVQESpec(nqubits=6, depth=3)
    target = TFIMVQESpec(nqubits=4, depth=2)
    parameters = np.arange(
        np.prod(source.parameter_shape),
        dtype=np.float32,
    ).reshape(source.parameter_shape)

    recycled, _ = recycle_parameters(
        parameters,
        source,
        target,
    )

    np.testing.assert_allclose(
        recycled[:, 0, :-1],
        parameters[:2, 0, :3],
    )
    np.testing.assert_allclose(
        recycled[:, 1],
        parameters[:2, 1, :4],
    )
    np.testing.assert_array_equal(recycled[:, 0, -1], 0)


def test_initialize_recycled_parameters_uses_request_payload():
    source = TFIMVQESpec(nqubits=3, depth=1)
    target = TFIMVQESpec(nqubits=4, depth=2)
    payload = (
        (
            (0.1, 0.2, 0.0),
            (0.3, 0.4, 0.5),
        ),
    )
    values, provenance = initialize_parameters(
        _request(
            target,
            "recycled",
            recycled_source_spec=source,
            recycled_parameters=payload,
        )
    )

    assert values.shape == target.parameter_shape
    assert provenance["policy"] == "translation-mean-recycle"
