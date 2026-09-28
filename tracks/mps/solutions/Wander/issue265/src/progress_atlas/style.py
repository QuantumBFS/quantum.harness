"""Visual tokens for paper, atlas, and presentation outputs."""

from __future__ import annotations

from dataclasses import dataclass


COLORS = {
    "magnetization": "#2864A5",
    "current": "#D97732",
    "kpz": "#168C84",
    "memory": "#7656A5",
    "risk": "#B44545",
    "unresolved": "#8A9099",
    "ink": "#17202A",
    "paper": "#F8FAFC",
    "grid": "#D9E0E8",
}


@dataclass(frozen=True)
class StyleTarget:
    figsize: tuple[float, float]
    dpi: int
    title_size: float
    panel_size: float
    label_size: float
    min_font_size: float


STYLE_TARGETS = {
    "paper": StyleTarget((7.0, 4.8), 300, 10.5, 9.0, 7.5, 7.0),
    "atlas": StyleTarget((16.0, 10.8), 180, 22.0, 14.0, 10.0, 8.0),
    "presentation": StyleTarget((16.0, 9.0), 240, 26.0, 18.0, 13.0, 10.0),
}


def apply_style(target: str) -> StyleTarget:
    import matplotlib as mpl

    spec = STYLE_TARGETS[target]
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [
                "DejaVu Sans",
                "Noto Sans CJK SC",
                "Source Han Sans SC",
                "Hiragino Sans GB",
                "Heiti SC",
                "Source Sans 3",
            ],
            "mathtext.fontset": "stix",
            "font.size": spec.label_size,
            "axes.titlesize": spec.panel_size,
            "axes.labelsize": spec.label_size,
            "xtick.labelsize": spec.label_size,
            "ytick.labelsize": spec.label_size,
            "axes.edgecolor": COLORS["grid"],
            "axes.linewidth": 0.8,
            "axes.facecolor": "white",
            "figure.facecolor": COLORS["paper"],
            "savefig.facecolor": COLORS["paper"],
            # Preserve the designed canvas. A tight bounding box can silently
            # change the aspect ratio and crop text placed in page margins.
            "savefig.bbox": None,
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
        }
    )
    return spec
