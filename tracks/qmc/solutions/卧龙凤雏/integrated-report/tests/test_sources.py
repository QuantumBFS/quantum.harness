import math


def _load(repo_root):
    from analysis.sources import load_all_models

    return load_all_models(repo_root)


def test_loads_three_frozen_models(repo_root):
    models = _load(repo_root)

    assert [model.slug for model in models] == [
        "clean-ising",
        "nishimori-ising",
        "weak-self-dual",
    ]
    assert [model.target for model in models] == [0.5, 0.464, 0.447]


def test_loads_expected_primary_estimates(repo_root):
    clean, nishimori, weak = _load(repo_root)

    assert clean.estimate == 0.4987390622675896
    assert clean.exact_estimate == 0.49942440242816655
    assert nishimori.estimate == 0.45646940076821396
    assert weak.estimate == 0.44410663549565277


def test_intervals_contain_estimates_and_required_gates_pass(repo_root):
    for model in _load(repo_root):
        assert model.ci95[0] <= model.estimate <= model.ci95[1]
        assert model.standard_error > 0.0
        assert math.isfinite(model.runtime_s) and model.runtime_s > 0.0
        assert all(not gate.required or gate.passed for gate in model.gates)


def test_parameters_figures_tables_and_provenance_are_complete(repo_root):
    for model in _load(repo_root):
        assert model.parameters
        assert all(len(row) == 4 for row in model.parameters)
        assert len(model.figures) >= 5
        assert all(path.is_file() for path in model.figures)
        assert model.tables
        assert model.provenance
        assert all(len(digest) == 64 for digest in model.provenance.values())
