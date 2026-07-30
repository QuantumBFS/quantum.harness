import pytest

from paper_data import load_paper_data


def test_headline_values_are_loaded_from_frozen_sources(repo_root):
    data = load_paper_data(repo_root)

    assert data.clean.c_eff == pytest.approx(0.4987390622675896)
    assert data.clean.exact_c == pytest.approx(0.49942440242816655)
    assert data.nishimori.c_eff == pytest.approx(0.45646940076821396)
    assert data.nishimori.ci95 == pytest.approx(
        (0.44006391478771134, 0.4723035402043263)
    )
    assert data.weak.c_eff == pytest.approx(0.44410663549565277)
    assert data.learning.candidate_phi_pi == pytest.approx(0.30)


def test_learning_result_remains_exploratory(repo_root):
    learning = load_paper_data(repo_root).learning

    assert learning.entanglement_c_eff == pytest.approx(3.060739513110786)
    assert learning.casimir_c_eff == pytest.approx(12.579932843147617)
    assert learning.alpha_stable is False
    assert learning.estimator_agrees is False
    assert learning.central_charge_published is False
    assert learning.claim_reasons == (
        "diii_transition_not_bracketed",
        "anisotropy_unstable",
        "estimator_disagreement",
    )


def test_learning_summary_matches_frozen_pointer(repo_root):
    data = load_paper_data(repo_root)

    assert data.learning.summary_sha256 == (
        "cc08a6e6d6d414046c744b4d29d48f112d44526dfc2145b867aae01f07d53c33"
    )


def test_benchmark_required_gates_pass(repo_root):
    data = load_paper_data(repo_root)

    for benchmark in (data.clean, data.nishimori, data.weak):
        assert benchmark.gates
        assert benchmark.widths
        assert benchmark.source_hashes
