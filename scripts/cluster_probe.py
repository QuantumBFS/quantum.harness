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
import shlex
import subprocess
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

SINFO_FMT = "%P|%a|%l|%D|%t|%c|%m|%G"


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
    if wall_secs and wall_secs >= 14 * 86400:
        return "long-cpu"
    return "default-cpu"


def parse_partitions(sinfo_text: str) -> list[dict]:
    """Aggregate ``sinfo -h -o SINFO_FMT`` rows into one record per partition.

    Sums node counts by state (idle vs total); takes cores/mem/gpu/wall from the
    rows (consistent within a partition). Preserves a trailing ``*`` on the
    default partition name as ``is_default``.
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
        is_default = raw_name.endswith("*")
        name = raw_name.rstrip("*")
        rec = agg.get(name)
        if rec is None:
            wall_secs = parse_walltime_to_secs(wall)
            gpu = "" if gres in ("", "(null)") else gres
            rec = {
                "name": name,
                "cores": _int_prefix(cores),
                "mem_mb": _int_prefix(mem),
                "gpu": gpu,
                "max_wall": wall.strip(),
                "max_wall_secs": wall_secs,
                "is_default": is_default,
                "total_nodes": 0,
                "idle_nodes": 0,
            }
            rec["class"] = classify_partition(name, rec["mem_mb"], gpu, wall_secs)
            agg[name] = rec
            order.append(name)
        rec["is_default"] = rec["is_default"] or is_default
        n = _int_prefix(nodes)
        rec["total_nodes"] += n
        if state.startswith("idle"):
            rec["idle_nodes"] += n
        # A partition row may carry GPUs on some node sets and not others
        # (e.g. debug): keep the GPU spec if any row has one.
        if not rec["gpu"] and gres not in ("", "(null)"):
            rec["gpu"] = gres
    return [agg[n] for n in order]


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
    """The CPU partition a student should default to: most idle, not private."""
    cands = [p for p in partitions if p["class"] in ("default-cpu",)]
    if not cands:
        cands = [
            p
            for p in partitions
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


def probe(runner) -> dict:
    """Gather the full inventory through ``runner`` (login-shell wrapped)."""
    partitions = parse_partitions(runner.run(f"sinfo -h -o '{SINFO_FMT}'").out)
    limits = parse_scontrol_limits(runner.run("scontrol show config").out)
    modules = parse_modules(runner.run("module avail 2>&1 || true").out)
    internet = (
        runner.run(
            "curl -s -o /dev/null -w '%{http_code}' --max-time 10 https://github.com || echo 000"
        )
        .out.strip()
        .endswith("200")
    )
    return {
        "partitions": partitions,
        "limits": limits,
        "modules": modules,
        "internet_from_login": internet,
        "default_partition": pick_default_partition(partitions),
    }


# --------------------------------------------------------------------------- #
# Emitters
# --------------------------------------------------------------------------- #
def build_card_md(inv: dict, name: str) -> str:
    """Human-readable cluster card from the probed inventory."""
    lines = [f"# {name} — Cluster Card", ""]
    lines.append(
        "Probed inventory (snapshot — re-probe before relying on idle counts)."
    )
    lines.append("")
    lines.append("| Partition | Class | Cores | Mem | GPU | Wall | Idle/Total |")
    lines.append("|---|---|---|---|---|---|---|")
    for p in inv["partitions"]:
        gpu = p["gpu"] or "—"
        lines.append(
            f"| `{p['name']}`{' *' if p['is_default'] else ''} | {p['class']} | "
            f"{p['cores']} | {fmt_mem(p['mem_mb'])} | {gpu} | {p['max_wall']} | "
            f"{p['idle_nodes']}/{p['total_nodes']} |"
        )
    lines.append("")
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


def build_partitions_toml(inv: dict) -> str:
    """The ``[[partitions]]`` array + a ``[cluster_limits]`` block for a profile.

    Connection/identity are intentionally NOT emitted — those are per-user
    secrets the agent fills in with the warm-gate, not facts to probe.
    """
    out: list[str] = []
    for p in inv["partitions"]:
        if p["class"] == "private":
            continue
        out += [
            "[[partitions]]",
            f'name = "{p["name"]}"',
            f'class = "{p["class"]}"',
            f"cores = {p['cores']}",
            f'memory = "{fmt_mem(p["mem_mb"])}"',
            f'max_wall = "{p["max_wall"]}"',
            f'gpu = "{p["gpu"]}"',
            "",
        ]
    if inv["limits"]:
        out.append("[cluster_limits]")
        for k, v in inv["limits"].items():
            out.append(f"{k} = {v}")
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
    ap.add_argument(
        "--no-login-shell",
        action="store_true",
        help="force plain ssh (skip login-shell auto-detect)",
    )
    ap.add_argument("--name", default=None, help="cluster name for the card title")
    args = ap.parse_args(argv)

    login_shell = False if args.no_login_shell else detect_login_shell(args.alias)
    runner = SSHRunner(args.alias, login_shell=login_shell)
    inv = probe(runner)
    inv["login_shell"] = login_shell

    if args.emit == "json":
        print(json.dumps(inv, indent=2))
    elif args.emit == "toml":
        print(build_partitions_toml(inv))
    else:
        print(build_card_md(inv, args.name or args.alias))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
