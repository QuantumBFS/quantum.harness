from src.progress_atlas.qa import audit_evidence_text
from src.progress_atlas.style import STYLE_TARGETS


def test_paper_font_floor_is_seven_points() -> None:
    assert STYLE_TARGETS["paper"].min_font_size >= 7.0


def test_unaccepted_gate_cannot_use_verified_label() -> None:
    assert audit_evidence_text("verified", gate_accepted=False)
