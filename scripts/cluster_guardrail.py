#!/usr/bin/env python3
"""Deterministic safety judgments for the /cluster-jobs student toolkit.

Read-only checks, each emitting JSON and an exit code the calling skill
maps to an action:

* ``inspect <script>`` — parse a job script's ``#SBATCH`` directives into a
  normalized resource table, grade each field against the profile's
  ``[limits]`` (hard ceiling → block, soft threshold → warn), and secret-scan
  the script. Exit 0 clean / 1 soft-warn / 2 hard-block.
* ``check-path <path>`` — confirm a download/delete target sits under the
  profile's ``[limits.paths].allowed_roots``. Exit 0 ok / 2 refused.
* ``expect`` / ``check-alloc`` — predict, before submitting, the allocation
  ``sacct`` will report (it is fixed by the request and the partition policy),
  then compare a submitted job's ``sacct`` rows (stdin) against it.
  ``check-alloc`` exits 0 as predicted / 1 mismatch.

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
    "C": "constraint",
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


def node_cores(row: dict, constraint: str | None) -> int:
    """Cores of the node a whole-node job may land on (worst case).

    With ``node_types`` and a ``--constraint``, only node types carrying the
    requested features count (``a&b`` / ``a,b`` need all, ``a|b`` needs any);
    otherwise the largest node type, falling back to the row's ``cores``.
    """
    types = [t for t in row.get("node_types", []) if isinstance(t, dict)]
    if types and constraint:
        tokens = [t for t in re.split(r"[&,|\[\]*()\s]+", constraint) if t]
        need = any if "|" in constraint else all
        matched = [
            t for t in types if need(tok in t.get("features", []) for tok in tokens)
        ]
        types = matched or types
    if not types:
        return int(row.get("cores", 0) or 0)
    return max(int(t.get("cores", 0)) for t in types)


def apply_allocation(
    resources: dict, directives: dict[str, str], profile: dict
) -> list[str]:
    """Count what the scheduler will actually allocate, not what was typed.

    On a partition with ``whole_node = true`` (or with ``--exclusive``) a
    1-task job still occupies every core of its nodes, so the CPU figure the
    limits see is ``nodes × cores-per-node``. Updates ``resources`` in place and
    returns an explanatory warning (empty when nothing changed).
    """
    part = resources["partition"] or cp.get_field(profile, "scheduler.default_partition")
    row = cp.get_partition(profile, part) if part else None
    exclusive = "exclusive" in directives
    if not (exclusive or (row and row.get("whole_node"))):
        return []
    if row is None:
        return [f"--exclusive on partition {part!r} with no [[partitions]] row; "
                "cannot count the cores of a whole node"]
    per_node = node_cores(row, directives.get("constraint"))
    nodes = resources["nodes"] or 1
    allocated = nodes * per_node
    if not per_node or allocated <= (resources["cpus"] or 0):
        return []
    resources.setdefault("cpus_requested", resources["cpus"])
    resources["cpus"] = allocated
    why = "--exclusive" if exclusive else f"partition '{part}' allocates whole nodes"
    return [f"{why}: counting {nodes} node(s) × {per_node} cores = {allocated} cpus"]


_MEM_UNITS = {"K": 1 / 1024, "M": 1, "G": 1024, "T": 1024 * 1024}


def parse_mem_mb(text: str) -> float:
    """Slurm ``--mem`` / ``--mem-per-cpu`` value in MB (``3G`` → 3072, ``500`` → 500)."""
    s = text.strip().upper()
    if s.endswith("B"):
        s = s[:-1]
    unit = s[-1] if s and s[-1] in _MEM_UNITS else "M"
    num = s[:-1] if s and s[-1] in _MEM_UNITS else s
    return float(num) * _MEM_UNITS[unit]


def apply_mem_per_cpu(
    resources: dict, directives: dict[str, str], profile: dict
) -> tuple[list[dict], list[str]]:
    """Count the cpus Slurm adds when the memory request outgrows MaxMemPerCPU.

    A job asking for more than ``cpus × MaxMemPerCPU`` is not rejected: Slurm
    raises its cpu count to ``ceil(mem / MaxMemPerCPU)`` and bills every one of
    them, while a single-threaded program leaves the extra cores idle. Updates
    ``resources["cpus"]`` in place; returns a soft verdict (the student confirms
    or lowers ``--mem``) and warnings.
    """
    mem, per_cpu = directives.get("mem"), directives.get("mem-per-cpu")
    if not mem and not per_cpu:
        return [], []
    part = resources["partition"] or cp.get_field(profile, "scheduler.default_partition")
    row = cp.get_partition(profile, part) if part else None
    cap = (row or {}).get("max_mem_per_cpu_mb") or cp.get_field(
        profile, "cluster_limits.max_mem_per_cpu_mb"
    )
    if not cap:
        return [], [
            f"no max_mem_per_cpu_mb for partition {part!r} in the profile; cannot tell "
            "whether the memory request raises the cpu count (re-probe with /setup-cluster)"
        ]
    try:
        if per_cpu:
            want = parse_mem_mb(per_cpu)
            factor = -(-want // cap)
            raised = int((resources["cpus"] or 1) * factor) if factor > 1 else None
            asked = f"--mem-per-cpu={per_cpu}"
        else:
            want = parse_mem_mb(mem)
            if want == 0:  # --mem=0: all of a node's memory; whole-node logic applies
                return [], []
            nodes = resources["nodes"] or 1
            per_node = -(-(resources["cpus"] or 1) // nodes)
            need = int(-(-want // cap))
            raised = need * nodes if need > per_node else None
            asked = f"--mem={mem}"
    except ValueError:
        return [], [f"unparseable memory request {mem or per_cpu!r}; cannot check MaxMemPerCPU"]
    if raised is None:
        return [], []
    resources.setdefault("cpus_requested", resources["cpus"])
    resources["cpus"] = raised
    msg = (
        f"{asked} exceeds MaxMemPerCPU={cap}M on '{part}': Slurm raises the job to "
        f"{raised} cpus and bills them all; request at most {int(cap)}M per cpu if the "
        "job's peak memory fits"
    )
    return [{"field": "memory", "value": mem or per_cpu, "limit": f"{int(cap)}M/cpu",
             "tier": "soft", "message": msg}], []


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

    # Memory beyond cpus × MaxMemPerCPU silently adds (billed) cpus: soft verdict.
    mem_verdicts, mem_warns = apply_mem_per_cpu(resources, directives, prof)
    # Informational: the adjusted CPU count is graded below; no extra tier.
    report["warnings"].extend(apply_allocation(resources, directives, prof))

    verdicts, grade_warns = grade(resources, limits)
    report["verdicts"] = mem_verdicts + verdicts
    report["warnings"].extend(mem_warns + grade_warns)

    if secrets:
        overall = worst(overall, "hard")
    if parse_warns or grade_warns or mem_warns:
        overall = worst(overall, "soft")
    for v in report["verdicts"]:
        overall = worst(overall, v["tier"])

    report["overall"] = overall
    return report, _TIER_RANK[overall]


# sacct columns read by check-alloc; harness_slurm.sh asks for exactly these.
SACCT_ALLOC_FMT = "JobID,State,Partition,AllocCPUS,NNodes,ReqMem,AllocTRES,Timelimit,MaxRSS,Elapsed"

# sbatch options that change what a job is allocated.
_ALLOC_OPTIONS = ("partition", "time", "cpus-per-task", "ntasks", "ntasks-per-node",
                  "nodes", "mem", "mem-per-cpu", "array", "constraint", "exclusive")


def predict_alloc(directives: dict[str, str], profile: dict) -> dict:
    """What ``sacct`` should report for this job, before it is submitted.

    The allocation is a deterministic function of the request and the partition
    policy in the profile: cpus raised by a memory request above
    ``max_mem_per_cpu_mb`` or by a whole-node partition, memory defaulting to
    ``def_mem_per_cpu_mb × cpus``, one billing unit per cpu. Fields that cannot
    be predicted (no ``--time``, unknown memory default) are ``None`` and not
    checked later; the assumptions are listed so a mismatch can be traced.
    """
    resources, warns = build_resources(directives)
    _, mem_warns = apply_mem_per_cpu(resources, directives, profile)
    warns += mem_warns + apply_allocation(resources, directives, profile)
    part = resources["partition"] or cp.get_field(profile, "scheduler.default_partition")
    row = (cp.get_partition(profile, part) if part else None) or {}
    nodes = resources["nodes"] or 1
    cpus = resources["cpus"] or 1
    requested = resources.get("cpus_requested", cpus)
    assumptions = ["billing = 1 unit per allocated cpu (no TRESBillingWeights in the profile)"]
    mem_mb = None
    try:
        if directives.get("mem") and parse_mem_mb(directives["mem"]) > 0:
            mem_mb = parse_mem_mb(directives["mem"]) * nodes
        elif directives.get("mem-per-cpu"):
            # Slurm keeps the total when it raises the cpu count for memory.
            mem_mb = parse_mem_mb(directives["mem-per-cpu"]) * requested
    except ValueError:
        pass
    if mem_mb is None and not directives.get("mem") and not directives.get("mem-per-cpu"):
        default = row.get("def_mem_per_cpu_mb") or cp.get_field(
            profile, "cluster_limits.def_mem_per_cpu_mb"
        )
        if default:
            mem_mb = default * cpus
            assumptions.append(f"memory = DefMemPerCPU {default}M × {cpus} cpus")
    return {
        "partition": part,
        "tasks": resources["array_size"] or 1,
        "cpus_per_task": cpus,
        "cpus_requested": requested,
        "nodes_per_task": nodes,
        "mem_mb_per_task": round(mem_mb) if mem_mb else None,
        "timelimit_s": resources["walltime_seconds"],
        "billing_per_task": cpus,
        "assumptions": assumptions,
        "warnings": warns,
    }


def cmd_expect(script: str | None, profile_path: str | None, overrides: dict[str, str]) -> dict:
    """Predicted sacct for a script plus command-line options (which win, as in sbatch)."""
    directives = parse_directives(Path(script).read_text(encoding="utf-8")) if script else {}
    directives.update({k: v for k, v in overrides.items() if v is not None})
    try:
        prof = cp.load_profile(cp.resolve_profile_path(profile_path))
    except cp.ProfileError as exc:
        prof = {}
        report = predict_alloc(directives, prof)
        report["warnings"].append(f"{exc}; predicted without partition policy")
        return report
    return predict_alloc(directives, prof)


def expect_summary(e: dict) -> str:
    """One readable block of a prediction, for the submit preview."""
    mem = e["mem_mb_per_task"]
    lines = [
        "expected sacct (per task): "
        f"partition={e['partition']} tasks={e['tasks']} cpus={e['cpus_per_task']} "
        f"(requested {e['cpus_requested']}) nodes={e['nodes_per_task']} "
        f"mem={f'{mem:.0f}M' if mem else '?'} billing={e['billing_per_task']} "
        f"timelimit_s={e['timelimit_s']}"
    ]
    lines += [f"  ! {w}" for w in e["warnings"]]
    return "\n".join(lines)


def _tres_value(tres: str, key: str) -> int | None:
    """``billing=2,cpu=2,mem=3G`` → ``2`` for ``billing``; ``None`` when absent."""
    for item in tres.split(","):
        k, _, v = item.partition("=")
        if k == key and v.isdigit():
            return int(v)
    return None


def _req_mem_mb(text: str, cpus: int, nodes: int) -> float | None:
    """sacct ``ReqMem`` in MB per task: ``3G`` (total), or older ``3Gn`` (per
    node) / ``3Gc`` (per cpu)."""
    t = text.strip()
    if not t:
        return None
    scale = 1
    if t[-1] in "cC":
        scale, t = cpus, t[:-1]
    elif t[-1] in "nN":
        scale, t = nodes, t[:-1]
    try:
        return parse_mem_mb(t) * scale
    except ValueError:
        return None


def _parse_sacct_alloc(text: str) -> dict[str, dict]:
    """Rows of ``SACCT_ALLOC_FMT`` → one record per task (steps folded into peak RSS)."""
    tasks: dict[str, dict] = {}
    for line in text.splitlines():
        cols = line.strip().split("|")
        if len(cols) < 10 or not cols[0] or cols[0] == "JobID":
            continue
        job, state, part, alloc, nnodes, req_mem, tres, limit, maxrss, elapsed = cols[:10]
        task, _, step = job.partition(".")
        t = tasks.setdefault(task, {"task": task, "peak_mb": None})
        if not step:
            n = int(alloc) if alloc.isdigit() else 0
            nn = int(nnodes) if nnodes.isdigit() else 0
            try:
                limit_s = parse_walltime(limit) if limit and limit[0].isdigit() else None
            except ValueError:
                limit_s = None
            t.update(state=state.split()[0], partition=part, alloc_cpus=n, nodes=nn,
                     billing=_tres_value(tres, "billing"),
                     req_mem_mb=_req_mem_mb(req_mem, n or 1, nn or 1),
                     timelimit_s=limit_s, elapsed=elapsed)
        elif maxrss.strip():
            try:
                t["peak_mb"] = max(t["peak_mb"] or 0, parse_mem_mb(maxrss))
            except ValueError:
                pass
    return {k: v for k, v in tasks.items() if "state" in v}


def check_alloc(sacct_text: str, expect: dict) -> tuple[dict, int]:
    """Compare a job's sacct rows with the allocation predicted before submit.

    Every predicted field that is not ``None`` must match on every started
    task; pending tasks are listed but not judged. Any difference is a
    mismatch for the agent to explain (site policy the profile does not
    capture, a wrong profile field, a script that changed) before more jobs go
    out. Exit 0 as predicted / 1 mismatch.
    """
    tasks = _parse_sacct_alloc(sacct_text)
    rows, bad = [], 0
    for t in tasks.values():
        issues: list[str] = []
        if t["state"] == "PENDING" or not t["alloc_cpus"]:
            verdict = "pending"
        else:
            def diff(name, got, want, tol=0.0):
                if want is None or got is None:
                    return
                if abs(got - want) > tol * max(abs(want), 1):
                    issues.append(f"{name}: sacct {got}, predicted {want}")
            if expect.get("partition") and t["partition"] != expect["partition"]:
                issues.append(f"partition: sacct {t['partition']}, predicted {expect['partition']}")
            diff("cpus", t["alloc_cpus"], expect.get("cpus_per_task"))
            diff("nodes", t["nodes"] or None, expect.get("nodes_per_task"))
            diff("billing", t["billing"], expect.get("billing_per_task"))
            mem = t["req_mem_mb"]
            diff("mem_mb", round(mem) if mem else None, expect.get("mem_mb_per_task"), tol=0.02)
            diff("timelimit_s", t["timelimit_s"], expect.get("timelimit_s"))
            verdict = "mismatch" if issues else "ok"
        if t["peak_mb"] and t["req_mem_mb"]:
            t["peak_frac"] = round(t["peak_mb"] / t["req_mem_mb"], 3)
        bad += verdict == "mismatch"
        rows.append(dict(t, verdict=verdict, issues=issues))

    judged = [r for r in rows if r["verdict"] != "pending"]
    summary: dict = {"tasks_seen": len(rows), "tasks_judged": len(judged), "mismatched": bad}
    if expect.get("tasks") and len(rows) != expect["tasks"]:
        summary["task_count"] = f"sacct {len(rows)}, predicted {expect['tasks']}"
        bad += 1
    if judged:
        want = expect.get("billing_per_task") or expect.get("cpus_per_task")
        billed = sum(r["billing"] or r["alloc_cpus"] for r in judged)
        if want:
            summary["billing_vs_predicted"] = round(billed / (want * len(judged)), 3)
        peaks = [r["peak_mb"] for r in judged if r["peak_mb"]]
        if peaks:
            summary["peak_rss_mb_max"] = round(max(peaks), 1)
    if not rows:
        summary["note"] = "no sacct rows for this job"
    return {"expected": expect, "summary": summary, "tasks": rows}, 1 if bad else 0


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

    p_exp = sub.add_parser("expect", help="predict the sacct allocation before submitting")
    p_exp.add_argument("script", nargs="?", default=None)
    p_exp.add_argument("--profile", default=None)
    p_exp.add_argument("--partition", default=None)
    p_exp.add_argument("--time", default=None)
    p_exp.add_argument("--cpus", default=None, help="--cpus-per-task given on the command line")
    p_exp.add_argument("--array", default=None)
    p_exp.add_argument("--extra", default="", help="raw extra sbatch options")

    p_alc = sub.add_parser(
        "check-alloc", help="compare sacct rows (stdin) with the predicted allocation"
    )
    src = p_alc.add_mutually_exclusive_group(required=True)
    src.add_argument("--expect", help="prediction JSON written by `expect`")
    src.add_argument("--cpus", type=int, help="intended cpus per task (no prediction file)")
    p_alc.add_argument("--mem", default=None, help="with --cpus: intended memory per task")

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
    if args.command == "expect":
        try:
            overrides = {f: parse_sbatch_option(args.extra, f) for f in _ALLOC_OPTIONS}
        except ValueError as exc:
            print(f"cluster_guardrail: {exc}", file=sys.stderr)
            return 2
        if overrides.get("exclusive") is None:
            overrides.pop("exclusive")
        overrides.update(partition=args.partition or overrides["partition"],
                         time=args.time or overrides["time"],
                         array=args.array or overrides["array"])
        overrides["cpus-per-task"] = args.cpus or overrides["cpus-per-task"]
        expect = cmd_expect(args.script, args.profile, overrides)
        print(expect_summary(expect), file=sys.stderr)
        print(json.dumps(expect, indent=2))
        return 0
    if args.command == "check-alloc":
        if args.expect:
            expect = json.loads(Path(args.expect).read_text(encoding="utf-8"))
        else:
            mem = parse_mem_mb(args.mem) if args.mem else None
            expect = {"cpus_per_task": args.cpus, "billing_per_task": args.cpus,
                      "mem_mb_per_task": mem}
        report, code = check_alloc(sys.stdin.read(), expect)
        print(json.dumps(report, indent=2))
        return code
    if args.command == "inspect":
        report, code = cmd_inspect(args.script, args.profile)
    else:
        report, code = cmd_check_path(args.path, args.profile)
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
