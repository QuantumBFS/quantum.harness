#!/usr/bin/env python3
"""Read and validate the unified cluster profile (TOML).

The cluster profile is one TOML file per cluster under
``skills/using-slurm/profiles/`` holding everything a cluster-aware skill needs:
ssh connection, scheduler, partitions, network reach, region, and the student
safety ``[limits]``. This module is the single source of truth for *parsing*
that file:

* ``cluster_guardrail.py`` imports it to read ``[limits]``.
* ``harness_slurm.sh`` shells out to the ``--field`` CLI for ssh/repo fields,
  so the bash driver never parses TOML itself (bash = mechanics, Python =
  parsing).

Profile *content* (which partition, which limits) is the user's; this module
only loads, resolves, and validates shape.
"""

from __future__ import annotations

import argparse
import os
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PROFILES_DIR = "skills/using-slurm/profiles"
DEFAULT_PROFILE = f"{PROFILES_DIR}/active.toml"

# Sections every usable profile must carry. Validation is intentionally light:
# the schema is additive, so unknown keys are tolerated, but these anchors must
# be present for the cluster to be drivable at all.
REQUIRED_SECTIONS = ("identity", "connection", "scheduler")


class ProfileError(Exception):
    """Raised when a profile cannot be read or is missing required shape."""


@dataclass
class Limits:
    """The ``[limits]`` block: hard ceilings, soft thresholds, allowed paths.

    Missing sub-tables are represented as empty dicts/lists, not ``None``, so
    callers never branch on absence — they branch on *emptiness*, which the
    guardrail surfaces as "no ceiling configured" (a fail-closed warning).
    """

    hard: dict = field(default_factory=dict)
    soft: dict = field(default_factory=dict)
    allowed_roots: list[str] = field(default_factory=list)

    @property
    def configured(self) -> bool:
        """True when at least one ceiling or path root is defined."""
        return bool(self.hard or self.soft or self.allowed_roots)


# --------------------------------------------------------------------------- #
# Path resolution
# --------------------------------------------------------------------------- #
def resolve_profile_path(explicit: str | None = None) -> Path:
    """Resolve which profile file to read.

    Precedence: explicit ``--profile`` > ``$HARNESS_PROFILE_FILE`` >
    ``$HARNESS_CLUSTER_PROFILE`` (→ ``<name>.toml``) > ``active.toml``.
    Path resolution only — the file is not required to exist here.
    """
    if explicit:
        return Path(explicit)
    env_file = os.environ.get("HARNESS_PROFILE_FILE")
    if env_file:
        return Path(env_file)
    named = os.environ.get("HARNESS_CLUSTER_PROFILE")
    if named:
        return Path(f"{PROFILES_DIR}/{named}.toml")
    return Path(DEFAULT_PROFILE)


# --------------------------------------------------------------------------- #
# Load / validate
# --------------------------------------------------------------------------- #
def load_profile(path: str | Path) -> dict:
    """Parse a TOML profile. Raise ``ProfileError`` on missing/invalid file."""
    p = Path(path)
    if not p.is_file():
        raise ProfileError(f"profile not found: {p}")
    try:
        with p.open("rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ProfileError(f"malformed TOML in {p}: {exc}") from exc


def validate(profile: dict) -> list[str]:
    """Return a list of warnings; missing required sections are warnings.

    Validation never raises — a profile may be partially filled during setup.
    The guardrail decides whether a given gap is fail-closed-blocking.
    """
    warnings = []
    for section in REQUIRED_SECTIONS:
        if section not in profile:
            warnings.append(f"missing required section [{section}]")
    return warnings


# --------------------------------------------------------------------------- #
# Accessors
# --------------------------------------------------------------------------- #
def get_field(profile: dict, dotted: str) -> object | None:
    """Descend a dotted path (``ssh.alias``) through nested tables.

    Returns ``None`` if any segment is missing or a non-table is traversed.
    Lists/arrays are returned whole; this is for scalar leaf lookups.
    """
    node: object = profile
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def get_partition(profile: dict, name: str) -> dict | None:
    """Return the named ``[[partitions]]`` row, or ``None`` when absent."""
    partitions = profile.get("partitions", [])
    if not isinstance(partitions, list):
        return None
    for partition in partitions:
        if isinstance(partition, dict) and partition.get("name") == name:
            return partition
    return None


def get_limits(profile: dict) -> Limits:
    """Extract ``[limits]`` into a :class:`Limits`, tolerating absence."""
    block = profile.get("limits", {})
    if not isinstance(block, dict):
        return Limits()
    hard = block.get("hard", {})
    soft = block.get("soft", {})
    paths = block.get("paths", {})
    roots = paths.get("allowed_roots", []) if isinstance(paths, dict) else []
    return Limits(
        hard=hard if isinstance(hard, dict) else {},
        soft=soft if isinstance(soft, dict) else {},
        allowed_roots=list(roots) if isinstance(roots, list) else [],
    )


# --------------------------------------------------------------------------- #
# CLI (consumed by harness_slurm.sh)
# --------------------------------------------------------------------------- #
def _format_value(value: object) -> str:
    """Render a leaf value for the ``--field`` CLI (one line)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return str(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read a field from a cluster profile.")
    parser.add_argument("--field", required=True, help="dotted path, e.g. ssh.alias")
    parser.add_argument(
        "--partition",
        default=None,
        help="read --field from the named [[partitions]] row",
    )
    parser.add_argument("--profile", default=None, help="profile file (default: resolved active)")
    args = parser.parse_args(argv)

    path = resolve_profile_path(args.profile)
    try:
        profile = load_profile(path)
    except ProfileError as exc:
        print(f"cluster_profile: {exc}", file=sys.stderr)
        return 1

    scope = profile
    if args.partition:
        scope = get_partition(profile, args.partition)
        if scope is None:
            print(
                f"cluster_profile: partition '{args.partition}' not found in {path}",
                file=sys.stderr,
            )
            return 1

    value = get_field(scope, args.field)
    if value is None:
        print(f"cluster_profile: field '{args.field}' not set in {path}", file=sys.stderr)
        return 1
    print(_format_value(value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
