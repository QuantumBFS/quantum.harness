import vqetape


def test_public_api_exposes_end_to_end_layers():
    expected = {
        "compile_vqe",
        "train_vqe",
        "run_ansatz_growth",
        "TFIMVQESpec",
        "LongitudinalIsingSpec",
        "SpatialProgramConfig",
        "VQETrainingRequest",
        "AnsatzGrowthRequest",
    }

    assert expected <= set(vqetape.__all__)
    assert all(hasattr(vqetape, name) for name in expected)
