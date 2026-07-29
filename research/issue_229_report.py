#!/usr/bin/env python3
"""Recompute issue #229 matrix baselines and SU(2) evidence using NumPy only."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

import numpy as np

RESEARCH = Path(__file__).resolve().parent
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

from candidate.reducer import reduce_invariant_hermitian

ROOT = RESEARCH.parent
DEFAULT_PRIVATE = Path("/home/hzxiaxz/quantum.harness/research/benchmark/private")
DEFAULT_JSON = ROOT / "research" / "benchmark" / "issue-229-evidence.json"
DEFAULT_HTML = ROOT / "docs" / "discussion" / "issue-229-final.html"


def _relative_frobenius(value: np.ndarray, reference: np.ndarray) -> float:
    return float(np.linalg.norm(value) / max(1.0, np.linalg.norm(reference)))


def compute_abelian_instance(path: Path, corpus: str, spec: dict) -> dict:
    """Recompute all matrix-level finite-Abelian reduction diagnostics."""
    with np.load(path) as data:
        matrix = np.asarray(data["matrix"], dtype=np.complex128)
        generators = np.asarray(data["generators"], dtype=np.complex128)
        moduli = np.asarray(data["moduli"], dtype=np.int64)
    reduction = reduce_invariant_hermitian(matrix, generators, moduli)
    bases = [sector["basis"] for sector in reduction["sectors"]]
    blocks = [sector["block"] for sector in reduction["sectors"]]
    joined = np.concatenate(bases, axis=1)
    transformed = joined.conj().T @ matrix @ joined
    block_diagonal = np.zeros_like(transformed)
    offset = 0
    sectors = []
    for sector, block in zip(reduction["sectors"], blocks):
        size = block.shape[0]
        block_diagonal[offset : offset + size, offset : offset + size] = block
        sectors.append({"character": sector["character"], "dimension": size})
        offset += size
    reconstructed = joined @ block_diagonal @ joined.conj().T
    dense_spectrum = np.linalg.eigvalsh(matrix)
    reduced_spectrum = np.sort(np.concatenate([np.linalg.eigvalsh(block) for block in blocks]))
    commutators = [matrix @ generator - generator @ matrix for generator in generators]
    return {
        "id": spec["id"],
        "corpus": corpus,
        "family": spec["family"],
        "dimension": int(matrix.shape[0]),
        "moduli": moduli.tolist(),
        "sector_dimensions": [int(block.shape[0]) for block in blocks],
        "sectors": sectors,
        "spectrum_max_error": float(np.max(np.abs(dense_spectrum - reduced_spectrum))),
        "reconstruction_residual": _relative_frobenius(matrix - reconstructed, matrix),
        "orthogonality_residual": float(
            np.linalg.norm(joined.conj().T @ joined - np.eye(matrix.shape[0]))
        ),
        "block_leakage_residual": _relative_frobenius(transformed - block_diagonal, matrix),
        "symmetry_commutator_residual": max(
            _relative_frobenius(commutator, matrix) for commutator in commutators
        ),
        "ground_energy": float(dense_spectrum[0]),
        "cubic_work_proxy": float(
            matrix.shape[0] ** 3 / sum(block.shape[0] ** 3 for block in blocks)
        ),
    }


def compute_abelian_corpus(directory: Path, corpus: str) -> list[dict]:
    specs = json.loads((directory / "specs.json").read_text())["instances"]
    return [
        compute_abelian_instance(directory / f"{spec['id']}.npz", corpus, spec)
        for spec in specs
    ]


def heisenberg_operators(length: int) -> tuple[np.ndarray, np.ndarray]:
    """Return open-chain H=sum_i S_i.S_(i+1) and total S^2 for spin 1/2."""
    dimension = 1 << length
    hamiltonian = np.zeros((dimension, dimension), dtype=np.float64)
    spin_squared = np.eye(dimension, dtype=np.float64) * (0.75 * length)

    def add_pair(operator: np.ndarray, left: int, right: int, scale: float = 1.0) -> None:
        for state in range(dimension):
            left_spin = (state >> left) & 1
            right_spin = (state >> right) & 1
            operator[state, state] += scale * (0.25 if left_spin == right_spin else -0.25)
            if left_spin != right_spin:
                flipped = state ^ (1 << left) ^ (1 << right)
                operator[flipped, state] += scale * 0.5

    for site in range(length - 1):
        add_pair(hamiltonian, site, site + 1)
    for left in range(length):
        for right in range(left + 1, length):
            add_pair(spin_squared, left, right, scale=2.0)
    return hamiltonian, spin_squared


def _fixed_m_indices(length: int, spin: int) -> np.ndarray:
    up_spins = length // 2 + spin
    return np.asarray([state for state in range(1 << length) if state.bit_count() == up_spins])


def compute_su2_case(length: int, projection_tolerance: float = 1e-8) -> dict:
    """Reduce H into true SU(2) multiplicity blocks using M=S and S^2 projection."""
    hamiltonian, spin_squared = heisenberg_operators(length)
    dimension = hamiltonian.shape[0]
    dense_spectrum = np.linalg.eigvalsh(hamiltonian)
    reconstructed_spectrum = []
    sector_results = []
    for spin in range(length // 2 + 1):
        indices = _fixed_m_indices(length, spin)
        restricted_s2 = spin_squared[np.ix_(indices, indices)]
        s2_values, s2_vectors = np.linalg.eigh(restricted_s2)
        target = float(spin * (spin + 1))
        selected = np.abs(s2_values - target) < projection_tolerance
        fixed_m_basis = np.eye(dimension)[:, indices]
        basis = fixed_m_basis @ s2_vectors[:, selected]
        block = basis.T @ hamiltonian @ basis
        block = (block + block.T) / 2
        eigenvalues = np.linalg.eigvalsh(block)
        multiplicity = int(block.shape[0])
        reconstructed_spectrum.extend(np.repeat(eigenvalues, 2 * spin + 1))
        leakage = (np.eye(dimension) - basis @ basis.T) @ hamiltonian @ basis
        sector_results.append(
            {
                "spin": spin,
                "multiplicity": multiplicity,
                "block_dimension": multiplicity,
                "irrep_dimension": 2 * spin + 1,
                "eigenvalues": [float(value) for value in eigenvalues],
                "block_leakage_residual": _relative_frobenius(leakage, hamiltonian),
                "orthogonality_residual": float(
                    np.linalg.norm(basis.T @ basis - np.eye(multiplicity))
                ),
                "s2_projection_residual": _relative_frobenius(
                    spin_squared @ basis - target * basis, spin_squared
                ),
            }
        )
    reconstructed_spectrum = np.sort(np.asarray(reconstructed_spectrum))
    multiplicity_complete = sum(
        sector["irrep_dimension"] * sector["multiplicity"] for sector in sector_results
    )
    commutator = hamiltonian @ spin_squared - spin_squared @ hamiltonian
    return {
        "length": length,
        "boundary": "open",
        "coupling": 1.0,
        "dense_dimension": dimension,
        "sectors": sector_results,
        "multiplicity_completeness": multiplicity_complete,
        "spectrum_max_error": float(np.max(np.abs(dense_spectrum - reconstructed_spectrum))),
        "commutator_residual": float(
            np.linalg.norm(commutator)
            / max(1.0, np.linalg.norm(hamiltonian) * np.linalg.norm(spin_squared))
        ),
        "block_leakage_residual": max(
            sector["block_leakage_residual"] for sector in sector_results
        ),
        "orthogonality_residual": max(
            sector["orthogonality_residual"] for sector in sector_results
        ),
        "s2_projection_residual": max(
            sector["s2_projection_residual"] for sector in sector_results
        ),
        "ground_energy": float(dense_spectrum[0]),
        "cubic_work_proxy": float(
            dimension**3 / sum(sector["multiplicity"] ** 3 for sector in sector_results)
        ),
    }


def build_evidence(dev_dir: Path, private_dir: Path) -> dict:
    baseline = compute_abelian_corpus(dev_dir, "development")
    baseline.extend(compute_abelian_corpus(private_dir, "private"))
    return {
        "schema_version": 1,
        "generated_by": "research/issue_229_report.py",
        "finite_abelian_baseline": {
            "description": "Matrix-only finite-Abelian character-projector baseline; not an NC moment SDP or non-Abelian result.",
            "instances": baseline,
        },
        "su2_evidence": {
            "description": "Spin-1/2 antiferromagnetic Heisenberg open chain, H=sum_i S_i.S_(i+1), J=+1; true SU(2) irrep/multiplicity reduction.",
            "cases": [compute_su2_case(length) for length in (4, 6, 8)],
        },
    }


def _number(value: float) -> str:
    return f"{value:.3e}"


def _baseline_rows(instances: list[dict]) -> str:
    rows = []
    for item in instances:
        rows.append(
            "<tr data-baseline-instance><td>{}</td><td>{}</td><td>{}</td><td>{}</td>"
            "<td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{:.2f}x</td></tr>".format(
                html.escape(item["id"]), item["corpus"], item["family"], item["dimension"],
                "+".join(map(str, item["sector_dimensions"])), _number(item["spectrum_max_error"]),
                _number(item["reconstruction_residual"]), _number(item["orthogonality_residual"]),
                _number(item["block_leakage_residual"]),
                _number(item["symmetry_commutator_residual"]), item["cubic_work_proxy"],
            )
        )
    return "\n".join(rows)


def _su2_plot(cases: list[dict]) -> str:
    width, height = 760, 280
    left, right, top, bottom = 70, 720, 35, 225
    maximum = max(case["cubic_work_proxy"] for case in cases)
    bars = []
    bar_width = 110
    spacing = (right - left) / len(cases)
    for index, case in enumerate(cases):
        center = left + spacing * (index + 0.5)
        bar_height = (case["cubic_work_proxy"] / maximum) * (bottom - top)
        x = center - bar_width / 2
        y = bottom - bar_height
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width}" height="{bar_height:.1f}" class="bar"/>'
            f'<text x="{center:.1f}" y="{y - 8:.1f}" text-anchor="middle" class="number">'
            f'{case["cubic_work_proxy"]:.2f}x</text>'
            f'<text x="{center:.1f}" y="{bottom + 23}" text-anchor="middle" class="label">'
            f'L={case["length"]}, error={case["spectrum_max_error"]:.1e}</text>'
        )
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        'aria-label="SU(2) cubic work proxy and spectrum reconstruction error">'
        f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" class="axis"/>'
        + "".join(bars)
        + '<text x="22" y="140" transform="rotate(-90 22 140)" text-anchor="middle" '
        'class="label">D³ / Σ_S m_S³</text></svg>'
    )


def _su2_sections(cases: list[dict]) -> str:
    sections = []
    for case in cases:
        sector_rows = "".join(
            "<tr><td>{spin}</td><td>{multiplicity}</td><td>{block_dimension}</td>"
            "<td>{irrep_dimension}</td><td>{block_leakage_residual:.3e}</td>"
            "<td>{orthogonality_residual:.3e}</td><td>{eigenvalue_text}</td></tr>".format(
                **sector,
                eigenvalue_text=", ".join(f"{value:.12g}" for value in sector["eigenvalues"]),
            )
            for sector in case["sectors"]
        )
        sections.append(
            f'<section data-su2-case><h3>L={case["length"]}: D={case["dense_dimension"]}</h3>'
            f'<p>Spectrum error <b>{_number(case["spectrum_max_error"])}</b>; '
            f'[H,S²] residual <b>{_number(case["commutator_residual"])}</b>; '
            f'ground energy <b>{case["ground_energy"]:.15g}</b>; cubic proxy '
            f'<b>{case["cubic_work_proxy"]:.2f}x</b>; completeness '
            f'<b>{case["multiplicity_completeness"]}={case["dense_dimension"]}</b>.</p>'
            '<table><thead><tr><th>S</th><th>Multiplicity m_S</th><th>Reduced block</th>'
            '<th>Irrep dimension</th><th>Leakage</th><th>Orthogonality</th><th>Block eigenvalues</th>'
            f'</tr></thead><tbody>{sector_rows}</tbody></table></section>'
        )
    return "\n".join(sections)


def render_html(evidence: dict) -> str:
    baseline = evidence["finite_abelian_baseline"]["instances"]
    cases = evidence["su2_evidence"]["cases"]
    worst_spectrum = max(item["spectrum_max_error"] for item in baseline)
    worst_reconstruction = max(item["reconstruction_residual"] for item in baseline)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Issue #229 finite-Abelian baseline and SU(2) evidence</title>
<style>body{{margin:0;background:#f7f7f4;color:#171717;font:15px/1.5 system-ui,sans-serif}}main{{max-width:1120px;margin:auto;padding:30px 22px 55px}}h1{{font-size:25px}}h2{{margin-top:30px;border-bottom:1px solid #ccc}}h3{{margin-top:24px}}.kpis{{display:flex;gap:12px;flex-wrap:wrap}}.kpi{{background:white;border:1px solid #ddd;border-radius:7px;padding:12px;min-width:190px}}.value{{font-size:24px;font-weight:700}}.note{{color:#555}}table{{border-collapse:collapse;width:100%;background:white;font-size:13px}}th,td{{padding:7px 8px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}}th{{position:sticky;top:0;background:#eee}}details{{border:1px solid #ddd;border-radius:7px;padding:10px;background:#fff;overflow:auto}}code{{background:#eee;padding:2px 4px}}svg{{max-width:100%;height:auto;background:#fff;border:1px solid #ddd;border-radius:7px;margin:10px 0}}.bar{{fill:#276fbf}}.axis{{stroke:#999}}.label{{font:12px system-ui,sans-serif;fill:#444}}.number{{font:12px system-ui,sans-serif;font-weight:700;fill:#111}}</style></head>
<body><main><h1>Issue #229: finite-Abelian baseline and SU(2) evidence</h1>
<p class="note">Generated reproducibly with NumPy 2.5.1. The three evidence layers below are explicitly distinct.</p>
<div class="kpis"><div class="kpi"><div>Finite-Abelian baseline</div><div class="value">30 dev + 20 private</div></div>
<div class="kpi"><div>Baseline worst spectrum error</div><div class="value">{_number(worst_spectrum)}</div></div>
<div class="kpi"><div>Baseline worst reconstruction</div><div class="value">{_number(worst_reconstruction)}</div></div>
<div class="kpi"><div>New SU(2) cases</div><div class="value">L=4, 6, 8</div></div></div>
<h2>1. Existing NC moment-SDP evidence</h2>
<p>This prior finite-Abelian optimization result remains separate: CHSH Z₂ order 1 had dense/reduced optimum gap 1.33e-15 and 1.92x cubic cone proxy; the Pauli-style Z₂xZ₂ order-2 case had gap 2.74e-9 and 8.48x proxy. <strong>An NC moment SDP is not identified with non-Abelian symmetry.</strong></p>
<h2>2. Finite-Abelian matrix baseline (recomputed)</h2>
<p>These 50 matrix instances test character-projector reduction only. Residuals use Frobenius norms (reconstruction, leakage, and commutator relative to max(1, ‖H‖_F)); cubic proxy is D³ / Σ_k d_k³.</p>
<details open><summary><strong>All 50 baseline instances</strong> (collapse/expand)</summary><table><thead><tr><th>ID</th><th>Corpus</th><th>Family</th><th>D</th><th>Blocks</th><th>Spectrum error</th><th>Reconstruction</th><th>Orthogonality</th><th>Leakage</th><th>Symmetry commutator</th><th>Cubic proxy</th></tr></thead><tbody>
{_baseline_rows(baseline)}</tbody></table></details>
<h2>3. New true SU(2) irrep/multiplicity reduction</h2>
<p>Spin-1/2 antiferromagnetic Heisenberg open chain H=Σ_i S_i·S_(i+1), J=+1. In fixed M=S, S² projection selects one highest-weight vector per irrep copy, producing an m_S by m_S multiplicity block. Each block eigenvalue is repeated 2S+1 times to reconstruct the full spectrum. Cubic proxy is D³ / Σ_S m_S³.</p>
{_su2_plot(cases)}
{_su2_sections(cases)}
<h2>Reproduce</h2><p><code>/home/hzxiaxz/quantum.harness/.venv/bin/python research/issue_229_report.py --private-dir /home/hzxiaxz/quantum.harness/research/benchmark/private</code></p>
<p>Machine-readable artifact: <code>research/benchmark/issue-229-evidence.json</code>.</p>
<h2>Scope</h2><p>The 50-case baseline establishes finite-Abelian matrix reduction. The three Heisenberg-chain cases add genuine non-Abelian SU(2) evidence at L=4,6,8. Neither statement upgrades the finite-Abelian NC moment-SDP implementation itself into a non-Abelian SDP implementation.</p>
</main></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev-dir", type=Path, default=ROOT / "research" / "benchmark" / "dev")
    parser.add_argument("--private-dir", type=Path, default=DEFAULT_PRIVATE)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML)
    args = parser.parse_args()
    evidence = build_evidence(args.dev_dir, args.private_dir)
    args.json_output.write_text(json.dumps(evidence, indent=2) + "\n")
    args.html_output.write_text(render_html(evidence))
    print(f"wrote {args.json_output} and {args.html_output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
