#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Plan and persist a finite-size-crossing phase-boundary search."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

REPORT_STATUSES = {"WAITING", "ACTION_REQUIRED", "HUMAN_REQUIRED", "COMPLETE"}
ACTION_TRANSITIONS = {
    "PLANNED": {"PREPARED", "ABORTED"},
    "PREPARED": {"SUBMITTING", "ABORTED"},
    "SUBMITTING": {"SUBMITTED", "ABORTED"},
    "SUBMITTED": {"REGISTERED", "ABORTED"},
    "REGISTERED": set(),
    "ABORTED": set(),
}


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime | None = None) -> str:
    return (value or now()).isoformat(timespec="seconds").replace("+00:00", "Z")


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def locked(state_path: Path) -> Iterator[None]:
    lock_path = state_path.with_suffix(state_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def action_id(spec: dict[str, Any]) -> str:
    return "act-" + hashlib.sha256(canonical(spec)).hexdigest()[:20]


def require_policy(policy: dict[str, Any]) -> None:
    required = {"schema_version", "goal_id", "pattern", "axes", "observable", "criteria", "execution"}
    missing = required - policy.keys()
    if missing:
        raise ValueError(f"policy missing fields: {sorted(missing)}")
    if policy["schema_version"] != 1 or policy["pattern"] != "finite_size_crossing":
        raise ValueError("only finite_size_crossing policy schema 1 is supported")
    axes = policy["axes"]
    if not all(name in axes for name in ("control", "size")):
        raise ValueError("axes.control and axes.size are required")
    control = axes["control"]
    sizes = axes["size"].get("values", [])
    points = control.get("initial_points", [])
    if len(sizes) < 2 or len(points) < 2 or sizes != sorted(set(sizes)) or points != sorted(set(points)):
        raise ValueError("size values and control initial_points must be sorted and unique")
    lower, upper = control.get("bounds", [None, None])
    if lower is None or upper is None or lower >= upper or points[0] < lower or points[-1] > upper:
        raise ValueError("control bounds must contain all initial points")
    criteria = policy["criteria"]
    if float(criteria.get("sigma", 0)) <= 0 or float(criteria.get("target_width", 0)) <= 0:
        raise ValueError("criteria sigma and target_width must be positive")
    execution = policy["execution"]
    if execution.get("controller") != "local" or execution.get("runner") != "uv":
        raise ValueError("execution.controller must be local and execution.runner must be uv")
    if int(execution.get("base_budget", 0)) <= 0 or int(execution.get("poll_seconds", 0)) <= 0:
        raise ValueError("execution base_budget and poll_seconds must be positive")


def slices(policy: dict[str, Any]) -> list[Any]:
    axis = policy["axes"].get("slice")
    return axis.get("values", []) if axis else [None]


def spec(policy: dict[str, Any], slice_value: Any, control: float, size: int, budget: int) -> dict[str, Any]:
    params = {
        policy["axes"]["control"]["name"]: control,
        policy["axes"]["size"]["name"]: size,
    }
    slice_axis = policy["axes"].get("slice")
    if slice_axis:
        params[slice_axis["name"]] = slice_value
    return {"kind": "phase-diagram-cell", "params": params, "budget": budget}


def record_key(policy: dict[str, Any], record: dict[str, Any]) -> tuple[Any, float, int]:
    params = record.get("params", {})
    slice_axis = policy["axes"].get("slice")
    return (
        params.get(slice_axis["name"]) if slice_axis else None,
        params.get(policy["axes"]["control"]["name"]),
        params.get(policy["axes"]["size"]["name"]),
    )


def validate_observations(policy: dict[str, Any], observations: dict[str, Any]) -> None:
    if observations.get("schema_version") != 1 or not isinstance(observations.get("records"), list):
        raise ValueError("observations must use schema 1 and contain records")
    valid_slices = slices(policy)
    valid_sizes = policy["axes"]["size"]["values"]
    seen: set[tuple[Any, float, int]] = set()
    for record in observations["records"]:
        key = record_key(policy, record)
        if key in seen:
            raise ValueError(f"duplicate observation key: {key}")
        seen.add(key)
        if key[0] not in valid_slices or key[2] not in valid_sizes:
            raise ValueError(f"observation outside declared slice or size axes: {key}")
        if record.get("status") not in {"pending", "success", "failed"}:
            raise ValueError("record status must be pending, success, or failed")
        if record["status"] == "success":
            if not all(isinstance(record.get(field), (int, float)) for field in ("value", "error", "budget")):
                raise ValueError("successful records require numeric value, error, and budget")
            if record["error"] < 0 or not str(record.get("artifact", "")).strip():
                raise ValueError("successful records require nonnegative error and an artifact")


def difference(index: dict[tuple[Any, float, int], dict[str, Any]], slice_value: Any,
               point: float, pair: tuple[int, int]) -> tuple[float, float] | None:
    first = index.get((slice_value, point, pair[0]))
    second = index.get((slice_value, point, pair[1]))
    if not first or not second or first["status"] != "success" or second["status"] != "success":
        return None
    return second["value"] - first["value"], math.hypot(first["error"], second["error"])


def significant_sign(value: float, error: float, sigma: float) -> int:
    if value - sigma * error > 0:
        return 1
    if value + sigma * error < 0:
        return -1
    return 0


def make_report(status: str, reason: str, *, evidence: list[Any] | None = None,
                actions: list[dict[str, Any]] | None = None, next_wake_at: str | None = None,
                question: str | None = None, accepted_artifacts: list[str] | None = None) -> dict[str, Any]:
    report = {
        "schema_version": 1, "status": status, "checked_at": iso(), "reason": reason,
        "evidence": evidence or [], "actions": actions or [],
        "accepted_artifacts": accepted_artifacts or [],
    }
    if next_wake_at:
        report["next_wake_at"] = next_wake_at
    if question:
        report["question"] = question
    return report


def decide(policy: dict[str, Any], observations: dict[str, Any]) -> dict[str, Any]:
    require_policy(policy)
    validate_observations(policy, observations)
    records = observations["records"]
    pending = [record for record in records if record["status"] == "pending"]
    poll = int(policy["execution"]["poll_seconds"])
    if pending:
        return make_report("WAITING", f"{len(pending)} registered cells remain pending",
                           evidence=[{"pending_cells": len(pending)}],
                           next_wake_at=iso(now() + timedelta(seconds=poll)))
    failed = [record for record in records if record["status"] == "failed"]
    if failed:
        return make_report("HUMAN_REQUIRED", "one or more cells failed",
                           evidence=[{"failed": record.get("artifact") or record.get("params")} for record in failed],
                           question="Retry, change resources, or exclude the failed cells?")

    index = {record_key(policy, record): record for record in records}
    sizes = policy["axes"]["size"]["values"]
    initial_count = int(policy["axes"]["size"].get("initial_count", 2))
    initial_count = max(2, min(initial_count, len(sizes)))
    points = policy["axes"]["control"]["initial_points"]
    base_budget = int(policy["execution"]["base_budget"])
    sigma = float(policy["criteria"]["sigma"])
    target_width = float(policy["criteria"]["target_width"])
    max_multiplier = int(policy["criteria"].get("max_statistics_multiplier", 8))
    all_actions: list[dict[str, Any]] = []
    accepted: list[str] = []
    evidence: list[Any] = []

    for slice_value in slices(policy):
        available_sizes = [size for size in sizes if any(key[0] == slice_value and key[2] == size for key in index)]
        active_sizes = sizes[:initial_count] if not available_sizes else sizes[:max(initial_count, sizes.index(max(available_sizes)) + 1)]
        coarse_sizes = sizes[:initial_count]
        missing = [spec(policy, slice_value, point, size, base_budget)
                   for point in points for size in coarse_sizes if (slice_value, point, size) not in index]
        if missing:
            all_actions.extend({"spec": item, "reason": "complete the declared coarse grid"} for item in missing)
            continue

        pair = (active_sizes[-2], active_sizes[-1])
        observed_points = sorted({key[1] for key in index if key[0] == slice_value and key[2] in pair})
        values = [(point, difference(index, slice_value, point, pair)) for point in observed_points]
        complete_values = [(point, item) for point, item in values if item is not None]
        if len(complete_values) < 2:
            needed = [spec(policy, slice_value, point, size, base_budget) for point in points for size in pair
                      if (slice_value, point, size) not in index]
            all_actions.extend({"spec": item, "reason": "complete the active size pair"} for item in needed)
            continue

        signed = [(point, item, significant_sign(item[0], item[1], sigma)) for point, item in complete_values]
        brackets = [(left, right) for left, right in zip(signed, signed[1:]) if left[2] * right[2] == -1]
        if not brackets:
            uncertain = [entry for entry in signed if entry[2] == 0]
            if uncertain:
                point = min(uncertain, key=lambda item: abs(item[1][0]) / max(item[1][1], 1e-300))[0]
                current_budget = max(index[(slice_value, point, size)]["budget"] for size in pair)
                if current_budget < base_budget * max_multiplier:
                    new_budget = min(current_budget * 2, base_budget * max_multiplier)
                    for size in pair:
                        all_actions.append({"spec": spec(policy, slice_value, point, size, new_budget),
                                            "reason": "resolve an inconclusive crossing sign"})
                    continue
            return make_report("HUMAN_REQUIRED", "no significant crossing bracket exists inside the fixed bounds",
                               evidence=evidence + [{"slice": slice_value, "size_pair": list(pair)}],
                               question="Expand the control bounds, increase the statistics limit, or stop?")

        left, right = min(brackets, key=lambda item: item[1][0] - item[0][0])
        low, high = left[0], right[0]
        evidence.append({"slice": slice_value, "size_pair": list(pair), "bracket": [low, high],
                         "width": high - low, "sigma": sigma})
        if high - low > target_width:
            midpoint = (low + high) / 2
            for size in pair:
                if (slice_value, midpoint, size) not in index:
                    all_actions.append({"spec": spec(policy, slice_value, midpoint, size, base_budget),
                                        "reason": "bisect the crossing bracket"})
            if all((slice_value, midpoint, size) in index for size in pair):
                return make_report("HUMAN_REQUIRED", "the existing midpoint did not reduce the bracket",
                                   evidence=evidence, question="Increase statistics or revise the refinement policy?")
            continue

        if pair[1] != sizes[-1]:
            next_size = sizes[sizes.index(pair[1]) + 1]
            for point in (low, high):
                if (slice_value, point, next_size) not in index:
                    all_actions.append({"spec": spec(policy, slice_value, point, next_size, base_budget),
                                        "reason": "promote the converged bracket to the next size"})
            continue

        for point in (low, high):
            for size in pair:
                accepted.append(index[(slice_value, point, size)]["artifact"])

    if all_actions:
        unique = {action_id(item["spec"]): item for item in all_actions}
        return make_report("ACTION_REQUIRED", f"{len(unique)} phase-diagram cells are required",
                           evidence=evidence, actions=list(unique.values()))
    return make_report("COMPLETE", "every slice has a target-width crossing on the final adjacent size pair",
                       evidence=evidence, accepted_artifacts=sorted(set(accepted)))


def validate_report(report: dict[str, Any]) -> None:
    required = {"schema_version", "status", "checked_at", "reason", "evidence", "actions", "accepted_artifacts"}
    missing = required - report.keys()
    if missing or report.get("schema_version") != 1 or report.get("status") not in REPORT_STATUSES:
        raise ValueError(f"invalid report contract; missing fields: {sorted(missing)}")
    status = report["status"]
    if status == "WAITING" and (report["actions"] or not report.get("next_wake_at")):
        raise ValueError("WAITING requires next_wake_at and forbids actions")
    if status == "ACTION_REQUIRED" and not report["actions"]:
        raise ValueError("ACTION_REQUIRED requires actions")
    if status == "HUMAN_REQUIRED" and (report["actions"] or not report.get("question")):
        raise ValueError("HUMAN_REQUIRED requires a question and forbids actions")
    if status == "COMPLETE" and (report["actions"] or report.get("next_wake_at") or not report["accepted_artifacts"]):
        raise ValueError("COMPLETE requires artifacts and forbids actions or a next wake")


def require_state(policy: dict[str, Any], state: dict[str, Any]) -> None:
    if state.get("schema_version") != 1 or state.get("goal_id") != policy["goal_id"]:
        raise ValueError("state does not match policy")
    for action in state.get("actions", []):
        if action.get("state") not in ACTION_TRANSITIONS:
            raise ValueError("invalid action state")


def initialize(policy_path: Path, state_path: Path) -> dict[str, Any]:
    policy = load(policy_path)
    require_policy(policy)
    with locked(state_path):
        if state_path.exists():
            state = load(state_path)
            require_state(policy, state)
            return state
        state = {"schema_version": 1, "goal_id": policy["goal_id"], "control_state": "RUNNING",
                 "latest_report": None, "next_wake_at": None, "actions": [], "events": []}
        state["events"].append({"at": iso(), "kind": "INITIALIZED"})
        atomic_write(state_path, state)
        return state


def ingest(policy_path: Path, state_path: Path, report_path: Path) -> dict[str, Any]:
    policy, report = load(policy_path), load(report_path)
    require_policy(policy)
    validate_report(report)
    with locked(state_path):
        state = load(state_path)
        require_state(policy, state)
        status = report["status"]
        state["latest_report"] = {"path": str(report_path), "status": status, "checked_at": report["checked_at"],
                                  "reason": report["reason"], "accepted_artifacts": report["accepted_artifacts"],
                                  "authorized_action_ids": [action_id(item["spec"]) for item in report["actions"]]}
        state["next_wake_at"] = report.get("next_wake_at")
        state["control_state"] = "COMPLETE" if status == "COMPLETE" else ("HUMAN_REQUIRED" if status == "HUMAN_REQUIRED" else "RUNNING")
        state["events"].append({"at": iso(), "kind": "REPORT_INGESTED", "status": status})
        atomic_write(state_path, state)
        return {"status": status, "next_wake_at": state["next_wake_at"], "actions": report["actions"]}


def plan(policy_path: Path, state_path: Path, spec_path: Path) -> dict[str, Any]:
    policy, action_spec = load(policy_path), load(spec_path)
    require_policy(policy)
    identifier = action_id(action_spec)
    with locked(state_path):
        state = load(state_path)
        require_state(policy, state)
        latest = state.get("latest_report") or {}
        if state["control_state"] != "RUNNING" or latest.get("status") != "ACTION_REQUIRED" or identifier not in latest.get("authorized_action_ids", []):
            raise ValueError("action spec is not authorized by the latest report")
        existing = next((item for item in state["actions"] if item["action_id"] == identifier), None)
        if existing:
            return existing
        maximum = int(policy["execution"].get("max_actions", 0))
        if maximum and len(state["actions"]) >= maximum:
            raise ValueError("max_actions reached")
        action = {"action_id": identifier, "spec": action_spec, "state": "PLANNED", "created_at": iso()}
        state["actions"].append(action)
        state["events"].append({"at": iso(), "kind": "ACTION_PLANNED", "action_id": identifier})
        atomic_write(state_path, state)
        return action


def advance(policy_path: Path, state_path: Path, identifier: str, target: str,
            receipt: str | None, reason: str | None) -> dict[str, Any]:
    policy = load(policy_path)
    require_policy(policy)
    with locked(state_path):
        state = load(state_path)
        require_state(policy, state)
        action = next((item for item in state["actions"] if item["action_id"] == identifier), None)
        if not action:
            raise ValueError(f"unknown action: {identifier}")
        current = action["state"]
        if target == current:
            if receipt and action.get("receipt") not in {None, receipt}:
                raise ValueError("receipt does not match")
            return action
        if target not in ACTION_TRANSITIONS[current]:
            raise ValueError(f"illegal action transition: {current} -> {target}")
        if target == "SUBMITTED" and not receipt:
            raise ValueError("SUBMITTED requires a durable receipt")
        if target == "ABORTED" and not reason:
            raise ValueError("ABORTED requires a reason")
        action.update({"state": target, "updated_at": iso()})
        if receipt:
            action["receipt"] = receipt
        if reason:
            action["reason"] = reason
        state["events"].append({"at": iso(), "kind": "ACTION_ADVANCED", "action_id": identifier,
                                "previous": current, "action_state": target})
        atomic_write(state_path, state)
        return action


def inspect(policy_path: Path, state_path: Path) -> dict[str, Any]:
    policy, state = load(policy_path), load(state_path)
    require_policy(policy)
    require_state(policy, state)
    return {"goal_id": state["goal_id"], "control_state": state["control_state"],
            "next_wake_at": state.get("next_wake_at"),
            "unresolved_submitting": [item for item in state["actions"] if item["state"] == "SUBMITTING"],
            "action_counts": {name: sum(item["state"] == name for item in state["actions"]) for name in ACTION_TRANSITIONS}}


def nested(value: dict[str, Any], field: str) -> Any:
    current: Any = value
    for part in field.split("."):
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"manifest missing field: {field}")
        current = current[part]
    return current


def collect(policy_path: Path, cells_dir: Path, output_path: Path) -> dict[str, Any]:
    policy = load(policy_path)
    require_policy(policy)
    observable = policy["observable"]
    budget_field = observable.get("budget_field", "budget")
    records_by_key: dict[tuple[Any, float, int], dict[str, Any]] = {}
    for manifest_path in sorted(cells_dir.glob("*/manifest.json")):
        manifest = load(manifest_path)
        status = manifest.get("status")
        if status not in {"pending", "success", "failed"}:
            raise ValueError(f"invalid manifest status in {manifest_path}")
        record: dict[str, Any] = {
            "params": nested(manifest, "params"),
            "status": status,
            "budget": nested(manifest, budget_field),
            "artifact": str(manifest_path),
        }
        if status == "success":
            record["value"] = nested(manifest, observable["value_field"])
            record["error"] = nested(manifest, observable["error_field"])
        key = record_key(policy, record)
        previous = records_by_key.get(key)
        if previous and previous["budget"] == record["budget"]:
            raise ValueError(f"ambiguous manifests share key and budget: {key}")
        if not previous or record["budget"] > previous["budget"]:
            records_by_key[key] = record
    result = {"schema_version": 1, "records": list(records_by_key.values())}
    validate_observations(policy, result)
    atomic_write(output_path, result)
    return result


def scaffold(directory: Path) -> dict[str, str]:
    directory.mkdir(parents=True, exist_ok=True)
    policy_path, observations_path = directory / "phase-policy.json", directory / "observations.json"
    if policy_path.exists() or observations_path.exists():
        raise ValueError("scaffold refuses to overwrite existing policy or observations")
    policy = {"schema_version": 1, "goal_id": "example-boundary", "pattern": "finite_size_crossing",
              "axes": {"control": {"name": "coupling", "bounds": [0.0, 1.0], "initial_points": [0.0, 0.5, 1.0]},
                       "size": {"name": "L", "values": [8, 12, 16], "initial_count": 2}},
              "observable": {"name": "dimensionless_ratio", "value_field": "observables.ratio.value",
                             "error_field": "observables.ratio.error", "budget_field": "settings.budget"},
              "criteria": {"sigma": 2.0, "target_width": 0.1, "max_statistics_multiplier": 8,
                           "final_pair_required": True},
              "execution": {"controller": "local", "runner": "uv", "base_budget": 1000,
                            "poll_seconds": 1800, "max_actions": 100}}
    atomic_write(policy_path, policy)
    atomic_write(observations_path, {"schema_version": 1, "records": []})
    return {"policy": str(policy_path), "observations": str(observations_path)}


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    command = commands.add_parser("scaffold")
    command.add_argument("--directory", type=Path, required=True)
    command = commands.add_parser("collect")
    command.add_argument("--policy", type=Path, required=True)
    command.add_argument("--cells-dir", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command = commands.add_parser("check")
    command.add_argument("--policy", type=Path, required=True)
    command.add_argument("--observations", type=Path, required=True)
    command.add_argument("--report", type=Path)
    for name in ("init", "inspect"):
        command = commands.add_parser(name)
        command.add_argument("--policy", type=Path, required=True)
        command.add_argument("--state", type=Path, required=True)
    command = commands.add_parser("ingest")
    command.add_argument("--policy", type=Path, required=True); command.add_argument("--state", type=Path, required=True); command.add_argument("--report", type=Path, required=True)
    command = commands.add_parser("plan")
    command.add_argument("--policy", type=Path, required=True); command.add_argument("--state", type=Path, required=True); command.add_argument("--spec", type=Path, required=True)
    command = commands.add_parser("advance")
    command.add_argument("--policy", type=Path, required=True); command.add_argument("--state", type=Path, required=True); command.add_argument("--action-id", required=True)
    command.add_argument("--to", choices=tuple(ACTION_TRANSITIONS), required=True); command.add_argument("--receipt"); command.add_argument("--reason")
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "scaffold":
            result = scaffold(args.directory)
        elif args.command == "collect":
            result = collect(args.policy, args.cells_dir, args.output)
        elif args.command == "check":
            result = decide(load(args.policy), load(args.observations))
            if args.report:
                atomic_write(args.report, result)
        elif args.command == "init":
            result = initialize(args.policy, args.state)
        elif args.command == "inspect":
            result = inspect(args.policy, args.state)
        elif args.command == "ingest":
            result = ingest(args.policy, args.state, args.report)
        elif args.command == "plan":
            result = plan(args.policy, args.state, args.spec)
        else:
            result = advance(args.policy, args.state, args.action_id, args.to, args.receipt, args.reason)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"phase-diagram error: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
