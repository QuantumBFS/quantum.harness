from src.progress_atlas.figures import core_hero_names


def test_core_hero_figure_names() -> None:
    assert set(core_hero_names()) == {
        "01_evidence_map",
        "02_time_coverage",
        "03_profile_current_convergence",
        "04_initial_state_dynamics",
    }
