"""Independent, scalar oracle for Challenge 66 reload timelines."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class FixtureError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code


@dataclass
class SiteState:
    active: bool = True
    reload_due: int | None = None


SCHEMA_VERSION = "q66-policy-case-v1"


def should_request(
    policy: dict[str, Any], round_index: int, missing_count: int, n_sites: int
) -> bool:
    name = policy["name"]
    if name == "none":
        return False
    if name == "immediate":
        return True
    if name == "periodic":
        interval = int(policy["interval"])
        if interval <= 0:
            raise FixtureError(
                "invalid_policy", f"periodic interval must be positive, got {interval}"
            )
        return (round_index + 1) % interval == 0
    if name == "threshold":
        fraction = float(policy["fraction"])
        if not 0 < fraction <= 1:
            raise FixtureError(
                "invalid_policy", f"threshold fraction outside (0,1]: {fraction}"
            )
        return missing_count >= math.ceil(fraction * n_sites)
    raise FixtureError("invalid_policy", f"unknown policy {name!r}")


def simulate(case: dict[str, Any]) -> dict[str, Any]:
    if case.get("schema_version") != SCHEMA_VERSION:
        raise FixtureError(
            "schema_mismatch",
            f"expected {SCHEMA_VERSION}, got {case.get('schema_version')!r}",
        )
    rounds = int(case["rounds"])
    n_sites = int(case["n_sites"])
    if rounds <= 0 or n_sites <= 0:
        raise FixtureError(
            "invalid_shape", f"rounds/n_sites must be positive: {rounds}/{n_sites}"
        )
    site_id = int(case["site_id"])
    if not 0 <= site_id < n_sites:
        raise FixtureError(
            "invalid_coordinate", f"site_id {site_id} outside [0,{n_sites})"
        )

    reload = case["reload"]
    for field in ("reset_error_probability", "failure_probability"):
        probability = float(reload[field])
        if not 0 <= probability <= 1:
            raise FixtureError(
                "invalid_probability", f"{field} outside [0,1]: {probability}"
            )

    manual_boundaries = list(case.get("manual_reload_boundaries", []))
    if "manual_reload_boundary" in case:
        manual_boundaries.append(int(case["manual_reload_boundary"]))
    if "loss_after_round" not in case:
        if manual_boundaries:
            raise FixtureError(
                "reload_before_loss", f"site {site_id} has never been lost"
            )
        raise FixtureError("missing_loss", f"site {site_id} has no loss event")

    loss_after_round = int(case["loss_after_round"])
    if not 0 <= loss_after_round < rounds:
        raise FixtureError(
            "invalid_loss_time",
            f"loss round {loss_after_round} outside [0,{rounds})",
        )

    delay = int(reload["delay_rounds"])
    if delay < 0:
        raise FixtureError("invalid_reload_delay", f"negative delay {delay}")
    state = SiteState()
    missing = [0] * (rounds + 1)
    reloaded = [0] * (rounds + 1)

    for boundary in range(rounds + 1):
        if state.reload_due == boundary:
            if state.active:
                raise FixtureError(
                    "duplicate_reload",
                    f"site {site_id} active at due boundary {boundary}",
                )
            state.active = True
            state.reload_due = None
            reloaded[boundary] = 1
        missing[boundary] = int(not state.active)
        if boundary == rounds:
            break

        if boundary == loss_after_round:
            if not state.active:
                raise FixtureError("duplicate_loss", f"site {site_id} already missing")
            state.active = False

        if manual_boundaries:
            for _ in range(manual_boundaries.count(boundary)):
                if state.active:
                    raise FixtureError("reload_before_loss", f"site {site_id} is active")
                if state.reload_due is not None:
                    raise FixtureError("duplicate_reload", f"site {site_id} already reloading")
                state.reload_due = boundary + delay + 1
        elif not state.active and state.reload_due is None:
            if should_request(case["policy"], boundary, missing_count=1, n_sites=n_sites):
                state.reload_due = boundary + delay + 1

    return {
        "valid": True,
        "site_missing_at_boundaries": missing,
        "site_reloaded_at_boundaries": reloaded,
    }


def check_case(case: dict[str, Any]) -> dict[str, Any]:
    expected = case["expected"]
    try:
        observed = simulate(case)
    except FixtureError as exc:
        observed = {"valid": False, "error_code": exc.code, "detail": str(exc)}

    expected_core = {
        key: value
        for key, value in expected.items()
        if key
        in {
            "valid",
            "error_code",
            "site_missing_at_boundaries",
            "site_reloaded_at_boundaries",
        }
    }
    observed_core = {key: observed[key] for key in expected_core if key in observed}
    passed = observed_core == expected_core
    return {
        "case_id": case["case_id"],
        "passed": passed,
        "expected": expected_core,
        "observed": observed_core,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = [
        json.loads(line)
        for line in args.fixtures.read_text(encoding="utf-8").splitlines()
        if line
    ]
    results = [check_case(case) for case in cases]
    failures = [result for result in results if not result["passed"]]
    print(
        json.dumps(
            {"cases": len(results), "failures": failures, "passed": not failures},
            sort_keys=True,
        )
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
