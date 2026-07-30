"""Strict audited cluster profiles used by production wrappers."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .production_schema import payload_sha256, validate_envelope


@dataclass(frozen=True)
class ClusterProfile:
    controller: str
    active: bool
    scheduler: dict[str, Any]
    allowed_roles: tuple[str, ...]
    array_concurrency: int
    threads: int
    project_root: str
    results_root: str
    evidence: dict[str, Any]

    @property
    def sha256(self) -> str:
        return payload_sha256(self.to_payload())

    def to_payload(self) -> dict[str, Any]:
        return {
            "controller": self.controller,
            "partition": self.scheduler["partition"],
            "account": self.scheduler["account"],
            "qos": self.scheduler["qos"],
            "nodes": self.scheduler["nodes"],
            "ntasks": self.scheduler["ntasks"],
            "cpus_per_task": self.scheduler["cpus_per_task"],
            "memory": self.scheduler["mem"],
            "wall_time": self.scheduler["time"],
            "array_concurrency": self.array_concurrency,
            "approved_project_root": self.project_root,
            "approved_results_root": self.results_root,
            "scheduler_facts": dict(self.evidence),
        }

    def require_role(self, role: str) -> None:
        if role not in self.allowed_roles:
            if self.controller == "qdeshell":
                raise ValueError("CPU-only roles are forbidden on Qdeshell")
            raise ValueError(f"role {role!r} is not enabled on {self.controller}")

    def contains_result(self, value: Path | str) -> bool:
        candidate = Path(value)
        root = Path(self.results_root)
        return candidate.is_absolute() and (
            candidate == root or root in candidate.parents
        )


def load_profile(path: Path | str, *, allow_inactive: bool = False) -> ClusterProfile:
    profile_path = Path(path)
    value = json.loads(profile_path.read_text(encoding="utf-8"))
    if isinstance(value, Mapping) and value.get("active") is False:
        if not allow_inactive:
            raise ValueError(f"cluster profile {value.get('controller')} is inactive")
        raise ValueError("inactive discovery records are not executable profiles")
    payload = validate_envelope(profile_path, "challenge15.cluster-profile.v1")
    controller = str(payload["controller"])
    scheduler = {
        "partition": payload["partition"],
        "account": payload["account"],
        "qos": payload["qos"],
        "nodes": payload["nodes"],
        "ntasks": payload["ntasks"],
        "cpus_per_task": payload["cpus_per_task"],
        "mem": payload["memory"],
        "time": payload["wall_time"],
    }
    if controller == "qdeshell":
        scheduler["gres"] = f"gpu:{payload['scheduler_facts']['gpu']}"
    allowed_roles = (
        ("training", "coordinate")
        if controller == "qdeshell"
        else ("oracle", "exact", "reducer")
    )
    profile = ClusterProfile(
        controller=controller,
        active=True,
        scheduler=dict(scheduler),
        allowed_roles=allowed_roles,
        array_concurrency=int(payload["array_concurrency"]),
        threads=int(payload["cpus_per_task"]),
        project_root=str(payload["approved_project_root"]),
        results_root=str(payload["approved_results_root"]),
        evidence=dict(payload["scheduler_facts"]),
    )
    _validate(profile)
    return profile


def _validate(profile: ClusterProfile) -> None:
    if profile.controller not in {"qdeshell", "lasg02", "wuzh02"}:
        raise ValueError("unknown production controller")
    if profile.array_concurrency < 1 or profile.threads < 1:
        raise ValueError("profile concurrency and threads must be positive")
    for label, value in (
        ("project", profile.project_root),
        ("results", profile.results_root),
    ):
        if not Path(value).is_absolute():
            raise ValueError(f"profile {label} root must be absolute")
    if profile.controller == "qdeshell":
        exact = {
            "partition": "dzagnormal",
            "account": "giggleliu",
            "qos": "user_jiangweiqi",
            "nodes": 1,
            "ntasks": 1,
            "cpus_per_task": 8,
            "gres": "gpu:NVIDIAA80080GBPCIeLC:1",
            "mem": "60000M",
            "time": "24:00:00",
        }
        if profile.scheduler != exact or profile.allowed_roles != (
            "training",
            "coordinate",
        ):
            raise ValueError("Qdeshell profile differs from audited GPU shape")
    if profile.controller == "lasg02":
        exact = {
            "partition": "ihicnormal",
            "account": "chenkun2025",
            "qos": "user_student090",
            "nodes": 1,
            "ntasks": 1,
            "cpus_per_task": 24,
            "mem": "80000M",
            "time": "24:00:00",
        }
        if profile.scheduler != exact or profile.allowed_roles != (
            "oracle",
            "exact",
            "reducer",
        ):
            raise ValueError("LASG02 profile differs from audited CPU shape")
    if profile.controller == "wuzh02":
        validate_wuzh_capacity(
            cpus_per_task=profile.scheduler["cpus_per_task"],
            memory=profile.scheduler["mem"],
        )
        if profile.evidence.get("status") not in {
            "live-verified",
            "audited-active",
        }:
            raise ValueError("WUZH02 capacity evidence is not active and audited")


def validate_wuzh_capacity(*, cpus_per_task: int, memory: str) -> None:
    if (
        isinstance(cpus_per_task, bool)
        or not isinstance(cpus_per_task, int)
        or cpus_per_task < 128
        or not isinstance(memory, str)
        or not memory.endswith("M")
    ):
        raise ValueError("WUZH02 capacity requires 128 cores and 500000 MiB")
    try:
        memory_mib = int(memory[:-1])
    except ValueError as exc:
        raise ValueError(
            "WUZH02 capacity requires 128 cores and 500000 MiB"
        ) from exc
    if memory_mib < 500_000:
        raise ValueError("WUZH02 capacity requires 128 cores and 500000 MiB")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m challenge15.cluster_profile")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("verify", "get"):
        child = commands.add_parser(command)
        child.add_argument("--profile", required=True)
        if command == "verify":
            child.add_argument("--minimum-cores", type=int, default=1)
            child.add_argument("--minimum-memory-mib", type=int, default=1)
        else:
            child.add_argument("--field", required=True)
    args = parser.parse_args(argv)
    profile = load_profile(args.profile)
    if args.command == "verify":
        if profile.threads < args.minimum_cores:
            parser.error("profile has insufficient audited cores")
        memory = int(str(profile.scheduler["mem"]).removesuffix("M"))
        if memory < args.minimum_memory_mib:
            parser.error("profile has insufficient audited memory")
        return 0
    aliases = {
        "project_root": profile.project_root,
        "results_root": profile.results_root,
    }
    value = aliases.get(args.field, profile.to_payload().get(args.field))
    if value is None:
        parser.error("unknown profile field")
    print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
