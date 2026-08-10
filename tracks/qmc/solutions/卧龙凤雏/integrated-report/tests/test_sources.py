import math
import shutil


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


def test_learning_mit_loads_only_the_hash_selected_frozen_summary(repo_root):
    from analysis.sources import load_learning_mit

    result = load_learning_mit(repo_root)

    assert result.summary_sha256 == (
        "cc08a6e6d6d414046c744b4d29d48f112d44526dfc2145b867aae01f07d53c33"
    )
    assert result.status == "xy_reproduced_diii_inconclusive"
    assert result.exploratory is True
    assert result.xy_bracket == (0.24, 0.25)
    assert result.diii_bracket is None
    assert result.candidate_status == "exploratory"
    assert result.candidate_phi_pi == 0.30
    assert result.entanglement_c_eff == 3.060739513110786
    assert result.entanglement_interval == (
        1.5716339582529457,
        4.549845067968627,
    )
    assert result.casimir_c_eff == 12.579932843147617
    assert result.casimir_interval == (
        10.727803858293923,
        14.610336665219892,
    )
    assert result.estimator_agrees is False
    assert result.claim_status == "exploratory"
    assert result.claim_reasons == (
        "diii_transition_not_bracketed",
        "anisotropy_unstable",
        "estimator_disagreement",
    )
    assert result.central_charge_published is False
    assert set(result.figures) == {"en", "zh"}
    assert all(len(paths) == 6 for paths in result.figures.values())
    assert all(path.is_file() for paths in result.figures.values() for path in paths)


def test_learning_mit_rejects_a_summary_that_does_not_match_frozen_hash(
    repo_root, tmp_path
):
    from analysis.sources import load_learning_mit

    pointer_dir = (
        tmp_path / "tracks/qmc/solutions/卧龙凤雏/learning-mit"
    )
    result_dir = tmp_path / "tracks/qmc/results/tampered"
    pointer_dir.mkdir(parents=True)
    (result_dir / "plots/en").mkdir(parents=True)
    (result_dir / "plots/zh").mkdir(parents=True)
    source = (
        repo_root
        / "tracks/qmc/results/learning-mit-production-v2-20260730-132322"
    )
    shutil.copy2(source / "summary.json", result_dir / "summary.json")
    for language in ("en", "zh"):
        for name in ("xy-phase-scan.png", "diii-phase-scan.png"):
            shutil.copy2(source / f"plots/{language}/{name}", result_dir / f"plots/{language}/{name}")
    pointer_dir.joinpath("FROZEN_RESULT").write_text(
        "result_path=tracks/qmc/results/tampered\n"
        f"summary_sha256={'0' * 64}\n"
        "status=xy_reproduced_diii_inconclusive\n",
        encoding="utf-8",
    )

    try:
        load_learning_mit(tmp_path)
    except ValueError as error:
        assert "SHA-256" in str(error)
    else:
        raise AssertionError("tampered frozen summary was accepted")
