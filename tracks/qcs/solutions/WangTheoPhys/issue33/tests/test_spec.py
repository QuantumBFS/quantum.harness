import pytest

from vqetape.spec import (
    CompileRequest,
    ProgramConfig,
    SpatialProgramConfig,
    TFIMVQESpec,
    TensorProgramConfig,
    dtype_bytes,
)


def test_tfim_spec_parameter_shape_and_count():
    spec = TFIMVQESpec(nqubits=5, depth=3)
    assert spec.parameter_shape == (3, 2, 5)
    assert spec.active_parameter_count == 3 * (2 * 5 - 1)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"nqubits": 1}, "nqubits"),
        ({"depth": 0}, "depth"),
        ({"dtype": "float32"}, "dtype"),
        ({"initial_state": "bell"}, "initial_state"),
    ],
)
def test_tfim_spec_rejects_invalid_values(kwargs, message):
    values = {"nqubits": 4, "depth": 2}
    values.update(kwargs)
    with pytest.raises(ValueError, match=message):
        TFIMVQESpec(**values)


def test_segmented_config_requires_scan_and_segment_length():
    with pytest.raises(ValueError, match="segmented"):
        ProgramConfig(
            control_flow="unrolled",
            adjoint="segmented",
            unroll=1,
            segment_length=2,
        )
    with pytest.raises(ValueError, match="segment_length"):
        ProgramConfig(control_flow="scan", adjoint="segmented", unroll=1)


def test_compile_request_requires_positive_budget_and_steps():
    spec = TFIMVQESpec(nqubits=4, depth=2)
    with pytest.raises(ValueError, match="memory_budget_bytes"):
        CompileRequest(spec=spec, memory_budget_bytes=0, expected_vqe_steps=10)
    with pytest.raises(ValueError, match="expected_vqe_steps"):
        CompileRequest(spec=spec, memory_budget_bytes=1024, expected_vqe_steps=0)


def test_dtype_bytes():
    assert dtype_bytes("complex64") == 8
    assert dtype_bytes("complex128") == 16


def test_request_round_trip():
    request = CompileRequest(
        spec=TFIMVQESpec(nqubits=4, depth=2),
        memory_budget_bytes=1024,
        expected_vqe_steps=10,
    )
    assert CompileRequest.from_dict(request.to_dict()) == request


def test_tensor_program_representation_round_trip():
    config = TensorProgramConfig(
        "greedy",
        "none",
        gate_representation="operator_schmidt",
    )
    assert TensorProgramConfig.from_dict(config.to_dict()) == config
    assert "operator-schmidt" in config.label


def test_tensor_program_rejects_unknown_gate_representation():
    with pytest.raises(ValueError, match="gate_representation"):
        TensorProgramConfig(
            "greedy",
            "none",
            gate_representation="sparse",
        )


def test_tensor_program_hamiltonian_representation_round_trip():
    config = TensorProgramConfig(
        "greedy",
        "none",
        hamiltonian_representation="mpo",
    )
    assert TensorProgramConfig.from_dict(config.to_dict()) == config
    assert "-mpo-" in config.label


def test_tensor_program_rejects_unknown_hamiltonian_representation():
    with pytest.raises(ValueError, match="hamiltonian_representation"):
        TensorProgramConfig(
            "greedy",
            "none",
            hamiltonian_representation="dense_matrix",
        )


def test_spatial_program_config_round_trip():
    config = SpatialProgramConfig(
        path_strategy="greedy",
        adjoint="segmented",
        unroll=2,
        segment_length=3,
    )
    assert SpatialProgramConfig.from_dict(config.to_dict()) == config
    assert config.label == "spatial-transfer-greedy-b1-segmented-u2-s3"


def test_spatial_config_round_trips_block_width():
    config = SpatialProgramConfig(
        "greedy",
        "remat",
        unroll=2,
        block_width=3,
    )

    assert SpatialProgramConfig.from_dict(config.to_dict()) == config
    assert "-b3-" in config.label


def test_explicit_spatial_adjoint_round_trip():
    config = SpatialProgramConfig(
        "greedy",
        "explicit",
        block_width=2,
        unroll=2,
    )

    assert SpatialProgramConfig.from_dict(config.to_dict()) == config
    assert "explicit" in config.label


@pytest.mark.parametrize(
    "symmetry",
    ["none", "z2-reference", "z2-native"],
)
def test_spatial_symmetry_mode_round_trip(symmetry):
    config = SpatialProgramConfig(
        "greedy",
        "default",
        block_width=2,
        symmetry=symmetry,
    )

    assert SpatialProgramConfig.from_dict(config.to_dict()) == config
    if symmetry == "none":
        assert "z2" not in config.label
    else:
        assert symmetry in config.label


def test_old_spatial_config_defaults_to_no_symmetry():
    payload = SpatialProgramConfig(
        "greedy",
        "default",
    ).to_dict()
    payload.pop("symmetry")

    assert (
        SpatialProgramConfig.from_dict(payload).symmetry
        == "none"
    )


def test_spatial_config_rejects_nonpositive_block_width():
    with pytest.raises(ValueError, match="block_width"):
        SpatialProgramConfig(
            "greedy",
            "default",
            block_width=0,
        )


def test_old_spatial_config_defaults_to_width_one():
    payload = {
        "path_strategy": "greedy",
        "adjoint": "default",
        "unroll": 1,
        "segment_length": None,
        "column_paths": None,
        "representation": "spatial_transfer",
    }

    assert SpatialProgramConfig.from_dict(payload).block_width == 1


def test_spatial_program_paths_round_trip():
    paths = (
        ((0, 1), (0, 1)),
        ((0, 1), (0, 1), (0, 1)),
        ((0, 1),),
    )
    config = SpatialProgramConfig(
        path_strategy="random-greedy",
        adjoint="default",
        column_paths=paths,
    )

    assert SpatialProgramConfig.from_dict(config.to_dict()) == config
    assert config.column_paths == paths


@pytest.mark.parametrize(
    "kwargs",
    [
        {"path_strategy": "unknown", "adjoint": "default"},
        {"path_strategy": "greedy", "adjoint": "unknown"},
        {
            "path_strategy": "greedy",
            "adjoint": "default",
            "symmetry": "unknown",
        },
        {"path_strategy": "greedy", "adjoint": "default", "unroll": 0},
        {
            "path_strategy": "greedy",
            "adjoint": "segmented",
            "segment_length": None,
        },
        {
            "path_strategy": "greedy",
            "adjoint": "default",
            "segment_length": 2,
        },
        {
            "path_strategy": "greedy",
            "adjoint": "default",
            "column_paths": (((0, 1),),),
        },
    ],
)
def test_spatial_program_config_rejects_invalid_values(kwargs):
    with pytest.raises(ValueError):
        SpatialProgramConfig(**kwargs)
