"""The delivery command must preserve the explicit held-out unseal boundary."""

from __future__ import annotations

from pathlib import Path


def test_delivery_script_orders_assets_and_never_unseals() -> None:
    script = (
        Path(__file__).resolve().parents[1] / "run_susy_hodge_delivery_v7.sh"
    ).read_text(encoding="utf-8")
    merge = script.index("merge_susy_hodge_pilot_v7.py")
    figure = script.index("make_susy_hodge_figure_v7.py")
    assets = script.index("make_susy_hodge_manuscript_assets_v7.py")
    compile_pdf = script.index("latexmk")
    archive_pdf = script.index("response_complex_memory_v7.pdf")
    supplement = script.index("supplement.tex")
    archive_supplement = script.index("response_complex_memory_supplement_v7.pdf")
    audit = script.index("verify_susy_hodge_delivery_v7.py")
    manuscript = script.index("verify_susy_hodge_manuscript_v7.py")

    assert (
        merge
        < figure
        < assets
        < compile_pdf
        < supplement
        < archive_pdf
        < archive_supplement
        < audit
        < manuscript
    )
    assert " unseal" not in script.lower()
    assert "analyze_susy_hodge_geometric_eth_v7.py unseal" not in script
