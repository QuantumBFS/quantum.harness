"""Quality-class rubric: does a candidate belong to a publishable quality class?

Two classes, both distilled from mentor-curated challenges:

  record class (#124-#128, curated by Fable+human):
    beat a pinned published number with a machine-checkable certificate.
    1. literature_anchor  - named target with pinned number + reference
    2. certificate_gate   - gate family in issue #133's machine-checkable kinds
    3. single_scalar      - one figure of merit with a push direction
    4. publishable_unit   - why passing the bar is a paper

  map class (#112, released by Kun Chen):
    chart a declared uncharted region, anchored by exact closed forms.
    1. literature_anchor  - exact anchor battery (integer degeneracies, closed forms)
    2. certificate_gate   - anchors machine-checkable ("off by one is a bug")
    3. uncharted_region   - the literature gap is named, with the boundary reference
    4. curve_merit        - deliverable is a curve family WITH an analytic cross-check
    5. publishable_unit   - why the map is a paper

A candidate is accepted if it fully passes either class. Presence of fields is
the structural layer; whether numbers are real and checkers run is verified
downstream (static fire / hop).
"""

import yaml

GATE_FAMILIES = {"certificate", "fresh_sample", "interval_arithmetic", "cost_arithmetic"}


def load(path):
    with open(path) as f:
        return yaml.safe_load(f)


def _record_checks(c):
    return {
        "literature_anchor": bool(c["target"].get("pinned_number")) and bool(c["target"].get("reference")),
        "certificate_gate": c["gate"].get("family") in GATE_FAMILIES and bool(c["gate"].get("checker")),
        "single_scalar": bool(c["merit"].get("scalar")) and c["merit"].get("direction") in ("up", "down"),
        "publishable_unit": bool(c.get("publishable_unit")),
    }


def _map_checks(c):
    return {
        "literature_anchor": bool(c["target"].get("pinned_number")) and bool(c["target"].get("reference")),
        "certificate_gate": c["gate"].get("family") in GATE_FAMILIES and bool(c["gate"].get("checker")),
        "uncharted_region": bool(c.get("uncharted")),
        "curve_merit": bool(c["merit"].get("curve")) and bool(c["merit"].get("analytic_check")),
        "publishable_unit": bool(c.get("publishable_unit")),
    }


def grade(c):
    classes = {"record": _record_checks(c), "map": _map_checks(c)}
    passed = [name for name, checks in classes.items() if all(checks.values())]
    return {"accepted": bool(passed), "class": passed[0] if passed else None, "classes": classes}
