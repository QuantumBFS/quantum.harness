#!/usr/bin/env python3
"""Generate deterministic Challenge 15 report figures from compact evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CPU_RUN = "ee55cd5-n6-r1-2-4-8-cpu-smoke"
DCU_BUNDLE = "2e0614c0643048bf82f56b34746ab2ec18cbabb8ddba6b5e3e947b3ffdba1405"
RANKS = (1, 2, 4, 8)
SEEDS = (0, 1, 2, 3, 4)
TEST_ORDER = (
    "value_parity_sizes_0_2_4_6_8",
    "singular_all_minor_reverse",
    "torch_func_jvp",
    "batched_reverse_and_jvp",
    "bordered_odd_case",
    "second_derivative_rejection",
    "deterministic_replay",
)

INK = "#25313C"
MUTED = "#5D6B76"
GRID = "#D6DEE3"
PAPER = "#FFFFFF"
PANEL = "#F5F7F8"
BLUE = "#0072B2"
ORANGE = "#E69F00"
GREEN = "#009E73"
PURPLE = "#CC79A7"
RED = "#B33A3A"


class ArtifactError(ValueError):
    """Raised when artifact evidence is absent or internally inconsistent."""


@dataclass(frozen=True)
class Evidence:
    manifest_path: Path
    manifest_sha256: str
    source_paths: tuple[str, ...]
    editorial_record_hashes: tuple[str, ...]
    cpu_source_sha: str
    dcu_source_sha: str
    bundle_hash: str
    generated_at: str
    completed: frozenset[tuple[int, int]]
    timings: tuple[tuple[str, float], ...]
    runtime: dict[str, Any]
    peak_memory_bytes: int
    elapsed_seconds: float
    job_elapsed: str


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ArtifactError(f"required artifact is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ArtifactError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ArtifactError(f"expected a JSON object in {path}")
    return value


def require(value: bool, message: str) -> None:
    if not value:
        raise ArtifactError(message)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_payload_hash(document: dict[str, Any], path: Path) -> None:
    payload = document.get("payload")
    expected = document.get("payload_sha256")
    require(isinstance(payload, dict), f"{path}: payload must be an object")
    require(isinstance(expected, str) and len(expected) == 64, f"{path}: invalid payload_sha256")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    require(hashlib.sha256(encoded).hexdigest() == expected, f"{path}: payload_sha256 mismatch")


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PACKAGE_ROOT / "report_assets" / "challenge15-report-evidence.json"
FAILED_DCU_BUNDLE = "4f591a485b9e286948e03d6636523fe5bb5b76c451c0c64d349b62bdc3899f7b"
EDITORIAL_SOURCE_PATHS = (
    "README.md",
    "DESIGN.md",
    "src/challenge15/carriers.py",
    "src/challenge15/projector.py",
    "src/challenge15/model.py",
    "src/challenge15/chiral_source.py",
    "src/challenge15/response_operator.py",
    "src/challenge15/spectral_response.py",
    "src/challenge15/torch_projector.py",
    "production/runtime/dcu25.04-runtime-lock.json",
)
ARCHIVED_REVIEW_RECORDS = (
    {
        "id": "chiral-task-11-report",
        "logical_path": "<WORKTREE_ROOT>/.superpowers/sdd/task-11-chiral-report.md",
        "sha256": "17957dfdc26490585d39d6caba9e5a0849820da83fc27e581388e41a3ac524e0",
    },
    {
        "id": "chiral-progress",
        "logical_path": "<WORKTREE_ROOT>/.superpowers/sdd/chiral-response-progress.md",
        "sha256": "33a78245c3e9acb38c6b0513f023205ec47ba7ae97bdc270248e9461aff8b222",
    },
    {
        "id": "chiral-task-11-review-diff",
        "logical_path": "<WORKTREE_ROOT>/.superpowers/sdd/task-11-chiral-review.diff",
        "sha256": "921e00eb513f84029ab8ce56d18dde274823e4f3d69ada2f80887d65e28f6c0f",
    },
    {
        "id": "dcu-progress",
        "logical_path": "<WORKTREE_ROOT>/.superpowers/sdd/dcu-backend-progress.md",
        "sha256": "ffaf060f0cdfd70839ef078c510d55d785db3e0e2a82a9f5e70a312d7fa1f4d7",
    },
    {
        "id": "torch-projector-task-7-independent-review",
        "logical_path": None,
        "sha256": "9f6983467cd65f28ddc4dc2faf25cea0575ec84bb6d84d10141c88f7551e357c",
    },
)


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def manifest_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "payload": payload,
        "payload_sha256": hashlib.sha256(canonical_json(payload)).hexdigest(),
        "schema": "challenge15.report-evidence-envelope.v1",
    }


def validate_download_hashes(directory: Path, verification: dict[str, Any]) -> dict[str, str]:
    hashes = verification.get("download_sha256")
    require(isinstance(hashes, dict) and hashes, f"{directory}: missing download_sha256")
    for name, expected in hashes.items():
        require(isinstance(name, str) and isinstance(expected, str), f"{directory}: invalid download hash")
        require(sha256_file(directory / name) == expected, f"{directory / name}: download SHA256 mismatch")
    return dict(sorted(hashes.items()))


def collect_dcu_bundle(root: Path, bundle: str, *, successor: bool) -> dict[str, Any]:
    directory = root / "dcu-task5-smoke" / bundle
    output = load_json(directory / "smoke-output.json")
    receipt = load_json(directory / "receipt.json")
    verification = load_json(directory / "local-verification.json")
    accounting = (directory / "slurm-accounting.txt").read_text(encoding="utf-8").splitlines()
    accounting_fields = accounting[0].split("|") if accounting else []
    require(len(accounting_fields) >= 11, f"{directory}: malformed Slurm accounting")
    download_sha256 = validate_download_hashes(directory, verification)
    require(receipt.get("job_id") == verification.get("job_id"), f"{directory}: job ID mismatch")
    require(receipt.get("status") == output.get("status"), f"{directory}: status mismatch")
    require(receipt.get("hashes", {}).get("output_sha256") == download_sha256["smoke-output.json"], f"{directory}: output hash mismatch")
    require(receipt.get("hashes", {}).get("source_sha256") == output.get("hashes", {}).get("source_sha256"), f"{directory}: source hash mismatch")
    require(receipt.get("hashes", {}).get("sif_sha256") == output.get("hashes", {}).get("sif_sha256"), f"{directory}: SIF hash mismatch")
    if successor:
        require(receipt.get("job_id") == "719801" and output.get("status") == "PASS", "successful DCU evidence mismatch")
        require(verification.get("all_checks_pass") is True, "successful local verification failed")
        require([item.get("name") for item in output.get("tests", [])] == list(TEST_ORDER), "unexpected DCU test order")
        require(all(item.get("status") == "PASS" for item in output["tests"]), "successful DCU test did not pass")
        require(accounting and "|COMPLETED|0:0|00:00:58|" in accounting[0], "successful Slurm accounting mismatch")
    else:
        require(receipt.get("job_id") == "719643" and output.get("status") == "FAIL", "failed DCU predecessor mismatch")
        require(verification.get("all_hash_checks_pass") is True, "failed predecessor hash verification failed")
    return {
        "bundle_content_hash": bundle,
        "created_unix": receipt["created_unix"],
        "driver_exit_code": receipt["driver_exit_code"],
        "elapsed_seconds": output["elapsed_seconds"],
        "error_message": output.get("error", {}).get("message"),
        "file_sha256": download_sha256,
        "hashes": receipt["hashes"],
        "job_id": receipt["job_id"],
        "lineage": receipt.get("lineage"),
        "peak_device_memory_bytes": output.get("peak_device_memory_bytes"),
        "python": output.get("facts", {}).get("python"),
        "runtime": output.get("facts", {}).get("runtime"),
        "slurm_accounting": {
            "allocated_dcu": 1,
            "cpus": int(accounting_fields[9]),
            "elapsed": accounting_fields[7],
            "exit_code": accounting_fields[6],
            "memory": accounting_fields[8],
            "state": accounting_fields[5],
        },
        "status": output["status"],
        "tests": [{"name": item["name"], "status": item["status"]} for item in output.get("tests", [])],
        "timings_seconds": output.get("timings_seconds", {}),
    }


def build_manifest_payload(artifact_root: Path) -> dict[str, Any]:
    artifact_root = artifact_root.resolve()
    cpu_dir = artifact_root / CPU_RUN
    cpu_results: list[dict[str, Any]] = []
    source_revisions: set[str] = set()
    source_hash_sets: list[dict[str, str]] = []
    fingerprint_digests: set[str] = set()
    fingerprint_source_sets: list[dict[str, str]] = []
    for seed in SEEDS:
        path = cpu_dir / f"seed-{seed}" / "result.json"
        document = load_json(path)
        validate_payload_hash(document, path)
        require(document.get("schema") == "challenge15.artifact.v1", f"{path}: bad envelope schema")
        payload = document["payload"]
        config = payload.get("configuration", {})
        require(payload.get("schema") == "challenge15.train-result.v1", f"{path}: bad result schema")
        require(payload.get("production_accepted") is False, f"{path}: expected unaccepted smoke")
        require(payload.get("acceptance_status") == "pending exact evaluation and all production gates", f"{path}: bad acceptance status")
        require(config.get("particles") == 6 and config.get("ranks") == list(RANKS), f"{path}: N/rank mismatch")
        require(config.get("seeds") == [seed] and config.get("steps") == 1, f"{path}: seed/step mismatch")
        records: list[dict[str, Any]] = []
        for record in payload.get("records", []):
            step = record.get("steps", [])
            require(record.get("rank") in RANKS and record.get("seed") == seed, f"{path}: record identity mismatch")
            require(len(step) == 1 and step[0].get("diagnostic_parameter_state") == "pre_update", f"{path}: not one pre-update step")
            require(step[0].get("acceptance_rate_l0") is None and step[0].get("acceptance_rate_l2") is None, f"{path}: acceptance rate unexpectedly present")
            records.append(
                {
                    "diagnostic_parameter_state": "pre_update",
                    "energy_l0": step[0]["energy_l0"],
                    "energy_l0_display_4dp": f'{step[0]["energy_l0"]:.4f}',
                    "energy_l2": step[0]["energy_l2"],
                    "energy_l2_display_4dp": f'{step[0]["energy_l2"]:.4f}',
                    "rank": record["rank"],
                    "seed": seed,
                    "steps": 1,
                }
            )
        require([record["rank"] for record in records] == list(RANKS), f"{path}: incomplete rank records")
        expected_completed = [[rank, seed] for rank in RANKS]
        require(payload.get("completed") == expected_completed, f"{path}: completion mismatch")
        provenance = payload["code_provenance"]
        fingerprint = payload["execution_fingerprint"]
        source_revisions.add(provenance["git_revision"])
        source_hash_sets.append(provenance["source_hashes"])
        fingerprint_digests.add(fingerprint["digest"])
        fingerprint_source_sets.append(fingerprint["source_hashes"])
        cpu_results.append(
            {
                "acceptance_status": payload["acceptance_status"],
                "completed": expected_completed,
                "payload_sha256": document["payload_sha256"],
                "production_accepted": False,
                "records": records,
                "result_file_sha256": sha256_file(path),
                "runtime": payload["runtime_provenance"],
                "seed": seed,
                "telemetry": {
                    "elapsed_wall_seconds": payload["telemetry"]["elapsed_wall_seconds"],
                    "peak_rss_mib": payload["telemetry"]["peak_rss_mib"],
                },
            }
        )
    require(len(source_revisions) == 1 and len(fingerprint_digests) == 1, "CPU provenance disagrees")
    require(all(item == source_hash_sets[0] for item in source_hash_sets), "CPU source hashes disagree")
    require(all(item == fingerprint_source_sets[0] for item in fingerprint_source_sets), "CPU fingerprint sources disagree")

    successful = collect_dcu_bundle(artifact_root, DCU_BUNDLE, successor=True)
    failed = collect_dcu_bundle(artifact_root, FAILED_DCU_BUNDLE, successor=False)
    require(successful["lineage"]["parent_bundle_content_hash"] == FAILED_DCU_BUNDLE, "DCU parent bundle mismatch")
    require(successful["lineage"]["parent_job_id"] == failed["job_id"], "DCU parent job mismatch")
    require(successful["lineage"]["parent_receipt_sha256"] == failed["file_sha256"]["receipt.json"], "DCU parent receipt mismatch")
    created = successful["created_unix"]
    generated_at = dt.datetime.fromtimestamp(created, tz=dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    runtime_lock_path = PACKAGE_ROOT / "production/runtime/dcu25.04-runtime-lock.json"
    runtime_lock = load_json(runtime_lock_path)
    editorial_sources = [
        {"path": path, "sha256": sha256_file(PACKAGE_ROOT / path)}
        for path in EDITORIAL_SOURCE_PATHS
    ]
    return {
        "cpu": {
            "execution_fingerprint": {
                "digest": next(iter(fingerprint_digests)),
                "policy": document["payload"]["execution_fingerprint"]["policy"],
                "runtime": document["payload"]["execution_fingerprint"]["runtime"],
                "schema": document["payload"]["execution_fingerprint"]["schema"],
            },
            "git_revision": next(iter(source_revisions)),
            "results": cpu_results,
            "run_id": CPU_RUN,
            "source_files_sha256": dict(sorted(fingerprint_source_sets[0].items())),
        },
        "dcu": {
            "failed_predecessor": failed,
            "successful_successor": successful,
        },
        "deterministic_receipt_timestamp": {
            "created_unix": created,
            "generated_at_utc": generated_at,
        },
        "editorial_status": {
            "facts": {
                "chiral_response": "IMPLEMENTED; production response acceptance PENDING",
                "scientific_acceptance": "PENDING",
                "software_nodes": "IMPLEMENTED means implementation present, not production acceptance",
                "torch_dcu_pfaffian": "SMOKE-ONLY",
                "torch_projector_checkpoint_jvp_gate": "BLOCKED",
            },
            "review_records": list(ARCHIVED_REVIEW_RECORDS),
            "source_files": editorial_sources,
            "status_labels_are_editorial_constants": True,
        },
        "manifest_version": 1,
        "runtime_lock": {
            "file_sha256": sha256_file(runtime_lock_path),
            "runtime": runtime_lock["runtime"],
            "status": runtime_lock["status"],
            "validation_job_id": runtime_lock["validation"]["job_id"],
        },
        "schema": "challenge15.report-evidence.v1",
        "trust_boundary": {
            "compact_manifest": "Reproduces report figures and checks report consistency.",
            "raw_artifacts": "Required for full scientific re-verification and optional independent audit.",
        },
    }


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json(manifest_envelope(payload)) + b"\n")


def load_manifest(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    document = json.loads(raw)
    require(document.get("schema") == "challenge15.report-evidence-envelope.v1", "bad report manifest envelope")
    require(set(document) == {"payload", "payload_sha256", "schema"}, "bad report manifest fields")
    require(raw == canonical_json(document) + b"\n", "report manifest is not canonical JSON")
    payload = document.get("payload")
    require(isinstance(payload, dict), "report manifest payload must be an object")
    require(hashlib.sha256(canonical_json(payload)).hexdigest() == document.get("payload_sha256"), "report manifest self-hash mismatch")
    require(payload.get("schema") == "challenge15.report-evidence.v1" and payload.get("manifest_version") == 1, "unsupported report manifest")
    for item in payload["editorial_status"]["source_files"]:
        source = PACKAGE_ROOT / item["path"]
        require(source.is_file() and sha256_file(source) == item["sha256"], f"editorial source hash mismatch: {item['path']}")
    return payload, hashlib.sha256(raw).hexdigest()


def evidence_from_manifest(path: Path) -> Evidence:
    payload, manifest_sha = load_manifest(path)
    cpu = payload["cpu"]
    success = payload["dcu"]["successful_successor"]
    completed = {
        (result["seed"], record["rank"])
        for result in cpu["results"]
        for record in result["records"]
    }
    timings = tuple((name, float(success["timings_seconds"][name])) for name in TEST_ORDER)
    source_paths = tuple(
        [f"<ARTIFACT_ROOT>/{CPU_RUN}/seed-{seed}/result.json" for seed in SEEDS]
        + [
            f"<ARTIFACT_ROOT>/dcu-task5-smoke/{DCU_BUNDLE}/{name}"
            for name in ("config.json", "smoke-output.json", "receipt.json", "local-verification.json", "slurm-accounting.txt")
        ]
        + [item["path"] for item in payload["editorial_status"]["source_files"]]
    )
    return Evidence(
        manifest_path=path.resolve(),
        manifest_sha256=manifest_sha,
        source_paths=source_paths,
        editorial_record_hashes=tuple(item["sha256"] for item in payload["editorial_status"]["review_records"]),
        cpu_source_sha=cpu["git_revision"],
        dcu_source_sha=success["hashes"]["source_sha256"],
        bundle_hash=success["bundle_content_hash"],
        generated_at=payload["deterministic_receipt_timestamp"]["generated_at_utc"],
        completed=frozenset(completed),
        timings=timings,
        runtime=success["runtime"],
        peak_memory_bytes=int(success["peak_device_memory_bytes"]),
        elapsed_seconds=float(success["elapsed_seconds"]),
        job_elapsed="00:00:58",
    )


def audit_raw_artifacts(root: Path, manifest_payload: dict[str, Any]) -> None:
    rebuilt = build_manifest_payload(root)
    for section in ("cpu", "dcu", "deterministic_receipt_timestamp", "runtime_lock"):
        require(rebuilt[section] == manifest_payload[section], f"raw artifact audit mismatch: {section}")


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def text(x: float, y: float, value: object, cls: str = "", anchor: str = "start") -> str:
    return f'<text x="{x:g}" y="{y:g}" class="{cls}" text-anchor="{anchor}">{esc(value)}</text>'


def multiline(x: float, y: float, lines: tuple[str, ...], cls: str = "", anchor: str = "start", step: int = 20) -> str:
    spans = "".join(
        f'<tspan x="{x:g}" dy="{0 if index == 0 else step}">{esc(line)}</tspan>'
        for index, line in enumerate(lines)
    )
    return f'<text x="{x:g}" y="{y:g}" class="{cls}" text-anchor="{anchor}">{spans}</text>'


def rect(x: float, y: float, width: float, height: float, cls: str, radius: int = 10) -> str:
    return f'<rect x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" rx="{radius}" class="{cls}"/>'


def status_pill(x: int, y: int, label: str, kind: str) -> str:
    widths = {"IMPLEMENTED": 116, "SMOKE-ONLY": 116, "PENDING": 88, "BLOCKED": 88}
    width = widths[label]
    return (
        f'<g aria-label="Status: {esc(label.lower())}">'
        f'<rect x="{x}" y="{y}" width="{width}" height="24" rx="12" class="status {kind}"/>'
        f'{text(x + width / 2, y + 17, label, "pill", "middle")}</g>'
    )


def metadata(evidence: Evidence, title_value: str, sources: tuple[str, ...]) -> str:
    source_elements = "".join(f"<source>{esc(path)}</source>" for path in sources)
    review_elements = "".join(f"<review-record-sha256>{esc(value)}</review-record-sha256>" for value in evidence.editorial_record_hashes)
    return (
        f"<metadata><report>"
        f"<title>{esc(title_value)}</title>"
        f"<generated>{esc(evidence.generated_at)}</generated>"
        f"<evidence-manifest-sha256>{evidence.manifest_sha256}</evidence-manifest-sha256>"
        f"<bundle-hash>{evidence.bundle_hash}</bundle-hash>"
        f"<dcu-source-sha256>{evidence.dcu_source_sha}</dcu-source-sha256>"
        f"<cpu-source-git-sha>{evidence.cpu_source_sha}</cpu-source-git-sha>"
        f"<sources>{source_elements}</sources>"
        f"<editorial-review-records>{review_elements}</editorial-review-records>"
        f"</report></metadata>"
    )


def svg_header(width: int, height: int, title_value: str, description: str, metadata_value: str) -> list[str]:
    return [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc" viewBox="0 0 {width} {height}">',
        f"<title id=\"title\">{esc(title_value)}</title>",
        f"<desc id=\"desc\">{esc(description)}</desc>",
        metadata_value,
        """<style>
text { font-family: sans-serif; fill: #25313C; }
.title { font-size: 30px; font-weight: 700; }
.subtitle { font-size: 15px; fill: #5D6B76; }
.section { font-size: 19px; font-weight: 700; }
.label { font-size: 15px; font-weight: 700; }
.body { font-size: 13px; }
.small { font-size: 11px; fill: #5D6B76; }
.mono { font-family: monospace; font-size: 10px; fill: #5D6B76; }
.pill { font-size: 10px; font-weight: 700; fill: #FFFFFF; letter-spacing: .7px; }
.panel { fill: #F5F7F8; stroke: #D6DEE3; stroke-width: 1.5; }
.node { fill: #FFFFFF; stroke: #0072B2; stroke-width: 2; }
.branch { fill: #FFFFFF; stroke: #5D6B76; stroke-width: 1.5; }
.status.implemented { fill: #009E73; }
.status.smoke { fill: #0072B2; }
.status.pending { fill: #E69F00; }
.status.blocked { fill: #B33A3A; }
.flow { fill: none; stroke: #5D6B76; stroke-width: 2; marker-end: url(#arrow); }
.branch-flow { fill: none; stroke: #5D6B76; stroke-width: 1.5; stroke-dasharray: 5 4; marker-end: url(#arrow); }
.axis { stroke: #5D6B76; stroke-width: 1; }
.grid { stroke: #D6DEE3; stroke-width: 1; }
</style>""",
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#5D6B76"/></marker></defs>',
        f'<rect width="{width}" height="{height}" fill="{PAPER}"/>',
    ]


def generate_method_flow(evidence: Evidence) -> str:
    title_value = "Challenge 15 method and acceptance flow"
    sources = evidence.source_paths
    parts = svg_header(
        1440,
        900,
        title_value,
        "Architecture from the physical sphere model through exact symmetry projection and shared neural states to evidence and acceptance gates. Branches distinguish implementation present, smoke-only evidence, pending acceptance, and a blocked later Torch JVP gate.",
        metadata(evidence, title_value, sources),
    )
    parts += [
        text(56, 62, title_value, "title"),
        text(56, 88, "Editorial status constants from hashed repository/review records; execution facts from compact artifact evidence", "subtitle"),
        rect(44, 116, 1352, 410, "panel", 14),
        text(66, 150, "Scientific data flow", "section"),
    ]
    nodes = (
        (70, "Physical model", ("ν=1/3 sphere", "N electrons; 2Q=3(N−1)")),
        (326, "LLL Pfaffian carriers", ("Holomorphic spinors", "antisymmetric carrier bank")),
        (582, "Exact SU(2) projection", ("M=0: L=0 and L=2", "full L=2 multiplet")),
        (838, "Shared L=0 / L=2 NQS", ("one parameter tree", "rank χ=1,2,4,8")),
        (1094, "Evaluation & acceptance", ("CPU/JAX • ED • VMC", "exact gates and provenance")),
    )
    for index, (x, heading, body) in enumerate(nodes):
        parts += [rect(x, 188, 220, 138, "node", 12), text(x + 18, 223, heading, "label")]
        parts.append(multiline(x + 18, 252, body, "body", step=22))
        if index < len(nodes) - 1:
            parts.append(f'<path d="M{x + 220} 257 H{x + 250}" class="flow"/>')
    parts += [
        status_pill(88, 287, "IMPLEMENTED", "implemented"),
        status_pill(344, 287, "IMPLEMENTED", "implemented"),
        status_pill(600, 287, "IMPLEMENTED", "implemented"),
        status_pill(856, 287, "IMPLEMENTED", "implemented"),
        status_pill(1112, 287, "PENDING", "pending"),
        f'<path d="M692 326 V370 H282 V404" class="branch-flow"/>',
        f'<path d="M948 326 V370 H720 V404" class="branch-flow"/>',
        rect(100, 404, 364, 96, "branch", 10),
        text(120, 434, "Chiral-response branch", "label"),
        text(120, 459, "Exact spectral contraction and invariant pole grouping", "body"),
        status_pill(330, 464, "IMPLEMENTED", "implemented"),
        rect(536, 404, 394, 96, "branch", 10),
        text(556, 434, "Torch projector branch", "label"),
        text(556, 459, "Exact M=0 / multiplet projection; CPU-focused tests", "body"),
        status_pill(796, 464, "IMPLEMENTED", "implemented"),
        rect(1002, 404, 364, 96, "branch", 10),
        text(1022, 434, "Torch / DCU execution branch", "label"),
        text(1022, 459, "Pfaffian kernel attested on DCU; not full VMC", "body"),
        status_pill(1230, 464, "SMOKE-ONLY", "smoke"),
        f'<path d="M1216 326 V404" class="branch-flow"/>',
        rect(44, 550, 1352, 248, "panel", 14),
        text(66, 586, "Acceptance boundary", "section"),
        rect(70, 612, 300, 94, "branch", 10),
        text(88, 642, "N=6 CPU/JAX evidence", "label"),
        text(88, 667, "5 seeds × 4 ranks; one pre-update step", "body"),
        status_pill(236, 672, "SMOKE-ONLY", "smoke"),
        rect(402, 612, 300, 94, "branch", 10),
        text(420, 642, "ED and exact evaluation", "label"),
        text(420, 667, "No accepted exact-evaluation artifact present", "body"),
        status_pill(596, 672, "PENDING", "pending"),
        rect(734, 612, 300, 94, "branch", 10),
        text(752, 642, "Production VMC gates", "label"),
        text(752, 667, "Optimization, final statistics, all gates", "body"),
        status_pill(928, 672, "PENDING", "pending"),
        rect(1066, 612, 300, 94, "branch", 10),
        text(1084, 642, "Torch projector checkpoint/JVP gate", "label"),
        text(1084, 667, "Required before full Torch/DCU VMC execution", "body"),
        status_pill(1260, 672, "BLOCKED", "blocked"),
        text(70, 742, "Important: the DCU PASS covers seven Torch Pfaffian smoke tests only. It does not attest the full Torch projector/model/VMC path.", "body"),
        text(70, 770, "This blocked gate is the Torch projector checkpoint/JVP path, not the passing Pfaffian JVP primitive in job 719801.", "small"),
        text(56, 832, f"Generated {evidence.generated_at}  •  bundle {evidence.bundle_hash}", "mono"),
        text(56, 850, f"DCU source SHA-256 {evidence.dcu_source_sha}", "mono"),
        text(56, 868, f"CPU source git SHA {evidence.cpu_source_sha}", "mono"),
        text(1384, 850, "Manifest, source and editorial hashes embedded in metadata", "small", "end"),
        "</svg>",
    ]
    return "\n".join(parts) + "\n"


def short_test_name(name: str) -> str:
    labels = {
        "value_parity_sizes_0_2_4_6_8": "value parity (0–8)",
        "singular_all_minor_reverse": "singular reverse",
        "torch_func_jvp": "torch.func JVP",
        "batched_reverse_and_jvp": "batched rev + JVP",
        "bordered_odd_case": "bordered odd",
        "second_derivative_rejection": "2nd-deriv rejection",
        "deterministic_replay": "deterministic replay",
    }
    return labels[name]


def generate_evidence(evidence: Evidence) -> str:
    title_value = "Challenge 15 artifact evidence"
    sources = evidence.source_paths
    parts = svg_header(
        1440,
        980,
        title_value,
        "Evidence dashboard showing complete N=6 CPU smoke coverage and seven measured Torch Pfaffian DCU test timings for job 719801. CPU diagnostic energies are deliberately omitted because they are pre-update smoke diagnostics, not an accepted physical gap.",
        metadata(evidence, title_value, sources),
    )
    parts += [
        text(56, 62, title_value, "title"),
        text(56, 88, "Default source: canonical compact evidence manifest; optional raw-artifact audit available", "subtitle"),
        rect(44, 116, 598, 586, "panel", 14),
        text(66, 152, "N=6 CPU smoke coverage", "section"),
        text(66, 177, "5 seeds × ranks 1, 2, 4, 8 = 20 completed smoke cells", "body"),
    ]
    grid_x, grid_y, cell_w, cell_h = 182, 224, 86, 60
    for column, rank in enumerate(RANKS):
        parts.append(text(grid_x + column * cell_w + cell_w / 2, 208, f"χ={rank}", "label", "middle"))
    for row, seed in enumerate(SEEDS):
        y = grid_y + row * cell_h
        parts.append(text(144, y + 37, f"seed {seed}", "label", "end"))
        for column, rank in enumerate(RANKS):
            x = grid_x + column * cell_w
            require((seed, rank) in evidence.completed, "render requested an incomplete CPU cell")
            parts += [
                f'<rect x="{x}" y="{y}" width="{cell_w - 8}" height="{cell_h - 8}" rx="7" fill="{GREEN}" aria-label="Seed {seed}, rank {rank}: smoke completed"/>',
                text(x + (cell_w - 8) / 2, y + 34, "SMOKE", "pill", "middle"),
            ]
    parts += [
        text(66, 550, "Interpretation boundary", "label"),
        multiline(
            66,
            578,
            (
                "One training step per rank",
                "Diagnostics are pre-update",
                "Acceptance rates absent",
                "production_accepted = false",
                "Exact evaluation and all gates pending",
            ),
            "body",
            step=22,
        ),
        rect(66, 650, 552, 32, "branch", 7),
        text(342, 671, "CPU smoke energies intentionally not plotted as a physical gap", "small", "middle"),
        rect(670, 116, 726, 586, "panel", 14),
        text(692, 152, "DCU job 719801 — seven measured test timings", "section"),
        text(692, 177, "Torch Pfaffian successor smoke • wall-clock seconds per test", "body"),
    ]
    chart_x, chart_y, chart_w, chart_h = 914, 214, 402, 336
    max_tick = 1.2
    for tick in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2):
        x = chart_x + chart_w * tick / max_tick
        parts += [
            f'<line x1="{x:g}" y1="{chart_y}" x2="{x:g}" y2="{chart_y + chart_h}" class="grid"/>',
            text(x, chart_y + chart_h + 22, f"{tick:.1f}", "small", "middle"),
        ]
    parts += [
        f'<line x1="{chart_x}" y1="{chart_y}" x2="{chart_x}" y2="{chart_y + chart_h}" class="axis"/>',
        f'<line x1="{chart_x}" y1="{chart_y + chart_h}" x2="{chart_x + chart_w}" y2="{chart_y + chart_h}" class="axis"/>',
    ]
    bar_h, gap = 26, 20
    for index, (name, value) in enumerate(evidence.timings):
        y = chart_y + index * (bar_h + gap) + 5
        width = chart_w * value / max_tick
        parts += [
            text(chart_x - 14, y + 18, short_test_name(name), "small", "end"),
            f'<rect x="{chart_x}" y="{y}" width="{width:.3f}" height="{bar_h}" rx="4" fill="{BLUE}" aria-label="{esc(short_test_name(name))}: {value:.6f} seconds"/>',
            text(chart_x + width + 8, y + 18, f"{value:.3f} s", "small"),
        ]
    parts += [
        text(chart_x + chart_w / 2, 592, "measured wall-clock time (seconds)", "body", "middle"),
        text(692, 626, "Source: smoke-output.json timings_seconds; all seven statuses PASS.", "small"),
        text(692, 648, "Bars are individual test timings, not a benchmark suite total.", "small"),
        rect(44, 726, 1352, 156, "panel", 14),
        text(66, 762, "DCU runtime facts", "section"),
    ]
    facts = (
        ("Device", f'{evidence.runtime["device_name"]} • {evidence.runtime["tensor_device"]} • count {evidence.runtime["device_count"]}'),
        ("Runtime", f'Torch {evidence.runtime["torch_version"]} • HIP {evidence.runtime["torch_hip_version"]}'),
        ("Numerics", f'{evidence.runtime["complex128"]} • deterministic algorithms'),
        ("Peak device memory", f'{evidence.peak_memory_bytes:,} bytes ({evidence.peak_memory_bytes / 1024:.1f} KiB)'),
        ("Driver elapsed", f"{evidence.elapsed_seconds:.3f} s"),
        ("Slurm job", f"COMPLETED 0:0 • elapsed {evidence.job_elapsed} • 1 DCU"),
    )
    for index, (heading, value) in enumerate(facts):
        column = index % 3
        row = index // 3
        x = 66 + column * 440
        y = 794 + row * 48
        parts += [text(x, y, heading, "label"), text(x, y + 20, value, "body")]
    parts += [
        text(56, 914, f"Generated {evidence.generated_at}  •  bundle {evidence.bundle_hash}", "mono"),
        text(56, 932, f"DCU source SHA-256 {evidence.dcu_source_sha}", "mono"),
        text(56, 950, f"CPU source git SHA {evidence.cpu_source_sha}", "mono"),
        text(1384, 932, "Manifest and audited source paths embedded in metadata", "small", "end"),
        "</svg>",
    ]
    return "\n".join(parts) + "\n"


def write_if_changed(path: Path, content: str) -> None:
    encoded = content.encode("utf-8")
    if path.exists() and path.read_bytes() == encoded:
        return
    path.write_bytes(encoded)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Canonical compact evidence manifest (default: checked-in report asset)",
    )
    parser.add_argument(
        "--artifact-root",
        type=Path,
        help="Optional full .production-results root for independent manifest audit",
    )
    parser.add_argument(
        "--refresh-manifest-from-artifacts",
        action="store_true",
        help="Rebuild --manifest from --artifact-root before generation",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PACKAGE_ROOT / "report_assets",
        help="Directory for generated SVG files",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.refresh_manifest_from_artifacts:
        require(args.artifact_root is not None, "--refresh-manifest-from-artifacts requires --artifact-root")
        write_manifest(args.manifest, build_manifest_payload(args.artifact_root))
        print(f"wrote canonical evidence manifest {args.manifest}")
    manifest_payload, _ = load_manifest(args.manifest)
    if args.artifact_root is not None:
        audit_raw_artifacts(args.artifact_root, manifest_payload)
        print("raw artifact audit matched compact evidence manifest")
    evidence = evidence_from_manifest(args.manifest)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "challenge15-method-flow.svg": generate_method_flow(evidence),
        "challenge15-evidence.svg": generate_evidence(evidence),
    }
    for filename, content in outputs.items():
        require("<image" not in content and "linearGradient" not in content, f"{filename}: forbidden SVG content")
        font_families = re.findall(r"font-family:\s*([^;}]+)", content)
        require(
            all(family.strip() in {"sans-serif", "monospace"} for family in font_families),
            f"{filename}: external font",
        )
        write_if_changed(args.output_dir / filename, content)
        print(f"wrote {args.output_dir / filename}")
    print("validated compact manifest: 5 CPU results, 20 smoke cells, DCU jobs 719801/719643")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
