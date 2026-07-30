"""Generate deterministic TeX macros from the frozen paper data."""

from __future__ import annotations

from pathlib import Path

from paper_data import load_paper_data


def tex_command(name: str, value: str) -> str:
    if not name.isascii() or not name.isalpha():
        raise ValueError(f"invalid TeX command name: {name}")
    if "\n" in value or "{" in value or "}" in value:
        raise ValueError(f"unsafe TeX command value: {name}")
    return rf"\newcommand{{\{name}}}{{{value}}}" + "\n"


def build_values(repo_root: Path, output: Path) -> Path:
    data = load_paper_data(repo_root)
    values = (
        ("CleanMCCharge", f"{data.clean.c_eff:.6f}"),
        ("CleanMCSE", f"{data.clean.standard_error:.6f}"),
        ("CleanExactCharge", f"{data.clean.exact_c:.6f}"),
        ("CleanCILow", f"{data.clean.ci95[0]:.6f}"),
        ("CleanCIHigh", f"{data.clean.ci95[1]:.6f}"),
        ("NishimoriCharge", f"{data.nishimori.c_eff:.6f}"),
        ("NishimoriSE", f"{data.nishimori.standard_error:.6f}"),
        ("NishimoriCILow", f"{data.nishimori.ci95[0]:.6f}"),
        ("NishimoriCIHigh", f"{data.nishimori.ci95[1]:.6f}"),
        ("WeakCharge", f"{data.weak.c_eff:.6f}"),
        ("WeakSE", f"{data.weak.standard_error:.6f}"),
        ("WeakCILow", f"{data.weak.ci95[0]:.6f}"),
        ("WeakCIHigh", f"{data.weak.ci95[1]:.6f}"),
        ("LearningCandidate", f"{data.learning.candidate_phi_pi:.2f}"),
        ("LearningEntanglementCharge", f"{data.learning.entanglement_c_eff:.6f}"),
        ("LearningEntanglementSE", f"{data.learning.entanglement_standard_error:.6f}"),
        ("LearningEntanglementCILow", f"{data.learning.entanglement_ci95[0]:.6f}"),
        ("LearningEntanglementCIHigh", f"{data.learning.entanglement_ci95[1]:.6f}"),
        ("LearningCasimirCharge", f"{data.learning.casimir_c_eff:.6f}"),
        ("LearningCasimirSE", f"{data.learning.casimir_standard_error:.6f}"),
        ("LearningCasimirCILow", f"{data.learning.casimir_ci95[0]:.6f}"),
        ("LearningCasimirCIHigh", f"{data.learning.casimir_ci95[1]:.6f}"),
        ("LearningAlpha", f"{data.learning.alpha:.6f}"),
        ("LearningPublished", str(data.learning.central_charge_published).lower()),
        ("LearningTasks", str(data.learning.streams)),
        ("LearningRuntime", f"{data.learning.elapsed_s:.3f}"),
        ("LearningSummaryHash", data.learning.summary_sha256),
    )
    payload = "% Generated from frozen result artifacts; do not edit.\n" + "".join(
        tex_command(name, value) for name, value in values
    )
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(payload, encoding="ascii")
    temporary.replace(output)
    return output


if __name__ == "__main__":
    package = Path(__file__).resolve().parent
    build_values(package.parents[4], package / "generated/headline_values.tex")
