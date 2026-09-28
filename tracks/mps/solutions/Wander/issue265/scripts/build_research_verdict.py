#!/usr/bin/env python3
"""Build the Phase-0 preregistered verdict and pilot report."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.research_protocol import load_decision_rules
from src.research_verdict import evaluate_verdict


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _pilot_report(
    verdict: dict,
    evidence: dict,
    bridge: dict,
    tension: dict,
) -> str:
    late = bridge["late_window"]
    baseline = bridge["baseline"]
    bootstrap = bridge["bootstrap"]
    closure = tension["constant_closure"]
    flow = bridge["parameter_flows"]
    return rf"""# Phase 0 pilot: microscopic moment law and finite-window Burgers

## Outcome

The current public dataset contains one weak rising domain wall. It supports a
high-accuracy finite-window scalar surrogate and a coefficient-level tangent
bridge, but it cannot decide cross-initial-condition universality or the
two-mode theory.

Machine verdict:

```json
{json.dumps(verdict, indent=2, ensure_ascii=False)}
```

## Reproduced baseline

- Constant profile closure:
  \(a={baseline['profile_a']:.8f}\),
  \(D_{{\\rm cl}}={baseline['profile_D']:.8f}\).
- Integrated profile error:
  \(E_U={closure['observed_window_profile_error']['integrated_relative_l2']:.6f}\)
  ({100 * closure['observed_window_profile_error']['integrated_relative_l2']:.3f}%).
- Width exponent on \(t=80\!-\!190\):
  \(\beta={baseline['width_exponent']:.6f}\).
- Moment-diffusivity exponent:
  \(\gamma={baseline['moment_diffusivity_exponent_direct']:.6f}\).
- Deterministic scalar continuation local exponent:
  {closure['extended_local_exponent']['at_t_200']:.4f} near \(t=200\),
  {closure['extended_local_exponent']['at_t_5000']:.4f} at \(t=5000\).

## New derivative-free bridge

On \(t={late['t_min']:.0f}\!-\!{late['t_max']:.0f}\), the microscopic
constitutive amplitude is estimated from

\[
W^{{3/2}}(t)=b+\frac{{3A_W}}{{2}}t
\]

without differentiating the data:

\[
A_W={late['A_width']:.8f}.
\]

The exact implicit Burgers width law gives

\[
D={late['D_width_implicit']:.8f},\qquad
v={late['v_width_implicit']:.8f},\qquad
a={late['a_width_implicit']:.8f}.
\]

Its tangent amplitude is

\[
A_B=2\sqrt{{Dv}}={late['A_bridge']:.8f},
\qquad
\frac{{A_B}}{{A_W}}={late['A_bridge_over_A_width']:.8f}.
\]

Thus the two descriptions agree internally at the moment level to
{100 * abs(late['A_bridge_over_A_width'] - 1):.3f}% on this window.
This is a same-dataset internal closure, not an independent microscopic
confirmation.

The infinite-temperature GHD value is

\[
A_\infty=\frac{{20\pi}}{{81}}={late['A_GHD']:.8f},
\qquad
\frac{{A_W}}{{A_\infty}}={late['A_width_over_A_GHD']:.6f}.
\]

The finite-time amplitude is {100 * (1 - late['A_width_over_A_GHD']):.2f}%
below the asymptotic prediction. Longer accepted quantum data are required to
test convergence.

## Physical-time block bootstrap

Using blocks of duration {bootstrap['block_duration']:.0f} and
{bootstrap['accepted_replicates']} accepted replicates:

- \(A_W\):
  [{bootstrap['A']['low']:.8f}, {bootstrap['A']['high']:.8f}].
- \(D\):
  [{bootstrap['D']['low']:.8f}, {bootstrap['D']['high']:.8f}].
- \(v\):
  [{bootstrap['v']['low']:.8f}, {bootstrap['v']['high']:.8f}].
- \(A_B/A_W\):
  [{bootstrap['A_bridge_over_A']['low']:.8f},
  {bootstrap['A_bridge_over_A']['high']:.8f}].
- \(W_*=D/v\):
  [{bootstrap['W_star']['low']:.4f}, {bootstrap['W_star']['high']:.4f}].

These intervals measure time-block sampling sensitivity of the single
trajectory. They do not include tensor-network truncation uncertainty or
between-initial-condition variation.

## Rolling coefficient flow

The four currently available preregistered windows give

\[
a(t_*)\sim t_*^{{{flow['a']['exponent']:.3f}}},
\qquad
D(t_*)\sim t_*^{{{flow['D']['exponent']:.3f}}},
\qquad
A_W(t_*)\sim t_*^{{{flow['A_width']['exponent']:.3f}}}.
\]

The near-zero power of \(A_W\) is encouraging for a stable microscopic
moment amplitude. The \(a,D\) powers are not yet precise evidence for the
ideal tangent values \((-1/3,+1/3)\): only four overlapping windows are
available, the earliest windows are preasymptotic, and no independent
initial condition is present.

## What Phase 0 establishes

1. The public-data baseline is exactly reproduced.
2. The \(W^{{3/2}}\) and implicit-width estimators avoid direct time
   differentiation.
3. The affine Burgers moment law is locally tangent to the square-root moment
   law at coefficient level.
4. Constant scalar Burgers is a supported local predictive surrogate for this
   trajectory.
5. The deterministic scalar continuation has the wrong long-time rarefaction
   trend for asymptotic KPZ.

## What Phase 0 cannot establish

1. It cannot show that one \(a,D\) works for both wall directions or multiple
   amplitudes.
2. It cannot derive a quadratic current for physical magnetization despite
   the spin-flip no-go.
3. It cannot distinguish two-mode NLFH from a more general memory/multimode
   theory.
4. It cannot confirm convergence \(A_W\to A_\infty\) without later quantum
   times.

## Next experimental gate

Generate the four convergence-pilot conditions registered in
`configs/burgers_research_matrix.json`: rising and falling \(\mu=0.05\)
walls, the double wall, and the \(m_0=0.05\) background wall. Only after
coarse/medium/fine agreement passes the frozen numerical gate should the full
amplitude and shape matrix be produced.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bridge",
        default=str(
            ROOT / "results_research_program" / "moment_bridge" / "summary.json"
        ),
    )
    parser.add_argument(
        "--tension",
        default=str(ROOT / "results_tension_resolution" / "summary.json"),
    )
    parser.add_argument(
        "--rules",
        default=str(ROOT / "configs" / "burgers_decision_rules.json"),
    )
    parser.add_argument(
        "--outdir",
        default=str(ROOT / "results_research_program"),
    )
    parser.add_argument(
        "--expect-phase0",
        action="store_true",
        help="Fail unless the single-trajectory verdict has the frozen scope.",
    )
    args = parser.parse_args()

    bridge = _load(Path(args.bridge))
    tension = _load(Path(args.tension))
    rules = load_decision_rules(Path(args.rules))
    late = bridge["late_window"]
    closure = tension["constant_closure"]

    evidence = {
        "phase": "phase_0_public_single_trajectory_pilot",
        "coverage": {
            "n_primary_conditions": 1,
            "has_both_orientations": False,
            "has_blinded_future_test": False,
            "has_current_observable": False,
            "has_fcs": False,
        },
        "convergence": {
            "status": "not_available_legacy",
            "note": (
                "The published NPZ has no coarse/medium/fine tensor-network "
                "ladder; it is retained for the internal Phase-0 audit."
            ),
        },
        "universal_scalar": {
            "field_identified": False,
            "controlled_derivation": False,
        },
        "finite_window": {
            "within_condition_integrated_error": closure[
                "observed_window_profile_error"
            ]["integrated_relative_l2"],
            "tangent_ratio": late["A_bridge_over_A_width"],
            "long_continuation_exposes_ballistic_crossover": bool(
                closure["extended_local_exponent"]["at_t_5000"]
                > closure["extended_local_exponent"]["at_t_200"]
            ),
        },
        "microscopic_moment": {
            "A_width_over_A_GHD": late["A_width_over_A_GHD"],
            "future_convergence_tested": False,
        },
        "two_mode": {"tested": False},
    }
    verdict_object = evaluate_verdict(evidence, rules)
    verdict = asdict(verdict_object)

    if args.expect_phase0:
        expected = {
            "universal_scalar": "unresolved",
            "finite_window_surrogate": "supported",
            "microscopic_moment_law": "not_rejected",
            "two_mode": "not_tested",
            "overall": "insufficient_observables",
        }
        observed = {key: verdict[key] for key in expected}
        if observed != expected:
            raise RuntimeError(
                f"Phase-0 verdict escaped its evidence scope: {observed}"
            )

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "phase0_evidence.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n"
    )
    (outdir / "verdict.json").write_text(
        json.dumps(verdict, indent=2, ensure_ascii=False) + "\n"
    )
    (outdir / "PILOT_REPORT.md").write_text(
        _pilot_report(verdict, evidence, bridge, tension)
    )
    print(f"[OK] wrote Phase-0 verdict to {outdir / 'verdict.json'}")


if __name__ == "__main__":
    main()
