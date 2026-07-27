#!/usr/bin/env python3
"""Deterministic safety judgments for the /cluster-jobs student toolkit.

Two read-only checks, each emitting JSON and an exit code the calling skill
maps to an action:

* ``inspect <script>`` — parse a job script's ``#SBATCH`` directives into a
  normalized resource table, grade each field against the profile's
  ``[limits]`` (hard ceiling → block, soft threshold → warn), and secret-scan
  the script. Exit 0 clean / 1 soft-warn / 2 hard-block.
* ``check-path <path>`` — confirm a download/delete target sits under the
  profile's ``[limits.paths].allowed_roots``. Exit 0 ok / 2 refused.

**Fail closed.** An unreadable/malformed profile blocks (exit 2). A profile
with no ``[limits]`` warns (exit 1) rather than silently allowing. A resource
the script does not specify but a limit governs surfaces a warning. Safety is
never assumed; it is measured or flagged.

This module judges *facts only*. The skill owns the interaction (preview,
confirm); ``harness_slurm.sh`` owns the mechanics.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
from pathlib import Path

import cluster_profile as cp

# Tier ordering for "take the worst" aggregation.
_TIER_RANK = {"clean": 0, "soft": 1, "hard": 2}

# Short-flag → canonical long name for the directives we grade.
_SHORT_FLAGS = {
    "t": "time",
    "N": "nodes",
    "n": "ntasks",
    "c": "cpus-per-task",
    "p": "partition",
    "a": "array",
}

# Secret patterns. Kept specific to limit false positives on scientific code:
# we match credential *shapes*, not every "key = ..." assignment.
_SECRET_RULES = [
    ("private-key-block", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("bearer-token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{16,}\b")),
    (
        "inline-secret-assignment",
        re.compile(
            r"(?i)(password|passwd|secret|api[_-]?key|access[_-]?token)"
            r"\s*[:=]\s*['\"]?[^\s'\"#]{8,}"
        ),
    ),
]


def parse_sbatch_option(extra: str, field: str) -> str | None:
    """Return the last requested sbatch option from a raw ``--extra`` string."""
    try:
        tokens = shlex.split(extra)
    except ValueError as exc:
        raise ValueError(f"malformed --extra: {exc}") from exc

    value: str | None = None
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("--"):
            name_value = token[2:]
            name, sep, option_value = name_value.partition("=")
            if name == field:
                if sep:
                    value = option_value
                elif i + 1 < len(tokens):
                    i += 1
                    value = tokens[i]
                else:
                    value = ""
        elif field == "partition" and token == "-p":
            if i + 1 < len(tokens):
                i += 1
                value = tokens[i]
            else:
                value = ""
        elif field == "partition" and token.startswith("-p") and len(token) > 2:
            value = token[2:]
        i += 1
    return value


def worst(*tiers: str) -> str:
    """Return the highest-severity tier among the arguments."""
    return max(tiers, key=lambda t: _TIER_RANK[t], default="clean")


# --------------------------------------------------------------------------- #
# #SBATCH parsing
# --------------------------------------------------------------------------- #
def parse_directives(text: str) -> dict[str, str]:
    """Pull ``#SBATCH`` options out of a job script into a flat dict.

    Handles ``--key=value``, ``--key value``, and short flags ``-k value``.
    Later directives override earlier ones (Slurm's own behavior). A trailing
    ``%N`` concurrency suffix on ``--array`` is preserved for the array parser.
    """
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or (line.startswith("#") and not line.startswith("#SBATCH")):
            continue
        if not line.startswith("#SBATCH"):
            break
        body = line[len("#SBATCH") :].strip()
        # strip trailing inline comment
        body = body.split("#", 1)[0].strip()
        if not body:
            continue
        if body.startswith("--"):
            token = body[2:]
            if "=" in token:
                key, value = token.split("=", 1)
            else:
                parts = token.split(None, 1)
                key, value = parts[0], (parts[1] if len(parts) > 1 else "")
            out[key.strip()] = value.strip()
        elif body.startswith("-"):
            parts = body[1:].split(None, 1)
            flag = parts[0]
            value = parts[1].strip() if len(parts) > 1 else ""
            canonical = _SHORT_FLAGS.get(flag)
            if canonical:
                out[canonical] = value
    return out


def parse_walltime(text: str) -> int:
    """Parse a Slurm ``--time`` value into seconds. Raise ``ValueError`` if bad.

    Accepts: ``minutes``, ``minutes:seconds``, ``hours:minutes:seconds``,
    ``days-hours``, ``days-hours:minutes``, ``days-hours:minutes:seconds``.
    """
    s = text.strip()
    if not s:
        raise ValueError("empty walltime")
    days = 0
    if "-" in s:
        d, s = s.split("-", 1)
        days = int(d)
        parts = [int(p) for p in s.split(":")]
        # days-H[:M[:S]]
        hms = parts + [0] * (3 - len(parts))
        hours, minutes, seconds = hms[0], hms[1], hms[2]
    else:
        parts = [int(p) for p in s.split(":")]
        if len(parts) == 1:
            hours, minutes, seconds = 0, parts[0], 0
        elif len(parts) == 2:
            hours, minutes, seconds = 0, parts[0], parts[1]
        elif len(parts) == 3:
            hours, minutes, seconds = parts
        else:
            raise ValueError(f"bad walltime: {text!r}")
    return ((days * 24 + hours) * 60 + minutes) * 60 + seconds


def count_array(spec: str) -> int:
    """Count tasks in a Slurm ``--array`` spec (ignoring any ``%N`` suffix)."""
    spec = spec.split("%", 1)[0].strip()
    total = 0
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            rng, _, step_s = token.partition(":")
            lo_s, _, hi_s = rng.partition("-")
            lo, hi = int(lo_s), int(hi_s)
            step = int(step_s) if step_s else 1
            total += len(range(lo, hi + 1, step))
        else:
            total += 1
    return total


def derive_cpus(directives: dict[str, str]) -> int:
    """Best-effort total CPU count from task/cpu/node directives."""
    cpus_per_task = int(directives.get("cpus-per-task", "1") or "1")
    if "ntasks" in directives:
        ntasks = int(directives["ntasks"] or "1")
    elif "nodes" in directives and "ntasks-per-node" in directives:
        ntasks = int(directives["nodes"] or "1") * int(directives["ntasks-per-node"] or "1")
    else:
        ntasks = 1
    return ntasks * cpus_per_task


# --------------------------------------------------------------------------- #
# Secret scan
# --------------------------------------------------------------------------- #
def _redact(line: str) -> str:
    """Trim and partially mask a matched line for safe display."""
    snippet = line.strip()[:80]
    return re.sub(r"[A-Za-z0-9/+_\-]{8,}", lambda m: m.group(0)[:3] + "…", snippet)


def scan_secrets(text: str) -> list[dict]:
    """Return one finding per line/rule match (value redacted)."""
    findings = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for rule, pattern in _SECRET_RULES:
            if pattern.search(line):
                findings.append({"rule": rule, "line": lineno, "excerpt": _redact(line)})
    return findings


# --------------------------------------------------------------------------- #
# Resource extraction + grading
# --------------------------------------------------------------------------- #
def build_resources(directives: dict[str, str]) -> tuple[dict, list[str]]:
    """Normalize directives into a resource table; collect parse warnings."""
    warnings: list[str] = []
    res: dict = {
        "walltime": None,
        "walltime_seconds": None,
        "nodes": None,
        "cpus": None,
        "array_size": None,
        "partition": directives.get("partition"),
    }
    if "time" in directives:
        try:
            res["walltime_seconds"] = parse_walltime(directives["time"])
            res["walltime"] = directives["time"]
        except ValueError:
            warnings.append(f"unparseable --time={directives['time']!r}; cannot verify walltime")
    if "nodes" in directives:
        res["nodes"] = int(directives["nodes"] or "1")
    res["cpus"] = derive_cpus(directives)
    if "array" in directives:
        try:
            res["array_size"] = count_array(directives["array"])
        except ValueError:
            warnings.append(f"unparseable --array={directives['array']!r}; cannot verify size")
    return res, warnings


def grade(resources: dict, limits: cp.Limits) -> tuple[list[dict], list[str]]:
    """Grade each resource against hard/soft limits. Return verdicts + warnings.

    Fail-closed: a hard limit configured for walltime with no ``--time`` in the
    script yields a soft warning (cluster default applies, unverifiable here).
    """
    verdicts: list[dict] = []
    warnings: list[str] = []
    hard, soft = limits.hard, limits.soft

    def add(field: str, value, limit, tier: str, message: str) -> None:
        verdicts.append(
            {"field": field, "value": value, "limit": limit, "tier": tier, "message": message}
        )

    # walltime
    if resources["walltime_seconds"] is not None:
        secs = resources["walltime_seconds"]
        if "max_walltime" in hard and secs > parse_walltime(str(hard["max_walltime"])):
            add("walltime", resources["walltime"], hard["max_walltime"], "hard",
                f"requested walltime exceeds hard cap {hard['max_walltime']}")
        elif "warn_walltime" in soft and secs > parse_walltime(str(soft["warn_walltime"])):
            add("walltime", resources["walltime"], soft["warn_walltime"], "soft",
                f"walltime above soft threshold {soft['warn_walltime']}")
    elif "max_walltime" in hard:
        warnings.append("no --time set; cluster default applies, cannot verify against max_walltime")

    # nodes
    if resources["nodes"] is not None and "max_nodes" in hard and resources["nodes"] > hard["max_nodes"]:
        add("nodes", resources["nodes"], hard["max_nodes"], "hard",
            f"requested nodes exceeds hard cap {hard['max_nodes']}")

    # cpus
    cpus = resources["cpus"]
    if cpus is not None:
        if "max_cpus" in hard and cpus > hard["max_cpus"]:
            add("cpus", cpus, hard["max_cpus"], "hard",
                f"requested cpus exceeds hard cap {hard['max_cpus']}")
        elif "warn_cpus" in soft and cpus > soft["warn_cpus"]:
            add("cpus", cpus, soft["warn_cpus"], "soft",
                f"cpus above soft threshold {soft['warn_cpus']}")

    # array size
    size = resources["array_size"]
    if size is not None and "max_array_size" in hard and size > hard["max_array_size"]:
        add("array_size", size, hard["max_array_size"], "hard",
            f"array size exceeds hard cap {hard['max_array_size']}")

    # partition
    part = resources["partition"]
    if part and part in soft.get("unusual_partitions", []):
        add("partition", part, soft["unusual_partitions"], "soft",
            f"'{part}' is flagged as an unusual partition")

    return verdicts, warnings


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_inspect(script: str, profile_path: str | None) -> tuple[dict, int]:
    """Inspect a job script. Return (report, exit_code)."""
    text = Path(script).read_text(encoding="utf-8")
    directives = parse_directives(text)
    resources, parse_warns = build_resources(directives)
    secrets = scan_secrets(text)

    report: dict = {
        "script": script,
        "resources": resources,
        "verdicts": [],
        "secrets": secrets,
        "warnings": list(parse_warns),
    }

    overall = "clean"
    path = cp.resolve_profile_path(profile_path)
    try:
        prof = cp.load_profile(path)
    except cp.ProfileError as exc:
        report["profile"] = str(path)
        report["warnings"].append(f"{exc}")
        report["overall"] = "hard"
        return report, 2
    report["profile"] = str(path)

    limits = cp.get_limits(prof)
    if not limits.configured:
        report["warnings"].append("profile has no [limits]; submitting without resource ceilings")
        overall = worst(overall, "soft")

    verdicts, grade_warns = grade(resources, limits)
    report["verdicts"] = verdicts
    report["warnings"].extend(grade_warns)

    if secrets:
        overall = worst(overall, "hard")
    if parse_warns or grade_warns:
        overall = worst(overall, "soft")
    for v in verdicts:
        overall = worst(overall, v["tier"])

    report["overall"] = overall
    return report, _TIER_RANK[overall]


def _is_under(child: str, parent: str) -> bool:
    """True if ``child`` resolves inside ``parent`` (after ~ and .. handling)."""
    c = os.path.normpath(os.path.expanduser(child))
    p = os.path.normpath(os.path.expanduser(parent))
    return c == p or c.startswith(p + os.sep)


def cmd_check_path(target: str, profile_path: str | None) -> tuple[dict, int]:
    """Check a download/delete path against allowed roots. (report, exit_code)."""
    path = cp.resolve_profile_path(profile_path)
    report: dict = {"path": target, "profile": str(path)}
    try:
        prof = cp.load_profile(path)
    except cp.ProfileError as exc:
        report.update(ok=False, allowed_roots=[], message=str(exc))
        return report, 2

    roots = cp.get_limits(prof).allowed_roots
    report["allowed_roots"] = roots
    if not roots:
        report.update(ok=False, message="no allowed_roots configured in [limits.paths]")
        return report, 2
    if any(_is_under(target, r) for r in roots):
        report.update(ok=True, message="path is within an allowed root")
        return report, 0
    report.update(ok=False, message="path is outside every allowed root")
    return report, 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cluster-jobs safety guardrail.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ins = sub.add_parser("inspect", help="grade a job script's resources + secrets")
    p_ins.add_argument("script")
    p_ins.add_argument("--profile", default=None)

    p_chk = sub.add_parser("check-path", help="confirm a path is under allowed roots")
    p_chk.add_argument("path")
    p_chk.add_argument("--profile", default=None)

    p_dir = sub.add_parser("directive", help="read one #SBATCH directive")
    p_dir.add_argument("script")
    p_dir.add_argument("--field", required=True, choices=("partition", "gres"))

    p_opt = sub.add_parser("option", help="read one option from a raw sbatch --extra string")
    p_opt.add_argument("extra")
    p_opt.add_argument("--field", required=True, choices=("partition", "gres"))

    args = parser.parse_args(argv)
    if args.command == "option":
        try:
            value = parse_sbatch_option(args.extra, args.field)
        except ValueError as exc:
            print(f"cluster_guardrail: {exc}", file=sys.stderr)
            return 2
        if value is None:
            return 1
        print(value)
        return 0
    if args.command == "directive":
        directives = parse_directives(Path(args.script).read_text(encoding="utf-8"))
        value = directives.get(args.field)
        if value is None:
            return 1
        print(value)
        return 0
    if args.command == "inspect":
        report, code = cmd_inspect(args.script, args.profile)
    else:
        report, code = cmd_check_path(args.path, args.profile)
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
