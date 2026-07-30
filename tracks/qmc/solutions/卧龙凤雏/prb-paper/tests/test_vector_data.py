import pytest

from vector_data import load_vector_plot_data


def test_vector_plot_data_loads_frozen_numeric_sources(repo_root):
    data = load_vector_plot_data(repo_root)

    assert data.clean.free_energy[0].width == 4
    assert data.clean.free_energy[-1].width == 20
    assert len(data.clean.free_energy) == 9
    assert data.clean.primary_mc_charge == pytest.approx(0.4987390622675896)

    assert len(data.nishimori.bootstrap) == 4000
    assert data.nishimori.free_energy[-1].width == 14
    assert data.nishimori.primary_charge == pytest.approx(0.45646940076821396)

    assert data.weak.finite_size[-1].width == 32
    assert len(data.weak.finite_size) == 14
    assert data.weak.primary_charge == pytest.approx(0.44410663549565277)

    assert len(data.learning.xy_evidence) == 6
    assert len(data.learning.diii_evidence) == 10
    assert data.learning.xy_bracket == pytest.approx((0.24, 0.25))
    assert data.learning.diii_bracket is None
    assert data.learning.candidate_phi_pi == pytest.approx(0.30)


def test_learning_vector_data_preserves_exploratory_claim_gates(repo_root):
    learning = load_vector_plot_data(repo_root).learning

    assert learning.entanglement.value == pytest.approx(3.060739513110786)
    assert learning.casimir.value == pytest.approx(12.579932843147617)
    assert learning.anisotropy.stable is False
    assert learning.estimator_comparison.agrees is False
    assert learning.central_charge_published is False
    assert learning.claim_reasons == (
        "diii_transition_not_bracketed",
        "anisotropy_unstable",
        "estimator_disagreement",
    )


def test_vector_data_rejects_wrong_learning_hash(repo_root, monkeypatch):
    import vector_data

    monkeypatch.setattr(vector_data, "EXPECTED_LEARNING_SHA256", "wrong")

    with pytest.raises(ValueError, match="learning summary hash"):
        load_vector_plot_data(repo_root)
