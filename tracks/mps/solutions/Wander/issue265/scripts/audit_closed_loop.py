#!/usr/bin/env python3
"""Build a machine-readable and human-readable verdict for the full loop."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.fcs_closure_audit import published_fcs_audit


OUTPUT = ROOT / "results_closed_loop"


def load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text())


def main() -> None:
    tension = load_json("results_tension_resolution/summary.json")
    mechanism = load_json("results_analytic_mechanism/summary.json")
    fcs = published_fcs_audit()

    closure = tension["constant_closure"]
    spin = mechanism["linear_response_and_symmetry"]
    moment = mechanism["moment_transport"]
    prediction = fcs["independent_two_burgers"]
    experiment = fcs["experiment"]

    propositions = [
        {
            "id": "P1",
            "claim": "The Delta=1 XXZ chain has an exact magnetization continuity law.",
            "verdict": "proved",
            "reason": "It follows directly from the Heisenberg commutator and fixes the microscopic spin current.",
        },
        {
            "id": "P2",
            "claim": "Microscopic GHD exactly reduces to only the fields m and phi.",
            "verdict": "not_proved",
            "reason": "The reduction uses the explicit moment closure I2 approximately proportional to I0, then adds Markovian diffusion and noise.",
        },
        {
            "id": "P3",
            "claim": "At the equal-coupling fixed point, u_plus=m+phi and u_minus=m-phi obey opposite-chirality Burgers equations.",
            "verdict": "conditionally_proved",
            "reason": "The diagonalization is exact algebra once the two-mode closure, equal nonlinear couplings, equal diffusion, and the stochastic effective description are assumed.",
        },
        {
            "id": "P4",
            "claim": "Equilibrium magnetization-transfer odd cumulants vanish.",
            "verdict": "proved",
            "reason": "Spin-flip and reflection symmetry make the transfer distribution even; the opposite chiral modes provide a compatible mechanism.",
        },
        {
            "id": "P5",
            "claim": "Two independent opposite Baik-Rains modes quantitatively explain the full counting statistics.",
            "verdict": "falsified_at_accessible_times",
            "reason": (
                f"They predict excess kurtosis {prediction['combined_excess_kurtosis']:.3f}, "
                f"whereas experiment reports {experiment['excess_kurtosis']:.2f}"
                f"+/-{experiment['stderr']:.2f}; longer-time QGF work trends to zero or weakly negative kurtosis."
            ),
        },
        {
            "id": "P6",
            "claim": "Noise averaging a stochastic Burgers equation gives the deterministic Kharkov equation.",
            "verdict": "disproved",
            "reason": "The averaged nonlinear flux contains <u^2>=<u>^2+Var(u), so a variance-flux term remains.",
        },
        {
            "id": "P7",
            "claim": "The Kharkov scalar quadratic current is a universal one-field constitutive law for physical magnetization.",
            "verdict": "disproved",
            "reason": "A fixed quadratic flux is even in m, while spin flip requires the physical magnetization current to be odd.",
        },
        {
            "id": "P8",
            "claim": "The Kharkov deterministic PDE is an accurate finite-window surrogate for the published wall trajectory.",
            "verdict": "supported",
            "reason": (
                f"The full-window profile error is {100 * closure['observed_window_profile_error']['integrated_relative_l2']:.3f}% "
                f"with a={closure['fit']['a']:.5f}, D={closure['fit']['D0']:.5f}."
            ),
        },
        {
            "id": "P9",
            "claim": "The same deterministic PDE has asymptotic KPZ width t^(2/3).",
            "verdict": "disproved",
            "reason": (
                "Its rising-wall Riemann solution is a rarefaction with asymptotic ballistic width. "
                f"The numerical local exponent already drifts from {closure['extended_local_exponent']['at_t_200']:.3f} "
                f"at t~200 to {closure['extended_local_exponent']['at_t_5000']:.3f} at t=5000."
            ),
        },
    ]

    summary = {
        "scope": "Delta=1 high-temperature isotropic Heisenberg/XXZ hydrodynamics",
        "data_source": tension["source_meta"]["source"],
        "public_profile_evidence": {
            "spin_flip_antisymmetry_error": spin["spin_flip_antisymmetry_error"],
            "width_exponent_80_190": moment["width_exponent"],
            "moment_diffusivity_exponent": moment[
                "moment_diffusivity_exponent_direct"
            ],
            "constant_closure": closure,
        },
        "published_fcs_evidence": fcs,
        "propositions": propositions,
        "bottom_line": {
            "proved_or_supported": ["P1", "P3 (conditional)", "P4", "P8"],
            "disproved_or_falsified": ["P5 (finite time)", "P6", "P7", "P9"],
            "open": ["P2", "asymptotic quantitative validity of the two-mode truncation"],
            "closed_loop_verdict": (
                "The exact identity 'Kharkov deterministic scalar Burgers = "
                "noise-averaged two-Burgers magnetization dynamics' is false. "
                "The defensible relation is that both reproduce selected "
                "low-order finite-window signatures, while the microscopic "
                "two-mode theory and the learned scalar surrogate are distinct "
                "effective descriptions."
            ),
        },
    }

    lines = [
        "# Closed-loop verdict",
        "",
        "## Bottom line",
        "",
        summary["bottom_line"]["closed_loop_verdict"],
        "",
        "## Proposition audit",
        "",
        "| ID | Verdict | Claim | Reason |",
        "|---|---|---|---|",
    ]
    for item in propositions:
        reason = item["reason"].replace("|", "\\|")
        claim = item["claim"].replace("|", "\\|")
        lines.append(
            f"| {item['id']} | `{item['verdict']}` | {claim} | {reason} |"
        )
    lines.extend(
        [
            "",
            "## Numeric anchors",
            "",
            f"- Public-wall constant closure: `a={closure['fit']['a']:.5f}`, "
            f"`D={closure['fit']['D0']:.5f}`, integrated profile error "
            f"`{100 * closure['observed_window_profile_error']['integrated_relative_l2']:.3f}%`.",
            f"- Public-wall width exponent on `t=80..190`: "
            f"`{moment['width_exponent']:.4f}`; moment diffusivity exponent "
            f"`{moment['moment_diffusivity_exponent_direct']:.4f}`.",
            f"- Deterministic-PDE local width exponent: "
            f"`{closure['extended_local_exponent']['at_t_200']:.4f}` near `t=200`, "
            f"`{closure['extended_local_exponent']['at_t_5000']:.4f}` at `t=5000`.",
            f"- Independent two-Burgers excess kurtosis: "
            f"`{prediction['combined_excess_kurtosis']:.3f}`; experiment: "
            f"`{experiment['excess_kurtosis']:.2f} +/- {experiment['stderr']:.2f}`.",
            "",
            "The quoted standard-error separation is a finite-time diagnostic, "
            "not an asymptotic theorem. The symmetry and nonlinear-averaging "
            "no-go statements do not depend on this finite-time comparison.",
            "",
        ]
    )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    )
    (OUTPUT / "REPORT.md").write_text("\n".join(lines))
    print(f"Wrote {OUTPUT / 'summary.json'}")
    print(f"Wrote {OUTPUT / 'REPORT.md'}")


if __name__ == "__main__":
    main()
