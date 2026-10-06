#!/usr/bin/env python3
"""Probe a Slurm cluster over ssh and draft a profile + card.

Replaces the agent hand-running ``sinfo`` / ``scontrol`` / ``module avail`` and
assembling the TOML profile and the human-readable card by hand — a sequence
that is deterministic, so it belongs in a script, not in LLM turns. The agent's
job shrinks to *ratifying* the partition choice and the ``[limits]`` (judgment),
not gathering the facts (mechanism).

Design for testability: all ssh/exec goes through an injectable ``Runner``, and
every parser/emitter is a pure function over captured command output. Tests feed
real ``sinfo``/``scontrol`` text and never touch a cluster.

Remote commands run through a login shell by default, because some clusters put
the scheduler only on the login-shell PATH (the harness ``login_shell`` gotcha);
``detect_login_shell`` decides whether that wrapping is actually needed.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass

# Module names worth surfacing in the card (containers, languages, toolchains).
MODULE_KEYS = (
    "julia",
    "anaconda",
    "apptainer",
    "singularity",
    "cuda",
    "gcc",
    "openmpi",
    "mpich",
)

SINFO_FMT = "%P|%a|%l|%D|%t|%c|%m|%G|%f"

# Per-user association and QOS caps — where the limits a student actually hits
# live (partition MaxTime is only the outer bound).
ASSOC_CMD = (
    "sacctmgr -n -P show assoc where user=$USER "
    "format=Account,Partition,QOS,DefaultQOS"
)
QOS_CMD = (
    "sacctmgr -n -P show qos "
    "format=Name,MaxWall,MaxTRESPU,MaxJobsPU,MaxSubmitPU"
)

# Proposed-limit defaults when the cluster imposes nothing tighter.
DEFAULT_MAX_ARRAY = 200
DEFAULT_WARN_WALLTIME_SECS = 8 * 3600


class ProbeError(RuntimeError):
    """The cluster could not be inventoried (no partitions came back)."""


# --------------------------------------------------------------------------- #
# Runner — the one impure seam
# --------------------------------------------------------------------------- #
@dataclass
class CmdResult:
    out: str
    code: int


class SSHRunner:
    """Runs a command on the cluster via ``ssh``, optionally in a login shell."""

    def __init__(self, alias: str, login_shell: bool = True, timeout: int = 30):
        self.alias = alias
        self.login_shell = login_shell
        self.timeout = timeout

    def run(self, cmd: str) -> CmdResult:
        remote = f"bash -lc {shlex.quote(cmd)}" if self.login_shell else cmd
        try:
            p = subprocess.run(
                [
                    "ssh",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    f"ConnectTimeout={self.timeout}",
                    self.alias,
                    remote,
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout + 10,
            )
            # module avail and friends print to stderr; fold it in.
            return CmdResult((p.stdout or "") + (p.stderr or ""), p.returncode)
        except (subprocess.TimeoutExpired, OSError) as exc:
            return CmdResult(str(exc), 124)


# --------------------------------------------------------------------------- #
# Pure parsers
# --------------------------------------------------------------------------- #
def parse_walltime_to_secs(s: str) -> int | None:
    """Parse a Slurm walltime (``D-HH:MM:SS`` / ``HH:MM:SS`` / ``MM:SS``)."""
    s = s.strip()
    if not s or s.lower() in ("infinite", "n/a", "unlimited"):
        return None
    days = 0
    if "-" in s:
        d, s = s.split("-", 1)
        days = int(d)
    parts = [int(x) for x in s.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, sec = parts[-3:]
    return days * 86400 + h * 3600 + m * 60 + sec


def _int_prefix(s: str) -> int:
    """Leading integer of e.g. ``64`` or ``64+`` → 64; 0 if none."""
    num = ""
    for ch in s.strip():
        if ch.isdigit():
            num += ch
        else:
            break
    return int(num) if num else 0


def fmt_mem(mb: int) -> str:
    """MB → human, matching card style: 512000→512G, 1024000→1T, 3072000→3T."""
    gb = round(mb / 1000)
    return f"{gb // 1000}T" if gb >= 1000 else f"{gb}G"


def classify_partition(name: str, mem_mb: int, gpu: str, wall_secs: int | None) -> str:
    """Map a partition to a class skills pick by (not by raw name)."""
    n = name.rstrip("*")
    if n.endswith("_rent") or n.endswith("_qos"):
        return "private"
    if n == "debug":
        return "debug"
    if gpu:
        return "long-gpu" if wall_secs and wall_secs >= 14 * 86400 else "gpu"
    if mem_mb >= 2_000_000:
        return "high-mem"
    if "emergency" in n:
        return "emergency"
    if "preempt" in n:
        return "preemptible"
    if wall_secs and wall_secs >= 14 * 86400:
        return "long-cpu"
    return "default-cpu"


def parse_partitions(sinfo_text: str) -> list[dict]:
    """Aggregate ``sinfo -h -o SINFO_FMT`` rows into one record per partition.

    Sums node counts by state (idle vs total) and groups rows by hardware into
    ``node_types`` (cores, memory, GRES, features), because one partition often
    mixes node generations. ``cores`` / ``mem_mb`` are the largest node type
    (the most one node can hold); the class is judged on the smallest memory so
    a partition with a few big nodes is not labelled high-mem. Preserves a
    trailing ``*`` on the default partition name as ``is_default``. The ninth
    (features) column is optional so older captures still parse.
    """
    agg: dict[str, dict] = {}
    order: list[str] = []
    for line in sinfo_text.splitlines():
        line = line.strip()
        if not line or line.startswith("PARTITION"):
            continue
        cols = line.split("|")
        if len(cols) < 8:
            continue
        raw_name, _avail, wall, nodes, state, cores, mem, gres = cols[:8]
        # Skip anything that is not a data row (ssh/sinfo diagnostics folded
        # in from stderr can contain '|').
        try:
            parse_walltime_to_secs(wall)
        except ValueError:
            continue
        if not nodes.strip().isdigit():
            continue
        features = cols[8].strip() if len(cols) > 8 else ""
        if features == "(null)":
            features = ""
        is_default = raw_name.endswith("*")
        name = raw_name.rstrip("*")
        gpu = "" if gres in ("", "(null)") else gres
        rec = agg.get(name)
        if rec is None:
            rec = {
                "name": name,
                "gpu": gpu,
                "max_wall": wall.strip(),
                "max_wall_secs": parse_walltime_to_secs(wall),
                "is_default": is_default,
                "total_nodes": 0,
                "idle_nodes": 0,
                "_types": {},
            }
            agg[name] = rec
            order.append(name)
        rec["is_default"] = rec["is_default"] or is_default
        n = _int_prefix(nodes)
        rec["total_nodes"] += n
        if state.startswith("idle"):
            rec["idle_nodes"] += n
        # A partition row may carry GPUs on some node sets and not others
        # (e.g. debug): keep the GPU spec if any row has one.
        if not rec["gpu"] and gpu:
            rec["gpu"] = gpu
        key = (_int_prefix(cores), _int_prefix(mem), gpu, features)
        rec["_types"][key] = rec["_types"].get(key, 0) + n

    out = []
    for name in order:
        rec = agg[name]
        types = [
            {"cores": c, "mem_mb": m, "gpu": g, "features": f, "nodes": n}
            for (c, m, g, f), n in rec.pop("_types").items()
        ]
        rec["node_types"] = types
        rec["cores"] = max(t["cores"] for t in types)
        rec["mem_mb"] = max(t["mem_mb"] for t in types)
        rec["class"] = classify_partition(
            name, min(t["mem_mb"] for t in types), rec["gpu"], rec["max_wall_secs"]
        )
        out.append(rec)
    return out


def _kv_tokens(line: str) -> dict[str, str]:
    """Split one ``scontrol ... -o`` line into ``Key=Value`` pairs."""
    out: dict[str, str] = {}
    for tok in line.split():
        k, sep, v = tok.partition("=")
        if sep:
            out[k] = v
    return out


def _csv(v: str | None) -> list[str]:
    """Slurm list value → list; ``(null)`` / empty → ``[]``."""
    if not v or v in ("(null)", "N/A"):
        return []
    return [x for x in v.split(",") if x]


def _mem_mb(v: str | None) -> int | None:
    """Slurm memory field in MB (``2764``) → int; ``UNLIMITED`` / absent → ``None``."""
    if not v or not v.isdigit() or int(v) == 0:
        return None
    return int(v)


def parse_scontrol_partitions(text: str) -> dict[str, dict]:
    """Access rules and allocation policy from ``scontrol show partition -o``.

    ``DefMemPerCPU`` / ``MaxMemPerCPU`` are read here because many sites set
    them per partition only (``scontrol show config`` then says nothing).
    """
    out: dict[str, dict] = {}
    for line in text.splitlines():
        kv = _kv_tokens(line)
        name = kv.get("PartitionName")
        if not name:
            continue
        qos = kv.get("QoS", "")
        out[name] = {
            "allow_accounts": _csv(kv.get("AllowAccounts")),
            "deny_accounts": _csv(kv.get("DenyAccounts")),
            "allow_qos": _csv(kv.get("AllowQos")),
            "deny_qos": _csv(kv.get("DenyQos")),
            "qos": "" if qos in ("", "N/A", "(null)") else qos,
            "oversubscribe": kv.get("OverSubscribe", ""),
            "def_mem_per_cpu_mb": _mem_mb(kv.get("DefMemPerCPU")),
            "max_mem_per_cpu_mb": _mem_mb(kv.get("MaxMemPerCPU")),
        }
    return out


def parse_assoc(text: str) -> list[dict]:
    """The user's associations from ``ASSOC_CMD`` (pipe-separated)."""
    out = []
    for line in text.splitlines():
        cols = line.strip().split("|")
        if len(cols) < 3 or not cols[0]:
            continue
        out.append(
            {
                "account": cols[0],
                "partition": cols[1],
                "qos": _csv(cols[2]),
                "default_qos": cols[3] if len(cols) > 3 else "",
            }
        )
    return out


def parse_tres(spec: str) -> dict[str, int]:
    """``cpu=512,node=4,gres/gpu=8,mem=6000G`` → ``{cpu: 512, node: 4, gpu: 8}``."""
    out: dict[str, int] = {}
    for item in _csv(spec):
        k, _, v = item.partition("=")
        k = k.split("/")[-1]
        if k in ("cpu", "node", "gpu") and v.isdigit():
            out[k] = int(v)
    return out


def parse_qos(text: str) -> dict[str, dict]:
    """Per-user caps per QOS from ``QOS_CMD``. Absent caps are omitted."""
    out: dict[str, dict] = {}
    for line in text.splitlines():
        cols = line.strip().split("|")
        if len(cols) < 5 or not cols[0]:
            continue
        name, wall, tres_pu, jobs_pu, submit_pu = cols[:5]
        caps: dict = {}
        if parse_walltime_to_secs(wall):
            caps["max_wall"] = wall
        tres = parse_tres(tres_pu)
        for src, dst in (("cpu", "max_cpus"), ("node", "max_nodes"), ("gpu", "max_gpus")):
            if src in tres:
                caps[dst] = tres[src]
        if jobs_pu.isdigit():
            caps["max_jobs"] = int(jobs_pu)
        if submit_pu.isdigit():
            caps["max_submit"] = int(submit_pu)
        out[name] = caps
    return out


def parse_test_only(text: str) -> dict[str, int]:
    """Processors a 1-task job would get, per partition, from a batch of
    ``sbatch --test-only`` runs each preceded by an ``@@<partition>`` marker."""
    out: dict[str, int] = {}
    current = None
    for line in text.splitlines():
        if line.startswith("@@"):
            current = line[2:].strip()
            continue
        m = re.search(r"using (\d+) processors", line)
        if current and m:
            out[current] = int(m.group(1))
    return out


def partition_access(meta: dict | None, assocs: list[dict], name: str) -> bool | None:
    """Can any of the user's associations submit to this partition?

    ``None`` when either side is unknown (no scontrol row, or sacctmgr gave
    nothing) — callers keep such partitions rather than guess them away.
    """
    if meta is None or not assocs:
        return None
    allow_acc, deny_acc = meta["allow_accounts"], meta["deny_accounts"]
    allow_qos, deny_qos = meta["allow_qos"], meta["deny_qos"]
    for a in assocs:
        if a["partition"] and a["partition"] != name:
            continue
        if allow_acc and "ALL" not in allow_acc and a["account"] not in allow_acc:
            continue
        if a["account"] in deny_acc:
            continue
        usable = [q for q in a["qos"] if q not in deny_qos]
        if allow_qos and "ALL" not in allow_qos and not set(usable) & set(allow_qos):
            continue
        return True
    return False


def user_caps(meta: dict | None, assocs: list[dict], qos: dict[str, dict]) -> dict:
    """Per-user caps for jobs in a partition: the user's default QOS, overlaid
    by the partition QOS (Slurm lets the partition QOS win by default)."""
    caps: dict = {}
    for a in assocs:
        if a["default_qos"] in qos:
            caps.update(qos[a["default_qos"]])
            break
    if meta and meta["qos"] in qos:
        caps.update(qos[meta["qos"]])
    return caps


def secs_to_walltime(secs: int) -> str:
    """Seconds → Slurm ``D-HH:MM:SS`` (or ``HH:MM:SS`` under a day)."""
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    hms = f"{h:02d}:{m:02d}:{s:02d}"
    return f"{d}-{hms}" if d else hms


def suggest_limits(inv: dict, partition: str | None = None) -> dict:
    """Proposed ``[limits]`` from the real per-user caps of one partition.

    Hard caps are the tighter of the partition bound and the user's QOS; the
    student ratifies (and usually tightens) them. Returns ``{}`` when the
    partition is unknown.
    """
    name = partition or inv.get("default_partition")
    rows = {p["name"]: p for p in inv["partitions"]}
    p = rows.get(name or "")
    if p is None:
        return {}
    caps = p.get("user_caps", {})

    walls = [
        s
        for s in (p["max_wall_secs"], parse_walltime_to_secs(caps.get("max_wall", "")))
        if s
    ]
    hard: dict = {}
    if walls:
        hard["max_walltime"] = secs_to_walltime(min(walls))
    hard["max_nodes"] = caps.get("max_nodes", p["total_nodes"])
    hard["max_cpus"] = caps.get("max_cpus", hard["max_nodes"] * p["cores"])
    arrays = [DEFAULT_MAX_ARRAY, caps.get("max_submit")]
    if inv.get("limits", {}).get("max_array_size"):
        arrays.append(inv["limits"]["max_array_size"] - 1)
    hard["max_array_size"] = min(a for a in arrays if a)

    soft: dict = {}
    if walls:
        soft["warn_walltime"] = secs_to_walltime(
            min(min(walls), DEFAULT_WARN_WALLTIME_SECS)
        )
    # Anything beyond one (largest) node deserves a second look.
    soft["warn_cpus"] = min(p["cores"], hard["max_cpus"])
    soft["unusual_partitions"] = [
        q["name"]
        for q in inv["partitions"]
        if q["name"] != name
        and q.get("accessible") is not False
        and q["class"] not in ("default-cpu", "debug", "private")
    ]
    return {"partition": name, "hard": hard, "soft": soft}


def parse_scontrol_limits(text: str) -> dict:
    """Pull scheduler-wide caps from ``scontrol show config``."""
    keys = {
        "MaxArraySize": "max_array_size",
        "DefMemPerCPU": "def_mem_per_cpu_mb",
        "MaxMemPerCPU": "max_mem_per_cpu_mb",
        "MaxJobCount": "max_job_count",
    }
    out: dict = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if k in keys and v and v.split()[0].lstrip("-").isdigit():
            out[keys[k]] = int(v.split()[0])
    return out


def parse_modules(text: str, keys: tuple[str, ...] = MODULE_KEYS) -> list[str]:
    """Extract module names matching the key prefixes from ``module avail``."""
    found: set[str] = set()
    for tok in text.replace("\t", " ").split():
        low = tok.lower()
        if any(low.startswith(k) for k in keys) and "/" not in tok[:1]:
            found.add(tok)
    return sorted(found)


def pick_default_partition(partitions: list[dict]) -> str | None:
    """The CPU partition a student should default to: not private, not one the
    user's associations cannot submit to, preferring a partition reserved for
    the user's own account (their group's allocation), then the most idle."""
    usable = [p for p in partitions if p.get("accessible") is not False]
    cands = [p for p in usable if p["class"] == "default-cpu" and p.get("own_account")]
    if not cands:
        cands = [p for p in usable if p["class"] in ("default-cpu",)]
    if not cands:
        cands = [
            p
            for p in usable
            if p["class"] not in ("private", "gpu", "long-gpu", "debug")
        ]
    if not cands:
        return None
    return max(cands, key=lambda p: (p["idle_nodes"], p["total_nodes"]))["name"]


# --------------------------------------------------------------------------- #
# Probe orchestration (uses a Runner)
# --------------------------------------------------------------------------- #
def detect_login_shell(alias: str, timeout: int = 30, runner_factory=SSHRunner) -> bool:
    """True if the scheduler is reachable only via a login shell.

    Compares ``command -v sbatch`` with a plain non-interactive ssh vs a login
    shell. If plain fails but login-shell succeeds, the profile needs
    ``login_shell = true``. ``runner_factory`` is injectable for testing.
    """
    plain = runner_factory(alias, login_shell=False, timeout=timeout)
    if plain.run("command -v sbatch").out.strip():
        return False
    login = runner_factory(alias, login_shell=True, timeout=timeout)
    return bool(login.run("command -v sbatch").out.strip())


def whole_node_probe_cmd(names: list[str]) -> str:
    """One remote command that dry-runs a 1-task job in each partition.

    ``sbatch --test-only`` submits nothing; it reports what the scheduler
    *would* allocate, which is the only reliable way to see site policies
    (job_submit plugins, partition defaults) that hand out whole nodes.
    """
    parts = [
        f"echo @@{shlex.quote(n)}; "
        f"sbatch --test-only -p {shlex.quote(n)} -n 1 -t 1 --wrap=true 2>&1"
        for n in names
    ]
    return "; ".join(parts)


def annotate_partitions(
    partitions: list[dict],
    meta: dict[str, dict],
    assocs: list[dict],
    qos: dict[str, dict],
    test_only: dict[str, int],
    cluster_limits: dict | None = None,
) -> None:
    """Add ``accessible`` / ``qos`` / ``user_caps`` / ``whole_node`` and the
    per-CPU memory (partition value, else the cluster-wide one) in place."""
    accounts = {a["account"] for a in assocs}
    cluster_limits = cluster_limits or {}
    for p in partitions:
        m = meta.get(p["name"])
        p["accessible"] = partition_access(m, assocs, p["name"])
        p["qos"] = m["qos"] if m else ""
        p["user_caps"] = user_caps(m, assocs, qos)
        # A QOS that grants zero cpus or nodes is a request-only gate.
        if p["user_caps"].get("max_cpus") == 0 or p["user_caps"].get("max_nodes") == 0:
            p["accessible"] = False
        # Restricted to one of the user's own accounts: the group's partition.
        allow = m["allow_accounts"] if m else []
        p["own_account"] = bool(allow) and "ALL" not in allow and bool(set(allow) & accounts)
        exclusive = bool(m and m["oversubscribe"].upper().startswith("EXCLUSIVE"))
        p["whole_node"] = exclusive or test_only.get(p["name"], 1) > 1
        # Asking for more memory than cpus × MaxMemPerCPU makes Slurm raise the
        # cpu count (and the bill) silently; job sizing needs these numbers.
        for key in ("def_mem_per_cpu_mb", "max_mem_per_cpu_mb"):
            v = (m or {}).get(key) or cluster_limits.get(key)
            if v:
                p[key] = v


def probe(runner) -> dict:
    """Gather the full inventory through ``runner`` (login-shell wrapped)."""
    sinfo = runner.run(f"sinfo -h -o '{SINFO_FMT}'")
    partitions = parse_partitions(sinfo.out)
    if sinfo.code != 0 or not partitions:
        # Never draft a profile from an empty inventory (slow controller, ssh
        # drop): say so and let the caller retry.
        raise ProbeError(f"sinfo returned no partitions (exit {sinfo.code}): {sinfo.out[:200]}")
    meta = parse_scontrol_partitions(runner.run("scontrol show partition -o").out)
    assocs = parse_assoc(runner.run(ASSOC_CMD).out)
    qos = parse_qos(runner.run(QOS_CMD).out)
    cpu_names = [
        p["name"]
        for p in partitions
        if not p["gpu"]
        and p["class"] != "private"
        and partition_access(meta.get(p["name"]), assocs, p["name"]) is not False
    ]
    test_only = (
        parse_test_only(runner.run(whole_node_probe_cmd(cpu_names)).out)
        if cpu_names
        else {}
    )
    limits = parse_scontrol_limits(runner.run("scontrol show config").out)
    annotate_partitions(partitions, meta, assocs, qos, test_only, limits)
    modules = parse_modules(runner.run("module avail 2>&1 || true").out)
    internet = (
        runner.run(
            "curl -s -o /dev/null -w '%{http_code}' --max-time 10 https://github.com || echo 000"
        )
        .out.strip()
        .endswith("200")
    )
    inv = {
        "partitions": partitions,
        "accounts": sorted({a["account"] for a in assocs}),
        "limits": limits,
        "modules": modules,
        "internet_from_login": internet,
        "default_partition": pick_default_partition(partitions),
    }
    inv["suggested_limits"] = suggest_limits(inv)
    return inv


# --------------------------------------------------------------------------- #
# Emitters
# --------------------------------------------------------------------------- #
def _visible(inv: dict, drop_private: bool) -> tuple[list[dict], list[str]]:
    """Partitions worth showing + the hidden names. Partitions the user's
    associations cannot submit to are always hidden; ``private`` ones only
    when ``drop_private`` (the profile keeps them out, the card lists them)."""
    shown, hidden = [], []
    for p in inv["partitions"]:
        if p.get("accessible") is False or (drop_private and p["class"] == "private"):
            hidden.append(p["name"])
        else:
            shown.append(p)
    return shown, hidden


def _fmt_caps(caps: dict) -> str:
    """``{max_cpus: 512, max_jobs: 50}`` → ``512 cpu, 50 jobs`` (per user)."""
    labels = (
        ("max_cpus", "cpu"),
        ("max_nodes", "nodes"),
        ("max_gpus", "gpu"),
        ("max_jobs", "running"),
        ("max_submit", "queued"),
        ("max_wall", "wall"),
    )
    parts = [f"{caps[k]} {label}" for k, label in labels if k in caps]
    return ", ".join(parts) or "—"


def _gpu_models(p: dict) -> str:
    """Distinct GPU models across a partition's node types (``gpu:h100:4`` → h100)."""
    models: list[str] = []
    for t in p.get("node_types", []) or [{"gpu": p["gpu"]}]:
        for g in _csv(t["gpu"]):
            parts = g.split("(")[0].split(":")
            model = parts[1] if len(parts) >= 3 else parts[-1]
            if model and model not in models:
                models.append(model)
    return ", ".join(models)


MAX_CARD_TYPES = 6


def _fmt_mem_per_cpu(p: dict) -> str:
    """``2700M/2764M`` from the partition's DefMemPerCPU / MaxMemPerCPU."""
    d, m = p.get("def_mem_per_cpu_mb"), p.get("max_mem_per_cpu_mb")
    if not d and not m:
        return "—"
    return f"{f'{d}M' if d else '—'}/{f'{m}M' if m else '—'}"


def _fmt_node_type(t: dict) -> str:
    """One node type for the card: ``12× 96c/1.5T cpu,fast-net``."""
    bits = [f"{t['nodes']}× {t['cores']}c/{fmt_mem(t['mem_mb'])}"]
    if t["gpu"]:
        bits.append(t["gpu"])
    if t["features"]:
        bits.append(t["features"])
    return " ".join(bits)


def build_card_md(inv: dict, name: str) -> str:
    """Human-readable cluster card from the probed inventory."""
    shown, hidden = _visible(inv, drop_private=False)
    lines = [f"# {name} — Cluster Card", ""]
    lines.append(
        "Probed inventory (snapshot — re-probe before relying on idle counts)."
    )
    lines.append("")
    lines.append(
        "| Partition | Class | Cores | Mem | Mem/cpu def/max | GPU | Wall | Idle/Total "
        "| Whole node | Per-user caps |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for p in shown:
        gpu = _gpu_models(p) or "—"
        lines.append(
            f"| `{p['name']}`{' *' if p['is_default'] else ''} | {p['class']} | "
            f"{p['cores']} | {fmt_mem(p['mem_mb'])} | {_fmt_mem_per_cpu(p)} | "
            f"{gpu} | {p['max_wall']} | "
            f"{p['idle_nodes']}/{p['total_nodes']} | "
            f"{'yes' if p.get('whole_node') else 'no'} | "
            f"{_fmt_caps(p.get('user_caps', {}))} |"
        )
    lines.append("")
    # Group partitions that share the same node set, and cap the list length.
    groups: dict[tuple, list[str]] = {}
    for p in shown:
        if len(p.get("node_types", [])) > 1:
            key = tuple(_fmt_node_type(t) for t in p["node_types"])
            groups.setdefault(key, []).append(p["name"])
    if groups:
        lines.append("**Mixed hardware** (pin with `--constraint=<feature>`):")
        for key, names in groups.items():
            types = "; ".join(key[:MAX_CARD_TYPES])
            if len(key) > MAX_CARD_TYPES:
                types += f"; +{len(key) - MAX_CARD_TYPES} more (see `--emit json`)"
            lines.append(f"- {', '.join(f'`{n}`' for n in names)}: {types}")
        lines.append("")
    if inv.get("accounts"):
        lines.append(f"**Your accounts:** {', '.join(inv['accounts'])}.")
    if hidden:
        lines.append(
            f"**Not usable by you (hidden):** {len(hidden)} partitions "
            f"({', '.join(hidden)})."
        )
    if inv["limits"]:
        lims = ", ".join(f"{k}={v}" for k, v in inv["limits"].items())
        lines.append(f"**Scheduler caps:** {lims}.")
    if inv["modules"]:
        lines.append(f"**Modules (key):** {', '.join(inv['modules'])}.")
    lines.append(
        f"**Internet from login:** {'yes' if inv['internet_from_login'] else 'no'}."
    )
    lines.append(f"**Default CPU partition:** `{inv['default_partition']}`.")
    return "\n".join(lines) + "\n"


def _toml_value(v) -> str:
    """Scalar / list / flat dict → TOML literal."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k} = {_toml_value(x)}" for k, x in v.items()) + " }"
    return f'"{v}"'


def build_partitions_toml(inv: dict) -> str:
    """``[[partitions]]`` rows, ``[cluster_limits]``, and a proposed ``[limits]``.

    Connection/identity are intentionally NOT emitted — those are per-user
    secrets the agent fills in with the warm-gate, not facts to probe. Private
    partitions and partitions the user's associations cannot use are dropped.
    The ``[limits]`` block is a proposal for the student to ratify.
    """
    out: list[str] = []
    shown, _hidden = _visible(inv, drop_private=True)
    for p in shown:
        out += [
            "[[partitions]]",
            f'name = "{p["name"]}"',
            f'class = "{p["class"]}"',
            f"cores = {p['cores']}",
            f'memory = "{fmt_mem(p["mem_mb"])}"',
            f'max_wall = "{p["max_wall"]}"',
            f'gpu = "{p["gpu"]}"',
        ]
        if p.get("whole_node"):
            out.append("whole_node = true")
        for key in ("def_mem_per_cpu_mb", "max_mem_per_cpu_mb"):
            if p.get(key):
                out.append(f"{key} = {p[key]}")
        if p.get("qos"):
            out.append(f'qos = "{p["qos"]}"')
        if p.get("user_caps"):
            out.append(f"user_caps = {_toml_value(p['user_caps'])}")
        out.append("")
        if len(p.get("node_types", [])) > 1:
            for t in p["node_types"]:
                out += [
                    "[[partitions.node_types]]",
                    f"cores = {t['cores']}",
                    f'memory = "{fmt_mem(t["mem_mb"])}"',
                    f'gpu = "{t["gpu"]}"',
                    f"features = {_toml_value([f for f in t['features'].split(',') if f])}",
                    f"nodes = {t['nodes']}",
                    "",
                ]
    if inv["limits"]:
        out.append("[cluster_limits]")
        for k, v in inv["limits"].items():
            out.append(f"{k} = {v}")
        out.append("")
    sugg = inv.get("suggested_limits") or {}
    if sugg:
        out.append(
            f"# Proposed from the per-user caps of '{sugg['partition']}' — ratify "
            "(and usually tighten) before saving."
        )
        for tier in ("hard", "soft"):
            out.append(f"[limits.{tier}]")
            for k, v in sugg[tier].items():
                out.append(f"{k} = {_toml_value(v)}")
            out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Probe a Slurm cluster; draft profile + card."
    )
    ap.add_argument("--alias", required=True, help="ssh alias of the login node")
    ap.add_argument("--emit", choices=("json", "toml", "card"), default="json")
    shell = ap.add_mutually_exclusive_group()
    shell.add_argument(
        "--no-login-shell",
        action="store_true",
        help="force plain ssh (skip login-shell auto-detect)",
    )
    shell.add_argument(
        "--login-shell",
        action="store_true",
        help="force a login shell (skip auto-detect; the profile already says so)",
    )
    ap.add_argument("--name", default=None, help="cluster name for the card title")
    ap.add_argument(
        "--limits-for",
        default=None,
        metavar="PARTITION",
        help="seed the proposed [limits] from this partition (default: the picked default)",
    )
    args = ap.parse_args(argv)

    if args.no_login_shell or args.login_shell:
        login_shell = args.login_shell
    else:
        login_shell = detect_login_shell(args.alias)
    runner = SSHRunner(args.alias, login_shell=login_shell)
    try:
        inv = probe(runner)
    except ProbeError as exc:
        print(f"cluster_probe: {exc}", file=sys.stderr)
        return 1
    inv["login_shell"] = login_shell
    if args.limits_for:
        inv["suggested_limits"] = suggest_limits(inv, args.limits_for)

    if args.emit == "json":
        print(json.dumps(inv, indent=2))
    elif args.emit == "toml":
        print(build_partitions_toml(inv))
    else:
        print(build_card_md(inv, args.name or args.alias))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
