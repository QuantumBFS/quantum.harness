"""Evidence-language and render-level QA helpers."""

from __future__ import annotations


FORBIDDEN_WHEN_GATE_OPEN = ("verified", "validated", "gate accepted")


def audit_evidence_text(text: str, gate_accepted: bool) -> list[str]:
    if gate_accepted:
        return []
    lower = text.lower()
    return [token for token in FORBIDDEN_WHEN_GATE_OPEN if token in lower]


def audit_figure(fig, evidence_text: str, gate_accepted: bool = False) -> list[str]:
    errors = audit_evidence_text(evidence_text, gate_accepted)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    canvas = fig.bbox
    for text in fig.findobj(match=lambda x: hasattr(x, "get_window_extent")):
        if not hasattr(text, "get_text") or not text.get_text() or not text.get_visible():
            continue
        try:
            box = text.get_window_extent(renderer)
        except Exception:
            continue
        if box.width and box.height and not canvas.contains(*box.get_points()[0]):
            errors.append(f"text begins outside canvas: {text.get_text()[:40]}")
    return errors

