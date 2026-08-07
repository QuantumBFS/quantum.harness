#!/usr/bin/env python3
"""Audit the local cluster's dynamic CPU/GPU project constraints."""

from __future__ import annotations

import argparse
import getpass
import json
import re
import shlex
import subprocess
from typing import Any


GPU_ALLOC_PATTERN = re.compile(r"(?:^|,)gres/gpu(?::[^:,()]+)?:([0-9]+)")


def remote(ssh_alias: str, command: str) -> str:
    return subprocess.run(
        ["ssh", ssh_alias, command],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def parse_nodes(payload: str) -> dict[str, dict[str, int]]:
    nodes: dict[str, dict[str, int]] = {}
    for line in payload.splitlines():
        if not line.strip():
            continue
        fields = {
            key: value
            for key, value in re.findall(r"(NodeName|CPUAlloc|CPUTot)=([^ ]+)", line)
        }
        cfg_match = re.search(r"CfgTRES=([^ ]+)", line)
        alloc_match = re.search(r"AllocTRES=(.*?) CapWatts=", line)
        if not fields or cfg_match is None or alloc_match is None:
            raise ValueError(f"cannot parse scontrol node row: {line}")
        configured_gpu = sum(
            int(value)
            for value in re.findall(r"(?:^|,)gres/gpu=([0-9]+)", cfg_match.group(1))
        )
        allocated_gpu = sum(
            int(value)
            for value in re.findall(
                r"(?:^|,)gres/gpu=([0-9]+)", alloc_match.group(1)
            )
        )
        nodes[fields["NodeName"]] = {
            "total_cpu": int(fields["CPUTot"]),
            "allocated_cpu": int(fields["CPUAlloc"]),
            "total_gpu": configured_gpu,
            "allocated_gpu": allocated_gpu,
        }
    return nodes


def parse_running_jobs(payload: str) -> tuple[int, int, int]:
    allocated_cpu = 0
    allocated_gpu = 0
    gpu_tasks = 0
    for line in payload.splitlines():
        if not line.strip():
            continue
        cpu_field, tres_field = line.split("|", 1)
        allocated_cpu += int(cpu_field)
        gpu_counts = [
            int(match) for match in GPU_ALLOC_PATTERN.findall(tres_field)
        ]
        if gpu_counts:
            allocated_gpu += sum(gpu_counts)
            gpu_tasks += 1
    return allocated_cpu, allocated_gpu, gpu_tasks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ssh", default="ws4")
    parser.add_argument("--user", default=getpass.getuser())
    parser.add_argument("--reserve-cpus-per-free-gpu", type=int, default=4)
    parser.add_argument("--maximum-gpu-tasks", type=int, default=4)
    parser.add_argument("--planned-cpus", type=int, default=0)
    parser.add_argument("--planned-gpus", type=int, default=0)
    parser.add_argument("--planned-gpu-tasks", type=int, default=0)
    parser.add_argument("--planned-node")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    node_payload = remote(args.ssh, "scontrol show node -o")
    job_payload = remote(
        args.ssh,
        f"squeue -u {shlex.quote(args.user)} -h -t R -o '%C|%b'",
    )
    nodes = parse_nodes(node_payload)
    _, _, gpu_tasks = parse_running_jobs(job_payload)
    if args.planned_cpus or args.planned_gpus:
        if not args.planned_node:
            raise ValueError("--planned-node is required for a planned allocation")
        if args.planned_node not in nodes:
            raise ValueError(f"unknown planned node {args.planned_node}")
        nodes[args.planned_node]["allocated_cpu"] += args.planned_cpus
        nodes[args.planned_node]["allocated_gpu"] += args.planned_gpus
    projected_gpu_tasks = gpu_tasks + args.planned_gpu_tasks
    node_rows: dict[str, dict[str, Any]] = {}
    for name, node in nodes.items():
        free_cpu = node["total_cpu"] - node["allocated_cpu"]
        free_gpu = node["total_gpu"] - node["allocated_gpu"]
        required = args.reserve_cpus_per_free_gpu * free_gpu
        node_rows[name] = {
            **node,
            "free_cpu": free_cpu,
            "free_gpu": free_gpu,
            "required_reserved_cpu": required,
            "passes": (
                free_cpu >= required
                and free_cpu >= 0
                and free_gpu >= 0
            ),
        }
    gates = {
        "per_node_cpu_reservation": all(
            row["passes"] for row in node_rows.values()
        ),
        "gpu_task_limit": projected_gpu_tasks <= args.maximum_gpu_tasks,
    }
    result: dict[str, Any] = {
        "nodes": node_rows,
        "total_cpu": sum(row["total_cpu"] for row in node_rows.values()),
        "total_gpu": sum(row["total_gpu"] for row in node_rows.values()),
        "running_allocated_cpu": sum(
            row["allocated_cpu"] for row in node_rows.values()
        ),
        "running_allocated_gpu": sum(
            row["allocated_gpu"] for row in node_rows.values()
        ),
        "user": args.user,
        "user_running_gpu_tasks": gpu_tasks,
        "planned_cpu": args.planned_cpus,
        "planned_gpu": args.planned_gpus,
        "planned_gpu_tasks": args.planned_gpu_tasks,
        "planned_node": args.planned_node,
        "reserve_cpus_per_free_gpu": args.reserve_cpus_per_free_gpu,
        "maximum_gpu_tasks": args.maximum_gpu_tasks,
        "gates": gates,
        "passes": all(gates.values()),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passes"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
