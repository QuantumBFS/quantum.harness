#!/usr/bin/env python3
from fractions import Fraction
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

with (ROOT / "artifacts/issue128-summary.json").open() as handle:
    summary = json.load(handle)
with (ROOT / "certificates/issue128-certificate.json").open() as handle:
    certificate = json.load(handle)

baseline = certificate["published_baseline"]
candidate = certificate["candidate"]
resources = certificate["claimed_resources"]

assert baseline["steps"] == 393
assert candidate["steps"] == 97
assert resources["published_group_exponentials"] == 11791
assert resources["candidate_group_exponentials"] == 2911
assert resources["published_bond_propagators"] == 848952
assert resources["candidate_bond_propagators"] == 209592
assert resources["published_cnot_upper"] == 2546856
assert resources["candidate_cnot_upper"] == 628776
assert Fraction(11791, 2911) > 4
assert summary["improvement"]["exact_ratio"] == [11791, 2911]

tolerance = Fraction(*certificate["benchmark"]["tolerance"])
accepted = Fraction(*candidate["global_error_upper"])
rejected = Fraction(*candidate["previous_step_error_upper"])
assert accepted < tolerance
assert rejected > tolerance
assert candidate["d4_certificate"]["term_count"] == 75324
assert candidate["d4_certificate"]["group_count"] == 7576
assert candidate["d4_certificate"]["max_group_size"] == 10
assert summary["fivefold_followup"]["status"] == "not_certified"

print("headline_claims=PASS")
